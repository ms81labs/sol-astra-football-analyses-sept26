from __future__ import annotations

SOURCE_EDGE_SHARE_REPAIR_TARGET_CLIP = "trimed-5min.mp4"
UNIFORM_EDGE_RUN_THIN_MODE = "uniform_edge_run_thin"
SUPPORT_GUARDED_THIN_MODE = "support_guarded_thin"
TOUCHLINE_PROBE_REPLACE_MODE = "touchline_probe_replace"
TOUCHLINE_ACQUISITION_UPGRADE_MODE = "touchline_acquisition_upgrade"
TOUCHLINE_ACQUISITION_REOPEN_MODE = "touchline_acquisition_reopen"
TOUCHLINE_CANDIDATE_ADMISSION_REOPEN_MODE = "touchline_candidate_admission_reopen"

ACTIVE_SOURCE_EDGE_SHARE_REPAIR_CONFIGS = {
    "source_robustness_shadow_edge_run_keep_every_2_min8": {
        "mode": UNIFORM_EDGE_RUN_THIN_MODE,
        "keepEvery": 2,
        "minRunLength": 8,
        "guardFrameCount": 0,
    },
    "source_robustness_shadow_edge_run_keep_every_2_min9": {
        "mode": UNIFORM_EDGE_RUN_THIN_MODE,
        "keepEvery": 2,
        "minRunLength": 9,
        "guardFrameCount": 0,
    },
    "source_robustness_shadow_edge_run_keep_every_2_min10": {
        "mode": UNIFORM_EDGE_RUN_THIN_MODE,
        "keepEvery": 2,
        "minRunLength": 10,
        "guardFrameCount": 0,
    },
    "source_robustness_shadow_edge_run_keep_every_3_min9": {
        "mode": UNIFORM_EDGE_RUN_THIN_MODE,
        "keepEvery": 3,
        "minRunLength": 9,
        "guardFrameCount": 0,
    },
    "source_robustness_shadow_edge_run_keep_every_3_min10": {
        "mode": UNIFORM_EDGE_RUN_THIN_MODE,
        "keepEvery": 3,
        "minRunLength": 10,
        "guardFrameCount": 0,
    },
    "source_robustness_shadow_edge_run_keep_every_3_min11": {
        "mode": UNIFORM_EDGE_RUN_THIN_MODE,
        "keepEvery": 3,
        "minRunLength": 11,
        "guardFrameCount": 0,
    },
}

SUPPORT_AWARE_SOURCE_EDGE_SHARE_REPAIR_CONFIGS = {
    "source_robustness_shadow_supported_edge_run_keep_every_2_min10_guard2": {
        "mode": SUPPORT_GUARDED_THIN_MODE,
        "keepEvery": 2,
        "minRunLength": 10,
        "guardFrameCount": 2,
    },
    "source_robustness_shadow_supported_edge_run_keep_every_3_min10_guard2": {
        "mode": SUPPORT_GUARDED_THIN_MODE,
        "keepEvery": 3,
        "minRunLength": 10,
        "guardFrameCount": 2,
    },
    "source_robustness_shadow_supported_edge_run_keep_every_2_min14_guard2": {
        "mode": SUPPORT_GUARDED_THIN_MODE,
        "keepEvery": 2,
        "minRunLength": 14,
        "guardFrameCount": 2,
    },
    "source_robustness_shadow_supported_edge_run_keep_every_3_min14_guard2": {
        "mode": SUPPORT_GUARDED_THIN_MODE,
        "keepEvery": 3,
        "minRunLength": 14,
        "guardFrameCount": 2,
    },
}

TOUCHLINE_REPLACEMENT_SOURCE_EDGE_SHARE_REPAIR_CONFIGS = {
    "source_robustness_shadow_touchline_probe_replace_v1": {
        "mode": TOUCHLINE_PROBE_REPLACE_MODE,
        "keepEvery": 0,
        "minRunLength": 10,
        "guardFrameCount": 0,
    },
}

TOUCHLINE_ACQUISITION_SOURCE_EDGE_SHARE_REPAIR_CONFIGS = {
    "source_robustness_shadow_touchline_acquisition_upgrade_v1": {
        "mode": TOUCHLINE_ACQUISITION_UPGRADE_MODE,
        "keepEvery": 0,
        "minRunLength": 10,
        "guardFrameCount": 0,
    },
    "source_robustness_shadow_touchline_acquisition_reopen_v2": {
        "mode": TOUCHLINE_ACQUISITION_REOPEN_MODE,
        "keepEvery": 0,
        "minRunLength": 10,
        "guardFrameCount": 0,
    },
    "source_robustness_shadow_touchline_candidate_admission_reopen_v3": {
        "mode": TOUCHLINE_CANDIDATE_ADMISSION_REOPEN_MODE,
        "keepEvery": 0,
        "minRunLength": 10,
        "guardFrameCount": 0,
    },
}

