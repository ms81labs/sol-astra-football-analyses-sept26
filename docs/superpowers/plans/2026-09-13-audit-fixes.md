# Audit fixes implementation plan

**Goal:** Fix all 23 findings and the five proven Ponytail cuts from `docs/superpowers/audits/2026-09-13-full-code-analysis.md`.
**Authorization:** User requested “fix them” after receiving that report and its proposed remedies.
**Architecture:** Repair existing boundaries; retain public coordinate conventions, durable storage and sealed remote result contracts. Use existing dependencies and native browser controls. No provider calls, data deletion, or new services.
**Verification:** Each task adds behavioral regressions, observes failure, implements the minimal remedy, and runs its focused tests. Final integration runs the full verifier in the pinned environment and an independent code review.

- [x] Task 1: frontend findings 5,16–22; heatmap, frame navigation, playback, stale analysis, annotations, hit testing, accessible uploads/dialogs. Own frontend only. Remove dead bundle/shot helpers and reuse createBundle.
- [x] Task 2: API/storage findings 12–15,23; atomic config reprocessing, provider validation/escaping, disconnected sockets, validation responses and nonexistent-match guards. Own main/storage/llm/report-export and relevant tests. Coordinate processor reprocessing signature with Task 4.
- [x] Task 3: video findings 1,2,6,8; current detector profile contract, canonical auto homography, temporal calibration pairs across all recovery passes and acquisition-mode execution. Own run_guerilla/pitch_detector/video_pipeline/proof_runtime/gpu_worker and focused tests. Do not edit processor/analytics.
- [x] Task 4: analytics findings 3,4,7,9–11; direction at shared analytics calls, correct partial assignment, unknown team membership, sprint transitions, PPDA and contextual negation. Own analytics/processor/team_classification/semantic_search/lap and tests. Remove dead processor computations.
- Task 5 (completion recorded by `.verification/receipt.json`): integrate, independently review all changes, run scripts/verify.sh using pinned Daytona 0.207.0; preserve historical release evidence and explicitly report real-video/provider acceptance not executed.

Interfaces: Tasks 1/4 preserve camera-space display coordinates and existing response field names; analytical direction is explicit and defaults left-to-right. Task 2 must call reprocessing with candidate config before durable publication; Task 4 owns any processor signature changes. Task 3 preserves existing process_video parameters and adds only supported runtime choices. Review same-file interactions before combining.

Progress and evidence will be recorded below as work completes.

Implementation evidence: frontend 128 tests plus lint/build and native Chromium keyboard/dialog checks; API initial 219 focused tests plus 13 rollback checks, followed by 66 tests after independent review; analytics 9 behavioral regressions plus existing focused suites. Pipeline initial 570 tests passed; independent review identified two spatial-coverage gaps for correction before integration. Final verifier remains pending.

Review follow-up: API race and direction-context corrections passed 66 tests and independent re-review. Both pipeline coverage corrections passed 574 focused tests, including separate probe and recovery marker checks. Frontend independent review found no blocker.

Independent follow-up review approved both remaining pipeline fixes: 13 regressions and both original reproductions now confirm the intended spatial coverage. The first full verifier run found existing annotation/curation fixtures that omitted parent matches; fixtures were corrected while keeping corruption, atomicity and concurrency assertions. The final clean-source verification receipt is the completion record for Task 5.
