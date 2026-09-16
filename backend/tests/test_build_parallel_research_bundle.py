from __future__ import annotations

import json
import os
from pathlib import Path
import stat
import zipfile

import pytest

import backend.scripts.build_parallel_research_bundle as build_parallel_research_bundle


def _write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _write_json(path: Path, payload: dict[str, object]) -> None:
    _write_text(path, json.dumps(payload, indent=2))


def _build_minimal_repo(repo_root: Path) -> None:
    _write_text(repo_root / "README.md", "# Fotball Analyst\n")
    _write_text(repo_root / "SESSION-HANDOFF.md", "# Session Handoff\n")
    _write_text(repo_root / "docs" / "video-analysis-research-brief.md", "# Research Brief\n")
    _write_text(repo_root / "lap.py", "print('lap')\n")
    _write_text(repo_root / "backend" / "scripts" / "worker.py", "print('worker')\n")
    _write_text(repo_root / "backend" / "tests" / "test_worker.py", "def test_ok():\n    assert True\n")
    _write_text(repo_root / "research-addon" / "helpers.py", "print('helper')\n")
    _write_text(repo_root / "memorybank" / "activeContext.md", "# Active Context\n")
    _write_text(repo_root / "memorybank" / "currentRoadmap.md", "# Roadmap\n")
    _write_text(repo_root / "memorybank" / "progress.md", "# Progress\n")
    _write_text(repo_root / "memorybank" / "features" / "source-robustness-lane.md", "# Source Robustness\n")
    _write_text(repo_root / "memorybank" / "operations" / "touchline-detector-evaluation-workflow.md", "# Eval Workflow\n")
    _write_text(repo_root / "memorybank" / "operations" / "touchline-detector-training-workflow.md", "# Training Workflow\n")
    _write_text(repo_root / "memorybank" / "operations" / "touchline-review-densification-workflow.md", "# Review Workflow\n")
    _write_text(
        repo_root / "docs" / "superpowers" / "plans" / "2026-04-11-active-now-systematic-roadmap.md",
        "# Active Roadmap\n",
    )
    _write_text(
        repo_root / "docs" / "superpowers" / "plans" / "2026-04-19-current-state-report.md",
        "# Current State Report\n",
    )

    _write_text(repo_root / "backend" / "scripts" / "run_source_robustness_batch.py", "print('robustness')\n")
    _write_text(repo_root / "backend" / "scripts" / "run_touchline_training_data_curation_batch.py", "print('curation')\n")
    _write_text(repo_root / "backend" / "scripts" / "run_touchline_review_densification_batch.py", "print('densify')\n")
    _write_text(repo_root / "backend" / "scripts" / "run_touchline_detector_candidate_training.py", "print('training')\n")
    _write_text(repo_root / "backend" / "scripts" / "run_touchline_detector_candidate_evaluation.py", "print('evaluation')\n")
    _write_text(repo_root / "backend" / "scripts" / "run_touchline_detector_candidate_failure_analysis.py", "print('failure-analysis')\n")
    _write_text(repo_root / "backend" / "scripts" / "run_touchline_detector_candidate_model_data_quality_fix.py", "print('data-fix')\n")
    _write_text(repo_root / "backend" / "scripts" / "run_touchline_detector_candidate_proposal_signal_generation_fix.py", "print('proposal-fix')\n")
    _write_text(repo_root / "backend" / "scripts" / "run_trimmed_ball_recovery_matrix.py", "print('matrix')\n")
    _write_text(repo_root / "backend" / "scripts" / "run_pod_proof_cycle.py", "print('proof')\n")
    _write_text(repo_root / "backend" / "scripts" / "runpod_session.py", "print('runpod')\n")
    _write_text(repo_root / "backend" / "run_guerilla.py", "print('guerilla')\n")
    _write_text(repo_root / "backend" / "app" / "proof_runtime.py", "print('proof_runtime')\n")
    _write_text(repo_root / "backend" / "app" / "video_pipeline.py", "print('video_pipeline')\n")
    _write_text(repo_root / "backend" / "app" / "processor.py", "print('processor')\n")

    suite_root = repo_root / "backend" / "storage" / "benchmark_suites" / "frozen-viable-baseline-slice-suite"
    _write_json(
        suite_root / "suite_summary.json",
        {
            "suiteVerdict": "baseline_not_robust",
            "sourceRobustnessRecommendedNextLever": "evaluate_touchline_detector_candidate",
            "detectorTrainingDiagnosis": {
                "trainingCandidateName": "touchline_detector_candidate_v4",
                "trainingBatchName": "touchline_detector_candidate_proposal_signal_generation_fix_v1",
            },
            "detectorCandidateProposalSignalFixDiagnosis": {
                "trainingCandidateName": "touchline_detector_candidate_v4",
                "proposalSignalFixBatchName": "touchline_proposal_signal_generation_fix_v1",
                "proposalPositiveExampleCount": 99,
                "proposalNegativeExampleCount": 12,
                "batchOutcomeAnalysis": {
                    "englishSummary": (
                        "This batch converted the reviewed source set into proposal-aligned crops, "
                        "increased the ball's relative size in the export, and trained an evaluation-ready v4 candidate."
                    ),
                    "englishDecision": (
                        "The batch achieved its goal, but the suite still stays on "
                        "evaluate_touchline_detector_candidate until v4 wins bounded evaluation."
                    ),
                    "goalAchieved": True,
                    "nextRecommendedNextLever": "evaluate_touchline_detector_candidate",
                },
            },
        },
    )
    _write_json(suite_root / "active_lane_snapshot.json", {"sourceRobustnessRecommendedNextLever": "evaluate_touchline_detector_candidate"})
    _write_json(suite_root / "suite_robustness_diagnosis.json", {"sourceRobustnessRecommendedNextLever": "evaluate_touchline_detector_candidate"})

    curation_root = repo_root / "backend" / "storage" / "training_prep" / "touchline_training_data_curation_foundation"
    _write_json(curation_root / "curation_manifest.json", {"name": "foundation"})
    _write_json(curation_root / "split_manifest.json", {"name": "foundation-split"})
    _write_json(curation_root / "seeded_issue_report.json", {"issues": []})

    review_root = repo_root / "backend" / "storage" / "training_prep" / "touchline_review_densification_v1"
    _write_json(review_root / "review_densification_manifest.json", {"name": "review"})
    _write_json(review_root / "reviewed_label_overlay.json", {"items": []})
    _write_json(review_root / "review_bundle_report.json", {"bundles": []})
    _write_json(review_root / "split_manifest.json", {"name": "review-split"})
    _write_json(review_root / "batch_outcome_analysis.json", {"goalAchieved": True})

    data_fix_root = repo_root / "backend" / "storage" / "training_prep" / "touchline_model_data_quality_fix_v1"
    _write_json(data_fix_root / "data_quality_fix_manifest.json", {"name": "data-fix"})
    _write_json(data_fix_root / "reviewed_label_overlay.json", {"items": []})
    _write_json(data_fix_root / "review_bundle_report.json", {"bundles": []})
    _write_json(data_fix_root / "split_manifest.json", {"name": "data-fix-split"})
    _write_json(data_fix_root / "batch_outcome_analysis.json", {"goalAchieved": True})

    proposal_fix_root = repo_root / "backend" / "storage" / "training_prep" / "touchline_proposal_signal_generation_fix_v1"
    _write_json(proposal_fix_root / "proposal_signal_fix_manifest.json", {"name": "proposal-fix"})
    _write_json(proposal_fix_root / "split_manifest.json", {"name": "proposal-fix-split"})
    _write_json(
        proposal_fix_root / "batch_outcome_analysis.json",
        {
            "goalAchieved": True,
            "englishSummary": "proposal-signal fix outcome",
            "nextRecommendedNextLever": "evaluate_touchline_detector_candidate",
        },
    )

    v2_root = repo_root / "backend" / "storage" / "trained_detector_candidates" / "touchline_detector_candidate_v2"
    _write_json(v2_root / "training_run_summary.json", {"name": "v2"})
    _write_json(v2_root / "batch_outcome_analysis.json", {"goalAchieved": True})
    _write_json(v2_root / "evaluation_contract.json", {"targetClip": "trimed-5min.mp4"})
    _write_text(v2_root / "results.csv", "epoch,metric\n1,0.1\n")
    _write_json(v2_root / "evaluation_v1" / "evaluation_summary.json", {"name": "v2-eval"})
    _write_json(v2_root / "evaluation_v1" / "screen_matrix.json", {"name": "v2-screen"})
    _write_json(v2_root / "evaluation_v1" / "proof_report.json", {"name": "v2-proof"})
    _write_json(v2_root / "evaluation_v1" / "batch_outcome_analysis.json", {"goalAchieved": False})
    _write_json(v2_root / "evaluation_v1" / "evaluation_contract.json", {"targetClip": "trimed-5min.mp4"})

    v3_root = repo_root / "backend" / "storage" / "trained_detector_candidates" / "touchline_detector_candidate_v3"
    _write_json(v3_root / "training_run_summary.json", {"name": "v3"})
    _write_json(v3_root / "batch_outcome_analysis.json", {"goalAchieved": True})
    _write_json(v3_root / "evaluation_contract.json", {"targetClip": "trimed-5min.mp4"})
    _write_json(v3_root / "remote_training_result.json", {"status": "ok"})
    _write_json(v3_root / "evaluation_v1" / "evaluation_summary.json", {"name": "v3-eval"})
    _write_json(v3_root / "evaluation_v1" / "screen_matrix.json", {"name": "v3-screen"})
    _write_json(v3_root / "evaluation_v1" / "proof_report.json", {"name": "v3-proof"})
    _write_json(
        v3_root / "evaluation_v1" / "batch_outcome_analysis.json",
        {
            "goalAchieved": False,
            "englishSummary": "v3 evaluation failed honestly",
            "nextRecommendedNextLever": "evaluate_touchline_detector_candidate",
        },
    )
    _write_json(
        v3_root / "failure_analysis_v1" / "failure_analysis_summary.json",
        {
            "rootCauseClass": "auxiliary_probe_zero_raw_rows",
            "changeFromPreviousCandidateClass": "no_observable_improvement",
            "recommendedFixClass": "model_data_quality",
            "recommendedFixFocus": "proposal_signal_generation",
        },
    )
    _write_json(v3_root / "failure_analysis_v1" / "candidate_vs_baseline_delta.json", {"name": "delta"})
    _write_json(v3_root / "failure_analysis_v1" / "candidate_vs_previous_candidate_delta.json", {"name": "previous-delta"})
    _write_json(v3_root / "failure_analysis_v1" / "profile_matrix_delta.json", {"name": "profile-delta"})
    _write_json(v3_root / "failure_analysis_v1" / "frame_level_probe_delta.json", {"name": "frame-delta"})
    _write_json(
        v3_root / "failure_analysis_v1" / "batch_outcome_analysis.json",
        {
            "goalAchieved": True,
            "englishSummary": "v3 failure analysis narrowed the issue to proposal_signal_generation",
            "recommendedFixFocus": "proposal_signal_generation",
        },
    )

    v4_root = repo_root / "backend" / "storage" / "trained_detector_candidates" / "touchline_detector_candidate_v4"
    _write_json(v4_root / "training_run_summary.json", {"name": "v4"})
    _write_json(
        v4_root / "batch_outcome_analysis.json",
        {
            "goalAchieved": True,
            "englishSummary": "This batch trained a refreshed v4 detector candidate from proposal-aligned crops and produced a complete evaluation-ready artifact.",
            "englishDecision": "The batch achieved its goal, but the roadmap stays pinned on evaluate_touchline_detector_candidate until v4 wins bounded evaluation.",
            "nextRecommendedNextLever": "evaluate_touchline_detector_candidate",
        },
    )
    _write_json(v4_root / "evaluation_contract.json", {"targetClip": "trimed-5min.mp4"})
    _write_json(v4_root / "remote_training_result.json", {"status": "ok"})
    _write_text(v4_root / "results.csv", "epoch,metric\n1,0.2\n")

    _write_text(repo_root / "videos" / "clip.mp4", "video")
    _write_text(repo_root / "backend" / "venv" / "lib" / "site.py", "print('venv')\n")
    _write_text(repo_root / "frontend" / "node_modules" / "pkg" / "index.js", "console.log('x')\n")
    _write_text(repo_root / "backend" / "storage" / "trained_detector_candidates" / "touchline_detector_candidate_v4" / "weights" / "best.pt", "weights")
    _write_text(repo_root / "backend" / "storage" / "training_prep" / "touchline_model_data_quality_fix_v1" / "yolo_export" / "images" / "frame.jpg", "image")
    _write_text(repo_root / "backend" / "storage" / "training_prep" / "touchline_model_data_quality_fix_v1" / "yolo_export" / "labels" / "frame.txt", "label")
    _write_text(repo_root / "backend" / "__pycache__" / "tmp.pyc", "cache")


