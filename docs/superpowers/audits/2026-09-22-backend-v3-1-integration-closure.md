# Backend v3.1 bounded-completion closure

**Date:** 2026-09-22  
**Verdict:** the supported local code pass is implemented and substantially verified, with explicit qualifications below. This is not a deployment, provider, football-accuracy, browser, macOS, GPU, or main-push-rollout sign-off.

## 1. Supported scope and source

| Field | Value |
|---|---|
| Historical audit source | `c685640a897c16669e3b1848d77bf9e6e5d7e8cf`, tree `c87ef6b2969573c170834b11ccb3dde80cfe55f6` |
| Candidate code source | `c05e6de0c87fd78a57f354cba67a7730b50d9ca8`, tree `ea3facd102740eff9d982b5e2ca427d6675b7488` |
| Branch | `agent/backend-bounded-completion-2026-09-22` |
| Remote `main` at final comparison | `c685640a897c16669e3b1848d77bf9e6e5d7e8cf` |
| Local state before closure document | clean |
| Runtime | Linux; Python 3.12.3; FFmpeg 6.1.1; Node 24.20; npm 11.19 |
| Locks | `dev.lock` `f16a7566...60798`; `quality-linux.lock` `c97200d4...1d0ba` |
| Scorer | TrackEval `12c8791b303e0a0b50f753af204249e622d0281a` |
| Provider controls | `VERIFY_DAYTONA=0`, `ALLOW_DAYTONA_MUTATION=0`; no credentials or paid calls |
| Active test stub | `ultralytics`, disclosed by receipts |
| Evidence root | `/tmp/sol-astra-completion.Q1rHef` |

The declared Python 3.11 profile was unavailable locally. The repository-supported Python 3.12.3 profile was used; Python 3.11 remains a canonical-CI qualification. The kit's checksum file also references `historical/sol-astra-backend-audit-evidence-2026-09-22.zip`, which was absent. All supplied kit files verified, but F00.6-F00.7 could not be reconstructed or relabelled.

## 2. Follow-up register

| ID | Disposition | Current evidence | Remaining qualification |
|---|---|---|---|
| A01 | fixed | Trust-crop reads are held under one existing generation snapshot, return its ID, and cover interleaved/current/history/error cases. Commit `185ea29`; 43 backend tests plus UI/type checks. | None in supported local contract. |
| A02 | fixed | Ball displacement is converted from declared normalized pitch coordinates to metres; invalid/unknown geometry withholds only that heuristic and is disclosed. Commit `296e5fd`; 74 backend tests plus UI/type checks. | This is a diagnostic heuristic, not measured 3-D ball speed. |
| A03 | fixed | Receipts are per invocation, source/tree/profile/stub bound, preserve event SHA separately, and do not sum overlapping gates. Commit `d498a84`; 53 tests, plus 9 final environment-isolation tests. | Historical malformed receipts are classified, not promoted. |
| A04 configuration | fixed | Main, PR, retained branch, shared determining paths, pinned scorer and read-only permissions have a workflow contract. Commit `775a784`; contract pass and pinned C05 46-pass lane. | — |
| A04 rollout | still open | No branch push/merge was authorized; therefore no qualifying `main` push run ID exists. | Observe an actual main-push run after separately authorized integration. |
| A05 | fixed | One composed test performs J01-J16 for video and tracking stores using real processes, real FFmpeg source generation, fake paid boundaries, and the pinned real scorer. Commit `4e36db3`; final lane 2 passed. | Synthetic observations/labels do not demonstrate football accuracy. |
| A06 | fixed at classified scope | Ownership-publication and both remote-debug auxiliary failures now emit stable secret-safe warnings without changing primary result, cleanup, or unknown-cost semantics. Commit `849b4ec`; focused 5 passed and neighbours 363 passed, 1 skipped. | Cleanup and compatibility suppressions remain deliberately retained. |

## 3. Functional R/N register

| ID | Disposition | Evidence and remaining scope |
|---|---|---|
| R01 | fixed | Existing generation pin/history/retention suite plus composed held-reader journey; trust crops reuse the same authority. |
| R02 | fixed | Existing publication kill/recovery matrix retained; V3T50 executes a real child termination and repeated recovery. |
| R03 | fixed for supported diagnostics | Explicit geometry provenance and metres; source-pixel video observations and tracking projection are exercised. No new inference claim. |
| R04 | fixed | Ordered config, team mapping, identity, event review, undo and restart behavior run in both V3T50 modes. |
| R05 | fixed | Generation-bound trust crops and current/historical report behavior are exercised. |
| R06 | fixed | Scoped references and unavailable numeric evidence remain enforced; fake report gateway only. |
| R07 | fixed locally; real provider disabled | Nullable unknown exposure, reconciliation and idempotency run against the ledger. No billable call occurred. |
| R08 | fixed at demonstrated reuse boundary | V3T50 reads a real verified post-perception artifact after compatible edits; no universal detector-cache claim. |
| R09 | fixed for declared synthetic envelope | Real FFmpeg media lanes and the opt-in greater-than-8-GiB decode pass. Representative full-match performance remains unmeasured. |
| R10 | fixed for synthetic evaluation | Pinned TrackEval selection passes and keeps metadata completeness distinct from policy acceptance. Real-football scoring is not claimed. |
| N01 | fixed | Requested config and derived outputs survive same-request updates and reopen in both modes. |
| N02 | fixed for declared limits | Actual child controls and resource-unit tests retained; no production capacity claim. |
| N03 | fixed | Reads do not repair/prune; trust-crop reader is pinned. |
| N04 | fixed | Explicit pair/target semantics and swap/undo controls retained. |
| N05 | fixed locally | Source-bound per-run evidence and composed closure exist. Missing archive and absent main rollout are separately recorded. |
| N06 | fixed at measured stage boundary | Materialisation/reuse counters distinguish analytical work from detector/provider work; no 2x billing claim. |

