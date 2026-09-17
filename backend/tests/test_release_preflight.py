from __future__ import annotations

from datetime import datetime, timezone
import hashlib
import io
import json
import os
from pathlib import Path
import shutil
import subprocess
import tarfile

import pytest

import backend.release.preflight as preflight_module
from backend.release.preflight import (
    REMOTE_GATE_NAME,
    IMMUTABLE_TAG_RE,
    METADATA_ALLOWLIST,
    REQUIRED_GATE_COMMANDS,
    PreflightError,
    build_validated_tar_context,
    load_verification_evidence,
    main,
    validate_image_labels,
    validate_release_preflight,
    validate_staged_context,
    validate_tar_context,
)


NOW = datetime(2026, 8, 22, 13, 0, 0, tzinfo=timezone.utc)
MANIFEST_RELATIVE_PATH = Path("backend/release/v7.3.json")
BUILD_EVIDENCE_RELATIVE_PATH = Path(
    "backend/release/verification/v7.3-pre-cloud.json"
)
FINAL_EVIDENCE_RELATIVE_PATH = Path("backend/release/verification/v7.3.json")
EXPECTED_ALLOWLIST = frozenset(
    {
        "backend/release/v7.3.json",
        "backend/release/verification/v7.3-pre-cloud.json",
        "backend/release/verification/v7.3.json",
        "docs/recovery/2026-08-19/current-tree-inventory.json",
        "docs/recovery/2026-08-24/daytona-gpu-smoke.md",
        "docs/recovery/2026-08-24/final-verification-report.md",
        "docs/status/current.md",
    }
)


def _git(root: Path, *args: str, input_text: str | None = None) -> str:
    result = subprocess.run(
        ["git", *args],
        cwd=root,
        check=True,
        capture_output=True,
        text=True,
        input=input_text,
    )
    return result.stdout.strip()


def _write_json(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def _commit_all(root: Path, message: str) -> str:
    _git(root, "add", "--all")
    _git(root, "commit", "-m", message)
    return _git(root, "rev-parse", "HEAD")


def _manifest(source_commit: str, content: bytes) -> dict[str, object]:
    return {
        "schemaVersion": 1,
        "releaseVersion": "v7.3",
        "candidateVersion": "v7.3",
        "runtimeVersion": "v7.3",
        "sourceCommit": source_commit,
        "createdAt": "2026-08-22T12:00:00Z",
        "runtimeOptions": {
            "primary_model": {"artifactId": "primary-model"},
            "auxiliary_ball_model": None,
            "auxiliary_ball_model_profile": None,
            "primary_acquisition_mode": "anchored-player-ranked-context-960",
            "edge_share_repair_profile": None,
            "baseline_guided_rescue_reference": None,
            "proposal_selection_truth_seed": None,
            "reviewed_positive_anchor_seed": None,
        },
        "artifacts": [
            {
                "id": "primary-model",
                "sha256": hashlib.sha256(content).hexdigest(),
                "sizeBytes": len(content),
                "localRelativePath": "artifacts/model.pt",
                "containerPath": "/app/models/model.pt",
                "origin": "external-recovery-archive",
                "retentionClass": "release-essential",
            }
        ],
        "requiredContracts": [
            "video_to_analysis_product_api_v1",
            "video_to_analysis_report_v1",
        ],
    }


def _evidence(
    source_commit: str,
    manifest_sha256: str,
    *,
    verification_commit: str | None = None,
    phase: str = "pre_cloud",
    created_at: str = "2026-08-22T12:30:00Z",
) -> dict[str, object]:
    pre_cloud = phase == "pre_cloud"
    return {
        "schemaVersion": 2,
        "phase": phase,
        "sourceCommit": source_commit,
        "verificationCommit": verification_commit or source_commit,
        "manifestSha256": manifest_sha256,
        "createdAt": created_at,
        "toolVersions": {"python": "3.11.9", "pytest": "8.4.1"},
        "gates": [
            {
                "name": name,
                "command": command,
                "status": "pending" if pre_cloud and name == REMOTE_GATE_NAME else "passed",
                "completedAt": (
                    None
                    if pre_cloud and name == REMOTE_GATE_NAME
                    else "2026-08-22T12:19:00Z" if name == REMOTE_GATE_NAME
                    else "2026-08-22T12:20:00Z"
                ),
                "logSha256": (
                    None if pre_cloud and name == REMOTE_GATE_NAME else "e" * 64
                ),
            }
            for name, command in REQUIRED_GATE_COMMANDS.items()
        ],
        "overallPassed": not pre_cloud,
        "remoteExecution": None if pre_cloud else {
            "sourceCommit": source_commit,
            "verificationCommit": verification_commit or source_commit,
            "manifestSha256": manifest_sha256,
            "workerContextSha256": "f" * 64,
            "sdkVersion": "0.207.0", "imageDigest": "docker.io/pytorch/pytorch@sha256:417bd75df6365104c283ea4c1651fb3530d9eb5a4c2fafa51943cff2a94e6385",
            "requestedTarget": "us", "requestedGpuOrder": ["RTX-PRO-6000", "H100"],
            "observedGpu": "RTX-PRO-6000", "sandboxId": "sandbox-123",
            "createdAt": "2026-08-22T12:00:00Z", "startedAt": "2026-08-22T12:01:00Z",
            "completedAt": "2026-08-22T12:18:00Z", "deletedAt": "2026-08-22T12:19:00Z",
            "commandResults": [{"command": "nvidia-smi", "exitCode": 0, "stdout": "ok", "stderr": ""}],
            "uploads": [{"name": "context", "sha256": "c" * 64, "sizeBytes": 1}],
            "downloads": [{"name": "result", "sha256": "d" * 64, "sizeBytes": 1}],
            "cleanupAttempts": 1, "deletionConfirmed": True,
            "runpodMutationOccurred": False, "registryMutationOccurred": False,
        },
    }


def _gate(payload: dict[str, object], name: str) -> dict[str, object]:
    return next(gate for gate in payload["gates"] if gate["name"] == name)  # type: ignore[union-attr]


@pytest.fixture
def release_repo(tmp_path: Path) -> dict[str, object]:
    root = tmp_path / "repo"
    root.mkdir()
    _git(root, "init", "-q")
    _git(root, "config", "user.email", "release-tests@example.invalid")
    _git(root, "config", "user.name", "Release Tests")
    (root / ".gitignore").write_text("artifacts/\n", encoding="utf-8")
    from backend.app.daytona_worker_image import WORKER_CONTEXT_MEMBERS

    project_root = Path(__file__).parents[2]
    for relative in set(WORKER_CONTEXT_MEMBERS).union({
        ".dockerignore",
        "lap.py",
        "backend/app/release_manifest.py",
        "backend/app/remote_contracts.py",
        "backend/app/runtime_options.py",
        "backend/release/__init__.py",
        "backend/release/evidence.py",
        "backend/release/daytona_policy.py",
        "backend/release/daytona-v7.3.json",
        "backend/release/preflight.py",
        "backend/daytona_worker/Dockerfile",
        "backend/daytona_worker/requirements.txt",
        "backend/daytona_worker/requirements.lock",
    }) - {"backend/release/v7.3.json"}:
        source = project_root / relative
        destination = root / relative
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, destination)
    product = root / "backend/app/main.py"
    product.parent.mkdir(parents=True, exist_ok=True)
    product.write_text("PRODUCT = 'v7.3'\n", encoding="utf-8")
    source_commit = _commit_all(root, "source")

    content = b"verified-model"
    artifact = root / "artifacts/model.pt"
    artifact.parent.mkdir(parents=True)
    artifact.write_bytes(content)
    manifest_path = root / MANIFEST_RELATIVE_PATH
    _write_json(manifest_path, _manifest(source_commit, content))
    manifest_sha256 = hashlib.sha256(manifest_path.read_bytes()).hexdigest()
    verification_commit = _commit_all(root, "release manifest")
    build_evidence_path = root / BUILD_EVIDENCE_RELATIVE_PATH
    final_evidence_path = root / FINAL_EVIDENCE_RELATIVE_PATH
    _write_json(
        build_evidence_path,
        _evidence(
            source_commit, manifest_sha256, verification_commit=verification_commit
        ),
    )
    final_evidence = _evidence(
        source_commit, manifest_sha256,
        verification_commit=verification_commit, phase="final",
    )
    from backend.app.daytona_worker_image import repository_worker_context_sha256
    final_evidence["remoteExecution"]["workerContextSha256"] = (  # type: ignore[index]
        repository_worker_context_sha256(root)
    )
    _write_json(final_evidence_path, final_evidence)
    _commit_all(root, "release metadata")
    return {
        "root": root,
        "source_commit": source_commit,
        "verification_commit": verification_commit,
        "manifest_path": manifest_path,
        "manifest_sha256": manifest_sha256,
        "build_evidence_path": build_evidence_path,
        "final_evidence_path": final_evidence_path,
        "artifact": artifact,
    }


