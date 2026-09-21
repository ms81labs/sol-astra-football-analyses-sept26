from __future__ import annotations

import asyncio
from html import escape
from pathlib import Path
from typing import Any

import httpx

REPO_ROOT = Path(__file__).resolve().parents[2]

from backend.app.main import create_app  # noqa: E402
from backend.scripts.football_external_real_eval_chain_common import (  # noqa: E402
    DEFAULT_CANDIDATE_NAME,
    DEFAULT_STORAGE_ROOT,
    candidate_root,
    load_json,
    main_for,
    reset_output,
    standard_false_flags,
    utc_now_iso,
    write_json,
    write_outcome,
)

DEFAULT_READOUT_PACK_DIR_NAME = "video_to_analysis_release_readout_pack_v1"
DEFAULT_OUTPUT_DIR_NAME = "video_to_analysis_release_readout_route_binding_v1"

BLOCKER_PACK_MISSING = "video_to_analysis_release_readout_pack_missing"
BLOCKER_ROUTE_SMOKE_FAILED = "video_to_analysis_release_readout_route_smoke_failed"
NEXT_PACK = "video_to_analysis_release_readout_pack"
NEXT_REPAIR = "video_to_analysis_release_readout_route_repair"
NEXT_STRATEGIC_SELECTION = "video_to_analysis_next_strategic_lane_selection"


def _attempt_plan() -> dict[str, Any]:
    return {
        "attemptBudget": 3,
        "attempts": [
            {
                "attemptNumber": 1,
                "attemptApproachFamily": "video_to_analysis_release_readout_route_binding",
                "successCriteria": [
                    "serve release/readout API and HTML routes from saved artifacts",
                    "preserve all guardrails",
                    "route next to strategic lane selection",
                ],
                "failureAdaptation": "If readout pack truth is missing, route back to the readout pack.",
            },
            {
                "attemptNumber": 2,
                "attemptApproachFamily": "release_readout_route_repair",
                "successCriteria": ["repair only saved view model, route contract, or HTML rendering"],
                "failureAdaptation": "If route smoke still fails, write blocker truth.",
            },
            {
                "attemptNumber": 3,
                "attemptApproachFamily": "release_readout_route_blocker_summary",
                "successCriteria": ["write blocker truth", "select exactly one next family"],
                "failureAdaptation": "Route to pack, route repair, or strategic lane selection.",
            },
        ],
    }


def _pack_ready(
    summary: dict[str, Any] | None,
    manifest: dict[str, Any] | None,
    matrix: dict[str, Any] | None,
    guardrails: dict[str, Any] | None,
) -> bool:
    return bool(
        isinstance(summary, dict)
        and summary.get("goalAchieved") is True
        and summary.get("primaryBlocker") is None
        and summary.get("releaseReadoutPackReady") is True
        and summary.get("growthLaneCloseoutSnapshot") == "video_to_analysis_next_sample_selection_snapshot_v38"
        and summary.get("externalBenchmarkProductBindingReady") is True
        and summary.get("runtimeOperationallyComplete") is True
        and summary.get("trainingExecuted") is False
        and summary.get("promotionMutationExecuted") is False
        and summary.get("runtimeDefaultMutationExecuted") is False
        and summary.get("videoDownloadExecuted") is False
        and summary.get("dataDownloadExecuted") is False
        and summary.get("normalMatchStorageMutationExecuted") is False
        and isinstance(manifest, dict)
        and manifest.get("schemaVersion") == "video_to_analysis_release_readout_manifest_v1"
        and manifest.get("latestSnapshot") == "video_to_analysis_next_sample_selection_snapshot_v38"
        and isinstance(matrix, dict)
        and matrix.get("schemaVersion") == "video_to_analysis_next_strategic_lane_matrix_v1"
        and isinstance(matrix.get("candidateStrategicLanes"), list)
        and isinstance(guardrails, dict)
        and guardrails.get("allMutationGuardrailsPreserved") is True
    )


