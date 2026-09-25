"""C02 source-space projection boundary; no detector invocation or source writes.

Named pre-envelope Guerilla FrameData/uppercase row imports are the historical
normalised-pitch format. This migration is shape/version based, never a guess
from coordinate magnitudes. Video Source_X* fields are already original-source
boxes; a generic processed bbox requires an explicit inverse mapping.
"""
from __future__ import annotations

from dataclasses import replace
import math
from typing import Any, Literal, NoReturn, NotRequired, TypedDict

from .coordinate_contracts import CoordinateConvention
from .schemas import FrameData, BallData
from .semantic_commands import SemanticCommandError
from .workbench.contracts import CalibrationRevision
from .workbench.geometry import CalibrationProfile, project_point, validate_homography


def refused(code: str, message: str) -> NoReturn:
    raise SemanticCommandError(code, message, status_code=409)


def _point(matrix, x: float, y: float) -> tuple[float, float]:
    if validate_homography(matrix):
        refused("INVALID_SOURCE_MAPPING", "The inverse observation mapping is unusable")
    w = matrix[2][0] * x + matrix[2][1] * y + matrix[2][2]
    if not math.isfinite(w) or abs(w) <= 1e-12:
        refused("INVALID_SOURCE_MAPPING", "The source anchor maps to infinity")
    out = ((matrix[0][0]*x+matrix[0][1]*y+matrix[0][2])/w,
           (matrix[1][0]*x+matrix[1][1]*y+matrix[1][2])/w)
    if not all(math.isfinite(v) for v in out):
        refused("INVALID_SOURCE_MAPPING", "Nonfinite source anchor")
    return out


def _profile(revision, convention: CoordinateConvention):
    if revision is None or not revision.accepted or not revision.measured:
        refused("CALIBRATION_REQUIRED", "Source pixels need a measured accepted calibration")
    profile = CalibrationProfile.model_validate(revision.profile)
    if profile.cameraModel != "planar_homography" or profile.distortionK:
        refused("CAMERA_MODEL_UNSUPPORTED", "This materialiser admits planar calibrated source pixels only")
    if convention.streamId is not None and convention.streamId != profile.sourceStreamId:
        refused("CALIBRATION_SOURCE_MISMATCH", "Calibration belongs to another source stream")
    for field in ("sourceWidth", "sourceHeight"):
        actual, expected = getattr(convention, field), getattr(profile, field)
        if actual is not None and expected is not None and actual != expected:
            refused("CALIBRATION_SOURCE_MISMATCH", "Calibration source dimensions differ")
    return profile


def _covered(profile, revision, timestamp: float) -> bool:
    start = max(profile.sourceIntervalStart, revision.validInterval.start)
    ends = [v for v in (profile.sourceIntervalEnd, revision.validInterval.end) if v is not None]
    return timestamp >= start and (not ends or timestamp < min(ends))


class _CoordinateProvenance(TypedDict):
    schemaVersion: Literal[1]
    inputConvention: dict[str, object]
    outputConvention: Literal["pitch_normalized_0_100"]
    calibrationRevision: str | None
    migration: str | None
    reasonCodes: list[str]
    sourceClock: NotRequired[dict[str, int]]
    sourceDimensions: NotRequired[dict[str, int]]
    geometryAvailable: NotRequired[bool]


def _provenance(
    convention: CoordinateConvention,
    *,
    revision: CalibrationRevision | None = None,
    migration: str | None = None,
) -> _CoordinateProvenance:
    return {"schemaVersion": 1, "inputConvention": convention.model_dump(mode="json"),
            "outputConvention": "pitch_normalized_0_100",
            "calibrationRevision": revision.revisionId if revision else None,
            "migration": migration, "reasonCodes": []}


def import_tracking(payload: Any, *, convention=None) -> tuple[list[FrameData], CoordinateConvention, str | None]:
    from .analytics import normalize_tracking_rows
    migration = None
    if isinstance(payload, dict):
        if payload.get("schemaVersion") != 2 or payload.get("format") != "guerilla_tracking_v2":
            refused("COORDINATE_CONVENTION_REQUIRED", "An undeclared tracking object is not calibrated geometry")
        if ("frames" in payload) == ("rows" in payload):
            refused("INVALID_TRACKING_ENVELOPE", "Declare exactly one frames or rows collection")
        source = payload.get("frames", payload.get("rows"))
        declared = CoordinateConvention.model_validate(payload.get("coordinates", {"space": "unknown"}))
    elif isinstance(payload, list):
        source = payload
        # Named historical API formats, not arbitrary x/y dictionaries.
        if payload and not all(isinstance(row, dict) and ("frameId" in row or
                       {"Frame_ID", "Timestamp", "Entity_Type", "Track_ID", "X", "Y"} <= row.keys()) for row in payload):
            refused("COORDINATE_CONVENTION_REQUIRED", "Unknown legacy tracking format")
        declared = CoordinateConvention(space="pitch_normalized_0_100")
        migration = "guerilla_frame_or_rows_v1:normalised_pitch"
    else:
        refused("INVALID_TRACKING_ENVELOPE", "Tracking input must be a named frame/row array or v2 envelope")
    if not isinstance(source, list):
        refused("INVALID_TRACKING_ENVELOPE", "Tracking observations must be an array")
    declared = convention or declared
    if declared.space == "unknown":
        refused("COORDINATE_CONVENTION_REQUIRED", "Unknown coordinates cannot publish geometric analysis")
    return normalize_tracking_rows(source), declared, migration


