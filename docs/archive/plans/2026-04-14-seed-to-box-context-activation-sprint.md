# Seed-to-Box Context Activation Sprint

## Summary

Keep the roadmap on the detector lane and make `direct_seed_context` activate from bounded seed-to-source-box distance instead of requiring the player center to land inside the tight seed window.

Closed outcome:
- `seed-to-box context activation did not materially improve the 5-minute truth gates`

## Implementation

Landed in:
- `backend/run_guerilla.py`
- `backend/app/run_benchmarks.py`
- `backend/scripts/run_local_app_path_proof.py`
- `backend/scripts/run_remote_app_path_proof.py`

Core changes:
- `direct_seed_context` no longer depends on player-center-in-window activation
- the nearest same-frame player source box now becomes eligible when its seed-to-box distance is `<= BALL_RECOVERY_PADDING_PX`
- candidate choice is deterministic by:
  - lower seed-to-box distance
  - lower seed-to-source-box-center distance
  - original row order
- proposal ranking, truth semantics, and downstream recovery scoring stayed unchanged
- proposal diagnostics now persist:
  - `proposalDirectSeedContextEligibleFrames`
  - `proposalDirectSeedContextDuplicateFrames`
  - `proposalDirectSeedContextMeanSeedToBoxDistance`

## Verification

- `PYTHONPATH=/root/WorkSpace/fotball-analyst pytest -q backend/tests/test_run_guerilla.py -k 'direct_seed_context or proposal_funnel_fields or proposal_diagnostics'` -> `5 passed, 111 deselected`
- `PYTHONPATH=/root/WorkSpace/fotball-analyst pytest -q backend/tests/test_run_guerilla.py backend/tests/test_run_benchmarks.py backend/tests/test_run_local_app_path_proof.py backend/tests/test_run_remote_app_path_proof.py` -> `144 passed`
- `./backend/venv/bin/python -m ruff check backend/run_guerilla.py backend/app/run_benchmarks.py backend/scripts/run_local_app_path_proof.py backend/scripts/run_remote_app_path_proof.py backend/tests/test_run_guerilla.py backend/tests/test_run_benchmarks.py backend/tests/test_run_local_app_path_proof.py backend/tests/test_run_remote_app_path_proof.py` -> `All checks passed!`

## Fresh Pod Proof

- pod id: `37n9f2lf2uq390`
- GPU: `NVIDIA RTX PRO 4500 Blackwell`
- proof match: `ca4d252320164bd498761ac3caef48d2`
- proof job: `d2aec9f567184fc6bbf23d675f427ded`
- selected cluster: `1`

Pulled-back artifacts:
- `backend/storage/pod_artifacts/seed-to-box-context-activation-pod-local-proof.json`
- `backend/storage/pod_artifacts/seed-to-box-context-activation-pod-selected-cluster-delta.json`
- `backend/storage/pod_artifacts/seed-to-box-context-activation-recovery-profile-matrix.json`

Best proposal activation diagnostics:
- profile: `proposal_windows_075`
- `proposalDirectSeedWindowFrames=201`
- `proposalDirectSeedTightWindowFrames=111`
- `proposalDirectSeedContextWindowFrames=90`
- `proposalDirectSeedContextEligibleFrames=90`
- `proposalDirectSeedContextDuplicateFrames=0`
- `proposalDirectSeedContextMeanSeedToBoxDistance=71.74`
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

- the activation seam is now fixed and benchmarked
- `direct_seed_context` activation jumped from `7` frames to `90` frames on this clip
- direct-seed detections still stayed at zero
- all surviving proposal detections still came from `player_ranked` windows
- the winning recovery profile stayed `width_cap_075`
- the 5-minute truth plateau did not move

## Next Move

Stay on the pod lane and go deeper into direct-seed crop geometry / false-negative suppression inside already-activated seeded windows before recovery scoring.
