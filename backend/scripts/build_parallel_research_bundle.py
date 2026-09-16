from __future__ import annotations

import argparse
from contextlib import contextmanager, ExitStack
from datetime import date, datetime, timezone
import json
import os
from pathlib import Path, PurePosixPath
import secrets
import shutil
import stat
import sys
from typing import Callable
import zipfile

REPO_ROOT = Path(__file__).resolve().parents[2]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

FULL_BUNDLE_PREFIX = "fotball-analyst-research-pack"
CORE_BUNDLE_PREFIX = "fotball-analyst-research-core-pack"
DEFAULT_ARCHIVE_ROOT = REPO_ROOT / "archive"

SUITE_ROOT = Path("backend/storage/benchmark_suites/frozen-viable-baseline-slice-suite")
TRAINING_PREP_ROOT = Path("backend/storage/training_prep")
TRAINED_CANDIDATES_ROOT = Path("backend/storage/trained_detector_candidates")

DOCUMENT_PATHS = [
    Path("SESSION-HANDOFF.md"),
    Path("docs/superpowers/plans/2026-04-11-active-now-systematic-roadmap.md"),
    Path("docs/superpowers/plans/2026-04-19-current-state-report.md"),
]

CORE_DOCUMENT_PATHS = [
    Path("SESSION-HANDOFF.md"),
    Path("docs/video-analysis-research-brief.md"),
    Path("docs/superpowers/plans/2026-04-11-active-now-systematic-roadmap.md"),
    Path("docs/superpowers/plans/2026-04-19-current-state-report.md"),
]

SUITE_TRUTH_PATHS = [
    SUITE_ROOT / "suite_summary.json",
    SUITE_ROOT / "active_lane_snapshot.json",
    SUITE_ROOT / "suite_robustness_diagnosis.json",
]

TRAINING_PREP_ARTIFACT_PATHS = [
    TRAINING_PREP_ROOT / "touchline_training_data_curation_foundation" / "curation_manifest.json",
    TRAINING_PREP_ROOT / "touchline_training_data_curation_foundation" / "split_manifest.json",
    TRAINING_PREP_ROOT / "touchline_training_data_curation_foundation" / "seeded_issue_report.json",
    TRAINING_PREP_ROOT / "touchline_review_densification_v1" / "review_densification_manifest.json",
    TRAINING_PREP_ROOT / "touchline_review_densification_v1" / "reviewed_label_overlay.json",
    TRAINING_PREP_ROOT / "touchline_review_densification_v1" / "review_bundle_report.json",
    TRAINING_PREP_ROOT / "touchline_review_densification_v1" / "split_manifest.json",
    TRAINING_PREP_ROOT / "touchline_review_densification_v1" / "batch_outcome_analysis.json",
    TRAINING_PREP_ROOT / "touchline_model_data_quality_fix_v1" / "data_quality_fix_manifest.json",
    TRAINING_PREP_ROOT / "touchline_model_data_quality_fix_v1" / "reviewed_label_overlay.json",
    TRAINING_PREP_ROOT / "touchline_model_data_quality_fix_v1" / "review_bundle_report.json",
    TRAINING_PREP_ROOT / "touchline_model_data_quality_fix_v1" / "split_manifest.json",
    TRAINING_PREP_ROOT / "touchline_model_data_quality_fix_v1" / "batch_outcome_analysis.json",
    TRAINING_PREP_ROOT / "touchline_proposal_signal_generation_fix_v1" / "proposal_signal_fix_manifest.json",
    TRAINING_PREP_ROOT / "touchline_proposal_signal_generation_fix_v1" / "split_manifest.json",
    TRAINING_PREP_ROOT / "touchline_proposal_signal_generation_fix_v1" / "batch_outcome_analysis.json",
]

