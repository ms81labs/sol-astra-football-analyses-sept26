"""GA-11 provider policy, evidence selector and output grounding."""

from __future__ import annotations

from typing import Any, Iterable


def select_evidence(claimed_ids: Iterable[str], *, known_ids: set[str]) -> list[str]:
    selected = []
    for evidence_id in claimed_ids:
        if evidence_id not in known_ids:
            raise ValueError("fabricated evidence id")
        selected.append(evidence_id)
    return selected


def ground_output(payload: dict[str, Any], *, known_ids: set[str]) -> dict[str, Any]:
    claimed = list(payload.get("evidence") or [])
    try:
        evidence = select_evidence(claimed, known_ids=known_ids)
    except ValueError:
        return {
            "route": "rejected",
            "reasonCodes": ["FABRICATED_EVIDENCE"],
            "output": {},
        }
    return {
        "route": "template",
        "reasonCodes": ["GROUNDED"],
        "output": {**payload, "evidence": evidence},
    }
