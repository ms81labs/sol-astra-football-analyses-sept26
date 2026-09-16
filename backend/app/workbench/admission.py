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