PROMOTED_V6_ADMISSION_WIDENING_SOURCE_EDGE_SHARE_REPAIR_CONFIGS = {
    "source_robustness_shadow_promoted_v6_admission_widening_v1": {
        "mode": TOUCHLINE_CANDIDATE_ADMISSION_REOPEN_MODE,
        "keepEvery": 0,
        "minRunLength": 10,
        "guardFrameCount": 0,
        "admissionWideningEnabled": True,
        "admissionWideningRequirePlayerSupport": True,
        "admissionWideningMaxProjectedEdgeShare": 0.6,
    },
    "source_robustness_shadow_promoted_v6_baseline_guided_rescue_v1": {
        "mode": TOUCHLINE_CANDIDATE_ADMISSION_REOPEN_MODE,
        "keepEvery": 0,
        "minRunLength": 10,
        "guardFrameCount": 0,
        "baselineGuidedRescueEnabled": True,
        "baselineGuidedRescueMaxProjectedEdgeShare": 0.6,
    },
    "source_robustness_shadow_promoted_v6_continuity_bridge_recovery_v1": {
        "mode": TOUCHLINE_CANDIDATE_ADMISSION_REOPEN_MODE,
        "keepEvery": 0,
        "minRunLength": 10,
        "guardFrameCount": 0,
        "continuityBridgeRecoveryEnabled": True,
        "continuityBridgeRecoveryMaxGapFrames": 20,
        "continuityBridgeRecoveryMaxProjectedEdgeShare": 0.6,
        "continuityBridgeRecoveryRequireEndpointContinuity": True,
    },
    "source_robustness_shadow_promoted_v6_acceptance_support_gating_v1": {
        "mode": TOUCHLINE_CANDIDATE_ADMISSION_REOPEN_MODE,
        "keepEvery": 0,
        "minRunLength": 10,
        "guardFrameCount": 0,
        "acceptanceSupportGatingEnabled": True,
        "acceptanceSupportGatingRequirePlayerSupport": True,
        "acceptanceSupportGatingRequireSupportImprovement": True,
        "acceptanceSupportGatingMaxProjectedEdgeShare": 0.6,
        "acceptanceSupportGatingRequireRealDetectedCandidateRows": True,
    },
    "source_robustness_shadow_promoted_v6_proposal_selection_admission_fix_v1": {
        "mode": TOUCHLINE_CANDIDATE_ADMISSION_REOPEN_MODE,
        "keepEvery": 0,
        "minRunLength": 10,
        "guardFrameCount": 0,
        "proposalSelectionAdmissionFixEnabled": True,
        "proposalSelectionAdmissionFixApproachFamily": "truth_seed_guided_selection",
        "proposalSelectionAdmissionFixTruthSeedPath": (
            "backend/storage/benchmark_suites/frozen-viable-baseline-slice-suite/"
            "promoted_v6_source_manifest_and_gold_truth_refresh_v1/"
            "gold_truth_bootstrap_attempt_v1/accepted_controlled_truth_seed.json"
        ),
        "proposalSelectionAdmissionFixTargetSourceClipId": SOURCE_EDGE_SHARE_REPAIR_TARGET_CLIP,
        "proposalSelectionAdmissionFixMaxProjectedEdgeShare": 0.6,
        "proposalSelectionAdmissionFixRequireRealDetectedCandidateRows": True,
        "proposalSelectionAdmissionFixPreserveRepeatedAnchorGuard": True,
        "proposalSelectionAdmissionFixPreserveContinuityGuard": True,
        "proposalSelectionAdmissionFixMaxSeedPitchDistance": 8.0,
    },
    "source_robustness_shadow_promoted_v6_proposal_selection_admission_fix_v2": {
        "mode": TOUCHLINE_CANDIDATE_ADMISSION_REOPEN_MODE,
        "keepEvery": 0,
        "minRunLength": 10,
        "guardFrameCount": 0,
        "proposalSelectionAdmissionFixEnabled": True,
        "proposalSelectionAdmissionFixApproachFamily": "window_local_proposal_kind_rescue",
        "proposalSelectionAdmissionFixTruthSeedPath": (
            "backend/storage/benchmark_suites/frozen-viable-baseline-slice-suite/"
            "promoted_v6_source_manifest_and_gold_truth_refresh_v1/"
            "gold_truth_bootstrap_attempt_v1/accepted_controlled_truth_seed.json"
        ),
        "proposalSelectionAdmissionFixTargetSourceClipId": SOURCE_EDGE_SHARE_REPAIR_TARGET_CLIP,
        "proposalSelectionAdmissionFixMaxProjectedEdgeShare": 0.6,
        "proposalSelectionAdmissionFixRequireRealDetectedCandidateRows": True,
        "proposalSelectionAdmissionFixPreserveRepeatedAnchorGuard": True,
        "proposalSelectionAdmissionFixPreserveContinuityGuard": True,
        "proposalSelectionAdmissionFixMaxSeedPitchDistance": 8.0,
    },
    "source_robustness_shadow_promoted_v6_proposal_selection_admission_fix_v3": {
        "mode": TOUCHLINE_CANDIDATE_ADMISSION_REOPEN_MODE,
        "keepEvery": 0,
        "minRunLength": 10,
        "guardFrameCount": 0,
        "proposalSelectionAdmissionFixEnabled": True,
        "proposalSelectionAdmissionFixApproachFamily": "segment_level_seed_continuity",
        "proposalSelectionAdmissionFixTruthSeedPath": (
            "backend/storage/benchmark_suites/frozen-viable-baseline-slice-suite/"
            "promoted_v6_source_manifest_and_gold_truth_refresh_v1/"
            "gold_truth_bootstrap_attempt_v1/accepted_controlled_truth_seed.json"
        ),
        "proposalSelectionAdmissionFixTargetSourceClipId": SOURCE_EDGE_SHARE_REPAIR_TARGET_CLIP,
        "proposalSelectionAdmissionFixMaxProjectedEdgeShare": 0.6,
        "proposalSelectionAdmissionFixRequireRealDetectedCandidateRows": True,
        "proposalSelectionAdmissionFixPreserveRepeatedAnchorGuard": True,
        "proposalSelectionAdmissionFixPreserveContinuityGuard": True,
        "proposalSelectionAdmissionFixMaxSeedPitchDistance": 8.0,
    },
    "source_robustness_shadow_promoted_v6_support_viability_admission_fix_v1": {
        "mode": TOUCHLINE_CANDIDATE_ADMISSION_REOPEN_MODE,
        "keepEvery": 0,
        "minRunLength": 10,
        "guardFrameCount": 0,
        "supportViabilityAdmissionFixEnabled": True,
        "supportViabilityAdmissionFixApproachFamily": "support_evidence_lift",
        "supportViabilityAdmissionFixTruthSeedPath": (
            "backend/storage/benchmark_suites/frozen-viable-baseline-slice-suite/"
            "promoted_v6_source_manifest_and_gold_truth_refresh_v1/"
            "gold_truth_bootstrap_attempt_v1/accepted_controlled_truth_seed.json"
        ),
        "supportViabilityAdmissionFixTargetSourceClipId": SOURCE_EDGE_SHARE_REPAIR_TARGET_CLIP,
        "supportViabilityAdmissionFixMaxProjectedEdgeShare": 0.6,
        "supportViabilityAdmissionFixRequireRealDetectedCandidateRows": True,
        "supportViabilityAdmissionFixPreserveRepeatedAnchorGuard": True,
        "supportViabilityAdmissionFixPreserveContinuityGuard": True,
    },
    "source_robustness_shadow_promoted_v6_support_viability_admission_fix_v2": {
        "mode": TOUCHLINE_CANDIDATE_ADMISSION_REOPEN_MODE,
        "keepEvery": 0,
        "minRunLength": 10,
        "guardFrameCount": 0,
        "supportViabilityAdmissionFixEnabled": True,
        "supportViabilityAdmissionFixApproachFamily": "source_space_support_neighborhood",
        "supportViabilityAdmissionFixTruthSeedPath": (
            "backend/storage/benchmark_suites/frozen-viable-baseline-slice-suite/"
            "promoted_v6_source_manifest_and_gold_truth_refresh_v1/"
            "gold_truth_bootstrap_attempt_v1/accepted_controlled_truth_seed.json"
        ),
        "supportViabilityAdmissionFixTargetSourceClipId": SOURCE_EDGE_SHARE_REPAIR_TARGET_CLIP,
        "supportViabilityAdmissionFixMaxProjectedEdgeShare": 0.6,
        "supportViabilityAdmissionFixRequireRealDetectedCandidateRows": True,
        "supportViabilityAdmissionFixPreserveRepeatedAnchorGuard": True,
        "supportViabilityAdmissionFixPreserveContinuityGuard": True,
    },
    "source_robustness_shadow_promoted_v6_support_viability_admission_fix_v3": {
        "mode": TOUCHLINE_CANDIDATE_ADMISSION_REOPEN_MODE,
        "keepEvery": 0,
        "minRunLength": 10,
        "guardFrameCount": 0,
        "supportViabilityAdmissionFixEnabled": True,
        "supportViabilityAdmissionFixApproachFamily": "viability_neutral_seed_window",
        "supportViabilityAdmissionFixTruthSeedPath": (
            "backend/storage/benchmark_suites/frozen-viable-baseline-slice-suite/"
            "promoted_v6_source_manifest_and_gold_truth_refresh_v1/"
            "gold_truth_bootstrap_attempt_v1/accepted_controlled_truth_seed.json"
        ),
        "supportViabilityAdmissionFixTargetSourceClipId": SOURCE_EDGE_SHARE_REPAIR_TARGET_CLIP,
        "supportViabilityAdmissionFixMaxProjectedEdgeShare": 0.6,
        "supportViabilityAdmissionFixRequireRealDetectedCandidateRows": True,
        "supportViabilityAdmissionFixPreserveRepeatedAnchorGuard": True,
        "supportViabilityAdmissionFixPreserveContinuityGuard": True,
    },
    "source_robustness_shadow_promoted_v6_proposal_crop_geometry_fix_v1": {
        "mode": TOUCHLINE_CANDIDATE_ADMISSION_REOPEN_MODE,
        "keepEvery": 0,
        "minRunLength": 10,
        "guardFrameCount": 0,
        "proposalCropGeometryFixEnabled": True,
        "proposalCropGeometryFixTruthSeedPath": (
            "backend/storage/benchmark_suites/frozen-viable-baseline-slice-suite/"
            "promoted_v6_source_manifest_and_gold_truth_refresh_v1/"
            "gold_truth_bootstrap_attempt_v1/accepted_controlled_truth_seed.json"
        ),
        "proposalCropGeometryFixTargetSourceClipId": SOURCE_EDGE_SHARE_REPAIR_TARGET_CLIP,
        "proposalCropGeometryFixUseTruthSeedRowsAsProposalAnchors": True,
        "proposalCropGeometryFixMaxWindowsPerFrame": 4,
        "proposalCropGeometryFixMinSeedWindowFrames": 78,
        "proposalCropGeometryFixRetryScales": [1600, 960, 1920],
    },
    "source_robustness_shadow_promoted_v6_proposal_crop_geometry_fix_v2": {
        "mode": TOUCHLINE_CANDIDATE_ADMISSION_REOPEN_MODE,
        "keepEvery": 0,
        "minRunLength": 10,
        "guardFrameCount": 0,
        "proposalCropGeometryFixEnabled": True,
        "proposalCropGeometryFixTruthSeedPath": (
            "backend/storage/benchmark_suites/frozen-viable-baseline-slice-suite/"
            "promoted_v6_source_manifest_and_gold_truth_refresh_v1/"
            "gold_truth_bootstrap_attempt_v1/accepted_controlled_truth_seed.json"
        ),
        "proposalCropGeometryFixTargetSourceClipId": SOURCE_EDGE_SHARE_REPAIR_TARGET_CLIP,
        "proposalCropGeometryFixUseTruthSeedRowsAsProposalAnchors": True,
        "proposalCropGeometryFixMaxWindowsPerFrame": 4,
        "proposalCropGeometryFixMinSeedWindowFrames": 78,
        "proposalCropGeometryFixRetryScales": [1600, 960, 1920],
        "proposalCropGeometryFixCropWidthRatio": 0.5,
        "proposalCropGeometryFixCropHeightRatio": 0.5,
        "proposalCropGeometryFixCropPaddingPx": 80,
    },
    "source_robustness_shadow_promoted_v6_proposal_crop_geometry_fix_v3": {
        "mode": TOUCHLINE_CANDIDATE_ADMISSION_REOPEN_MODE,
        "keepEvery": 0,
        "minRunLength": 10,
        "guardFrameCount": 0,
        "proposalCropGeometryFixEnabled": True,
        "proposalCropGeometryFixTruthSeedPath": (
            "backend/storage/benchmark_suites/frozen-viable-baseline-slice-suite/"
            "promoted_v6_source_manifest_and_gold_truth_refresh_v1/"
            "gold_truth_bootstrap_attempt_v1/accepted_controlled_truth_seed.json"
        ),
        "proposalCropGeometryFixTargetSourceClipId": SOURCE_EDGE_SHARE_REPAIR_TARGET_CLIP,
        "proposalCropGeometryFixUseTruthSeedRowsAsProposalAnchors": True,
        "proposalCropGeometryFixMaxWindowsPerFrame": 4,
        "proposalCropGeometryFixMinSeedWindowFrames": 78,
        "proposalCropGeometryFixRetryScales": [1600, 960, 1920],
        "proposalCropGeometryFixCropWidthRatio": 0.5,
        "proposalCropGeometryFixCropHeightRatio": 0.5,
        "proposalCropGeometryFixCropPaddingPx": 80,
        "supportViabilityAdmissionFixEnabled": True,
        "supportViabilityAdmissionFixApproachFamily": "viability_neutral_seed_window",
        "supportViabilityAdmissionFixTruthSeedPath": (
            "backend/storage/benchmark_suites/frozen-viable-baseline-slice-suite/"
            "promoted_v6_source_manifest_and_gold_truth_refresh_v1/"
            "gold_truth_bootstrap_attempt_v1/accepted_controlled_truth_seed.json"
        ),
        "supportViabilityAdmissionFixTargetSourceClipId": SOURCE_EDGE_SHARE_REPAIR_TARGET_CLIP,
        "supportViabilityAdmissionFixMaxProjectedEdgeShare": 0.6,
        "supportViabilityAdmissionFixRequireRealDetectedCandidateRows": True,
        "supportViabilityAdmissionFixPreserveRepeatedAnchorGuard": True,
        "supportViabilityAdmissionFixPreserveContinuityGuard": True,
    },
    "source_robustness_shadow_promoted_v6_selection_segment_viability_fix_v1": {
        "mode": TOUCHLINE_CANDIDATE_ADMISSION_REOPEN_MODE,
        "keepEvery": 0,
        "minRunLength": 10,
        "guardFrameCount": 0,
        "proposalCropGeometryFixEnabled": True,
        "proposalCropGeometryFixTruthSeedPath": (
            "backend/storage/benchmark_suites/frozen-viable-baseline-slice-suite/"
            "promoted_v6_source_manifest_and_gold_truth_refresh_v1/"
            "gold_truth_bootstrap_attempt_v1/accepted_controlled_truth_seed.json"
        ),
        "proposalCropGeometryFixTargetSourceClipId": SOURCE_EDGE_SHARE_REPAIR_TARGET_CLIP,
        "proposalCropGeometryFixUseTruthSeedRowsAsProposalAnchors": True,
        "proposalCropGeometryFixMaxWindowsPerFrame": 4,
        "proposalCropGeometryFixMinSeedWindowFrames": 78,
        "proposalCropGeometryFixRetryScales": [1600, 960, 1920],
        "proposalCropGeometryFixCropWidthRatio": 0.5,
        "proposalCropGeometryFixCropHeightRatio": 0.5,
        "proposalCropGeometryFixCropPaddingPx": 80,
        "selectionSegmentViabilityFixEnabled": True,
        "selectionSegmentViabilityFixTargetSourceClipId": SOURCE_EDGE_SHARE_REPAIR_TARGET_CLIP,
        "selectionSegmentViabilityFixMinSegmentFrames": 3,
        "selectionSegmentViabilityFixMaxProjectedEdgeShare": 0.6,
        "selectionSegmentViabilityFixRequireRealDetectedCandidateRows": True,
        "selectionSegmentViabilityFixRequireProposalLineage": True,
        "selectionSegmentViabilityFixPreserveRepeatedAnchorGuard": True,
    },
    "source_robustness_shadow_promoted_v6_reviewed_positive_proposal_generation_fix_v1": {
        "mode": TOUCHLINE_CANDIDATE_ADMISSION_REOPEN_MODE,
        "keepEvery": 0,
        "minRunLength": 10,
        "guardFrameCount": 0,
        "reviewedPositiveProposalGenerationFixEnabled": True,
        "reviewedPositiveAnchorSeedPath": (
            "backend/storage/benchmark_suites/frozen-viable-baseline-slice-suite/"
            "reviewed_positive_proposal_generation_fix_v1/reviewed_positive_anchor_seed.json"
        ),
        "reviewedPositiveProposalGenerationFixTargetSourceClipId": SOURCE_EDGE_SHARE_REPAIR_TARGET_CLIP,
        "reviewedPositiveProposalGenerationFixMaxWindowsPerFrame": 3,
        "reviewedPositiveProposalGenerationFixRetryScales": [1600, 960, 1920],
        "reviewedPositiveProposalGenerationFixRequireRealDetectedCandidateRows": True,
        "reviewedPositiveProposalGenerationFixCropWidthRatio": 0.35,
        "reviewedPositiveProposalGenerationFixCropHeightRatio": 0.35,
        "reviewedPositiveProposalGenerationFixCropPaddingPx": 24,
    },
    "source_robustness_shadow_promoted_v6_reviewed_positive_crop_geometry_scale_fix_v1": {
        "mode": UNIFORM_EDGE_RUN_THIN_MODE,
        "keepEvery": 0,
        "minRunLength": 10,
        "guardFrameCount": 0,
        "reviewedPositiveProposalGenerationFixEnabled": True,
        "reviewedPositiveAnchorSeedPath": (
            "backend/storage/benchmark_suites/frozen-viable-baseline-slice-suite/"
            "reviewed_positive_proposal_generation_fix_v1/reviewed_positive_anchor_seed.json"
        ),
        "reviewedPositiveProposalGenerationFixTargetSourceClipId": SOURCE_EDGE_SHARE_REPAIR_TARGET_CLIP,
        "reviewedPositiveProposalGenerationFixMaxWindowsPerFrame": 3,
        "reviewedPositiveProposalGenerationFixRetryScales": [640, 960, 1600],
        "reviewedPositiveProposalGenerationFixRequireRealDetectedCandidateRows": True,
        "reviewedPositiveProposalGenerationFixContextRatios": [1.0, 4.0, 8.0],
        "reviewedPositiveProposalGenerationFixMinCropSizePx": 64,
        "reviewedPositiveProposalGenerationFixCropWidthRatio": 0.35,
        "reviewedPositiveProposalGenerationFixCropHeightRatio": 0.35,
        "reviewedPositiveProposalGenerationFixCropPaddingPx": 24,
    },
    "source_robustness_shadow_promoted_v6_reviewed_positive_crop_geometry_scale_fix_v2": {
        "mode": UNIFORM_EDGE_RUN_THIN_MODE,
        "keepEvery": 0,
        "minRunLength": 10,
        "guardFrameCount": 0,
        "reviewedPositiveProposalGenerationFixEnabled": True,
        "reviewedPositiveAnchorSeedPath": (
            "backend/storage/benchmark_suites/frozen-viable-baseline-slice-suite/"
            "reviewed_positive_proposal_generation_fix_v1/reviewed_positive_anchor_seed.json"
        ),
        "reviewedPositiveProposalGenerationFixTargetSourceClipId": SOURCE_EDGE_SHARE_REPAIR_TARGET_CLIP,
        "reviewedPositiveProposalGenerationFixMaxWindowsPerFrame": 3,
        "reviewedPositiveProposalGenerationFixRetryScales": [1600, 640, 960],
        "reviewedPositiveProposalGenerationFixRequireRealDetectedCandidateRows": True,
        "reviewedPositiveProposalGenerationFixUseAuditBestAttempts": True,
        "reviewedPositiveProposalGenerationFixAuditMatrixPath": (
            "backend/storage/benchmark_suites/frozen-viable-baseline-slice-suite/"
            "reviewed_positive_crop_reinference_audit_v1/"
            "reviewed_positive_crop_reinference_matrix.json"
        ),
        "reviewedPositiveProposalGenerationFixContextRatios": [1.0, 8.0, 4.0],
        "reviewedPositiveProposalGenerationFixMinCropSizePx": 64,
        "reviewedPositiveProposalGenerationFixCropWidthRatio": 0.35,
        "reviewedPositiveProposalGenerationFixCropHeightRatio": 0.35,
        "reviewedPositiveProposalGenerationFixCropPaddingPx": 24,
    },
    "source_robustness_shadow_promoted_v6_reviewed_positive_selected_segment_profile_v1": {
        "mode": UNIFORM_EDGE_RUN_THIN_MODE,
        "keepEvery": 0,
        "minRunLength": 10,
        "guardFrameCount": 0,
        "reviewedPositiveProposalGenerationFixEnabled": True,
        "reviewedPositiveAnchorSeedPath": (
            "backend/storage/benchmark_suites/frozen-viable-baseline-slice-suite/"
            "reviewed_positive_proposal_generation_fix_v1/reviewed_positive_anchor_seed.json"
        ),
        "reviewedPositiveProposalGenerationFixTargetSourceClipId": SOURCE_EDGE_SHARE_REPAIR_TARGET_CLIP,
        "reviewedPositiveProposalGenerationFixMaxWindowsPerFrame": 3,
        "reviewedPositiveProposalGenerationFixRetryScales": [1600, 640, 960],
        "reviewedPositiveProposalGenerationFixRequireRealDetectedCandidateRows": True,
        "reviewedPositiveProposalGenerationFixUseAuditBestAttempts": True,
        "reviewedPositiveProposalGenerationFixAuditMatrixPath": (
            "backend/storage/benchmark_suites/frozen-viable-baseline-slice-suite/"
            "reviewed_positive_crop_reinference_audit_v1/"
            "reviewed_positive_crop_reinference_matrix.json"
        ),
        "reviewedPositiveProposalGenerationFixContextRatios": [1.0, 8.0, 4.0],
        "reviewedPositiveProposalGenerationFixMinCropSizePx": 64,
        "reviewedPositiveProposalGenerationFixCropWidthRatio": 0.35,
        "reviewedPositiveProposalGenerationFixCropHeightRatio": 0.35,
        "reviewedPositiveProposalGenerationFixCropPaddingPx": 24,
        "reviewedPositiveSelectedSegmentFixEnabled": True,
        "reviewedPositiveSelectedSegmentFixTargetSourceClipId": SOURCE_EDGE_SHARE_REPAIR_TARGET_CLIP,
        "reviewedPositiveSelectedSegmentFixRequiredProposalWindowKindPrefix": "reviewed_positive_",
        "reviewedPositiveSelectedSegmentFixMinSegmentFrames": 5,
        "reviewedPositiveSelectedSegmentFixMaxProjectedEdgeShare": 0.6,
        "reviewedPositiveSelectedSegmentFixRequireRealDetectedCandidateRows": True,
        "reviewedPositiveSelectedSegmentFixPreserveRepeatedAnchorGuard": True,
        "reviewedPositiveSelectedSegmentFixPreserveContinuityGuard": True,
    },
    "source_robustness_shadow_promoted_v6_reviewed_positive_edge_share_gate_override_v1": {
        "mode": UNIFORM_EDGE_RUN_THIN_MODE,
        "keepEvery": 0,
        "minRunLength": 10,
        "guardFrameCount": 0,
        "reviewedPositiveProposalGenerationFixEnabled": True,
        "reviewedPositiveAnchorSeedPath": (
            "backend/storage/benchmark_suites/frozen-viable-baseline-slice-suite/"
            "reviewed_positive_proposal_generation_fix_v1/reviewed_positive_anchor_seed.json"
        ),
        "reviewedPositiveProposalGenerationFixTargetSourceClipId": SOURCE_EDGE_SHARE_REPAIR_TARGET_CLIP,
        "reviewedPositiveProposalGenerationFixMaxWindowsPerFrame": 3,
        "reviewedPositiveProposalGenerationFixRetryScales": [1600, 640, 960],
        "reviewedPositiveProposalGenerationFixRequireRealDetectedCandidateRows": True,
        "reviewedPositiveProposalGenerationFixUseAuditBestAttempts": True,
        "reviewedPositiveProposalGenerationFixAuditMatrixPath": (
            "backend/storage/benchmark_suites/frozen-viable-baseline-slice-suite/"
            "reviewed_positive_crop_reinference_audit_v1/"
            "reviewed_positive_crop_reinference_matrix.json"
        ),
        "reviewedPositiveProposalGenerationFixContextRatios": [1.0, 8.0, 4.0],
        "reviewedPositiveProposalGenerationFixMinCropSizePx": 64,
        "reviewedPositiveProposalGenerationFixCropWidthRatio": 0.35,
        "reviewedPositiveProposalGenerationFixCropHeightRatio": 0.35,
        "reviewedPositiveProposalGenerationFixCropPaddingPx": 24,
        "reviewedPositiveSelectedSegmentFixEnabled": True,
        "reviewedPositiveSelectedSegmentFixTargetSourceClipId": SOURCE_EDGE_SHARE_REPAIR_TARGET_CLIP,
        "reviewedPositiveSelectedSegmentFixRequiredProposalWindowKindPrefix": "reviewed_positive_",
        "reviewedPositiveSelectedSegmentFixMinSegmentFrames": 5,
        "reviewedPositiveSelectedSegmentFixMaxProjectedEdgeShare": 0.6,
        "reviewedPositiveSelectedSegmentFixRequireRealDetectedCandidateRows": True,
        "reviewedPositiveSelectedSegmentFixPreserveRepeatedAnchorGuard": True,
        "reviewedPositiveSelectedSegmentFixPreserveContinuityGuard": True,
        "reviewedPositiveSelectedSegmentFixIgnoreEdgeShareGate": True,
    },
    "source_robustness_shadow_promoted_v6_reviewed_positive_acceptance_profile_v1": {
        "mode": UNIFORM_EDGE_RUN_THIN_MODE,
        "keepEvery": 0,
        "minRunLength": 10,
        "guardFrameCount": 0,
        "reviewedPositiveProposalGenerationFixEnabled": True,
        "reviewedPositiveAnchorSeedPath": (
            "backend/storage/benchmark_suites/frozen-viable-baseline-slice-suite/"
            "reviewed_positive_proposal_generation_fix_v1/reviewed_positive_anchor_seed.json"
        ),
        "reviewedPositiveProposalGenerationFixTargetSourceClipId": SOURCE_EDGE_SHARE_REPAIR_TARGET_CLIP,
        "reviewedPositiveProposalGenerationFixMaxWindowsPerFrame": 3,
        "reviewedPositiveProposalGenerationFixRetryScales": [1600, 640, 960],
        "reviewedPositiveProposalGenerationFixRequireRealDetectedCandidateRows": True,
        "reviewedPositiveProposalGenerationFixUseAuditBestAttempts": True,
        "reviewedPositiveProposalGenerationFixAuditMatrixPath": (
            "backend/storage/benchmark_suites/frozen-viable-baseline-slice-suite/"
            "reviewed_positive_crop_reinference_audit_v1/"
            "reviewed_positive_crop_reinference_matrix.json"
        ),
        "reviewedPositiveProposalGenerationFixContextRatios": [1.0, 8.0, 4.0],
        "reviewedPositiveProposalGenerationFixMinCropSizePx": 64,
        "reviewedPositiveProposalGenerationFixCropWidthRatio": 0.35,
        "reviewedPositiveProposalGenerationFixCropHeightRatio": 0.35,
        "reviewedPositiveProposalGenerationFixCropPaddingPx": 24,
        "reviewedPositiveSelectedSegmentFixEnabled": True,
        "reviewedPositiveSelectedSegmentFixTargetSourceClipId": SOURCE_EDGE_SHARE_REPAIR_TARGET_CLIP,
        "reviewedPositiveSelectedSegmentFixRequiredProposalWindowKindPrefix": "reviewed_positive_",
        "reviewedPositiveSelectedSegmentFixMinSegmentFrames": 5,
        "reviewedPositiveSelectedSegmentFixMaxProjectedEdgeShare": 0.6,
        "reviewedPositiveSelectedSegmentFixRequireRealDetectedCandidateRows": True,
        "reviewedPositiveSelectedSegmentFixPreserveRepeatedAnchorGuard": True,
        "reviewedPositiveSelectedSegmentFixPreserveContinuityGuard": True,
        "reviewedPositiveSelectedSegmentFixIgnoreEdgeShareGate": True,
        "reviewedPositiveAcceptanceProfileEnabled": True,
        "reviewedPositiveAcceptanceProfileTargetSourceClipId": SOURCE_EDGE_SHARE_REPAIR_TARGET_CLIP,
        "reviewedPositiveAcceptanceProfileRequiredProposalWindowKindPrefix": "reviewed_positive_",
        "reviewedPositiveAcceptanceProfileMinSelectedFrames": 5,
        "reviewedPositiveAcceptanceProfileRequireRealDetectedRows": True,
        "reviewedPositiveAcceptanceProfilePreserveRepeatedAnchorGuard": True,
        "reviewedPositiveAcceptanceProfilePreserveContinuityGuard": True,
    },
    "source_robustness_shadow_promoted_v6_reviewed_positive_residual_proposal_generation_fix_v1": {
        "mode": UNIFORM_EDGE_RUN_THIN_MODE,
        "keepEvery": 0,
        "minRunLength": 10,
        "guardFrameCount": 0,
        "reviewedPositiveProposalGenerationFixEnabled": True,
        "reviewedPositiveAnchorSeedPath": (
            "backend/storage/benchmark_suites/frozen-viable-baseline-slice-suite/"
            "reviewed_positive_proposal_generation_fix_v1/reviewed_positive_anchor_seed.json"
        ),
        "reviewedPositiveProposalGenerationFixTargetSourceClipId": SOURCE_EDGE_SHARE_REPAIR_TARGET_CLIP,
        "reviewedPositiveProposalGenerationFixMaxWindowsPerFrame": 5,
        "reviewedPositiveProposalGenerationFixRetryScales": [640, 960, 1280, 1600, 1920],
        "reviewedPositiveProposalGenerationFixRequireRealDetectedCandidateRows": True,
        "reviewedPositiveProposalGenerationFixUseAuditBestAttempts": True,
        "reviewedPositiveProposalGenerationFixAuditMatrixPath": (
            "backend/storage/benchmark_suites/frozen-viable-baseline-slice-suite/"
            "reviewed_positive_crop_reinference_audit_v1/"
            "reviewed_positive_crop_reinference_matrix.json"
        ),
        "reviewedPositiveProposalGenerationFixContextRatios": [0.75, 1.0, 2.0, 4.0, 8.0, 12.0],
        "reviewedPositiveProposalGenerationFixMinCropSizePx": 64,
        "reviewedPositiveProposalGenerationFixCropWidthRatio": 0.35,
        "reviewedPositiveProposalGenerationFixCropHeightRatio": 0.35,
        "reviewedPositiveProposalGenerationFixCropPaddingPx": 24,
        "reviewedPositiveProposalGenerationFixExcludeFrameIds": [250, 255, 260, 265, 270],
        "reviewedPositiveSelectedSegmentFixEnabled": True,
        "reviewedPositiveSelectedSegmentFixTargetSourceClipId": SOURCE_EDGE_SHARE_REPAIR_TARGET_CLIP,
        "reviewedPositiveSelectedSegmentFixRequiredProposalWindowKindPrefix": "reviewed_positive_",
        "reviewedPositiveSelectedSegmentFixMinSegmentFrames": 5,
        "reviewedPositiveSelectedSegmentFixMaxProjectedEdgeShare": 0.6,
        "reviewedPositiveSelectedSegmentFixRequireRealDetectedCandidateRows": True,
        "reviewedPositiveSelectedSegmentFixPreserveRepeatedAnchorGuard": True,
        "reviewedPositiveSelectedSegmentFixPreserveContinuityGuard": True,
        "reviewedPositiveSelectedSegmentFixIgnoreEdgeShareGate": True,
        "reviewedPositiveAcceptanceProfileEnabled": True,
        "reviewedPositiveAcceptanceProfileTargetSourceClipId": SOURCE_EDGE_SHARE_REPAIR_TARGET_CLIP,
        "reviewedPositiveAcceptanceProfileRequiredProposalWindowKindPrefix": "reviewed_positive_",
        "reviewedPositiveAcceptanceProfileMinSelectedFrames": 5,
        "reviewedPositiveAcceptanceProfileRequireRealDetectedRows": True,
        "reviewedPositiveAcceptanceProfilePreserveRepeatedAnchorGuard": True,
        "reviewedPositiveAcceptanceProfilePreserveContinuityGuard": True,
    },
    "source_robustness_shadow_promoted_v6_reviewed_positive_residual_proposal_generation_fix_v2": {
        "mode": UNIFORM_EDGE_RUN_THIN_MODE,
        "keepEvery": 0,
        "minRunLength": 10,
        "guardFrameCount": 0,
        "reviewedPositiveProposalGenerationFixEnabled": True,
        "reviewedPositiveAnchorSeedPath": (
            "backend/storage/benchmark_suites/frozen-viable-baseline-slice-suite/"
            "reviewed_positive_proposal_generation_fix_v1/reviewed_positive_anchor_seed.json"
        ),
        "reviewedPositiveProposalGenerationFixTargetSourceClipId": SOURCE_EDGE_SHARE_REPAIR_TARGET_CLIP,
        "reviewedPositiveProposalGenerationFixMaxWindowsPerFrame": 5,
        "reviewedPositiveProposalGenerationFixRetryScales": [640, 960, 1280, 1600, 1920],
        "reviewedPositiveProposalGenerationFixRequireRealDetectedCandidateRows": True,
        "reviewedPositiveProposalGenerationFixUseAuditBestAttempts": True,
        "reviewedPositiveProposalGenerationFixAuditMatrixPath": (
            "backend/storage/benchmark_suites/frozen-viable-baseline-slice-suite/"
            "reviewed_positive_crop_reinference_audit_v1/"
            "reviewed_positive_crop_reinference_matrix.json"
        ),
        "reviewedPositiveProposalGenerationFixContextRatios": [0.75, 1.0, 2.0, 4.0, 8.0, 12.0],
        "reviewedPositiveProposalGenerationFixMinCropSizePx": 64,
        "reviewedPositiveProposalGenerationFixCropWidthRatio": 0.35,
        "reviewedPositiveProposalGenerationFixCropHeightRatio": 0.35,
        "reviewedPositiveProposalGenerationFixCropPaddingPx": 24,
        "reviewedPositiveSelectedSegmentFixEnabled": True,
        "reviewedPositiveSelectedSegmentFixTargetSourceClipId": SOURCE_EDGE_SHARE_REPAIR_TARGET_CLIP,
        "reviewedPositiveSelectedSegmentFixRequiredProposalWindowKindPrefix": "reviewed_positive_",
        "reviewedPositiveSelectedSegmentFixMinSegmentFrames": 5,
        "reviewedPositiveSelectedSegmentFixMaxProjectedEdgeShare": 0.6,
        "reviewedPositiveSelectedSegmentFixRequireRealDetectedCandidateRows": True,
        "reviewedPositiveSelectedSegmentFixPreserveRepeatedAnchorGuard": True,
        "reviewedPositiveSelectedSegmentFixPreserveContinuityGuard": True,
        "reviewedPositiveSelectedSegmentFixIgnoreEdgeShareGate": True,
        "reviewedPositiveAcceptanceProfileEnabled": True,
        "reviewedPositiveAcceptanceProfileTargetSourceClipId": SOURCE_EDGE_SHARE_REPAIR_TARGET_CLIP,
        "reviewedPositiveAcceptanceProfileRequiredProposalWindowKindPrefix": "reviewed_positive_",
        "reviewedPositiveAcceptanceProfileMinSelectedFrames": 5,
        "reviewedPositiveAcceptanceProfileRequireRealDetectedRows": True,
        "reviewedPositiveAcceptanceProfilePreserveRepeatedAnchorGuard": True,
        "reviewedPositiveAcceptanceProfilePreserveContinuityGuard": True,
    },
    "source_robustness_shadow_promoted_v6_residual_segment_selection_microfix_v1": {
        "mode": UNIFORM_EDGE_RUN_THIN_MODE,
        "keepEvery": 0,
        "minRunLength": 10,
        "guardFrameCount": 0,
        "reviewedPositiveProposalGenerationFixEnabled": True,
        "reviewedPositiveAnchorSeedPath": (
            "backend/storage/benchmark_suites/frozen-viable-baseline-slice-suite/"
            "reviewed_positive_proposal_generation_fix_v1/reviewed_positive_anchor_seed.json"
        ),
        "reviewedPositiveProposalGenerationFixTargetSourceClipId": SOURCE_EDGE_SHARE_REPAIR_TARGET_CLIP,
        "reviewedPositiveProposalGenerationFixMaxWindowsPerFrame": 5,
        "reviewedPositiveProposalGenerationFixRetryScales": [640, 960, 1280, 1600, 1920],
        "reviewedPositiveProposalGenerationFixRequireRealDetectedCandidateRows": True,
        "reviewedPositiveProposalGenerationFixUseAuditBestAttempts": True,
        "reviewedPositiveProposalGenerationFixAuditMatrixPath": (
            "backend/storage/benchmark_suites/frozen-viable-baseline-slice-suite/"
            "reviewed_positive_crop_reinference_audit_v1/"
            "reviewed_positive_crop_reinference_matrix.json"
        ),
        "reviewedPositiveProposalGenerationFixContextRatios": [0.75, 1.0, 2.0, 4.0, 8.0, 12.0],
        "reviewedPositiveProposalGenerationFixMinCropSizePx": 64,
        "reviewedPositiveProposalGenerationFixCropWidthRatio": 0.35,
        "reviewedPositiveProposalGenerationFixCropHeightRatio": 0.35,
        "reviewedPositiveProposalGenerationFixCropPaddingPx": 24,
        "reviewedPositiveSelectedSegmentFixEnabled": True,
        "reviewedPositiveSelectedSegmentFixTargetSourceClipId": SOURCE_EDGE_SHARE_REPAIR_TARGET_CLIP,
        "reviewedPositiveSelectedSegmentFixRequiredProposalWindowKindPrefix": "reviewed_positive_",
        "reviewedPositiveSelectedSegmentFixFrameIds": [305, 310, 315, 320],
        "reviewedPositiveSelectedSegmentFixMinSegmentFrames": 4,
        "reviewedPositiveSelectedSegmentFixMaxProjectedEdgeShare": 0.6,
        "reviewedPositiveSelectedSegmentFixRequireRealDetectedCandidateRows": True,
        "reviewedPositiveSelectedSegmentFixPreserveRepeatedAnchorGuard": True,
        "reviewedPositiveSelectedSegmentFixPreserveContinuityGuard": True,
        "reviewedPositiveSelectedSegmentFixIgnoreEdgeShareGate": True,
        "reviewedPositiveAcceptanceProfileEnabled": True,
        "reviewedPositiveAcceptanceProfileTargetSourceClipId": SOURCE_EDGE_SHARE_REPAIR_TARGET_CLIP,
        "reviewedPositiveAcceptanceProfileRequiredProposalWindowKindPrefix": "reviewed_positive_",
        "reviewedPositiveAcceptanceProfileMinSelectedFrames": 4,
        "reviewedPositiveAcceptanceProfileRequireRealDetectedRows": True,
        "reviewedPositiveAcceptanceProfilePreserveRepeatedAnchorGuard": True,
        "reviewedPositiveAcceptanceProfilePreserveContinuityGuard": True,
    },
    "source_robustness_shadow_promoted_v6_global_reachable_acceptance_probe_v1": {
        "mode": UNIFORM_EDGE_RUN_THIN_MODE,
        "keepEvery": 0,
        "minRunLength": 10,
        "guardFrameCount": 0,
        "reviewedPositiveProposalGenerationFixEnabled": True,
        "reviewedPositiveAnchorSeedPath": (
            "backend/storage/benchmark_suites/frozen-viable-baseline-slice-suite/"
            "reviewed_positive_proposal_generation_fix_v1/reviewed_positive_anchor_seed.json"
        ),
        "reviewedPositiveProposalGenerationFixTargetSourceClipId": SOURCE_EDGE_SHARE_REPAIR_TARGET_CLIP,
        "reviewedPositiveProposalGenerationFixMaxWindowsPerFrame": 5,
        "reviewedPositiveProposalGenerationFixRetryScales": [640, 960, 1280, 1600, 1920],
        "reviewedPositiveProposalGenerationFixRequireRealDetectedCandidateRows": True,
        "reviewedPositiveProposalGenerationFixUseAuditBestAttempts": True,
        "reviewedPositiveProposalGenerationFixAuditMatrixPath": (
            "backend/storage/benchmark_suites/frozen-viable-baseline-slice-suite/"
            "reviewed_positive_crop_reinference_audit_v1/"
            "reviewed_positive_crop_reinference_matrix.json"
        ),
        "reviewedPositiveProposalGenerationFixContextRatios": [0.75, 1.0, 2.0, 4.0, 8.0, 12.0],
        "reviewedPositiveProposalGenerationFixMinCropSizePx": 64,
        "reviewedPositiveProposalGenerationFixCropWidthRatio": 0.35,
        "reviewedPositiveProposalGenerationFixCropHeightRatio": 0.35,
        "reviewedPositiveProposalGenerationFixCropPaddingPx": 24,
        "reviewedPositiveSelectedSegmentFixEnabled": True,
        "reviewedPositiveSelectedSegmentFixTargetSourceClipId": SOURCE_EDGE_SHARE_REPAIR_TARGET_CLIP,
        "reviewedPositiveSelectedSegmentFixRequiredProposalWindowKindPrefix": "reviewed_positive_",
        "reviewedPositiveSelectedSegmentFixFrameIds": [255, 260, 265, 270, 275, 280, 285],
        "reviewedPositiveSelectedSegmentFixMinSegmentFrames": 7,
        "reviewedPositiveSelectedSegmentFixMaxProjectedEdgeShare": 0.6,
        "reviewedPositiveSelectedSegmentFixRequireRealDetectedCandidateRows": True,
        "reviewedPositiveSelectedSegmentFixPreserveRepeatedAnchorGuard": True,
        "reviewedPositiveSelectedSegmentFixPreserveContinuityGuard": True,
        "reviewedPositiveSelectedSegmentFixIgnoreEdgeShareGate": True,
        "reviewedPositiveAcceptanceProfileEnabled": True,
        "reviewedPositiveAcceptanceProfileTargetSourceClipId": SOURCE_EDGE_SHARE_REPAIR_TARGET_CLIP,
        "reviewedPositiveAcceptanceProfileRequiredProposalWindowKindPrefix": "reviewed_positive_",
        "reviewedPositiveAcceptanceProfileMinSelectedFrames": 7,
        "reviewedPositiveAcceptanceProfileRequireRealDetectedRows": True,
        "reviewedPositiveAcceptanceProfilePreserveRepeatedAnchorGuard": True,
        "reviewedPositiveAcceptanceProfilePreserveContinuityGuard": True,
    },
}

