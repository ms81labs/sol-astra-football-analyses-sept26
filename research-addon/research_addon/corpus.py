"""Corpus manifest management for supported-coverage experiments.

The corpus is the ONLY source of truth for supported-coverage inputs.
Membership and ordering are frozen - two consecutive reads of the
manifest produce identical corpus when the file is unchanged.
"""
from __future__ import annotations

import hashlib
import json
import os
import tempfile
from pathlib import Path
from typing import Any

from research_addon.path_guards import get_default_manifest_path, resolve_manifest_path


def _fingerprint_entries(entries: list[dict[str, Any]]) -> str:
    """Compute a stable fingerprint over corpus entries.

    Uses the canonical JSON representation (sorted keys) so that
    the fingerprint is independent of dict ordering.
    """
    canonical = json.dumps(entries, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode()).hexdigest()[:16]


class CorpusManifest:
    """A frozen, explicit manifest of supported-coverage inputs.

    Corpus membership comes ONLY from this explicit manifest.
    Ordering is stable. Two consecutive reads produce identical
    corpus when the file is unchanged.

    Attributes:
        entries: List of corpus entry dicts in stable order
        fingerprint: 16-char SHA prefix over the canonical entry list
        manifest_path: Path to the manifest file on disk

    Each entry is a dict with required keys:
        - video_id: str, unique identifier
        - video_path: str, path to video file
        - ground_truth_path: str, path to ground truth (or null)
        - tags: list[str], corpus classification tags

    Required output fields that the judge must emit:
        - acceptedBallFrames: int
        - supportedAcceptedBallRatio: float
        - controlledPossessionFrames: int
        - eventFamilyCount: int (count of distinct event types)
        - truthGateReasons: list[str]
    """

    def __init__(
        self,
        entries: list[dict[str, Any]] | None = None,
        manifest_path: Path | str | None = None,
    ) -> None:
        self.manifest_path = (
            Path(manifest_path) if manifest_path else get_default_manifest_path()
        )
        if entries is not None:
            self.entries = list(entries)
            self.fingerprint = _fingerprint_entries(self.entries)
        else:
            self._load()

    def _load(self) -> None:
        """Load manifest from disk, computing fingerprint from current entries."""
        if not self.manifest_path.exists():
            raise FileNotFoundError(f"Corpus manifest not found: {self.manifest_path}")
        raw = json.loads(self.manifest_path.read_text())
        self.entries = list(raw.get("entries", []))
        # Always compute fingerprint from entries (stored fingerprint may be stale after mutation)
        self.fingerprint = _fingerprint_entries(self.entries)

    def reload(self) -> None:
        """Reload manifest from disk, verify fingerprint matches."""
        old_fingerprint = self.fingerprint
        self._load()
        # A changed fingerprint means the manifest was modified
        if self.fingerprint != old_fingerprint:
            raise ValueError(
                f"Corpus manifest changed on reload: {old_fingerprint} != {self.fingerprint}"
            )

    def write(self, path: Path | str | None = None) -> None:
        """Write manifest to disk with embedded fingerprint."""
        target = resolve_manifest_path(path if path is not None else self.manifest_path)
        payload = {
            "version": "1.0",
            "entries": self.entries,
            "fingerprint": self.fingerprint,
        }
        encoded = json.dumps(payload, indent=2, sort_keys=False).encode()
        fd, temp_name = tempfile.mkstemp(
            prefix=f".{target.name}.", suffix=".tmp", dir=target.parent
        )
        temp_path = Path(temp_name)
        replaced = False
        try:
            try:
                stream = os.fdopen(fd, "wb")
            except Exception:
                os.close(fd)
                raise
            with stream:
                stream.write(encoded)
                stream.flush()
                os.fsync(stream.fileno())
            os.replace(temp_path, target)
            replaced = True
            parent_fd = os.open(target.parent, os.O_RDONLY | os.O_DIRECTORY)
            try:
                os.fsync(parent_fd)
            finally:
                os.close(parent_fd)
        finally:
            if not replaced:
                temp_path.unlink(missing_ok=True)

    def __len__(self) -> int:
        return len(self.entries)

    def __iter__(self):
        return iter(self.entries)

    def __getitem__(self, index: int) -> dict[str, Any]:
        return self.entries[index]

    @classmethod
    def from_file(cls, path: Path | str) -> "CorpusManifest":
        """Load a corpus manifest from a file path."""
        return cls(manifest_path=Path(path))

    @classmethod
    def create_with_default_entries(cls) -> "CorpusManifest":
        """Create a corpus manifest with the default supported-coverage entry.

        The default entry points at the trimmed 5-minute proof clip that is
        already used by the existing proof scripts under backend/scripts/.
        """
        entries = [
            {
                "video_id": "trimed-5min",
                "video_path": "videos/trimed-5min.mp4",
                "ground_truth_path": None,
                "tags": ["supported-coverage", "proof-clip", "default"],
            }
        ]
        return cls(entries=entries)
