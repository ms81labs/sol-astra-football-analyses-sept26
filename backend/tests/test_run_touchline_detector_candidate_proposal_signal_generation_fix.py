from __future__ import annotations

from pathlib import Path

import backend.scripts.run_touchline_detector_candidate_v5_proposal_signal_generation_fix as run_touchline_detector_candidate_v5_proposal_signal_generation_fix


def test_v5_proposal_signal_fix_split_manifest_uses_written_export_examples(tmp_path: Path) -> None:
    positive_label = tmp_path / "val_positive.txt"
    val_negative_label = tmp_path / "val_negative.txt"
    train_negative_label = tmp_path / "train_negative.txt"
    positive_label.write_text("0 0.5 0.5 0.1 0.1\n", encoding="utf-8")
    val_negative_label.write_text("", encoding="utf-8")
    train_negative_label.write_text("", encoding="utf-8")

    exported_examples = [
        {
            "curationUnitId": "unit-a",
            "split": "val",
            "labelPath": str(positive_label),
            "cropWindowKind": "direct_seed_tight",
        },
        {
            "curationUnitId": "unit-a",
            "split": "val",
            "labelPath": str(positive_label),
            "cropWindowKind": "direct_seed_tight",
        },
        {
            "curationUnitId": "unit-a",
            "split": "val",
            "labelPath": str(val_negative_label),
            "cropWindowKind": "player_ranked",
        },
        {
            "curationUnitId": "unit-b",
            "split": "train",
            "labelPath": str(train_negative_label),
            "cropWindowKind": "player_ranked",
        },
    ]

    split_manifest = run_touchline_detector_candidate_v5_proposal_signal_generation_fix._build_split_manifest(exported_examples)
    alignment_report = run_touchline_detector_candidate_v5_proposal_signal_generation_fix._build_alignment_report(
        alignment={
            "windowFamily": "proposal_windows_075",
            "positiveWindowKindCounts": {"direct_seed_tight": 1},
            "negativeWindowKindCounts": {"player_ranked": 2},
            "negativePriorityCounts": {},
        },
        exported_examples=exported_examples,
        split_manifest=split_manifest,
    )

    assert split_manifest["validationImageCount"] == 2
    assert split_manifest["validationPositiveLabelImageCount"] == 1
    assert split_manifest["validationEmptyLabelImageCount"] == 1
    assert alignment_report["proposalWindowValidationImageCount"] == 2
    assert alignment_report["proposalWindowValidationPositiveImageCount"] == 1
    assert alignment_report["validationPositiveWindowKindCounts"] == {"direct_seed_tight": 1}
