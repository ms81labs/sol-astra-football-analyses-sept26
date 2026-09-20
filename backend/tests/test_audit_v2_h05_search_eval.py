import json

from fastapi import FastAPI
from fastapi.testclient import TestClient

from backend.app.workbench.assistance import execute_typed_query, parse_typed_query
from backend.app.workbench.evaluation import current_repository_evaluation_gate, score_hota_idf1
from backend.app.workbench.leftover_routes import create_leftover_post_router
from backend.app.workbench.receipts import promotion_receipt


def test_typed_search_excludes_unknowns_and_checks_successor_fields() -> None:
    query = parse_typed_query("our second-half turnovers followed by opponent shots")
    events = [
        {"id": "exact", "type": "turnover", "team": "my_team", "period": 2, "timestamp": 1.0},
        {"id": "wrong-team-shot", "type": "shot", "team": "my_team", "period": 2, "timestamp": 2.0},
        {"id": "opponent-shot", "type": "shot", "team": "enemy", "period": 2, "timestamp": 3.0},
        {"id": "unknown-team", "type": "turnover", "team": None, "period": 2, "timestamp": 4.0},
        {"id": "unknown-period", "type": "turnover", "team": "my_team", "period": 0, "timestamp": 5.0},
        {"id": "wrong-half-shot", "type": "shot", "team": "enemy", "period": 1, "timestamp": 6.0},
    ]

    hits = execute_typed_query(events, query, match_id="m1")

    assert [hit.eventId for hit in hits] == ["exact"]
    assert query.interpreted["successor"] == {"kind": "shot", "team": "opponent", "period": 2, "withinSeconds": None}


def test_typed_search_reports_unsupported_terms_and_can_include_unknowns() -> None:
    query = parse_typed_query("show our turnovers with xg", include_unknown=True)
    events = [{"id": "unknown", "type": "turnover", "team": None, "period": 0, "timestamp": 1.0}]

    assert query.unsupportedTerms == ["with", "xg"]
    assert query.interpreted["includeUnknown"] is True
    assert [hit.eventId for hit in execute_typed_query(events, query, match_id="m1")] == ["unknown"]


def test_strict_typed_search_route_rejects_unsupported_terms() -> None:
    class StorageStub:
        def get_match(self, match_id):
            return {"id": match_id}

        def query_match_events(self, match_id, text, *, include_unknown=False):
            query = parse_typed_query(text, include_unknown=include_unknown)
            return {
                "query": query.model_dump(mode="json"),
                "interpreted": query.interpreted,
                "unsupportedTerms": query.unsupportedTerms,
                "results": [],
            }

    app = FastAPI()
    app.include_router(create_leftover_post_router(StorageStub()), prefix="/api")  # type: ignore[arg-type]

    response = TestClient(app).post(
        "/api/search",
        json={"matchId": "m1", "query": "our turnovers with xg", "strict": True},
    )

    assert response.status_code == 422
    assert response.json()["detail"]["unsupportedTerms"] == ["with", "xg"]


def test_evaluation_states_require_execution_and_numeric_provenance(tmp_path) -> None:
    ready = score_hota_idf1(
        label_space="image_space",
        hand_edited_summary=False,
        native_predictions_present=True,
    )
    assert ready["status"] == "prerequisites_ok"
    assert ready["scored"] is False
    assert ready["hota"] is None

    executed = score_hota_idf1(
        label_space="image_space",
        hand_edited_summary=False,
        native_predictions_present=True,
        scorer_executed=True,
    )
    assert executed["status"] == "executed"
    assert executed["scored"] is False

    scored = score_hota_idf1(
        label_space="image_space",
        hand_edited_summary=False,
        native_predictions_present=True,
        scorer_executed=True,
        hota=0.61,
        units="fraction",
        idf1=0.72,
        prediction_digest="a" * 64,
        label_digest="b" * 64,
        scorer_version="trackeval@12c8791",
        source_identity="match-1",
    )
    assert scored["status"] == "scored"
    assert scored["scored"] is True

    missing = current_repository_evaluation_gate(manifest_path=tmp_path / "missing.json")
    assert missing.status == "unknown"
    assert missing.completeTasks is None
    assert missing.reasonCodes == ["EVALUATION_MANIFEST_MISSING"]

    manifest = tmp_path / "manifest.json"
    manifest.write_text(
        json.dumps(
            {
                "schemaVersion": 1,
                "completeTasks": 18,
                "completeMinutes": 30.0,
                "lockedLabelsPresent": True,
                "nativePredictionsPresent": True,
                "teamDeclarationsPresent": True,
                "scorerReplayable": True,
                "artifacts": [{"kind": "labels", "sha256": "b" * 64}, {"kind": "predictions", "sha256": "a" * 64}],
                "scorerVersion": "trackeval@12c8791",
                "sourceIdentity": "match-1",
                "results": {"hota": 0.61, "idf1": 0.72},
            }
        )
    )
    assert current_repository_evaluation_gate(manifest_path=manifest).status == "unknown"
    assert not current_repository_evaluation_gate(manifest_path=manifest).accepted


def test_placeholder_promotion_measurements_are_explicitly_not_recorded() -> None:
    receipt = promotion_receipt(
        source_sha256="a" * 64,
        weights="weights.pt",
        configuration="baseline",
        hardware="unknown",
        native_builds=[],
        selected_backend="cpu",
        frame_count=1,
        call_count=1,
        cold_timing_ms=None,
        warm_timing_ms=None,
        peak_memory_bytes=None,
        transferred_bytes=None,
        output_quality="unmeasured",
        accepted_coverage=0.0,
        failure_cases=[],
        allocated_spend=0.0,
        fallback_event=None,
    )

    assert receipt["coldTimingMs"] is None
    assert receipt["notRecorded"] == ["coldTimingMs", "warmTimingMs", "peakMemoryBytes", "transferredBytes"]
