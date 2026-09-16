# Recovery inventory

## Recovery summary

- Frozen inventory: 487 paths total — 30 modified, 14 deleted, and 443 untracked.
- Reconciliation: exactly two compact-status directory entries were reconciled one-for-one to `.vscode/settings.json` and `backend/review_ui/football_external_soccernet_detector_miss_review/index.html`.
- Active release truth: `detector_candidate_promotion.json` is the detector-promotion contract, and `promoted_touchline_detector_candidate.json` is the active v7.3 runtime-default registry consumed by runtime/workflow code; neither is proven regenerable.
- Retained artifact sizes, hashes, origins, and restore sources are in the [artifact manifest](artifact-manifest.json); paused-worktree evidence is in the [worktree salvage manifest](worktree-salvage-manifest.json).
- Warning: the 81 `unique_unresolved` salvage occurrences represent worktree-specific variants. Do not use them as a flat commit list; review the global unresolved variant matrix before choosing any variant.

Total paths: 487

## Inventory

| Path | Original status | Classification | Disposition | Commit group |
| --- | --- | --- | --- | --- |
| `.vscode/settings.json` | `??` | `editor_or_cache_material` | `review_before_ignore` | `local-material` |
| `SESSION-HANDOFF.md` | ` M` | `essential_release_truth` | `preserve_commit` | `release-truth` |
| `backend/app/main.py` | ` M` | `product_source` | `preserve_commit` | `product-source` |
| `backend/app/match_bundle.py` | `??` | `product_source` | `preserve_commit` | `product-source` |
| `backend/app/proof_runtime.py` | ` M` | `product_source` | `preserve_commit` | `product-source` |
| `backend/app/runpod.py` | ` M` | `product_source` | `preserve_commit` | `product-source` |
| `backend/app/runpod_worker.py` | ` M` | `product_source` | `preserve_commit` | `product-source` |
| `backend/review_ui/football_external_soccernet_detector_miss_review/index.html` | `??` | `manual_review` | `manual_review` | `manual-review` |
| `backend/runpod_handler/handler.py` | ` M` | `product_source` | `preserve_commit` | `product-source` |
| `backend/scripts/football_external_real_eval_chain_common.py` | `??` | `reusable_workflow` | `preserve_commit` | `workflow` |
| `backend/scripts/run_canonical_match_bundle_export.py` | `??` | `one_shot_batch_entrypoint` | `preserve_or_archive` | `one-shot-batches` |
| `backend/scripts/run_football_external_benchmark_bounded_execution_smoke.py` | `??` | `one_shot_batch_entrypoint` | `preserve_or_archive` | `one-shot-batches` |
| `backend/scripts/run_football_external_benchmark_bounded_real_execution.py` | `??` | `one_shot_batch_entrypoint` | `preserve_or_archive` | `one-shot-batches` |
| `backend/scripts/run_football_external_benchmark_dataset_governance_plan.py` | `??` | `one_shot_batch_entrypoint` | `preserve_or_archive` | `one-shot-batches` |
| `backend/scripts/run_football_external_benchmark_execution_approval.py` | `??` | `one_shot_batch_entrypoint` | `preserve_or_archive` | `one-shot-batches` |
| `backend/scripts/run_football_external_benchmark_harness_prep.py` | ` M` | `one_shot_batch_entrypoint` | `preserve_or_archive` | `one-shot-batches` |
| `backend/scripts/run_football_external_benchmark_harness_smoke.py` | `??` | `one_shot_batch_entrypoint` | `preserve_or_archive` | `one-shot-batches` |
| `backend/scripts/run_football_external_benchmark_lane_closeout.py` | `??` | `one_shot_batch_entrypoint` | `preserve_or_archive` | `one-shot-batches` |
| `backend/scripts/run_football_external_benchmark_operationalization_plan.py` | `??` | `one_shot_batch_entrypoint` | `preserve_or_archive` | `one-shot-batches` |
| `backend/scripts/run_football_external_benchmark_product_decision_surface.py` | `??` | `one_shot_batch_entrypoint` | `preserve_or_archive` | `one-shot-batches` |
| `backend/scripts/run_football_external_benchmark_product_decision_surface_route_implementation.py` | `??` | `one_shot_batch_entrypoint` | `preserve_or_archive` | `one-shot-batches` |
| `backend/scripts/run_football_external_benchmark_product_ui_binding.py` | `??` | `one_shot_batch_entrypoint` | `preserve_or_archive` | `one-shot-batches` |
| `backend/scripts/run_football_external_benchmark_product_ui_route_implementation.py` | `??` | `one_shot_batch_entrypoint` | `preserve_or_archive` | `one-shot-batches` |
| `backend/scripts/run_football_external_benchmark_real_evaluation_approval.py` | `??` | `one_shot_batch_entrypoint` | `preserve_or_archive` | `one-shot-batches` |
| `backend/scripts/run_football_external_benchmark_real_evaluation_design.py` | `??` | `one_shot_batch_entrypoint` | `preserve_or_archive` | `one-shot-batches` |
| `backend/scripts/run_football_external_benchmark_real_report_and_product_binding.py` | `??` | `one_shot_batch_entrypoint` | `preserve_or_archive` | `one-shot-batches` |
| `backend/scripts/run_football_external_benchmark_real_source_path_consolidation.py` | `??` | `one_shot_batch_entrypoint` | `preserve_or_archive` | `one-shot-batches` |
| `backend/scripts/run_football_external_benchmark_report_smoke.py` | `??` | `one_shot_batch_entrypoint` | `preserve_or_archive` | `one-shot-batches` |
| `backend/scripts/run_football_external_safe_adapter_fixture_implementation.py` | `??` | `one_shot_batch_entrypoint` | `preserve_or_archive` | `one-shot-batches` |
| `backend/scripts/run_football_external_safe_source_adapter_smoke_test.py` | `??` | `one_shot_batch_entrypoint` | `preserve_or_archive` | `one-shot-batches` |
| `backend/scripts/run_football_external_safe_source_controlled_sample_fetch.py` | `??` | `one_shot_batch_entrypoint` | `preserve_or_archive` | `one-shot-batches` |
| `backend/scripts/run_football_external_safe_source_sample_download_approval.py` | `??` | `one_shot_batch_entrypoint` | `preserve_or_archive` | `one-shot-batches` |
| `backend/scripts/run_football_external_safe_source_sample_ingestion_plan.py` | `??` | `one_shot_batch_entrypoint` | `preserve_or_archive` | `one-shot-batches` |
| `backend/scripts/run_football_external_soccernet_analysis_product_api_smoke.py` | `??` | `one_shot_batch_entrypoint` | `preserve_or_archive` | `one-shot-batches` |
| `backend/scripts/run_football_external_soccernet_analysis_product_lane_closeout.py` | `??` | `one_shot_batch_entrypoint` | `preserve_or_archive` | `one-shot-batches` |
| `backend/scripts/run_football_external_soccernet_analysis_product_ui_binding.py` | `??` | `one_shot_batch_entrypoint` | `preserve_or_archive` | `one-shot-batches` |
| `backend/scripts/run_football_external_soccernet_analysis_product_ui_route_implementation.py` | `??` | `one_shot_batch_entrypoint` | `preserve_or_archive` | `one-shot-batches` |
| `backend/scripts/run_football_external_soccernet_api_listing_probe.py` | `??` | `one_shot_batch_entrypoint` | `preserve_or_archive` | `one-shot-batches` |
| `backend/scripts/run_football_external_soccernet_api_metadata_probe.py` | `??` | `one_shot_batch_entrypoint` | `preserve_or_archive` | `one-shot-batches` |
| `backend/scripts/run_football_external_soccernet_benchmark_adapter_contract_prep.py` | `??` | `one_shot_batch_entrypoint` | `preserve_or_archive` | `one-shot-batches` |
| `backend/scripts/run_football_external_soccernet_bounded_analysis_execution.py` | `??` | `one_shot_batch_entrypoint` | `preserve_or_archive` | `one-shot-batches` |
| `backend/scripts/run_football_external_soccernet_bounded_analysis_execution_approval.py` | `??` | `one_shot_batch_entrypoint` | `preserve_or_archive` | `one-shot-batches` |
| `backend/scripts/run_football_external_soccernet_bounded_analysis_lane_closeout.py` | `??` | `one_shot_batch_entrypoint` | `preserve_or_archive` | `one-shot-batches` |
| `backend/scripts/run_football_external_soccernet_bounded_analysis_report_smoke.py` | `??` | `one_shot_batch_entrypoint` | `preserve_or_archive` | `one-shot-batches` |
| `backend/scripts/run_football_external_soccernet_bounded_product_validation_execution.py` | `??` | `one_shot_batch_entrypoint` | `preserve_or_archive` | `one-shot-batches` |
| `backend/scripts/run_football_external_soccernet_bounded_product_validation_execution_approval.py` | `??` | `one_shot_batch_entrypoint` | `preserve_or_archive` | `one-shot-batches` |
| `backend/scripts/run_football_external_soccernet_bounded_product_validation_plan.py` | `??` | `one_shot_batch_entrypoint` | `preserve_or_archive` | `one-shot-batches` |
| `backend/scripts/run_football_external_soccernet_bounded_product_validation_report_binding.py` | `??` | `one_shot_batch_entrypoint` | `preserve_or_archive` | `one-shot-batches` |
| `backend/scripts/run_football_external_soccernet_broader_validation_choice.py` | `??` | `one_shot_batch_entrypoint` | `preserve_or_archive` | `one-shot-batches` |
| `backend/scripts/run_football_external_soccernet_controlled_label_metadata_probe.py` | `??` | `one_shot_batch_entrypoint` | `preserve_or_archive` | `one-shot-batches` |
| `backend/scripts/run_football_external_soccernet_controlled_label_sample_fetch.py` | `??` | `one_shot_batch_entrypoint` | `preserve_or_archive` | `one-shot-batches` |
| `backend/scripts/run_football_external_soccernet_controlled_label_sample_fetch_approval.py` | `??` | `one_shot_batch_entrypoint` | `preserve_or_archive` | `one-shot-batches` |
| `backend/scripts/run_football_external_soccernet_controlled_video_sample_fetch.py` | `??` | `one_shot_batch_entrypoint` | `preserve_or_archive` | `one-shot-batches` |
| `backend/scripts/run_football_external_soccernet_detector_miss_capture_and_label_queue.py` | `??` | `one_shot_batch_entrypoint` | `preserve_or_archive` | `one-shot-batches` |
| `backend/scripts/run_football_external_soccernet_detector_miss_manual_review_resolution.py` | `??` | `one_shot_batch_entrypoint` | `preserve_or_archive` | `one-shot-batches` |
| `backend/scripts/run_football_external_soccernet_event_adapter_fixture_materialization.py` | `??` | `one_shot_batch_entrypoint` | `preserve_or_archive` | `one-shot-batches` |
| `backend/scripts/run_football_external_soccernet_event_adapter_smoke_test.py` | `??` | `one_shot_batch_entrypoint` | `preserve_or_archive` | `one-shot-batches` |
| `backend/scripts/run_football_external_soccernet_event_benchmark_smoke.py` | `??` | `one_shot_batch_entrypoint` | `preserve_or_archive` | `one-shot-batches` |
| `backend/scripts/run_football_external_soccernet_event_lane_closeout.py` | `??` | `one_shot_batch_entrypoint` | `preserve_or_archive` | `one-shot-batches` |
| `backend/scripts/run_football_external_soccernet_event_report_contract_prep.py` | `??` | `one_shot_batch_entrypoint` | `preserve_or_archive` | `one-shot-batches` |
| `backend/scripts/run_football_external_soccernet_event_report_product_integration.py` | `??` | `one_shot_batch_entrypoint` | `preserve_or_archive` | `one-shot-batches` |
| `backend/scripts/run_football_external_soccernet_event_report_smoke.py` | `??` | `one_shot_batch_entrypoint` | `preserve_or_archive` | `one-shot-batches` |
| `backend/scripts/run_football_external_soccernet_full_analysis_execution.py` | `??` | `one_shot_batch_entrypoint` | `preserve_or_archive` | `one-shot-batches` |
| `backend/scripts/run_football_external_soccernet_full_analysis_execution_approval.py` | `??` | `one_shot_batch_entrypoint` | `preserve_or_archive` | `one-shot-batches` |
| `backend/scripts/run_football_external_soccernet_full_analysis_lane_closeout.py` | `??` | `one_shot_batch_entrypoint` | `preserve_or_archive` | `one-shot-batches` |
| `backend/scripts/run_football_external_soccernet_full_analysis_product_integration.py` | `??` | `one_shot_batch_entrypoint` | `preserve_or_archive` | `one-shot-batches` |
| `backend/scripts/run_football_external_soccernet_full_analysis_report_smoke.py` | `??` | `one_shot_batch_entrypoint` | `preserve_or_archive` | `one-shot-batches` |
| `backend/scripts/run_football_external_soccernet_label_fetch_contract_repair.py` | `??` | `one_shot_batch_entrypoint` | `preserve_or_archive` | `one-shot-batches` |
| `backend/scripts/run_football_external_soccernet_label_schema_ingestion_probe.py` | `??` | `one_shot_batch_entrypoint` | `preserve_or_archive` | `one-shot-batches` |
| `backend/scripts/run_football_external_soccernet_nda_api_access_approval.py` | `??` | `one_shot_batch_entrypoint` | `preserve_or_archive` | `one-shot-batches` |
| `backend/scripts/run_football_external_soccernet_real_sample_product_pipeline_training_decision.py` | `??` | `one_shot_batch_entrypoint` | `preserve_or_archive` | `one-shot-batches` |
| `backend/scripts/run_football_external_soccernet_split_archive_access_review.py` | `??` | `one_shot_batch_entrypoint` | `preserve_or_archive` | `one-shot-batches` |
| `backend/scripts/run_football_external_soccernet_split_archive_range_index_probe.py` | `??` | `one_shot_batch_entrypoint` | `preserve_or_archive` | `one-shot-batches` |
| `backend/scripts/run_football_external_soccernet_split_archive_size_probe.py` | `??` | `one_shot_batch_entrypoint` | `preserve_or_archive` | `one-shot-batches` |
| `backend/scripts/run_football_external_soccernet_video_analysis_dry_run.py` | `??` | `one_shot_batch_entrypoint` | `preserve_or_archive` | `one-shot-batches` |
| `backend/scripts/run_football_external_soccernet_video_analysis_dry_run_approval.py` | `??` | `one_shot_batch_entrypoint` | `preserve_or_archive` | `one-shot-batches` |
| `backend/scripts/run_football_external_soccernet_video_analysis_dry_run_product_bridge_smoke.py` | `??` | `one_shot_batch_entrypoint` | `preserve_or_archive` | `one-shot-batches` |
| `backend/scripts/run_football_external_soccernet_video_frame_probe.py` | `??` | `one_shot_batch_entrypoint` | `preserve_or_archive` | `one-shot-batches` |
| `backend/scripts/run_football_external_soccernet_video_member_extract.py` | `??` | `one_shot_batch_entrypoint` | `preserve_or_archive` | `one-shot-batches` |
| `backend/scripts/run_football_external_soccernet_video_member_extract_approval.py` | `??` | `one_shot_batch_entrypoint` | `preserve_or_archive` | `one-shot-batches` |
| `backend/scripts/run_football_external_soccernet_video_product_path_smoke.py` | `??` | `one_shot_batch_entrypoint` | `preserve_or_archive` | `one-shot-batches` |
| `backend/scripts/run_football_external_soccernet_video_sample_download_approval.py` | `??` | `one_shot_batch_entrypoint` | `preserve_or_archive` | `one-shot-batches` |
| `backend/scripts/run_football_external_soccernet_video_sample_probe.py` | `??` | `one_shot_batch_entrypoint` | `preserve_or_archive` | `one-shot-batches` |
| `backend/scripts/run_football_external_soccernet_video_to_analysis_bridge_prep.py` | `??` | `one_shot_batch_entrypoint` | `preserve_or_archive` | `one-shot-batches` |
| `backend/scripts/run_football_external_soccernet_zip_label_member_extract.py` | `??` | `one_shot_batch_entrypoint` | `preserve_or_archive` | `one-shot-batches` |
| `backend/scripts/run_football_external_soccernet_zip_label_member_extract_approval.py` | `??` | `one_shot_batch_entrypoint` | `preserve_or_archive` | `one-shot-batches` |
| `backend/scripts/run_football_external_soccertrack_adapter_smoke_test.py` | `??` | `one_shot_batch_entrypoint` | `preserve_or_archive` | `one-shot-batches` |
| `backend/scripts/run_football_external_soccertrack_analysis_product_lane_closeout.py` | `??` | `one_shot_batch_entrypoint` | `preserve_or_archive` | `one-shot-batches` |
| `backend/scripts/run_football_external_soccertrack_analysis_product_ui_binding.py` | `??` | `one_shot_batch_entrypoint` | `preserve_or_archive` | `one-shot-batches` |
| `backend/scripts/run_football_external_soccertrack_analysis_product_ui_route_implementation.py` | `??` | `one_shot_batch_entrypoint` | `preserve_or_archive` | `one-shot-batches` |
| `backend/scripts/run_football_external_soccertrack_analysis_report_smoke.py` | `??` | `one_shot_batch_entrypoint` | `preserve_or_archive` | `one-shot-batches` |
| `backend/scripts/run_football_external_soccertrack_authenticated_fixture_access_approval.py` | `??` | `one_shot_batch_entrypoint` | `preserve_or_archive` | `one-shot-batches` |
| `backend/scripts/run_football_external_soccertrack_controlled_sample_fetch.py` | `??` | `one_shot_batch_entrypoint` | `preserve_or_archive` | `one-shot-batches` |
| `backend/scripts/run_football_external_soccertrack_fixture_source_access_review.py` | `??` | `one_shot_batch_entrypoint` | `preserve_or_archive` | `one-shot-batches` |
| `backend/scripts/run_football_external_soccertrack_google_drive_bounded_fixture_fetch.py` | `??` | `one_shot_batch_entrypoint` | `preserve_or_archive` | `one-shot-batches` |
| `backend/scripts/run_football_external_soccertrack_google_drive_fixture_access_probe.py` | `??` | `one_shot_batch_entrypoint` | `preserve_or_archive` | `one-shot-batches` |
| `backend/scripts/run_football_external_soccertrack_lane_closeout.py` | `??` | `one_shot_batch_entrypoint` | `preserve_or_archive` | `one-shot-batches` |
| `backend/scripts/run_football_external_soccertrack_match_bundle_bridge_smoke.py` | `??` | `one_shot_batch_entrypoint` | `preserve_or_archive` | `one-shot-batches` |
| `backend/scripts/run_football_external_soccertrack_metadata_adapter_smoke.py` | `??` | `one_shot_batch_entrypoint` | `preserve_or_archive` | `one-shot-batches` |
| `backend/scripts/run_football_external_soccertrack_product_route_smoke.py` | `??` | `one_shot_batch_entrypoint` | `preserve_or_archive` | `one-shot-batches` |
| `backend/scripts/run_football_external_soccertrack_sample_fixture_materialization.py` | `??` | `one_shot_batch_entrypoint` | `preserve_or_archive` | `one-shot-batches` |
| `backend/scripts/run_football_external_soccertrack_sample_fixture_materialization_approval.py` | `??` | `one_shot_batch_entrypoint` | `preserve_or_archive` | `one-shot-batches` |
| `backend/scripts/run_football_external_soccertrack_sample_ingestion_contract_prep.py` | `??` | `one_shot_batch_entrypoint` | `preserve_or_archive` | `one-shot-batches` |
| `backend/scripts/run_football_external_soccertrack_sample_schema_probe.py` | `??` | `one_shot_batch_entrypoint` | `preserve_or_archive` | `one-shot-batches` |
| `backend/scripts/run_football_external_soccertrack_schema_doc_fetch.py` | `??` | `one_shot_batch_entrypoint` | `preserve_or_archive` | `one-shot-batches` |
| `backend/scripts/run_football_external_soccertrack_schema_doc_fetch_approval.py` | `??` | `one_shot_batch_entrypoint` | `preserve_or_archive` | `one-shot-batches` |
| `backend/scripts/run_football_external_soccertrack_schema_doc_parse.py` | `??` | `one_shot_batch_entrypoint` | `preserve_or_archive` | `one-shot-batches` |
| `backend/scripts/run_product_video_to_analysis_finish_line_execution.py` | `??` | `one_shot_batch_entrypoint` | `preserve_or_archive` | `one-shot-batches` |
| `backend/scripts/run_product_video_to_analysis_normal_storage_smoke.py` | `??` | `one_shot_batch_entrypoint` | `preserve_or_archive` | `one-shot-batches` |
| `backend/scripts/run_product_video_to_analysis_smoke.py` | `??` | `one_shot_batch_entrypoint` | `preserve_or_archive` | `one-shot-batches` |
| `backend/scripts/run_product_video_to_analysis_smoke_isolated.py` | `??` | `one_shot_batch_entrypoint` | `preserve_or_archive` | `one-shot-batches` |
| `backend/scripts/run_promoted_v6_reviewed_positive_residual_proposal_generation_fix.py` | ` M` | `one_shot_batch_entrypoint` | `preserve_or_archive` | `one-shot-batches` |
| `backend/scripts/run_v7_2_runtime_registry_product_path_binding.py` | `??` | `one_shot_batch_entrypoint` | `preserve_or_archive` | `one-shot-batches` |
| `backend/scripts/run_v7_3_bounded_retrain.py` | `??` | `one_shot_batch_entrypoint` | `preserve_or_archive` | `one-shot-batches` |
| `backend/scripts/run_v7_3_crop_probe_precision_guardrail_audit.py` | `??` | `one_shot_batch_entrypoint` | `preserve_or_archive` | `one-shot-batches` |
| `backend/scripts/run_v7_3_export_label_overlay_audit.py` | `??` | `one_shot_batch_entrypoint` | `preserve_or_archive` | `one-shot-batches` |
| `backend/scripts/run_v7_3_full_pipeline_non_promotion_eval.py` | `??` | `one_shot_batch_entrypoint` | `preserve_or_archive` | `one-shot-batches` |
| `backend/scripts/run_v7_3_post_runtime_default_source_robustness_validation.py` | `??` | `one_shot_batch_entrypoint` | `preserve_or_archive` | `one-shot-batches` |
| `backend/scripts/run_v7_3_promotion_readiness_validation.py` | `??` | `one_shot_batch_entrypoint` | `preserve_or_archive` | `one-shot-batches` |
| `backend/scripts/run_v7_3_runtime_default_change_validation.py` | `??` | `one_shot_batch_entrypoint` | `preserve_or_archive` | `one-shot-batches` |
| `backend/scripts/run_v7_3_runtime_default_rollout_closeout.py` | `??` | `one_shot_batch_entrypoint` | `preserve_or_archive` | `one-shot-batches` |
| `backend/scripts/run_v7_3_training_manifest_prep_from_soccernet_real_misses.py` | `??` | `one_shot_batch_entrypoint` | `preserve_or_archive` | `one-shot-batches` |
| `backend/scripts/run_v7_4_training_decision_from_real_misses.py` | `??` | `one_shot_batch_entrypoint` | `preserve_or_archive` | `one-shot-batches` |
| `backend/scripts/run_video_to_analysis_acceptance_report_product_backlog.py` | `??` | `one_shot_batch_entrypoint` | `preserve_or_archive` | `one-shot-batches` |
| `backend/scripts/run_video_to_analysis_acceptance_report_route_binding.py` | `??` | `one_shot_batch_entrypoint` | `preserve_or_archive` | `one-shot-batches` |
| `backend/scripts/run_video_to_analysis_bounded_next_sample_closeout.py` | `??` | `one_shot_batch_entrypoint` | `preserve_or_archive` | `one-shot-batches` |
| `backend/scripts/run_video_to_analysis_bounded_next_sample_execution.py` | `??` | `one_shot_batch_entrypoint` | `preserve_or_archive` | `one-shot-batches` |
| `backend/scripts/run_video_to_analysis_bounded_next_sample_execution_approval.py` | `??` | `one_shot_batch_entrypoint` | `preserve_or_archive` | `one-shot-batches` |
| `backend/scripts/run_video_to_analysis_bounded_next_sample_report_route_binding.py` | `??` | `one_shot_batch_entrypoint` | `preserve_or_archive` | `one-shot-batches` |
| `backend/scripts/run_video_to_analysis_broader_real_video_acceptance_approval.py` | `??` | `one_shot_batch_entrypoint` | `preserve_or_archive` | `one-shot-batches` |
| `backend/scripts/run_video_to_analysis_broader_real_video_acceptance_closeout.py` | `??` | `one_shot_batch_entrypoint` | `preserve_or_archive` | `one-shot-batches` |
| `backend/scripts/run_video_to_analysis_broader_real_video_acceptance_execution.py` | `??` | `one_shot_batch_entrypoint` | `preserve_or_archive` | `one-shot-batches` |
| `backend/scripts/run_video_to_analysis_broader_real_video_acceptance_suite_prep.py` | `??` | `one_shot_batch_entrypoint` | `preserve_or_archive` | `one-shot-batches` |
| `backend/scripts/run_video_to_analysis_current_release_acceptance_decision_surface.py` | `??` | `one_shot_batch_entrypoint` | `preserve_or_archive` | `one-shot-batches` |
| `backend/scripts/run_video_to_analysis_detector_evaluation_bounded_existing_artifact_execution.py` | `??` | `one_shot_batch_entrypoint` | `preserve_or_archive` | `one-shot-batches` |
| `backend/scripts/run_video_to_analysis_detector_evaluation_chain_common.py` | `??` | `reusable_workflow` | `preserve_commit` | `workflow` |
| `backend/scripts/run_video_to_analysis_detector_evaluation_lane_closeout.py` | `??` | `one_shot_batch_entrypoint` | `preserve_or_archive` | `one-shot-batches` |
| `backend/scripts/run_video_to_analysis_detector_evaluation_reentry_approval.py` | `??` | `one_shot_batch_entrypoint` | `preserve_or_archive` | `one-shot-batches` |
| `backend/scripts/run_video_to_analysis_detector_evaluation_reentry_plan.py` | `??` | `one_shot_batch_entrypoint` | `preserve_or_archive` | `one-shot-batches` |
| `backend/scripts/run_video_to_analysis_detector_evaluation_report_binding.py` | `??` | `one_shot_batch_entrypoint` | `preserve_or_archive` | `one-shot-batches` |
| `backend/scripts/run_video_to_analysis_detector_evaluation_report_route_binding.py` | `??` | `one_shot_batch_entrypoint` | `preserve_or_archive` | `one-shot-batches` |
| `backend/scripts/run_video_to_analysis_finish_line_closeout.py` | `??` | `one_shot_batch_entrypoint` | `preserve_or_archive` | `one-shot-batches` |
| `backend/scripts/run_video_to_analysis_finish_line_completion_summary.py` | `??` | `one_shot_batch_entrypoint` | `preserve_or_archive` | `one-shot-batches` |
| `backend/scripts/run_video_to_analysis_finish_line_execution_approval.py` | `??` | `one_shot_batch_entrypoint` | `preserve_or_archive` | `one-shot-batches` |
| `backend/scripts/run_video_to_analysis_finish_line_integration_plan.py` | `??` | `one_shot_batch_entrypoint` | `preserve_or_archive` | `one-shot-batches` |
| `backend/scripts/run_video_to_analysis_finish_line_normal_storage_closeout.py` | `??` | `one_shot_batch_entrypoint` | `preserve_or_archive` | `one-shot-batches` |
| `backend/scripts/run_video_to_analysis_finish_line_normal_storage_execution_approval.py` | `??` | `one_shot_batch_entrypoint` | `preserve_or_archive` | `one-shot-batches` |
| `backend/scripts/run_video_to_analysis_finish_line_operational_readiness.py` | `??` | `one_shot_batch_entrypoint` | `preserve_or_archive` | `one-shot-batches` |
| `backend/scripts/run_video_to_analysis_finish_line_product_acceptance_closeout.py` | `??` | `one_shot_batch_entrypoint` | `preserve_or_archive` | `one-shot-batches` |
| `backend/scripts/run_video_to_analysis_finish_line_product_binding.py` | `??` | `one_shot_batch_entrypoint` | `preserve_or_archive` | `one-shot-batches` |
| `backend/scripts/run_video_to_analysis_finish_line_product_execution_approval.py` | `??` | `one_shot_batch_entrypoint` | `preserve_or_archive` | `one-shot-batches` |
| `backend/scripts/run_video_to_analysis_finish_line_product_execution_plan.py` | `??` | `one_shot_batch_entrypoint` | `preserve_or_archive` | `one-shot-batches` |
| `backend/scripts/run_video_to_analysis_finish_line_route_implementation.py` | `??` | `one_shot_batch_entrypoint` | `preserve_or_archive` | `one-shot-batches` |
| `backend/scripts/run_video_to_analysis_finish_line_route_polish.py` | `??` | `one_shot_batch_entrypoint` | `preserve_or_archive` | `one-shot-batches` |
| `backend/scripts/run_video_to_analysis_finish_line_user_acceptance_trial.py` | `??` | `one_shot_batch_entrypoint` | `preserve_or_archive` | `one-shot-batches` |
| `backend/scripts/run_video_to_analysis_growth_lane_closeout_readout.py` | `??` | `one_shot_batch_entrypoint` | `preserve_or_archive` | `one-shot-batches` |
| `backend/scripts/run_video_to_analysis_growth_lane_decision_snapshot.py` | `??` | `one_shot_batch_entrypoint` | `preserve_or_archive` | `one-shot-batches` |
| `backend/scripts/run_video_to_analysis_manual_operator_release_decision.py` | `??` | `one_shot_batch_entrypoint` | `preserve_or_archive` | `one-shot-batches` |
| `backend/scripts/run_video_to_analysis_next_roadmap_direction_snapshot.py` | `??` | `one_shot_batch_entrypoint` | `preserve_or_archive` | `one-shot-batches` |
| `backend/scripts/run_video_to_analysis_next_sample_selection_snapshot.py` | `??` | `one_shot_batch_entrypoint` | `preserve_or_archive` | `one-shot-batches` |
| `backend/scripts/run_video_to_analysis_next_strategic_lane_selection.py` | `??` | `one_shot_batch_entrypoint` | `preserve_or_archive` | `one-shot-batches` |
| `backend/scripts/run_video_to_analysis_operational_backlog_prioritization.py` | `??` | `one_shot_batch_entrypoint` | `preserve_or_archive` | `one-shot-batches` |
| `backend/scripts/run_video_to_analysis_operational_sprint_closeout.py` | `??` | `one_shot_batch_entrypoint` | `preserve_or_archive` | `one-shot-batches` |
| `backend/scripts/run_video_to_analysis_operator_dashboard_polish.py` | `??` | `one_shot_batch_entrypoint` | `preserve_or_archive` | `one-shot-batches` |
| `backend/scripts/run_video_to_analysis_operator_handoff_pack.py` | `??` | `one_shot_batch_entrypoint` | `preserve_or_archive` | `one-shot-batches` |
| `backend/scripts/run_video_to_analysis_operator_handoff_route_binding.py` | `??` | `one_shot_batch_entrypoint` | `preserve_or_archive` | `one-shot-batches` |
| `backend/scripts/run_video_to_analysis_post_release_monitoring_closeout.py` | `??` | `one_shot_batch_entrypoint` | `preserve_or_archive` | `one-shot-batches` |
| `backend/scripts/run_video_to_analysis_post_release_monitoring_plan.py` | `??` | `one_shot_batch_entrypoint` | `preserve_or_archive` | `one-shot-batches` |
| `backend/scripts/run_video_to_analysis_post_release_monitoring_route_binding.py` | `??` | `one_shot_batch_entrypoint` | `preserve_or_archive` | `one-shot-batches` |
| `backend/scripts/run_video_to_analysis_product_hardening_backlog.py` | `??` | `one_shot_batch_entrypoint` | `preserve_or_archive` | `one-shot-batches` |
| `backend/scripts/run_video_to_analysis_product_lane_closeout.py` | `??` | `one_shot_batch_entrypoint` | `preserve_or_archive` | `one-shot-batches` |
| `backend/scripts/run_video_to_analysis_promoted_runtime_operational_completion_summary.py` | `??` | `one_shot_batch_entrypoint` | `preserve_or_archive` | `one-shot-batches` |
| `backend/scripts/run_video_to_analysis_promoted_runtime_operator_acceptance_trial.py` | `??` | `one_shot_batch_entrypoint` | `preserve_or_archive` | `one-shot-batches` |
| `backend/scripts/run_video_to_analysis_promoted_runtime_post_release_monitoring_execution.py` | `??` | `one_shot_batch_entrypoint` | `preserve_or_archive` | `one-shot-batches` |
| `backend/scripts/run_video_to_analysis_promoted_runtime_post_release_monitoring_plan.py` | `??` | `one_shot_batch_entrypoint` | `preserve_or_archive` | `one-shot-batches` |
| `backend/scripts/run_video_to_analysis_promoted_runtime_post_release_monitoring_route_binding.py` | `??` | `one_shot_batch_entrypoint` | `preserve_or_archive` | `one-shot-batches` |
| `backend/scripts/run_video_to_analysis_promoted_runtime_release_closeout.py` | `??` | `one_shot_batch_entrypoint` | `preserve_or_archive` | `one-shot-batches` |
| `backend/scripts/run_video_to_analysis_promotion_review_closeout.py` | `??` | `one_shot_batch_entrypoint` | `preserve_or_archive` | `one-shot-batches` |
| `backend/scripts/run_video_to_analysis_promotion_review_design.py` | `??` | `one_shot_batch_entrypoint` | `preserve_or_archive` | `one-shot-batches` |
| `backend/scripts/run_video_to_analysis_promotion_review_execution.py` | `??` | `one_shot_batch_entrypoint` | `preserve_or_archive` | `one-shot-batches` |
| `backend/scripts/run_video_to_analysis_promotion_review_report_binding.py` | `??` | `one_shot_batch_entrypoint` | `preserve_or_archive` | `one-shot-batches` |
| `backend/scripts/run_video_to_analysis_promotion_review_report_route_binding.py` | `??` | `one_shot_batch_entrypoint` | `preserve_or_archive` | `one-shot-batches` |
| `backend/scripts/run_video_to_analysis_real_video_scaleout_bounded_execution.py` | `??` | `one_shot_batch_entrypoint` | `preserve_or_archive` | `one-shot-batches` |
| `backend/scripts/run_video_to_analysis_real_video_scaleout_execution_approval.py` | `??` | `one_shot_batch_entrypoint` | `preserve_or_archive` | `one-shot-batches` |
| `backend/scripts/run_video_to_analysis_real_video_scaleout_lane_closeout.py` | `??` | `one_shot_batch_entrypoint` | `preserve_or_archive` | `one-shot-batches` |
| `backend/scripts/run_video_to_analysis_real_video_scaleout_plan.py` | `??` | `one_shot_batch_entrypoint` | `preserve_or_archive` | `one-shot-batches` |
| `backend/scripts/run_video_to_analysis_real_video_scaleout_plan_refresh.py` | `??` | `one_shot_batch_entrypoint` | `preserve_or_archive` | `one-shot-batches` |
| `backend/scripts/run_video_to_analysis_real_video_scaleout_report_route_binding.py` | `??` | `one_shot_batch_entrypoint` | `preserve_or_archive` | `one-shot-batches` |
| `backend/scripts/run_video_to_analysis_real_video_scaleout_source_sampling_expansion.py` | `??` | `one_shot_batch_entrypoint` | `preserve_or_archive` | `one-shot-batches` |
| `backend/scripts/run_video_to_analysis_release_acceptance_archive.py` | `??` | `one_shot_batch_entrypoint` | `preserve_or_archive` | `one-shot-batches` |
| `backend/scripts/run_video_to_analysis_release_candidate_closeout.py` | `??` | `one_shot_batch_entrypoint` | `preserve_or_archive` | `one-shot-batches` |
| `backend/scripts/run_video_to_analysis_release_completion_summary.py` | `??` | `one_shot_batch_entrypoint` | `preserve_or_archive` | `one-shot-batches` |
| `backend/scripts/run_video_to_analysis_release_readout_pack.py` | `??` | `one_shot_batch_entrypoint` | `preserve_or_archive` | `one-shot-batches` |
| `backend/scripts/run_video_to_analysis_release_readout_route_binding.py` | `??` | `one_shot_batch_entrypoint` | `preserve_or_archive` | `one-shot-batches` |
| `backend/scripts/run_video_to_analysis_roadmap_state_reconciliation.py` | `??` | `one_shot_batch_entrypoint` | `preserve_or_archive` | `one-shot-batches` |
| `backend/scripts/run_video_to_analysis_scaleout_or_backlog_decision_snapshot.py` | `??` | `one_shot_batch_entrypoint` | `preserve_or_archive` | `one-shot-batches` |
| `backend/scripts/run_video_to_analysis_source_and_artifact_cleanup_map.py` | `??` | `one_shot_batch_entrypoint` | `preserve_or_archive` | `one-shot-batches` |
| `backend/scripts/run_video_to_analysis_source_pool_replenishment_approval.py` | `??` | `one_shot_batch_entrypoint` | `preserve_or_archive` | `one-shot-batches` |
| `backend/scripts/run_video_to_analysis_source_pool_replenishment_plan.py` | `??` | `one_shot_batch_entrypoint` | `preserve_or_archive` | `one-shot-batches` |
| `backend/scripts/run_video_to_analysis_steady_state_monitoring_cycle.py` | `??` | `one_shot_batch_entrypoint` | `preserve_or_archive` | `one-shot-batches` |
| `backend/scripts/run_video_to_analysis_steady_state_monitoring_recurring_schedule.py` | `??` | `one_shot_batch_entrypoint` | `preserve_or_archive` | `one-shot-batches` |
| `backend/scripts/run_video_to_analysis_storage_cleanup_approval.py` | `??` | `one_shot_batch_entrypoint` | `preserve_or_archive` | `one-shot-batches` |
| `backend/scripts/run_video_to_analysis_storage_cleanup_bounded_execution.py` | `??` | `one_shot_batch_entrypoint` | `preserve_or_archive` | `one-shot-batches` |
| `backend/scripts/run_video_to_analysis_storage_cleanup_closeout.py` | `??` | `one_shot_batch_entrypoint` | `preserve_or_archive` | `one-shot-batches` |
| `backend/scripts/run_video_to_analysis_storage_cleanup_dry_run_execution.py` | `??` | `one_shot_batch_entrypoint` | `preserve_or_archive` | `one-shot-batches` |
| `backend/scripts/run_video_to_analysis_storage_cleanup_execution_approval.py` | `??` | `one_shot_batch_entrypoint` | `preserve_or_archive` | `one-shot-batches` |
| `backend/scripts/run_video_to_analysis_storage_retention_and_artifact_hygiene.py` | `??` | `one_shot_batch_entrypoint` | `preserve_or_archive` | `one-shot-batches` |
| `backend/scripts/run_video_to_analysis_upload_to_analysis_walkthrough.py` | `??` | `one_shot_batch_entrypoint` | `preserve_or_archive` | `one-shot-batches` |
| `backend/scripts/run_video_to_analysis_user_facing_release_readout.py` | `??` | `one_shot_batch_entrypoint` | `preserve_or_archive` | `one-shot-batches` |
| `backend/scripts/run_video_to_analysis_v7_3_release_packaging_and_worktree_triage.py` | `??` | `one_shot_batch_entrypoint` | `preserve_or_archive` | `one-shot-batches` |
| `backend/scripts/serve_football_external_soccernet_detector_miss_review_ui.py` | `??` | `manual_review` | `manual_review` | `manual-review` |
| `backend/scripts/video_to_analysis_operational_sprint_common.py` | `??` | `reusable_workflow` | `preserve_commit` | `workflow` |
| `backend/scripts/video_to_analysis_promoted_runtime_monitoring_common.py` | `??` | `reusable_workflow` | `preserve_commit` | `workflow` |
| `backend/storage/automation/unattended_roadmap_loop_status.json` | ` M` | `regenerable_truth` | `retain_external` | `generated-truth` |
| `backend/storage/benchmark_suites/frozen-viable-baseline-slice-suite/detector_candidate_promotion.json` | ` M` | `essential_release_truth` | `preserve_commit` | `release-truth` |
| `backend/storage/runtime/promoted_touchline_detector_candidate.json` | ` M` | `essential_release_truth` | `preserve_commit` | `release-truth` |
| `backend/storage/trained_detector_candidates/touchline_detector_candidate_v7/football_external_benchmark_harness_prep_v1/batch_outcome_analysis.json` | ` M` | `regenerable_truth` | `retain_external` | `generated-truth` |
| `backend/storage/trained_detector_candidates/touchline_detector_candidate_v7/football_external_benchmark_harness_prep_v1/batch_outcome_analysis.md` | ` M` | `regenerable_truth` | `retain_external` | `generated-truth` |
| `backend/storage/trained_detector_candidates/touchline_detector_candidate_v7/football_external_benchmark_harness_prep_v1/benchmark_harness_readiness_audit.json` | ` M` | `regenerable_truth` | `retain_external` | `generated-truth` |
| `backend/storage/trained_detector_candidates/touchline_detector_candidate_v7/football_external_benchmark_harness_prep_v1/benchmark_resource_inventory.json` | ` M` | `regenerable_truth` | `retain_external` | `generated-truth` |
| `backend/storage/trained_detector_candidates/touchline_detector_candidate_v7/football_external_benchmark_harness_prep_v1/benchmark_split_plan.json` | ` M` | `regenerable_truth` | `retain_external` | `generated-truth` |
| `backend/storage/trained_detector_candidates/touchline_detector_candidate_v7/football_external_benchmark_harness_prep_v1/dataset_adapter_contract.json` | ` M` | `regenerable_truth` | `retain_external` | `generated-truth` |
| `backend/storage/trained_detector_candidates/touchline_detector_candidate_v7/football_external_benchmark_harness_prep_v1/decision_matrix.json` | ` M` | `regenerable_truth` | `retain_external` | `generated-truth` |
| `backend/storage/trained_detector_candidates/touchline_detector_candidate_v7/football_external_benchmark_harness_prep_v1/external_benchmark_harness_summary.json` | ` M` | `regenerable_truth` | `retain_external` | `generated-truth` |
| `backend/storage/trained_detector_candidates/touchline_detector_candidate_v7/football_external_benchmark_harness_prep_v1/failsafe_attempt_plan.json` | ` M` | `regenerable_truth` | `retain_external` | `generated-truth` |
| `backend/storage/trained_detector_candidates/touchline_detector_candidate_v7/football_external_benchmark_harness_prep_v1/stage_gate_contract.json` | ` M` | `regenerable_truth` | `retain_external` | `generated-truth` |
| `backend/storage/trained_detector_candidates/touchline_detector_candidate_v7/v7_1_positive_candidate_mining_expansion_v1/batch_outcome_analysis.json` | ` D` | `tracked_deletion` | `manual_review` | `tracked-deletions` |
| `backend/storage/trained_detector_candidates/touchline_detector_candidate_v7/v7_1_positive_candidate_mining_expansion_v1/batch_outcome_analysis.md` | ` D` | `tracked_deletion` | `manual_review` | `tracked-deletions` |
| `backend/storage/trained_detector_candidates/touchline_detector_candidate_v7/v7_1_positive_candidate_mining_expansion_v1/corrected_label_overlay.json` | ` D` | `tracked_deletion` | `manual_review` | `tracked-deletions` |
| `backend/storage/trained_detector_candidates/touchline_detector_candidate_v7/v7_1_positive_candidate_mining_expansion_v1/correction_review_index.html` | ` D` | `tracked_deletion` | `manual_review` | `tracked-deletions` |
| `backend/storage/trained_detector_candidates/touchline_detector_candidate_v7/v7_1_positive_candidate_mining_expansion_v1/decision_matrix.json` | ` D` | `tracked_deletion` | `manual_review` | `tracked-deletions` |
| `backend/storage/trained_detector_candidates/touchline_detector_candidate_v7/v7_1_positive_candidate_mining_expansion_v1/new_mined_candidate_manifest.json` | ` D` | `tracked_deletion` | `manual_review` | `tracked-deletions` |
| `backend/storage/trained_detector_candidates/touchline_detector_candidate_v7/v7_1_positive_candidate_mining_expansion_v1/salvage_candidate_summary.json` | ` D` | `tracked_deletion` | `manual_review` | `tracked-deletions` |
| `backend/storage/trained_detector_candidates/touchline_detector_candidate_v7/v7_1_positive_candidate_mining_expansion_v1/v7_1_positive_candidate_mining_expansion_summary.json` | ` D` | `tracked_deletion` | `manual_review` | `tracked-deletions` |
| `backend/storage/trained_detector_candidates/touchline_detector_candidate_v7/v7_1_positive_diversity_manual_review_resolution_v1/batch_outcome_analysis.json` | ` D` | `tracked_deletion` | `manual_review` | `tracked-deletions` |
| `backend/storage/trained_detector_candidates/touchline_detector_candidate_v7/v7_1_positive_diversity_manual_review_resolution_v1/batch_outcome_analysis.md` | ` D` | `tracked_deletion` | `manual_review` | `tracked-deletions` |
| `backend/storage/trained_detector_candidates/touchline_detector_candidate_v7/v7_1_positive_diversity_manual_review_resolution_v1/decision_matrix.json` | ` D` | `tracked_deletion` | `manual_review` | `tracked-deletions` |
| `backend/storage/trained_detector_candidates/touchline_detector_candidate_v7/v7_1_positive_diversity_manual_review_resolution_v1/reviewed_positive_resolution_counts.json` | ` D` | `tracked_deletion` | `manual_review` | `tracked-deletions` |
| `backend/storage/trained_detector_candidates/touchline_detector_candidate_v7/v7_1_positive_diversity_manual_review_resolution_v1/reviewed_positive_truth_additions.json` | ` D` | `tracked_deletion` | `manual_review` | `tracked-deletions` |
| `backend/storage/trained_detector_candidates/touchline_detector_candidate_v7/v7_1_positive_diversity_manual_review_resolution_v1/v7_1_positive_diversity_manual_review_resolution_summary.json` | ` D` | `tracked_deletion` | `manual_review` | `tracked-deletions` |
| `backend/tests/test_api.py` | ` M` | `product_source` | `preserve_commit` | `product-source` |
| `backend/tests/test_external_soccernet_product_route.py` | `??` | `product_source` | `preserve_commit` | `product-source` |
| `backend/tests/test_external_soccertrack_analysis_product_route.py` | `??` | `product_source` | `preserve_commit` | `product-source` |
| `backend/tests/test_external_soccertrack_product_route.py` | `??` | `product_source` | `preserve_commit` | `product-source` |
| `backend/tests/test_processor.py` | ` M` | `product_source` | `preserve_commit` | `product-source` |
| `backend/tests/test_run_canonical_match_bundle_export.py` | `??` | `product_source` | `preserve_commit` | `product-source` |
| `backend/tests/test_run_football_external_benchmark_bounded_execution_smoke.py` | `??` | `product_source` | `preserve_commit` | `product-source` |
| `backend/tests/test_run_football_external_benchmark_execution_approval.py` | `??` | `product_source` | `preserve_commit` | `product-source` |
| `backend/tests/test_run_football_external_benchmark_harness_prep.py` | ` M` | `product_source` | `preserve_commit` | `product-source` |
| `backend/tests/test_run_football_external_benchmark_harness_smoke.py` | `??` | `product_source` | `preserve_commit` | `product-source` |
| `backend/tests/test_run_football_external_benchmark_lane_closeout.py` | `??` | `product_source` | `preserve_commit` | `product-source` |
| `backend/tests/test_run_football_external_benchmark_operationalization_plan.py` | `??` | `product_source` | `preserve_commit` | `product-source` |
| `backend/tests/test_run_football_external_benchmark_product_decision_surface.py` | `??` | `product_source` | `preserve_commit` | `product-source` |
| `backend/tests/test_run_football_external_benchmark_product_decision_surface_route_implementation.py` | `??` | `product_source` | `preserve_commit` | `product-source` |
| `backend/tests/test_run_football_external_benchmark_product_ui_binding.py` | `??` | `product_source` | `preserve_commit` | `product-source` |
| `backend/tests/test_run_football_external_benchmark_product_ui_route_implementation.py` | `??` | `product_source` | `preserve_commit` | `product-source` |
| `backend/tests/test_run_football_external_benchmark_real_evaluation_chain.py` | `??` | `product_source` | `preserve_commit` | `product-source` |
| `backend/tests/test_run_football_external_benchmark_real_evaluation_design.py` | `??` | `product_source` | `preserve_commit` | `product-source` |
| `backend/tests/test_run_football_external_benchmark_report_smoke.py` | `??` | `product_source` | `preserve_commit` | `product-source` |
| `backend/tests/test_run_football_external_safe_adapter_fixture_implementation.py` | `??` | `product_source` | `preserve_commit` | `product-source` |
| `backend/tests/test_run_football_external_safe_source_adapter_smoke_test.py` | `??` | `product_source` | `preserve_commit` | `product-source` |
| `backend/tests/test_run_football_external_safe_source_controlled_sample_fetch.py` | `??` | `product_source` | `preserve_commit` | `product-source` |
| `backend/tests/test_run_football_external_safe_source_sample_download_approval.py` | `??` | `product_source` | `preserve_commit` | `product-source` |
| `backend/tests/test_run_football_external_safe_source_sample_ingestion_plan.py` | `??` | `product_source` | `preserve_commit` | `product-source` |
| `backend/tests/test_run_football_external_soccernet_analysis_product_api_smoke.py` | `??` | `product_source` | `preserve_commit` | `product-source` |
| `backend/tests/test_run_football_external_soccernet_analysis_product_lane_closeout.py` | `??` | `product_source` | `preserve_commit` | `product-source` |
| `backend/tests/test_run_football_external_soccernet_analysis_product_ui_binding.py` | `??` | `product_source` | `preserve_commit` | `product-source` |
| `backend/tests/test_run_football_external_soccernet_analysis_product_ui_route_implementation.py` | `??` | `product_source` | `preserve_commit` | `product-source` |
| `backend/tests/test_run_football_external_soccernet_api_listing_probe.py` | `??` | `product_source` | `preserve_commit` | `product-source` |
| `backend/tests/test_run_football_external_soccernet_api_metadata_probe.py` | `??` | `product_source` | `preserve_commit` | `product-source` |
| `backend/tests/test_run_football_external_soccernet_benchmark_adapter_contract_prep.py` | `??` | `product_source` | `preserve_commit` | `product-source` |
| `backend/tests/test_run_football_external_soccernet_bounded_analysis_execution.py` | `??` | `product_source` | `preserve_commit` | `product-source` |
| `backend/tests/test_run_football_external_soccernet_bounded_analysis_execution_approval.py` | `??` | `product_source` | `preserve_commit` | `product-source` |
| `backend/tests/test_run_football_external_soccernet_bounded_analysis_lane_closeout.py` | `??` | `product_source` | `preserve_commit` | `product-source` |
| `backend/tests/test_run_football_external_soccernet_bounded_analysis_report_smoke.py` | `??` | `product_source` | `preserve_commit` | `product-source` |
| `backend/tests/test_run_football_external_soccernet_bounded_product_validation_execution.py` | `??` | `product_source` | `preserve_commit` | `product-source` |
| `backend/tests/test_run_football_external_soccernet_bounded_product_validation_execution_approval.py` | `??` | `product_source` | `preserve_commit` | `product-source` |
| `backend/tests/test_run_football_external_soccernet_bounded_product_validation_plan.py` | `??` | `product_source` | `preserve_commit` | `product-source` |
| `backend/tests/test_run_football_external_soccernet_bounded_product_validation_report_binding.py` | `??` | `product_source` | `preserve_commit` | `product-source` |
| `backend/tests/test_run_football_external_soccernet_broader_validation_choice.py` | `??` | `product_source` | `preserve_commit` | `product-source` |
| `backend/tests/test_run_football_external_soccernet_controlled_label_metadata_probe.py` | `??` | `product_source` | `preserve_commit` | `product-source` |
| `backend/tests/test_run_football_external_soccernet_controlled_label_sample_fetch.py` | `??` | `product_source` | `preserve_commit` | `product-source` |
| `backend/tests/test_run_football_external_soccernet_controlled_label_sample_fetch_approval.py` | `??` | `product_source` | `preserve_commit` | `product-source` |
| `backend/tests/test_run_football_external_soccernet_controlled_video_sample_fetch.py` | `??` | `product_source` | `preserve_commit` | `product-source` |
| `backend/tests/test_run_football_external_soccernet_detector_miss_capture_and_label_queue.py` | `??` | `product_source` | `preserve_commit` | `product-source` |
| `backend/tests/test_run_football_external_soccernet_detector_miss_manual_review_resolution.py` | `??` | `product_source` | `preserve_commit` | `product-source` |
| `backend/tests/test_run_football_external_soccernet_event_adapter_fixture_materialization.py` | `??` | `product_source` | `preserve_commit` | `product-source` |
| `backend/tests/test_run_football_external_soccernet_event_adapter_smoke_test.py` | `??` | `product_source` | `preserve_commit` | `product-source` |
| `backend/tests/test_run_football_external_soccernet_event_benchmark_smoke.py` | `??` | `product_source` | `preserve_commit` | `product-source` |
| `backend/tests/test_run_football_external_soccernet_event_lane_closeout.py` | `??` | `product_source` | `preserve_commit` | `product-source` |
| `backend/tests/test_run_football_external_soccernet_event_report_contract_prep.py` | `??` | `product_source` | `preserve_commit` | `product-source` |
| `backend/tests/test_run_football_external_soccernet_event_report_product_integration.py` | `??` | `product_source` | `preserve_commit` | `product-source` |
| `backend/tests/test_run_football_external_soccernet_event_report_smoke.py` | `??` | `product_source` | `preserve_commit` | `product-source` |
| `backend/tests/test_run_football_external_soccernet_full_analysis_execution.py` | `??` | `product_source` | `preserve_commit` | `product-source` |
| `backend/tests/test_run_football_external_soccernet_full_analysis_execution_approval.py` | `??` | `product_source` | `preserve_commit` | `product-source` |
| `backend/tests/test_run_football_external_soccernet_full_analysis_lane_closeout.py` | `??` | `product_source` | `preserve_commit` | `product-source` |
| `backend/tests/test_run_football_external_soccernet_full_analysis_product_integration.py` | `??` | `product_source` | `preserve_commit` | `product-source` |
| `backend/tests/test_run_football_external_soccernet_full_analysis_report_smoke.py` | `??` | `product_source` | `preserve_commit` | `product-source` |
| `backend/tests/test_run_football_external_soccernet_label_fetch_contract_repair.py` | `??` | `product_source` | `preserve_commit` | `product-source` |
| `backend/tests/test_run_football_external_soccernet_label_schema_ingestion_probe.py` | `??` | `product_source` | `preserve_commit` | `product-source` |
| `backend/tests/test_run_football_external_soccernet_nda_api_access_approval.py` | `??` | `product_source` | `preserve_commit` | `product-source` |
| `backend/tests/test_run_football_external_soccernet_real_sample_product_pipeline_training_decision.py` | `??` | `product_source` | `preserve_commit` | `product-source` |
| `backend/tests/test_run_football_external_soccernet_split_archive_access_review.py` | `??` | `product_source` | `preserve_commit` | `product-source` |
| `backend/tests/test_run_football_external_soccernet_split_archive_range_index_probe.py` | `??` | `product_source` | `preserve_commit` | `product-source` |
| `backend/tests/test_run_football_external_soccernet_split_archive_size_probe.py` | `??` | `product_source` | `preserve_commit` | `product-source` |
| `backend/tests/test_run_football_external_soccernet_video_analysis_dry_run.py` | `??` | `product_source` | `preserve_commit` | `product-source` |
| `backend/tests/test_run_football_external_soccernet_video_analysis_dry_run_approval.py` | `??` | `product_source` | `preserve_commit` | `product-source` |
| `backend/tests/test_run_football_external_soccernet_video_analysis_dry_run_product_bridge_smoke.py` | `??` | `product_source` | `preserve_commit` | `product-source` |
| `backend/tests/test_run_football_external_soccernet_video_frame_probe.py` | `??` | `product_source` | `preserve_commit` | `product-source` |
| `backend/tests/test_run_football_external_soccernet_video_member_extract.py` | `??` | `product_source` | `preserve_commit` | `product-source` |
| `backend/tests/test_run_football_external_soccernet_video_member_extract_approval.py` | `??` | `product_source` | `preserve_commit` | `product-source` |
| `backend/tests/test_run_football_external_soccernet_video_product_path_smoke.py` | `??` | `product_source` | `preserve_commit` | `product-source` |
| `backend/tests/test_run_football_external_soccernet_video_sample_download_approval.py` | `??` | `product_source` | `preserve_commit` | `product-source` |
| `backend/tests/test_run_football_external_soccernet_video_sample_probe.py` | `??` | `product_source` | `preserve_commit` | `product-source` |
| `backend/tests/test_run_football_external_soccernet_video_to_analysis_bridge_prep.py` | `??` | `product_source` | `preserve_commit` | `product-source` |
| `backend/tests/test_run_football_external_soccernet_zip_label_member_extract.py` | `??` | `product_source` | `preserve_commit` | `product-source` |
| `backend/tests/test_run_football_external_soccernet_zip_label_member_extract_approval.py` | `??` | `product_source` | `preserve_commit` | `product-source` |
| `backend/tests/test_run_football_external_soccertrack_adapter_smoke_test.py` | `??` | `product_source` | `preserve_commit` | `product-source` |
| `backend/tests/test_run_football_external_soccertrack_analysis_product_lane_closeout.py` | `??` | `product_source` | `preserve_commit` | `product-source` |
| `backend/tests/test_run_football_external_soccertrack_analysis_product_ui_binding.py` | `??` | `product_source` | `preserve_commit` | `product-source` |
| `backend/tests/test_run_football_external_soccertrack_analysis_product_ui_route_implementation.py` | `??` | `product_source` | `preserve_commit` | `product-source` |
| `backend/tests/test_run_football_external_soccertrack_analysis_report_smoke.py` | `??` | `product_source` | `preserve_commit` | `product-source` |
| `backend/tests/test_run_football_external_soccertrack_authenticated_fixture_access_approval.py` | `??` | `product_source` | `preserve_commit` | `product-source` |
| `backend/tests/test_run_football_external_soccertrack_controlled_sample_fetch.py` | `??` | `product_source` | `preserve_commit` | `product-source` |
| `backend/tests/test_run_football_external_soccertrack_fixture_source_access_review.py` | `??` | `product_source` | `preserve_commit` | `product-source` |
| `backend/tests/test_run_football_external_soccertrack_google_drive_bounded_fixture_fetch.py` | `??` | `product_source` | `preserve_commit` | `product-source` |
| `backend/tests/test_run_football_external_soccertrack_google_drive_fixture_access_probe.py` | `??` | `product_source` | `preserve_commit` | `product-source` |
| `backend/tests/test_run_football_external_soccertrack_lane_closeout.py` | `??` | `product_source` | `preserve_commit` | `product-source` |
| `backend/tests/test_run_football_external_soccertrack_match_bundle_bridge_smoke.py` | `??` | `product_source` | `preserve_commit` | `product-source` |
| `backend/tests/test_run_football_external_soccertrack_metadata_adapter_smoke.py` | `??` | `product_source` | `preserve_commit` | `product-source` |
| `backend/tests/test_run_football_external_soccertrack_product_route_smoke.py` | `??` | `product_source` | `preserve_commit` | `product-source` |
| `backend/tests/test_run_football_external_soccertrack_sample_fixture_materialization.py` | `??` | `product_source` | `preserve_commit` | `product-source` |
| `backend/tests/test_run_football_external_soccertrack_sample_fixture_materialization_approval.py` | `??` | `product_source` | `preserve_commit` | `product-source` |
| `backend/tests/test_run_football_external_soccertrack_sample_ingestion_contract_prep.py` | `??` | `product_source` | `preserve_commit` | `product-source` |
| `backend/tests/test_run_football_external_soccertrack_sample_schema_probe.py` | `??` | `product_source` | `preserve_commit` | `product-source` |
| `backend/tests/test_run_football_external_soccertrack_schema_doc_fetch.py` | `??` | `product_source` | `preserve_commit` | `product-source` |
| `backend/tests/test_run_football_external_soccertrack_schema_doc_fetch_approval.py` | `??` | `product_source` | `preserve_commit` | `product-source` |
| `backend/tests/test_run_football_external_soccertrack_schema_doc_parse.py` | `??` | `product_source` | `preserve_commit` | `product-source` |
| `backend/tests/test_run_product_video_to_analysis_finish_line_execution.py` | `??` | `product_source` | `preserve_commit` | `product-source` |
| `backend/tests/test_run_product_video_to_analysis_normal_storage_smoke.py` | `??` | `product_source` | `preserve_commit` | `product-source` |
| `backend/tests/test_run_product_video_to_analysis_smoke.py` | `??` | `product_source` | `preserve_commit` | `product-source` |
| `backend/tests/test_run_product_video_to_analysis_smoke_isolated.py` | `??` | `product_source` | `preserve_commit` | `product-source` |
| `backend/tests/test_run_v7_2_runtime_registry_product_path_binding.py` | `??` | `product_source` | `preserve_commit` | `product-source` |
| `backend/tests/test_run_v7_3_bounded_retrain.py` | `??` | `product_source` | `preserve_commit` | `product-source` |
| `backend/tests/test_run_v7_3_crop_probe_precision_guardrail_audit.py` | `??` | `product_source` | `preserve_commit` | `product-source` |
| `backend/tests/test_run_v7_3_export_label_overlay_audit.py` | `??` | `product_source` | `preserve_commit` | `product-source` |
| `backend/tests/test_run_v7_3_full_pipeline_non_promotion_eval.py` | `??` | `product_source` | `preserve_commit` | `product-source` |
| `backend/tests/test_run_v7_3_post_runtime_default_source_robustness_validation.py` | `??` | `product_source` | `preserve_commit` | `product-source` |
| `backend/tests/test_run_v7_3_promotion_readiness_validation.py` | `??` | `product_source` | `preserve_commit` | `product-source` |
| `backend/tests/test_run_v7_3_runtime_default_change_validation.py` | `??` | `product_source` | `preserve_commit` | `product-source` |
| `backend/tests/test_run_v7_3_runtime_default_rollout_closeout.py` | `??` | `product_source` | `preserve_commit` | `product-source` |
| `backend/tests/test_run_v7_3_training_manifest_prep_from_soccernet_real_misses.py` | `??` | `product_source` | `preserve_commit` | `product-source` |
| `backend/tests/test_run_v7_4_training_decision_from_real_misses.py` | `??` | `product_source` | `preserve_commit` | `product-source` |
| `backend/tests/test_run_video_to_analysis_acceptance_report_product_backlog.py` | `??` | `product_source` | `preserve_commit` | `product-source` |
| `backend/tests/test_run_video_to_analysis_acceptance_report_route_binding.py` | `??` | `product_source` | `preserve_commit` | `product-source` |
| `backend/tests/test_run_video_to_analysis_bounded_next_sample_execution_chain.py` | `??` | `product_source` | `preserve_commit` | `product-source` |
| `backend/tests/test_run_video_to_analysis_broader_real_video_acceptance_approval.py` | `??` | `product_source` | `preserve_commit` | `product-source` |
| `backend/tests/test_run_video_to_analysis_broader_real_video_acceptance_closeout.py` | `??` | `product_source` | `preserve_commit` | `product-source` |
| `backend/tests/test_run_video_to_analysis_broader_real_video_acceptance_execution.py` | `??` | `product_source` | `preserve_commit` | `product-source` |
| `backend/tests/test_run_video_to_analysis_broader_real_video_acceptance_suite_prep.py` | `??` | `product_source` | `preserve_commit` | `product-source` |
| `backend/tests/test_run_video_to_analysis_current_release_acceptance_decision_surface.py` | `??` | `product_source` | `preserve_commit` | `product-source` |
| `backend/tests/test_run_video_to_analysis_detector_evaluation_reentry_chain.py` | `??` | `product_source` | `preserve_commit` | `product-source` |
| `backend/tests/test_run_video_to_analysis_finish_line_closeout_chain.py` | `??` | `product_source` | `preserve_commit` | `product-source` |
| `backend/tests/test_run_video_to_analysis_finish_line_completion_summary.py` | `??` | `product_source` | `preserve_commit` | `product-source` |
| `backend/tests/test_run_video_to_analysis_finish_line_execution_approval.py` | `??` | `product_source` | `preserve_commit` | `product-source` |
| `backend/tests/test_run_video_to_analysis_finish_line_normal_storage_closeout.py` | `??` | `product_source` | `preserve_commit` | `product-source` |
| `backend/tests/test_run_video_to_analysis_finish_line_normal_storage_execution_approval.py` | `??` | `product_source` | `preserve_commit` | `product-source` |
| `backend/tests/test_run_video_to_analysis_finish_line_operational_readiness.py` | `??` | `product_source` | `preserve_commit` | `product-source` |
| `backend/tests/test_run_video_to_analysis_finish_line_product_acceptance_closeout.py` | `??` | `product_source` | `preserve_commit` | `product-source` |
| `backend/tests/test_run_video_to_analysis_finish_line_product_execution_approval.py` | `??` | `product_source` | `preserve_commit` | `product-source` |
| `backend/tests/test_run_video_to_analysis_finish_line_route_polish.py` | `??` | `product_source` | `preserve_commit` | `product-source` |
| `backend/tests/test_run_video_to_analysis_finish_line_user_acceptance_trial.py` | `??` | `product_source` | `preserve_commit` | `product-source` |
| `backend/tests/test_run_video_to_analysis_growth_lane_closeout_readout.py` | `??` | `product_source` | `preserve_commit` | `product-source` |
| `backend/tests/test_run_video_to_analysis_manual_operator_release_decision.py` | `??` | `product_source` | `preserve_commit` | `product-source` |
| `backend/tests/test_run_video_to_analysis_next_strategic_lane_selection.py` | `??` | `product_source` | `preserve_commit` | `product-source` |
| `backend/tests/test_run_video_to_analysis_operational_backlog_prioritization.py` | `??` | `product_source` | `preserve_commit` | `product-source` |
| `backend/tests/test_run_video_to_analysis_operational_roadmap_sprint.py` | `??` | `product_source` | `preserve_commit` | `product-source` |
| `backend/tests/test_run_video_to_analysis_operator_dashboard_polish.py` | `??` | `product_source` | `preserve_commit` | `product-source` |
| `backend/tests/test_run_video_to_analysis_operator_handoff_pack.py` | `??` | `product_source` | `preserve_commit` | `product-source` |
| `backend/tests/test_run_video_to_analysis_operator_handoff_route_binding.py` | `??` | `product_source` | `preserve_commit` | `product-source` |
| `backend/tests/test_run_video_to_analysis_post_release_monitoring_closeout.py` | `??` | `product_source` | `preserve_commit` | `product-source` |
| `backend/tests/test_run_video_to_analysis_post_release_monitoring_plan.py` | `??` | `product_source` | `preserve_commit` | `product-source` |
| `backend/tests/test_run_video_to_analysis_post_release_monitoring_route_binding.py` | `??` | `product_source` | `preserve_commit` | `product-source` |
| `backend/tests/test_run_video_to_analysis_product_hardening_backlog.py` | `??` | `product_source` | `preserve_commit` | `product-source` |
| `backend/tests/test_run_video_to_analysis_product_lane_closeout.py` | `??` | `product_source` | `preserve_commit` | `product-source` |
| `backend/tests/test_run_video_to_analysis_promoted_runtime_operator_acceptance_trial.py` | `??` | `product_source` | `preserve_commit` | `product-source` |
| `backend/tests/test_run_video_to_analysis_promoted_runtime_post_release_monitoring_chain.py` | `??` | `product_source` | `preserve_commit` | `product-source` |
| `backend/tests/test_run_video_to_analysis_promoted_runtime_release_closeout_chain.py` | `??` | `product_source` | `preserve_commit` | `product-source` |
| `backend/tests/test_run_video_to_analysis_promotion_review_chain.py` | `??` | `product_source` | `preserve_commit` | `product-source` |
| `backend/tests/test_run_video_to_analysis_real_video_scaleout_execution_chain.py` | `??` | `product_source` | `preserve_commit` | `product-source` |
| `backend/tests/test_run_video_to_analysis_release_acceptance_archive.py` | `??` | `product_source` | `preserve_commit` | `product-source` |
| `backend/tests/test_run_video_to_analysis_release_candidate_closeout.py` | `??` | `product_source` | `preserve_commit` | `product-source` |
| `backend/tests/test_run_video_to_analysis_release_readout_pack.py` | `??` | `product_source` | `preserve_commit` | `product-source` |
| `backend/tests/test_run_video_to_analysis_release_readout_route_binding.py` | `??` | `product_source` | `preserve_commit` | `product-source` |
| `backend/tests/test_run_video_to_analysis_roadmap_state_reconciliation.py` | `??` | `product_source` | `preserve_commit` | `product-source` |
| `backend/tests/test_run_video_to_analysis_source_pool_replenishment_plan.py` | `??` | `product_source` | `preserve_commit` | `product-source` |
| `backend/tests/test_run_video_to_analysis_steady_state_monitoring_cycle.py` | `??` | `product_source` | `preserve_commit` | `product-source` |
| `backend/tests/test_run_video_to_analysis_storage_cleanup_approval.py` | `??` | `product_source` | `preserve_commit` | `product-source` |
| `backend/tests/test_run_video_to_analysis_storage_cleanup_bounded_execution.py` | `??` | `product_source` | `preserve_commit` | `product-source` |
| `backend/tests/test_run_video_to_analysis_storage_cleanup_closeout.py` | `??` | `product_source` | `preserve_commit` | `product-source` |
| `backend/tests/test_run_video_to_analysis_storage_cleanup_dry_run_execution.py` | `??` | `product_source` | `preserve_commit` | `product-source` |
| `backend/tests/test_run_video_to_analysis_storage_cleanup_execution_approval.py` | `??` | `product_source` | `preserve_commit` | `product-source` |
| `backend/tests/test_run_video_to_analysis_storage_retention_and_artifact_hygiene.py` | `??` | `product_source` | `preserve_commit` | `product-source` |
| `backend/tests/test_run_video_to_analysis_upload_to_analysis_walkthrough.py` | `??` | `product_source` | `preserve_commit` | `product-source` |
| `backend/tests/test_run_video_to_analysis_user_facing_release_readout.py` | `??` | `product_source` | `preserve_commit` | `product-source` |
| `backend/tests/test_run_video_to_analysis_v7_3_release_packaging_and_worktree_triage.py` | `??` | `product_source` | `preserve_commit` | `product-source` |
| `backend/tests/test_runpod.py` | ` M` | `product_source` | `preserve_commit` | `product-source` |
| `backend/tests/test_runpod_handler.py` | ` M` | `product_source` | `preserve_commit` | `product-source` |
| `backend/tests/test_runpod_worker.py` | ` M` | `product_source` | `preserve_commit` | `product-source` |
| `backend/tests/test_serve_football_external_soccernet_detector_miss_review_ui.py` | `??` | `product_source` | `preserve_commit` | `product-source` |
| `docs/foot-soccer-deepresearch.md` | `??` | `manual_review` | `manual_review` | `manual-review` |
| `docs/goal-1-12april-00-1am.md` | `??` | `manual_review` | `manual_review` | `manual-review` |
| `docs/project-review-2026-07-06.md` | `??` | `manual_review` | `manual_review` | `manual-review` |
| `docs/superpowers/plans/2026-05-04-canonical-match-bundle-export.md` | `??` | `reusable_workflow` | `preserve_commit` | `workflow` |
| `docs/superpowers/plans/2026-05-04-football-external-soccernet-api-listing-probe.md` | `??` | `reusable_workflow` | `preserve_commit` | `workflow` |
| `docs/superpowers/plans/2026-05-04-football-external-soccernet-benchmark-adapter-contract-prep.md` | `??` | `reusable_workflow` | `preserve_commit` | `workflow` |
| `docs/superpowers/plans/2026-05-04-football-external-soccernet-bounded-analysis-execution-approval.md` | `??` | `reusable_workflow` | `preserve_commit` | `workflow` |
| `docs/superpowers/plans/2026-05-04-football-external-soccernet-bounded-analysis-execution.md` | `??` | `reusable_workflow` | `preserve_commit` | `workflow` |
| `docs/superpowers/plans/2026-05-04-football-external-soccernet-bounded-analysis-lane-closeout.md` | `??` | `reusable_workflow` | `preserve_commit` | `workflow` |
| `docs/superpowers/plans/2026-05-04-football-external-soccernet-bounded-analysis-report-smoke.md` | `??` | `reusable_workflow` | `preserve_commit` | `workflow` |
| `docs/superpowers/plans/2026-05-04-football-external-soccernet-controlled-label-metadata-probe.md` | `??` | `reusable_workflow` | `preserve_commit` | `workflow` |
| `docs/superpowers/plans/2026-05-04-football-external-soccernet-controlled-video-sample-fetch.md` | `??` | `reusable_workflow` | `preserve_commit` | `workflow` |
| `docs/superpowers/plans/2026-05-04-football-external-soccernet-event-adapter-smoke-test.md` | `??` | `reusable_workflow` | `preserve_commit` | `workflow` |
| `docs/superpowers/plans/2026-05-04-football-external-soccernet-event-benchmark-smoke.md` | `??` | `reusable_workflow` | `preserve_commit` | `workflow` |
| `docs/superpowers/plans/2026-05-04-football-external-soccernet-event-lane-closeout.md` | `??` | `reusable_workflow` | `preserve_commit` | `workflow` |
| `docs/superpowers/plans/2026-05-04-football-external-soccernet-event-report-product-integration.md` | `??` | `reusable_workflow` | `preserve_commit` | `workflow` |
| `docs/superpowers/plans/2026-05-04-football-external-soccernet-event-report-smoke.md` | `??` | `reusable_workflow` | `preserve_commit` | `workflow` |
| `docs/superpowers/plans/2026-05-04-football-external-soccernet-full-analysis-execution-approval.md` | `??` | `reusable_workflow` | `preserve_commit` | `workflow` |
| `docs/superpowers/plans/2026-05-04-football-external-soccernet-full-analysis-execution.md` | `??` | `reusable_workflow` | `preserve_commit` | `workflow` |
| `docs/superpowers/plans/2026-05-04-football-external-soccernet-full-analysis-lane-closeout.md` | `??` | `reusable_workflow` | `preserve_commit` | `workflow` |
| `docs/superpowers/plans/2026-05-04-football-external-soccernet-full-analysis-report-smoke.md` | `??` | `reusable_workflow` | `preserve_commit` | `workflow` |
| `docs/superpowers/plans/2026-05-04-football-external-soccernet-label-fetch-contract-repair.md` | `??` | `reusable_workflow` | `preserve_commit` | `workflow` |
| `docs/superpowers/plans/2026-05-04-football-external-soccernet-label-member-range-pipeline.md` | `??` | `reusable_workflow` | `preserve_commit` | `workflow` |
| `docs/superpowers/plans/2026-05-04-football-external-soccernet-split-archive-access-review.md` | `??` | `reusable_workflow` | `preserve_commit` | `workflow` |
| `docs/superpowers/plans/2026-05-04-football-external-soccernet-video-analysis-dry-run-approval.md` | `??` | `reusable_workflow` | `preserve_commit` | `workflow` |
| `docs/superpowers/plans/2026-05-04-football-external-soccernet-video-analysis-dry-run-product-bridge-smoke.md` | `??` | `reusable_workflow` | `preserve_commit` | `workflow` |
| `docs/superpowers/plans/2026-05-04-football-external-soccernet-video-analysis-dry-run.md` | `??` | `reusable_workflow` | `preserve_commit` | `workflow` |
| `docs/superpowers/plans/2026-05-04-football-external-soccernet-video-frame-probe.md` | `??` | `reusable_workflow` | `preserve_commit` | `workflow` |
| `docs/superpowers/plans/2026-05-04-football-external-soccernet-video-member-extract-approval.md` | `??` | `reusable_workflow` | `preserve_commit` | `workflow` |
| `docs/superpowers/plans/2026-05-04-football-external-soccernet-video-member-extract.md` | `??` | `reusable_workflow` | `preserve_commit` | `workflow` |
| `docs/superpowers/plans/2026-05-04-football-external-soccernet-video-product-path-smoke.md` | `??` | `reusable_workflow` | `preserve_commit` | `workflow` |
| `docs/superpowers/plans/2026-05-04-football-external-soccernet-video-sample-download-approval.md` | `??` | `reusable_workflow` | `preserve_commit` | `workflow` |
| `docs/superpowers/plans/2026-05-04-football-external-soccernet-video-sample-probe.md` | `??` | `reusable_workflow` | `preserve_commit` | `workflow` |
| `docs/superpowers/plans/2026-05-04-football-external-soccernet-video-to-analysis-bridge-prep.md` | `??` | `reusable_workflow` | `preserve_commit` | `workflow` |
| `docs/superpowers/plans/2026-05-04-product-video-to-analysis-smoke.md` | `??` | `reusable_workflow` | `preserve_commit` | `workflow` |
| `docs/superpowers/plans/2026-05-04-v7-2-runtime-registry-product-path-binding.md` | `??` | `reusable_workflow` | `preserve_commit` | `workflow` |
| `docs/superpowers/plans/2026-05-05-football-external-benchmark-bounded-execution-smoke.md` | `??` | `reusable_workflow` | `preserve_commit` | `workflow` |
| `docs/superpowers/plans/2026-05-05-football-external-benchmark-execution-approval.md` | `??` | `reusable_workflow` | `preserve_commit` | `workflow` |
| `docs/superpowers/plans/2026-05-05-football-external-benchmark-harness-prep.md` | `??` | `reusable_workflow` | `preserve_commit` | `workflow` |
| `docs/superpowers/plans/2026-05-05-football-external-benchmark-harness-smoke.md` | `??` | `reusable_workflow` | `preserve_commit` | `workflow` |
| `docs/superpowers/plans/2026-05-05-football-external-benchmark-lane-closeout.md` | `??` | `reusable_workflow` | `preserve_commit` | `workflow` |
| `docs/superpowers/plans/2026-05-05-football-external-benchmark-operationalization-plan.md` | `??` | `reusable_workflow` | `preserve_commit` | `workflow` |
| `docs/superpowers/plans/2026-05-05-football-external-benchmark-product-decision-route-implementation.md` | `??` | `reusable_workflow` | `preserve_commit` | `workflow` |
| `docs/superpowers/plans/2026-05-05-football-external-benchmark-product-decision-surface.md` | `??` | `reusable_workflow` | `preserve_commit` | `workflow` |
| `docs/superpowers/plans/2026-05-05-football-external-benchmark-product-ui-binding.md` | `??` | `reusable_workflow` | `preserve_commit` | `workflow` |
| `docs/superpowers/plans/2026-05-05-football-external-benchmark-product-ui-route-implementation.md` | `??` | `reusable_workflow` | `preserve_commit` | `workflow` |
| `docs/superpowers/plans/2026-05-05-football-external-benchmark-real-evaluation-chain.md` | `??` | `reusable_workflow` | `preserve_commit` | `workflow` |
| `docs/superpowers/plans/2026-05-05-football-external-benchmark-real-evaluation-design.md` | `??` | `reusable_workflow` | `preserve_commit` | `workflow` |
| `docs/superpowers/plans/2026-05-05-football-external-benchmark-report-smoke.md` | `??` | `reusable_workflow` | `preserve_commit` | `workflow` |
| `docs/superpowers/plans/2026-05-05-football-external-soccernet-analysis-product-lane-closeout.md` | `??` | `reusable_workflow` | `preserve_commit` | `workflow` |
| `docs/superpowers/plans/2026-05-05-football-external-soccernet-analysis-product-ui-route-implementation.md` | `??` | `reusable_workflow` | `preserve_commit` | `workflow` |
| `docs/superpowers/plans/2026-05-05-football-external-soccernet-full-analysis-product-integration.md` | `??` | `reusable_workflow` | `preserve_commit` | `workflow` |
| `docs/superpowers/plans/2026-05-05-football-external-soccertrack-authenticated-fixture-access-approval.md` | `??` | `reusable_workflow` | `preserve_commit` | `workflow` |
| `docs/superpowers/plans/2026-05-05-football-external-soccertrack-controlled-sample-fetch.md` | `??` | `reusable_workflow` | `preserve_commit` | `workflow` |
| `docs/superpowers/plans/2026-05-05-football-external-soccertrack-fixture-source-access-review.md` | `??` | `reusable_workflow` | `preserve_commit` | `workflow` |
| `docs/superpowers/plans/2026-05-05-football-external-soccertrack-sample-fixture-materialization-approval.md` | `??` | `reusable_workflow` | `preserve_commit` | `workflow` |
| `docs/superpowers/plans/2026-05-05-football-external-soccertrack-sample-ingestion-contract-prep.md` | `??` | `reusable_workflow` | `preserve_commit` | `workflow` |
| `docs/superpowers/plans/2026-05-05-football-external-soccertrack-sample-schema-probe.md` | `??` | `reusable_workflow` | `preserve_commit` | `workflow` |
| `docs/superpowers/plans/2026-05-05-football-external-soccertrack-schema-doc-fetch-approval.md` | `??` | `reusable_workflow` | `preserve_commit` | `workflow` |
| `docs/superpowers/plans/2026-05-05-football-external-soccertrack-schema-doc-fetch.md` | `??` | `reusable_workflow` | `preserve_commit` | `workflow` |
| `docs/superpowers/plans/2026-05-05-football-external-soccertrack-schema-doc-parse.md` | `??` | `reusable_workflow` | `preserve_commit` | `workflow` |
| `docs/superpowers/plans/2026-05-05-housekeeping-direction-snapshot.md` | `??` | `reusable_workflow` | `preserve_commit` | `workflow` |
| `docs/superpowers/plans/2026-05-09-video-to-analysis-growth-lane-finish-roadmap.md` | `??` | `reusable_workflow` | `preserve_commit` | `workflow` |
| `docs/superpowers/plans/2026-05-09-video-to-analysis-strategic-lane-priority-plan.md` | `??` | `reusable_workflow` | `preserve_commit` | `workflow` |
| `docs/superpowers/plans/2026-05-10-soccernet-real-sample-training-decision-cascade.md` | `??` | `reusable_workflow` | `preserve_commit` | `workflow` |
| `docs/superpowers/plans/2026-05-11-codex-goal-autonomous-video-to-analysis-growth-marathon.md` | `??` | `reusable_workflow` | `preserve_commit` | `workflow` |
| `docs/superpowers/plans/2026-05-11-codex-goal-video-to-analysis-bounded-chain-continuation.md` | `??` | `reusable_workflow` | `preserve_commit` | `workflow` |
| `docs/superpowers/plans/2026-05-11-codex-goal-video-to-analysis-finishline-push.md` | `??` | `reusable_workflow` | `preserve_commit` | `workflow` |
| `docs/superpowers/plans/2026-05-11-codex-goal-video-to-analysis-scaleout-followup-marathon.md` | `??` | `reusable_workflow` | `preserve_commit` | `workflow` |
| `docs/superpowers/plans/2026-05-11-codex-goal-video-to-analysis-total-finishline.md` | `??` | `reusable_workflow` | `preserve_commit` | `workflow` |
| `docs/video-to-analysis-finish-line-roadmap-completion-report-2026-05-08.md` | `??` | `manual_review` | `manual_review` | `manual-review` |
| `docs/video-to-analysis-finish-line-roadmap-guide.md` | `??` | `manual_review` | `manual_review` | `manual-review` |
| `docs/video-to-analysis-growth-lane-closeout-readout-2026-05-09.md` | `??` | `manual_review` | `manual_review` | `manual-review` |
| `docs/video-to-analysis-user-facing-release-readout-2026-05-09.md` | `??` | `manual_review` | `manual_review` | `manual-review` |
| `memorybank/activeContext.md` | ` M` | `essential_release_truth` | `preserve_commit` | `release-truth` |
| `memorybank/currentRoadmap.md` | ` M` | `essential_release_truth` | `preserve_commit` | `release-truth` |
| `memorybank/progress.md` | ` M` | `essential_release_truth` | `preserve_commit` | `release-truth` |