def test_build_parallel_research_bundle_includes_expected_files_and_excludes_heavy_content(tmp_path: Path) -> None:
    _build_minimal_repo(tmp_path)

    result = build_parallel_research_bundle.build_parallel_research_bundle(
        repo_root=tmp_path,
        bundle_date="2026-04-23",
    )

    bundle_root = Path(result["bundleRoot"])
    zip_path = Path(result["zipPath"])
    manifest_path = bundle_root / "bundle_manifest.json"
    readme_path = bundle_root / "README.md"

    assert bundle_root.exists()
    assert zip_path.exists()
    assert manifest_path.exists()
    assert readme_path.exists()

    assert (bundle_root / "backend" / "scripts" / "worker.py").exists()
    assert (bundle_root / "backend" / "tests" / "test_worker.py").exists()
    assert (bundle_root / "research-addon" / "helpers.py").exists()
    assert (bundle_root / "memorybank" / "activeContext.md").exists()
    assert (bundle_root / "backend" / "storage" / "benchmark_suites" / "frozen-viable-baseline-slice-suite" / "suite_summary.json").exists()

    assert not (bundle_root / "videos" / "clip.mp4").exists()
    assert not (bundle_root / "backend" / "venv" / "lib" / "site.py").exists()
    assert not (bundle_root / "frontend" / "node_modules" / "pkg" / "index.js").exists()
    assert not (bundle_root / "backend" / "storage" / "trained_detector_candidates" / "touchline_detector_candidate_v4" / "weights" / "best.pt").exists()
    assert not (bundle_root / "backend" / "storage" / "training_prep" / "touchline_model_data_quality_fix_v1" / "yolo_export" / "images" / "frame.jpg").exists()
    assert not (bundle_root / "backend" / "__pycache__" / "tmp.pyc").exists()

    readme_text = readme_path.read_text(encoding="utf-8")
    assert "touchline_detector_candidate_v4" in readme_text
    assert "evaluate_touchline_detector_candidate" in readme_text
    assert "baseline_not_robust" in readme_text
    assert "proposal-signal" in readme_text.lower()

    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    included_files = set(manifest["includedRepoFiles"])
    assert "backend/scripts/worker.py" in included_files
    assert "memorybank/activeContext.md" in included_files
    assert "videos/clip.mp4" not in included_files

    with zipfile.ZipFile(zip_path) as archive:
        names = set(archive.namelist())
    assert "fotball-analyst-research-pack-2026-04-23/README.md" in names
    assert "fotball-analyst-research-pack-2026-04-23/backend/scripts/worker.py" in names
    assert "fotball-analyst-research-pack-2026-04-23/memorybank/activeContext.md" in names
    assert "fotball-analyst-research-pack-2026-04-23/videos/clip.mp4" not in names