## 4. Code-quality preservation register

The earlier 21 findings remain separate from C01-C06. No completed item was reopened merely to create work.

| IDs | Current disposition and verification |
|---|---|
| CQA-C01, CQA-C03 | Preserved by full/focused API, model-capability and output regressions. |
| CQA-C02 | Preserved: six-path manifest complement ran 594 passed. |
| CQA-H01-H06 | Preserved: composition/storage/benchmark/schema/helper boundaries were not broadened; compatibility exports and script hygiene pass. |
| CQA-H07 | Completed at bounded scope: meaningful auxiliary failures trace safely; cleanup and compatibility catches remain. |
| CQA-H08 | Preserved: pinned blocking Ruff selections pass. |
| CQA-M01-M02 | Preserved under the documented rule context; report-only Ruff output is not converted into a new blocking backlog. |
| CQA-M03-M07 | Preserved: selection contracts, exit statuses, locks, stub disclosure and bounded normalizers remain. |
| CQA-M08-M09 | Retained by design: 410 compatibility routes and large integration tests were not deleted or fragmented. |
| CQA-M10 | Preserved: stable internal aliases/callers remain covered. |

## 5. Execution ledger

Counts overlap and are not added into a unique total.

| Lane | Source | Result | Evidence |
|---|---|---|---|
| Complete backend | `c3e4b87` | 4,465 passed, 5 skipped, 2 failed in 35:04 | `F08-backend-all`; one stale test double was fixed and isolated green, one 2-second semantic-index threshold reproduced on exact baseline at 2.178s and candidate at 2.199s. This run is qualified, not green. |
| Original code-only verifier | `c5cb4f6` | 3,858 passed, 16 skipped, 4 failed; stopped at backend gate | `F08-code-only`; three failures were test environment/selection isolation and are fixed with focused green reruns. The remaining semantic-index timing failure is the same baseline-local limitation. This verifier is qualified, not green. |
| Changed-file selection | `f332c5c` then `c05e6de` | 219 passed, 1 skipped, 1 test-isolation failure; final review-fix selection 93 passed | `F08-affected-final`, `F08-profile-isolation-fix`, `review-fixes-focused-04`. |
| Excluded complement | `f332c5c` | 594 passed | `F08-excluded-final`; six manifest paths. |
| Integration | `c05e6de` | 369 passed, 2 skipped, 4,108 deselected | `F08-integration-review-final`. |
| Real media | `c05e6de` | 24 passed, 2 skipped, 4,453 deselected | `F08-real-media-review-final`. |
| Pinned C05 | `f332c5c` | 46 passed, 1 warning | `F08-c05-final`; exact scorer pin above. |
| V3T50 | `f332c5c` | 2 passed, 1 warning | `F08-v3t50-final`; video and tracking. |
| C06 ordinary | `f332c5c` | 72 passed, 1 skipped | `F08-c06-final`. |
| C06 long decode | `f332c5c` | 1 passed in 30.52s | `F08-c06-long-final`; synthetic decoded work greater than 8 GiB. |
| Pre-v3 migration | `64fdca5` | 14 passed | `F08-legacy-migration-final`; exact legacy fixtures and recovery nodes. |
| Frontend | `64fdca5` | 59 files / 438 tests; lint, app/node TypeScript, build all exit 0 | `F08-frontend-final-64fdca5`. |
| Quality | `c05e6de` | F821/F822/F823, app/scripts F401, hygiene, and `git diff --check` exit 0 | `F08-quality-review-final`; Ruff 0.16.8 installed from the hash-pinned quality lock. Report-only selection emitted 6,699 lines and exit 0. |
| Copied-store/rollback | baseline `c685640`, candidate `64fdca5` | both modes opened, edited/recomputed/reopened; sources unchanged; candidate and old-reader SQLite integrity `ok` | `F08-compatibility-final`; later review fixes do not change storage schemas or persistence. |

The final review-fix commit `c05e6de` changes trust-crop authority, verifier evidence, workflow configuration and tests. Its affected selection, integration, real-media and quality lanes were rerun. Frontend code did not change after its `64fdca5` full pass.

