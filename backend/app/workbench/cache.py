"""GA-12 cache identity for selective recomputation."""

from __future__ import annotations

import hashlib
import json
import math
import re
from dataclasses import dataclass, is_dataclass
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict

from ..domain_types import Interval


_UNKNOWN = {"", "unknown", "unspecified", "none"}


def _known(value: Any) -> bool:
    if value is None or (isinstance(value, str) and value.strip().lower() in _UNKNOWN):
        return False
    if is_dataclass(value):
        return all(_known(item) for key, item in vars(value).items() if key != "_unknown_salt")
    if hasattr(value, "model_dump"):
        return all(_known(item) for item in value.model_dump().values())
    if isinstance(value, dict):
        return all(_known(item) for item in value.values())
    if isinstance(value, (list, tuple)):
        return all(_known(item) for item in value)
    if isinstance(value, float):
        return math.isfinite(value)
    return isinstance(value, (str, int, bool))


def _identity_payload(value: Any, *, include_unknown_salt: bool) -> Any:
    if is_dataclass(value):
        return {
            key: _identity_payload(item, include_unknown_salt=include_unknown_salt)
            for key, item in vars(value).items()
            if include_unknown_salt or key != "_unknown_salt"
        }
    if hasattr(value, "model_dump"):
        return _identity_payload(value.model_dump(mode="json"), include_unknown_salt=include_unknown_salt)
    if isinstance(value, dict):
        return {key: _identity_payload(item, include_unknown_salt=include_unknown_salt) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_identity_payload(item, include_unknown_salt=include_unknown_salt) for item in value]
    return value


class _LayerIdentity:
    @property
    def reusable(self) -> bool:
        if not _known(self):
            return False
        # A shaped all-zero digest is a sentinel, not verified source/weight bytes.
        return all(isinstance(value, str) and re.fullmatch(r"[0-9a-f]{64}", value)
                   and value != "0" * 64
                   for name, value in vars(self).items() if name.endswith("_sha256")) and all(
                       value.reusable for value in vars(self).values() if isinstance(value, _LayerIdentity))

    def digest(self) -> str | None:
        if not self.reusable:
            return None
        payload = self.components()
        canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"), allow_nan=False)
        return hashlib.sha256(canonical.encode("utf-8")).hexdigest()

    def components(self) -> dict[str, Any]:
        return _identity_payload(self, include_unknown_salt=False)


@dataclass(frozen=True)
class DetectionIdentity(_LayerIdentity):
    source_sha256: str | None
    stream_index: int | None
    interval: Interval | None
    weights_sha256: str | None
    preprocessing_id: str | None
    class_map_id: str | None
    precision: str | None
    runtime_build: str | None


@dataclass(frozen=True)
class TrackingIdentity(_LayerIdentity):
    detection: DetectionIdentity
    tracker_config_id: str | None


@dataclass(frozen=True)
class ProjectionIdentity(_LayerIdentity):
    tracking: TrackingIdentity
    calibration_revision: str | None


@dataclass(frozen=True)
class ReviewedIdentity(_LayerIdentity):
    projection: ProjectionIdentity
    correction_head: str | None


@dataclass(frozen=True)
class ReportIdentity(_LayerIdentity):
    reviewed: ReviewedIdentity
    report_template_version: str | None


class _RecomputeModel(BaseModel):
    model_config = ConfigDict(extra="forbid")


class RecomputePlan(_RecomputeModel):
    kind: Literal["plan"] = "plan"
    change: str
    rebuild: list[str]
    requires: list[str]
    visionRequired: bool


class RecomputeReceipt(_RecomputeModel):
    kind: Literal["executed"] = "executed"
    change: str
    inputArtifacts: dict[str, str]
    outputGeneration: str
    rebuilt: list[str]
    detectorCalls: int


class RecomputeRefusal(_RecomputeModel):
    kind: Literal["refused"] = "refused"
    reasonCodes: list[str]


def cache_identity(
    *,
    source_sha256: str,
    interval_start: float,
    interval_end: float,
    decoder_version: str,
    model_hash: str,
    temporal_policy: str,
    output_schema: str,
    crop: tuple[int, int, int, int] | None = None,
    colour_order: str = "bgr",
    calibration_id: str | None = None,
    namespace: str = "development",
) -> str:
    payload: dict[str, Any] = {
        "sourceSha256": source_sha256,
        "intervalStart": interval_start,
        "intervalEnd": interval_end,
        "decoderVersion": decoder_version,
        "modelHash": model_hash,
        "temporalPolicy": temporal_policy,
        "outputSchema": output_schema,
        "crop": list(crop) if crop else None,
        "colourOrder": colour_order,
        "calibrationId": calibration_id,
        "namespace": namespace,
    }
    canonical = json.dumps(payload, sort_keys=True, separators=(",", ":"), allow_nan=False)
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def cache_compatible(left: str | None, right: str | None) -> bool:
    return bool(left) and left == right


REBUILD_FOR: dict[str, list[str]] = {
    "report": ["report"],
    "team_mapping": ["team_state", "events", "metrics", "report"],
    "track_edit": ["ownership", "player_events", "metrics", "report"],
    "calibration": ["pitch_positions", "physical_metrics", "tactical_metrics", "report"],
    "perception": ["observations", "tracking", "dependants"],
    "ownership": ["events", "metrics", "report"],
}


def recompute_plan(
    *,
    previous_identity: str | None,
    current_identity: str,
    change: str,
) -> dict[str, Any]:
    if previous_identity is not None and cache_compatible(previous_identity, current_identity):
        return {"reuse": True, "rebuild": [], "reason": "identical_cache_identity"}
    return {
        "reuse": False,
        "rebuild": list(REBUILD_FOR[change]),
        "reason": "cache_identity_changed",
    }
