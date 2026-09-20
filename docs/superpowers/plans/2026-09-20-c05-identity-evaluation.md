# C05 Effective-input Identity and Verified Evaluation Implementation Plan

> **For agentic workers:** Use superpowers:executing-plans task by task, with regression-first checks and a separate final review.

**Goal:** Close the bounded R08/R10 software contract: reusable artifacts match their effective inputs; metadata, execution, valid scores and policy acceptance are distinct.

**Architecture:** Extend the existing layered identities, canonical review materializer and pinned pilot scorer. Preserve the generation store and algorithms. A read-only inventory is never execution proof. An explicit verifier replays the existing scorer on validated files and evaluates an externally supplied, scope-bound policy; no production policy is invented.

**Tech Stack:** Python, existing Pydantic/PyYAML/NumPy/SciPy, existing TrackEval revision `12c8791b303e0a0b50f753af204249e622d0281a`, pytest, existing GitHub CI.

**Spec:** User's `Guerilla_V3_1_Execution_Plan.md` §9 and V3T36–V3T42, plus C05's portion of V3T50; repository audit `docs/superpowers/audits/2026-09-18-backend-post-remediation-audit-v3.md` R08/R10. The uploaded older general code-quality audit and research-addon files are not this task's specification.

## Recovery and authority

Starting main: `55435949d267906d2eaf7bcc575821933af327b8`. Recovered C05 branch: `1924996c441b5dda048692855e8c00620ded42f1` (two provenance-workflow commits only). The original local implementation mentioned by the interrupted session was not in the recovered Git bundle or this runtime. Do not claim it as recovered implementation or its tests as fresh evidence.

User explicitly requested planning and execution and then continuation. Continue the existing bounded specification inline, preserving its restrictions. C06 runtime/media qualification is a separate package; unknown components disable reuse rather than inventing their identity.

## Global Constraints

- No changes to original CI/verifier, dependency locks, safety limits or unrelated Cursor branches.
- No model inference, training, provider calls, paid/GPU work, production-store writes or deployment.
- Work on the C05 branch. No push/merge to main without separate authorisation.
- Missing required identity is stable null/non-reusable, not a random key or sentinel digest.
- Raw combined/recovered/projected observations must not be advertised as primary detections.
- Retain existing source/history; an invalid reuse attempt cannot publish a generation.
- Score units are explicit. Zero is valid. Production thresholds, labels and prices are not guessed.
- Test-only models/prices/labels are labelled synthetic. Scorer integration is not football-model accuracy.

## Review Focus

1. Config or weight bytes change under the same filename, including while inference/scoring is in flight.
2. Stale, corrupt, cross-source or wrong-namespace stored observations, including a second process.
3. Self-authored metadata claiming execution, final acceptance or a favourable checkpoint without actual replay.
4. Invalid metric scales, booleans, non-finite scores, missing strata and absent/mismatched policies.
5. Missing/changed checkpoint and training split overlap or pseudo-label contamination of held-out data.

## Task 1: Identity boundaries (V3T36/38)

Files: `backend/app/workbench/cache.py`, `backend/app/video_pipeline.py`, targeted `backend/run_guerilla.py` producer metadata; `backend/tests/test_audit_v3_c05_identity_evaluation.py`.

Consumes: resolved source/model/config inputs at `process_video_input`; existing Detection/Tracking/Projection/Reviewed/Report identities.
Produces: deterministic nullable digests, reason codes, actual effective configuration identities and a separate combined-observation identity.

- [ ] Add regressions on the untouched source: unknown digests must be null; same-file tracker config changes must invalidate tracking; metadata-only equality must not count as artifact reuse.
- [ ] Run `PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 python -m pytest -q backend/tests/test_audit_v3_c05_identity_evaluation.py`, retain behavioural failures separately from setup errors.
- [ ] Remove random unknown salts; validate digest components; canonicalise effective YAML/configuration and bind weights/seed bytes. Preserve unaffected upstream identities.
- [ ] Capture producer input provenance at execution, compare boundary snapshots, and label missing runtime/default configuration non-reusable. Keep runtime qualification separate.
- [ ] Run targeted identity and video pipeline tests; commit the working change.

## Task 2: Actual post-perception reuse (V3T37/50)

Files: `backend/app/review_service.py`, `backend/app/processor.py`, `backend/app/storage.py`, `backend/app/generations.py`, `backend/app/workbench/contracts.py`; focused reuse tests.

Consumes: pinned current generation, original observations/source, effective semantic config and ordered commands.
Produces: verified reads consumed by the materializer; current input hashes in generation identities; controlled refusal before publication for stale/corrupt/missing inputs.