## 6. V3T50 composed evidence

For each of `video` and `tracking_json`, `test_audit_v3_final_journey.py` creates a separate temporary store and records original source hashes. It exercises current generation/report state, a held external reader, ordered team/config/identity/event operations, accepted calibration, nullable fake-provider exposure and reconciliation, verified artifact reuse, a real killed child at the publication boundary with repeated recovery, undo, report/export and trust-crop generation, pinned synthetic TrackEval scoring, and fresh reopen. The video path generates a real FFmpeg source and uses explicitly synthetic post-perception source-pixel observations. The tracking path has no associated footage and invents none.

No actual detector, cloud provider, Daytona, GPU or paid worker is called. Fake-provider accounting verifies software semantics, not real billing.

## 7. Public/data compatibility and rollback

The trust-crop response adds `generationId`, `ballTeleportGeometryAvailable`, and `ballTeleportReasonCodes`; the endpoint adds an optional `generationId` query. Existing crop shape, authorization and other heuristic reasons remain. The UI requests the active generation, ignores superseded responses, and displays unavailable physical geometry without hiding other reasons.

Verification receipts move to schema version 2 with per-invocation IDs, checkout commit/tree, separate event commit, dirty digest, profile/stubs, exit, counts and selected nodes. The latest receipt is a compatibility view, never a cross-run sum. Verifier gates preserve their actual exit and non-authoritative display counts.

For F08.4/F08.6, exact `c685640` created one video and one tracking store with sources inside the copied directory. The candidate copy opened, applied a supported team-mapping recomputation, reopened, preserved both source hashes and returned SQLite `ok`. A separate untouched copy opened under exact `c685640`, preserved original generation IDs/frame counts/source hashes and returned SQLite `ok`. This proves copied pre-follow-up compatibility and restore of an untouched backup; it is not an in-place downgrade. True pre-v3 behavior is separately covered by the 14-test legacy lane.

No retired-route, status, authentication, remote-bundle or provider-admission contract was intentionally changed.

## 8. Suppression classification

| Site/operation | Classification | Outcome |
|---|---|---|
| `processor._persist_prepared_video_outputs`: ownership publication | Meaningful auxiliary degradation; fixed | Stable warning includes safe match/job/artifact/type only; primary committed generation and ready state remain. |
| `remote_worker._run_remote_job`: completed debug publication | Meaningful auxiliary degradation; fixed | Stable warning; successful primary result remains successful. |
| `remote_worker._run_remote_job`: failed debug publication | Meaningful auxiliary degradation; fixed | Stable warning; original failure, cleanup ownership and unknown billing exposure remain authoritative. |
| Descriptor/temporary-file/rollback closes | Safe cleanup suppression; retained | A secondary close failure must not replace the primary error. |
| Optional compatibility/probe reads | Deliberate compatibility boundary; retained | Existing explicit unavailable/fallback result remains the observable contract. |
| Provider/remote admission catches | Safety boundary; retained | Fail-closed/refusal behavior remains covered; no broad exception rewrite was attempted. |

## 9. Separately qualified capabilities

| Capability | Status in this pass | Prerequisite |
|---|---|---|
| Actual model inference / independent football accuracy | not run | Permitted footage, prediction-blind labels, admitted weights/runtime and declared denominator. |
| Representative full-match performance | not run | Representative source, hardware and workload measurement. |
| Real browser journey | not run | No browser harness is installed/configured; component/jsdom tests passed. |
| Real provider spending/billing | not run | Explicit credentials, cost ceiling, approval and reconciliation policy. |
| Actual GPU / paid worker | not run | Separate authorization and bounded runtime. |
| macOS runtime | not run | Matching macOS environment and lock execution. |
| Public deployment/security | not run | Separate threat model, tenancy/access policy and deployment authorization. |
| Main-push C05 rollout | not observed | Authorized integration followed by the actual workflow run ID and checkout SHA. |

## 10. Review, integrity and next action

An independent read-only `gpt-6-astra` reviewer examined `c685640..64fdca5` and reported no Critical issues and eight Important issues: missing workflow receipt activation, unsafe new evidence paths, conflicting geometry provenance, lost flat-legacy reads, outcome/selection conflation, stale gate relabelling, untracked bytes omitted from dirty identity, and incomplete V3T50 assertions. Commit `c05e6de` fixes all eight. `review-fixes-focused-04` passed 93 tests, and the final integration/real-media/quality lanes are green. Ponytail review confirms the fixes reuse existing snapshots, provenance, pytest hooks and shell evidence rather than adding a framework.

Final code `git diff --check` passed. The evidence tree is retained outside Git and hashed after capture. The exact next action is an owner integration choice: keep the local branch, merge locally, or authorize a push/PR. Only after integration can A04's actual main-push rollout be observed. The missing historical archive and canonical Python 3.11 run remain explicit evidence prerequisites, not reasons to invent replacement results.