LEGACY_SOURCE_EDGE_SHARE_REPAIR_CONFIGS = {
    "source_robustness_shadow_edge_run_keep_every_3_min8": {
        "mode": UNIFORM_EDGE_RUN_THIN_MODE,
        "keepEvery": 3,
        "minRunLength": 8,
        "guardFrameCount": 0,
    },
    "source_robustness_shadow_edge_run_keep_every_4_min6": {
        "mode": UNIFORM_EDGE_RUN_THIN_MODE,
        "keepEvery": 4,
        "minRunLength": 6,
        "guardFrameCount": 0,
    },
}

SOURCE_EDGE_SHARE_REPAIR_CONFIGS = {
    **ACTIVE_SOURCE_EDGE_SHARE_REPAIR_CONFIGS,
    **SUPPORT_AWARE_SOURCE_EDGE_SHARE_REPAIR_CONFIGS,
    **TOUCHLINE_REPLACEMENT_SOURCE_EDGE_SHARE_REPAIR_CONFIGS,
    **TOUCHLINE_ACQUISITION_SOURCE_EDGE_SHARE_REPAIR_CONFIGS,
    **PROMOTED_V6_ADMISSION_WIDENING_SOURCE_EDGE_SHARE_REPAIR_CONFIGS,
    **LEGACY_SOURCE_EDGE_SHARE_REPAIR_CONFIGS,
}

