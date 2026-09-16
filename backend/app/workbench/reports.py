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
    grounded = ground_output({"evidence": claimed_evidence_ids}, known_ids=known_evidence_ids) if claimed_evidence_ids else {
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
        "publication": {"accepted": accepted, "requiresAnalyst": True},
    }