- [ ] Reproduce accepted stale-observation/source reuse with real disposable stores in both video and tracking modes.
- [ ] Validate source/scope/digest/size/schema at the common materialization boundary. Read once and use those validated observations, not a second unverified path read.
- [ ] Bind combined observations separately from primary detection identity; include config, identity revision, command digest, geometry and algorithm definitions in downstream keys.
- [ ] Retain legacy read compatibility without upgrading unknown upstream provenance into verified cross-run reuse.
- [ ] Prove real stored hit, input invalidation, corruption and restart cases, zero additional detector calls, and retained prior generation on failure; commit.

## Task 3: Verified evaluation (V3T39–41)

Files: `backend/app/workbench/evaluation.py`, a cohesive `backend/app/evaluation_verifier.py` if needed, existing pilot scorer functions; focused evaluator tests.

Consumes: versioned manifest with confined file descriptors, locked labels, native rows, source/checkpoint/config identities; explicit configured scorer root and optional policy.
Produces: inventoryStatus/executionStatus/scoreStatus/acceptanceStatus, nullable scores and exact replay evidence.

- [ ] Reproduce metadata-only acceptance, prerequisites-as-acceptance and invalid score claims before changing code.
- [ ] Add the four separate states; old accepted is true only for verified applicable policy acceptance. Legacy manifests remain unverified.
- [ ] Read/hash actual permitted files. Execute the existing pinned TrackEval scorer functions only through the explicit replay function, never by executing commands from a manifest or by an HTTP GET.
- [ ] Bind replay to inputs before and after execution; reject wrong coordinate schemas, edits, unapproved label provenance and scorer dirtiness. Preserve genuine zero and declared units.
- [ ] Check each required task/stratum/metric and coverage against explicit policy. Missing policy stays not_evaluated. Record exact command/function, exit result, scorer/config/weights/label/prediction digests.
- [ ] Execute tiny synthetic integration using the real pinned scorer; below-threshold, missing-artifact, edited-content and true-passing controls; commit.

## Task 4: Checkpoint and split provenance (V3T42)

Files: `backend/train_custom.py`, `backend/app/training_quality_gate.py`, existing checkpoint/evaluation provenance helpers as appropriate; focused tests.

Consumes: actual candidate bytes, dataset/config manifests, CSV diagnostics and retained checkpoint validation evidence.
Produces: separate diagnostic epoch selection and verified checkpoint binding; no inferred CSV-to-best.pt proof; exact split provenance with no held-out pseudo-label leakage.

- [ ] Test that a CSV's favourable row cannot certify another checkpoint and that modified weights/overlapping split inputs cannot pass verified acceptance.
- [ ] Retain useful CSV diagnostics but label old checkpoint association unverified. Use exact candidate digest and actual replay/validation receipt for a verified claim.
- [ ] No extra training or automatic model validation run in this implementation. Exercise with injected test-only adapters and real disposable files.
- [ ] Run neighbour training/evaluation tests; commit.

## Task 5: Integration and closure

- [ ] Run focused suites and C01–C04 compatibility, retaining failures and positive controls.
- [ ] Run the original full code-only verifier and existing integration/media CI unchanged on the exact final candidate.
- [ ] Add a read-only C05 CI lane for the real pinned scorer, exact source bundle, logs and checksums.
- [ ] Execute copied-store forward read/rebuild and backup-restore rollback; actual-process C05 composed journeys in both input modes.
- [ ] Review all diffs separately; fix demonstrated important findings with a regression first.
- [ ] Publish tested code to the existing C05 branch and open a reviewable PR; verify its SHA/tree and checks. Main merge requires separate authorisation.
- [ ] Deliver exact source/evidence bundle and closure, clearly separating software results from unavailable football/model/C06 qualification.

## Initial runnable behavioural examples

```python
assert DetectionIdentity(source_sha256=None, stream_index=0, interval=Interval(start=0, end=1),
    weights_sha256='a'*64, preprocessing_id='test', class_map_id='test',
    precision='fp32', runtime_build='test').digest() is None
assert not evaluate_protocol_prerequisites(complete_tasks=18, complete_minutes=30,
    locked_labels_present=True, native_predictions_present=True,
    team_declarations_present=True, scorer_replayable=True).accepted
```

Baseline fixtures and all later code steps are retained in the named test files alongside this plan. Baseline compatibility on the recovered source: 28 passed with the existing Ultralytics import stub, local Python 3.13.5 (not the declared locked profile).
