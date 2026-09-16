# Football Analysis Readiness Execution Design

## Goal

Turn the 13 September readiness assessment into measured evidence for a controlled tactical-video analyst pilot without converting narrow software or workflow checks into football-accuracy claims.

## Scope and order

The work proceeds through independently verifiable slices:

1. Bind the current source, model artifacts, runtime options, and local verification evidence into one truthful release baseline.
2. Stream bounded SoccerTrack v2 GSR windows into the existing reconstructed-player contract, with provenance and coordinate semantics preserved.
3. Define a disjoint, rights-cleared pilot corpus and keep held-out matches outside training and crop selection.
4. Score calibration, players, ball, GSR, possession, and events with explicit per-match denominators.
5. Run G-PRODUCT through the actual upload-to-UI path, then measure G-CAPACITY on a representative full match.
6. Add data or change models only in response to a measured stage failure.

Each slice gets its own implementation plan. A later slice may correct assumptions in this design when direct evidence requires it, but it must not weaken provenance, held-out separation, or denominator reporting.

## Evidence model

`docs/status/current.md` remains the single current operating status. It will separate five evidence classes:

- software verification;
- actual pipeline inference;
- independently labeled accuracy;
- resource/capacity measurement;
- analyst acceptance.

Every result identifies its source commit, input identity, runtime options, and denominator where applicable. Artifact assembly, HTTP success, schema validity, or a historical provider smoke never counts as labeled accuracy. Missing measurements remain `unproven`.

## Release baseline

The first slice reuses the existing release manifest writer, verifier, receipt, and pre-cloud evidence format. All source changes are committed before the release source is selected. A following metadata-only commit binds `backend/release/v7.3.json` to that source. The canonical mutation-disabled verifier then produces a fresh receipt, from which the existing evidence writer publishes `backend/release/verification/v7.3-pre-cloud.json`.

The old final evidence at `backend/release/verification/v7.3.json` is removed from the active release path because it is bound to the historical fourth infrastructure smoke. Git history and the dated recovery report preserve that historical evidence. A current final evidence file is created only by a successful G-PRODUCT run bound to the selected source and input.

## Evaluation flow

SoccerTrack coordinate work will use bounded streaming reads of the cached multi-gigabyte GSR files. The adapter will produce the application's existing frame/player structures rather than a parallel benchmark schema. Reference positions may score runtime predictions but may not seed, crop, or otherwise guide video-only inference.

Pilot manifests will group by whole match. Metrics will report per match and camera mode before aggregation, including unknown/failure coverage. Planning thresholds from the readiness report remain proposed pilot bars until the intended analyst accepts them.

## External operations

Local, read-only, and mutation-disabled work proceeds automatically. Dataset downloads require a verified license/provenance record. G-PRODUCT requires the exposed Daytona credential to be rotated and the exact source-bound operation to be authorized at the gate; this safety boundary is not replaced by general roadmap approval. G-CAPACITY starts only after G-PRODUCT succeeds and cleanup is confirmed.

## Error handling and preservation

Existing fail-closed release validators remain authoritative. A source, manifest, artifact, receipt, or evidence mismatch stops the release step. Large annotation files are streamed rather than loaded wholesale. Provider cleanup is part of acceptance, not a best-effort follow-up.

Historical artifacts are preserved in Git history or dated recovery records. Active files must describe the active source; historical successes are labeled historical and excluded from current accuracy and capacity denominators.

## Verification

Each behavioral change follows red-green TDD with the smallest focused test. Each slice ends with its focused checks and the appropriate integrated verifier. Documentation claims are checked against machine-readable receipts, manifests, metric outputs, and source/input hashes before publication.
