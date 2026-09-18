"""Summarize all code-only verification gates in one source-bound receipt."""

from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import re
import subprocess


def _passed(log: str) -> int | None:
    matches = re.findall(r"(?:Tests\s+)?(\d+) passed", log)
    return int(matches[-1]) if matches else None


def main() -> None:
    receipt_path = Path(".verification/receipt.json")
    try:
        prior = json.loads(receipt_path.read_text(encoding="utf-8"))
    except (FileNotFoundError, json.JSONDecodeError):
        prior = {}
    gates: dict[str, dict[str, object]] = {}
    counts: dict[str, int] = {}
    for path in sorted(Path(".verification/logs").glob("*.log")):
        content = path.read_text(encoding="utf-8")
        count = _passed(content)
        gate = {"status": "passed", "logSha256": hashlib.sha256(content.encode()).hexdigest()}
        if count is not None:
            gate["passed"] = count
            counts[path.stem] = count
        gates[path.stem] = gate
    commit = os.environ.get("GITHUB_SHA") or subprocess.run(
        ["git", "rev-parse", "HEAD"], check=True, capture_output=True, text=True
    ).stdout.strip()
    receipt = {
        "schemaVersion": 1,
        "commit": commit,
        "profile": os.environ.get("GA_VERIFICATION_PROFILE", "code-only"),
        "stubsActive": prior.get("stubsActive", []),
        "testCounts": counts,
        "totalPassed": sum(counts.values()),
        "gates": gates,
    }
    receipt_path.write_text(json.dumps(receipt, indent=2, sort_keys=True) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