def test_build_parallel_research_core_bundle_keeps_only_curated_core_files(tmp_path: Path) -> None:
    _build_minimal_repo(tmp_path)

    result = build_parallel_research_bundle.build_parallel_research_bundle(
        repo_root=tmp_path,
        bundle_date="2026-04-23",
        profile="core",
    )

    bundle_root = Path(result["bundleRoot"])
    zip_path = Path(result["zipPath"])
    manifest = json.loads((bundle_root / "bundle_manifest.json").read_text(encoding="utf-8"))

    assert result["bundleName"] == "fotball-analyst-research-core-pack-2026-04-23"
    assert manifest["profile"] == "core"
    assert (bundle_root / "backend" / "scripts" / "run_touchline_detector_candidate_evaluation.py").exists()
    assert (bundle_root / "backend" / "app" / "proof_runtime.py").exists()
    assert (bundle_root / "memorybank" / "activeContext.md").exists()
    assert (bundle_root / "backend" / "storage" / "trained_detector_candidates" / "touchline_detector_candidate_v4" / "batch_outcome_analysis.json").exists()

    assert not (bundle_root / "backend" / "scripts" / "worker.py").exists()
    assert not (bundle_root / "backend" / "tests" / "test_worker.py").exists()
    assert not (bundle_root / "research-addon" / "helpers.py").exists()

    readme_text = (bundle_root / "README.md").read_text(encoding="utf-8")
    assert "Core Pack" in readme_text
    assert "touchline_detector_candidate_v4" in readme_text
    assert "evaluate_touchline_detector_candidate" in readme_text

    included_files = set(manifest["includedRepoFiles"])
    assert "backend/scripts/run_touchline_detector_candidate_evaluation.py" in included_files
    assert "backend/scripts/worker.py" not in included_files
    assert "research-addon/helpers.py" not in included_files

    with zipfile.ZipFile(zip_path) as archive:
        names = set(archive.namelist())
    assert "fotball-analyst-research-core-pack-2026-04-23/README.md" in names
    assert "fotball-analyst-research-core-pack-2026-04-23/backend/scripts/run_touchline_detector_candidate_evaluation.py" in names
    assert "fotball-analyst-research-core-pack-2026-04-23/backend/scripts/worker.py" not in names


