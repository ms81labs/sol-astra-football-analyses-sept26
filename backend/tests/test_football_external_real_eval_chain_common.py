from __future__ import annotations

from pathlib import Path
import shutil

import pytest

from backend.scripts import football_external_real_eval_chain_common as common
from backend.scripts.football_external_real_eval_chain_common import reset_output


def test_reset_output_rejects_absolute_name_without_deleting_it(tmp_path: Path) -> None:
    candidate = tmp_path / "candidate"
    candidate.mkdir()
    sentinel = tmp_path / "sentinel"
    sentinel.mkdir()
    marker = sentinel / "keep.txt"
    marker.write_text("keep", encoding="utf-8")

    with pytest.raises(ValueError):
        reset_output(candidate, str(sentinel))

    assert marker.read_text(encoding="utf-8") == "keep"


def test_reset_output_rejects_candidate_root_without_deleting_it(tmp_path: Path) -> None:
    candidate = tmp_path / "candidate"
    candidate.mkdir()
    marker = candidate / "keep.txt"
    marker.write_text("keep", encoding="utf-8")

    with pytest.raises(ValueError):
        reset_output(candidate, ".")

    assert marker.read_text(encoding="utf-8") == "keep"


def test_reset_output_rejects_symlink_target_without_deleting_destination(tmp_path: Path) -> None:
    candidate = tmp_path / "candidate"
    candidate.mkdir()
    sentinel = tmp_path / "sentinel"
    sentinel.mkdir()
    marker = sentinel / "keep.txt"
    marker.write_text("keep", encoding="utf-8")
    (candidate / "output").symlink_to(sentinel, target_is_directory=True)

    with pytest.raises(ValueError):
        reset_output(candidate, "output")

    assert marker.read_text(encoding="utf-8") == "keep"


def test_reset_output_rejects_symlink_component_without_deleting_destination(tmp_path: Path) -> None:
    candidate = tmp_path / "candidate"
    candidate.mkdir()
    sentinel = tmp_path / "sentinel"
    output = sentinel / "output"
    output.mkdir(parents=True)
    marker = output / "keep.txt"
    marker.write_text("keep", encoding="utf-8")
    (candidate / "linked").symlink_to(sentinel, target_is_directory=True)

    with pytest.raises(ValueError):
        reset_output(candidate, "linked/output")

    assert marker.read_text(encoding="utf-8") == "keep"


def test_reset_output_rejects_symlink_in_candidate_root_without_deleting_destination(tmp_path: Path) -> None:
    real_parent = tmp_path / "real"
    output = real_parent / "candidate" / "output"
    output.mkdir(parents=True)
    marker = output / "keep.txt"
    marker.write_text("keep", encoding="utf-8")
    linked_parent = tmp_path / "linked"
    linked_parent.symlink_to(real_parent, target_is_directory=True)

    with pytest.raises(ValueError):
        reset_output(linked_parent / "candidate", "output")

    assert marker.read_text(encoding="utf-8") == "keep"


def test_reset_output_replaces_existing_child_directory(tmp_path: Path) -> None:
    candidate = tmp_path / "candidate"
    output = candidate / "output"
    output.mkdir(parents=True)
    (output / "stale.txt").write_text("stale", encoding="utf-8")

    result = reset_output(candidate, "output")

    assert result == output.absolute()
    assert list(result.iterdir()) == []


def test_reset_output_pins_candidate_when_ancestor_is_swapped_before_delete(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    stable_parent = tmp_path / "stable"
    candidate = stable_parent / "candidate"
    output = candidate / "output"
    output.mkdir(parents=True)
    (output / "stale.txt").write_text("stale", encoding="utf-8")

    outside = tmp_path / "outside"
    outside_output = outside / "candidate" / "output"
    outside_output.mkdir(parents=True)
    marker = outside_output / "keep.txt"
    marker.write_text("keep", encoding="utf-8")
    moved_parent = tmp_path / "moved"
    real_rmtree = shutil.rmtree

    def swap_ancestor_then_delete(path: str | Path, *, dir_fd: int | None = None) -> None:
        stable_parent.rename(moved_parent)
        stable_parent.symlink_to(outside, target_is_directory=True)
        real_rmtree(path, dir_fd=dir_fd)

    monkeypatch.setattr(common.shutil, "rmtree", swap_ancestor_then_delete)

    reset_output(candidate, "output")

    assert marker.read_text(encoding="utf-8") == "keep"
    assert list((moved_parent / "candidate" / "output").iterdir()) == []
