# Backend quality continuation — 24 September 2026

## Scope and source

Continuation of the earlier follow-up, on source `3dbb46acf43dda666c835f996def7ff5b95e76da`.
The temporary snapshot-only commit `8240a240b47e7ed66fd2e7816ad06babf0181362` supplied an
exact git archive and pinned offline quality tools. The design and execution plan are in
`docs/superpowers/specs/2026-09-24-backend-quality-next.md` and
`docs/superpowers/plans/2026-09-24-backend-quality-next.md`.

## What the previous pending CI actually found

Both full-backend and canonical verification failed one brittle test:
`test_ci_keeps_canonical_verifier_and_declares_acceptance_lanes` expected exactly four
`set -o pipefail` strings although the new quality gates correctly brought the total to six.
The prior full backend recorded one failure, 4,535 passes and 18 skips. This continuation
replaces the aggregate count with an actual failure-propagation check for each logged
pipeline while retaining the existing profile, dependency and acceptance-lane assertions.

## Implemented repairs

### Types and two real missing-clock crashes

The identical existing mypy configuration now reports **zero**, down from 108 diagnostics.
The scope is still workbench, schemas, settings and run_benchmarks, not the entire backend.
No type ignore was added and no mypy rule/configuration was weakened. Existing dynamic
third-party inputs and missing stubs remain coverage limitations.

Fixed-shape benchmark, file-identity, proxy and currency-bucket records now have explicit
shapes. Validated enum values and optional results are narrowed locally. Decimal reservation
arithmetic stays Decimal and reaches both the attempt and charge records. Receipt attachment,
resource limits and source-time rational arithmetic are retained.

`map_decoded_to_sample` no longer adds an offset to a missing timestamp; it withholds that
sample. Anchor scanning no longer subtracts None: it preserves missing endpoints and only
compares two known adjacent times. Two regressions fail on the original source and pass after
the change. No timestamp is invented, and unknown gaps do not become artificial camera cuts.

### Runtime research dependency and package boundary

Fourteen shared validation/scoring functions were moved into `app/pilot_labels.py` and
`app/pilot_tracking.py`. Their bodies were copied unchanged; the later explicit zip
`strict=False` additions preserve previous truncation semantics. The original research
modules explicitly re-export their APIs and retain command-specific logic.

`app/evaluation_verifier.py` no longer imports backend.scripts. A fresh-process import guard
rejects all research modules while exercising duplicate-key rejection, cadence, empty
TrackEval input construction and unpinned-scorer rejection. A real wheel, built from clean
source, excludes backend/scripts and passes that probe outside the source tree. Existing
source/editable-checkout research commands remain in place. Runtime locks are unchanged.

### Route structure without global routers

`leftover_get_routes.py` and `leftover_routes.py` are now 37- and 33-line assembly modules.
Five domain modules retain the handler implementations and registration order. Report
readers have explicit Storage parameters; request handlers still close over their own
application dependencies. Legacy factory/attachment entry points remain available.

The complete OpenAPI and ordered route snapshots are identical before/after extraction
under both flag values in the same environment: 319 paths with the compatibility flag off,
490 with it on. Cross-environment CI pins route order and path counts rather than a
FastAPI-version-specific schema hash. The new storage/auth regression proves separate apps
do not share match state and the hosted boundary is still denied.

The former factory complexities 238 and 124 are replaced by root assemblers with no nested
handlers. The largest new registration function has complexity 39; aggregate warning counts
must not be mistaken for equivalent complexity measures.

### Lint and regression-test specificity

All **F, S110 and B904** checks now pass across backend, not merely app/scripts, and CI's
zero-debt command covers that whole scope. Unused test imports were removed; intentional
release compatibility imports became explicit re-exports. Existing zip calls use
`strict=False`, not an unreviewed change to equal-length enforcement.

Seventeen broad expected-error assertions now specify actual exception classes. All 94
parametrized cases pass with the narrowed assertions. The two remaining optional-metadata
pass-only handlers use fixed debug messages without raw errors, credentials or tracebacks;
metadata remains best effort and does not flood normal logs.

## Measured debt, not a blanket closure

Ruff under the comparable pinned rules: **581 -> 504**, a net reduction of 77. Eighty-four
findings in the concrete F401/F541/B009/B017/B905/S110 categories were resolved. Splitting
one nested-factory warning into several smaller registration-function warnings adds seven
C901 entries; this reviewed structural migration explains the difference.

Remaining Ruff families: **235 C901, 175 BLE001, 94 B008**. The exact diagnostic baseline
still rejects new or stale entries; CI never regenerates it automatically. Mypy is zero
within its unchanged initial scope; this is not a claim that a separately configured
596-error full-app report has been fully remediated.

Still open: broader storage/run_guerilla/other-router decomposition, review of remaining
catch-all policies and dependency-style findings, wider typing coverage, and physical
relocation of research commands where command/release compatibility permits. Other
Pydantic contracts still need individual compatibility review, not blanket extra-forbid.

## Verification and recovery

The execution workspace restarted during a full-suite launch before publication. The
source was recovered from the known snapshot and reconstructed; focused tests were rerun
instead of trusting lost files or incomplete output. The rebuilt patch's API tests caught
a missed charge-record reference during a local rename; that defect was repaired before
publication, and the complete route/API subset passed afterward.

Retained post-recovery batches: 67 typed-boundary/CI-contract passes; 67 runtime/pilot passes
with six pinned-scorer skips; 93 route/API/architecture passes; 86 ledger/money/boundary passes;
and 94 specific-exception passes. These overlap and are not a unique total. Local runtime
is Python 3.13 with the repository ultralytics stub, not the pinned Python 3.11 CI profile.
An earlier memory-capped hash test failed in the local environment on both unchanged and
modified source; its limit was not weakened. Final pinned CI must resolve acceptance.

Final acceptance is the published commit's completed normal CI, including complete backend,
canonical code-only verification, quality ratchets, API/platform profiles, media/integration
and the dedicated C05/C06 evidence workflows. Running jobs and the local subsets above are
not a green full suite. CPU acceptance does not establish GPU or football-model accuracy.
The temporary transfer workflow is removed from the final published tree. No extra remote
branch, force-push, deployment, live-store or paid provider/GPU execution is part of this work.