@pytest.mark.parametrize("bundle_date", [
    "../outside", "2026-04-23/../../outside", "2026-04-23\\..\\outside",
    "/2026-04-23", "..", "2026-02-30", "2026-13-01", "not-a-date",
])
@pytest.mark.parametrize("profile", ["full", "core"])
def test_bundle_date_rejects_path_components(tmp_path: Path, bundle_date: str, profile: str) -> None:
    _build_minimal_repo(tmp_path / "repo")
    output = tmp_path / "archive"
    sentinel = tmp_path / "outside" / "keep.txt"
    _write_text(sentinel, "keep")
    with pytest.raises(ValueError):
        build_parallel_research_bundle.build_parallel_research_bundle(
            repo_root=tmp_path / "repo", archive_root=output, bundle_date=bundle_date, profile=profile,
        )
    assert not output.exists()
    assert sentinel.read_text() == "keep"


@pytest.mark.parametrize("profile,prefix", [
    ("full", "fotball-analyst-research-pack"), ("core", "fotball-analyst-research-core-pack"),
])
def test_bundle_date_is_canonical_everywhere(tmp_path: Path, profile: str, prefix: str) -> None:
    _build_minimal_repo(tmp_path / "repo")
    output = tmp_path / "custom" / "archive"
    bundle = output / f"{prefix}-2026-04-23"
    _write_text(bundle / "stale.txt", "replace this exact bundle")
    _write_text(bundle / "nested" / "old.txt", "remove nested old content")
    outside = tmp_path / "outside"
    _write_text(outside / "keep.txt", "outside sentinel")
    (bundle / "directory-link").symlink_to(outside, target_is_directory=True)
    (bundle / "file-link").symlink_to(outside / "keep.txt")
    (bundle / "dangling-link").symlink_to(outside / "absent")
    _write_text(output / "historical.zip", "keep historical archive")
    _write_text(output / "historical" / "keep.txt", "keep historical directory")
    result = build_parallel_research_bundle.build_parallel_research_bundle(
        repo_root=tmp_path / "repo", archive_root=output, bundle_date="20260423", profile=profile,
    )
    assert Path(result["bundleRoot"]) == bundle
    assert Path(result["zipPath"]) == output / f"{prefix}-2026-04-23.zip"
    manifest = json.loads((bundle / "bundle_manifest.json").read_text())
    assert manifest["bundleDate"] == "2026-04-23"
    assert manifest["bundleName"] == bundle.name
    assert "on `2026-04-23`" in (bundle / "README.md").read_text()
    assert not (bundle / "stale.txt").exists()
    assert not (bundle / "nested").exists()
    assert not any((bundle / name).is_symlink() for name in ["directory-link", "file-link", "dangling-link"])
    assert (outside / "keep.txt").read_text() == "outside sentinel"
    assert (output / "historical.zip").read_text() == "keep historical archive"
    assert (output / "historical" / "keep.txt").read_text() == "keep historical directory"
    with zipfile.ZipFile(result["zipPath"]) as archive:
        assert archive.testzip() is None
        assert set(archive.namelist()) == {
            f"{bundle.name}/{name}" for name in manifest["includedRepoFiles"] + ["README.md", "bundle_manifest.json"]
        }