## Reference relationships

- `backend/tests/test_run_canonical_match_bundle_export.py` tests `backend/scripts/run_canonical_match_bundle_export.py` (matching dirty test and source path names)
- `backend/tests/test_run_football_external_benchmark_bounded_execution_smoke.py` tests `backend/scripts/run_football_external_benchmark_bounded_execution_smoke.py` (matching dirty test and source path names)
- `backend/tests/test_run_football_external_benchmark_execution_approval.py` tests `backend/scripts/run_football_external_benchmark_execution_approval.py` (matching dirty test and source path names)
- `backend/tests/test_run_football_external_benchmark_harness_prep.py` tests `backend/scripts/run_football_external_benchmark_harness_prep.py` (matching dirty test and source path names)
- `backend/tests/test_run_football_external_benchmark_harness_smoke.py` tests `backend/scripts/run_football_external_benchmark_harness_smoke.py` (matching dirty test and source path names)
- `backend/tests/test_run_football_external_benchmark_lane_closeout.py` tests `backend/scripts/run_football_external_benchmark_lane_closeout.py` (matching dirty test and source path names)
- `backend/tests/test_run_football_external_benchmark_operationalization_plan.py` tests `backend/scripts/run_football_external_benchmark_operationalization_plan.py` (matching dirty test and source path names)
- `backend/tests/test_run_football_external_benchmark_product_decision_surface.py` tests `backend/scripts/run_football_external_benchmark_product_decision_surface.py` (matching dirty test and source path names)
- `backend/tests/test_run_football_external_benchmark_product_decision_surface_route_implementation.py` tests `backend/scripts/run_football_external_benchmark_product_decision_surface_route_implementation.py` (matching dirty test and source path names)
- `backend/tests/test_run_football_external_benchmark_product_ui_binding.py` tests `backend/scripts/run_football_external_benchmark_product_ui_binding.py` (matching dirty test and source path names)
- `backend/tests/test_run_football_external_benchmark_product_ui_route_implementation.py` tests `backend/scripts/run_football_external_benchmark_product_ui_route_implementation.py` (matching dirty test and source path names)
- `backend/tests/test_run_football_external_benchmark_real_evaluation_design.py` tests `backend/scripts/run_football_external_benchmark_real_evaluation_design.py` (matching dirty test and source path names)
- `backend/tests/test_run_football_external_benchmark_report_smoke.py` tests `backend/scripts/run_football_external_benchmark_report_smoke.py` (matching dirty test and source path names)
- `backend/tests/test_run_football_external_safe_adapter_fixture_implementation.py` tests `backend/scripts/run_football_external_safe_adapter_fixture_implementation.py` (matching dirty test and source path names)
- `backend/tests/test_run_football_external_safe_source_adapter_smoke_test.py` tests `backend/scripts/run_football_external_safe_source_adapter_smoke_test.py` (matching dirty test and source path names)
- `backend/tests/test_run_football_external_safe_source_controlled_sample_fetch.py` tests `backend/scripts/run_football_external_safe_source_controlled_sample_fetch.py` (matching dirty test and source path names)
- `backend/tests/test_run_football_external_safe_source_sample_download_approval.py` tests `backend/scripts/run_football_external_safe_source_sample_download_approval.py` (matching dirty test and source path names)
- `backend/tests/test_run_football_external_safe_source_sample_ingestion_plan.py` tests `backend/scripts/run_football_external_safe_source_sample_ingestion_plan.py` (matching dirty test and source path names)
- `backend/tests/test_run_football_external_soccernet_analysis_product_api_smoke.py` tests `backend/scripts/run_football_external_soccernet_analysis_product_api_smoke.py` (matching dirty test and source path names)
- `backend/tests/test_run_football_external_soccernet_analysis_product_lane_closeout.py` tests `backend/scripts/run_football_external_soccernet_analysis_product_lane_closeout.py` (matching dirty test and source path names)
- `backend/tests/test_run_football_external_soccernet_analysis_product_ui_binding.py` tests `backend/scripts/run_football_external_soccernet_analysis_product_ui_binding.py` (matching dirty test and source path names)
- `backend/tests/test_run_football_external_soccernet_analysis_product_ui_route_implementation.py` tests `backend/scripts/run_football_external_soccernet_analysis_product_ui_route_implementation.py` (matching dirty test and source path names)
- `backend/tests/test_run_football_external_soccernet_api_listing_probe.py` tests `backend/scripts/run_football_external_soccernet_api_listing_probe.py` (matching dirty test and source path names)
- `backend/tests/test_run_football_external_soccernet_api_metadata_probe.py` tests `backend/scripts/run_football_external_soccernet_api_metadata_probe.py` (matching dirty test and source path names)
- `backend/tests/test_run_football_external_soccernet_benchmark_adapter_contract_prep.py` tests `backend/scripts/run_football_external_soccernet_benchmark_adapter_contract_prep.py` (matching dirty test and source path names)
- `backend/tests/test_run_football_external_soccernet_bounded_analysis_execution.py` tests `backend/scripts/run_football_external_soccernet_bounded_analysis_execution.py` (matching dirty test and source path names)
- `backend/tests/test_run_football_external_soccernet_bounded_analysis_execution_approval.py` tests `backend/scripts/run_football_external_soccernet_bounded_analysis_execution_approval.py` (matching dirty test and source path names)
- `backend/tests/test_run_football_external_soccernet_bounded_analysis_lane_closeout.py` tests `backend/scripts/run_football_external_soccernet_bounded_analysis_lane_closeout.py` (matching dirty test and source path names)
- `backend/tests/test_run_football_external_soccernet_bounded_analysis_report_smoke.py` tests `backend/scripts/run_football_external_soccernet_bounded_analysis_report_smoke.py` (matching dirty test and source path names)
- `backend/tests/test_run_football_external_soccernet_bounded_product_validation_execution.py` tests `backend/scripts/run_football_external_soccernet_bounded_product_validation_execution.py` (matching dirty test and source path names)
- `backend/tests/test_run_football_external_soccernet_bounded_product_validation_execution_approval.py` tests `backend/scripts/run_football_external_soccernet_bounded_product_validation_execution_approval.py` (matching dirty test and source path names)
- `backend/tests/test_run_football_external_soccernet_bounded_product_validation_plan.py` tests `backend/scripts/run_football_external_soccernet_bounded_product_validation_plan.py` (matching dirty test and source path names)
- `backend/tests/test_run_football_external_soccernet_bounded_product_validation_report_binding.py` tests `backend/scripts/run_football_external_soccernet_bounded_product_validation_report_binding.py` (matching dirty test and source path names)
- `backend/tests/test_run_football_external_soccernet_broader_validation_choice.py` tests `backend/scripts/run_football_external_soccernet_broader_validation_choice.py` (matching dirty test and source path names)
- `backend/tests/test_run_football_external_soccernet_controlled_label_metadata_probe.py` tests `backend/scripts/run_football_external_soccernet_controlled_label_metadata_probe.py` (matching dirty test and source path names)
- `backend/tests/test_run_football_external_soccernet_controlled_label_sample_fetch.py` tests `backend/scripts/run_football_external_soccernet_controlled_label_sample_fetch.py` (matching dirty test and source path names)
- `backend/tests/test_run_football_external_soccernet_controlled_label_sample_fetch_approval.py` tests `backend/scripts/run_football_external_soccernet_controlled_label_sample_fetch_approval.py` (matching dirty test and source path names)
- `backend/tests/test_run_football_external_soccernet_controlled_video_sample_fetch.py` tests `backend/scripts/run_football_external_soccernet_controlled_video_sample_fetch.py` (matching dirty test and source path names)
- `backend/tests/test_run_football_external_soccernet_detector_miss_capture_and_label_queue.py` tests `backend/scripts/run_football_external_soccernet_detector_miss_capture_and_label_queue.py` (matching dirty test and source path names)
- `backend/tests/test_run_football_external_soccernet_detector_miss_manual_review_resolution.py` tests `backend/scripts/run_football_external_soccernet_detector_miss_manual_review_resolution.py` (matching dirty test and source path names)
- `backend/tests/test_run_football_external_soccernet_event_adapter_fixture_materialization.py` tests `backend/scripts/run_football_external_soccernet_event_adapter_fixture_materialization.py` (matching dirty test and source path names)
- `backend/tests/test_run_football_external_soccernet_event_adapter_smoke_test.py` tests `backend/scripts/run_football_external_soccernet_event_adapter_smoke_test.py` (matching dirty test and source path names)
- `backend/tests/test_run_football_external_soccernet_event_benchmark_smoke.py` tests `backend/scripts/run_football_external_soccernet_event_benchmark_smoke.py` (matching dirty test and source path names)
- `backend/tests/test_run_football_external_soccernet_event_lane_closeout.py` tests `backend/scripts/run_football_external_soccernet_event_lane_closeout.py` (matching dirty test and source path names)
- `backend/tests/test_run_football_external_soccernet_event_report_contract_prep.py` tests `backend/scripts/run_football_external_soccernet_event_report_contract_prep.py` (matching dirty test and source path names)
- `backend/tests/test_run_football_external_soccernet_event_report_product_integration.py` tests `backend/scripts/run_football_external_soccernet_event_report_product_integration.py` (matching dirty test and source path names)
- `backend/tests/test_run_football_external_soccernet_event_report_smoke.py` tests `backend/scripts/run_football_external_soccernet_event_report_smoke.py` (matching dirty test and source path names)
- `backend/tests/test_run_football_external_soccernet_full_analysis_execution.py` tests `backend/scripts/run_football_external_soccernet_full_analysis_execution.py` (matching dirty test and source path names)
- `backend/tests/test_run_football_external_soccernet_full_analysis_execution_approval.py` tests `backend/scripts/run_football_external_soccernet_full_analysis_execution_approval.py` (matching dirty test and source path names)
- `backend/tests/test_run_football_external_soccernet_full_analysis_lane_closeout.py` tests `backend/scripts/run_football_external_soccernet_full_analysis_lane_closeout.py` (matching dirty test and source path names)
- `backend/tests/test_run_football_external_soccernet_full_analysis_product_integration.py` tests `backend/scripts/run_football_external_soccernet_full_analysis_product_integration.py` (matching dirty test and source path names)
- `backend/tests/test_run_football_external_soccernet_full_analysis_report_smoke.py` tests `backend/scripts/run_football_external_soccernet_full_analysis_report_smoke.py` (matching dirty test and source path names)
- `backend/tests/test_run_football_external_soccernet_label_fetch_contract_repair.py` tests `backend/scripts/run_football_external_soccernet_label_fetch_contract_repair.py` (matching dirty test and source path names)
- `backend/tests/test_run_football_external_soccernet_label_schema_ingestion_probe.py` tests `backend/scripts/run_football_external_soccernet_label_schema_ingestion_probe.py` (matching dirty test and source path names)
- `backend/tests/test_run_football_external_soccernet_nda_api_access_approval.py` tests `backend/scripts/run_football_external_soccernet_nda_api_access_approval.py` (matching dirty test and source path names)
- `backend/tests/test_run_football_external_soccernet_real_sample_product_pipeline_training_decision.py` tests `backend/scripts/run_football_external_soccernet_real_sample_product_pipeline_training_decision.py` (matching dirty test and source path names)
- `backend/tests/test_run_football_external_soccernet_split_archive_access_review.py` tests `backend/scripts/run_football_external_soccernet_split_archive_access_review.py` (matching dirty test and source path names)
- `backend/tests/test_run_football_external_soccernet_split_archive_range_index_probe.py` tests `backend/scripts/run_football_external_soccernet_split_archive_range_index_probe.py` (matching dirty test and source path names)
- `backend/tests/test_run_football_external_soccernet_split_archive_size_probe.py` tests `backend/scripts/run_football_external_soccernet_split_archive_size_probe.py` (matching dirty test and source path names)
- `backend/tests/test_run_football_external_soccernet_video_analysis_dry_run.py` tests `backend/scripts/run_football_external_soccernet_video_analysis_dry_run.py` (matching dirty test and source path names)
- `backend/tests/test_run_football_external_soccernet_video_analysis_dry_run_approval.py` tests `backend/scripts/run_football_external_soccernet_video_analysis_dry_run_approval.py` (matching dirty test and source path names)
- `backend/tests/test_run_football_external_soccernet_video_analysis_dry_run_product_bridge_smoke.py` tests `backend/scripts/run_football_external_soccernet_video_analysis_dry_run_product_bridge_smoke.py` (matching dirty test and source path names)
- `backend/tests/test_run_football_external_soccernet_video_frame_probe.py` tests `backend/scripts/run_football_external_soccernet_video_frame_probe.py` (matching dirty test and source path names)
- `backend/tests/test_run_football_external_soccernet_video_member_extract.py` tests `backend/scripts/run_football_external_soccernet_video_member_extract.py` (matching dirty test and source path names)
- `backend/tests/test_run_football_external_soccernet_video_member_extract_approval.py` tests `backend/scripts/run_football_external_soccernet_video_member_extract_approval.py` (matching dirty test and source path names)
- `backend/tests/test_run_football_external_soccernet_video_product_path_smoke.py` tests `backend/scripts/run_football_external_soccernet_video_product_path_smoke.py` (matching dirty test and source path names)
- `backend/tests/test_run_football_external_soccernet_video_sample_download_approval.py` tests `backend/scripts/run_football_external_soccernet_video_sample_download_approval.py` (matching dirty test and source path names)
- `backend/tests/test_run_football_external_soccernet_video_sample_probe.py` tests `backend/scripts/run_football_external_soccernet_video_sample_probe.py` (matching dirty test and source path names)
- `backend/tests/test_run_football_external_soccernet_video_to_analysis_bridge_prep.py` tests `backend/scripts/run_football_external_soccernet_video_to_analysis_bridge_prep.py` (matching dirty test and source path names)
- `backend/tests/test_run_football_external_soccernet_zip_label_member_extract.py` tests `backend/scripts/run_football_external_soccernet_zip_label_member_extract.py` (matching dirty test and source path names)
- `backend/tests/test_run_football_external_soccernet_zip_label_member_extract_approval.py` tests `backend/scripts/run_football_external_soccernet_zip_label_member_extract_approval.py` (matching dirty test and source path names)
- `backend/tests/test_run_football_external_soccertrack_adapter_smoke_test.py` tests `backend/scripts/run_football_external_soccertrack_adapter_smoke_test.py` (matching dirty test and source path names)
- `backend/tests/test_run_football_external_soccertrack_analysis_product_lane_closeout.py` tests `backend/scripts/run_football_external_soccertrack_analysis_product_lane_closeout.py` (matching dirty test and source path names)
- `backend/tests/test_run_football_external_soccertrack_analysis_product_ui_binding.py` tests `backend/scripts/run_football_external_soccertrack_analysis_product_ui_binding.py` (matching dirty test and source path names)
- `backend/tests/test_run_football_external_soccertrack_analysis_product_ui_route_implementation.py` tests `backend/scripts/run_football_external_soccertrack_analysis_product_ui_route_implementation.py` (matching dirty test and source path names)
- `backend/tests/test_run_football_external_soccertrack_analysis_report_smoke.py` tests `backend/scripts/run_football_external_soccertrack_analysis_report_smoke.py` (matching dirty test and source path names)
- `backend/tests/test_run_football_external_soccertrack_authenticated_fixture_access_approval.py` tests `backend/scripts/run_football_external_soccertrack_authenticated_fixture_access_approval.py` (matching dirty test and source path names)
- `backend/tests/test_run_football_external_soccertrack_controlled_sample_fetch.py` tests `backend/scripts/run_football_external_soccertrack_controlled_sample_fetch.py` (matching dirty test and source path names)
- `backend/tests/test_run_football_external_soccertrack_fixture_source_access_review.py` tests `backend/scripts/run_football_external_soccertrack_fixture_source_access_review.py` (matching dirty test and source path names)
- `backend/tests/test_run_football_external_soccertrack_google_drive_bounded_fixture_fetch.py` tests `backend/scripts/run_football_external_soccertrack_google_drive_bounded_fixture_fetch.py` (matching dirty test and source path names)
- `backend/tests/test_run_football_external_soccertrack_google_drive_fixture_access_probe.py` tests `backend/scripts/run_football_external_soccertrack_google_drive_fixture_access_probe.py` (matching dirty test and source path names)
- `backend/tests/test_run_football_external_soccertrack_lane_closeout.py` tests `backend/scripts/run_football_external_soccertrack_lane_closeout.py` (matching dirty test and source path names)
- `backend/tests/test_run_football_external_soccertrack_match_bundle_bridge_smoke.py` tests `backend/scripts/run_football_external_soccertrack_match_bundle_bridge_smoke.py` (matching dirty test and source path names)
- `backend/tests/test_run_football_external_soccertrack_metadata_adapter_smoke.py` tests `backend/scripts/run_football_external_soccertrack_metadata_adapter_smoke.py` (matching dirty test and source path names)
- `backend/tests/test_run_football_external_soccertrack_product_route_smoke.py` tests `backend/scripts/run_football_external_soccertrack_product_route_smoke.py` (matching dirty test and source path names)
- `backend/tests/test_run_football_external_soccertrack_sample_fixture_materialization.py` tests `backend/scripts/run_football_external_soccertrack_sample_fixture_materialization.py` (matching dirty test and source path names)
- `backend/tests/test_run_football_external_soccertrack_sample_fixture_materialization_approval.py` tests `backend/scripts/run_football_external_soccertrack_sample_fixture_materialization_approval.py` (matching dirty test and source path names)
- `backend/tests/test_run_football_external_soccertrack_sample_ingestion_contract_prep.py` tests `backend/scripts/run_football_external_soccertrack_sample_ingestion_contract_prep.py` (matching dirty test and source path names)
- `backend/tests/test_run_football_external_soccertrack_sample_schema_probe.py` tests `backend/scripts/run_football_external_soccertrack_sample_schema_probe.py` (matching dirty test and source path names)
- `backend/tests/test_run_football_external_soccertrack_schema_doc_fetch.py` tests `backend/scripts/run_football_external_soccertrack_schema_doc_fetch.py` (matching dirty test and source path names)
- `backend/tests/test_run_football_external_soccertrack_schema_doc_fetch_approval.py` tests `backend/scripts/run_football_external_soccertrack_schema_doc_fetch_approval.py` (matching dirty test and source path names)
- `backend/tests/test_run_football_external_soccertrack_schema_doc_parse.py` tests `backend/scripts/run_football_external_soccertrack_schema_doc_parse.py` (matching dirty test and source path names)
- `backend/tests/test_run_product_video_to_analysis_finish_line_execution.py` tests `backend/scripts/run_product_video_to_analysis_finish_line_execution.py` (matching dirty test and source path names)
- `backend/tests/test_run_product_video_to_analysis_normal_storage_smoke.py` tests `backend/scripts/run_product_video_to_analysis_normal_storage_smoke.py` (matching dirty test and source path names)
- `backend/tests/test_run_product_video_to_analysis_smoke.py` tests `backend/scripts/run_product_video_to_analysis_smoke.py` (matching dirty test and source path names)
- `backend/tests/test_run_product_video_to_analysis_smoke_isolated.py` tests `backend/scripts/run_product_video_to_analysis_smoke_isolated.py` (matching dirty test and source path names)
- `backend/tests/test_run_v7_2_runtime_registry_product_path_binding.py` tests `backend/scripts/run_v7_2_runtime_registry_product_path_binding.py` (matching dirty test and source path names)
- `backend/tests/test_run_v7_3_bounded_retrain.py` tests `backend/scripts/run_v7_3_bounded_retrain.py` (matching dirty test and source path names)
- `backend/tests/test_run_v7_3_crop_probe_precision_guardrail_audit.py` tests `backend/scripts/run_v7_3_crop_probe_precision_guardrail_audit.py` (matching dirty test and source path names)
- `backend/tests/test_run_v7_3_export_label_overlay_audit.py` tests `backend/scripts/run_v7_3_export_label_overlay_audit.py` (matching dirty test and source path names)
- `backend/tests/test_run_v7_3_full_pipeline_non_promotion_eval.py` tests `backend/scripts/run_v7_3_full_pipeline_non_promotion_eval.py` (matching dirty test and source path names)
- `backend/tests/test_run_v7_3_post_runtime_default_source_robustness_validation.py` tests `backend/scripts/run_v7_3_post_runtime_default_source_robustness_validation.py` (matching dirty test and source path names)
- `backend/tests/test_run_v7_3_promotion_readiness_validation.py` tests `backend/scripts/run_v7_3_promotion_readiness_validation.py` (matching dirty test and source path names)
- `backend/tests/test_run_v7_3_runtime_default_change_validation.py` tests `backend/scripts/run_v7_3_runtime_default_change_validation.py` (matching dirty test and source path names)
- `backend/tests/test_run_v7_3_runtime_default_rollout_closeout.py` tests `backend/scripts/run_v7_3_runtime_default_rollout_closeout.py` (matching dirty test and source path names)
- `backend/tests/test_run_v7_3_training_manifest_prep_from_soccernet_real_misses.py` tests `backend/scripts/run_v7_3_training_manifest_prep_from_soccernet_real_misses.py` (matching dirty test and source path names)
- `backend/tests/test_run_v7_4_training_decision_from_real_misses.py` tests `backend/scripts/run_v7_4_training_decision_from_real_misses.py` (matching dirty test and source path names)
- `backend/tests/test_run_video_to_analysis_acceptance_report_product_backlog.py` tests `backend/scripts/run_video_to_analysis_acceptance_report_product_backlog.py` (matching dirty test and source path names)
- `backend/tests/test_run_video_to_analysis_acceptance_report_route_binding.py` tests `backend/scripts/run_video_to_analysis_acceptance_report_route_binding.py` (matching dirty test and source path names)
- `backend/tests/test_run_video_to_analysis_broader_real_video_acceptance_approval.py` tests `backend/scripts/run_video_to_analysis_broader_real_video_acceptance_approval.py` (matching dirty test and source path names)
- `backend/tests/test_run_video_to_analysis_broader_real_video_acceptance_closeout.py` tests `backend/scripts/run_video_to_analysis_broader_real_video_acceptance_closeout.py` (matching dirty test and source path names)
- `backend/tests/test_run_video_to_analysis_broader_real_video_acceptance_execution.py` tests `backend/scripts/run_video_to_analysis_broader_real_video_acceptance_execution.py` (matching dirty test and source path names)
- `backend/tests/test_run_video_to_analysis_broader_real_video_acceptance_suite_prep.py` tests `backend/scripts/run_video_to_analysis_broader_real_video_acceptance_suite_prep.py` (matching dirty test and source path names)
- `backend/tests/test_run_video_to_analysis_current_release_acceptance_decision_surface.py` tests `backend/scripts/run_video_to_analysis_current_release_acceptance_decision_surface.py` (matching dirty test and source path names)
- `backend/tests/test_run_video_to_analysis_finish_line_completion_summary.py` tests `backend/scripts/run_video_to_analysis_finish_line_completion_summary.py` (matching dirty test and source path names)
- `backend/tests/test_run_video_to_analysis_finish_line_execution_approval.py` tests `backend/scripts/run_video_to_analysis_finish_line_execution_approval.py` (matching dirty test and source path names)
- `backend/tests/test_run_video_to_analysis_finish_line_normal_storage_closeout.py` tests `backend/scripts/run_video_to_analysis_finish_line_normal_storage_closeout.py` (matching dirty test and source path names)
- `backend/tests/test_run_video_to_analysis_finish_line_normal_storage_execution_approval.py` tests `backend/scripts/run_video_to_analysis_finish_line_normal_storage_execution_approval.py` (matching dirty test and source path names)
- `backend/tests/test_run_video_to_analysis_finish_line_operational_readiness.py` tests `backend/scripts/run_video_to_analysis_finish_line_operational_readiness.py` (matching dirty test and source path names)
- `backend/tests/test_run_video_to_analysis_finish_line_product_acceptance_closeout.py` tests `backend/scripts/run_video_to_analysis_finish_line_product_acceptance_closeout.py` (matching dirty test and source path names)
- `backend/tests/test_run_video_to_analysis_finish_line_product_execution_approval.py` tests `backend/scripts/run_video_to_analysis_finish_line_product_execution_approval.py` (matching dirty test and source path names)
- `backend/tests/test_run_video_to_analysis_finish_line_route_polish.py` tests `backend/scripts/run_video_to_analysis_finish_line_route_polish.py` (matching dirty test and source path names)
- `backend/tests/test_run_video_to_analysis_finish_line_user_acceptance_trial.py` tests `backend/scripts/run_video_to_analysis_finish_line_user_acceptance_trial.py` (matching dirty test and source path names)
- `backend/tests/test_run_video_to_analysis_growth_lane_closeout_readout.py` tests `backend/scripts/run_video_to_analysis_growth_lane_closeout_readout.py` (matching dirty test and source path names)
- `backend/tests/test_run_video_to_analysis_manual_operator_release_decision.py` tests `backend/scripts/run_video_to_analysis_manual_operator_release_decision.py` (matching dirty test and source path names)
- `backend/tests/test_run_video_to_analysis_next_strategic_lane_selection.py` tests `backend/scripts/run_video_to_analysis_next_strategic_lane_selection.py` (matching dirty test and source path names)
- `backend/tests/test_run_video_to_analysis_operational_backlog_prioritization.py` tests `backend/scripts/run_video_to_analysis_operational_backlog_prioritization.py` (matching dirty test and source path names)
- `backend/tests/test_run_video_to_analysis_operator_dashboard_polish.py` tests `backend/scripts/run_video_to_analysis_operator_dashboard_polish.py` (matching dirty test and source path names)
- `backend/tests/test_run_video_to_analysis_operator_handoff_pack.py` tests `backend/scripts/run_video_to_analysis_operator_handoff_pack.py` (matching dirty test and source path names)
- `backend/tests/test_run_video_to_analysis_operator_handoff_route_binding.py` tests `backend/scripts/run_video_to_analysis_operator_handoff_route_binding.py` (matching dirty test and source path names)
- `backend/tests/test_run_video_to_analysis_post_release_monitoring_closeout.py` tests `backend/scripts/run_video_to_analysis_post_release_monitoring_closeout.py` (matching dirty test and source path names)
- `backend/tests/test_run_video_to_analysis_post_release_monitoring_plan.py` tests `backend/scripts/run_video_to_analysis_post_release_monitoring_plan.py` (matching dirty test and source path names)
- `backend/tests/test_run_video_to_analysis_post_release_monitoring_route_binding.py` tests `backend/scripts/run_video_to_analysis_post_release_monitoring_route_binding.py` (matching dirty test and source path names)
- `backend/tests/test_run_video_to_analysis_product_hardening_backlog.py` tests `backend/scripts/run_video_to_analysis_product_hardening_backlog.py` (matching dirty test and source path names)
- `backend/tests/test_run_video_to_analysis_product_lane_closeout.py` tests `backend/scripts/run_video_to_analysis_product_lane_closeout.py` (matching dirty test and source path names)
- `backend/tests/test_run_video_to_analysis_promoted_runtime_operator_acceptance_trial.py` tests `backend/scripts/run_video_to_analysis_promoted_runtime_operator_acceptance_trial.py` (matching dirty test and source path names)
- `backend/tests/test_run_video_to_analysis_release_acceptance_archive.py` tests `backend/scripts/run_video_to_analysis_release_acceptance_archive.py` (matching dirty test and source path names)
- `backend/tests/test_run_video_to_analysis_release_candidate_closeout.py` tests `backend/scripts/run_video_to_analysis_release_candidate_closeout.py` (matching dirty test and source path names)
- `backend/tests/test_run_video_to_analysis_release_readout_pack.py` tests `backend/scripts/run_video_to_analysis_release_readout_pack.py` (matching dirty test and source path names)
- `backend/tests/test_run_video_to_analysis_release_readout_route_binding.py` tests `backend/scripts/run_video_to_analysis_release_readout_route_binding.py` (matching dirty test and source path names)
- `backend/tests/test_run_video_to_analysis_roadmap_state_reconciliation.py` tests `backend/scripts/run_video_to_analysis_roadmap_state_reconciliation.py` (matching dirty test and source path names)
- `backend/tests/test_run_video_to_analysis_source_pool_replenishment_plan.py` tests `backend/scripts/run_video_to_analysis_source_pool_replenishment_plan.py` (matching dirty test and source path names)
- `backend/tests/test_run_video_to_analysis_steady_state_monitoring_cycle.py` tests `backend/scripts/run_video_to_analysis_steady_state_monitoring_cycle.py` (matching dirty test and source path names)
- `backend/tests/test_run_video_to_analysis_storage_cleanup_approval.py` tests `backend/scripts/run_video_to_analysis_storage_cleanup_approval.py` (matching dirty test and source path names)
- `backend/tests/test_run_video_to_analysis_storage_cleanup_bounded_execution.py` tests `backend/scripts/run_video_to_analysis_storage_cleanup_bounded_execution.py` (matching dirty test and source path names)
- `backend/tests/test_run_video_to_analysis_storage_cleanup_closeout.py` tests `backend/scripts/run_video_to_analysis_storage_cleanup_closeout.py` (matching dirty test and source path names)
- `backend/tests/test_run_video_to_analysis_storage_cleanup_dry_run_execution.py` tests `backend/scripts/run_video_to_analysis_storage_cleanup_dry_run_execution.py` (matching dirty test and source path names)
- `backend/tests/test_run_video_to_analysis_storage_cleanup_execution_approval.py` tests `backend/scripts/run_video_to_analysis_storage_cleanup_execution_approval.py` (matching dirty test and source path names)
- `backend/tests/test_run_video_to_analysis_storage_retention_and_artifact_hygiene.py` tests `backend/scripts/run_video_to_analysis_storage_retention_and_artifact_hygiene.py` (matching dirty test and source path names)
- `backend/tests/test_run_video_to_analysis_upload_to_analysis_walkthrough.py` tests `backend/scripts/run_video_to_analysis_upload_to_analysis_walkthrough.py` (matching dirty test and source path names)
- `backend/tests/test_run_video_to_analysis_user_facing_release_readout.py` tests `backend/scripts/run_video_to_analysis_user_facing_release_readout.py` (matching dirty test and source path names)
- `backend/tests/test_run_video_to_analysis_v7_3_release_packaging_and_worktree_triage.py` tests `backend/scripts/run_video_to_analysis_v7_3_release_packaging_and_worktree_triage.py` (matching dirty test and source path names)
- `backend/tests/test_runpod.py` tests `backend/app/runpod.py` (matching dirty test and source path names)
- `backend/tests/test_runpod_worker.py` tests `backend/app/runpod_worker.py` (matching dirty test and source path names)
- `backend/tests/test_serve_football_external_soccernet_detector_miss_review_ui.py` tests `backend/scripts/serve_football_external_soccernet_detector_miss_review_ui.py` (matching dirty test and source path names)