def _view_model(manifest: dict[str, Any], matrix: dict[str, Any]) -> dict[str, Any]:
    return {
        "schemaVersion": "video_to_analysis_release_readout_view_model_v1",
        "generatedAt": utc_now_iso(),
        "title": "Video-to-analysis release readout",
        "latestSnapshot": manifest.get("latestSnapshot"),
        "activeQueueCandidateIds": manifest.get("activeQueueCandidateIds", []),
        "runtimeOperationallyComplete": manifest.get("runtimeOperationallyComplete") is True,
        "externalBenchmarkProductBindingReady": manifest.get("externalBenchmarkProductBindingReady") is True,
        "recommendedLane": matrix.get("recommendedLane"),
        "candidateStrategicLanes": matrix.get("candidateStrategicLanes", []),
        "guardrails": {
            "trainingExecuted": False,
            "promotionMutationExecuted": False,
            "runtimeDefaultMutationExecuted": False,
            "videoDownloadExecuted": False,
            "dataDownloadExecuted": False,
            "normalMatchStorageMutationExecuted": False,
        },
        "nextRecommendedNextLever": NEXT_STRATEGIC_SELECTION,
    }


def _render_html(view_model: dict[str, Any], brief: str) -> str:
    queue_items = "\n".join(
        f"<li><code>{escape(str(sample_id))}</code></li>"
        for sample_id in view_model.get("activeQueueCandidateIds", [])
    )
    lanes = "\n".join(
        f"<li><code>{escape(str(row.get('id')))}</code> {escape(str(row.get('label')))}</li>"
        for row in view_model.get("candidateStrategicLanes", [])
        if isinstance(row, dict)
    )
    return "\n".join(
        [
            "<!doctype html>",
            "<html lang=\"en\">",
            "<head><meta charset=\"utf-8\"><title>Video-to-analysis release readout</title></head>",
            "<body>",
            "<h1>Video-to-analysis release readout</h1>",
            f"<p>Latest snapshot: <code>{escape(str(view_model.get('latestSnapshot')))}</code></p>",
            "<h2>Active v38 queue</h2>",
            f"<ul>{queue_items}</ul>",
            "<h2>Candidate next strategic lanes</h2>",
            f"<ol>{lanes}</ol>",
            "<h2>Operator brief</h2>",
            f"<pre>{escape(brief)}</pre>",
            "</body>",
            "</html>",
            "",
        ]
    )


async def _route_smoke_async(storage_root: Path) -> dict[str, Any]:
    app = create_app(storage_root=storage_root)
    async with httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://127.0.0.1") as client:
        api_response = await client.get("/api/video-to-analysis/release-readout")
        html_response = await client.get("/video-to-analysis/release-readout")
    api_payload: dict[str, Any] = {}
    if api_response.headers.get("content-type", "").startswith("application/json"):
        api_payload = api_response.json()
    return {
        "apiRoutePath": "/api/video-to-analysis/release-readout",
        "htmlRoutePath": "/video-to-analysis/release-readout",
        "apiRouteStatusCode": api_response.status_code,
        "htmlRouteStatusCode": html_response.status_code,
        "apiSchemaVersion": api_payload.get("schemaVersion"),
        "htmlContainsTitle": "Video-to-analysis release readout" in html_response.text,
        "htmlMentionsV38": "v38" in html_response.text,
    }


def _route_smoke(storage_root: Path) -> dict[str, Any]:
    return asyncio.run(_route_smoke_async(storage_root))