@pytest.mark.parametrize("target", ["archive", "ancestor", "bundle", "zip", "dangling_zip"])
def test_bundle_rejects_output_symlinks(tmp_path: Path, target: str) -> None:
    repo = tmp_path / "repo"
    _build_minimal_repo(repo)
    output = tmp_path / "parent" / "archive"
    output.mkdir(parents=True)
    name = "fotball-analyst-research-pack-2026-04-23"
    outside = tmp_path / "outside"
    _write_text(outside / "keep.txt", "outside")
    prior = output / f"{name}.zip"
    prior.write_bytes(b"previous archive")
    if target == "archive":
        output.rename(tmp_path / "original")
        output.symlink_to(outside, target_is_directory=True)
        prior = tmp_path / "original" / prior.name
    elif target == "ancestor":
        output.parent.rename(tmp_path / "original")
        output.parent.symlink_to(outside, target_is_directory=True)
        prior = tmp_path / "original" / "archive" / prior.name
    elif target == "bundle":
        (output / name).symlink_to(outside, target_is_directory=True)
    else:
        prior.unlink()
        prior.symlink_to(outside / ("keep.txt" if target == "zip" else "missing.zip"))
    with pytest.raises((ValueError, OSError)):
        build_parallel_research_bundle.build_parallel_research_bundle(
            repo_root=repo, archive_root=output, bundle_date="2026-04-23",
        )
    assert (outside / "keep.txt").read_text() == "outside"
    assert sorted(p.name for p in outside.iterdir()) == ["keep.txt"]
    if target in {"zip", "dangling_zip"}:
        assert prior.is_symlink()
    else:
        assert prior.read_bytes() == b"previous archive"