ACTIVE_SOURCE_EDGE_SHARE_REPAIR_PROFILE_NAMES = tuple(ACTIVE_SOURCE_EDGE_SHARE_REPAIR_CONFIGS.keys())
SUPPORT_AWARE_SOURCE_EDGE_SHARE_REPAIR_PROFILE_NAMES = tuple(SUPPORT_AWARE_SOURCE_EDGE_SHARE_REPAIR_CONFIGS.keys())
TOUCHLINE_REPLACEMENT_SOURCE_EDGE_SHARE_REPAIR_PROFILE_NAMES = tuple(
    TOUCHLINE_REPLACEMENT_SOURCE_EDGE_SHARE_REPAIR_CONFIGS.keys()
)
TOUCHLINE_ACQUISITION_SOURCE_EDGE_SHARE_REPAIR_PROFILE_NAMES = tuple(
    TOUCHLINE_ACQUISITION_SOURCE_EDGE_SHARE_REPAIR_CONFIGS.keys()
)
PROMOTED_V6_ADMISSION_WIDENING_SOURCE_EDGE_SHARE_REPAIR_PROFILE_NAMES = tuple(
    PROMOTED_V6_ADMISSION_WIDENING_SOURCE_EDGE_SHARE_REPAIR_CONFIGS.keys()
)
SHADOW_SOURCE_EDGE_SHARE_REPAIR_PROFILE_NAMES = (
    ACTIVE_SOURCE_EDGE_SHARE_REPAIR_PROFILE_NAMES
    + SUPPORT_AWARE_SOURCE_EDGE_SHARE_REPAIR_PROFILE_NAMES
    + TOUCHLINE_REPLACEMENT_SOURCE_EDGE_SHARE_REPAIR_PROFILE_NAMES
    + TOUCHLINE_ACQUISITION_SOURCE_EDGE_SHARE_REPAIR_PROFILE_NAMES
    + PROMOTED_V6_ADMISSION_WIDENING_SOURCE_EDGE_SHARE_REPAIR_PROFILE_NAMES
)


