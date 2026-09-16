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
) -> DpiaDecision:
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
