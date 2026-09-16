"""8.4 architecture decisions. Alternatives, evidence, owner and reconsideration."""

from __future__ import annotations

from typing import Any


def architecture_decisions() -> list[dict[str, Any]]:
    return [
        {
            "id": "camera_support",
            "decision": "stitched_panoramic_view_declared_initial",
            "alternatives": ["stable_elevated_wide_first", "generic_camera_automation"],
            "evidence": "plan_4_1_admission_table; independent_accuracy_unproven",
            "owner": "cv",
            "reversible": True,
            "reconsiderWhen": "independent_labels_and_declared_camera_pilot_accepted",
        },
        {
            "id": "coordinate_conventions",
            "decision": "pitch_x_longitudinal_y_lateral_image_space_separate",
            "alternatives": ["unified_pixel_metres_label", "broadcast_origin_only"],
            "evidence": "plan_6_1_quantities; four_point_homography_compat",
            "owner": "cv",
            "reversible": True,
            "reconsiderWhen": "versioned_calibration_with_distortion_replaces_four_points",
        },
        {
            "id": "persistence",
            "decision": "sqlite_metadata_plus_content_addressed_artifacts",
            "alternatives": ["replace_storage_py_immediately", "mandatory_duckdb"],
            "evidence": "plan_6_2_6_3; repository_adapter_does_not_replace_storage",
            "owner": "backend_media",
            "reversible": True,
            "reconsiderWhen": "measured_observation_tables_justify_columnar_migration",
        },
        {
            "id": "detector_licensing",
            "decision": "review_exact_ultralytics_code_and_weights_before_commercial_use",
            "alternatives": ["treat_yolo_name_as_unrestricted", "silent_agpl_assumption"],
            "evidence": "plan_9_1; rights_register",
            "owner": "lead",
            "reversible": True,
            "reconsiderWhen": "qualified_licence_advice_for_exact_pinned_assets",
        },
        {
            "id": "ai_routing",
            "decision": "typed_allowlist_then_grounded_template_fallback",
            "alternatives": ["video_chatbot_rewrite", "unbounded_provider_calls"],
            "evidence": "plan_5_2_5_3; fabricated_evidence_rejected",
            "owner": "backend",
            "reversible": True,
            "reconsiderWhen": "held_out_questions_show_material_recall_benefit",
        },
        {
            "id": "cloud_region",
            "decision": "loopback_until_g_network_daytona_region_is_not_eu_proof",
            "alternatives": ["assume_requested_gpu_region", "silent_cloud_fallback"],
            "evidence": "plan_9_2; residency_claim",
            "owner": "operations",
            "reversible": True,
            "reconsiderWhen": "explicit_provider_arrangement_proves_residency",
            "euGpuProven": False,
        },
        {
            "id": "capability_release",
            "decision": "independent_gates_not_merged_files",
            "alternatives": ["treat_synthetic_fixtures_as_accuracy", "unlock_labels_from_software"],
            "evidence": "plan_8_2_progress_signal; frozen_protocol_v3",
            "owner": "independent_evaluation",
            "reversible": True,
            "reconsiderWhen": "locked_labels_18_of_18_and_analyst_accepted_pilot",
        },
    ]