def _normalize_admission_widening(config: dict[str, object], normalized: dict[str, object]) -> None:
        if bool(config.get("admissionWideningEnabled")):
            normalized["admissionWideningEnabled"] = True
            normalized["admissionWideningRequirePlayerSupport"] = bool(
                config.get("admissionWideningRequirePlayerSupport", True)
            )
            normalized["admissionWideningMaxProjectedEdgeShare"] = float(
                config.get("admissionWideningMaxProjectedEdgeShare", 0.6)
            )


def _normalize_baseline_guided_rescue(config: dict[str, object], normalized: dict[str, object]) -> None:
        if bool(config.get("baselineGuidedRescueEnabled")):
            normalized["baselineGuidedRescueEnabled"] = True
            normalized["baselineGuidedRescueMaxProjectedEdgeShare"] = float(
                config.get("baselineGuidedRescueMaxProjectedEdgeShare", 0.6)
            )


def _normalize_continuity_bridge_recovery(config: dict[str, object], normalized: dict[str, object]) -> None:
        if bool(config.get("continuityBridgeRecoveryEnabled")):
            normalized["continuityBridgeRecoveryEnabled"] = True
            normalized["continuityBridgeRecoveryMaxGapFrames"] = int(
                config.get("continuityBridgeRecoveryMaxGapFrames", 20)
            )
            normalized["continuityBridgeRecoveryMaxProjectedEdgeShare"] = float(
                config.get("continuityBridgeRecoveryMaxProjectedEdgeShare", 0.6)
            )
            normalized["continuityBridgeRecoveryRequireEndpointContinuity"] = bool(
                config.get("continuityBridgeRecoveryRequireEndpointContinuity", True)
            )


