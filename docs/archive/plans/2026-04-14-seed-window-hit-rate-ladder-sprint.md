# Seed Window Hit-Rate Ladder Sprint

## Summary

Keep the roadmap on the detector lane and improve direct-seed proposal hit rate without widening the proposal geometry ladder or adding detector sweeps.

Closed outcome:
- `seed-window ladder did not materially improve the 5-minute truth gates`

## Implementation

Landed in:
- `backend/run_guerilla.py`
- `backend/app/run_benchmarks.py`
- `backend/scripts/run_local_app_path_proof.py`
- `backend/scripts/run_remote_app_path_proof.py`

Core changes:
- seeded proposal frames now reserve a bounded ladder of window kinds:
  - `direct_seed_tight`
  - `direct_seed_context`
  - `player_ranked`
- `direct_seed_context` is only created when a player center falls inside the tight seed window
- proposal rows now keep true seed metadata while persisting the split window kind
- proposal pre-collapse now includes a deterministic kind tie-break:
  - `direct_seed_context`
  - `direct_seed_tight`
  - `player_ranked`
- proposal diagnostics now split direct-seed hit rate into:
  - tight vs context window counts
  - tight vs context detected-frame counts

## Verification

- `PYTHONPATH=/root/WorkSpace/fotball-analyst pytest -q backend/tests/test_run_guerilla.py -k 'proposal and (context or direct_seed or hit_rate or pre_collapse or preserves_true_seed_metadata or recovery_profile_matrix or proposal_diagnostics)'` -> `8 passed`
- `PYTHONPATH=/root/WorkSpace/fotball-analyst pytest -q backend/tests/test_run_guerilla.py backend/tests/test_run_benchmarks.py backend/tests/test_run_local_app_path_proof.py backend/tests/test_run_remote_app_path_proof.py` -> `141 passed`
- `./backend/venv/bin/python -m ruff check backend/run_guerilla.py backend/app/run_benchmarks.py backend/scripts/run_local_app_path_proof.py backend/scripts/run_remote_app_path_proof.py backend/tests/test_run_guerilla.py backend/tests/test_run_benchmarks.py backend/tests/test_run_local_app_path_proof.py backend/tests/test_run_remote_app_path_proof.py` -> `All checks passed!`

## Fresh Pod Proof

- pod id: `37n9f2lf2uq390`
- GPU: `NVIDIA RTX PRO 4500 Blackwell`
- proof match: `feff32e5d442427b9ff845ce9820d039`
- proof job: `e6fbcc07233644e5b03004438a2956dc`
- selected cluster: `1`

Pulled-back artifacts:
- `backend/storage/pod_artifacts/seed-window-hit-rate-ladder-pod-local-proof.json`
- `backend/storage/pod_artifacts/seed-window-hit-rate-ladder-pod-selected-cluster-delta.json`
- `backend/storage/pod_artifacts/seed-window-hit-rate-ladder-recovery-profile-matrix.json`

Best proposal ladder diagnostics:
- profile: `proposal_windows_075`
- `proposalDirectSeedWindowFrames=118`
- `proposalDirectSeedTightWindowFrames=111`
- `proposalDirectSeedContextWindowFrames=7`
- `proposalPlayerRankedWindowFrames=111`
- `bestProposalRawDetectedFrames=9`
- `bestProposalAfterSeedCollapseFrames=9`
- `bestProposalAfterFalseBallSuppressionFrames=9`
- `bestProposalDirectSeedDetectedFrames=0`
- `bestProposalDirectSeedTightDetectedFrames=0`
- `bestProposalDirectSeedContextDetectedFrames=0`
- `bestProposalPlayerRankedDetectedFrames=9`
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

- the ladder is real and benchmarked
- `direct_seed_context` windows were exercised on this clip, but they still produced zero detections
- all surviving proposal detections still came from `player_ranked` windows
- the winning recovery profile stayed `width_cap_075`
- the 5-minute truth plateau did not move

## Next Move

Stay on the pod lane and go deeper into direct-seed hit rate / false-negative suppression inside seeded windows before recovery scoring.
