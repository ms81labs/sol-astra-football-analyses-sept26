from __future__ import annotations

import json
from pathlib import Path
from typing import Callable

import pytest

from backend.scripts.run_v7_1_export_label_overlay_audit import run_v7_1_export_label_overlay_audit
from backend.scripts.run_v7_2_export_label_overlay_audit import run_v7_2_export_label_overlay_audit
from backend.scripts.run_v7_3_export_label_overlay_audit import run_v7_3_export_label_overlay_audit


Runner = Callable[..., dict[str, object]]


@pytest.mark.parametrize(
    ("runner", "input_dir_name", "manifest_name"),
    [
        (
            run_v7_1_export_label_overlay_audit,
            "v7_1_crop_manifest_consistency_refresh_v1",
            "v7_1_local_crop_training_manifest.json",
        ),
        (
            run_v7_2_export_label_overlay_audit,
            "v7_2_training_manifest_prep_v1",
            "v7_2_training_manifest.json",
        ),
        (
            run_v7_3_export_label_overlay_audit,
            "v7_3_training_manifest_prep_from_soccernet_real_misses_v1",
            "v7_3_training_manifest.json",
        ),
    ],
)
@pytest.mark.parametrize(
    ("manifest_contents", "expected_error"),
    [(None, FileNotFoundError), ("{not-json", json.JSONDecodeError)],
)
def test_export_audit_preserves_existing_output_until_manifest_is_valid(
    tmp_path: Path,
    runner: Runner,
    input_dir_name: str,
    manifest_name: str,
    manifest_contents: str | None,
    expected_error: type[Exception],
) -> None:
    candidate = tmp_path / "trained_detector_candidates" / "candidate"
    input_root = candidate / input_dir_name
    input_root.mkdir(parents=True)
    if manifest_contents is not None:
        (input_root / manifest_name).write_text(manifest_contents, encoding="utf-8")
    output = candidate / "existing-output"
    output.mkdir()
    sentinel = output / "keep.txt"
    sentinel.write_text("keep", encoding="utf-8")

    with pytest.raises(expected_error):
        runner(
            storage_root=tmp_path,
            candidate_name="candidate",
            input_batch_name=input_dir_name,
            output_dir_name="existing-output",
        )

    assert sentinel.read_text(encoding="utf-8") == "keep"
