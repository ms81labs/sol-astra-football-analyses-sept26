"""GA-05.1 task-specific model roster. Upgrades stay unpromoted until independent acceptance."""

from __future__ import annotations

from typing import Any


def model_roster() -> list[dict[str, Any]]:
    return [
        {"task": "geometry_metrics", "first": "python_numpy", "upgrade": "profiled_numerics", "promoted": False},
        {"task": "player_ball", "first": "pinned_yolo", "upgrade": "rfdetr_compact_candidate", "promoted": False},
        {"task": "identity_association", "first": "botsort_adapter", "upgrade": "detector_independent_tracker", "promoted": False},
        {"task": "shot_probability", "first": "logistic_baseline", "upgrade": "boosted_tree_if_calibrated", "promoted": False},
        {"task": "temporal_events", "first": "state_machine_rules", "upgrade": "frozen_video_features_plus_head", "promoted": False},
        {"task": "search_notes", "first": "typed_filters_templates", "upgrade": "compact_language_model", "promoted": False},
        {"task": "tactical_comparison", "first": "analyst_led_review", "upgrade": "configured_stronger_model", "promoted": False},
    ]


def promotion_gate(*, task: str, independent_accepted: bool, licence_recorded: bool) -> dict[str, Any]:
    reasons: list[str] = []
    if not independent_accepted:
        reasons.append("INDEPENDENT_ACCEPTANCE_MISSING")
    if not licence_recorded:
        reasons.append("LICENCE_UNREVIEWED")
    return {"task": task, "promoted": not reasons, "reasonCodes": reasons}


def label_products() -> dict[str, Any]:
    return {
        "cvat": {"role": "independent_labelling", "sameProductAsCorrections": False},
        "in_app_corrections": {"role": "analyst_repair", "sameProductAsCorrections": False},
    }


def video_model_roster() -> dict[str, Any]:
    return {
        "qwen3_5_4b": {"promoted": False, "role": "compact_local_language_candidate"},
        "mvitv2": {"promoted": False, "role": "pretrained_video_reference"},
        "videomae_v2": {"promoted": False, "role": "pretrained_video_reference"},
    }


def frontier_provider_role(*, model_id: str) -> dict[str, Any]:
    return {
        "modelId": model_id,
        "role": "frontier",
        "hardCodedModelName": False,
        "promoted": False,
    }
