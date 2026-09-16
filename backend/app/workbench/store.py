"""Filesystem persistence for workbench artifacts."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .contracts import jsonable
from .dossier import BaselineDossier, build_baseline_dossier, build_release_dossier
from .review import Correction


class WorkbenchStore:
    def __init__(self, storage_root: Path):
        self.root = Path(storage_root) / "workbench"
        self.root.mkdir(parents=True, exist_ok=True)

    def save_dossier(self, dossier: BaselineDossier) -> Path:
        path = self.root / "baseline-dossier.json"
        path.write_text(json.dumps(jsonable(dossier), indent=2) + "\n", encoding="utf-8")
        release = build_release_dossier(dossier)
        (self.root / "release-dossier.json").write_text(json.dumps(release, indent=2) + "\n", encoding="utf-8")
        return path

    def load_dossier(self) -> dict[str, Any]:
        path = self.root / "baseline-dossier.json"
        if not path.exists():
            dossier = build_baseline_dossier()
            self.save_dossier(dossier)
        return json.loads((self.root / "baseline-dossier.json").read_text(encoding="utf-8"))

    def append_correction(self, correction: Correction) -> None:
        path = self.root / "corrections" / f"{correction.matchId}.jsonl"
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("a", encoding="utf-8") as handle:
            handle.write(correction.model_dump_json() + "\n")

    def list_corrections(self, match_id: str) -> list[dict[str, Any]]:
        path = self.root / "corrections" / f"{match_id}.jsonl"
        if not path.exists():
            return []
        return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]

    def write_json(self, name: str, payload: dict[str, Any]) -> Path:
        path = self.root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(payload, indent=2) + "\n", encoding="utf-8")
        return path
