# Bounded Anchor-Seed Proposal Sprint

## Goal

Wake up the proposal-window recovery path on the real 5-minute clip by seeding proposal windows from bounded observed-source anchors before proposal construction, then validate the result on the pod-first proof lane.

## Implementation

Code landed in:
- `backend/run_guerilla.py`
- `backend/app/processor.py`
- `backend/app/run_benchmarks.py`
- `backend/scripts/run_local_app_path_proof.py`
- `backend/scripts/run_remote_app_path_proof.py`

What changed:
- proposal windows now use bounded seed modes:
  - `exact`
  - `interpolated`
  - `single`
  - `none`
- proposal windows are skipped when the seed mode is `none`
- same-frame proposal ranking now prefers lower seed distance before anchored/support/non-edge quality ties
- recovery persistence now writes `recovery_profile_matrix.json`
- benchmark/proof summaries now support:
  - selected-profile proposal seed fields
  - best-proposal profile fields

## Verification

Focused local verification:
- `PYTHONPATH=/root/WorkSpace/fotball-analyst pytest -q backend/tests/test_run_guerilla.py backend/tests/test_processor.py backend/tests/test_run_benchmarks.py backend/tests/test_run_local_app_path_proof.py backend/tests/test_run_remote_app_path_proof.py`
- Result: `159 passed`
- `./backend/venv/bin/python -m ruff check backend/run_guerilla.py backend/app/processor.py backend/app/run_benchmarks.py backend/scripts/run_local_app_path_proof.py backend/scripts/run_remote_app_path_proof.py backend/tests/test_run_guerilla.py backend/tests/test_processor.py backend/tests/test_run_benchmarks.py backend/tests/test_run_local_app_path_proof.py backend/tests/test_run_remote_app_path_proof.py`
- Result: `All checks passed!`

Pod validation lane:
- pod id: `37n9f2lf2uq390`
- GPU: `NVIDIA RTX PRO 4500 Blackwell`
- proof match: `94ca70a555124b169174b45b85bdaa00`
- proof job: `a60f7fc754cd433590229235a13fd17c`

Local copies of the pod artifacts:
- `backend/storage/pod_artifacts/bounded-anchor-seed-pod-local-proof.json`
- `backend/storage/pod_artifacts/bounded-anchor-seed-pod-selected-cluster-delta.json`
- `backend/storage/pod_artifacts/bounded-anchor-seed-recovery-profile-matrix.json`

## Fresh Result

Selected recovery winner still stayed non-proposal:
- selected profile: `width_cap_075`

But bounded seeding did activate the proposal path:
- best proposal profile: `proposal_windows_075`
- `bestProposalCandidateFrames=111`
- `bestProposalSelectedFrames=9`
- `bestProposalViable=true`
- `proposalExactSeedFrames=81`
- `proposalInterpolatedSeedFrames=4`
- `proposalSingleSeedFrames=26`
- `proposalUnseededFrames=1405`

After explicit selected-cluster promotion:
- selected cluster: `1`
- `acceptedBallFrames=101`
- `controlledPossessionFrames=98`
- `eventFamilyCount=5`
- `ballTrackEdgeFrameShare=0.812`
- `ballTrackViable=false`

## Binary Outcome

- `bounded anchor-seed proposals did not materially improve the 5-minute truth gates`

## Interpretation

This sprint changed the diagnosis in a useful way:
- the proposal path is no longer dead on this clip
- bounded seeding produced a real proposal profile with candidate and selected frames
- but that proposal profile still lost to `width_cap_075`, and the promoted 5-minute truth result stayed pinned at the same blocker

That means the next batch should go deeper into seeded proposal false-negative suppression and row quality inside proposal windows, not back to runtime, team selection, or truth-gate relaxation.
