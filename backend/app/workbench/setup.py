"""GA-04 match setup: periods, camera, rights and a support assessment."""

from __future__ import annotations

from typing import Any

from .admission import admit_camera


def assess_match_setup(
    *,
    camera_profile: str,
    pitch_length_m: float | None,
    rights: dict[str, Any],
    periods: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    admission = admit_camera(camera_profile)  # type: ignore[arg-type]
    automation = admission.automation in {"candidate", "development"} and not admission.withhold
    if camera_profile == "stable_elevated_wide":
        automation = True
    return {
        "cameraProfile": camera_profile,
        "automationAdmitted": automation,
        "manualTaggingPermitted": True,
        "cannotMeasure": list(admission.withhold),
        "certified": False,
        "pitchLengthM": pitch_length_m,
        "periods": periods or [],
        "cloudPermission": bool(rights.get("cloudPermission")),
        "costEstimateRequiresAuthorisation": True,
        "explanation": (
            "Rejected automation still permits manual tagging; withheld metrics are not measured."
            if not automation
            else "Candidate automation profile; not a certification of the current implementation."
        ),
    }


def create_match(*, title: str, camera_profile: str, rights: dict[str, Any] | None = None) -> dict[str, Any]:
    assessment = assess_match_setup(
        camera_profile=camera_profile,
        pitch_length_m=None,
        rights=rights or {},
    )
    return {
        "title": title,
        "processingStarted": False,
        "manualTaggingPermitted": True,
        "cameraProfile": camera_profile,
        "automationAdmitted": assessment["automationAdmitted"],
        "cannotMeasure": assessment["cannotMeasure"],
    }