def _normalize_acceptance_support_gating(config: dict[str, object], normalized: dict[str, object]) -> None:
        if bool(config.get("acceptanceSupportGatingEnabled")):
            normalized["acceptanceSupportGatingEnabled"] = True
            normalized["acceptanceSupportGatingRequirePlayerSupport"] = bool(
                config.get("acceptanceSupportGatingRequirePlayerSupport", True)
            )
            normalized["acceptanceSupportGatingRequireSupportImprovement"] = bool(
                config.get("acceptanceSupportGatingRequireSupportImprovement", True)
            )
            normalized["acceptanceSupportGatingMaxProjectedEdgeShare"] = float(
                config.get("acceptanceSupportGatingMaxProjectedEdgeShare", 0.6)
            )
            normalized["acceptanceSupportGatingRequireRealDetectedCandidateRows"] = bool(
                config.get("acceptanceSupportGatingRequireRealDetectedCandidateRows", True)
            )


def _normalize_proposal_selection_admission_fix(config: dict[str, object], normalized: dict[str, object]) -> None:
        if bool(config.get("proposalSelectionAdmissionFixEnabled")):
            normalized["proposalSelectionAdmissionFixEnabled"] = True
            normalized["proposalSelectionAdmissionFixApproachFamily"] = str(
                config.get("proposalSelectionAdmissionFixApproachFamily") or "truth_seed_guided_selection"
            )
            normalized["proposalSelectionAdmissionFixTruthSeedPath"] = str(
                config.get("proposalSelectionAdmissionFixTruthSeedPath") or ""
            )
            normalized["proposalSelectionAdmissionFixTargetSourceClipId"] = str(
                config.get("proposalSelectionAdmissionFixTargetSourceClipId")
                or SOURCE_EDGE_SHARE_REPAIR_TARGET_CLIP
            )
            normalized["proposalSelectionAdmissionFixMaxProjectedEdgeShare"] = float(
                config.get("proposalSelectionAdmissionFixMaxProjectedEdgeShare", 0.6)
            )
            normalized["proposalSelectionAdmissionFixRequireRealDetectedCandidateRows"] = bool(
                config.get("proposalSelectionAdmissionFixRequireRealDetectedCandidateRows", True)
            )
            normalized["proposalSelectionAdmissionFixPreserveRepeatedAnchorGuard"] = bool(
                config.get("proposalSelectionAdmissionFixPreserveRepeatedAnchorGuard", True)
            )
            normalized["proposalSelectionAdmissionFixPreserveContinuityGuard"] = bool(
                config.get("proposalSelectionAdmissionFixPreserveContinuityGuard", True)
            )
            normalized["proposalSelectionAdmissionFixMaxSeedPitchDistance"] = float(
                config.get("proposalSelectionAdmissionFixMaxSeedPitchDistance", 8.0)
            )


