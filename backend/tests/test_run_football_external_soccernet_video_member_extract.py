from __future__ import annotations

import json
from pathlib import Path
import sys
import zipfile

import backend.scripts.run_football_external_soccernet_video_member_extract as extract


def _write_json(path: Path, payload: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def _write_pyzipper_shim(root: Path, *, actual_size: int | None = None, declared_size: int | None = None) -> None:
    root.mkdir(parents=True, exist_ok=True)
    if actual_size is None:
        source = "from zipfile import ZipFile as AESZipFile\n"
    else:
        source = f"""
import io

class _Info:
    file_size = {declared_size}

class AESZipFile:
    def __init__(self, _path):
        self.pwd = None
    def __enter__(self):
        return self
    def __exit__(self, *_args):
        return False
    def getinfo(self, _member):
        return _Info()
    def open(self, _member):
        return io.BytesIO(b'x' * {actual_size})
"""
    (root / "pyzipper.py").write_text(source, encoding="utf-8")


def _write_memory_limited_python(path: Path) -> None:
    path.write_text(
        f"""#!{sys.executable}
import os
import resource
import sys

limit = 48 * 1024 * 1024
resource.setrlimit(resource.RLIMIT_AS, (limit, limit))
os.execv({sys.executable!r}, [{sys.executable!r}, *sys.argv[1:]])
""",
        encoding="utf-8",
    )
    path.chmod(0o755)


def _write_inputs(tmp_path: Path, *, approved: bool = True) -> Path:
    candidate_root = tmp_path / "trained_detector_candidates" / "touchline_detector_candidate_v7"
    _write_json(
        candidate_root / "football_external_soccernet_video_member_extract_approval_v1/video_member_extract_approval_summary.json",
        {
            "goalAchieved": approved,
            "primaryBlocker": None if approved else "football_external_soccernet_video_sample_probe_missing",
            "videoMemberExtractionApproved": approved,
            "approvedVideoMemberPath": "game/224p.mp4",
            "approvedCompressedSizeBytes": 236289867,
            "approvedUncompressedSizeBytes": 237589445,
            "fullArchiveDownloadApproved": False,
            "videoMemberExtractionExecuted": False,
            "trainingExecuted": False,
            "runtimeDefaultMutationExecuted": False,
        },
    )
    _write_json(
        candidate_root / "football_external_soccernet_video_member_extract_approval_v1/video_member_extract_approval_contract.json",
        {
            "contractName": "football_external_soccernet_video_member_extract",
            "videoMemberExtractionApproved": approved,
            "approvedVideoMemberPath": "game/224p.mp4",
            "approvedCompressedSizeBytes": 236289867,
            "approvedUncompressedSizeBytes": 237589445,
            "approvedLocalHeaderOffset": 226,
            "fullArchiveDownloadApproved": False,
            "requiresRuntimeCredential": True,
            "credentialEnvVar": "SOCCERNET_PASSWORD",
            "credentialPersistenceAllowed": False,
        },
    )
    _write_json(
        candidate_root / "football_external_soccernet_split_archive_range_index_probe_v1/zip_central_directory_audit.json",
        {
            "archiveSizeBytes": 2042230928,
            "centralDirectoryOffset": 2042230255,
            "zipEntries": [
                {"path": "game/224p.mp4", "isDirectory": False, "localHeaderOffset": 226, "compressedSizeBytes": 236289867, "uncompressedSizeBytes": 237589445},
                {"path": "game/720p.mp4", "isDirectory": False, "localHeaderOffset": 236290211, "compressedSizeBytes": 1805926920, "uncompressedSizeBytes": 1806605353},
            ],
        },
    )
    return candidate_root


def test_video_member_extract_writes_injected_member_payload(tmp_path: Path) -> None:
    candidate_root = _write_inputs(tmp_path)

    payload = extract.run_football_external_soccernet_video_member_extract(
        storage_root=tmp_path,
        video_member_payload=b"\x00\x00\x00\x18ftypmp42payload",
        env={"SOCCERNET_PASSWORD": "runtime-only"},
    )

    output_root = candidate_root / "football_external_soccernet_video_member_extract_v1"
    inventory = json.loads((output_root / "extracted_video_member_inventory.json").read_text(encoding="utf-8"))
    extracted = output_root / inventory["extractedVideoFiles"][0]["relativePath"]

    assert payload["goalAchieved"] is True
    assert payload["primaryBlocker"] is None
    assert payload["videoMemberExtractionExecuted"] is True
    assert payload["videoMemberFullDownloadExecuted"] is True
    assert payload["archiveDownloadExecuted"] is False
    assert payload["credentialPersisted"] is False
    assert payload["nextRecommendedNextLever"] == "football_external_soccernet_video_frame_probe"
    assert extracted.read_bytes().startswith(b"\x00\x00\x00\x18ftyp")


def test_video_member_extract_blocks_without_runtime_credential(tmp_path: Path) -> None:
    _write_inputs(tmp_path)

    payload = extract.run_football_external_soccernet_video_member_extract(storage_root=tmp_path, env={})

    assert payload["goalAchieved"] is False
    assert payload["primaryBlocker"] == "football_external_soccernet_video_member_extract_credential_missing"
    assert payload["nextRecommendedNextLever"] == "football_external_soccernet_secret_env_setup"


def test_video_member_extract_blocks_without_approval(tmp_path: Path) -> None:
    _write_inputs(tmp_path, approved=False)

    payload = extract.run_football_external_soccernet_video_member_extract(storage_root=tmp_path, env={"SOCCERNET_PASSWORD": "x"})

    assert payload["goalAchieved"] is False
    assert payload["primaryBlocker"] == "football_external_soccernet_video_member_extract_approval_missing"
    assert payload["nextRecommendedNextLever"] == "football_external_soccernet_video_member_extract_approval"


def test_video_member_extract_contains_three_adaptive_attempts(tmp_path: Path) -> None:
    _write_inputs(tmp_path)

    payload = extract.run_football_external_soccernet_video_member_extract(
        storage_root=tmp_path,
        video_member_payload=b"\x00\x00\x00\x18ftypmp42payload",
        env={"SOCCERNET_PASSWORD": "runtime-only"},
    )

    assert payload["attemptPlanFamilies"] == [
        "scoped_encrypted_video_member_extract",
        "video_member_extract_runtime_repair",
        "video_member_extract_blocker_summary",
    ]


def test_video_member_extract_streams_large_member_under_rss_ceiling(tmp_path: Path) -> None:
    shim = tmp_path / "shim"
    _write_pyzipper_shim(shim)
    archive = tmp_path / "large.zip"
    member = "game/224p.mp4"
    size = 64 * 1024 * 1024
    with zipfile.ZipFile(archive, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        with zf.open(member, "w") as stream:
            for _ in range(64):
                stream.write(b"\0" * (1024 * 1024))

    output_dir = tmp_path / "output"
    limited_python = tmp_path / "limited-python"
    _write_memory_limited_python(limited_python)
    result = extract._extract_with_pyzipper(
        python_executable=str(limited_python),
        sparse_zip_path=archive,
        member_path=member,
        expected_size_bytes=size,
        output_dir=output_dir,
        env={"PYTHONPATH": str(shim), "SOCCERNET_PASSWORD": "runtime-only"},
        credential_env_var="SOCCERNET_PASSWORD",
    )

    assert result["returnCode"] == 0, result["stderrTail"]
    assert result["parsedResult"]["sizeBytes"] == size
    assert (output_dir / member).stat().st_size == size


def test_video_member_extract_rejects_stream_larger_than_declared_size(tmp_path: Path) -> None:
    shim = tmp_path / "shim"
    _write_pyzipper_shim(shim, actual_size=5, declared_size=4)
    output_dir = tmp_path / "output"

    result = extract._extract_with_pyzipper(
        python_executable=sys.executable,
        sparse_zip_path=tmp_path / "unused.zip",
        member_path="game/224p.mp4",
        expected_size_bytes=4,
        output_dir=output_dir,
        env={"PYTHONPATH": str(shim), "SOCCERNET_PASSWORD": "runtime-only"},
        credential_env_var="SOCCERNET_PASSWORD",
    )

    assert result["returnCode"] != 0
    assert not (output_dir / "game/224p.mp4").exists()
