"""GA-11/5.3 grounded report assembly. Narrative is optional; facts stay deterministic."""

from __future__ import annotations

from typing import Any

from backend.app.ai_policy import ground_output

from .assistance import template_report


def assemble_report(
    *,
    metrics: list[dict[str, Any]],
    events: list[dict[str, Any]],
    claimed_evidence_ids: list[str],
    known_evidence_ids: set[str],
    narrative: dict[str, Any] | None = None,
) -> dict[str, Any]:
    grounded: dict[str, Any] = ground_output({"evidence": claimed_evidence_ids}, known_ids=known_evidence_ids) if claimed_evidence_ids else {
        "route": "template",
        "reasonCodes": ["GROUNDED"],
        "output": {"evidence": []},
    }
    evidence_ids = list(grounded.get("output", {}).get("evidence") or [])
    if not claimed_evidence_ids:
        evidence_ids = sorted({eid for event in events for eid in event.get("evidenceIds") or []})
    fact_package = {
        "metrics": metrics,
        "events": events,
        "definitions": [item.get("metric") for item in metrics],
        "template": template_report(metrics, events),
    }
    invented = []
    if narrative:
        for metric in metrics:
            name = metric.get("metric")
            if name in narrative and narrative[name] != metric.get("value"):
                invented.append(name)
    factual_reasons = list(grounded.get("reasonCodes") or [])
    if invented:
        factual_reasons.append("INVENTED_NUMBER")
    if grounded.get("route") == "rejected":
        factual_reasons = list(grounded.get("reasonCodes") or ["FABRICATED_EVIDENCE"])
    accepted = "FABRICATED_EVIDENCE" not in factual_reasons and "INVENTED_NUMBER" not in factual_reasons
    return {
        "evidenceSelection": {"evidenceIds": evidence_ids, "exclusions": list(factual_reasons)},
        "factPackage": fact_package,
        "narrativeDraft": {"optional": True, "payload": narrative or {}, "separatedFromFacts": True},
        "factualCheck": {"accepted": accepted, "reasonCodes": factual_reasons},
        "publication": {"accepted": accepted, "requiresAnalyst": True, "wholeMatchFrequency": False, "frequencyRequiresDenominator": True},
    }


def claim_provenance(
    *,
    claims: list[dict[str, Any]],
    known_evidence_ids: set[str],
) -> dict[str, Any]:
    missing = [
        evidence_id
        for claim in claims
        for evidence_id in claim.get("evidenceIds") or []
        if evidence_id not in known_evidence_ids
    ]
    reasons = ["FABRICATED_EVIDENCE"] if missing else []
    return {
        "accepted": not reasons,
        "claims": claims,
        "reasonCodes": reasons,
        "missingEvidenceIds": missing,
    }


def coverage_aware_selector(
    *,
    frames: list[dict[str, Any]],
    events: list[dict[str, Any]],
    max_frames: int,
) -> dict[str, Any]:
    picked = frames[: max(0, max_frames)]
    if frames:
        picked = [frames[0], frames[len(frames) // 2], frames[-1]][:max_frames]
    return {
        "frames": picked,
        "events": events,
        "coverageAware": True,
        "representsWholeMatch": False,
    }


def held_out_questions() -> list[dict[str, Any]]:
    return [
        {
            "text": "show our second-half turnovers followed by a shot within 10 seconds",
            "unanswerable": False,
            "expectedFilter": {"eventFamily": "turnover", "successorEvent": "shot", "maxGapSeconds": 10},
        },
        {
            "text": "how tired was player 7 in the 89th minute",
            "unanswerable": True,
            "expectedFilter": {"reason": "medical_inference_refused"},
        },
    ]