@pytest.mark.parametrize("fault", ["write", "close", "file_fsync", "replace"])
def test_bundle_failure_preserves_previous_archive(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, fault: str) -> None:
    _build_minimal_repo(tmp_path)
    output = tmp_path / "archive"
    output.mkdir()
    name = "fotball-analyst-research-pack-2026-04-23"
    prior = output / f"{name}.zip"
    with zipfile.ZipFile(prior, "w") as archive:
        archive.writestr("previous.txt", "previous archive")
    before = prior.read_bytes()
    if fault in {"write", "close"}:
        original = getattr(zipfile.ZipFile, fault)

        def fail(archive, *args, **kwargs):
            was_open = archive.fp is not None
            original(archive, *args, **kwargs)
            if archive.mode == "w" and was_open:
                raise OSError(f"injected {fault}")

        monkeypatch.setattr(zipfile.ZipFile, fault, fail)
    elif fault == "file_fsync":
        original = os.fsync

        def fail(fd):
            if stat.S_ISREG(os.fstat(fd).st_mode):
                raise OSError("injected file_fsync")
            original(fd)

        monkeypatch.setattr(os, "fsync", fail)
    else:
        def fail(*args, **kwargs):
            raise OSError("injected replace")

        monkeypatch.setattr(os, "replace", fail)
    with pytest.raises(OSError, match=f"injected {fault}"):
        build_parallel_research_bundle.build_parallel_research_bundle(repo_root=tmp_path, bundle_date="2026-04-23")
    assert prior.read_bytes() == before
    assert sorted(p.name for p in output.iterdir()) == [name, f"{name}.zip"]


