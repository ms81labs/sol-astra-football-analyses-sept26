"""4.6 deferred xT/VAEP. Importing socceraction does not validate extraction."""

from __future__ import annotations


def xt_deferred_plan() -> dict[str, object]:
    return {
        "enabled": False,
        "imported": False,
        "blockedUntil": "event schema maps consistently into a SPADL action representation",
        "socceractionImportDoesNotValidateExtraction": True,
        "vaepEnabled": False,
    }
