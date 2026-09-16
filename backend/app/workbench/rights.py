"""GA-14 rights: uncertain commercial permission blocks the use."""

from __future__ import annotations

from typing import Any

from pydantic import Field

from .contracts import StrictModel


class RightsDecision(StrictModel):
    allowed: bool
    cloudPermitted: bool = False
    reasonCodes: list[str] = Field(default_factory=list)
    asset: str | None = None


def evaluate_rights(record: dict[str, Any]) -> RightsDecision:
    asset = str(record.get("asset") or "")
    if record.get("commercialPermission") == "uncertain":
        return RightsDecision(
            asset=asset,
            allowed=False,
            cloudPermitted=False,
            reasonCodes=["UNCERTAIN_COMMERCIAL_PERMISSION"],
        )
    return RightsDecision(
        asset=asset,
        allowed=True,
        cloudPermitted=bool(record.get("cloudPermitted")),
        reasonCodes=[],
    )


def rights_register() -> dict[str, Any]:
    return {
        "uncertainCommercialPermissionBlocks": True,
        "items": [
            {"asset": "match_recording", "control": "source_rights_and_retention"},
            {"asset": "ultralytics_weights", "control": "review_exact_code_and_weight_licence"},
            {"asset": "soccernet", "control": "research_use_not_commercial_product"},
            {"asset": "youth_footage", "control": "safeguarding_and_club_permission_required"},
        ],
        "openSourceDoesNotMeanUnrestricted": True,
    }
