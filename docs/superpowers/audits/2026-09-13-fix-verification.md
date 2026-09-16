# Audit fix verification — 2026-09-13

Follow-up to [the full analysis](2026-09-13-full-code-analysis.md). The original report records the pre-fix snapshot and remains unchanged.

| Findings | Repair | Behavioral evidence |
|---|---|---|
| 1, 2, 6, 8 | Ball-only profile, square source crops, canonical 100×100 calibration, time-matched homography/polygon, acquisition validation and forwarding | `backend/tests/test_pipeline_contract_regressions.py` and existing video/runtime tests |
| 3, 4, 7, 9 | Direction across processing paths, unmatched LAP choices, unknown possession membership, sprint transitions | `backend/tests/test_audit_analytics_fixes.py` |
| 10, 11 | Correct PPDA interpretation and contextual word-boundary negation | Analytics regression file and semantic-search suite |
| 12–15, 23 | Config rollback, provider response validation and HTML escaping, socket disconnect handling, 422 validation, missing-match guards | `backend/tests/test_audit_api_boundaries.py`, API, concurrency, LLM and remote rollback suites |
| 5, 16–22 | Heatmap bounds, source-ID navigation, playback/seek state, stale-response cancellation, annotation ranges, live-position selection, keyboard upload and native dialogs | Frontend component/hook/utility tests; Chromium checks of both upload controls and all five dialog families |

Independent review also identified stale provider results racing config updates and missing attack direction in prompts. Analysis now snapshots under the existing config lock and rejects publication after a match change; provider context preserves display coordinates and declares attack direction. Concurrent provider execution remains outside the lock. Two further review cases cover distinct player proposals and anchorless player-centered crops.

Removed the five identified unused or duplicate pieces: bundle hook methods, shot-marker builder, processor output wrapper, overwritten event types, and duplicate bundle creation request.

Verification uses the repository-pinned Daytona 0.207.0 in an isolated environment. Full suite results and source identity are recorded by `scripts/verify.sh` in `.verification/receipt.json` and `.verification/logs/`. No cloud calls, model downloads, or real-video acceptance were performed. Synthetic detector tests establish execution and coordinate contracts; they do not establish real-video recall. Config rollback remains process-local and is not a crash-atomic multi-file transaction.
