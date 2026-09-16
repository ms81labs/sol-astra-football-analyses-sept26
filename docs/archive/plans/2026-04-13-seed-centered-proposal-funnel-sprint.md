# Seed-Centered Proposal Funnel Sprint

## Goal

Improve the quality of rows inside seeded proposal windows before recovery scoring, then validate the result on the pod-first proof lane.

## Implementation

Code landed in:
- `backend/run_guerilla.py`
- `backend/app/run_benchmarks.py`
- `backend/scripts/run_local_app_path_proof.py`
- `backend/scripts/run_remote_app_path_proof.py`

What changed:
- proposal-window recovery now has a proposal-only same-frame pre-collapse before the shared recovery pipeline
- proposal pre-collapse prefers:
  - lower seed distance
  - anchored rows
  - supported rows
  - non-edge rows
  - higher confidence
  - original row order for deterministic ties
- proposal funnel diagnostics now persist through:
  - `candidateSummary`
  - `recoveryDebug`
  - `recovery_profile_matrix.json`
- benchmark/proof summaries now expose:
  - `bestProposalRawDetectedFrames`
  - `bestProposalAfterSeedCollapseFrames`
  - `bestProposalAfterFalseBallSuppressionFrames`

## Verification

Focused local verification:
- `PYTHONPATH=/root/WorkSpace/fotball-analyst pytest -q backend/tests/test_run_guerilla.py backend/tests/test_run_benchmarks.py backend/tests/test_run_local_app_path_proof.py backend/tests/test_run_remote_app_path_proof.py`
- Result: `136 passed`
- `./backend/venv/bin/python -m ruff check backend/run_guerilla.py backend/app/run_benchmarks.py backend/scripts/run_local_app_path_proof.py backend/scripts/run_remote_app_path_proof.py backend/tests/test_run_guerilla.py backend/tests/test_run_benchmarks.py backend/tests/test_run_local_app_path_proof.py backend/tests/test_run_remote_app_path_proof.py`
- Result: `All checks passed!`

Fresh pod validation lane:
- pod id: `37n9f2lf2uq390`
- GPU: `NVIDIA RTX PRO 4500 Blackwell`
- corrected proof match: `1128ea6b17ec467d95dd8f292bf29ea8`
- corrected proof job: `cd0035b896d341dc8347684794e101da`

Local copies of the corrected pod artifacts:
- `backend/storage/pod_artifacts/seed-centered-proposal-funnel-pod-local-proof.json`
- `backend/storage/pod_artifacts/seed-centered-proposal-funnel-pod-selected-cluster-delta.json`
- `backend/storage/pod_artifacts/seed-centered-proposal-funnel-recovery-profile-matrix.json`

Operational notes from the pod lane:
- the first rerun failed because pod OpenCV still needed `QT_QPA_PLATFORM=offscreen` in the parent shell before Python started
- the first pullback also revealed that the pod proof scripts were still defaulting to the hardcoded local storage root, so the corrected rerun pinned `--storage-root /workspace/fotball-analyst/backend/storage`
- after those two corrections, the pod proof and explicit selected-cluster promotion both completed cleanly

## Fresh Result

Before team selection:
- selected recovery winner: `width_cap_075`
- `acceptedBallFrames=101`
- `controlledPossessionFrames=0`
- `ballTrackEdgeFrameShare=0.812`
- `ballTrackViable=false`
- recommended cluster: `1`

Best proposal profile on the corrected proof:
- profile: `proposal_windows_075`
- `bestProposalRawDetectedFrames=9`
- `bestProposalAfterSeedCollapseFrames=9`
- `bestProposalAfterFalseBallSuppressionFrames=9`
- `bestProposalCandidateFrames=111`
- `bestProposalSelectedFrames=9`
- `bestProposalViable=true`

After explicit selected-cluster promotion:
- selected cluster: `1`
- `acceptedBallFrames=101`
- `controlledPossessionFrames=98`
- `eventFamilyCount=5`
- `ballTrackEdgeFrameShare=0.812`
- `ballTrackViable=false`

## Binary Outcome

- `seed-centered proposal funnel did not materially improve the 5-minute truth gates`

## Interpretation

This sprint improved the proposal observability story in a real way:
- proposal-only pre-collapse is now explicit and deterministic
- the best-proposal funnel counts are now visible in the proof summary and profile matrix
- the corrected pod proof shows the proposal funnel surviving cleanly through collapse and false-ball suppression

But the football result still did not move:
- the winning recovery profile stayed `width_cap_075`
- accepted coverage stayed pinned at `101`
- controlled possession after promotion stayed pinned at `98`
- viable ball track never flipped true

That means the next batch should go deeper into seeded proposal false-negative suppression and proposal-row quality inside seeded windows, not back to runtime, team selection, or truth-gate relaxation.