## Artifact retention

- No large local artifacts occur in this inventory.

## Tracked deletions

- `backend/storage/trained_detector_candidates/touchline_detector_candidate_v7/v7_1_positive_candidate_mining_expansion_v1/batch_outcome_analysis.json`: `manual_review`
- `backend/storage/trained_detector_candidates/touchline_detector_candidate_v7/v7_1_positive_candidate_mining_expansion_v1/batch_outcome_analysis.md`: `manual_review`
- `backend/storage/trained_detector_candidates/touchline_detector_candidate_v7/v7_1_positive_candidate_mining_expansion_v1/corrected_label_overlay.json`: `manual_review`
- `backend/storage/trained_detector_candidates/touchline_detector_candidate_v7/v7_1_positive_candidate_mining_expansion_v1/correction_review_index.html`: `manual_review`
- `backend/storage/trained_detector_candidates/touchline_detector_candidate_v7/v7_1_positive_candidate_mining_expansion_v1/decision_matrix.json`: `manual_review`
- `backend/storage/trained_detector_candidates/touchline_detector_candidate_v7/v7_1_positive_candidate_mining_expansion_v1/new_mined_candidate_manifest.json`: `manual_review`
- `backend/storage/trained_detector_candidates/touchline_detector_candidate_v7/v7_1_positive_candidate_mining_expansion_v1/salvage_candidate_summary.json`: `manual_review`
- `backend/storage/trained_detector_candidates/touchline_detector_candidate_v7/v7_1_positive_candidate_mining_expansion_v1/v7_1_positive_candidate_mining_expansion_summary.json`: `manual_review`
- `backend/storage/trained_detector_candidates/touchline_detector_candidate_v7/v7_1_positive_diversity_manual_review_resolution_v1/batch_outcome_analysis.json`: `manual_review`
- `backend/storage/trained_detector_candidates/touchline_detector_candidate_v7/v7_1_positive_diversity_manual_review_resolution_v1/batch_outcome_analysis.md`: `manual_review`
- `backend/storage/trained_detector_candidates/touchline_detector_candidate_v7/v7_1_positive_diversity_manual_review_resolution_v1/decision_matrix.json`: `manual_review`
- `backend/storage/trained_detector_candidates/touchline_detector_candidate_v7/v7_1_positive_diversity_manual_review_resolution_v1/reviewed_positive_resolution_counts.json`: `manual_review`
- `backend/storage/trained_detector_candidates/touchline_detector_candidate_v7/v7_1_positive_diversity_manual_review_resolution_v1/reviewed_positive_truth_additions.json`: `manual_review`
- `backend/storage/trained_detector_candidates/touchline_detector_candidate_v7/v7_1_positive_diversity_manual_review_resolution_v1/v7_1_positive_diversity_manual_review_resolution_summary.json`: `manual_review`