CANDIDATE_ARTIFACT_PATHS = [
    TRAINED_CANDIDATES_ROOT / "touchline_detector_candidate_v2" / "training_run_summary.json",
    TRAINED_CANDIDATES_ROOT / "touchline_detector_candidate_v2" / "batch_outcome_analysis.json",
    TRAINED_CANDIDATES_ROOT / "touchline_detector_candidate_v2" / "evaluation_contract.json",
    TRAINED_CANDIDATES_ROOT / "touchline_detector_candidate_v2" / "results.csv",
    TRAINED_CANDIDATES_ROOT / "touchline_detector_candidate_v2" / "evaluation_v1" / "evaluation_summary.json",
    TRAINED_CANDIDATES_ROOT / "touchline_detector_candidate_v2" / "evaluation_v1" / "screen_matrix.json",
    TRAINED_CANDIDATES_ROOT / "touchline_detector_candidate_v2" / "evaluation_v1" / "proof_report.json",
    TRAINED_CANDIDATES_ROOT / "touchline_detector_candidate_v2" / "evaluation_v1" / "batch_outcome_analysis.json",
    TRAINED_CANDIDATES_ROOT / "touchline_detector_candidate_v2" / "evaluation_v1" / "evaluation_contract.json",
    TRAINED_CANDIDATES_ROOT / "touchline_detector_candidate_v3" / "training_run_summary.json",
    TRAINED_CANDIDATES_ROOT / "touchline_detector_candidate_v3" / "batch_outcome_analysis.json",
    TRAINED_CANDIDATES_ROOT / "touchline_detector_candidate_v3" / "evaluation_contract.json",
    TRAINED_CANDIDATES_ROOT / "touchline_detector_candidate_v3" / "remote_training_result.json",
    TRAINED_CANDIDATES_ROOT / "touchline_detector_candidate_v3" / "evaluation_v1" / "evaluation_summary.json",
    TRAINED_CANDIDATES_ROOT / "touchline_detector_candidate_v3" / "evaluation_v1" / "screen_matrix.json",
    TRAINED_CANDIDATES_ROOT / "touchline_detector_candidate_v3" / "evaluation_v1" / "proof_report.json",
    TRAINED_CANDIDATES_ROOT / "touchline_detector_candidate_v3" / "evaluation_v1" / "batch_outcome_analysis.json",
    TRAINED_CANDIDATES_ROOT / "touchline_detector_candidate_v3" / "failure_analysis_v1" / "failure_analysis_summary.json",
    TRAINED_CANDIDATES_ROOT / "touchline_detector_candidate_v3" / "failure_analysis_v1" / "candidate_vs_baseline_delta.json",
    TRAINED_CANDIDATES_ROOT / "touchline_detector_candidate_v3" / "failure_analysis_v1" / "candidate_vs_previous_candidate_delta.json",
    TRAINED_CANDIDATES_ROOT / "touchline_detector_candidate_v3" / "failure_analysis_v1" / "profile_matrix_delta.json",
    TRAINED_CANDIDATES_ROOT / "touchline_detector_candidate_v3" / "failure_analysis_v1" / "frame_level_probe_delta.json",
    TRAINED_CANDIDATES_ROOT / "touchline_detector_candidate_v3" / "failure_analysis_v1" / "batch_outcome_analysis.json",
    TRAINED_CANDIDATES_ROOT / "touchline_detector_candidate_v4" / "training_run_summary.json",
    TRAINED_CANDIDATES_ROOT / "touchline_detector_candidate_v4" / "batch_outcome_analysis.json",
    TRAINED_CANDIDATES_ROOT / "touchline_detector_candidate_v4" / "evaluation_contract.json",
    TRAINED_CANDIDATES_ROOT / "touchline_detector_candidate_v4" / "remote_training_result.json",
    TRAINED_CANDIDATES_ROOT / "touchline_detector_candidate_v4" / "results.csv",
]

CORE_CODE_PATHS = [
    Path("backend/scripts/run_source_robustness_batch.py"),
    Path("backend/scripts/run_touchline_training_data_curation_batch.py"),
    Path("backend/scripts/run_touchline_review_densification_batch.py"),
    Path("backend/scripts/run_touchline_detector_candidate_training.py"),
    Path("backend/scripts/run_touchline_detector_candidate_evaluation.py"),
    Path("backend/scripts/run_touchline_detector_candidate_failure_analysis.py"),
    Path("backend/scripts/run_touchline_detector_candidate_model_data_quality_fix.py"),
    Path("backend/scripts/run_touchline_detector_candidate_proposal_signal_generation_fix.py"),
    Path("backend/scripts/run_trimmed_ball_recovery_matrix.py"),
    Path("backend/scripts/run_pod_proof_cycle.py"),
    Path("backend/scripts/runpod_session.py"),
    Path("backend/run_guerilla.py"),
    Path("backend/app/proof_runtime.py"),
    Path("backend/app/video_pipeline.py"),
    Path("backend/app/processor.py"),
]

CORE_MEMORYBANK_PATHS = [
    Path("memorybank/activeContext.md"),
    Path("memorybank/progress.md"),
    Path("memorybank/currentRoadmap.md"),
    Path("memorybank/features/source-robustness-lane.md"),
    Path("memorybank/operations/touchline-detector-evaluation-workflow.md"),
    Path("memorybank/operations/touchline-detector-training-workflow.md"),
    Path("memorybank/operations/touchline-review-densification-workflow.md"),
]

