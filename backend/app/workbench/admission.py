"""GA-02 camera admission profiles. These are declarations, not certifications."""

from __future__ import annotations

from typing import Literal

from pydantic import Field

from .contracts import StrictModel

CameraProfile = Literal[
    "stable_elevated_wide",
    "stitched_panoramic_view",
    "broadcast_cuts_zoom",
    "handheld_low_angle",
]


class CameraAdmission(StrictModel):
    profile: CameraProfile
    automation: str
    withhold: list[str] = Field(default_factory=list)
    certified: bool = False


_PROFILES: dict[CameraProfile, tuple[str, list[str]]] = {
    "stable_elevated_wide": ("candidate", ["far_side_visibility"]),
    "stitched_panoramic_view": ("development", ["global_homography_may_be_inadequate"]),
    "broadcast_cuts_zoom": ("manual_review", ["continuous_tracking", "distance_totals"]),
    "handheld_low_angle": ("manual_tagging", ["physical_metrics", "full_team_metrics"]),
}


def admit_camera(profile: CameraProfile) -> CameraAdmission:
    automation, withhold = _PROFILES[profile]
    return CameraAdmission(profile=profile, automation=automation, withhold=withhold, certified=False)


SUPPORTED_CODECS = {"h264", "hevc", "av1", "mpeg4", "vp9", "mpeg2video"}


def admit_media(
    identity,
    *,
    existing_digests: set[str] | None = None,
    require_audio: bool = False,
    supported_codecs: set[str] | None = None,
) -> dict[str, object]:
    """Reject unsafe/unsupported/duplicate/interrupted media before allocation."""

    reasons: list[str] = []
    warnings: list[str] = []
    codecs = supported_codecs or SUPPORTED_CODECS
    existing = existing_digests or set()
    errors = [str(item).lower() for item in (identity.decodeErrors or [])]
    if any("unsafe" in item for item in errors):
        reasons.append("UNSAFE_MEDIA")
    if identity.codec not in codecs:
        reasons.append("UNSUPPORTED_CODEC")
    if identity.sourceSha256 in existing:
        reasons.append("DUPLICATE_CONTENT")
    if any("truncat" in item or "interrupt" in item for item in errors):
        reasons.append("INTERRUPTED_FILE")
    if int(identity.audioTracks or 0) == 0:
        if require_audio:
            reasons.append("MISSING_AUDIO")
        else:
            warnings.append("MISSING_AUDIO")
    return {
        "admitted": not reasons,
        "reasonCodes": reasons,
        "warnings": warnings,
        "variableFrameRate": bool(identity.variableFrameRate),
        "rotation": int(identity.rotation or 0),
    }
