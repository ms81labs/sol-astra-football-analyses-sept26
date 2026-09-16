"""9.3 risk register, independent-reviewer gate, and Appendix A worked flow."""

from __future__ import annotations

from typing import Any


def risk_register() -> list[dict[str, str]]:
    return [
        {"id": "low_coverage", "signal": "accurate accepted samples but many unknown intervals", "owner": "cv_analyst"},
        {"id": "labels_incomplete", "signal": "service checks pass but locked labels remain incomplete", "owner": "reviewer_owner"},
        {"id": "identity_corruption", "signal": "frequent joins/splits or kit-based confusion", "owner": "cv_backend"},
        {"id": "cost_without_gain", "signal": "miscounted inference or idle allocation", "owner": "operations_media"},
        {"id": "unsupported_ai_claims", "signal": "invented evidence IDs or whole-match conclusions", "owner": "backend_analyst"},
        {"id": "unpermitted_assets", "signal": "missing licence or ambiguous commercial terms", "owner": "owner_legal"},
        {"id": "hosted_exposure", "signal": "missing object-level checks or uncontrolled share links", "owner": "security"},
        {"id": "false_precision", "signal": "exact-looking offside lines or 3D without calibrated evidence", "owner": "product_cv"},
    ]


def worked_match_flow() -> dict[str, Any]:
    return {
        "illustrative": True,
        "assetId": "asset-A",
        "calibrationId": "cal-3",
        "jobId": "run-17",
        "events": ["event-52", "event-53"],
        "correctionId": "edit-8",
        "correctionInvalidatesReportWithoutRerun": True,
        "templateReportSurvivesProviderFailure": True,
    }


def independent_reviewer(*, developer: str, reviewer: str, inspected_held_out: bool) -> dict[str, Any]:
    accepted = reviewer != developer and not inspected_held_out
    reasons = []
    if reviewer == developer:
        reasons.append("REVIEWER_NOT_INDEPENDENT")
    if inspected_held_out:
        reasons.append("HELD_OUT_PREDICTIONS_INSPECTED")
    return {"accepted": accepted, "reasonCodes": reasons}


def telestration_before_3d() -> dict[str, Any]:
    return {"pitchView": "2d", "blenderEnabled": False, "telestration": "basic"}
