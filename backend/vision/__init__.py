"""GA-06/08 vision extraction boundary. Detectors and trackers remain adapters."""

from backend.app.workbench.geometry import CalibrationProfile, ground_contact_point, project_to_pitch, review_incident_geometry
from backend.app.workbench.perception import (
    DetectorAdapter,
    IdentityRepair,
    PreprocessorAdapter,
    TrackerAdapter,
    score_detections_by_stratum,
)

__all__ = [
    "CalibrationProfile",
    "DetectorAdapter",
    "IdentityRepair",
    "PreprocessorAdapter",
    "TrackerAdapter",
    "ground_contact_point",
    "project_to_pitch",
    "review_incident_geometry",
    "score_detections_by_stratum",
]