def _validate(
    repo: dict[str, object],
    *,
    mode: str = "build-only",
    image_tag: str | None = None,
    now: datetime = NOW,
) -> object:
    source_commit = str(repo["source_commit"])
    digest = str(repo["manifest_sha256"])
    evidence_key = "build_evidence_path" if mode == "build-only" else "final_evidence_path"
    return validate_release_preflight(
        repo_root=Path(repo["root"]),
        manifest_path=Path(repo["manifest_path"]),
        evidence_path=Path(repo[evidence_key]),
        mode=mode,
        image_tag=image_tag or f"v7.3-{source_commit}-{digest[:12]}",
        now=now,
    )


def test_metadata_allowlist_is_exactly_the_plan_contract() -> None:
    assert METADATA_ALLOWLIST == EXPECTED_ALLOWLIST


def test_valid_pre_cloud_accepts_metadata_only_descendant(release_repo: dict[str, object]) -> None:
    result = _validate(release_repo)

    assert release_repo["source_commit"] != release_repo["verification_commit"]
    assert result.source_commit == release_repo["source_commit"]
    assert result.manifest_sha256 == release_repo["manifest_sha256"]
    assert result.artifacts == (("primary-model", Path(release_repo["artifact"]), "/app/models/model.pt"),)


def test_preflight_allows_the_local_untracked_verifier_receipt(
    release_repo: dict[str, object],
) -> None:
    receipt = Path(release_repo["root"]) / ".verification/receipt.json"
    receipt.parent.mkdir(); receipt.write_text("{}\n", encoding="utf-8")

    _validate(release_repo)


@pytest.mark.parametrize("variable", ["GIT_DIR", "GIT_WORK_TREE", "GIT_INDEX_FILE"])
def test_preflight_git_helpers_ignore_repository_redirection(
    release_repo: dict[str, object], monkeypatch: pytest.MonkeyPatch, variable: str
) -> None:
    monkeypatch.setenv(variable, "/definitely/not/the/repository")
    _validate(release_repo)


