"""GA-06/08 vision extraction boundary. Detectors and trackers remain adapters."""

from backend.app.workbench.geometry import CalibrationProfile, ground_contact_point, project_to_pitch, review_incident_geometry
from backend.app.workbench.perception import (
    DetectorAdapter,
    IdentityRepair,
    PreprocessPlan,
    TrackerAdapter,
    merge_tiled_detections,
    score_detections_by_stratum,
    tile_to_source,
)

__all__ = [
    "CalibrationProfile",
    "DetectorAdapter",
    "IdentityRepair",
    "PreprocessPlan",
    "TrackerAdapter",
    "ground_contact_point",
    "merge_tiled_detections",
    "project_to_pitch",
    "review_incident_geometry",
    "score_detections_by_stratum",
    "tile_to_source",
]
