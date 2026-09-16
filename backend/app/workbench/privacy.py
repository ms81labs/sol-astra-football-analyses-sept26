"""GA-14 privacy-by-design screening. Track IDs do not anonymise identifiable video."""

from __future__ import annotations

from pydantic import Field

from .contracts import StrictModel


class DpiaDecision(StrictModel):
    cloudAllowed: bool
    localProcessingRequired: bool
    faceRecognition: bool = False
    crossSeasonIdentity: bool = False
    reasonCodes: list[str] = Field(default_factory=list)


def dpia_screen(
    *,
    youth_footage: bool,
    identifiable_faces: bool,
    cloud_requested: bool,
    cloud_permitted: bool,
    face_recognition_requested: bool = False,
    cross_season_requested: bool = False,
) -> DpiaDecision:
    del face_recognition_requested, cross_season_requested
    reasons: list[str] = []
    if youth_footage:
        reasons.append("YOUTH_FOOTAGE")
    if identifiable_faces and cloud_requested:
        reasons.append("IDENTIFIABLE_VIDEO")
    if cloud_requested and not cloud_permitted:
        reasons.append("CLOUD_PERMISSION_ABSENT")
    cloud_allowed = cloud_requested and cloud_permitted and not youth_footage
    return DpiaDecision(
        cloudAllowed=cloud_allowed,
        localProcessingRequired=not cloud_allowed,
        faceRecognition=False,
        crossSeasonIdentity=False,
        reasonCodes=reasons,
    )


def residency_claim(*, requested_region: str, provider: str) -> dict[str, object]:
    return {
        "provider": provider,
        "requestedRegion": requested_region,
        "euProcessingProven": False,
        "reasonCodes": ["REQUESTED_REGION_IS_NOT_PROOF"],
    }