def test_preflight_rejects_untracked_file_hidden_by_inherited_global_excludes(
    release_repo: dict[str, object], tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    root = Path(release_repo["root"])
    hidden = root / "hidden.py"
    hidden.write_text("raise SystemExit\n")
    excludes = tmp_path / "global-excludes"
    excludes.write_text("hidden.py\n")
    config = tmp_path / "global-gitconfig"
    _git(root, "config", "--file", str(config), "core.excludesFile", str(excludes))
    monkeypatch.setenv("GIT_CONFIG_GLOBAL", str(config))

    with pytest.raises(PreflightError, match="worktree.*hidden.py"):
        _validate(release_repo)


@pytest.mark.parametrize("flag,label", [
    ("--assume-unchanged", "assume-unchanged"),
    ("--skip-worktree", "skip-worktree"),
])
def test_preflight_rejects_hidden_index_flags(
    release_repo: dict[str, object], flag: str, label: str
) -> None:
    root = Path(release_repo["root"])
    path = "backend/app/main.py"
    _git(root, "update-index", flag, "--", path)

    with pytest.raises(PreflightError, match=rf"{label}.*{path}"):
        _validate(release_repo)


def test_git_archive_receives_only_the_sanitized_git_environment(
    release_repo: dict[str, object], monkeypatch: pytest.MonkeyPatch
) -> None:
    inherited = {
        "GIT_CONFIG_GLOBAL": "/secret/global-config",
        "GIT_OBJECT_DIRECTORY": "/secret/objects",
    }
    for key, value in inherited.items():
        monkeypatch.setenv(key, value)
    real_popen = preflight_module.subprocess.Popen
    observed = []

    def capture_popen(*args, **kwargs):
        observed.append(kwargs.get("env"))
        return real_popen(*args, **kwargs)

    monkeypatch.setattr(preflight_module.subprocess, "Popen", capture_popen)
    with preflight_module._git_archive_stream(
        Path(release_repo["root"]), str(release_repo["source_commit"])
    ) as stream:
        assert stream.read()

    assert len(observed) == 1
    assert observed[0]["GIT_NO_REPLACE_OBJECTS"] == "1"
    assert set(key for key in observed[0] if key.startswith("GIT_")) == {
        "GIT_NO_REPLACE_OBJECTS"
    }


def test_receipt_generated_pre_cloud_evidence_passes_with_distinct_source_and_verifier(
    release_repo: dict[str, object], tmp_path: Path
) -> None:
    from backend.scripts.write_verification_evidence import (
        record_verifier_success,
        write_verification_evidence,
    )

    root = Path(release_repo["root"])
    logs = root / ".verification/logs"; logs.mkdir(parents=True)
    with (root / ".git/info/exclude").open("a", encoding="utf-8") as stream:
        stream.write(".verification/logs/\n")
    base = datetime(2026, 8, 22, 12, tzinfo=timezone.utc).timestamp()
    for index, name in enumerate(tuple(REQUIRED_GATE_COMMANDS)[:-1]):
        log = logs / f"{name}.log"; log.write_text(f"{name} passed\n")
        os.utime(log, (base + index, base + index))
    receipt = record_verifier_success(
        root, now=datetime(2026, 8, 22, 12, 30, tzinfo=timezone.utc)
    )
    generated = tmp_path / "generated.json"
    evidence = write_verification_evidence(
        generated, phase="pre_cloud", repo_root=root,
        now=datetime(2026, 8, 22, 12, 31, tzinfo=timezone.utc),
    )
    Path(release_repo["build_evidence_path"]).write_bytes(generated.read_bytes())
    _git(root, "add", BUILD_EVIDENCE_RELATIVE_PATH.as_posix())
    _git(root, "commit", "-m", "generated verifier-bound evidence")

    assert evidence.source_commit == release_repo["source_commit"]
    assert evidence.verification_commit == receipt["repositoryCommit"]
    _validate(release_repo)


def test_valid_final_evidence_accepts_metadata_only_descendant(release_repo: dict[str, object]) -> None:
    assert _validate(release_repo, mode="deploy").evidence_phase == "final"


def test_final_preflight_rejects_worker_context_not_used_by_remote_smoke(
    release_repo: dict[str, object],
) -> None:
    path = Path(release_repo["final_evidence_path"])
    payload = json.loads(path.read_text(encoding="utf-8"))
    payload["remoteExecution"]["workerContextSha256"] = "0" * 64
    _write_json(path, payload)
    _commit_all(Path(release_repo["root"]), "wrong worker context")

    with pytest.raises(PreflightError, match="workerContextSha256"):
        _validate(release_repo, mode="deploy")


@pytest.mark.parametrize(
    "mutation,error",
    [
        (lambda payload: payload["runtimeOptions"].update({"arbitrary": True}), "runtimeOptions"),
        (
            lambda payload: payload["runtimeOptions"].update(
                {"primary_model": {"artifactId": "missing-model"}}
            ),
            "undeclared artifact",
        ),
        (lambda payload: payload.update({"candidateVersion": "v7.2"}), "releaseVersion"),
        (
            lambda payload: payload.update(
                {"requiredContracts": ["video_to_analysis_product_api_v1"]}
            ),
            "requiredContracts.*exactly",
        ),
    ],
)
def test_preflight_rejects_semantically_invalid_manifest(
    release_repo: dict[str, object], mutation, error: str
) -> None:
    root = Path(release_repo["root"])
    manifest_path = Path(release_repo["manifest_path"])
    payload = json.loads(manifest_path.read_text(encoding="utf-8"))
    mutation(payload)
    _write_json(manifest_path, payload)
    digest = hashlib.sha256(manifest_path.read_bytes()).hexdigest()
    for evidence_key in ("build_evidence_path", "final_evidence_path"):
        evidence_path = Path(release_repo[evidence_key])
        evidence = json.loads(evidence_path.read_text(encoding="utf-8"))
        evidence["manifestSha256"] = digest
        _write_json(evidence_path, evidence)
    _commit_all(root, "semantically invalid release metadata")
    release_repo["manifest_sha256"] = digest

    with pytest.raises(PreflightError, match=error):
        _validate(release_repo)


def test_preflight_rejects_dirty_source(release_repo: dict[str, object]) -> None:
    (Path(release_repo["root"]) / "README.md").write_text("dirty\n", encoding="utf-8")

    with pytest.raises(PreflightError, match="worktree.*dirty"):
        _validate(release_repo)


@pytest.mark.parametrize("relative", [
    "README.md", ".github/workflows/release.yml", "backend/app/main.py",
    "backend/daytona_worker/requirements.txt", "docs/runbooks/daytona-gpu-execution.md",
    "docs/recovery/2026-08-24/unlisted.md",
])
def test_post_freeze_history_rejects_every_non_allowlisted_path(
    release_repo: dict[str, object], relative: str
) -> None:
    root = Path(release_repo["root"]); path = root / relative
    path.parent.mkdir(parents=True, exist_ok=True); path.write_text("mutation\n", encoding="utf-8")
    _commit_all(root, "forbidden post-freeze mutation")
    with pytest.raises(PreflightError, match="touches paths not permitted"):
        _validate(release_repo)


def test_preflight_rejects_non_ancestor_source(release_repo: dict[str, object]) -> None:
    root = Path(release_repo["root"])
    tree = _git(root, "mktree", input_text="")
    unrelated = _git(root, "commit-tree", tree, "-m", "unrelated")
    payload = json.loads(Path(release_repo["manifest_path"]).read_text(encoding="utf-8"))
    payload["sourceCommit"] = unrelated
    _write_json(Path(release_repo["manifest_path"]), payload)
    digest = hashlib.sha256(Path(release_repo["manifest_path"]).read_bytes()).hexdigest()
    _write_json(Path(release_repo["build_evidence_path"]), _evidence(unrelated, digest))
    _commit_all(root, "non ancestor metadata")
    release_repo["source_commit"] = unrelated
    release_repo["manifest_sha256"] = digest

    with pytest.raises(PreflightError, match="not an ancestor"):
        _validate(release_repo)


def test_preflight_rejects_non_ancestor_verification_commit(
    release_repo: dict[str, object],
) -> None:
    root = Path(release_repo["root"])
    tree = _git(root, "mktree", input_text="")
    unrelated = _git(root, "commit-tree", tree, "-m", "unrelated verifier")
    payload = json.loads(Path(release_repo["build_evidence_path"]).read_text())
    payload["verificationCommit"] = unrelated
    _write_json(Path(release_repo["build_evidence_path"]), payload)
    _commit_all(root, "wrong verifier")

    with pytest.raises(PreflightError, match="verificationCommit.*not an ancestor"):
        _validate(release_repo)


def test_preflight_rejects_manifest_bytes_not_present_at_verification_commit(
    release_repo: dict[str, object],
) -> None:
    root = Path(release_repo["root"])
    payload = json.loads(Path(release_repo["build_evidence_path"]).read_text())
    payload["verificationCommit"] = release_repo["source_commit"]
    _write_json(Path(release_repo["build_evidence_path"]), payload)
    _commit_all(root, "verifier predates manifest")

    with pytest.raises(PreflightError, match="manifest.*verificationCommit"):
        _validate(release_repo)


@pytest.mark.parametrize("target_key,replacement_key", [("source_commit", "head"), ("head", "source_commit")])
def test_preflight_rejects_git_replace_objects(
    release_repo: dict[str, object], target_key: str, replacement_key: str
) -> None:
    root = Path(release_repo["root"])
    values = {
        "source_commit": str(release_repo["source_commit"]),
        "head": _git(root, "rev-parse", "HEAD"),
    }
    _git(root, "replace", values[target_key], values[replacement_key])

    with pytest.raises(PreflightError, match="replace objects are forbidden"):
        _validate(release_repo)


def test_preflight_rejects_legacy_grafts(release_repo: dict[str, object]) -> None:
    root = Path(release_repo["root"])
    grafts = Path(_git(root, "rev-parse", "--path-format=absolute", "--git-path", "info/grafts"))
    grafts.parent.mkdir(parents=True, exist_ok=True)
    grafts.write_text(f"{release_repo['source_commit']}\n", encoding="utf-8")

    with pytest.raises(PreflightError, match="legacy grafts are forbidden"):
        _validate(release_repo)


def test_raw_graph_rejects_forbidden_revert_when_graft_appears_after_initial_check(
    release_repo: dict[str, object], monkeypatch: pytest.MonkeyPatch
) -> None:
    root = Path(release_repo["root"])
    product = root / "backend/app/main.py"
    original = product.read_bytes()
    product.write_text("PRODUCT = 'graft-hidden forbidden change'\n", encoding="utf-8")
    _commit_all(root, "forbidden change before graft race")
    product.write_bytes(original)
    head = _commit_all(root, "byte-identical revert before graft race")
    grafts = Path(_git(root, "rev-parse", "--path-format=absolute", "--git-path", "info/grafts"))
    original_git = preflight_module._git
    injected = False

    def racing_git(
        repo_root: Path, *args: str, check: bool = True
    ) -> subprocess.CompletedProcess[str]:
        nonlocal injected
        if args and args[0] == "status" and not injected:
            grafts.parent.mkdir(parents=True, exist_ok=True)
            grafts.write_text(f"{head} {release_repo['source_commit']}\n", encoding="utf-8")
            injected = True
        return original_git(repo_root, *args, check=check)

    monkeypatch.setattr(preflight_module, "_git", racing_git)

    with pytest.raises(
        PreflightError,
        match="commit history touches paths not permitted.*backend/app/main.py",
    ):
        _validate(release_repo)
    assert injected


def test_provenance_walk_does_not_use_graft_aware_parentage_commands(
    release_repo: dict[str, object], monkeypatch: pytest.MonkeyPatch
) -> None:
    original_git = preflight_module._git

    def guarded_git(
        repo_root: Path, *args: str, check: bool = True
    ) -> subprocess.CompletedProcess[str]:
        if args and args[0] in {"merge-base", "rev-list"}:
            raise AssertionError(f"graft-aware provenance command used: {args[0]}")
        return original_git(repo_root, *args, check=check)

    monkeypatch.setattr(preflight_module, "_git", guarded_git)

    _validate(release_repo)


def test_preflight_rejects_product_or_runtime_change_after_source(release_repo: dict[str, object]) -> None:
    product = Path(release_repo["root"]) / "backend/app/main.py"
    product.write_text("PRODUCT = 'changed after source'\n", encoding="utf-8")
    _commit_all(Path(release_repo["root"]), "late product change")

    with pytest.raises(PreflightError, match="not permitted after sourceCommit.*backend/app/main.py"):
        _validate(release_repo)


def test_preflight_rejects_forbidden_change_hidden_by_byte_identical_revert(
    release_repo: dict[str, object]
) -> None:
    root = Path(release_repo["root"])
    product = root / "backend/app/main.py"
    original = product.read_bytes()
    product.write_text("PRODUCT = 'forbidden intermediate change'\n", encoding="utf-8")
    _commit_all(root, "forbidden intermediate product change")
    product.write_bytes(original)
    _commit_all(root, "revert product bytes")

    with pytest.raises(PreflightError, match="commit history touches paths not permitted.*backend/app/main.py"):
        _validate(release_repo)


def test_preflight_rejects_merge_parent_path_hidden_by_ours_resolution(
    release_repo: dict[str, object]
) -> None:
    root = Path(release_repo["root"])
    main_branch = _git(root, "branch", "--show-current")
    _git(root, "checkout", "--orphan", "external-history")
    _git(root, "rm", "-r", "--force", ".")
    (root / ".gitignore").write_text("artifacts/\n", encoding="utf-8")
    product = root / "backend/app/main.py"
    product.parent.mkdir(parents=True, exist_ok=True)
    product.write_text("PRODUCT = 'unrelated forbidden parent'\n", encoding="utf-8")
    _commit_all(root, "unrelated product history")
    _git(root, "checkout", main_branch)
    _git(
        root,
        "merge",
        "--allow-unrelated-histories",
        "--strategy=ours",
        "external-history",
        "-m",
        "metadata line merge",
    )

    with pytest.raises(PreflightError, match="commit history touches paths not permitted.*backend/app/main.py"):
        _validate(release_repo)


def test_preflight_rejects_orphan_change_revert_hidden_by_identical_tree_merge(
    release_repo: dict[str, object]
) -> None:
    root = Path(release_repo["root"])
    main_branch = _git(root, "branch", "--show-current")
    main_tree = _git(root, "rev-parse", "HEAD^{tree}")
    orphan_root = _git(root, "commit-tree", main_tree, "-m", "orphan identical root")
    _git(root, "branch", "orphan-identical", orphan_root)
    _git(root, "checkout", "orphan-identical")
    product = root / "backend/app/main.py"
    original = product.read_bytes()
    product.write_text("PRODUCT = 'hidden orphan change'\n", encoding="utf-8")
    _commit_all(root, "orphan forbidden product change")
    product.write_bytes(original)
    _commit_all(root, "orphan byte-identical revert")
    _git(root, "checkout", main_branch)
    _git(
        root,
        "merge",
        "--allow-unrelated-histories",
        "--strategy=ours",
        "orphan-identical",
        "-m",
        "merge identical orphan tree",
    )

    with pytest.raises(PreflightError, match="commit history touches paths not permitted.*backend/app/main.py"):
        _validate(release_repo)


def test_preflight_accepts_metadata_only_branch_merge_based_on_source(
    release_repo: dict[str, object]
) -> None:
    root = Path(release_repo["root"])
    main_branch = _git(root, "branch", "--show-current")
    _git(root, "branch", "metadata-branch", str(release_repo["source_commit"]))
    _git(root, "checkout", "metadata-branch")
    branch_path = root / "docs/recovery/2026-08-19/current-tree-inventory.json"
    branch_path.parent.mkdir(parents=True, exist_ok=True)
    branch_path.write_text("{}\n", encoding="utf-8")
    _commit_all(root, "metadata branch readme")
    _git(root, "checkout", main_branch)
    status_path = root / "docs/status/current.md"
    status_path.parent.mkdir(parents=True, exist_ok=True)
    status_path.write_text("main metadata\n", encoding="utf-8")
    _commit_all(root, "main metadata status")
    _git(root, "merge", "--no-ff", "metadata-branch", "-m", "merge metadata branch")

    _validate(release_repo)


def test_preflight_accepts_every_individual_allowlisted_descendant(
    release_repo: dict[str, object], tmp_path: Path
) -> None:
    # Prove all entries, including top-level historical mirrors, are interpreted literally.
    root = Path(release_repo["root"])
    for index, relative in enumerate(sorted(EXPECTED_ALLOWLIST)):
        path = root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        if path in {
            release_repo["manifest_path"],
            release_repo["build_evidence_path"],
            release_repo["final_evidence_path"],
        }:
            continue
        path.write_text(f"metadata {index}\n", encoding="utf-8")
    _commit_all(root, "all allowed metadata")

    _validate(release_repo)


def test_preflight_rejects_absent_evidence(release_repo: dict[str, object]) -> None:
    Path(release_repo["build_evidence_path"]).unlink()

    with pytest.raises(PreflightError, match="evidence.*cannot load"):
        _validate(release_repo)


def test_preflight_rejects_manifest_outside_declared_release_path(
    release_repo: dict[str, object], tmp_path: Path
) -> None:
    external = tmp_path / "external-manifest.json"
    external.write_bytes(Path(release_repo["manifest_path"]).read_bytes())

    with pytest.raises(PreflightError, match="manifest path must be backend/release/v7.3.json"):
        validate_release_preflight(
            repo_root=Path(release_repo["root"]),
            manifest_path=external,
            evidence_path=Path(release_repo["build_evidence_path"]),
            mode="build-only",
            image_tag=(
                f"v7.3-{release_repo['source_commit']}-{str(release_repo['manifest_sha256'])[:12]}"
            ),
            now=NOW,
        )


def test_preflight_rejects_evidence_outside_phase_release_path(
    release_repo: dict[str, object], tmp_path: Path
) -> None:
    external = tmp_path / "external-evidence.json"
    external.write_bytes(Path(release_repo["build_evidence_path"]).read_bytes())

    with pytest.raises(PreflightError, match="evidence path must be"):
        validate_release_preflight(
            repo_root=Path(release_repo["root"]),
            manifest_path=Path(release_repo["manifest_path"]),
            evidence_path=external,
            mode="build-only",
            image_tag=(
                f"v7.3-{release_repo['source_commit']}-{str(release_repo['manifest_sha256'])[:12]}"
            ),
            now=NOW,
        )


def test_preflight_rejects_ignored_untracked_evidence(release_repo: dict[str, object]) -> None:
    root = Path(release_repo["root"])
    relative = BUILD_EVIDENCE_RELATIVE_PATH.as_posix()
    _git(root, "rm", "--cached", relative)
    with (root / ".git/info/exclude").open("a", encoding="utf-8") as stream:
        stream.write(relative + "\n")
    _commit_all(root, "stop tracking evidence")

    with pytest.raises(PreflightError, match="release input is not tracked.*v7.3-pre-cloud.json"):
        _validate(release_repo)


@pytest.mark.parametrize("status", ["failed", "pending"])
def test_pre_cloud_rejects_non_remote_gate_not_passed(
    release_repo: dict[str, object], status: str
) -> None:
    payload = json.loads(Path(release_repo["build_evidence_path"]).read_text(encoding="utf-8"))
    gate = _gate(payload, "backend")
    gate["status"] = status
    gate["completedAt"] = None if status == "pending" else "2026-08-22T12:20:00Z"
    gate["logSha256"] = None if status == "pending" else "e" * 64
    _write_json(Path(release_repo["build_evidence_path"]), payload)
    _commit_all(Path(release_repo["root"]), "failed build evidence")

    with pytest.raises(PreflightError, match="pre-cloud gate.*must be passed"):
        _validate(release_repo)


@pytest.mark.parametrize("status", ["passed", "failed"])
def test_pre_cloud_requires_only_remote_gate_pending(
    release_repo: dict[str, object], status: str
) -> None:
    payload = json.loads(Path(release_repo["build_evidence_path"]).read_text(encoding="utf-8"))
    gate = _gate(payload, REMOTE_GATE_NAME)
    gate["status"] = status
    gate["completedAt"] = "2026-08-22T12:25:00Z"
    gate["logSha256"] = "e" * 64
    _write_json(Path(release_repo["build_evidence_path"]), payload)
    _commit_all(Path(release_repo["root"]), "invalid pending gate")

    with pytest.raises(PreflightError, match="remote gate must be pending"):
        _validate(release_repo)


def test_pre_cloud_rejects_overall_passed_true(release_repo: dict[str, object]) -> None:
    payload = json.loads(Path(release_repo["build_evidence_path"]).read_text(encoding="utf-8"))
    payload["overallPassed"] = True
    _write_json(Path(release_repo["build_evidence_path"]), payload)
    _commit_all(Path(release_repo["root"]), "invalid overall status")

    with pytest.raises(PreflightError, match="overallPassed must be false"):
        _validate(release_repo)


def test_pre_cloud_requires_at_least_one_pre_cloud_gate(
    release_repo: dict[str, object]
) -> None:
    payload = json.loads(Path(release_repo["build_evidence_path"]).read_text(encoding="utf-8"))
    payload["gates"] = [_gate(payload, REMOTE_GATE_NAME)]
    _write_json(Path(release_repo["build_evidence_path"]), payload)
    _commit_all(Path(release_repo["root"]), "missing pre-cloud gates")

    with pytest.raises(PreflightError, match="canonical gate inventory"):
        _validate(release_repo)


@pytest.mark.parametrize("status", ["failed", "pending"])
def test_deployment_requires_every_gate_passed(
    release_repo: dict[str, object], status: str
) -> None:
    payload = json.loads(Path(release_repo["final_evidence_path"]).read_text(encoding="utf-8"))
    gate = _gate(payload, "backend")
    gate["status"] = status
    gate["completedAt"] = None if status == "pending" else "2026-08-22T12:20:00Z"
    gate["logSha256"] = None if status == "pending" else "e" * 64
    payload["overallPassed"] = False
    _write_json(Path(release_repo["final_evidence_path"]), payload)
    _commit_all(Path(release_repo["root"]), "failed final evidence")

    with pytest.raises(PreflightError, match="final evidence requires every gate passed"):
        _validate(release_repo, mode="deploy")


def test_deployment_requires_overall_passed_true(release_repo: dict[str, object]) -> None:
    payload = json.loads(Path(release_repo["final_evidence_path"]).read_text(encoding="utf-8"))
    payload["overallPassed"] = False
    _write_json(Path(release_repo["final_evidence_path"]), payload)
    _commit_all(Path(release_repo["root"]), "invalid final overall status")

    with pytest.raises(PreflightError, match="overallPassed must be true"):
        _validate(release_repo, mode="deploy")


@pytest.mark.parametrize(
    "mode,target_key,wrong_key",
    [
        ("build-only", "build_evidence_path", "final_evidence_path"),
        ("deploy", "final_evidence_path", "build_evidence_path"),
    ],
)
def test_preflight_rejects_wrong_phase(
    release_repo: dict[str, object], mode: str, target_key: str, wrong_key: str
) -> None:
    source = str(release_repo["source_commit"])
    digest = str(release_repo["manifest_sha256"])
    Path(release_repo[target_key]).write_bytes(Path(release_repo[wrong_key]).read_bytes())
    _commit_all(Path(release_repo["root"]), "wrong evidence phase")

    with pytest.raises(PreflightError, match="phase mismatch"):
        validate_release_preflight(
            repo_root=Path(release_repo["root"]),
            manifest_path=Path(release_repo["manifest_path"]),
            evidence_path=Path(release_repo[target_key]),
            mode=mode,
            image_tag=f"v7.3-{source}-{digest[:12]}",
            now=NOW,
        )


def test_preflight_rejects_stale_evidence(release_repo: dict[str, object]) -> None:
    payload = json.loads(Path(release_repo["build_evidence_path"]).read_text(encoding="utf-8"))
    payload["createdAt"] = "2026-08-20T12:30:00Z"
    for gate in payload["gates"]:
        if gate["status"] == "passed":
            gate["completedAt"] = "2026-08-20T12:20:00Z"
    _write_json(Path(release_repo["build_evidence_path"]), payload)
    _commit_all(Path(release_repo["root"]), "stale evidence")

    with pytest.raises(PreflightError, match="evidence is stale"):
        _validate(release_repo)


@pytest.mark.parametrize(
    "timestamp",
    [
        "2026-08-22T12:30:00+00:00",
        "2026-08-22 12:30:00Z",
        "2026-08-22T12:30Z",
        "2026-8-22T12:30:00Z",
        "2026-08-22T12:30:00.1234567890Z",
    ],
)
def test_evidence_rejects_noncanonical_utc_timestamp(
    release_repo: dict[str, object], timestamp: str
) -> None:
    payload = json.loads(Path(release_repo["build_evidence_path"]).read_text(encoding="utf-8"))
    payload["createdAt"] = timestamp
    _write_json(Path(release_repo["build_evidence_path"]), payload)
    _commit_all(Path(release_repo["root"]), "invalid evidence timestamp")

    with pytest.raises(PreflightError, match="exact UTC RFC3339"):
        _validate(release_repo)


def test_evidence_rejects_gate_completed_after_evidence(release_repo: dict[str, object]) -> None:
    payload = json.loads(Path(release_repo["build_evidence_path"]).read_text(encoding="utf-8"))
    _gate(payload, "backend")["completedAt"] = "2026-08-22T12:31:00Z"
    _write_json(Path(release_repo["build_evidence_path"]), payload)
    _commit_all(Path(release_repo["root"]), "future gate completion")

    with pytest.raises(PreflightError, match="completedAt must not be after evidence createdAt"):
        _validate(release_repo)


def test_evidence_rejects_stale_completed_gate(release_repo: dict[str, object]) -> None:
    payload = json.loads(Path(release_repo["build_evidence_path"]).read_text(encoding="utf-8"))
    _gate(payload, "backend")["completedAt"] = "2026-08-20T12:20:00Z"
    _write_json(Path(release_repo["build_evidence_path"]), payload)
    _commit_all(Path(release_repo["root"]), "stale completed gate")

    with pytest.raises(PreflightError, match="gate backend is stale"):
        _validate(release_repo)


@pytest.mark.parametrize("mutation", ["missing", "extra", "command"])
def test_evidence_requires_exact_canonical_gate_inventory(
    release_repo: dict[str, object], mutation: str
) -> None:
    payload = json.loads(Path(release_repo["build_evidence_path"]).read_text(encoding="utf-8"))
    if mutation == "missing":
        payload["gates"] = [gate for gate in payload["gates"] if gate["name"] != "sidecar"]
    elif mutation == "extra":
        payload["gates"].append(
            {
                "name": "surprise",
                "command": "true",
                "status": "passed",
                "completedAt": "2026-08-22T12:20:00Z",
                "logSha256": "e" * 64,
            }
        )
    else:
        _gate(payload, "sidecar")["command"] = "pytest research-addon"
    _write_json(Path(release_repo["build_evidence_path"]), payload)
    _commit_all(Path(release_repo["root"]), "invalid gate inventory")

    with pytest.raises(PreflightError, match="canonical gate inventory|canonical command"):
        _validate(release_repo)


def test_preflight_rejects_evidence_source_mismatch(release_repo: dict[str, object]) -> None:
    payload = json.loads(Path(release_repo["build_evidence_path"]).read_text(encoding="utf-8"))
    payload["sourceCommit"] = "b" * 40
    _write_json(Path(release_repo["build_evidence_path"]), payload)
    _commit_all(Path(release_repo["root"]), "wrong evidence source")

    with pytest.raises(PreflightError, match="evidence sourceCommit mismatch"):
        _validate(release_repo)


def test_preflight_rejects_manifest_digest_mismatch(release_repo: dict[str, object]) -> None:
    payload = json.loads(Path(release_repo["build_evidence_path"]).read_text(encoding="utf-8"))
    payload["manifestSha256"] = "b" * 64
    _write_json(Path(release_repo["build_evidence_path"]), payload)
    _commit_all(Path(release_repo["root"]), "wrong manifest digest")

    with pytest.raises(PreflightError, match="manifestSha256 mismatch"):
        _validate(release_repo)


def test_preflight_rejects_missing_artifact(release_repo: dict[str, object]) -> None:
    Path(release_repo["artifact"]).unlink()

    with pytest.raises(PreflightError, match="missing artifact"):
        _validate(release_repo)


def test_preflight_rejects_corrupt_artifact(release_repo: dict[str, object]) -> None:
    Path(release_repo["artifact"]).write_bytes(b"corrupt-model")

    with pytest.raises(PreflightError, match="(size|sha256) mismatch"):
        _validate(release_repo)


def test_preflight_rejects_invalid_manifest_contract(release_repo: dict[str, object]) -> None:
    payload = json.loads(Path(release_repo["manifest_path"]).read_text(encoding="utf-8"))
    payload["unknown"] = "not allowed"
    _write_json(Path(release_repo["manifest_path"]), payload)
    digest = hashlib.sha256(Path(release_repo["manifest_path"]).read_bytes()).hexdigest()
    _write_json(
        Path(release_repo["build_evidence_path"]),
        _evidence(str(release_repo["source_commit"]), digest),
    )
    _commit_all(Path(release_repo["root"]), "invalid manifest")

    with pytest.raises(PreflightError, match="invalid release manifest"):
        _validate(release_repo)


@pytest.mark.parametrize(
    "tag",
    [
        "latest",
        "v7.3",
        "v7.3-" + "a" * 7 + "-" + "b" * 12,
        "v7.3-" + "a" * 40,
        "v7.3-" + "A" * 40 + "-" + "b" * 12,
    ],
)
def test_preflight_rejects_mutable_release_only_or_short_tags(
    release_repo: dict[str, object], tag: str
) -> None:
    assert IMMUTABLE_TAG_RE.fullmatch(tag) is None
    with pytest.raises(PreflightError, match="immutable image tag"):
        _validate(release_repo, image_tag=tag)


def test_preflight_rejects_tag_with_wrong_source_or_manifest_identity(
    release_repo: dict[str, object]
) -> None:
    wrong = f"v7.3-{'b' * 40}-{'c' * 12}"
    with pytest.raises(PreflightError, match="image tag does not bind"):
        _validate(release_repo, image_tag=wrong)


@pytest.mark.parametrize(
    "source_label,manifest_label,match",
    [
        ("b" * 40, "c" * 64, "source revision label mismatch"),
        ("a" * 40, "d" * 64, "manifest digest label mismatch"),
        (None, "c" * 64, "source revision label is missing"),
        ("a" * 40, None, "manifest digest label is missing"),
    ],
)
def test_image_labels_fail_closed(
    source_label: str | None, manifest_label: str | None, match: str
) -> None:
    with pytest.raises(PreflightError, match=match):
        validate_image_labels(
            expected_source_commit="a" * 40,
            expected_manifest_sha256="c" * 64,
            source_label=source_label,
            manifest_label=manifest_label,
        )


def test_image_labels_accept_exact_source_and_manifest_identity() -> None:
    validate_image_labels(
        expected_source_commit="a" * 40,
        expected_manifest_sha256="c" * 64,
        source_label="a" * 40,
        manifest_label="c" * 64,
    )


@pytest.mark.parametrize(
    "mutation,match",
    [
        (("surprise", True), "unknown keys"),
        (("schemaVersion", 3), "schemaVersion"),
        (("schemaVersion", 1.0), "schemaVersion"),
        (("phase", "candidate"), "phase"),
        (("manifestSha256", "A" * 64), "manifestSha256"),
        (("overallPassed", "yes"), "overallPassed"),
        (("toolVersions", {"python": 311}), "toolVersions"),
        (("gates", []), "gates"),
    ],
)
def test_evidence_contract_rejects_invalid_top_level_values(
    tmp_path: Path, mutation: tuple[str, object], match: str
) -> None:
    payload = _evidence("a" * 40, "b" * 64)
    payload[mutation[0]] = mutation[1]
    path = tmp_path / "evidence.json"
    _write_json(path, payload)

    with pytest.raises(PreflightError, match=match):
        load_verification_evidence(path)


@pytest.mark.parametrize(
    "mutation,match",
    [
        (("surprise", True), "unknown keys"),
        (("name", ""), "gate name"),
        (("command", ""), "gate command"),
        (("status", "unknown"), "gate status"),
        (("completedAt", "not-a-time"), "completedAt"),
    ],
)
def test_evidence_contract_rejects_invalid_gate_values(
    tmp_path: Path, mutation: tuple[str, object], match: str
) -> None:
    payload = _evidence("a" * 40, "b" * 64)
    _gate(payload, "backend")[mutation[0]] = mutation[1]
    path = tmp_path / "evidence.json"
    _write_json(path, payload)

    with pytest.raises(PreflightError, match=match):
        load_verification_evidence(path)


def test_evidence_contract_rejects_duplicate_gate_names(tmp_path: Path) -> None:
    payload = _evidence("a" * 40, "b" * 64)
    _gate(payload, REMOTE_GATE_NAME)["name"] = "backend"
    path = tmp_path / "evidence.json"
    _write_json(path, payload)

    with pytest.raises(PreflightError, match="duplicate gate name"):
        load_verification_evidence(path)


def test_cli_emits_machine_readable_validated_inputs(
    release_repo: dict[str, object], capsys: pytest.CaptureFixture[str]
) -> None:
    source = str(release_repo["source_commit"])
    digest = str(release_repo["manifest_sha256"])
    exit_code = main(
        [
            "validate",
            "--repo-root",
            str(release_repo["root"]),
            "--manifest",
            str(release_repo["manifest_path"]),
            "--evidence",
            str(release_repo["build_evidence_path"]),
            "--mode",
            "build-only",
            "--image-tag",
            f"v7.3-{source}-{digest[:12]}",
            "--now",
            "2026-08-22T13:00:00Z",
        ]
    )

    assert exit_code == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload == {
        "artifacts": [
            {
                "containerPath": "/app/models/model.pt",
                "id": "primary-model",
                "localPath": str(Path(release_repo["artifact"]).resolve()),
                "sha256": hashlib.sha256(b"verified-model").hexdigest(),
                "sizeBytes": len(b"verified-model"),
            }
        ],
        "evidencePath": str(Path(release_repo["build_evidence_path"]).resolve()),
        "evidencePhase": "pre_cloud",
        "evidenceSha256": hashlib.sha256(
            Path(release_repo["build_evidence_path"]).read_bytes()
        ).hexdigest(),
        "manifestPath": str(Path(release_repo["manifest_path"]).resolve()),
        "manifestSha256": digest,
        "sourceCommit": source,
    }


def test_cli_checks_evidence_validity_window(
    release_repo: dict[str, object], capsys: pytest.CaptureFixture[str]
) -> None:
    exit_code = main(
        [
            "check-freshness",
            "--evidence",
            str(release_repo["build_evidence_path"]),
            "--mode",
            "build-only",
            "--minimum-validity-seconds",
            "3600",
            "--now",
            "2026-08-22T13:00:00Z",
        ]
    )

    assert exit_code == 0
    assert json.loads(capsys.readouterr().out) == {
        "evidenceFresh": True,
        "minimumValiditySeconds": 3600,
        "remainingValiditySeconds": 84000,
    }


def _staged_context(
    release_repo: dict[str, object], tmp_path: Path
) -> tuple[Path, dict[str, object]]:
    result = _validate(release_repo)
    receipt = result.to_mapping()
    context = tmp_path / "context"
    (context / "backend/release/verification").mkdir(parents=True)
    shutil.copy2(
        Path(release_repo["manifest_path"]),
        context / MANIFEST_RELATIVE_PATH,
    )
    shutil.copy2(
        Path(release_repo["build_evidence_path"]),
        context / BUILD_EVIDENCE_RELATIVE_PATH,
    )
    for artifact in receipt["artifacts"]:  # type: ignore[union-attr]
        relative = str(artifact["containerPath"]).removeprefix("/app/")
        destination = context / relative
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(Path(str(artifact["localPath"])), destination)
    return context, receipt


def test_staged_context_accepts_exact_receipt_bytes(
    release_repo: dict[str, object], tmp_path: Path
) -> None:
    context, receipt = _staged_context(release_repo, tmp_path)

    result = validate_staged_context(context_root=context, receipt=receipt)

    assert result.source_commit == release_repo["source_commit"]
    assert result.manifest_sha256 == release_repo["manifest_sha256"]
    assert result.evidence_sha256 == receipt["evidenceSha256"]


@pytest.mark.parametrize(
    "target_key,match",
    [
        ("manifest_path", "live manifest digest mismatch"),
        ("build_evidence_path", "live evidence digest mismatch"),
        ("artifact", "live artifact primary-model.*mismatch"),
    ],
)
def test_staged_context_rejects_live_input_mutation_after_preflight(
    release_repo: dict[str, object],
    tmp_path: Path,
    target_key: str,
    match: str,
) -> None:
    context, receipt = _staged_context(release_repo, tmp_path)
    target = Path(release_repo[target_key])
    target.write_bytes(target.read_bytes() + b"mutated-after-preflight")

    with pytest.raises(PreflightError, match=match):
        validate_staged_context(context_root=context, receipt=receipt)


@pytest.mark.parametrize(
    "relative,match",
    [
        (MANIFEST_RELATIVE_PATH, "staged manifest digest mismatch"),
        (BUILD_EVIDENCE_RELATIVE_PATH, "staged evidence digest mismatch"),
        (Path("models/model.pt"), "staged artifact primary-model.*mismatch"),
    ],
)
def test_staged_context_rejects_staged_byte_corruption(
    release_repo: dict[str, object],
    tmp_path: Path,
    relative: Path,
    match: str,
) -> None:
    context, receipt = _staged_context(release_repo, tmp_path)
    target = context / relative
    target.write_bytes(target.read_bytes() + b"corrupt-staged-byte")

    with pytest.raises(PreflightError, match=match):
        validate_staged_context(context_root=context, receipt=receipt)


def test_staged_context_rejects_receipt_destination_escape(
    release_repo: dict[str, object], tmp_path: Path
) -> None:
    context, receipt = _staged_context(release_repo, tmp_path)
    receipt["artifacts"][0]["containerPath"] = "/app/models/../escape.pt"  # type: ignore[index]

    with pytest.raises(PreflightError, match="containerPath"):
        validate_staged_context(context_root=context, receipt=receipt)


def test_cli_validates_exact_staged_context(
    release_repo: dict[str, object],
    tmp_path: Path,
    capsys: pytest.CaptureFixture[str],
) -> None:
    context, receipt = _staged_context(release_repo, tmp_path)
    receipt_path = tmp_path / "receipt.json"
    _write_json(receipt_path, receipt)

    exit_code = main(
        [
            "validate-staged",
            "--context-root",
            str(context),
            "--receipt",
            str(receipt_path),
        ]
    )

    assert exit_code == 0
    assert json.loads(capsys.readouterr().out)["stagedContextValid"] is True


def _rewrite_tar(
    source: Path,
    destination: Path,
    *,
    replace_name: str | None = None,
    replace_content: bytes | None = None,
    replace_type: bytes | None = None,
    extra_name: str | None = None,
    header_mutation: str | None = None,
) -> None:
    output_options: dict[str, object] = {"format": tarfile.PAX_FORMAT}
    if header_mutation == "global-pax":
        output_options["pax_headers"] = {"comment": "noncanonical-global-header"}
    with tarfile.open(source, "r:") as archive, tarfile.open(
        destination, "w", **output_options
    ) as output:
        for member in archive.getmembers():
            stream = archive.extractfile(member) if member.isfile() else None
            content = stream.read() if stream is not None else b""
            copied = tarfile.TarInfo(member.name)
            copied.mode = member.mode
            copied.type = member.type
            copied.linkname = member.linkname
            if member.name.removesuffix("/") == replace_name:
                if replace_type is not None:
                    copied.type = replace_type
                    copied.linkname = "backend/app/main.py"
                    content = b""
                elif replace_content is not None:
                    content = replace_content
                if header_mutation == "uid":
                    copied.uid = 123
                elif header_mutation == "gid":
                    copied.gid = 456
                elif header_mutation == "uname":
                    copied.uname = "builder"
                elif header_mutation == "gname":
                    copied.gname = "builders"
                elif header_mutation == "mtime":
                    copied.mtime = 1
                elif header_mutation == "mode":
                    copied.mode = 0o777
                elif header_mutation == "linkname":
                    copied.linkname = "unexpected-regular-file-target"
                elif header_mutation == "pax":
                    copied.pax_headers = {"comment": "noncanonical-member-header"}
            copied.size = len(content) if copied.type == tarfile.REGTYPE else 0
            output.addfile(copied, io.BytesIO(content) if copied.size else None)
        if extra_name is not None:
            extra = tarfile.TarInfo(extra_name)
            extra.size = len(b"extra")
            output.addfile(extra, io.BytesIO(b"extra"))


def test_validated_tar_context_contains_exact_source_and_injected_bytes(
    release_repo: dict[str, object], tmp_path: Path
) -> None:
    receipt = _validate(release_repo).to_mapping()
    context_tar = build_validated_tar_context(
        repo_root=release_repo["root"],
        receipt=receipt,
        output_path=tmp_path / "context.tar",
        now=NOW,
    )

    validate_tar_context(
        repo_root=release_repo["root"], receipt=receipt, tar_path=context_tar, now=NOW
    )
    with tarfile.open(context_tar, "r:") as archive:
        assert archive.pax_headers == {}
        members = archive.getmembers()
        assert members
        for member in members:
            assert (member.uid, member.gid, member.uname, member.gname, member.mtime) == (
                0,
                0,
                "",
                "",
                0,
            )
            assert member.pax_headers == {}
            assert member.mode == (0o755 if member.isdir() or member.mode & 0o111 else 0o644)
        assert archive.extractfile("backend/app/main.py").read() == b"PRODUCT = 'v7.3'\n"
        assert archive.extractfile(str(MANIFEST_RELATIVE_PATH)).read() == Path(
            release_repo["manifest_path"]
        ).read_bytes()
        assert archive.extractfile("models/model.pt").read() == b"verified-model"


@pytest.mark.parametrize(
    "mutation,match",
    [
        ("source", "source member mismatch"),
        ("manifest", "injected member mismatch"),
        ("artifact", "injected member mismatch"),
        ("symlink", "forbidden symlink or special member"),
        ("special", "forbidden symlink or special member"),
        ("extra", "member mismatch"),
        ("corrupt", "noncanonical raw tar layout"),
    ],
)
def test_tar_context_rejects_any_noncanonical_member_or_corruption(
    release_repo: dict[str, object], tmp_path: Path, mutation: str, match: str
) -> None:
    receipt = _validate(release_repo).to_mapping()
    original = build_validated_tar_context(
        repo_root=release_repo["root"],
        receipt=receipt,
        output_path=tmp_path / "original.tar",
        now=NOW,
    )
    candidate = tmp_path / "candidate.tar"
    if mutation == "corrupt":
        candidate.write_bytes(b"not a tar archive")
    else:
        options: dict[str, object] = {}
        if mutation == "source":
            options.update(replace_name="backend/app/main.py", replace_content=b"forged\n")
        elif mutation == "manifest":
            options.update(replace_name=str(MANIFEST_RELATIVE_PATH), replace_content=b"{}\n")
        elif mutation == "artifact":
            options.update(replace_name="models/model.pt", replace_content=b"forged-model")
        elif mutation == "symlink":
            options.update(replace_name="backend/app/main.py", replace_type=tarfile.SYMTYPE)
        elif mutation == "special":
            options.update(replace_name="backend/app/main.py", replace_type=tarfile.FIFOTYPE)
        else:
            options.update(extra_name="surprise.txt")
        _rewrite_tar(original, candidate, **options)  # type: ignore[arg-type]

    with pytest.raises(PreflightError, match=match):
        validate_tar_context(
            repo_root=release_repo["root"], receipt=receipt, tar_path=candidate, now=NOW
        )


@pytest.mark.parametrize(
    "mutation",
    ["uid", "gid", "uname", "gname", "mtime", "mode", "linkname", "pax", "global-pax"],
)
def test_tar_context_rejects_each_noncanonical_header(
    release_repo: dict[str, object], tmp_path: Path, mutation: str
) -> None:
    receipt = _validate(release_repo).to_mapping()
    original = build_validated_tar_context(
        repo_root=release_repo["root"],
        receipt=receipt,
        output_path=tmp_path / "original.tar",
        now=NOW,
    )
    candidate = tmp_path / f"{mutation}.tar"
    _rewrite_tar(
        original,
        candidate,
        replace_name="backend/app/main.py",
        header_mutation=mutation,
    )

    with pytest.raises(PreflightError, match="noncanonical.*header|noncanonical.*mode"):
        validate_tar_context(
            repo_root=release_repo["root"], receipt=receipt, tar_path=candidate, now=NOW
        )


def _raw_tar_offsets(content: bytes) -> tuple[int, int, int]:
    offset = 0
    first_file_padding = -1
    while content[offset : offset + tarfile.BLOCKSIZE] != b"\0" * tarfile.BLOCKSIZE:
        header = content[offset : offset + tarfile.BLOCKSIZE]
        assert len(header) == tarfile.BLOCKSIZE
        size = int(header[124:136].rstrip(b"\0 ") or b"0", 8)
        data_end = offset + tarfile.BLOCKSIZE + size
        padding_size = (-size) % tarfile.BLOCKSIZE
        if padding_size and first_file_padding < 0:
            first_file_padding = data_end
        offset = data_end + padding_size
    assert first_file_padding >= 0
    end_markers = offset
    record_padding = end_markers + 2 * tarfile.BLOCKSIZE
    return first_file_padding, end_markers, record_padding


def _rewrite_first_raw_tar_header(content: bytearray, mutation: str) -> None:
    header = content[: tarfile.BLOCKSIZE]
    if mutation == "magic":
        header[257:263] = b"ustar "
    elif mutation == "version":
        header[263:265] = b" \0"
    elif mutation == "devmajor":
        header[329:337] = b"0000001\0"
    elif mutation == "devminor":
        header[337:345] = b"0000001\0"
    else:
        checksum = sum(header[:148]) + (8 * ord(" ")) + sum(header[156:])
        header[148:156] = f"{checksum:06o}".encode("ascii") + b"  "
        content[: tarfile.BLOCKSIZE] = header
        return
    header[148:156] = b" " * 8
    checksum = sum(header)
    header[148:156] = f"{checksum:06o}".encode("ascii") + b"\0 "
    content[: tarfile.BLOCKSIZE] = header


@pytest.mark.parametrize(
    "mutation", ["magic", "version", "devmajor", "devminor", "checksum-encoding"]
)
def test_tar_context_rejects_noncanonical_raw_header_bytes(
    release_repo: dict[str, object], tmp_path: Path, mutation: str
) -> None:
    receipt = _validate(release_repo).to_mapping()
    original = build_validated_tar_context(
        repo_root=release_repo["root"],
        receipt=receipt,
        output_path=tmp_path / "original.tar",
        now=NOW,
    )
    content = bytearray(original.read_bytes())
    _rewrite_first_raw_tar_header(content, mutation)
    candidate = tmp_path / f"raw-header-{mutation}.tar"
    candidate.write_bytes(content)

    with pytest.raises(PreflightError, match="noncanonical raw tar layout"):
        validate_tar_context(
            repo_root=release_repo["root"], receipt=receipt, tar_path=candidate, now=NOW
        )


@pytest.mark.parametrize(
    "mutation",
    [
        "file-padding",
        "second-end-marker",
        "record-padding",
        "missing-one-end-block",
        "missing-both-end-blocks",
        "truncated-record-padding",
        "appended-byte",
        "appended-zero-record",
    ],
)
def test_tar_context_rejects_noncanonical_raw_layout(
    release_repo: dict[str, object], tmp_path: Path, mutation: str
) -> None:
    receipt = _validate(release_repo).to_mapping()
    original = build_validated_tar_context(
        repo_root=release_repo["root"],
        receipt=receipt,
        output_path=tmp_path / "original.tar",
        now=NOW,
    )
    content = bytearray(original.read_bytes())
    file_padding, end_markers, record_padding = _raw_tar_offsets(content)
    if mutation in {"record-padding", "truncated-record-padding"} and record_padding >= len(content):
        pytest.skip("canonical tar is already RECORDSIZE-aligned; no record padding to mutate")
    if mutation == "file-padding":
        content[file_padding] = 1
    elif mutation == "second-end-marker":
        content[end_markers + tarfile.BLOCKSIZE] = 1
    elif mutation == "record-padding":
        content[record_padding] = 1
    elif mutation == "missing-one-end-block":
        del content[end_markers : end_markers + tarfile.BLOCKSIZE]
    elif mutation == "missing-both-end-blocks":
        del content[end_markers : end_markers + 2 * tarfile.BLOCKSIZE]
    elif mutation == "truncated-record-padding":
        del content[record_padding:]
    elif mutation == "appended-byte":
        content.extend(b"trailing-data")
    else:
        content.extend(b"\0" * tarfile.RECORDSIZE)
    candidate = tmp_path / f"{mutation}.tar"
    candidate.write_bytes(content)

    with pytest.raises(PreflightError, match="noncanonical raw tar layout"):
        validate_tar_context(
            repo_root=release_repo["root"], receipt=receipt, tar_path=candidate, now=NOW
        )


def _add_second_release_artifact(release_repo: dict[str, object]) -> tuple[Path, Path]:
    root = Path(release_repo["root"])
    first = Path(release_repo["artifact"])
    second = root / "artifacts/seed.json"
    second.write_bytes(b"x" * (2 * 1024 * 1024 + 17))
    manifest_path = Path(release_repo["manifest_path"])
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    manifest["artifacts"].append(
        {
            "id": "review-seed",
            "sha256": hashlib.sha256(second.read_bytes()).hexdigest(),
            "sizeBytes": second.stat().st_size,
            "localRelativePath": "artifacts/seed.json",
            "containerPath": "/app/release-inputs/seed.json",
            "origin": "external-recovery-archive",
            "retentionClass": "release-essential",
        }
    )
    _write_json(manifest_path, manifest)
    digest = hashlib.sha256(manifest_path.read_bytes()).hexdigest()
    verification_commit = _commit_all(root, "add second release manifest")
    for evidence_key in ("build_evidence_path", "final_evidence_path"):
        evidence_path = Path(release_repo[evidence_key])
        evidence = json.loads(evidence_path.read_text(encoding="utf-8"))
        evidence["manifestSha256"] = digest
        evidence["verificationCommit"] = verification_commit
        _write_json(evidence_path, evidence)
    _commit_all(root, "add second release evidence")
    release_repo["manifest_sha256"] = digest
    release_repo["verification_commit"] = verification_commit
    return first.resolve(), second.resolve()


def test_artifact_snapshots_use_only_bounded_stream_reads(
    release_repo: dict[str, object], tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    artifacts = set(_add_second_release_artifact(release_repo))
    receipt = _validate(release_repo).to_mapping()
    original_open = Path.open
    requested_sizes: list[int] = []

    class BoundedReader:
        def __init__(self, stream: object) -> None:
            self.stream = stream

        def read(self, size: int = -1) -> bytes:
            if size < 0 or size > 1024 * 1024:
                raise AssertionError(f"artifact used unbounded read({size})")
            requested_sizes.append(size)
            return self.stream.read(size)  # type: ignore[union-attr]

        def __enter__(self) -> "BoundedReader":
            self.stream.__enter__()  # type: ignore[union-attr]
            return self

        def __exit__(self, *args: object) -> object:
            return self.stream.__exit__(*args)  # type: ignore[union-attr]

        def __getattr__(self, name: str) -> object:
            return getattr(self.stream, name)

    def bounded_open(path: Path, *args: object, **kwargs: object) -> object:
        stream = original_open(path, *args, **kwargs)
        mode = args[0] if args else kwargs.get("mode", "r")
        if path.resolve() in artifacts and mode == "rb":
            return BoundedReader(stream)
        return stream

    monkeypatch.setattr(Path, "open", bounded_open)

    context_tar = build_validated_tar_context(
        repo_root=release_repo["root"],
        receipt=receipt,
        output_path=tmp_path / "context.tar",
        now=NOW,
    )

    assert requested_sizes
    validate_tar_context(
        repo_root=release_repo["root"], receipt=receipt, tar_path=context_tar, now=NOW
    )


def test_artifact_snapshot_workspace_is_private_and_cleaned_on_failure(
    release_repo: dict[str, object], tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    _add_second_release_artifact(release_repo)
    receipt = _validate(release_repo).to_mapping()
    output = tmp_path / "context.tar"

    def fail_after_snapshot(**_kwargs: object) -> None:
        workspaces = list(tmp_path.glob(".release-inputs-*"))
        assert len(workspaces) == 1
        workspace = workspaces[0]
        assert workspace.stat().st_mode & 0o777 == 0o700
        snapshots = list(workspace.iterdir())
        assert len(snapshots) == 2
        assert all(path.stat().st_mode & 0o777 == 0o600 for path in snapshots)
        raise PreflightError("forced writer failure")

    monkeypatch.setattr(preflight_module, "_write_streamed_tar_context", fail_after_snapshot)

    with pytest.raises(PreflightError, match="forced writer failure"):
        build_validated_tar_context(
            repo_root=release_repo["root"],
            receipt=receipt,
            output_path=output,
            now=NOW,
        )

    assert not output.exists()
    assert list(tmp_path.glob(".release-inputs-*")) == []


def test_cli_label_mode_rejects_mismatch(capsys: pytest.CaptureFixture[str]) -> None:
    exit_code = main(
        [
            "validate-labels",
            "--expected-source-commit",
            "a" * 40,
            "--expected-manifest-sha256",
            "b" * 64,
            "--source-label",
            "c" * 40,
            "--manifest-label",
            "b" * 64,
        ]
    )

    assert exit_code == 2
    assert "source revision label mismatch" in capsys.readouterr().err


def test_verification_schema_is_strict_and_documents_phase_semantics() -> None:
    from jsonschema import Draft202012Validator

    schema_path = Path(__file__).parents[1] / "release/verification_schema.json"
    schema = json.loads(schema_path.read_text(encoding="utf-8"))

    assert schema["additionalProperties"] is False
    assert schema["required"] == [
        "schemaVersion",
        "phase",
        "sourceCommit",
        "verificationCommit",
        "manifestSha256",
        "createdAt",
        "toolVersions",
        "gates",
        "overallPassed",
        "remoteExecution",
    ]
    assert schema["properties"]["phase"]["enum"] == ["pre_cloud", "final"]
    assert schema["$defs"]["gate"]["properties"]["status"]["enum"] == [
        "passed",
        "failed",
        "pending",
    ]
    gates_schema = schema["properties"]["gates"]
    assert gates_schema["minItems"] == len(REQUIRED_GATE_COMMANDS) == 13
    assert gates_schema["maxItems"] == len(REQUIRED_GATE_COMMANDS)
    assert gates_schema["items"] is False
    prefix_items = gates_schema["prefixItems"]
    assert [item["properties"]["name"]["const"] for item in prefix_items] == list(
        REQUIRED_GATE_COMMANDS
    )
    assert [item["properties"]["command"]["const"] for item in prefix_items] == list(
        REQUIRED_GATE_COMMANDS.values()
    )

    Draft202012Validator.check_schema(schema)
    validator = Draft202012Validator(schema)
    valid_build = _evidence("a" * 40, "b" * 64)
    valid_final = _evidence("a" * 40, "b" * 64, phase="final")
    assert list(validator.iter_errors(valid_build)) == []
    assert list(validator.iter_errors(valid_final)) == []

    invalid_payloads: list[dict[str, object]] = []
    missing = json.loads(json.dumps(valid_build))
    missing["gates"].pop()  # type: ignore[union-attr]
    invalid_payloads.append(missing)
    reordered = json.loads(json.dumps(valid_build))
    reordered["gates"][0], reordered["gates"][1] = (  # type: ignore[index]
        reordered["gates"][1],
        reordered["gates"][0],
    )
    invalid_payloads.append(reordered)
    wrong_command = json.loads(json.dumps(valid_build))
    wrong_command["gates"][0]["command"] = "pytest"  # type: ignore[index]
    invalid_payloads.append(wrong_command)
    failed_build_gate = json.loads(json.dumps(valid_build))
    failed_build_gate["gates"][0]["status"] = "failed"  # type: ignore[index]
    invalid_payloads.append(failed_build_gate)
    pending_final = json.loads(json.dumps(valid_final))
    pending_final["gates"][-1]["status"] = "pending"  # type: ignore[index]
    pending_final["gates"][-1]["completedAt"] = None  # type: ignore[index]
    pending_final["gates"][-1]["logSha256"] = None  # type: ignore[index]
    pending_final["overallPassed"] = False
    invalid_payloads.append(pending_final)
    assert all(list(validator.iter_errors(payload)) for payload in invalid_payloads)
