# True Seed-Centered Proposal Window Sprint

## Summary

Keep the roadmap on the detector lane and fix the next concrete seam exposed by the current proposal pipeline: proposal seeding exists, but the seed was mostly being used to rank player-derived windows rather than guaranteeing a real seed-centered crop.

Closed outcome:
- `true seed-centered proposal windows did not materially improve the 5-minute truth gates`

## Implementation

Landed in:
- `backend/run_guerilla.py`
- `backend/app/run_benchmarks.py`
- `backend/scripts/run_local_app_path_proof.py`
- `backend/scripts/run_remote_app_path_proof.py`

Core changes:
- seeded frames now always reserve one direct seed-centered proposal crop window
- proposal recovery rows now preserve the true seed center from the observed-anchor seed policy
- proposal-only pre-collapse now ranks by true seed distance instead of crop-window-center distance
- proposal hit-rate diagnostics now distinguish:
  - direct seed vs player-ranked windows
  - exact vs interpolated vs single seed modes

## Verification

- `PYTHONPATH=/root/WorkSpace/fotball-analyst pytest -q backend/tests/test_run_guerilla.py -k 'proposal or seed'` -> `15 passed`
- `PYTHONPATH=/root/WorkSpace/fotball-analyst pytest -q backend/tests/test_run_guerilla.py backend/tests/test_run_benchmarks.py backend/tests/test_run_local_app_path_proof.py backend/tests/test_run_remote_app_path_proof.py` -> `138 passed`
- `./backend/venv/bin/python -m ruff check backend/run_guerilla.py backend/app/run_benchmarks.py backend/scripts/run_local_app_path_proof.py backend/scripts/run_remote_app_path_proof.py backend/tests/test_run_guerilla.py backend/tests/test_run_benchmarks.py backend/tests/test_run_local_app_path_proof.py backend/tests/test_run_remote_app_path_proof.py` -> `All checks passed!`

## Fresh Pod Proof

- pod id: `37n9f2lf2uq390`
- GPU: `NVIDIA RTX PRO 4500 Blackwell`
- proof match: `a42ae08a50d344fbb60ef8092505ac17`
- proof job: `0677998c4d0b4d4c92fc926a80453418`
- selected cluster: `1`

Pulled-back artifacts:
- `backend/storage/pod_artifacts/true-seed-centered-proposal-window-pod-local-proof.json`
- `backend/storage/pod_artifacts/true-seed-centered-proposal-window-pod-selected-cluster-delta.json`
- `backend/storage/pod_artifacts/true-seed-centered-proposal-window-recovery-profile-matrix.json`

Before team selection:
- selected recovery winner: `width_cap_075`
- `acceptedBallFrames=101`
- `controlledPossessionFrames=0`
- `ballTrackViable=false`

Best proposal hit-rate:
- profile: `proposal_windows_075`
- `bestProposalRawDetectedFrames=9`
- `bestProposalAfterSeedCollapseFrames=9`
- `bestProposalAfterFalseBallSuppressionFrames=9`
- `bestProposalDirectSeedDetectedFrames=0`
- `bestProposalPlayerRankedDetectedFrames=9`
- `bestProposalExactSeedDetectedFrames=0`
- `bestProposalInterpolatedSeedDetectedFrames=0`
- `bestProposalSingleSeedDetectedFrames=0`
- `bestProposalCandidateFrames=111`
- `bestProposalSelectedFrames=9`
- `bestProposalViable=true`

After explicit selected-cluster promotion:
- `acceptedBallFrames=101`
- `controlledPossessionFrames=98`
- `eventFamilyCount=5`
- `ballTrackEdgeFrameShare=0.812`
- `ballTrackViable=false`

## Interpretation

- the true seed-centered proposal window is now real
- the new diagnostics show the important blocker clearly
- on this clip, the direct seed windows produced zero detections
- all surviving proposal detections still came from `player_ranked` windows
- the winning recovery profile stayed `width_cap_075`

## Next Move

Stay on the pod lane and go deeper into seeded proposal false-negative suppression / proposal hit-rate improvement inside seeded windows before recovery scoring.