def _normalize_support_viability_admission_fix(config: dict[str, object], normalized: dict[str, object]) -> None:
        if bool(config.get("supportViabilityAdmissionFixEnabled")):
            normalized["supportViabilityAdmissionFixEnabled"] = True
            normalized["supportViabilityAdmissionFixApproachFamily"] = str(
                config.get("supportViabilityAdmissionFixApproachFamily") or "support_evidence_lift"
            )
            normalized["supportViabilityAdmissionFixTruthSeedPath"] = str(
                config.get("supportViabilityAdmissionFixTruthSeedPath") or ""
            )
            normalized["supportViabilityAdmissionFixTargetSourceClipId"] = str(
                config.get("supportViabilityAdmissionFixTargetSourceClipId")
                or SOURCE_EDGE_SHARE_REPAIR_TARGET_CLIP
            )
            normalized["supportViabilityAdmissionFixMaxProjectedEdgeShare"] = float(
                config.get("supportViabilityAdmissionFixMaxProjectedEdgeShare", 0.6)
            )
            normalized["supportViabilityAdmissionFixRequireRealDetectedCandidateRows"] = bool(
                config.get("supportViabilityAdmissionFixRequireRealDetectedCandidateRows", True)
            )
            normalized["supportViabilityAdmissionFixPreserveRepeatedAnchorGuard"] = bool(
                config.get("supportViabilityAdmissionFixPreserveRepeatedAnchorGuard", True)
            )
            normalized["supportViabilityAdmissionFixPreserveContinuityGuard"] = bool(
                config.get("supportViabilityAdmissionFixPreserveContinuityGuard", True)
            )


def _normalize_proposal_crop_geometry_fix(config: dict[str, object], normalized: dict[str, object]) -> None:
        if bool(config.get("proposalCropGeometryFixEnabled")):
            normalized["proposalCropGeometryFixEnabled"] = True
            normalized["proposalCropGeometryFixTruthSeedPath"] = str(
                config.get("proposalCropGeometryFixTruthSeedPath") or ""
            )
            normalized["proposalCropGeometryFixTargetSourceClipId"] = str(
                config.get("proposalCropGeometryFixTargetSourceClipId")
                or SOURCE_EDGE_SHARE_REPAIR_TARGET_CLIP
            )
            normalized["proposalCropGeometryFixUseTruthSeedRowsAsProposalAnchors"] = bool(
                config.get("proposalCropGeometryFixUseTruthSeedRowsAsProposalAnchors", True)
            )
            normalized["proposalCropGeometryFixMaxWindowsPerFrame"] = int(
                config.get("proposalCropGeometryFixMaxWindowsPerFrame", 4)
            )
            normalized["proposalCropGeometryFixMinSeedWindowFrames"] = int(
                config.get("proposalCropGeometryFixMinSeedWindowFrames", 78)
            )
            normalized["proposalCropGeometryFixRetryScales"] = [
                int(scale) for scale in config.get("proposalCropGeometryFixRetryScales", [1600, 960, 1920])
            ]
            if "proposalCropGeometryFixCropWidthRatio" in config:
                normalized["proposalCropGeometryFixCropWidthRatio"] = float(
                    config.get("proposalCropGeometryFixCropWidthRatio")
                )
            if "proposalCropGeometryFixCropHeightRatio" in config:
                normalized["proposalCropGeometryFixCropHeightRatio"] = float(
                    config.get("proposalCropGeometryFixCropHeightRatio")
                )
            if "proposalCropGeometryFixCropPaddingPx" in config:
                normalized["proposalCropGeometryFixCropPaddingPx"] = int(
                    config.get("proposalCropGeometryFixCropPaddingPx")
                )


def _normalize_reviewed_positive_proposal_generation_fix(config: dict[str, object], normalized: dict[str, object]) -> None:
        if bool(config.get("reviewedPositiveProposalGenerationFixEnabled")):
            normalized["reviewedPositiveProposalGenerationFixEnabled"] = True
            normalized["reviewedPositiveAnchorSeedPath"] = str(
                config.get("reviewedPositiveAnchorSeedPath") or ""
            )
            normalized["reviewedPositiveProposalGenerationFixTargetSourceClipId"] = str(
                config.get("reviewedPositiveProposalGenerationFixTargetSourceClipId")
                or SOURCE_EDGE_SHARE_REPAIR_TARGET_CLIP
            )
            normalized["reviewedPositiveProposalGenerationFixMaxWindowsPerFrame"] = int(
                config.get("reviewedPositiveProposalGenerationFixMaxWindowsPerFrame", 3)
            )
            normalized["reviewedPositiveProposalGenerationFixRetryScales"] = [
                int(scale)
                for scale in config.get("reviewedPositiveProposalGenerationFixRetryScales", [1600, 960, 1920])
            ]
            if "reviewedPositiveProposalGenerationFixContextRatios" in config:
                normalized["reviewedPositiveProposalGenerationFixContextRatios"] = [
                    float(ratio)
                    for ratio in config.get("reviewedPositiveProposalGenerationFixContextRatios", [])
                ]
            if "reviewedPositiveProposalGenerationFixMinCropSizePx" in config:
                normalized["reviewedPositiveProposalGenerationFixMinCropSizePx"] = int(
                    config.get("reviewedPositiveProposalGenerationFixMinCropSizePx", 64)
                )
            if "reviewedPositiveProposalGenerationFixUseAuditBestAttempts" in config:
                normalized["reviewedPositiveProposalGenerationFixUseAuditBestAttempts"] = bool(
                    config.get("reviewedPositiveProposalGenerationFixUseAuditBestAttempts", False)
                )
            if "reviewedPositiveProposalGenerationFixAuditMatrixPath" in config:
                normalized["reviewedPositiveProposalGenerationFixAuditMatrixPath"] = str(
                    config.get("reviewedPositiveProposalGenerationFixAuditMatrixPath") or ""
                )
            if "reviewedPositiveProposalGenerationFixExcludeFrameIds" in config:
                normalized["reviewedPositiveProposalGenerationFixExcludeFrameIds"] = [
                    int(frame_id)
                    for frame_id in config.get("reviewedPositiveProposalGenerationFixExcludeFrameIds", [])
                ]
            normalized["reviewedPositiveProposalGenerationFixRequireRealDetectedCandidateRows"] = bool(
                config.get("reviewedPositiveProposalGenerationFixRequireRealDetectedCandidateRows", True)
            )
            normalized["reviewedPositiveProposalGenerationFixCropWidthRatio"] = float(
                config.get("reviewedPositiveProposalGenerationFixCropWidthRatio", 0.35)
            )
            normalized["reviewedPositiveProposalGenerationFixCropHeightRatio"] = float(
                config.get("reviewedPositiveProposalGenerationFixCropHeightRatio", 0.35)
            )
            normalized["reviewedPositiveProposalGenerationFixCropPaddingPx"] = int(
                config.get("reviewedPositiveProposalGenerationFixCropPaddingPx", 24)
            )


