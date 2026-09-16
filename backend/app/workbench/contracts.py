"""Shared evidence, availability and capability contracts (GA-01, GA-03, GA-09)."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field


Availability = Literal[
    "available",
    "unknown",
    "insufficient_coverage",
    "withheld",
    "permission_denied",
    "experimental",
]
AVAILABILITY_STATES: tuple[Availability, ...] = (
    "available",
    "unknown",
    "insufficient_coverage",
    "withheld",
    "permission_denied",
    "experimental",
)

ObservationSource = Literal[
    "observed",
    "inferred",
    "player_conditioned",
    "unknown",
]
ReviewStatus = Literal["unreviewed", "accepted", "rejected", "corrected", "superseded"]
EvidenceClass = Literal[
    "software_verification",
    "pipeline_execution",
    "independent_accuracy",
    "capacity",
    "analyst_acceptance",
]
CapabilityStatus = Literal[
    "usable",
    "review_only",
    "experimental",
    "unavailable",
    "blocked",
    "unproven",
]

REASON_CODES: dict[str, str] = {
    "CALIBRATION_UNAVAILABLE": "No accepted calibration covers this interval.",
    "INSUFFICIENT_TEAM_VISIBILITY": "Too few accepted team observations for the requested metric.",
    "IDENTITY_DISCONTINUITY": "Track identity is fragmented across the requested interval.",
    "UNKNOWN_BALL_STATE": "Ball location is hidden, inferred or otherwise unsupported.",
    "PERMISSION_DENIED": "Rights or processing policy forbid this output.",
    "ZERO_DENOMINATOR": "The metric denominator is empty; the value is unknown, not zero.",
    "EXPORT_FPS_IS_NOT_INFERENCE_FPS": "Exported sample cadence is not an inference-cost measurement.",
    "LABELS_INCOMPLETE": "Independent locked labels are not complete for this protocol.",
    "HARDWARE_UNAVAILABLE": "Required accelerator hardware is not present or not authorised.",
    "NATIVE_GATE_CLOSED": "Custom native code is inert until an explicit reviewed approval exists.",
    "PROVIDER_DISABLED": "Language or remote providers are disabled; deterministic fallback is in use.",
    "FABRICATED_EVIDENCE": "A generated claim referenced evidence that does not exist.",
    "LEGACY_ZERO_DEFAULT": "A historical zero default is preserved for readers and is not a measurement.",
    "CAMERA_PROFILE_UNSUPPORTED": "Automated measurement is withheld for this camera profile.",
    "OUTCOME_UNKNOWN": "Remote submission timed out before a confirmed lifecycle state existed.",
}

CAPABILITY_IDS: tuple[str, ...] = (
    "manual_review",
    "team_level_tactical_estimates",
    "event_suggestions",
    "player_attribution",
    "physical_metrics",
    "incident_review",
)

INTERVAL_ENDPOINT = "half_open"  # [start, end)


class StrictModel(BaseModel):
    model_config = ConfigDict(strict=True, extra="forbid", frozen=True)


class Interval(StrictModel):
    """Half-open source interval in seconds of presentation time."""

    startSeconds: float
    endSeconds: float
    inclusiveStart: bool = True
    exclusiveEnd: bool = True

    def contains(self, timestamp_seconds: float) -> bool:
        start_ok = timestamp_seconds >= self.startSeconds if self.inclusiveStart else timestamp_seconds > self.startSeconds
        end_ok = timestamp_seconds < self.endSeconds if self.exclusiveEnd else timestamp_seconds <= self.endSeconds
        return start_ok and end_ok

    def duration_seconds(self) -> float:
        return max(0.0, self.endSeconds - self.startSeconds)


class MetricAvailability(StrictModel):
    metric: str
    definitionVersion: str
    value: float | None
    availability: Availability
    eligibleSeconds: float = 0.0
    requestedSeconds: float = 0.0
    evidenceIds: list[str] = Field(default_factory=list)
    reasonCodes: list[str] = Field(default_factory=list)
    reviewStatus: ReviewStatus = "unreviewed"
    unit: str | None = None
    denominator: str | None = None

    def published_value(self) -> float | None:
        if self.availability != "available":
            return None
        return self.value


class CapabilityEntry(StrictModel):
    id: str
    label: str
    status: CapabilityStatus
    evidenceClass: EvidenceClass
    evidenceLink: str
    notes: str = ""
    independentlyVisible: bool = True


class SourceClockIdentity(StrictModel):
    sourceSha256: str
    byteSize: int
    codec: str | None = None
    width: int | None = None
    height: int | None = None
    rotation: int = 0
    pixelFormat: str | None = None
    colourRange: str | None = None
    timeBaseNum: int = 1
    timeBaseDen: int = 1
    nominalFps: float | None = None
    durationSeconds: float | None = None
    frameCount: int | None = None
    variableFrameRate: bool = False
    audioTracks: int = 0
    decodeErrors: list[str] = Field(default_factory=list)


class FrameIdentity(StrictModel):
    sourceFrameIndex: int
    presentationTimeSeconds: float
    pts: int | None = None
    sampleId: str
    matchClockSeconds: float | None = None
    decoderBackend: str
    pixelFormat: str = "bgr24"


class SamplingReceipt(StrictModel):
    sourceSha256: str
    declaredTargetFps: float
    nominalFps: float | None
    frameInterval: int
    decodedFrameCount: int
    primaryInferenceCount: int
    recoveryInferenceCount: int
    trackerUpdateCount: int
    exportedSampleCount: int
    temporalPolicy: str
    selectedBackend: str
    fallbackBackend: str | None = None
    fallbackOccurred: bool = False
    notes: list[str] = Field(default_factory=list)

    def export_fps_equals_inference_fps(self) -> bool:
        return False


class JobPhase(StrictModel):
    requestId: str
    attemptId: str
    status: Literal[
        "submitted",
        "validating",
        "waiting_for_capacity",
        "running",
        "importing",
        "complete",
        "failed",
        "cancelling",
        "cancelled",
        "outcome_unknown",
    ]
    selectedBackend: str | None = None
    actualHardware: str | None = None
    temporalPolicy: str | None = None
    fallbackPolicy: str | None = None
    costReserved: float = 0.0
    costActual: float | None = None
    cleanupResult: Literal["confirmed", "failed", "not_required", "unknown"] = "not_required"
    cacheIdentity: str | None = None


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def unknown_metric(
    metric: str,
    *,
    definition_version: str,
    reason_codes: list[str],
    requested_seconds: float = 0.0,
    unit: str | None = None,
    denominator: str | None = None,
) -> MetricAvailability:
    return MetricAvailability(
        metric=metric,
        definitionVersion=definition_version,
        value=None,
        availability="unknown",
        eligibleSeconds=0.0,
        requestedSeconds=requested_seconds,
        evidenceIds=[],
        reasonCodes=reason_codes,
        reviewStatus="unreviewed",
        unit=unit,
        denominator=denominator,
    )


def migrate_legacy_zero(
    metric: str,
    legacy_value: float | int | None,
    *,
    definition_version: str,
    measured: bool,
    reason_if_unmeasured: str,
    unit: str | None = None,
    denominator: str | None = None,
) -> MetricAvailability:
    """Preserve a legacy numeric default without promoting it to a measurement."""

    if measured and legacy_value is not None:
        return MetricAvailability(
            metric=metric,
            definitionVersion=definition_version,
            value=float(legacy_value),
            availability="available",
            eligibleSeconds=0.0,
            requestedSeconds=0.0,
            evidenceIds=[],
            reasonCodes=[],
            unit=unit,
            denominator=denominator,
        )
    return unknown_metric(
        metric,
        definition_version=definition_version,
        reason_codes=["LEGACY_ZERO_DEFAULT", reason_if_unmeasured],
        unit=unit,
        denominator=denominator,
    )


def jsonable(model: BaseModel) -> dict[str, Any]:
    return model.model_dump(mode="json")
