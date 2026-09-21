from __future__ import annotations

from backend.scripts.football_external_real_eval_chain_common import utc_now_iso as _utc_now_iso

import argparse
import asyncio
import json
from pathlib import Path
from typing import Any

import httpx

REPO_ROOT = Path(__file__).resolve().parents[2]

from backend.scripts.football_external_real_eval_chain_common import write_json as _write_json  # noqa: E402
from backend.app.main import create_app  # noqa: E402
from backend.app.match_bundle import build_match_bundle  # noqa: E402
from backend.app.run_benchmarks import DEFAULT_STORAGE_ROOT  # noqa: E402
from backend.app.storage import Storage  # noqa: E402

DEFAULT_SUITE_NAME = "frozen-viable-baseline-slice-suite"
DEFAULT_OUTPUT_DIR_NAME = "product_video_to_analysis_smoke_v1"
TRACKING_FIXTURE = REPO_ROOT / "backend" / "tests" / "fixtures" / "sample_tracking.json"
NEXT_EXTERNAL_SMOKE = "football_external_safe_source_adapter_smoke_test"
NEXT_PRODUCT_REPAIR = "product_video_to_analysis_smoke_repair"

BLOCKER_API_UPLOAD = "product_smoke_api_upload_export_failure"


def _output_root(storage_root: Path) -> Path:
    return (
        Path(storage_root)
        / "benchmark_suites"
        / DEFAULT_SUITE_NAME
        / DEFAULT_OUTPUT_DIR_NAME
    )


def _attempt_plan() -> list[dict[str, Any]]:
    return [
        {
            "attemptNumber": 1,
            "attemptApproachFamily": "api_upload_export_smoke",
            "successCriteria": [
                "normal API upload/job path completes",
                "frames, analytics, events, CSV exports, report HTML, and match bundle are readable",
            ],
            "failureAdaptation": "If API exports fail, repair only product route/export plumbing.",
        },
        {
            "attemptNumber": 2,
            "attemptApproachFamily": "video_bundle_contract_repair",
            "successCriteria": [
                "existing ready video-backed matches export match_bundle_v1 with runtime provenance when available",
                "runtime registry binding remains separate and already validated",
            ],
            "failureAdaptation": "If no video bundle exists, carry a secondary concern and keep product API smoke result.",
        },
        {
            "attemptNumber": 3,
            "attemptApproachFamily": "product_smoke_blocker_summary",
            "successCriteria": [
                "write one blocker family",
                "do not train, promote, or mutate runtime defaults",
            ],
            "failureAdaptation": "Route to product smoke repair or external adapter smoke based on generated truth.",
        },
    ]


async def _api_upload_job_smoke(storage_root: Path) -> dict[str, Any]:
    app = create_app(storage_root=storage_root, run_jobs_inline=True)
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://127.0.0.1") as client:
        response = await client.post(
            "/api/matches",
            data={
                "name": "Product Smoke Tracking Fixture",
                "inputMode": "tracking_json",
                "config": json.dumps(
                    {
                        "attackDirection": "right_to_left",
                        "manualHomographyPoints": [
                            {"x": 0.0, "y": 0.0},
                            {"x": 100.0, "y": 0.0},
                            {"x": 100.0, "y": 100.0},
                            {"x": 0.0, "y": 100.0},
                        ],
                    }
                ),
            },
            files={"file": ("sample_tracking.json", TRACKING_FIXTURE.read_bytes(), "application/json")},
        )
        upload_status = response.status_code
        match_id = response.json().get("matchId") if response.status_code == 202 else None
        job_id = response.json().get("jobId") if response.status_code == 202 else None
        urls = {}
        statuses: dict[str, int] = {"upload": upload_status}
        bundle: dict[str, Any] | None = None
        if match_id:
            for key, url in {
                "job": f"/api/jobs/{job_id}",
                "frames": f"/api/matches/{match_id}/frames",
                "analytics": f"/api/matches/{match_id}/analytics",
                "events": f"/api/matches/{match_id}/events",
                "framesCsv": f"/api/matches/{match_id}/export/frames.csv",
                "eventsCsv": f"/api/matches/{match_id}/export/events.csv",
                "reportHtml": f"/api/matches/{match_id}/report/html",
                "matchJson": f"/api/matches/{match_id}/export/match.json",
            }.items():
                check = await client.get(url)
                urls[key] = url
                statuses[key] = check.status_code
                if key == "matchJson" and check.status_code == 200:
                    bundle = check.json()
    checks = {
        "uploadAccepted": statuses.get("upload") == 202,
        "jobCompleted": statuses.get("job") == 200,
        "framesReady": statuses.get("frames") == 200,
        "analyticsReady": statuses.get("analytics") == 200,
        "eventsReady": statuses.get("events") == 200,
        "framesCsvReady": statuses.get("framesCsv") == 200,
        "eventsCsvReady": statuses.get("eventsCsv") == 200,
        "reportHtmlReady": statuses.get("reportHtml") == 200,
        "matchJsonReady": statuses.get("matchJson") == 200,
        "matchBundleSchemaValid": bool(isinstance(bundle, dict) and bundle.get("schemaVersion") == "match_bundle_v1"),
    }
    return {
        "checks": checks,
        "apiUploadJobSmokePassed": all(checks.values()),
        "matchId": match_id,
        "jobId": job_id,
        "statuses": statuses,
        "urls": urls,
        "bundleFrameCount": len(bundle.get("frames", [])) if isinstance(bundle, dict) else 0,
        "bundleEventCount": len(bundle.get("events", [])) if isinstance(bundle, dict) else 0,
    }