def project_tracking(frames, convention, revision, *, migration=None):
    profile = _profile(revision, convention) if convention.space == "source_pixels" else None
    if profile is not None and (convention.sourceWidth is None or convention.streamId is None):
        refused("SOURCE_OBSERVATIONS_REQUIRED", "Pixel tracking needs source dimensions and stream identity")
    if convention.space == "unknown":
        refused("COORDINATE_CONVENTION_REQUIRED", "Unknown coordinates cannot publish geometric analysis")
    def point(x, y):
        if profile is not None:
            if convention.sourceFromObservation is not None:
                x, y = _point(convention.sourceFromObservation, x, y)
            if not (0 <= x <= convention.sourceWidth and 0 <= y <= convention.sourceHeight):
                refused("SOURCE_ANCHOR_OUT_OF_BOUNDS", "Tracking source anchor is outside declared dimensions")
            x, y = project_point(profile, x, y)
            return x / revision.pitchLengthM * 100, y / revision.pitchWidthM * 100
        if convention.space == "pitch_metres":
            return x / convention.pitchLengthM * 100, y / convention.pitchWidthM * 100
        return x, y
    result = []
    for f in frames:
        provenance = _provenance(convention, revision=revision if profile else None, migration=migration)
        covered = profile is None or _covered(profile, revision, f.timestamp)
        changes = {"coordinateSpace": "pitch_normalized_0_100", "geometryAvailable": covered,
                   "coordinateProvenance": provenance, "possession": None}
        if not covered:
            provenance["reasonCodes"] = ["CALIBRATION_INTERVAL_UNAVAILABLE"]
        for field in ("myTeam", "enemies", "unassignedPlayers"):
            players = []
            if covered:
                for player in getattr(f, field):
                    x, y = point(player.x, player.y)
                    players.append(replace(player, x=x, y=y))
            changes[field] = players
        # Pixel tracking's ball is not known to be on the ground. Do not create
        # a measured planar location without a per-observation ground-state contract.
        changes["ball"] = None
        if covered and f.ball is not None and profile is None:
            bx, by = point(f.ball.x, f.ball.y)
            changes["ball"] = BallData(x=bx, y=by, confidence=f.ball.confidence)
        if profile and f.ball is not None:
            provenance["reasonCodes"].append("BALL_GROUND_STATE_UNKNOWN")
        result.append(f.model_copy(update=changes))
    return result