@pytest.mark.parametrize("boundary", ["reset", "copy", "zip"])
@pytest.mark.parametrize("target", ["archive", "ancestor", "bundle"])
def test_bundle_rejects_namespace_swaps(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, boundary: str, target: str) -> None:
    repo = tmp_path / "repo"
    _build_minimal_repo(repo)
    output = tmp_path / "parent" / "archive"
    name = "fotball-analyst-research-pack-2026-04-23"
    _write_text(output / name / "old.txt", "old bundle")
    prior = output / f"{name}.zip"
    prior.write_bytes(b"previous archive")
    outside = tmp_path / "outside"
    _write_text(outside / "keep.txt", "outside")
    moved = tmp_path / "moved"
    swap_path = {"archive": output, "ancestor": output.parent, "bundle": output / name}[target]
    swapped = False

    def swap():
        nonlocal swapped
        if not swapped:
            swapped = True
            swap_path.rename(moved)
            swap_path.symlink_to(outside, target_is_directory=True)

    if boundary == "reset":
        original = os.stat

        def trigger(path, *args, **kwargs):
            result = original(path, *args, **kwargs)
            if path == name and kwargs.get("dir_fd") is not None:
                swap()
            return result

        monkeypatch.setattr(os, "stat", trigger)
    elif boundary == "copy":
        original = build_parallel_research_bundle._copy_repo_file

        def trigger(*args, **kwargs):
            swap()
            return original(*args, **kwargs)

        monkeypatch.setattr(build_parallel_research_bundle, "_copy_repo_file", trigger)
    else:
        original = zipfile.ZipFile.write

        def trigger(*args, **kwargs):
            swap()
            return original(*args, **kwargs)

        monkeypatch.setattr(zipfile.ZipFile, "write", trigger)
    with pytest.raises((ValueError, OSError)):
        build_parallel_research_bundle.build_parallel_research_bundle(
            repo_root=repo, archive_root=output, bundle_date="2026-04-23",
        )
    assert swapped
    assert sorted(p.name for p in outside.iterdir()) == ["keep.txt"]
    assert (outside / "keep.txt").read_text() == "outside"
    saved_root = {"archive": moved, "ancestor": moved / "archive", "bundle": output}[target]
    assert (saved_root / prior.name).read_bytes() == b"previous archive"
    assert not list(saved_root.glob(".*.tmp"))


@pytest.mark.parametrize("target", ["archive", "zip"])
def test_bundle_rejects_replaced_identity(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, target: str) -> None:
    _build_minimal_repo(tmp_path)
    output = tmp_path / "archive"
    output.mkdir()
    prior = output / "fotball-analyst-research-pack-2026-04-23.zip"
    prior.write_bytes(b"prior archive")
    moved = tmp_path / "moved"
    original = zipfile.ZipFile.write
    swapped = False

    def swap_then_write(*args, **kwargs):
        nonlocal swapped
        if not swapped:
            swapped = True
            if target == "archive":
                output.rename(moved)
                output.mkdir()
            else:
                prior.rename(moved)
            prior.write_bytes(b"replacement sentinel")
        return original(*args, **kwargs)

    monkeypatch.setattr(zipfile.ZipFile, "write", swap_then_write)
    with pytest.raises((ValueError, OSError)):
        build_parallel_research_bundle.build_parallel_research_bundle(repo_root=tmp_path, bundle_date="2026-04-23")
    assert prior.read_bytes() == b"replacement sentinel"
    retained = moved / prior.name if target == "archive" else moved
    assert retained.read_bytes() == b"prior archive"


