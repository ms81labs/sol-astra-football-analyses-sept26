# Accepted Match State v1 Sprint

## Summary

Build `acceptedMatchState v1` as an additive internal artifact above the existing ball layers, then use it in one narrow place only: hidden-ball possession continuity.

This batch intentionally kept:
- truth gates unchanged
- detector passes unchanged
- HTTP/API and frontend contracts unchanged
- event logic unchanged

## Implementation

Landed code:
- `backend/app/schemas.py`
- `backend/app/analytics.py`
- `backend/app/processor.py`
- `backend/app/run_benchmarks.py`
- `backend/run_guerilla.py`
- `backend/scripts/run_local_app_path_proof.py`
- `backend/scripts/run_remote_app_path_proof.py`

What shipped:
- new internal models:
  - `BallEstimate`
  - `MatchStateFrame`
- new internal evidence payload from the ball pipeline:
  - `matchStateEvidence`
- new persisted artifact:
  - `accepted_match_state.json`
- narrow post-pass continuity:
  - `apply_match_state_continuity(...)`
- additive benchmark/proof diagnostics for match-state coverage and continuity

## Verification

Focused local verification:
- `PYTHONPATH=/root/WorkSpace/fotball-analyst pytest -q backend/tests/test_analytics.py backend/tests/test_processor.py backend/tests/test_run_benchmarks.py backend/tests/test_run_local_app_path_proof.py backend/tests/test_run_remote_app_path_proof.py backend/tests/test_run_guerilla.py` -> `203 passed`
- `PYTHONPATH=/root/WorkSpace/fotball-analyst pytest -q backend/tests/test_api.py -k 'benchmark'` -> `2 passed, 13 deselected`
- `./backend/venv/bin/python -m ruff check backend/app/schemas.py backend/app/analytics.py backend/app/processor.py backend/app/run_benchmarks.py backend/run_guerilla.py backend/scripts/run_local_app_path_proof.py backend/scripts/run_remote_app_path_proof.py backend/tests/test_analytics.py backend/tests/test_processor.py backend/tests/test_run_benchmarks.py backend/tests/test_run_local_app_path_proof.py backend/tests/test_run_remote_app_path_proof.py backend/tests/test_run_guerilla.py` -> `All checks passed!`

## Pod Proof

Fresh valid pod proof lane:
- pod id: `37n9f2lf2uq390`
- GPU: `NVIDIA RTX PRO 4500 Blackwell`
- proof match: `519febf2168141899b57ff8b949b17dc`
- proof job: `7f8d4ee662d647649c7ce778f4902521`
- storage root pinned to `/workspace/fotball-analyst/backend/storage`

Pulled-back local artifacts:
- `backend/storage/pod_artifacts/accepted-match-state-v1-pod-local-proof.json`
- `backend/storage/pod_artifacts/accepted-match-state-v1-pod-selected-cluster-delta.json`
- `backend/storage/pod_artifacts/accepted-match-state-v1-accepted_match_state.json`

Fresh result before team selection:
- `acceptedBallFrames=101`
- `controlledPossessionFrames=0`
- `acceptedMatchStateCoverageRatio=0.997`
- `hiddenControlledStateFrames=0`
- `stateContinuityAppliedFrames=0`
- recommended cluster: `1`

Fresh result after explicit selected-cluster promotion:
- selected cluster: `1`
- `acceptedBallFrames=101`
- `controlledPossessionFrames=98`
- `acceptedMatchStateCoverageRatio=1.0`
- `controlledStateFrames=98`
- `hiddenControlledStateFrames=0`
- `stateContinuityAppliedFrames=0`
- `eventFamilyCount=5`
- `ballTrackEdgeFrameShare=0.812`
- `ballTrackViable=false`

## Outcome

Binary truth:
- `accepted match state v1 did not materially improve the 5-minute truth gates`

What this batch still accomplished:
- `accepted_match_state.json` is now real and persisted
- benchmark/proof diagnosis is more specific than the earlier ball-only summary
- the narrow hidden-ball continuity rule is wired and test-covered

Why the truth result stayed flat on this clip:
- the promoted proof produced no hidden controlled state frames
- `stateContinuityAppliedFrames` stayed `0`
- the narrow `player_conditioned` bridge rule found no same-holder hidden gaps within the 2-frame bracket window

## Next Move

Keep `acceptedMatchState v1` as an additive internal diagnostic layer, but return the next active batch to detector-side truth generation:
- keep the pod as the primary heavy-proof lane
- keep explicit selected-cluster promotion intact
- keep truth-gate thresholds unchanged
- do not expose `acceptedMatchState` over HTTP/frontend yet
- go back to upstream false-negative suppression / candidate generation, because this clip still fails before hidden-ball continuity becomes the dominant lever
