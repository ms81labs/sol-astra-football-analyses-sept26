"""GA-03 evidence versioning and GA-09 metric dictionary."""

from __future__ import annotations

from typing import Any, Iterable, Literal

from pydantic import Field

from .contracts import (
    MetricAvailability,
    ObservationSource,
    ReviewStatus,
    StrictModel,
    migrate_legacy_zero,
    unknown_metric,
)

DEFINITION_VERSION = "1"

PHYSICAL_METRICS = (
    "my_team_distance_m",
    "enemy_distance_m",
    "my_team_top_speed_kmh",
    "enemy_top_speed_kmh",
    "my_team_sprints",
    "enemy_sprints",
)
TEAM_METRICS = ("possession_pct",)
EVENT_HEURISTIC_NAME = "provisional_event_suggestion"


class EvidenceRecord(StrictModel):
    evidenceId: str
    schemaVersion: str = "evidence_v1"
    parentIds: list[str] = Field(default_factory=list)
    observationSource: ObservationSource
    reviewStatus: ReviewStatus
    supersededBy: str | None = None
    algorithmHash: str | None = None
    modelHash: str | None = None
    decoderVersion: str | None = None
    temporalPolicy: str | None = None
    payload: dict[str, Any] = Field(default_factory=dict)


class EvidenceStore:
    def __init__(self) -> None:
        self._records: dict[str, EvidenceRecord] = {}
        self._order: list[str] = []

    def put(self, record: EvidenceRecord) -> EvidenceRecord:
        if record.evidenceId in self._records:
            raise ValueError(f"evidence {record.evidenceId} already exists")
        self._records[record.evidenceId] = record
        self._order.append(record.evidenceId)
        return record

    def get(self, evidence_id: str) -> EvidenceRecord:
        return self._records[evidence_id]

    def correct(
        self,
        evidence_id: str,
        *,
        new_id: str,
        payload: dict[str, Any],
        review_status: ReviewStatus = "corrected",
    ) -> EvidenceRecord:
        previous = self.get(evidence_id)
        replacement = previous.model_copy(
            update={
                "evidenceId": new_id,
                "parentIds": [previous.evidenceId, *previous.parentIds],
                "reviewStatus": review_status,
                "payload": payload,
                "supersededBy": None,
            }
        )
        self.put(replacement)
        self._records[evidence_id] = previous.model_copy(update={"supersededBy": new_id, "reviewStatus": "superseded"})
        return replacement

    def lineage(self, evidence_id: str) -> list[EvidenceRecord]:
        current = self.get(evidence_id)
        chain = [current]
        for parent_id in current.parentIds:
            chain.append(self.get(parent_id))
        return chain


def metric_dictionary() -> dict[str, dict[str, str]]:
    return {
        "possession_pct": {
            "unit": "percent",
            "denominator": "controlled_possession_frames",
            "definition": "Share of controlled-possession frames assigned to my_team.",
        },
        "my_team_distance_m": {
            "unit": "metres",
            "denominator": "identity_continuous_eligible_seconds",
            "definition": "Sum of accepted pitch displacements for reviewed match identities.",
        },
        "enemy_distance_m": {
            "unit": "metres",
            "denominator": "identity_continuous_eligible_seconds",
            "definition": "Sum of accepted pitch displacements for opposing reviewed identities.",
        },
        "team_width_m": {
            "unit": "metres",
            "denominator": "eligible_seconds_with_team_visibility",
            "definition": "Lateral spread of accepted on-pitch teammates.",
        },
        EVENT_HEURISTIC_NAME: {
            "unit": "count",
            "denominator": "reviewed_or_protocol_eligible_events",
            "definition": "Heuristic event suggestions. Not independent event truth.",
        },
    }


def summarize_legacy_match(
    summary: dict[str, Any],
    *,
    identity_continuous: bool,
    calibration_accepted: bool,
    controlled_frames: int,
) -> list[MetricAvailability]:
    requested = float(summary.get("requestedSeconds") or 0.0)
    possession = summary.get("possession")
    metrics: list[MetricAvailability] = []
    if possession is None or controlled_frames <= 0:
        metrics.append(
            unknown_metric(
                "possession_pct",
                definition_version=DEFINITION_VERSION,
                reason_codes=["ZERO_DENOMINATOR"],
                requested_seconds=requested,
                unit="percent",
                denominator="controlled_possession_frames",
            )
        )
    else:
        metrics.append(
            MetricAvailability(
                metric="possession_pct",
                definitionVersion=DEFINITION_VERSION,
                value=float(possession),
                availability="available",
                eligibleSeconds=requested,
                requestedSeconds=requested,
                unit="percent",
                denominator="controlled_possession_frames",
            )
        )

    physical_ok = identity_continuous and calibration_accepted
    for name, key in (
        ("my_team_distance_m", "myTeamDistance"),
        ("enemy_distance_m", "enemyDistance"),
        ("my_team_top_speed_kmh", "myTeamTopSpeed"),
        ("enemy_top_speed_kmh", "enemyTopSpeed"),
        ("my_team_sprints", "myTeamSprints"),
        ("enemy_sprints", "enemySprints"),
    ):
        reason = "IDENTITY_DISCONTINUITY" if not identity_continuous else "CALIBRATION_UNAVAILABLE"
        metrics.append(
            migrate_legacy_zero(
                name,
                summary.get(key),
                definition_version=DEFINITION_VERSION,
                measured=physical_ok,
                reason_if_unmeasured=reason,
                unit=metric_dictionary().get(name, {}).get("unit"),
                denominator=metric_dictionary().get(name, {}).get("denominator"),
            )
        )
    return metrics


def round_trip_unknown(metric: MetricAvailability) -> MetricAvailability:
    restored = MetricAvailability.model_validate_json(metric.model_dump_json())
    if restored.published_value() is not None:
        raise ValueError("unknown metrics must not acquire a published value")
    return restored
