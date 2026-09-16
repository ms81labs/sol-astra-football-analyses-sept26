"""GA-06/08 vision extraction boundary. Detectors and trackers remain adapters."""

from backend.app.workbench.geometry import CalibrationProfile, review_incident_geometry
from backend.app.workbench.perception import IdentityRepair, TrackerAdapter, score_detections_by_stratum

__all__ = [
    "CalibrationProfile",
    "IdentityRepair",
    "TrackerAdapter",
    "review_incident_geometry",
    "score_detections_by_stratum",
]