def test_bundle_publishes_closed_valid_synced_zip(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    _build_minimal_repo(tmp_path)
    events = []
    original_fsync, original_replace = os.fsync, os.replace

    def sync(fd):
        events.append("directory" if stat.S_ISDIR(os.fstat(fd).st_mode) else "file")
        return original_fsync(fd)

    def replace(source, destination, *, src_dir_fd=None, dst_dir_fd=None):
        with os.fdopen(os.open(source, os.O_RDONLY, dir_fd=src_dir_fd), "rb") as handle:
            with zipfile.ZipFile(handle) as archive:
                assert archive.testzip() is None
                assert "fotball-analyst-research-pack-2026-04-23/README.md" in archive.namelist()
        events.append("replace")
        return original_replace(source, destination, src_dir_fd=src_dir_fd, dst_dir_fd=dst_dir_fd)

    monkeypatch.setattr(os, "fsync", sync)
    monkeypatch.setattr(os, "replace", replace)
    build_parallel_research_bundle.build_parallel_research_bundle(repo_root=tmp_path, bundle_date="2026-04-23")
    assert events == ["file", "replace", "directory"]


@pytest.mark.parametrize("fault", ["unavailable", "wrong_directory"])
def test_bundle_requires_bound_proc_fd_path(tmp_path: Path, monkeypatch: pytest.MonkeyPatch, fault: str) -> None:
    _build_minimal_repo(tmp_path)
    output = tmp_path / "archive"
    name = "fotball-analyst-research-pack-2026-04-23"
    _write_text(output / name / "old.txt", "old bundle")
    prior = output / f"{name}.zip"
    prior.write_bytes(b"prior archive")
    original = Path.stat

    def stat_path(path, *args, **kwargs):
        if str(path).startswith("/proc/self/fd/"):
            if fault == "unavailable":
                raise FileNotFoundError("proc fd unavailable")
            return original(tmp_path)
        return original(path, *args, **kwargs)

    monkeypatch.setattr(Path, "stat", stat_path)
    with pytest.raises((ValueError, OSError)):
        build_parallel_research_bundle.build_parallel_research_bundle(repo_root=tmp_path, bundle_date="2026-04-23")
    assert prior.read_bytes() == b"prior archive"
    assert (output / name / "old.txt").read_text() == "old bundle"


def test_bundle_rejects_replaced_temporary_zip(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    _build_minimal_repo(tmp_path)
    output = tmp_path / "archive"
    output.mkdir()
    prior = output / "fotball-analyst-research-pack-2026-04-23.zip"
    prior.write_bytes(b"prior archive")
    outside = tmp_path / "outside.zip"
    outside.write_bytes(b"outside sentinel")
    original = os.fsync

    def swap_then_sync(fd):
        if stat.S_ISREG(os.fstat(fd).st_mode):
            [temporary] = output.glob(".*.tmp")
            temporary.unlink()
            temporary.symlink_to(outside)
        return original(fd)

    monkeypatch.setattr(os, "fsync", swap_then_sync)
    with pytest.raises((ValueError, OSError)):
        build_parallel_research_bundle.build_parallel_research_bundle(repo_root=tmp_path, bundle_date="2026-04-23")
    assert prior.read_bytes() == b"prior archive"
    assert outside.read_bytes() == b"outside sentinel"
    assert not list(output.glob(".*.tmp"))


@pytest.mark.parametrize("boundary", ["classified", "traversal"])
@pytest.mark.parametrize("populated", [False, True])
def test_bundle_reset_rejects_replacement_directory(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch, boundary: str, populated: bool,
) -> None:
    _build_minimal_repo(tmp_path / "repo")
    output = tmp_path / "archive"
    bundle = output / "fotball-analyst-research-pack-2026-04-23"
    _write_text(bundle / "nested" / "old.txt", "old bundle")
    prior = output / f"{bundle.name}.zip"
    prior.write_bytes(b"previous archive")
    moved = tmp_path / "original-bundle"
    before = bundle.stat()
    swapped = False
    replacement = None

    def swap():
        nonlocal swapped, replacement
        swapped = True
        bundle.rename(moved)
        bundle.mkdir()
        if populated:
            _write_text(bundle / "keep.txt", "replacement sentinel")
        replacement = bundle.stat()

    if boundary == "classified":
        original = os.stat

        def trigger(path, *args, **kwargs):
            result = original(path, *args, **kwargs)
            if not swapped and path == bundle.name and kwargs.get("dir_fd") is not None:
                swap()
            return result

        monkeypatch.setattr(os, "stat", trigger)
    else:
        original = os.scandir

        def trigger(path):
            if not swapped and isinstance(path, int) and os.path.samestat(os.fstat(path), before):
                swap()
            return original(path)

        monkeypatch.setattr(os, "scandir", trigger)

    with pytest.raises((ValueError, OSError)):
        build_parallel_research_bundle.build_parallel_research_bundle(
            repo_root=tmp_path / "repo", archive_root=output, bundle_date="2026-04-23",
        )
    assert swapped
    assert os.path.samestat(bundle.stat(), replacement)
    if populated:
        assert (bundle / "keep.txt").read_text() == "replacement sentinel"
    assert prior.read_bytes() == b"previous archive"