def _existing_video_bundle_smoke(storage_root: Path) -> dict[str, Any]:
    storage = Storage(storage_root)
    selected_match_id: str | None = None
    bundle: dict[str, Any] | None = None
    for match in storage.list_matches():
        if match.inputMode != "video" or match.status != "ready":
            continue
        try:
            candidate = build_match_bundle(storage, match.id)
        except (FileNotFoundError, KeyError, ValueError, TypeError):
            continue
        selected_match_id = match.id
        bundle = candidate
        break
    checks = {
        "readyVideoMatchFound": selected_match_id is not None,
        "bundleSchemaValid": bool(isinstance(bundle, dict) and bundle.get("schemaVersion") == "match_bundle_v1"),
        "bundleHasFrames": bool(isinstance(bundle, dict) and bundle.get("frames")),
        "bundleHasAnalytics": bool(isinstance(bundle, dict) and isinstance(bundle.get("analytics"), dict)),
        "bundleHasEvents": bool(isinstance(bundle, dict) and isinstance(bundle.get("events"), list)),
    }
    return {
        "checks": checks,
        "existingVideoBundleSmokePassed": all(checks.values()),
        "existingVideoBundleMatchId": selected_match_id,
        "bundle": bundle,
    }


def _decision_matrix(api_audit: dict[str, Any]) -> dict[str, Any]:
    if not api_audit["apiUploadJobSmokePassed"]:
        return {
            "goalAchieved": False,
            "roadmapAdvanceAllowed": True,
            "primaryBlocker": BLOCKER_API_UPLOAD,
            "nextRecommendedNextLever": NEXT_PRODUCT_REPAIR,
            "englishDecision": "Product API upload/export smoke failed. Repair product route/export plumbing before external smoke.",
        }
    return {
        "goalAchieved": True,
        "roadmapAdvanceAllowed": True,
        "primaryBlocker": None,
        "nextRecommendedNextLever": NEXT_EXTERNAL_SMOKE,
        "englishDecision": "Product API upload/export smoke passed. Advance to safe-source external adapter smoke.",
    }


def _write_markdown(path: Path, payload: dict[str, Any]) -> None:
    lines = [
        "# Product Video To Analysis Smoke",
        "",
        f"- goalAchieved: `{payload['goalAchieved']}`",
        f"- primaryBlocker: `{payload['primaryBlocker']}`",
        f"- apiUploadJobSmokePassed: `{payload['apiUploadJobSmokePassed']}`",
        f"- existingVideoBundleSmokePassed: `{payload['existingVideoBundleSmokePassed']}`",
        f"- existingVideoBundleMatchId: `{payload['existingVideoBundleMatchId']}`",
        f"- secondaryConcern: `{payload['secondaryConcern']}`",
        f"- trainingExecuted: `{payload['trainingExecuted']}`",
        f"- runtimeDefaultMutationExecuted: `{payload['runtimeDefaultMutationExecuted']}`",
        f"- nextRecommendedNextLever: `{payload['nextRecommendedNextLever']}`",
        "",
        payload["englishDecision"],
        "",
    ]
    path.write_text("\n".join(lines), encoding="utf-8")


def run_product_video_to_analysis_smoke(*, storage_root: Path = DEFAULT_STORAGE_ROOT) -> dict[str, Any]:
    storage_root = Path(storage_root)
    output_root = _output_root(storage_root)
    output_root.mkdir(parents=True, exist_ok=True)
    api_audit = asyncio.run(_api_upload_job_smoke(storage_root))
    video_audit = _existing_video_bundle_smoke(storage_root)
    decision = _decision_matrix(api_audit)
    secondary_concern = None if video_audit["existingVideoBundleSmokePassed"] else "product_video_smoke_no_existing_video_bundle"
    summary = {
        "batchName": "product_video_to_analysis_smoke",
        "generatedAt": _utc_now_iso(),
        "attemptNumber": 1,
        "attemptBudget": 3,
        "attemptApproachFamily": "api_upload_export_smoke",
        "attemptPlan": _attempt_plan(),
        "apiUploadJobSmokePassed": api_audit["apiUploadJobSmokePassed"],
        "apiUploadMatchId": api_audit.get("matchId"),
        "existingVideoBundleSmokePassed": video_audit["existingVideoBundleSmokePassed"],
        "existingVideoBundleMatchId": video_audit.get("existingVideoBundleMatchId"),
        "secondaryConcern": secondary_concern,
        "trainingExecuted": False,
        "promotionMutationExecuted": False,
        "runtimeDefaultMutationExecuted": False,
        "candidateEvaluationExecuted": False,
        **decision,
    }
    _write_json(output_root / "api_upload_job_smoke_audit.json", api_audit)
    video_bundle = video_audit.pop("bundle", None)
    _write_json(output_root / "existing_video_bundle_smoke_audit.json", video_audit)
    if isinstance(video_bundle, dict):
        _write_json(output_root / "sample_exported_match_bundle.json", video_bundle)
    _write_json(output_root / "decision_matrix.json", decision)
    _write_json(output_root / "product_video_to_analysis_smoke_summary.json", summary)
    _write_json(output_root / "batch_outcome_analysis.json", summary)
    _write_markdown(output_root / "batch_outcome_analysis.md", summary)
    return summary


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--storage-root", type=Path, default=DEFAULT_STORAGE_ROOT)
    args = parser.parse_args()
    payload = run_product_video_to_analysis_smoke(storage_root=args.storage_root)
    print(json.dumps(payload, indent=2, sort_keys=True))


if __name__ == "__main__":
    main()
