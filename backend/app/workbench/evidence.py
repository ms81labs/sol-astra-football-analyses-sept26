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
    intervalStart: float = 0.0
    intervalEnd: float = 0.0
    payload: dict[str, Any] = Field(default_factory=dict)


class EvidencePage(StrictModel):
    items: list[EvidenceRecord] = Field(default_factory=list)
    nextCursor: str | None = None
    intervalEndpoint: str = "half_open"


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

    def query(
        self,
        *,
        interval_start: float | None = None,
        interval_end: float | None = None,
        cursor: str | None = None,
        limit: int = 100,
    ) -> EvidencePage:
        records = [self._records[evidence_id] for evidence_id in self._order]
        if interval_start is not None or interval_end is not None:
            start = float("-inf") if interval_start is None else interval_start
            end = float("inf") if interval_end is None else interval_end
            records = [item for item in records if item.intervalStart < end and item.intervalEnd > start]
        if cursor:
            try:
                index = next(i for i, item in enumerate(records) if item.evidenceId == cursor)
                records = records[index:]
            except StopIteration:
                records = []
        page_items = records[:limit]
        next_cursor = records[limit].evidenceId if len(records) > limit else None
        return EvidencePage(items=page_items, nextCursor=next_cursor)


def metric_dictionary() -> dict[str, dict[str, str]]:
    return {
        "possession_pct": {
            "unit": "percent",
            "denominator": "controlled_possession_frames",
            "definition": "Share of controlled-possession frames assigned to my_team.",
            "withholdUnless": "controlled_frames",
            "publishedLabel": "possession",
            "compatibilityFields": "possession",
        },
        "my_team_distance_m": {
            "unit": "metres",
            "denominator": "identity_continuous_eligible_seconds",
            "definition": "Sum of accepted pitch displacements for reviewed match identities.",
            "withholdUnless": "identity_continuous,calibration_accepted",
            "publishedLabel": "distance",
            "compatibilityFields": "myTeamDistance",
        },
        "enemy_distance_m": {
            "unit": "metres",
            "denominator": "identity_continuous_eligible_seconds",
            "definition": "Sum of accepted pitch displacements for opposing reviewed identities.",
            "withholdUnless": "identity_continuous,calibration_accepted",
            "publishedLabel": "distance",
            "compatibilityFields": "enemyDistance",
        },
        "team_width_m": {
            "unit": "metres",
            "denominator": "eligible_seconds_with_team_visibility",
            "definition": "Lateral spread of accepted on-pitch teammates.",
            "withholdUnless": "calibration_accepted,team_visibility",
            "publishedLabel": "team width",
            "compatibilityFields": "",
        },
        "my_team_ppda": {
            "unit": "passes_per_defensive_action",
            "denominator": "pressing_actions",
            "definition": "Passes allowed per defensive action in the pressing zone. Unknown when the denominator is empty.",
            "withholdUnless": "nonzero_denominator",
            "publishedLabel": "PPDA",
            "compatibilityFields": "myTeamPpda",
        },
        "experimental_shot_quality": {
            "unit": "probability",
            "denominator": "labelled_shots",
            "definition": "Heuristic shot quality. Compatibility field remains `xg`; this is not a calibrated xG model.",
            "withholdUnless": "",
            "publishedLabel": "experimental_shot_quality",
            "compatibilityFields": "xg",
        },
        EVENT_HEURISTIC_NAME: {
            "unit": "count",
            "denominator": "reviewed_or_protocol_eligible_events",
            "definition": "Heuristic event suggestions. Not independent event truth.",
            "withholdUnless": "independent_event_labels",
            "publishedLabel": "provisional event suggestion",
            "compatibilityFields": "",
        },
    }


def evaluate_metric_spec(
    metric: str,
    *,
    value: float | None,
    denominator: float,
    identity_continuous: bool,
    calibration_accepted: bool,
) -> MetricAvailability:
    spec = metric_dictionary().get(metric, {})
    required = {item for item in (spec.get("withholdUnless") or "").split(",") if item}
    reasons: list[str] = []
    if "identity_continuous" in required and not identity_continuous:
        reasons.append("IDENTITY_DISCONTINUITY")
    if "calibration_accepted" in required and not calibration_accepted:
        reasons.append("CALIBRATION_UNAVAILABLE")
    if "nonzero_denominator" in required and denominator <= 0:
        reasons.append("ZERO_DENOMINATOR")
    if "controlled_frames" in required and denominator <= 0:
        reasons.append("ZERO_DENOMINATOR")
    if reasons:
        availability = "unknown" if reasons == ["ZERO_DENOMINATOR"] else "withheld"
        return MetricAvailability(
            metric=metric,
            definitionVersion=DEFINITION_VERSION,
            value=None,
            availability=availability,
            reasonCodes=reasons,
            unit=spec.get("unit"),
            denominator=spec.get("denominator"),
        )
    return MetricAvailability(
        metric=metric,
        definitionVersion=DEFINITION_VERSION,
        value=value,
        availability="experimental" if metric == "experimental_shot_quality" else "available",
        unit=spec.get("unit"),
        denominator=spec.get("denominator"),
    )


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


def inspect_metric(
    metric: str,
    *,
    value: float | None = None,
    availability: str = "unknown",
    eligible_duration: float = 0.0,
    exclusions: list[str] | None = None,
) -> dict[str, Any]:
    spec = metric_dictionary().get(metric, {})
    unknown = availability != "available" or value is None
    return {
        "metric": metric,
        "unit": spec.get("unit"),
        "denominator": spec.get("denominator"),
        "definitionVersion": DEFINITION_VERSION,
        "eligibleDuration": eligible_duration,
        "exclusions": list(exclusions or []),
        "rendered": "unavailable" if unknown else str(value),
        "publishedValue": None if unknown else value,
    }


def migrate_legacy_record(summary: dict[str, Any]) -> dict[str, dict[str, Any]]:
    metrics = summarize_legacy_match(
        summary,
        identity_continuous=False,
        calibration_accepted=False,
        controlled_frames=int(summary.get("controlledFrames") or 0),
    )
    return {
        item.metric: {"value": item.value, "availability": item.availability, "reasonCodes": item.reasonCodes}
        for item in metrics
    }


def rollback_reader(migrated: dict[str, dict[str, Any]]) -> dict[str, Any]:
    return {
        "possession": (migrated.get("possession_pct") or {}).get("value"),
        "myTeamDistance": (migrated.get("my_team_distance_m") or {}).get("value"),
        "xg": (migrated.get("experimental_shot_quality") or {}).get("value"),
    }
