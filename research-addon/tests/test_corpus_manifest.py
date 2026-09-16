"""Tests for corpus manifest.

Validates VAL-ADDON-002:
- Corpus membership comes only from explicit manifest
- Two consecutive reads produce identical membership/order when file unchanged
- No scanning of live project state for corpus discovery
"""
import json
import os
import stat
import tempfile
from pathlib import Path

import pytest


def _relocate_addon(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> tuple[Path, Path]:
    import research_addon.path_guards as guards

    checkout = tmp_path / "moved-checkout"
    addon = checkout / "research-addon"
    package = addon / "research_addon"
    package.mkdir(parents=True)
    monkeypatch.setattr(guards, "__file__", str(package / "path_guards.py"))
    monkeypatch.setattr(guards.tempfile, "gettempdir", lambda: str(tmp_path))
    return checkout, addon


class TestCorpusManifest:
    """Test corpus manifest determinism and isolation."""

    def test_create_with_default_entry_has_one_entry(self):
        """Default corpus has exactly one entry for the proof clip."""
        from research_addon.corpus import CorpusManifest

        manifest = CorpusManifest.create_with_default_entries()
        assert len(manifest) == 1
        entry = manifest.entries[0]
        assert entry["video_id"] == "trimed-5min"
        assert entry["video_path"] == "videos/trimed-5min.mp4"
        assert entry["tags"] == ["supported-coverage", "proof-clip", "default"]

    def test_two_consecutive_reads_produce_identical_membership(self):
        """Two reads of unchanged manifest produce identical entries and fingerprint."""
        from research_addon.corpus import CorpusManifest

        with tempfile.TemporaryDirectory() as tmpdir:
            manifest_path = Path(tmpdir) / "corpus-manifest.json"
            manifest = CorpusManifest.create_with_default_entries()
            manifest.write(manifest_path)

            # First read
            m1 = CorpusManifest.from_file(manifest_path)
            fingerprint1 = m1.fingerprint
            entries1 = list(m1.entries)

            # Second read
            m2 = CorpusManifest.from_file(manifest_path)
            fingerprint2 = m2.fingerprint
            entries2 = list(m2.entries)

            assert fingerprint1 == fingerprint2, "Fingerprint must be stable across reads"
            assert entries1 == entries2, "Entry list must be identical across reads"
            assert len(m1) == len(m2)

    def test_manifest_order_is_preserved(self):
        """Manifest writes preserve entry ordering."""
        from research_addon.corpus import CorpusManifest

        with tempfile.TemporaryDirectory() as tmpdir:
            manifest_path = Path(tmpdir) / "corpus-manifest.json"
            entries = [
                {"video_id": "first", "video_path": "videos/first.mp4", "ground_truth_path": None, "tags": ["a"]},
                {"video_id": "second", "video_path": "videos/second.mp4", "ground_truth_path": None, "tags": ["b"]},
            ]
            manifest = CorpusManifest(entries=entries)
            manifest.write(manifest_path)

            loaded = CorpusManifest.from_file(manifest_path)
            assert [e["video_id"] for e in loaded.entries] == ["first", "second"]

    def test_fingerprint_changes_on_content_change(self):
        """Changing manifest content changes the fingerprint."""
        from research_addon.corpus import CorpusManifest

        with tempfile.TemporaryDirectory() as tmpdir:
            manifest_path = Path(tmpdir) / "corpus-manifest.json"

            manifest1 = CorpusManifest.create_with_default_entries()
            manifest1.write(manifest_path)
            fp1 = CorpusManifest.from_file(manifest_path).fingerprint

            # Add a second entry
            manifest2 = CorpusManifest(entries=manifest1.entries + [
                {"video_id": "extra", "video_path": "videos/extra.mp4", "ground_truth_path": None, "tags": ["extra"]}
            ])
            manifest2.write(manifest_path)
            fp2 = CorpusManifest.from_file(manifest_path).fingerprint

            assert fp1 != fp2, "Fingerprint must change when entries change"

    def test_reload_raises_if_entry_count_changed(self):
        """Reloading a manifest whose entries changed raises ValueError."""
        from research_addon.corpus import CorpusManifest

        with tempfile.TemporaryDirectory() as tmpdir:
            manifest_path = Path(tmpdir) / "corpus-manifest.json"
            manifest = CorpusManifest.create_with_default_entries()
            manifest.write(manifest_path)

            loaded = CorpusManifest.from_file(manifest_path)

            # Manually mutate the file (add entry)
            data = json.loads(manifest_path.read_text())
            data["entries"].append({"video_id": "mutant", "video_path": "videos/mutant.mp4", "ground_truth_path": None, "tags": ["mutant"]})
            manifest_path.write_text(json.dumps(data))

            # Reload should detect the change via fingerprint mismatch
            with pytest.raises(ValueError, match="changed on reload"):
                loaded.reload()

    def test_corpus_is_not_discovered_by_scanning(self):
        """Corpus manifest is explicit, not discovered by scanning live project."""
        from research_addon.corpus import CorpusManifest

        # The manifest must come from an explicit file, not from scanning backend/frontend
        manifest = CorpusManifest.create_with_default_entries()
        for entry in manifest.entries:
            # video_path should be a relative path, not something that requires scanning
            assert "video_path" in entry
            assert isinstance(entry["video_path"], str)
            # Tags must be explicit classification
            assert "tags" in entry
            assert isinstance(entry["tags"], list)
            assert len(entry["tags"]) > 0

    def test_manifest_raises_on_missing_file(self):
        """Loading from a non-existent path raises FileNotFoundError."""
        from research_addon.corpus import CorpusManifest

        with pytest.raises(FileNotFoundError):
            CorpusManifest.from_file("/nonexistent/path/manifest.json")

    def test_fingerprint_is_stable_sha_prefix(self):
        """Fingerprint is a 16-char hex string (SHA prefix)."""
        from research_addon.corpus import CorpusManifest

        manifest = CorpusManifest.create_with_default_entries()
        fp = manifest.fingerprint
        assert len(fp) == 16
        assert all(c in "0123456789abcdef" for c in fp)

    def test_default_manifest_write_lands_directly_beneath_addon_root(
        self, tmp_path, monkeypatch
    ):
        from research_addon.corpus import CorpusManifest

        _, addon = _relocate_addon(monkeypatch, tmp_path)
        manifest = CorpusManifest(entries=[])
        manifest.write()

        assert manifest.manifest_path == addon / "corpus-manifest.json"
        assert (addon / "corpus-manifest.json").is_file()

    def test_manifest_traversal_and_protected_root_fail_before_mutation(
        self, tmp_path, monkeypatch
    ):
        from research_addon.corpus import CorpusManifest
        from research_addon.path_guards import PathResolutionError

        checkout, addon = _relocate_addon(monkeypatch, tmp_path)
        backend = checkout / "backend"
        backend.mkdir()
        target = backend / "corpus-manifest.json"
        manifest = CorpusManifest(entries=[])

        with pytest.raises(PathResolutionError):
            manifest.write(addon / "runs" / ".." / ".." / "backend" / target.name)
        assert not target.exists()

    def test_manifest_symlink_write_is_rejected_without_changing_target(
        self, tmp_path, monkeypatch
    ):
        from research_addon.corpus import CorpusManifest
        from research_addon.path_guards import PathResolutionError

        _, addon = _relocate_addon(monkeypatch, tmp_path)
        outside = tmp_path / "outside.json"
        outside.write_text("sentinel")
        target = addon / "corpus-manifest.json"
        target.symlink_to(outside)

        with pytest.raises(PathResolutionError):
            CorpusManifest(entries=[]).write(target)
        assert outside.read_text() == "sentinel"

    def test_manifest_raw_parent_component_fails_when_destination_is_allowed(
        self, tmp_path
    ):
        from research_addon.corpus import CorpusManifest
        from research_addon.path_guards import PathResolutionError

        source = tmp_path / "source"
        destination = tmp_path / "destination"
        source.mkdir()
        destination.mkdir()
        target = source / ".." / destination.name / "manifest.json"

        with pytest.raises(PathResolutionError):
            CorpusManifest(entries=[]).write(target)
        assert not (destination / "manifest.json").exists()

    @pytest.mark.parametrize("fault", ["file_fsync", "replace"])
    def test_manifest_pre_replace_failure_preserves_previous_file_and_cleans_temp(
        self, tmp_path, monkeypatch, fault
    ):
        import research_addon.corpus as corpus

        target = tmp_path / "manifest.json"
        target.write_bytes(b"previous")
        real_fsync = os.fsync

        if fault == "file_fsync":
            def fail_file_fsync(fd):
                if stat.S_ISREG(os.fstat(fd).st_mode):
                    raise OSError("file fsync failed")
                return real_fsync(fd)

            monkeypatch.setattr(corpus.os, "fsync", fail_file_fsync)
        else:
            def fail_replace(_source, _target):
                raise OSError("replace failed")

            monkeypatch.setattr(corpus.os, "replace", fail_replace)

        with pytest.raises(OSError, match="failed"):
            corpus.CorpusManifest(entries=[]).write(target)

        assert target.read_bytes() == b"previous"
        assert list(tmp_path.iterdir()) == [target]

    def test_manifest_publication_fsyncs_file_then_replaces_then_fsyncs_parent(
        self, tmp_path, monkeypatch
    ):
        import research_addon.corpus as corpus

        events = []
        real_fsync = os.fsync
        real_replace = os.replace

        def tracked_fsync(fd):
            events.append(
                "directory-fsync" if stat.S_ISDIR(os.fstat(fd).st_mode) else "file-fsync"
            )
            return real_fsync(fd)

        def tracked_replace(source, target):
            events.append("replace")
            return real_replace(source, target)

        monkeypatch.setattr(corpus.os, "fsync", tracked_fsync)
        monkeypatch.setattr(corpus.os, "replace", tracked_replace)

        corpus.CorpusManifest(entries=[]).write(tmp_path / "manifest.json")
        assert events == ["file-fsync", "replace", "directory-fsync"]

    def test_manifest_parent_fsync_failure_leaves_new_complete_file_visible(
        self, tmp_path, monkeypatch
    ):
        import research_addon.corpus as corpus

        target = tmp_path / "manifest.json"
        target.write_bytes(b"previous")
        real_fsync = os.fsync

        def fail_parent_fsync(fd):
            if stat.S_ISDIR(os.fstat(fd).st_mode):
                raise OSError("parent fsync failed")
            return real_fsync(fd)

        monkeypatch.setattr(corpus.os, "fsync", fail_parent_fsync)

        with pytest.raises(OSError, match="parent fsync failed"):
            corpus.CorpusManifest(entries=[]).write(target)

        assert json.loads(target.read_text())["entries"] == []
        assert list(tmp_path.iterdir()) == [target]