CORE_TRAINING_PREP_ARTIFACT_PATHS = [
    TRAINING_PREP_ROOT / "touchline_training_data_curation_foundation" / "curation_manifest.json",
    TRAINING_PREP_ROOT / "touchline_review_densification_v1" / "review_densification_manifest.json",
    TRAINING_PREP_ROOT / "touchline_review_densification_v1" / "batch_outcome_analysis.json",
    TRAINING_PREP_ROOT / "touchline_model_data_quality_fix_v1" / "data_quality_fix_manifest.json",
    TRAINING_PREP_ROOT / "touchline_model_data_quality_fix_v1" / "batch_outcome_analysis.json",
    TRAINING_PREP_ROOT / "touchline_proposal_signal_generation_fix_v1" / "proposal_signal_fix_manifest.json",
    TRAINING_PREP_ROOT / "touchline_proposal_signal_generation_fix_v1" / "batch_outcome_analysis.json",
]

CORE_CANDIDATE_ARTIFACT_PATHS = [
    TRAINED_CANDIDATES_ROOT / "touchline_detector_candidate_v3" / "evaluation_v1" / "batch_outcome_analysis.json",
    TRAINED_CANDIDATES_ROOT / "touchline_detector_candidate_v3" / "failure_analysis_v1" / "failure_analysis_summary.json",
    TRAINED_CANDIDATES_ROOT / "touchline_detector_candidate_v3" / "failure_analysis_v1" / "profile_matrix_delta.json",
    TRAINED_CANDIDATES_ROOT / "touchline_detector_candidate_v3" / "failure_analysis_v1" / "frame_level_probe_delta.json",
    TRAINED_CANDIDATES_ROOT / "touchline_detector_candidate_v3" / "failure_analysis_v1" / "batch_outcome_analysis.json",
    TRAINED_CANDIDATES_ROOT / "touchline_detector_candidate_v4" / "training_run_summary.json",
    TRAINED_CANDIDATES_ROOT / "touchline_detector_candidate_v4" / "batch_outcome_analysis.json",
    TRAINED_CANDIDATES_ROOT / "touchline_detector_candidate_v4" / "evaluation_contract.json",
    TRAINED_CANDIDATES_ROOT / "touchline_detector_candidate_v4" / "remote_training_result.json",
    TRAINED_CANDIDATES_ROOT / "touchline_detector_candidate_v4" / "results.csv",
]

EXCLUDED_RULES = [
    "archive/**",
    "videos/**",
    "backend/venv/**",
    "frontend/node_modules/**",
    "**/__pycache__/**",
    "**/*.pyc",
    "**/*.pt",
    "**/*.cache",
    "**/yolo_export/images/**",
    "**/yolo_export/labels/**",
]


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _load_json(path: Path) -> dict[str, object]:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise ValueError(f"Expected JSON object in {path}")
    return payload


