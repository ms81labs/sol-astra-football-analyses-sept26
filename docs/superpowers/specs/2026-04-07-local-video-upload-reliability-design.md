# Local Video Upload Reliability Design

## Goal

Make the local `1-minute video upload -> processing -> review` path honest, debuggable, and test-proven so a real clip can be uploaded and reviewed without hidden team-label corruption or misleading tactical output.

## Why This Subproject Exists

The current live path has two correctness gaps and one reliability gap:

1. unresolved team selection is still auto-forced into `my_team` / `enemy`
2. untrusted-ball runs still render tactical/stat surfaces instead of pausing them
3. auto-homography failure in headless mode still fails the job without a strong operator-facing debugging path

These are more important than cloud GPU work because they directly affect whether the local system tells the truth.

## Scope

This design is intentionally bounded to the local processing path.

In scope:

- local video upload and job lifecycle
- team-selection honesty in backend and frontend
- trust/tactical gating in the review UI
- operator-visible failure diagnostics for local jobs
- test coverage for the real local upload/review contract

Out of scope:

- Modal / RunPod integration
- detector model upgrades
- broader dashboard/retrieval polish
- large refactors unrelated to the upload/review truth path

## Design Decisions

### 1. Preserve tracking without fake team semantics

When team selection is unresolved, player tracks must remain visible in the workspace, but they must not be silently assigned to `my_team` or `enemy`.

To support that, the match frame contract will gain an explicit neutral bucket for unresolved players. The backend will populate it whenever team clusters exist but `myTeamCluster` is still unset.

This gives us:

- visible player tracking for review
- no arbitrary tactical ownership claims
- a clean transition after team selection is chosen

### 2. Gate tactical interpretation on truth prerequisites

The UI should not present coach-facing tactical panels when either of these is true:

- `ballSignalStatus = untrusted`
- `requiresTeamSelection = true`

Tracking-safe information can stay visible:

- video playback
- raw player movement
- trust crops
- issue capture
- cluster selection UI

But tactical/statistical interpretation must pause until prerequisites are met.

### 3. Treat auto-homography failure as an operator-visible workflow state

Auto-homography is a valid convenience path, but on a headless server the fallback cannot become manual clicking. When auto-detect fails:

- the job should fail clearly
- the failure message should explain that manual points are required for this clip
- logs should be accessible from the API/UI

This is better than pretending upload succeeded while leaving the operator blind.

### 4. Test the path we actually use

The current API test path is not trustworthy enough. The new work should explicitly lock:

- auto-homography success path
- auto-homography failure path
- unresolved-team path
- post-selection relabeling path
- UI gating for untrusted / unresolved runs

## Architecture Changes

### Backend

Add an unresolved-player representation to frame data and normalization.

Expected touch points:

- `backend/app/schemas.py`
- `backend/app/analytics.py`
- `backend/app/processor.py`
- `backend/app/main.py`
- `backend/app/storage.py` only if schema persistence needs adjustment
- `backend/app/jobs.py`

### Frontend

Use the stronger truth contract in the review shell.

Expected touch points:

- `frontend/src/types/index.ts`
- `frontend/src/App.tsx`
- `frontend/src/components/TacticalPitch.tsx`
- `frontend/src/components/StatsPanel.tsx`
- `frontend/src/components/TeamSelectionBanner.tsx`
- `frontend/src/components/TrustCropPanel.tsx` only if diagnostics are surfaced there
- `frontend/src/utils/api.ts`

### Testing

Expected touch points:

- `backend/tests/test_processor.py`
- `backend/tests/test_video_pipeline.py`
- `backend/tests/test_api.py`
- `backend/tests/test_jobs.py`
- `backend/tests/test_worker.py`
- `frontend/src/components/StatsPanel.test.tsx`
- `frontend/src/components/TeamSelectionBanner.test.tsx`
- `frontend/src/utils/uploadConfig.test.ts`

## Success Criteria

This subproject is done when:

1. a video upload with unresolved team selection no longer creates fake `my_team` / `enemy` semantics
2. the review shell still shows tracked players before team choice
3. untrusted-ball and unresolved-team runs pause tactical/stat panels clearly
4. auto-homography failures produce actionable job error messages and readable logs
5. the local upload/review path is covered by focused tests that actually run

## Recommended Order

1. restore team-label honesty without losing player visibility
2. gate tactical UI on trust prerequisites
3. harden auto-homography failure diagnostics
4. stabilize/modernize the upload-path test harness
5. rerun the live 1-minute clip and inspect the outcome