def _normalize_selection_segment_viability_fix(config: dict[str, object], normalized: dict[str, object]) -> None:
        if bool(config.get("selectionSegmentViabilityFixEnabled")):
            normalized["selectionSegmentViabilityFixEnabled"] = True
            normalized["selectionSegmentViabilityFixTargetSourceClipId"] = str(
                config.get("selectionSegmentViabilityFixTargetSourceClipId")
                or SOURCE_EDGE_SHARE_REPAIR_TARGET_CLIP
            )
            normalized["selectionSegmentViabilityFixMinSegmentFrames"] = int(
                config.get("selectionSegmentViabilityFixMinSegmentFrames", 3)
            )
            normalized["selectionSegmentViabilityFixMaxProjectedEdgeShare"] = float(
                config.get("selectionSegmentViabilityFixMaxProjectedEdgeShare", 0.6)
            )
            normalized["selectionSegmentViabilityFixRequireRealDetectedCandidateRows"] = bool(
                config.get("selectionSegmentViabilityFixRequireRealDetectedCandidateRows", True)
            )
            normalized["selectionSegmentViabilityFixRequireProposalLineage"] = bool(
                config.get("selectionSegmentViabilityFixRequireProposalLineage", True)
            )
            normalized["selectionSegmentViabilityFixPreserveRepeatedAnchorGuard"] = bool(
                config.get("selectionSegmentViabilityFixPreserveRepeatedAnchorGuard", True)
            )


def _normalize_reviewed_positive_selected_segment_fix(config: dict[str, object], normalized: dict[str, object]) -> None:
        if bool(config.get("reviewedPositiveSelectedSegmentFixEnabled")):
            normalized["reviewedPositiveSelectedSegmentFixEnabled"] = True
            normalized["reviewedPositiveSelectedSegmentFixTargetSourceClipId"] = str(
                config.get("reviewedPositiveSelectedSegmentFixTargetSourceClipId")
                or SOURCE_EDGE_SHARE_REPAIR_TARGET_CLIP
            )
            normalized["reviewedPositiveSelectedSegmentFixRequiredProposalWindowKindPrefix"] = str(
                config.get("reviewedPositiveSelectedSegmentFixRequiredProposalWindowKindPrefix")
                or "reviewed_positive_"
            )
            normalized["reviewedPositiveSelectedSegmentFixMinSegmentFrames"] = int(
                config.get("reviewedPositiveSelectedSegmentFixMinSegmentFrames", 5)
            )
            if "reviewedPositiveSelectedSegmentFixFrameIds" in config:
                normalized["reviewedPositiveSelectedSegmentFixFrameIds"] = [
                    int(frame_id)
                    for frame_id in config.get("reviewedPositiveSelectedSegmentFixFrameIds", [])
                ]
            normalized["reviewedPositiveSelectedSegmentFixMaxProjectedEdgeShare"] = float(
                config.get("reviewedPositiveSelectedSegmentFixMaxProjectedEdgeShare", 0.6)
            )
            normalized["reviewedPositiveSelectedSegmentFixRequireRealDetectedCandidateRows"] = bool(
                config.get("reviewedPositiveSelectedSegmentFixRequireRealDetectedCandidateRows", True)
            )
            normalized["reviewedPositiveSelectedSegmentFixPreserveRepeatedAnchorGuard"] = bool(
                config.get("reviewedPositiveSelectedSegmentFixPreserveRepeatedAnchorGuard", True)
            )
            normalized["reviewedPositiveSelectedSegmentFixPreserveContinuityGuard"] = bool(
                config.get("reviewedPositiveSelectedSegmentFixPreserveContinuityGuard", True)
            )
            normalized["reviewedPositiveSelectedSegmentFixIgnoreEdgeShareGate"] = bool(
                config.get("reviewedPositiveSelectedSegmentFixIgnoreEdgeShareGate", False)
            )


def _normalize_reviewed_positive_acceptance_profile(config: dict[str, object], normalized: dict[str, object]) -> None:
        if bool(config.get("reviewedPositiveAcceptanceProfileEnabled")):
            normalized["reviewedPositiveAcceptanceProfileEnabled"] = True
            normalized["reviewedPositiveAcceptanceProfileTargetSourceClipId"] = str(
                config.get("reviewedPositiveAcceptanceProfileTargetSourceClipId")
                or SOURCE_EDGE_SHARE_REPAIR_TARGET_CLIP
            )
            normalized["reviewedPositiveAcceptanceProfileRequiredProposalWindowKindPrefix"] = str(
                config.get("reviewedPositiveAcceptanceProfileRequiredProposalWindowKindPrefix")
                or "reviewed_positive_"
            )
            normalized["reviewedPositiveAcceptanceProfileMinSelectedFrames"] = int(
                config.get("reviewedPositiveAcceptanceProfileMinSelectedFrames", 5)
            )
            normalized["reviewedPositiveAcceptanceProfileRequireRealDetectedRows"] = bool(
                config.get("reviewedPositiveAcceptanceProfileRequireRealDetectedRows", True)
            )
            normalized["reviewedPositiveAcceptanceProfilePreserveRepeatedAnchorGuard"] = bool(
                config.get("reviewedPositiveAcceptanceProfilePreserveRepeatedAnchorGuard", True)
            )
            normalized["reviewedPositiveAcceptanceProfilePreserveContinuityGuard"] = bool(
                config.get("reviewedPositiveAcceptanceProfilePreserveContinuityGuard", True)
            )


def _normalized_repair_config(config: dict[str, object]) -> dict[str, object]:
    normalized = {
        "mode": str(config.get("mode") or UNIFORM_EDGE_RUN_THIN_MODE),
        "keepEvery": int(config["keepEvery"]),
        "minRunLength": int(config["minRunLength"]),
        "guardFrameCount": int(config.get("guardFrameCount") or 0),
    }
    _normalize_admission_widening(config, normalized)
    _normalize_baseline_guided_rescue(config, normalized)
    _normalize_continuity_bridge_recovery(config, normalized)
    _normalize_acceptance_support_gating(config, normalized)
    _normalize_proposal_selection_admission_fix(config, normalized)
    _normalize_support_viability_admission_fix(config, normalized)
    _normalize_proposal_crop_geometry_fix(config, normalized)
    _normalize_reviewed_positive_proposal_generation_fix(config, normalized)
    _normalize_selection_segment_viability_fix(config, normalized)
    _normalize_reviewed_positive_selected_segment_fix(config, normalized)
    _normalize_reviewed_positive_acceptance_profile(config, normalized)
    return normalized
def get_source_edge_share_repair_config(profile_name: str | None) -> dict[str, object] | None:
    if not isinstance(profile_name, str):
        return None
    normalized_profile_name = profile_name.strip()
    if not normalized_profile_name:
        return None
    config = SOURCE_EDGE_SHARE_REPAIR_CONFIGS.get(normalized_profile_name)
    if config is None:
        return None
    return _normalized_repair_config(config)


def active_source_edge_share_repair_configs() -> dict[str, dict[str, object]]:
    return {
        profile_name: _normalized_repair_config(config)
        for profile_name, config in ACTIVE_SOURCE_EDGE_SHARE_REPAIR_CONFIGS.items()
    }


def shadow_source_edge_share_repair_configs() -> dict[str, dict[str, object]]:
    return {
        profile_name: _normalized_repair_config(config)
        for profile_name, config in {
            **ACTIVE_SOURCE_EDGE_SHARE_REPAIR_CONFIGS,
            **SUPPORT_AWARE_SOURCE_EDGE_SHARE_REPAIR_CONFIGS,
            **TOUCHLINE_REPLACEMENT_SOURCE_EDGE_SHARE_REPAIR_CONFIGS,
            **TOUCHLINE_ACQUISITION_SOURCE_EDGE_SHARE_REPAIR_CONFIGS,
            **PROMOTED_V6_ADMISSION_WIDENING_SOURCE_EDGE_SHARE_REPAIR_CONFIGS,
        }.items()
    }