def _write_json(path: Path, payload: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def _write_text(path: Path, text: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def _relative_path(path: Path, repo_root: Path) -> Path:
    return path.relative_to(repo_root)


def _exclude_reason(relative_path: Path) -> str | None:
    rel = PurePosixPath(relative_path.as_posix())
    rel_str = rel.as_posix()
    if rel_str.startswith("archive/"):
        return "archive_outputs"
    if rel_str.startswith("videos/"):
        return "videos"
    if rel_str.startswith("backend/venv/"):
        return "venv"
    if rel_str.startswith("frontend/node_modules/"):
        return "node_modules"
    if "__pycache__" in rel.parts:
        return "python_cache"
    if rel.suffix == ".pyc":
        return "python_bytecode"
    if rel.suffix == ".pt":
        return "model_weights"
    if rel.suffix == ".cache":
        return "cache_file"
    parts = list(rel.parts)
    if "yolo_export" in parts:
        yolo_index = parts.index("yolo_export")
        trailing_parts = parts[yolo_index + 1 :]
        if trailing_parts and trailing_parts[0] in {"images", "labels"}:
            return "bulky_yolo_tree"
    return None


def _discover_python_files(repo_root: Path) -> list[Path]:
    files: list[Path] = []
    search_roots = [
        repo_root,
        repo_root / "backend",
        repo_root / "research-addon",
    ]
    seen: set[Path] = set()
    for root in search_roots:
        if not root.exists():
            continue
        if root == repo_root:
            candidates = [path for path in repo_root.glob("*.py") if path.is_file()]
        else:
            candidates = [path for path in root.rglob("*.py") if path.is_file()]
        for path in candidates:
            relative_path = _relative_path(path, repo_root)
            if _exclude_reason(relative_path) is not None:
                continue
            if relative_path in seen:
                continue
            seen.add(relative_path)
            files.append(relative_path)
    return sorted(set(files))


def _memorybank_markdown_files(repo_root: Path) -> list[Path]:
    files: list[Path] = []
    memorybank_root = repo_root / "memorybank"
    if not memorybank_root.exists():
        return files
    for path in memorybank_root.rglob("*.md"):
        if not path.is_file():
            continue
        relative_path = _relative_path(path, repo_root)
        if _exclude_reason(relative_path) is not None:
            continue
        files.append(relative_path)
    return sorted(set(files))


def _bundle_prefix_for_profile(profile: str) -> str:
    if profile == "core":
        return CORE_BUNDLE_PREFIX
    return FULL_BUNDLE_PREFIX


def _explicit_existing_paths(repo_root: Path, paths: list[Path]) -> tuple[list[Path], list[str]]:
    existing: list[Path] = []
    missing: list[str] = []
    for relative_path in paths:
        candidate = repo_root / relative_path
        if candidate.exists() and candidate.is_file():
            if _exclude_reason(relative_path) is None:
                existing.append(relative_path)
        else:
            missing.append(relative_path.as_posix())
    return sorted(set(existing)), sorted(missing)


def collect_bundle_file_plan(repo_root: Path, *, profile: str = "full") -> dict[str, object]:
    if profile == "core":
        core_code_files, missing_core_code = _explicit_existing_paths(repo_root, CORE_CODE_PATHS)
        core_memorybank_files, missing_core_memorybank = _explicit_existing_paths(repo_root, CORE_MEMORYBANK_PATHS)
        document_files, missing_documents = _explicit_existing_paths(repo_root, CORE_DOCUMENT_PATHS)
        suite_truth_files, missing_suite_truth = _explicit_existing_paths(repo_root, SUITE_TRUTH_PATHS)
        training_prep_files, missing_training_prep = _explicit_existing_paths(repo_root, CORE_TRAINING_PREP_ARTIFACT_PATHS)
        candidate_files, missing_candidates = _explicit_existing_paths(repo_root, CORE_CANDIDATE_ARTIFACT_PATHS)

        categorized_files: dict[str, list[Path]] = {
            "coreCode": core_code_files,
            "memorybankDocs": core_memorybank_files,
            "documents": document_files,
            "suiteTruth": suite_truth_files,
            "trainingPrepArtifacts": training_prep_files,
            "candidateArtifacts": candidate_files,
        }
        all_files = sorted(
            {
                relative_path
                for paths in categorized_files.values()
                for relative_path in paths
            }
        )
        return {
            "categorizedFiles": categorized_files,
            "allFiles": all_files,
            "missingRequestedFiles": {
                "coreCode": missing_core_code,
                "memorybankDocs": missing_core_memorybank,
                "documents": missing_documents,
                "suiteTruth": missing_suite_truth,
                "trainingPrepArtifacts": missing_training_prep,
                "candidateArtifacts": missing_candidates,
            },
        }

    python_files = _discover_python_files(repo_root)
    memorybank_files = _memorybank_markdown_files(repo_root)
    document_files, missing_documents = _explicit_existing_paths(repo_root, DOCUMENT_PATHS)
    suite_truth_files, missing_suite_truth = _explicit_existing_paths(repo_root, SUITE_TRUTH_PATHS)
    training_prep_files, missing_training_prep = _explicit_existing_paths(repo_root, TRAINING_PREP_ARTIFACT_PATHS)
    candidate_files, missing_candidates = _explicit_existing_paths(repo_root, CANDIDATE_ARTIFACT_PATHS)

    categorized_files: dict[str, list[Path]] = {
        "python": python_files,
        "memorybankDocs": memorybank_files,
        "documents": document_files,
        "suiteTruth": suite_truth_files,
        "trainingPrepArtifacts": training_prep_files,
        "candidateArtifacts": candidate_files,
    }

    all_files = sorted(
        {
            relative_path
            for paths in categorized_files.values()
            for relative_path in paths
        }
    )
    return {
        "categorizedFiles": categorized_files,
        "allFiles": all_files,
        "missingRequestedFiles": {
            "documents": missing_documents,
            "suiteTruth": missing_suite_truth,
            "trainingPrepArtifacts": missing_training_prep,
            "candidateArtifacts": missing_candidates,
        },
    }


def _get_nested_dict(payload: dict[str, object], key: str) -> dict[str, object]:
    nested = payload.get(key)
    return dict(nested) if isinstance(nested, dict) else {}


def _current_truth(repo_root: Path) -> dict[str, object]:
    suite_summary = _load_json(repo_root / SUITE_TRUTH_PATHS[0])
    active_lane_snapshot = _load_json(repo_root / SUITE_TRUTH_PATHS[1])
    robustness_diagnosis = _load_json(repo_root / SUITE_TRUTH_PATHS[2])

    v3_evaluation_outcome = _load_json(
        repo_root
        / TRAINED_CANDIDATES_ROOT
        / "touchline_detector_candidate_v3"
        / "evaluation_v1"
        / "batch_outcome_analysis.json"
    )
    v3_failure_outcome = _load_json(
        repo_root
        / TRAINED_CANDIDATES_ROOT
        / "touchline_detector_candidate_v3"
        / "failure_analysis_v1"
        / "batch_outcome_analysis.json"
    )
    v4_training_outcome = _load_json(
        repo_root / TRAINED_CANDIDATES_ROOT / "touchline_detector_candidate_v4" / "batch_outcome_analysis.json"
    )
    proposal_signal_fix_outcome = _load_json(
        repo_root / TRAINING_PREP_ROOT / "touchline_proposal_signal_generation_fix_v1" / "batch_outcome_analysis.json"
    )

    detector_training = _get_nested_dict(suite_summary, "detectorTrainingDiagnosis")
    proposal_signal_fix = _get_nested_dict(suite_summary, "detectorCandidateProposalSignalFixDiagnosis")
    v4_candidate_name = str(
        detector_training.get("trainingCandidateName")
        or proposal_signal_fix.get("trainingCandidateName")
        or "touchline_detector_candidate_v4"
    )

    return {
        "suiteSummary": suite_summary,
        "activeLaneSnapshot": active_lane_snapshot,
        "suiteRobustnessDiagnosis": robustness_diagnosis,
        "v3EvaluationOutcome": v3_evaluation_outcome,
        "v3FailureOutcome": v3_failure_outcome,
        "v4TrainingOutcome": v4_training_outcome,
        "proposalSignalFixOutcome": proposal_signal_fix_outcome,
        "activeCandidateName": v4_candidate_name,
        "nextLever": str(
            suite_summary.get("sourceRobustnessRecommendedNextLever")
            or active_lane_snapshot.get("sourceRobustnessRecommendedNextLever")
            or "evaluate_touchline_detector_candidate"
        ),
        "suiteVerdict": str(suite_summary.get("suiteVerdict") or "unknown"),
    }


def generate_bundle_readme(repo_root: Path, bundle_date: str, truth: dict[str, object], *, profile: str = "full") -> str:
    suite_summary = dict(truth["suiteSummary"])
    detector_training = _get_nested_dict(suite_summary, "detectorTrainingDiagnosis")
    proposal_signal_fix = _get_nested_dict(suite_summary, "detectorCandidateProposalSignalFixDiagnosis")

    active_candidate_name = str(truth["activeCandidateName"])
    next_lever = str(truth["nextLever"])
    suite_verdict = str(truth["suiteVerdict"])
    v3_eval_outcome = dict(truth["v3EvaluationOutcome"])
    v3_failure_outcome = dict(truth["v3FailureOutcome"])
    v4_training_outcome = dict(truth["v4TrainingOutcome"])
    proposal_signal_fix_outcome = dict(truth["proposalSignalFixOutcome"])

    proposal_positive_count = proposal_signal_fix.get("proposalPositiveExampleCount")
    proposal_negative_count = proposal_signal_fix.get("proposalNegativeExampleCount")
    training_batch_name = detector_training.get("trainingBatchName") or proposal_signal_fix.get("proposalSignalFixBatchName")

    start_here_files = [
        "backend/storage/benchmark_suites/frozen-viable-baseline-slice-suite/suite_summary.json",
        "memorybank/currentRoadmap.md",
        "memorybank/activeContext.md",
        "SESSION-HANDOFF.md",
        "backend/storage/trained_detector_candidates/touchline_detector_candidate_v3/evaluation_v1/batch_outcome_analysis.json",
        "backend/storage/trained_detector_candidates/touchline_detector_candidate_v3/failure_analysis_v1/batch_outcome_analysis.json",
        "backend/storage/training_prep/touchline_proposal_signal_generation_fix_v1/batch_outcome_analysis.json",
        "backend/storage/trained_detector_candidates/touchline_detector_candidate_v4/batch_outcome_analysis.json",
        "backend/storage/trained_detector_candidates/touchline_detector_candidate_v4/evaluation_contract.json",
        "backend/scripts/run_touchline_detector_candidate_evaluation.py",
    ]

    pack_title = "Fotball Analyst Parallel Research Pack"
    if profile == "core":
        pack_title = "Fotball Analyst Parallel Research Core Pack"

    lines = [
        f"# {pack_title}",
        "",
        f"Generated from the repo at `{repo_root}` on `{bundle_date}`.",
        "",
        "## What This Bundle Is For",
        "",
        (
            "This pack is a lightweight handoff for parallel AI or engineer research. It keeps the roadmap, "
            "memorybank, session handoff, key generated truth artifacts, and the code that directly drives the "
            "touchline/source-robustness lane."
            if profile == "core"
            else "This pack is a lightweight handoff for parallel AI or engineer research. It keeps all Python code, the current roadmap and memorybank, session handoff material, and the key generated truth artifacts while excluding videos, weights, caches, and bulky dataset trees."
        ),
        "",
        "## Current Canonical Truth",
        "",
        f"- Suite verdict: `{suite_verdict}`",
        "- Active roadmap lane: `Phase 3 - detector candidate evaluation`",
        f"- Next honest lever: `{next_lever}`",
        f"- Active evaluation-ready candidate: `{active_candidate_name}`",
        f"- Current training batch for the active candidate: `{training_batch_name}`",
        "",
        "## Roadmap Status By Phase",
        "",
        "- Phase 1A training-prep foundation: completed and captured in the curated truth artifacts.",
        "- Phase 1B review densification: completed enough to unlock retraining; the review/output artifacts are included here for reference.",
        "- Phase 2 targeted data-quality corrective work: completed through the saved model/data-quality and proposal-signal corrective batches.",
        f"- Phase 3 bounded detector evaluation: still active. The roadmap cannot move beyond this lane until `{active_candidate_name}` wins bounded evaluation.",
        "",
        "## Current Active Candidate",
        "",
        f"`{active_candidate_name}` matters because it is the newest evaluation-ready detector artifact produced after the proposal-signal generation fix. The current truth says training completed, weights are ready, and the evaluation contract is ready, but the product claim is still unproven until the bounded evaluation runs.",
        "",
        "## What Failed Before This",
        "",
        f"- `touchline_detector_candidate_v3` evaluation failed honestly: {v3_eval_outcome.get('englishSummary', 'no saved summary')}",
        f"- `touchline_detector_candidate_v3` failure analysis narrowed the issue to `proposal_signal_generation`: {v3_failure_outcome.get('englishSummary', 'no saved summary')}",
        f"- The new v4 proposal-signal batch succeeded at producing an evaluation-ready candidate: {proposal_signal_fix_outcome.get('englishSummary', 'no saved summary')}",
        f"- The v4 training closeout also says the batch achieved its goal while keeping the roadmap pinned on `{next_lever}`: {v4_training_outcome.get('englishDecision', 'no saved decision')}",
        "",
        "## Major Closed Or Falsified Lanes",
        "",
        "- Do not spend cycles on generic plumbing-only debugging for the v3 path; that was already resolved before the truthful v3 product loss.",
        "- Do not reopen Phase 1B review densification as the primary next move; the current blocker is no longer there.",
        "- Do not treat the one-class candidate as a drop-in full-detector replacement; the evaluation lane already reframed it as an auxiliary ball-only probe model.",
        "- Do not reopen touchline repair-profile search, touchline replacement, touchline acquisition/window retuning, or broad detector-breadth reruns as the next default move.",
        "",
        "## Concrete Problems We Are Facing Now",
        "",
        f"- The suite is still `{suite_verdict}`.",
        "- A previous honest evaluation loss showed zero useful candidate signal at the proposal/probe/accepted layers for v3.",
        "- The corrective work improved the training data shape, but we still need the bounded evaluation result for v4 before claiming product lift.",
        f"- The next unresolved question is whether `{active_candidate_name}` actually beats the standing `101 / 98 / false / 0.812` failing-source reference under the bounded evaluation contract.",
        "",
        "## Last Batch Achieved vs Did Not Achieve",
        "",
        f"- Achieved: the proposal-signal generation corrective batch produced an evaluation-ready `{active_candidate_name}`.",
        f"- Achieved: the saved batch truth reports `{proposal_positive_count}` proposal-positive examples and `{proposal_negative_count}` proposal-negative examples in the corrective export.",
        "- Did not achieve: a product win. The roadmap still cannot advance beyond Phase 3 until the bounded v4 evaluation succeeds.",
        "",
        "## Recommended Next Batch",
        "",
        "- `Touchline Detector Candidate Evaluation v4`",
        "- Use `touchline_detector_candidate_v4` as the active candidate.",
        "- Keep the same bounded evaluation contract against `101 / 98 / false / 0.812`.",
        "- End with the same English achieved/not-achieved gate.",
        "- Only advance the roadmap if v4 actually wins the bounded evaluation.",
        "",
        "## Start Here",
        "",
    ]

    lines.extend(f"- `{path}`" for path in start_here_files)
    lines.extend(
        [
            "",
            "## Notes For Parallel Researchers",
            "",
            "- The bundle is optimized for analysis and decision support, not full training reproducibility.",
            "- Model weights, videos, large YOLO export trees, caches, and heavy pod-cycle artifacts are intentionally excluded.",
            "- If you recommend a next move, anchor it to the saved truth artifacts in this pack so it can be compared cleanly with the live roadmap.",
            "",
        ]
    )
    return "\n".join(lines)


def _copy_repo_file(repo_root: Path, bundle_root: Path, relative_path: Path) -> None:
    source_path = repo_root / relative_path
    target_path = bundle_root / relative_path
    target_path.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(source_path, target_path)


@contextmanager
def _archive_directory(path: Path):
    """Pin every archive ancestor, rejecting symlinks and namespace changes."""
    if ".." in path.parts:
        raise ValueError("archive_root cannot contain parent traversal")
    flags = os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW
    with ExitStack() as opened:
        descriptor = os.open(path.anchor, flags)
        opened.callback(os.close, descriptor)
        entries = []
        for part in path.parts[1:]:
            parent = descriptor
            try:
                descriptor = os.open(part, flags, dir_fd=parent)
            except FileNotFoundError:
                os.mkdir(part, dir_fd=parent)
                descriptor = os.open(part, flags, dir_fd=parent)
            opened.callback(os.close, descriptor)
            entries.append((parent, part, os.fstat(descriptor)))

        def validate() -> None:
            for parent, part, expected in entries:
                actual = os.stat(part, dir_fd=parent, follow_symlinks=False)
                if not os.path.samestat(actual, expected):
                    raise ValueError("archive namespace changed")

        validate()
        yield descriptor, validate


def _pinned_directory_path(descriptor: int) -> Path:
    # ponytail: Linux proc-fd bridge; use a dir_fd copier if other platforms need support.
    path = Path(f"/proc/self/fd/{descriptor}")
    if not os.path.samestat(path.stat(), os.fstat(descriptor)):
        raise ValueError("proc-fd path is not bound to the opened directory")
    return path


def _zip_identity(name: str, archive_fd: int) -> tuple[int, int] | None:
    try:
        entry = os.stat(name, dir_fd=archive_fd, follow_symlinks=False)
    except FileNotFoundError:
        return None
    if not stat.S_ISREG(entry.st_mode):
        raise ValueError("ZIP destination must be a regular file")
    return entry.st_dev, entry.st_ino


def _zip_bundle_root(
    bundle_root: Path, zip_path: Path, *, archive_fd: int, validate: Callable[[], None],
) -> None:
    temporary = f".{zip_path.name}.{secrets.token_hex(16)}.tmp"
    descriptor = os.open(
        temporary, os.O_RDWR | os.O_CREAT | os.O_EXCL | os.O_NOFOLLOW, 0o600, dir_fd=archive_fd,
    )
    try:
        with os.fdopen(descriptor, "w+b", closefd=False) as handle:
            with zipfile.ZipFile(handle, "w", compression=zipfile.ZIP_DEFLATED) as archive:
                for path in sorted(bundle_root.rglob("*")):
                    if path.is_dir():
                        continue
                    archive.write(path, arcname=f"{zip_path.stem}/{path.relative_to(bundle_root).as_posix()}")
            handle.flush()
            handle.seek(0)
            with zipfile.ZipFile(handle) as archive:
                if archive.testzip() is not None:
                    raise zipfile.BadZipFile("candidate ZIP failed CRC validation")
            os.fsync(handle.fileno())
        validate()
        candidate = os.fstat(descriptor)
        if _zip_identity(temporary, archive_fd) != (candidate.st_dev, candidate.st_ino):
            raise ValueError("temporary ZIP destination changed")
        os.replace(temporary, zip_path.name, src_dir_fd=archive_fd, dst_dir_fd=archive_fd)
        temporary = None
        os.fsync(archive_fd)
    finally:
        try:
            if temporary is not None:
                os.unlink(temporary, dir_fd=archive_fd)
        finally:
            os.close(descriptor)


def build_parallel_research_bundle(
    *,
    repo_root: Path = REPO_ROOT,
    archive_root: Path | None = None,
    bundle_date: str | None = None,
    profile: str = "full",
) -> dict[str, object]:
    bundle_date = date.fromisoformat(bundle_date).isoformat() if bundle_date else date.today().isoformat()
    repo_root = repo_root.resolve()
    archive_root = archive_root.absolute() if archive_root is not None else (repo_root / "archive")
    bundle_prefix = _bundle_prefix_for_profile(profile)
    bundle_name = f"{bundle_prefix}-{bundle_date}"
    bundle_root = archive_root / bundle_name
    zip_path = archive_root / f"{bundle_name}.zip"

    file_plan = collect_bundle_file_plan(repo_root, profile=profile)
    truth = _current_truth(repo_root)

    readme_text = generate_bundle_readme(repo_root, bundle_date, truth, profile=profile)

    categorized_files = dict(file_plan["categorizedFiles"])
    manifest = {
        "bundleName": bundle_name,
        "profile": profile,
        "bundleRoot": str(bundle_root),
        "zipPath": str(zip_path),
        "bundleDate": bundle_date,
        "generatedAtUtc": _utc_now_iso(),
        "includedFileCount": len(file_plan["allFiles"]),
        "includedRepoFiles": [path.as_posix() for path in file_plan["allFiles"]],
        "includedFileCountsByCategory": {
            category: len(paths)
            for category, paths in categorized_files.items()
        },
        "includedRepoFilesByCategory": {
            category: [path.as_posix() for path in paths]
            for category, paths in categorized_files.items()
        },
        "missingRequestedFiles": file_plan["missingRequestedFiles"],
        "excludedRules": EXCLUDED_RULES,
        "currentTruth": {
            "suiteVerdict": truth["suiteVerdict"],
            "nextLever": truth["nextLever"],
            "activeCandidateName": truth["activeCandidateName"],
        },
    }
    with _archive_directory(archive_root) as (archive_fd, validate_archive), ExitStack() as opened:
        _pinned_directory_path(archive_fd)  # Fail before reset when Linux proc-fd is unavailable.
        previous_zip = _zip_identity(zip_path.name, archive_fd)
        try:
            prior_bundle = os.stat(bundle_name, dir_fd=archive_fd, follow_symlinks=False)
        except FileNotFoundError:
            prior_bundle = None
        if prior_bundle is not None:
            if not stat.S_ISDIR(prior_bundle.st_mode):
                raise ValueError("bundle destination must be a directory, not a symlink")
            prior_fd = os.open(bundle_name, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=archive_fd)
            opened.callback(os.close, prior_fd)
            if not os.path.samestat(prior_bundle, os.fstat(prior_fd)):
                raise ValueError("bundle namespace changed before reset")
            for _, directories, files, parent_fd in os.fwalk(".", topdown=False, follow_symlinks=False, dir_fd=prior_fd):
                for name in files + directories:
                    entry = os.stat(name, dir_fd=parent_fd, follow_symlinks=False)
                    remove = os.rmdir if stat.S_ISDIR(entry.st_mode) else os.unlink
                    remove(name, dir_fd=parent_fd)
            validate_archive()
            current = os.stat(bundle_name, dir_fd=archive_fd, follow_symlinks=False)
            if not os.path.samestat(prior_bundle, current):
                raise ValueError("bundle namespace changed during reset")
            os.rmdir(bundle_name, dir_fd=archive_fd)
        validate_archive()
        os.mkdir(bundle_name, dir_fd=archive_fd)
        bundle_fd = os.open(bundle_name, os.O_RDONLY | os.O_DIRECTORY | os.O_NOFOLLOW, dir_fd=archive_fd)
        opened.callback(os.close, bundle_fd)
        pinned_bundle = _pinned_directory_path(bundle_fd)

        def validate() -> None:
            validate_archive()
            current = os.stat(bundle_name, dir_fd=archive_fd, follow_symlinks=False)
            if not os.path.samestat(current, os.fstat(bundle_fd)):
                raise ValueError("bundle namespace changed")
            if _zip_identity(zip_path.name, archive_fd) != previous_zip:
                raise ValueError("ZIP destination changed")

        validate()
        for relative_path in file_plan["allFiles"]:
            _copy_repo_file(repo_root, pinned_bundle, relative_path)
        _write_text(pinned_bundle / "README.md", readme_text)
        _write_json(pinned_bundle / "bundle_manifest.json", manifest)
        validate()
        _zip_bundle_root(pinned_bundle, zip_path, archive_fd=archive_fd, validate=validate)

    return {
        "bundleRoot": str(bundle_root),
        "zipPath": str(zip_path),
        "bundleName": bundle_name,
        "includedFileCount": len(file_plan["allFiles"]),
        "manifestPath": str(bundle_root / "bundle_manifest.json"),
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Build a curated parallel-research bundle.")
    parser.add_argument("--repo-root", default=str(REPO_ROOT))
    parser.add_argument("--archive-root", default=None)
    parser.add_argument("--bundle-date", default=None)
    parser.add_argument("--profile", choices=["full", "core"], default="full")
    args = parser.parse_args()

    result = build_parallel_research_bundle(
        repo_root=Path(args.repo_root),
        archive_root=Path(args.archive_root) if args.archive_root else None,
        bundle_date=args.bundle_date,
        profile=args.profile,
    )
    print(json.dumps(result, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
