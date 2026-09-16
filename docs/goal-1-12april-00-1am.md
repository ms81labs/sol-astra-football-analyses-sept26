In /root/WorkSpace/fotball-analyst, continue from backend/storage/trained_detector_candidates/touchline_detector_candidate_v7/
  video_to_analysis_total_finishline_closeout_v3/total_finishline_closeout_summary.json.

  Execute the current nextRecommendedNextLever video_to_analysis_source_and_artifact_cleanup_map and keep continuing the generated-truth roadmap chain for
  the autonomous/no-human-in-loop part only.

  Authoritative state:
  - Heartbeat: backend/storage/automation/unattended_roadmap_loop_status.json
  - Current closeout: backend/storage/trained_detector_candidates/touchline_detector_candidate_v7/video_to_analysis_total_finishline_closeout_v3/
  total_finishline_closeout_summary.json
  - Latest generated truth before this goal: backend/storage/trained_detector_candidates/touchline_detector_candidate_v7/
  video_to_analysis_scaleout_or_backlog_decision_snapshot_v376/scaleout_or_backlog_decision_snapshot_summary.json
  - Current next lever: video_to_analysis_source_and_artifact_cleanup_map

  Guardrails:
  - Do not execute training.
  - Do not execute promotion or promotion-readiness mutation.
  - Do not mutate runtime defaults.
  - Do not download videos or datasets.
  - Do not perform normal match storage mutation.
  - Do not delete generated truth or run destructive cleanup.
  - Use fresh versioned output dirs; do not overwrite/reuse existing generated output dirs.
  - Treat video_to_analysis_storage_cleanup_bounded_execution as a hard human/destructive gate. Stop before it unless I explicitly approve deletion in a
  separate goal.

  Continue through deterministic transition blockers when generated truth provides a safe next lever:
  - video_to_analysis_bounded_next_sample_pool_exhausted
  - video_to_analysis_real_video_scaleout_candidate_pool_insufficient
  - video_to_analysis_real_video_scaleout_source_sampling_pool_exhausted

  Stop only on:
  - autonomous finishline/no safe nextRecommendedNextLever
  - configured batch cap of 250 generated batches
  - human/non-autonomous gate
  - destructive cleanup gate, especially video_to_analysis_storage_cleanup_bounded_execution
  - unsafe guardrail flip
  - disk free below 25G
  - verification failure that cannot be repaired after the local failsafe attempts
  - generated primaryBlocker with no safe autonomous recovery lever

  Deploy read-only subagents if useful for code/gate review while executing.

  At completion:
  - Write a new closeout artifact set under touchline_detector_candidate_v7 with summary, executed chain, guardrail audit, verification audit, next action
  contract, and completion audit.
  - Refresh backend/storage/automation/unattended_roadmap_loop_status.json.
  - Refresh SESSION-HANDOFF.md, memorybank/activeContext.md, memorybank/currentRoadmap.md, memorybank/progress.md, and docs/video-to-analysis-finish-line-
  roadmap-guide.md.
  - Verify with focused roadmap tests, storage-cleanup safety tests if that chain is touched, py_compile, JSON sanity, df -h /, RunPod pod list, and post-
  heartbeat reentry tests.