def run_video_to_analysis_release_readout_route_binding(
    *,
    storage_root: Path = DEFAULT_STORAGE_ROOT,
    candidate_name: str = DEFAULT_CANDIDATE_NAME,
    output_dir_name: str = DEFAULT_OUTPUT_DIR_NAME,
) -> dict[str, Any]:
    root = candidate_root(Path(storage_root), candidate_name)
    pack_root = root / DEFAULT_READOUT_PACK_DIR_NAME
    output_root = reset_output(root, output_dir_name)

    pack_summary = load_json(pack_root / "release_readout_pack_summary.json")
    manifest = load_json(pack_root / "release_readout_manifest.json")
    matrix = load_json(pack_root / "next_strategic_lane_matrix.json")
    guardrails = load_json(pack_root / "guardrail_audit.json")
    brief_path = pack_root / "operator_release_brief.md"
    brief = brief_path.read_text(encoding="utf-8") if brief_path.exists() else ""
    pack_ready = _pack_ready(pack_summary, manifest, matrix, guardrails)

    if pack_ready and isinstance(manifest, dict) and isinstance(matrix, dict):
        view_model = _view_model(manifest, matrix)
        bound_contract = {
            "schemaVersion": "video_to_analysis_release_readout_bound_route_contract_v1",
            "generatedAt": utc_now_iso(),
            "apiRoutePath": "/api/video-to-analysis/release-readout",
            "htmlRoutePath": "/video-to-analysis/release-readout",
            "releaseReadoutRouteReady": True,
            "allowsTraining": False,
            "allowsPromotion": False,
            "allowsRuntimeDefaultMutation": False,
            "allowsDownloads": False,
            "allowsNormalMatchStorageMutation": False,
        }
        write_json(output_root / "release_readout_view_model.json", view_model)
        write_json(output_root / "release_readout_bound_route_contract.json", bound_contract)
        (output_root / "release_readout_render_smoke.html").write_text(
            _render_html(view_model, brief),
            encoding="utf-8",
        )
        smoke = _route_smoke(Path(storage_root))
    else:
        smoke = {"apiRouteStatusCode": 0, "htmlRouteStatusCode": 0}

    route_ready = bool(
        pack_ready
        and smoke.get("apiRouteStatusCode") == 200
        and smoke.get("htmlRouteStatusCode") == 200
        and smoke.get("apiSchemaVersion") == "video_to_analysis_release_readout_view_model_v1"
        and smoke.get("htmlContainsTitle") is True
        and smoke.get("htmlMentionsV38") is True
    )

    if not pack_ready:
        primary_blocker = BLOCKER_PACK_MISSING
        next_lever = NEXT_PACK
        english = "Release/readout pack is missing or unsafe; build the pack before route binding."
    elif not route_ready:
        primary_blocker = BLOCKER_ROUTE_SMOKE_FAILED
        next_lever = NEXT_REPAIR
        english = "Release/readout route smoke failed."
    else:
        primary_blocker = None
        next_lever = NEXT_STRATEGIC_SELECTION
        english = "Release/readout API and HTML routes are bound and smoked. Choose the next strategic lane deliberately."

    summary = {
        "batchName": "video_to_analysis_release_readout_route_binding",
        "generatedAt": utc_now_iso(),
        "attemptNumber": 1,
        "attemptBudget": 3,
        "attemptPlanFamilies": [row["attemptApproachFamily"] for row in _attempt_plan()["attempts"]],
        "goalAchieved": route_ready,
        "roadmapAdvanceAllowed": route_ready,
        "primaryBlocker": primary_blocker,
        "releaseReadoutRouteReady": route_ready,
        "apiRoutePath": "/api/video-to-analysis/release-readout",
        "htmlRoutePath": "/video-to-analysis/release-readout",
        "apiRouteStatusCode": smoke.get("apiRouteStatusCode"),
        "htmlRouteStatusCode": smoke.get("htmlRouteStatusCode"),
        **standard_false_flags(),
        "nextRecommendedNextLever": next_lever,
        "englishDecision": english,
    }
    decision_matrix = {
        "schemaVersion": "video_to_analysis_release_readout_route_decision_matrix_v1",
        "generatedAt": utc_now_iso(),
        "decisions": [
            {
                "condition": "release_readout_pack_missing",
                "selected": primary_blocker == BLOCKER_PACK_MISSING,
                "primaryBlocker": BLOCKER_PACK_MISSING,
                "nextRecommendedNextLever": NEXT_PACK,
            },
            {
                "condition": "release_readout_route_smoke_failed",
                "selected": primary_blocker == BLOCKER_ROUTE_SMOKE_FAILED,
                "primaryBlocker": BLOCKER_ROUTE_SMOKE_FAILED,
                "nextRecommendedNextLever": NEXT_REPAIR,
            },
            {
                "condition": "release_readout_route_ready",
                "selected": route_ready,
                "primaryBlocker": None,
                "nextRecommendedNextLever": NEXT_STRATEGIC_SELECTION,
            },
        ],
    }
    return write_outcome(
        output_root=output_root,
        summary_filename="release_readout_route_binding_summary.json",
        summary=summary,
        artifacts={
            "route_smoke_audit.json": smoke,
            "decision_matrix.json": decision_matrix,
            "failsafe_attempt_plan.json": _attempt_plan(),
        },
        markdown_title="Video To Analysis Release Readout Route Binding",
    )


def main() -> None:
    main_for("Bind video-to-analysis release/readout routes.", run_video_to_analysis_release_readout_route_binding)


if __name__ == "__main__":
    main()