def project_video_rows(rows, revision, *, convention=None):
    from .analytics import normalize_tracking_rows
    if revision is None:
        # The existing worker's X/Y view can still be reviewed, but this is not
        # a claim that a new calibration was applied or physical values verified.
        frames = normalize_tracking_rows(rows)
        return [f.model_copy(update={"geometryAvailable": False,
                "coordinateProvenance": {"schemaVersion":1,"migration":"guerilla_video_rows_v1:legacy_pitch_view",
                                         "reasonCodes":["CALIBRATION_REQUIRED"]}}) for f in frames]
    convention = convention or CoordinateConvention(space="source_pixels", streamId="video:0")
    if convention.space != "source_pixels":
        refused("SOURCE_OBSERVATIONS_REQUIRED", "Video recalibration requires source-pixel observations")
    profile = _profile(revision, convention)
    converted = []
    frame_info: dict[int, _CoordinateProvenance] = {}
    times: dict[int, float] = {}
    dimensions = None
    keys = ("Source_X1", "Source_Y1", "Source_X2", "Source_Y2")
    for row in rows:
        fid, timestamp = int(row["Frame_ID"]), float(row["Timestamp"])
        if not math.isfinite(timestamp) or fid < 0:
            refused("INVALID_SOURCE_CLOCK", "Invalid source frame or timestamp")
        if fid in times and times[fid] != timestamp:
            refused("INVALID_SOURCE_CLOCK", "Rows disagree about a frame timestamp")
        times[fid] = timestamp
        provenance = frame_info.setdefault(fid, _provenance(convention, revision=revision,
                                                migration="guerilla_video_source_boxes_v1"))
        clock = {k: row[k] for k in ("PTS", "TimeBaseNum", "TimeBaseDen") if k in row}
        if clock:
            if len(clock) != 3 or any(type(v) is not int for v in clock.values()) or clock['TimeBaseNum'] <= 0 or clock['TimeBaseDen'] <= 0:
                refused("INVALID_SOURCE_CLOCK", "Incomplete or invalid rational source clock")
            if not math.isclose(clock['PTS'] * clock['TimeBaseNum'] / clock['TimeBaseDen'], timestamp, abs_tol=1e-6):
                refused("INVALID_SOURCE_CLOCK", "Timestamp and source PTS disagree")
            if 'sourceClock' in provenance and provenance['sourceClock'] != clock:
                refused("INVALID_SOURCE_CLOCK", "Rows disagree about a frame's clock")
            provenance['sourceClock'] = clock
        covered = _covered(profile, revision, timestamp)
        provenance["geometryAvailable"] = covered
        if not covered:
            provenance["reasonCodes"] = ["CALIBRATION_INTERVAL_UNAVAILABLE"]
            continue
        kind = row["Entity_Type"]
        if kind == "ball" and (row.get("airborne") is True or (row.get("airborne") is not False and row.get("groundPlane") is not True)):
            provenance["reasonCodes"].append("BALL_GROUND_STATE_UNKNOWN" if not row.get("airborne") else "AERIAL_NOT_GROUND_PLANE")
            continue
        source_box = all(row.get(k) is not None for k in keys)
        box = [row[k] for k in keys] if source_box else row.get("bbox")
        if not isinstance(box, (list,tuple)) or len(box)!=4 or not all(type(v) in (float,int) and math.isfinite(v) for v in box):
            refused("SOURCE_OBSERVATIONS_REQUIRED", "Recalibration requires the original source box for every player")
        x1,y1,x2,y2 = box
        if x2 < x1 or y2 < y1:
            refused("SOURCE_OBSERVATIONS_REQUIRED", "Invalid source box")
        x,y = (x1+x2)/2, (y1+y2)/2 if kind == "ball" else y2
        if not source_box:
            if convention.sourceFromObservation is None:
                refused("SOURCE_OBSERVATIONS_REQUIRED", "A processed bbox requires an inverse crop/resize/rotation map")
            # A quarter-turn changes which processed edge represents the feet.
            # Recover the source-aligned box first, then take its contact anchor.
            corners = [_point(convention.sourceFromObservation, cx, cy)
                       for cx, cy in ((x1,y1),(x2,y1),(x2,y2),(x1,y2))]
            x = (min(p[0] for p in corners) + max(p[0] for p in corners)) / 2
            y = (min(p[1] for p in corners) + max(p[1] for p in corners)) / 2 if kind == "ball" else max(p[1] for p in corners)
        width = convention.sourceWidth or row.get('Source_Width') or profile.sourceWidth
        height = convention.sourceHeight or row.get('Source_Height') or profile.sourceHeight
        if any(type(v) is not int or v <= 0 for v in (width, height)):
            refused("SOURCE_OBSERVATIONS_REQUIRED", "Original source dimensions must be declared")
        for field, actual in (("sourceWidth", width), ("sourceHeight", height)):
            expected = getattr(profile, field)
            if expected is not None and expected != actual:
                refused("CALIBRATION_SOURCE_MISMATCH", "Calibration source dimensions differ")
        if dimensions is not None and dimensions != (width, height):
            refused("SOURCE_OBSERVATIONS_REQUIRED", "Variable source dimensions require a supported mapping")
        dimensions = (width, height)
        provenance["sourceDimensions"] = {"width": width, "height": height}
        if not (0 <= x <= width and 0 <= y <= height):
            refused("SOURCE_ANCHOR_OUT_OF_BOUNDS", "Player contact anchor lies outside source dimensions")
        px,py = project_point(profile,x,y)
        converted.append({**row,"X":px / revision.pitchLengthM * 100,"Y":py / revision.pitchWidthM * 100})
    by_id = {f.frameId:f for f in normalize_tracking_rows(converted)}
    for fid, provenance in frame_info.items():
        frame = by_id.get(fid, FrameData(frameId=fid,timestamp=times[fid]))
        by_id[fid] = frame.model_copy(update={"coordinateProvenance":provenance,
            "coordinateSpace":"pitch_normalized_0_100","geometryAvailable":provenance["geometryAvailable"]})
    return [by_id[fid] for fid in sorted(by_id)]
