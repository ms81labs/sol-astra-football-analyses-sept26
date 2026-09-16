# Exact v7.3 Preservation Commits Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Preserve the exact audited v7.3 working state with an exhaustive 487-path disposition: commit 461 current files, restore 14 audited-base files, archive and untrack 11 regenerable files while retaining local bytes, and keep one VS Code file local-only.

**Architecture:** Twelve dependency-ordered commits preserve product cohorts, shared workflow foundations, all 199 reproduction scripts, their direct tests, deferred chain tests, local-artifact policy, and chronology. Every mutating action uses a literal Bash path array; no glob or directory-wide staging is allowed. The 14 deleted files are restored without a commit because their `bc4f4e30` blobs are already the blobs tracked by the preservation branch.

**Tech Stack:** Git plumbing, Bash arrays, SHA-256, Python 3.11, pytest, JSON, Markdown.

---

## Non-negotiable execution rules

- Execute from `/root/WorkSpace/fotball-analyst` on `recovery-history-batch-current`. Review and commit this plan alone before execution. Task 0 verifies that commit and creates the durable start marker without overwriting anything.
- Do not edit, format, regenerate, or normalize any of the 487 frozen paths. `git add` records their current bytes only. The only authored repository file during these actions is `.gitignore`.
- Never use `git add .`, `git add -A`, a glob, a directory path, or `git commit -a`. Before each commit, assert that `git diff --cached --name-only` equals that action's literal staged path set (plus `.gitignore` in Task 12).
- All 199 `one_shot_batch_entrypoint` files are committed. They are required by tests and reproduction; none is sent to the external archive.
- Do not prune, remove, or mutate any worktree or branch. The salvage manifest records unresolved content and zero approved supersessions.
- Ten frozen paths overlap unresolved paused-worktree variants. This plan commits the current recovery-worktree bytes only and makes no supersession, integration, or variant-selection claim for:

```text
backend/app/main.py
backend/app/proof_runtime.py
backend/app/runpod.py
backend/app/runpod_worker.py
backend/runpod_handler/handler.py
backend/tests/test_api.py
backend/tests/test_processor.py
backend/tests/test_runpod.py
backend/tests/test_runpod_handler.py
backend/tests/test_runpod_worker.py
```

- Five of those ten have conflicting paused-worktree variants and remain explicitly unresolved in the salvage archives: `backend/app/proof_runtime.py`, `backend/app/runpod.py`, `backend/app/runpod_worker.py`, `backend/runpod_handler/handler.py`, and `backend/tests/test_processor.py`.
- Dependency order is fixed: `backend/app/main.py` precedes its 38 dirty importers; `backend/scripts/football_external_real_eval_chain_common.py` precedes its 106 importers; `backend/scripts/video_to_analysis_operational_sprint_common.py` is committed with and after the first helper and precedes its 27 importers; `backend/scripts/video_to_analysis_promoted_runtime_monitoring_common.py` follows `main.py` plus the first helper and precedes its two importers. Task 11 defers every multi-script chain test until all imported scripts exist.

## Reusable per-commit gate

After defining an action's literal `paths` array and before committing, use this exact gate. It proves there is no accidental staging and that every listed current-byte file is staged as the same blob present in the worktree:

```bash
expected=$(mktemp)
actual=$(mktemp)
printf '%s\n' "${paths[@]}" | sort -u > "$expected"
git diff --cached --name-only | sort -u > "$actual"
diff -u "$expected" "$actual"
for path in "${paths[@]}"; do
  test "$(git hash-object -- "$path")" = "$(git rev-parse ":$path")"
done
git diff --cached --check
rm -f -- "$expected" "$actual"
```

Expected: `diff` and `git diff --cached --check` print nothing, every blob comparison succeeds, and the command exits 0. After every commit, run `test -z "$(git diff --cached --name-only)"`; expected exit 0.

### Task 0: Bind the live tree to the immutable raw freeze

**Action subject:** Fail closed unless the reviewed plan is the only path in `HEAD` and all 487 live paths are byte/status-identical to the verified raw freeze.

- [ ] Run this literal preflight from the repository root. It verifies the exact branch, requires this plan to be tracked and clean, and requires the `HEAD` commit's tree diff to contain this plan and no other path:

```bash
set -euo pipefail
repo='/root/WorkSpace/fotball-analyst'
plan='docs/superpowers/plans/2026-08-19-exact-v7-3-preservation-commits.md'
freeze='/root/WorkSpace/fotball-analyst/archive/2026-08-19-recovery-freeze'
marker='/root/WorkSpace/fotball-analyst-recovery-archive/2026-08-19-preservation-start.commit'
test "$PWD" = "$repo"
test "$(git branch --show-current)" = 'recovery-history-batch-current'
git ls-files --error-unmatch -- "$plan" >/dev/null
test -z "$(git status --porcelain=v1 -- "$plan")"
mapfile -d '' head_paths < <(git diff-tree --no-commit-id --name-only -r -z HEAD)
test "${#head_paths[@]}" -eq 1
test "${head_paths[0]}" = "$plan"
test -d "$freeze"
test -d "$(dirname "$marker")"
test ! -e "$marker"
```

Expected: every assertion exits 0. Any mismatch stops preservation before a frozen path is staged or restored.

- [ ] Verify the raw archive checksum manifest from the archive directory, so its relative filenames resolve against the intended immutable bundle:

```bash
freeze_manifest='docs/recovery/2026-08-19/raw-freeze-manifest.json'
expected_checksum_manifest_sha256=$(jq -er '.archive.checksumManifest.sha256' "$freeze_manifest")
test "$(sha256sum -- "$freeze/SHA256SUMS" | cut -d ' ' -f 1)" = "$expected_checksum_manifest_sha256"
(
  cd "$freeze"
  sha256sum --check SHA256SUMS
)
```

Expected: the tracked manifest authenticates `SHA256SUMS` itself as `8ad7c9b7f1ed0ffee3ad685049f69d7dadb83374648dbcc8624f17b3fad676b1`, then every entry in `SHA256SUMS` prints `OK`.

- [ ] Reconstruct `bc4f4e30` plus the binary tracked patch in an isolated index, compare the exact 487-path porcelain status with the freeze, and compare every live tracked payload/deletion with the reconstructed index:

```bash
verify_root=$(mktemp -d)
test -n "$verify_root"
trap 'rm -rf -- "$verify_root"' EXIT
mapfile -d '' frozen_paths < "$freeze/original-paths.nul"
mapfile -d '' tracked_paths < "$freeze/original-tracked-paths.nul"
test "${#frozen_paths[@]}" -eq 487
test "${#tracked_paths[@]}" -eq 44
git status --porcelain=v1 -z --untracked-files=normal > "$verify_root/live-status.nul"
cmp -- "$freeze/original-status.nul" "$verify_root/live-status.nul"
isolated_index="$verify_root/index"
test ! -e "$isolated_index"
GIT_INDEX_FILE="$isolated_index" git read-tree bc4f4e30
GIT_INDEX_FILE="$isolated_index" git apply --cached --binary "$freeze/original-tracked.patch"
live_blob_count=0
deleted_count=0
for path in "${tracked_paths[@]}"; do
  if GIT_INDEX_FILE="$isolated_index" git ls-files --error-unmatch -- "$path" >/dev/null 2>&1; then
    test -f "$path"
    expected_blob=$(GIT_INDEX_FILE="$isolated_index" git rev-parse ":$path")
    test "$(git hash-object -- "$path")" = "$expected_blob"
    index_mode=$(GIT_INDEX_FILE="$isolated_index" git ls-files -s -- "$path" | awk '{print $1}')
    case "$index_mode" in
      100644) expected_executable=0 ;;
      100755) expected_executable=1 ;;
      *) printf 'unsupported tracked mode %s for %s\n' "$index_mode" "$path" >&2; exit 1 ;;
    esac
    live_executable=$(python3 - "$path" <<'PY'
import os
import sys
print(1 if os.lstat(sys.argv[1]).st_mode & 0o111 else 0)
PY
)
    test "$live_executable" -eq "$expected_executable"
    live_blob_count=$((live_blob_count + 1))
  else
    test ! -e "$path"
    deleted_count=$((deleted_count + 1))
  fi
done
test "$live_blob_count" -eq 30
test "$deleted_count" -eq 14
```

Expected: the NUL-delimited status is byte-identical to `original-status.nul`; the isolated index accepts the binary patch; all 30 live tracked payloads and executable-bit modes match reconstructed blobs/modes; all 14 recorded deletions are absent.

- [ ] Validate the untracked tar member set and extraction safety, extract into the private temporary directory, and compare all 443 live untracked payloads byte-for-byte:

```bash
untracked_extract="$verify_root/untracked"
mkdir -- "$untracked_extract"
python3 - "$freeze/original-untracked.tar.gz" "$freeze/original-untracked-paths.nul" "$untracked_extract" "$repo" <<'PY'
from pathlib import Path, PurePosixPath
import os
import stat
import sys
import tarfile

archive = Path(sys.argv[1])
path_list = Path(sys.argv[2])
destination = Path(sys.argv[3])
repository = Path(sys.argv[4])
expected = [item.decode("utf-8") for item in path_list.read_bytes().split(b"\0") if item]
if len(expected) != 443 or len(set(expected)) != 443:
    raise SystemExit("frozen untracked path list is not exactly 443 unique paths")
with tarfile.open(archive, "r:gz") as bundle:
    members = bundle.getmembers()
    names = [member.name for member in members]
    if len(names) != 443 or sorted(names) != sorted(expected):
        raise SystemExit("untracked archive member set differs from frozen path list")
    for member in members:
        path = PurePosixPath(member.name)
        if path.is_absolute() or ".." in path.parts:
            raise SystemExit(f"unsafe archive member: {member.name}")
        if not (member.isfile() or member.issym() or member.islnk()):
            raise SystemExit(f"unsupported archive member type: {member.name}")
        if member.issym() or member.islnk():
            link = PurePosixPath(member.linkname)
            if link.is_absolute() or ".." in link.parts:
                raise SystemExit(f"unsafe archive link: {member.name}")
        live = os.lstat(repository / member.name)
        if member.isfile():
            if not stat.S_ISREG(live.st_mode):
                raise SystemExit(f"live untracked type differs from regular member: {member.name}")
            if (member.mode & 0o111) != (live.st_mode & 0o111):
                raise SystemExit(f"live untracked executable bits differ: {member.name}")
        elif member.issym():
            if not stat.S_ISLNK(live.st_mode) or os.readlink(repository / member.name) != member.linkname:
                raise SystemExit(f"live untracked symlink differs: {member.name}")
        elif member.islnk() and not stat.S_ISREG(live.st_mode):
            raise SystemExit(f"live untracked hard-link payload is not regular: {member.name}")
    bundle.extractall(destination, members=members, filter="data")
PY
mapfile -d '' untracked_paths < "$freeze/original-untracked-paths.nul"
test "${#untracked_paths[@]}" -eq 443
for path in "${untracked_paths[@]}"; do
  test -e "$path" || test -L "$path"
  test -e "$untracked_extract/$path" || test -L "$untracked_extract/$path"
  if test -L "$path"; then
    test -L "$untracked_extract/$path"
    test "$(readlink -- "$path")" = "$(readlink -- "$untracked_extract/$path")"
  else
    cmp -- "$path" "$untracked_extract/$path"
  fi
done
```

Expected: the tar contains exactly the 443 frozen paths, contains no unsafe member/link, extracts only under the private temporary root, and every live payload, regular-file executable-bit mode, or symlink target matches its archived counterpart.

- [ ] Remove only the private verification directory, create the start marker with shell no-clobber semantics, and bind it to the already verified `HEAD`:

```bash
trap - EXIT
rm -rf -- "$verify_root"
test ! -e "$marker"
set -o noclobber
printf '%s\n' "$(git rev-parse HEAD)" > "$marker"
set +o noclobber
test "$(cat "$marker")" = "$(git rev-parse HEAD)"
```

Expected: the marker is newly created, contains exactly `HEAD`, and no existing marker or archive is overwritten.

### Task 1: Restore the 14 unapproved deletions from audited base

**Action subject:** Restore unresolved v7.1 evidence from `bc4f4e30`; no commit is created because the verified blobs equal the branch's tracked blobs.

- [ ] Define the only paths this action may restore:

```bash
paths=(
  'backend/storage/trained_detector_candidates/touchline_detector_candidate_v7/v7_1_positive_candidate_mining_expansion_v1/batch_outcome_analysis.json'
  'backend/storage/trained_detector_candidates/touchline_detector_candidate_v7/v7_1_positive_candidate_mining_expansion_v1/batch_outcome_analysis.md'
  'backend/storage/trained_detector_candidates/touchline_detector_candidate_v7/v7_1_positive_candidate_mining_expansion_v1/corrected_label_overlay.json'
  'backend/storage/trained_detector_candidates/touchline_detector_candidate_v7/v7_1_positive_candidate_mining_expansion_v1/correction_review_index.html'
  'backend/storage/trained_detector_candidates/touchline_detector_candidate_v7/v7_1_positive_candidate_mining_expansion_v1/decision_matrix.json'
  'backend/storage/trained_detector_candidates/touchline_detector_candidate_v7/v7_1_positive_candidate_mining_expansion_v1/new_mined_candidate_manifest.json'
  'backend/storage/trained_detector_candidates/touchline_detector_candidate_v7/v7_1_positive_candidate_mining_expansion_v1/salvage_candidate_summary.json'
  'backend/storage/trained_detector_candidates/touchline_detector_candidate_v7/v7_1_positive_candidate_mining_expansion_v1/v7_1_positive_candidate_mining_expansion_summary.json'
  'backend/storage/trained_detector_candidates/touchline_detector_candidate_v7/v7_1_positive_diversity_manual_review_resolution_v1/batch_outcome_analysis.json'
  'backend/storage/trained_detector_candidates/touchline_detector_candidate_v7/v7_1_positive_diversity_manual_review_resolution_v1/batch_outcome_analysis.md'
  'backend/storage/trained_detector_candidates/touchline_detector_candidate_v7/v7_1_positive_diversity_manual_review_resolution_v1/decision_matrix.json'
  'backend/storage/trained_detector_candidates/touchline_detector_candidate_v7/v7_1_positive_diversity_manual_review_resolution_v1/reviewed_positive_resolution_counts.json'
  'backend/storage/trained_detector_candidates/touchline_detector_candidate_v7/v7_1_positive_diversity_manual_review_resolution_v1/reviewed_positive_truth_additions.json'
  'backend/storage/trained_detector_candidates/touchline_detector_candidate_v7/v7_1_positive_diversity_manual_review_resolution_v1/v7_1_positive_diversity_manual_review_resolution_summary.json'
)
```

- [ ] Verify each inventory blob before restoration, then restore with the literal array:

```bash
for path in "${paths[@]}"; do
  expected_blob=$(jq -r --arg path "$path" '.deletionEvidence[] | select(.path == $path) | .lastReachableBlobId' docs/recovery/2026-08-19/current-tree-inventory.json)
  test -n "$expected_blob"
  git cat-file -e "${expected_blob}^{blob}"
  test "$(git rev-parse "bc4f4e30:$path")" = "$expected_blob"
  test "$(git rev-parse "HEAD:$path")" = "$expected_blob"
done
git restore --source=bc4f4e30 -- "${paths[@]}"
```

- [ ] Focused verification:

```bash
for path in "${paths[@]}"; do
  test -f "$path"
  test "$(git hash-object -- "$path")" = "$(git rev-parse "bc4f4e30:$path")"
done
test -z "$(git diff --name-only -- "${paths[@]}")"
```

Expected: all 14 files exist, every current blob equals its audited-base blob, the scoped diff is empty, and no commit is created.

### Task 2: Preserve the match-bundle API cohort

**Commit subject:** `feat: preserve match bundle API`

- [ ] Stage only this atomic source/importer/test cohort:

```bash
paths=(
  'backend/app/main.py'
  'backend/app/match_bundle.py'
  'backend/tests/test_api.py'
  'backend/tests/test_external_soccernet_product_route.py'
  'backend/tests/test_external_soccertrack_analysis_product_route.py'
  'backend/tests/test_external_soccertrack_product_route.py'
)
git add -- "${paths[@]}"
```

- [ ] Run the reusable per-commit gate, then the focused tests:

```bash
python3 -m pytest -q backend/tests/test_api.py backend/tests/test_external_soccernet_product_route.py backend/tests/test_external_soccertrack_analysis_product_route.py backend/tests/test_external_soccertrack_product_route.py
```

Expected: all selected tests pass. This commit establishes `main.py` and `match_bundle.py` before later scripts import them.

- [ ] Commit with `git commit -m "feat: preserve match bundle API"`.

### Task 3: Preserve the local and RunPod runtime cohort

**Commit subject:** `feat: preserve v7.3 runtime cohort`

- [ ] Stage the runtime source, processor/RunPod tests, and both active release JSON files together:

```bash
paths=(
  'backend/app/proof_runtime.py'
  'backend/app/runpod.py'
  'backend/app/runpod_worker.py'
  'backend/runpod_handler/handler.py'
  'backend/storage/benchmark_suites/frozen-viable-baseline-slice-suite/detector_candidate_promotion.json'
  'backend/storage/runtime/promoted_touchline_detector_candidate.json'
  'backend/tests/test_processor.py'
  'backend/tests/test_runpod.py'
  'backend/tests/test_runpod_handler.py'
  'backend/tests/test_runpod_worker.py'
)
git add -- "${paths[@]}"
```

- [ ] Run the reusable per-commit gate, then:

```bash
python3 -m pytest -q backend/tests/test_processor.py backend/tests/test_runpod.py backend/tests/test_runpod_handler.py backend/tests/test_runpod_worker.py
```

Expected: all selected runtime tests pass. The current bytes are preserved without selecting or superseding any paused-worktree variant.

- [ ] Commit with `git commit -m "feat: preserve v7.3 runtime cohort"`.

### Task 4: Preserve shared workflow foundations

**Commit subject:** `feat: preserve workflow chain foundations`

- [ ] Stage the shared modules before every importer:

```bash
paths=(
  'backend/scripts/football_external_real_eval_chain_common.py'
  'backend/scripts/run_video_to_analysis_detector_evaluation_chain_common.py'
  'backend/scripts/video_to_analysis_operational_sprint_common.py'
  'backend/scripts/video_to_analysis_promoted_runtime_monitoring_common.py'
)
git add -- "${paths[@]}"
```

- [ ] Run the reusable per-commit gate, then compile the exact modules:

```bash
python3 -m py_compile "${paths[@]}"
```

Expected: compilation exits 0. The first helper is available to 106 later importers; the operational helper (which depends on it) is available to 27 later importers; the promoted monitoring helper now has both `main.py` and the first helper available and precedes its two later importers.

- [ ] Commit with `git commit -m "feat: preserve workflow chain foundations"`.

### Task 5: Preserve the SoccerNet miss-review interface

**Commit subject:** `feat: preserve SoccerNet miss review UI`

- [ ] After the shared helper is committed, stage the server, UI, manual-review collector, and both direct tests atomically:

```bash
paths=(
  'backend/review_ui/football_external_soccernet_detector_miss_review/index.html'
  'backend/scripts/run_football_external_soccernet_detector_miss_manual_review_resolution.py'
  'backend/scripts/serve_football_external_soccernet_detector_miss_review_ui.py'
  'backend/tests/test_run_football_external_soccernet_detector_miss_manual_review_resolution.py'
  'backend/tests/test_serve_football_external_soccernet_detector_miss_review_ui.py'
)
git add -- "${paths[@]}"
```

- [ ] Run the reusable per-commit gate, then:

```bash
python3 -m pytest -q backend/tests/test_run_football_external_soccernet_detector_miss_manual_review_resolution.py backend/tests/test_serve_football_external_soccernet_detector_miss_review_ui.py
```

Expected: both focused collector/review-server test files pass, including clean-checkout collection after the helper commit.

- [ ] Commit with `git commit -m "feat: preserve SoccerNet miss review UI"`.

### Task 6: Preserve external benchmark and safe-source workflows

**Commit subject:** `feat: preserve external benchmark workflows`

- [ ] Stage all 22 entrypoints and their 17 direct tests; deliberately exclude the real-evaluation chain test until Task 11:

```bash
paths=(
  'backend/scripts/run_football_external_benchmark_bounded_execution_smoke.py'
  'backend/scripts/run_football_external_benchmark_bounded_real_execution.py'
  'backend/scripts/run_football_external_benchmark_dataset_governance_plan.py'
  'backend/scripts/run_football_external_benchmark_execution_approval.py'
  'backend/scripts/run_football_external_benchmark_harness_prep.py'
  'backend/scripts/run_football_external_benchmark_harness_smoke.py'
  'backend/scripts/run_football_external_benchmark_lane_closeout.py'
  'backend/scripts/run_football_external_benchmark_operationalization_plan.py'
  'backend/scripts/run_football_external_benchmark_product_decision_surface.py'
  'backend/scripts/run_football_external_benchmark_product_decision_surface_route_implementation.py'
  'backend/scripts/run_football_external_benchmark_product_ui_binding.py'
  'backend/scripts/run_football_external_benchmark_product_ui_route_implementation.py'
  'backend/scripts/run_football_external_benchmark_real_evaluation_approval.py'
  'backend/scripts/run_football_external_benchmark_real_evaluation_design.py'
  'backend/scripts/run_football_external_benchmark_real_report_and_product_binding.py'
  'backend/scripts/run_football_external_benchmark_real_source_path_consolidation.py'
  'backend/scripts/run_football_external_benchmark_report_smoke.py'
  'backend/scripts/run_football_external_safe_adapter_fixture_implementation.py'
  'backend/scripts/run_football_external_safe_source_adapter_smoke_test.py'
  'backend/scripts/run_football_external_safe_source_controlled_sample_fetch.py'
  'backend/scripts/run_football_external_safe_source_sample_download_approval.py'
  'backend/scripts/run_football_external_safe_source_sample_ingestion_plan.py'
  'backend/tests/test_run_football_external_benchmark_bounded_execution_smoke.py'
  'backend/tests/test_run_football_external_benchmark_execution_approval.py'
  'backend/tests/test_run_football_external_benchmark_harness_prep.py'
  'backend/tests/test_run_football_external_benchmark_harness_smoke.py'
  'backend/tests/test_run_football_external_benchmark_lane_closeout.py'
  'backend/tests/test_run_football_external_benchmark_operationalization_plan.py'
  'backend/tests/test_run_football_external_benchmark_product_decision_surface.py'
  'backend/tests/test_run_football_external_benchmark_product_decision_surface_route_implementation.py'
  'backend/tests/test_run_football_external_benchmark_product_ui_binding.py'
  'backend/tests/test_run_football_external_benchmark_product_ui_route_implementation.py'
  'backend/tests/test_run_football_external_benchmark_real_evaluation_design.py'
  'backend/tests/test_run_football_external_benchmark_report_smoke.py'
  'backend/tests/test_run_football_external_safe_adapter_fixture_implementation.py'
  'backend/tests/test_run_football_external_safe_source_adapter_smoke_test.py'
  'backend/tests/test_run_football_external_safe_source_controlled_sample_fetch.py'
  'backend/tests/test_run_football_external_safe_source_sample_download_approval.py'
  'backend/tests/test_run_football_external_safe_source_sample_ingestion_plan.py'
)
git add -- "${paths[@]}"
```

- [ ] Run the reusable per-commit gate, then run exactly the tests in the staged path array:

```bash
tests=()
for path in "${paths[@]}"; do [[ "$path" == backend/tests/test_*.py ]] && tests+=("$path"); done
python3 -m pytest -q "${tests[@]}"
```

Expected: all 17 selected tests pass.

- [ ] Commit with `git commit -m "feat: preserve external benchmark workflows"`.

### Task 7: Preserve SoccerNet workflows

**Commit subject:** `feat: preserve SoccerNet workflows`

- [ ] Stage the remaining 52 SoccerNet entrypoints and their 52 direct tests atomically:

```bash
paths=(
  'backend/scripts/run_football_external_soccernet_analysis_product_api_smoke.py'
  'backend/scripts/run_football_external_soccernet_analysis_product_lane_closeout.py'
  'backend/scripts/run_football_external_soccernet_analysis_product_ui_binding.py'
  'backend/scripts/run_football_external_soccernet_analysis_product_ui_route_implementation.py'
  'backend/scripts/run_football_external_soccernet_api_listing_probe.py'
  'backend/scripts/run_football_external_soccernet_api_metadata_probe.py'
  'backend/scripts/run_football_external_soccernet_benchmark_adapter_contract_prep.py'
  'backend/scripts/run_football_external_soccernet_bounded_analysis_execution.py'
  'backend/scripts/run_football_external_soccernet_bounded_analysis_execution_approval.py'
  'backend/scripts/run_football_external_soccernet_bounded_analysis_lane_closeout.py'
  'backend/scripts/run_football_external_soccernet_bounded_analysis_report_smoke.py'
  'backend/scripts/run_football_external_soccernet_bounded_product_validation_execution.py'
  'backend/scripts/run_football_external_soccernet_bounded_product_validation_execution_approval.py'
  'backend/scripts/run_football_external_soccernet_bounded_product_validation_plan.py'
  'backend/scripts/run_football_external_soccernet_bounded_product_validation_report_binding.py'
  'backend/scripts/run_football_external_soccernet_broader_validation_choice.py'
  'backend/scripts/run_football_external_soccernet_controlled_label_metadata_probe.py'
  'backend/scripts/run_football_external_soccernet_controlled_label_sample_fetch.py'
  'backend/scripts/run_football_external_soccernet_controlled_label_sample_fetch_approval.py'
  'backend/scripts/run_football_external_soccernet_controlled_video_sample_fetch.py'
  'backend/scripts/run_football_external_soccernet_detector_miss_capture_and_label_queue.py'
  'backend/scripts/run_football_external_soccernet_event_adapter_fixture_materialization.py'
  'backend/scripts/run_football_external_soccernet_event_adapter_smoke_test.py'
  'backend/scripts/run_football_external_soccernet_event_benchmark_smoke.py'
  'backend/scripts/run_football_external_soccernet_event_lane_closeout.py'
  'backend/scripts/run_football_external_soccernet_event_report_contract_prep.py'
  'backend/scripts/run_football_external_soccernet_event_report_product_integration.py'
  'backend/scripts/run_football_external_soccernet_event_report_smoke.py'
  'backend/scripts/run_football_external_soccernet_full_analysis_execution.py'
  'backend/scripts/run_football_external_soccernet_full_analysis_execution_approval.py'
  'backend/scripts/run_football_external_soccernet_full_analysis_lane_closeout.py'
  'backend/scripts/run_football_external_soccernet_full_analysis_product_integration.py'
  'backend/scripts/run_football_external_soccernet_full_analysis_report_smoke.py'
  'backend/scripts/run_football_external_soccernet_label_fetch_contract_repair.py'
  'backend/scripts/run_football_external_soccernet_label_schema_ingestion_probe.py'
  'backend/scripts/run_football_external_soccernet_nda_api_access_approval.py'
  'backend/scripts/run_football_external_soccernet_real_sample_product_pipeline_training_decision.py'
  'backend/scripts/run_football_external_soccernet_split_archive_access_review.py'
  'backend/scripts/run_football_external_soccernet_split_archive_range_index_probe.py'
  'backend/scripts/run_football_external_soccernet_split_archive_size_probe.py'
  'backend/scripts/run_football_external_soccernet_video_analysis_dry_run.py'
  'backend/scripts/run_football_external_soccernet_video_analysis_dry_run_approval.py'
  'backend/scripts/run_football_external_soccernet_video_analysis_dry_run_product_bridge_smoke.py'
  'backend/scripts/run_football_external_soccernet_video_frame_probe.py'
  'backend/scripts/run_football_external_soccernet_video_member_extract.py'
  'backend/scripts/run_football_external_soccernet_video_member_extract_approval.py'
  'backend/scripts/run_football_external_soccernet_video_product_path_smoke.py'
  'backend/scripts/run_football_external_soccernet_video_sample_download_approval.py'
  'backend/scripts/run_football_external_soccernet_video_sample_probe.py'
  'backend/scripts/run_football_external_soccernet_video_to_analysis_bridge_prep.py'
  'backend/scripts/run_football_external_soccernet_zip_label_member_extract.py'
  'backend/scripts/run_football_external_soccernet_zip_label_member_extract_approval.py'
  'backend/tests/test_run_football_external_soccernet_analysis_product_api_smoke.py'
  'backend/tests/test_run_football_external_soccernet_analysis_product_lane_closeout.py'
  'backend/tests/test_run_football_external_soccernet_analysis_product_ui_binding.py'
  'backend/tests/test_run_football_external_soccernet_analysis_product_ui_route_implementation.py'
  'backend/tests/test_run_football_external_soccernet_api_listing_probe.py'
  'backend/tests/test_run_football_external_soccernet_api_metadata_probe.py'
  'backend/tests/test_run_football_external_soccernet_benchmark_adapter_contract_prep.py'
  'backend/tests/test_run_football_external_soccernet_bounded_analysis_execution.py'
  'backend/tests/test_run_football_external_soccernet_bounded_analysis_execution_approval.py'
  'backend/tests/test_run_football_external_soccernet_bounded_analysis_lane_closeout.py'
  'backend/tests/test_run_football_external_soccernet_bounded_analysis_report_smoke.py'
  'backend/tests/test_run_football_external_soccernet_bounded_product_validation_execution.py'
  'backend/tests/test_run_football_external_soccernet_bounded_product_validation_execution_approval.py'
  'backend/tests/test_run_football_external_soccernet_bounded_product_validation_plan.py'
  'backend/tests/test_run_football_external_soccernet_bounded_product_validation_report_binding.py'
  'backend/tests/test_run_football_external_soccernet_broader_validation_choice.py'
  'backend/tests/test_run_football_external_soccernet_controlled_label_metadata_probe.py'
  'backend/tests/test_run_football_external_soccernet_controlled_label_sample_fetch.py'
  'backend/tests/test_run_football_external_soccernet_controlled_label_sample_fetch_approval.py'
  'backend/tests/test_run_football_external_soccernet_controlled_video_sample_fetch.py'
  'backend/tests/test_run_football_external_soccernet_detector_miss_capture_and_label_queue.py'
  'backend/tests/test_run_football_external_soccernet_event_adapter_fixture_materialization.py'
  'backend/tests/test_run_football_external_soccernet_event_adapter_smoke_test.py'
  'backend/tests/test_run_football_external_soccernet_event_benchmark_smoke.py'
  'backend/tests/test_run_football_external_soccernet_event_lane_closeout.py'
  'backend/tests/test_run_football_external_soccernet_event_report_contract_prep.py'
  'backend/tests/test_run_football_external_soccernet_event_report_product_integration.py'
  'backend/tests/test_run_football_external_soccernet_event_report_smoke.py'
  'backend/tests/test_run_football_external_soccernet_full_analysis_execution.py'
  'backend/tests/test_run_football_external_soccernet_full_analysis_execution_approval.py'
  'backend/tests/test_run_football_external_soccernet_full_analysis_lane_closeout.py'
  'backend/tests/test_run_football_external_soccernet_full_analysis_product_integration.py'
  'backend/tests/test_run_football_external_soccernet_full_analysis_report_smoke.py'
  'backend/tests/test_run_football_external_soccernet_label_fetch_contract_repair.py'
  'backend/tests/test_run_football_external_soccernet_label_schema_ingestion_probe.py'
  'backend/tests/test_run_football_external_soccernet_nda_api_access_approval.py'
  'backend/tests/test_run_football_external_soccernet_real_sample_product_pipeline_training_decision.py'
  'backend/tests/test_run_football_external_soccernet_split_archive_access_review.py'
  'backend/tests/test_run_football_external_soccernet_split_archive_range_index_probe.py'
  'backend/tests/test_run_football_external_soccernet_split_archive_size_probe.py'
  'backend/tests/test_run_football_external_soccernet_video_analysis_dry_run.py'
  'backend/tests/test_run_football_external_soccernet_video_analysis_dry_run_approval.py'
  'backend/tests/test_run_football_external_soccernet_video_analysis_dry_run_product_bridge_smoke.py'
  'backend/tests/test_run_football_external_soccernet_video_frame_probe.py'
  'backend/tests/test_run_football_external_soccernet_video_member_extract.py'
  'backend/tests/test_run_football_external_soccernet_video_member_extract_approval.py'
  'backend/tests/test_run_football_external_soccernet_video_product_path_smoke.py'
  'backend/tests/test_run_football_external_soccernet_video_sample_download_approval.py'
  'backend/tests/test_run_football_external_soccernet_video_sample_probe.py'
  'backend/tests/test_run_football_external_soccernet_video_to_analysis_bridge_prep.py'
  'backend/tests/test_run_football_external_soccernet_zip_label_member_extract.py'
  'backend/tests/test_run_football_external_soccernet_zip_label_member_extract_approval.py'
)
git add -- "${paths[@]}"
```

- [ ] Run the reusable per-commit gate, then run exactly the tests in the staged array:

```bash
tests=()
for path in "${paths[@]}"; do [[ "$path" == backend/tests/test_*.py ]] && tests+=("$path"); done
python3 -m pytest -q "${tests[@]}"
```

Expected: all 52 selected tests pass.

- [ ] Commit with `git commit -m "feat: preserve SoccerNet workflows"`.

### Task 8: Preserve SoccerTrack workflows

**Commit subject:** `feat: preserve SoccerTrack workflows`

- [ ] Stage all 21 entrypoints and their 21 direct tests atomically:

```bash
paths=(
  'backend/scripts/run_football_external_soccertrack_adapter_smoke_test.py'
  'backend/scripts/run_football_external_soccertrack_analysis_product_lane_closeout.py'
  'backend/scripts/run_football_external_soccertrack_analysis_product_ui_binding.py'
  'backend/scripts/run_football_external_soccertrack_analysis_product_ui_route_implementation.py'
  'backend/scripts/run_football_external_soccertrack_analysis_report_smoke.py'
  'backend/scripts/run_football_external_soccertrack_authenticated_fixture_access_approval.py'
  'backend/scripts/run_football_external_soccertrack_controlled_sample_fetch.py'
  'backend/scripts/run_football_external_soccertrack_fixture_source_access_review.py'
  'backend/scripts/run_football_external_soccertrack_google_drive_bounded_fixture_fetch.py'
  'backend/scripts/run_football_external_soccertrack_google_drive_fixture_access_probe.py'
  'backend/scripts/run_football_external_soccertrack_lane_closeout.py'
  'backend/scripts/run_football_external_soccertrack_match_bundle_bridge_smoke.py'
  'backend/scripts/run_football_external_soccertrack_metadata_adapter_smoke.py'
  'backend/scripts/run_football_external_soccertrack_product_route_smoke.py'
  'backend/scripts/run_football_external_soccertrack_sample_fixture_materialization.py'
  'backend/scripts/run_football_external_soccertrack_sample_fixture_materialization_approval.py'
  'backend/scripts/run_football_external_soccertrack_sample_ingestion_contract_prep.py'
  'backend/scripts/run_football_external_soccertrack_sample_schema_probe.py'
  'backend/scripts/run_football_external_soccertrack_schema_doc_fetch.py'
  'backend/scripts/run_football_external_soccertrack_schema_doc_fetch_approval.py'
  'backend/scripts/run_football_external_soccertrack_schema_doc_parse.py'
  'backend/tests/test_run_football_external_soccertrack_adapter_smoke_test.py'
  'backend/tests/test_run_football_external_soccertrack_analysis_product_lane_closeout.py'
  'backend/tests/test_run_football_external_soccertrack_analysis_product_ui_binding.py'
  'backend/tests/test_run_football_external_soccertrack_analysis_product_ui_route_implementation.py'
  'backend/tests/test_run_football_external_soccertrack_analysis_report_smoke.py'
  'backend/tests/test_run_football_external_soccertrack_authenticated_fixture_access_approval.py'
  'backend/tests/test_run_football_external_soccertrack_controlled_sample_fetch.py'
  'backend/tests/test_run_football_external_soccertrack_fixture_source_access_review.py'
  'backend/tests/test_run_football_external_soccertrack_google_drive_bounded_fixture_fetch.py'
  'backend/tests/test_run_football_external_soccertrack_google_drive_fixture_access_probe.py'
  'backend/tests/test_run_football_external_soccertrack_lane_closeout.py'
  'backend/tests/test_run_football_external_soccertrack_match_bundle_bridge_smoke.py'
  'backend/tests/test_run_football_external_soccertrack_metadata_adapter_smoke.py'
  'backend/tests/test_run_football_external_soccertrack_product_route_smoke.py'
  'backend/tests/test_run_football_external_soccertrack_sample_fixture_materialization.py'
  'backend/tests/test_run_football_external_soccertrack_sample_fixture_materialization_approval.py'
  'backend/tests/test_run_football_external_soccertrack_sample_ingestion_contract_prep.py'
  'backend/tests/test_run_football_external_soccertrack_sample_schema_probe.py'
  'backend/tests/test_run_football_external_soccertrack_schema_doc_fetch.py'
  'backend/tests/test_run_football_external_soccertrack_schema_doc_fetch_approval.py'
  'backend/tests/test_run_football_external_soccertrack_schema_doc_parse.py'
)
git add -- "${paths[@]}"
```

- [ ] Run the reusable per-commit gate and the exact staged test subset:

```bash
tests=()
for path in "${paths[@]}"; do [[ "$path" == backend/tests/test_*.py ]] && tests+=("$path"); done
python3 -m pytest -q "${tests[@]}"
```

Expected: all 21 selected tests pass.

- [ ] Commit with `git commit -m "feat: preserve SoccerTrack workflows"`.

### Task 9: Preserve canonical, product-smoke, and v7 workflows

**Commit subject:** `feat: preserve v7 release workflows`

- [ ] Stage these 17 entrypoints with their 16 direct tests. The canonical exporter follows the match-bundle cohort from Task 2.

```bash
paths=(
  'backend/scripts/run_canonical_match_bundle_export.py'
  'backend/scripts/run_product_video_to_analysis_finish_line_execution.py'
  'backend/scripts/run_product_video_to_analysis_normal_storage_smoke.py'
  'backend/scripts/run_product_video_to_analysis_smoke.py'
  'backend/scripts/run_product_video_to_analysis_smoke_isolated.py'
  'backend/scripts/run_promoted_v6_reviewed_positive_residual_proposal_generation_fix.py'
  'backend/scripts/run_v7_2_runtime_registry_product_path_binding.py'
  'backend/scripts/run_v7_3_bounded_retrain.py'
  'backend/scripts/run_v7_3_crop_probe_precision_guardrail_audit.py'
  'backend/scripts/run_v7_3_export_label_overlay_audit.py'
  'backend/scripts/run_v7_3_full_pipeline_non_promotion_eval.py'
  'backend/scripts/run_v7_3_post_runtime_default_source_robustness_validation.py'
  'backend/scripts/run_v7_3_promotion_readiness_validation.py'
  'backend/scripts/run_v7_3_runtime_default_change_validation.py'
  'backend/scripts/run_v7_3_runtime_default_rollout_closeout.py'
  'backend/scripts/run_v7_3_training_manifest_prep_from_soccernet_real_misses.py'
  'backend/scripts/run_v7_4_training_decision_from_real_misses.py'
  'backend/tests/test_run_canonical_match_bundle_export.py'
  'backend/tests/test_run_product_video_to_analysis_finish_line_execution.py'
  'backend/tests/test_run_product_video_to_analysis_normal_storage_smoke.py'
  'backend/tests/test_run_product_video_to_analysis_smoke.py'
  'backend/tests/test_run_product_video_to_analysis_smoke_isolated.py'
  'backend/tests/test_run_v7_2_runtime_registry_product_path_binding.py'
  'backend/tests/test_run_v7_3_bounded_retrain.py'
  'backend/tests/test_run_v7_3_crop_probe_precision_guardrail_audit.py'
  'backend/tests/test_run_v7_3_export_label_overlay_audit.py'
  'backend/tests/test_run_v7_3_full_pipeline_non_promotion_eval.py'
  'backend/tests/test_run_v7_3_post_runtime_default_source_robustness_validation.py'
  'backend/tests/test_run_v7_3_promotion_readiness_validation.py'
  'backend/tests/test_run_v7_3_runtime_default_change_validation.py'
  'backend/tests/test_run_v7_3_runtime_default_rollout_closeout.py'
  'backend/tests/test_run_v7_3_training_manifest_prep_from_soccernet_real_misses.py'
  'backend/tests/test_run_v7_4_training_decision_from_real_misses.py'
)
git add -- "${paths[@]}"
```

- [ ] Run the reusable per-commit gate and the exact staged test subset:

```bash
tests=()
for path in "${paths[@]}"; do [[ "$path" == backend/tests/test_*.py ]] && tests+=("$path"); done
python3 -m pytest -q "${tests[@]}"
```

Expected: all 16 selected tests pass.

- [ ] Commit with `git commit -m "feat: preserve v7 release workflows"`.

### Task 10: Preserve video-to-analysis workflows

**Commit subject:** `feat: preserve video analysis workflows`

- [ ] Stage all remaining video-to-analysis entrypoints with their direct tests and the one chain fixture those tests import. Leave the other eight chain tests for Task 11.

The moved fixture is `backend/tests/test_run_video_to_analysis_promoted_runtime_post_release_monitoring_chain.py`; it is imported by `backend/tests/test_run_video_to_analysis_operational_backlog_prioritization.py`, `backend/tests/test_run_video_to_analysis_operator_dashboard_polish.py`, `backend/tests/test_run_video_to_analysis_steady_state_monitoring_cycle.py`, and `backend/tests/test_run_video_to_analysis_storage_retention_and_artifact_hygiene.py`.

```bash
paths=(
  'backend/scripts/run_video_to_analysis_acceptance_report_product_backlog.py'
  'backend/scripts/run_video_to_analysis_acceptance_report_route_binding.py'
  'backend/scripts/run_video_to_analysis_bounded_next_sample_closeout.py'
  'backend/scripts/run_video_to_analysis_bounded_next_sample_execution.py'
  'backend/scripts/run_video_to_analysis_bounded_next_sample_execution_approval.py'
  'backend/scripts/run_video_to_analysis_bounded_next_sample_report_route_binding.py'
  'backend/scripts/run_video_to_analysis_broader_real_video_acceptance_approval.py'
  'backend/scripts/run_video_to_analysis_broader_real_video_acceptance_closeout.py'
  'backend/scripts/run_video_to_analysis_broader_real_video_acceptance_execution.py'
  'backend/scripts/run_video_to_analysis_broader_real_video_acceptance_suite_prep.py'
  'backend/scripts/run_video_to_analysis_current_release_acceptance_decision_surface.py'
  'backend/scripts/run_video_to_analysis_detector_evaluation_bounded_existing_artifact_execution.py'
  'backend/scripts/run_video_to_analysis_detector_evaluation_lane_closeout.py'
  'backend/scripts/run_video_to_analysis_detector_evaluation_reentry_approval.py'
  'backend/scripts/run_video_to_analysis_detector_evaluation_reentry_plan.py'
  'backend/scripts/run_video_to_analysis_detector_evaluation_report_binding.py'
  'backend/scripts/run_video_to_analysis_detector_evaluation_report_route_binding.py'
  'backend/scripts/run_video_to_analysis_finish_line_closeout.py'
  'backend/scripts/run_video_to_analysis_finish_line_completion_summary.py'
  'backend/scripts/run_video_to_analysis_finish_line_execution_approval.py'
  'backend/scripts/run_video_to_analysis_finish_line_integration_plan.py'
  'backend/scripts/run_video_to_analysis_finish_line_normal_storage_closeout.py'
  'backend/scripts/run_video_to_analysis_finish_line_normal_storage_execution_approval.py'
  'backend/scripts/run_video_to_analysis_finish_line_operational_readiness.py'
  'backend/scripts/run_video_to_analysis_finish_line_product_acceptance_closeout.py'
  'backend/scripts/run_video_to_analysis_finish_line_product_binding.py'
  'backend/scripts/run_video_to_analysis_finish_line_product_execution_approval.py'
  'backend/scripts/run_video_to_analysis_finish_line_product_execution_plan.py'
  'backend/scripts/run_video_to_analysis_finish_line_route_implementation.py'
  'backend/scripts/run_video_to_analysis_finish_line_route_polish.py'
  'backend/scripts/run_video_to_analysis_finish_line_user_acceptance_trial.py'
  'backend/scripts/run_video_to_analysis_growth_lane_closeout_readout.py'
  'backend/scripts/run_video_to_analysis_growth_lane_decision_snapshot.py'
  'backend/scripts/run_video_to_analysis_manual_operator_release_decision.py'
  'backend/scripts/run_video_to_analysis_next_roadmap_direction_snapshot.py'
  'backend/scripts/run_video_to_analysis_next_sample_selection_snapshot.py'
  'backend/scripts/run_video_to_analysis_next_strategic_lane_selection.py'
  'backend/scripts/run_video_to_analysis_operational_backlog_prioritization.py'
  'backend/scripts/run_video_to_analysis_operational_sprint_closeout.py'
  'backend/scripts/run_video_to_analysis_operator_dashboard_polish.py'
  'backend/scripts/run_video_to_analysis_operator_handoff_pack.py'
  'backend/scripts/run_video_to_analysis_operator_handoff_route_binding.py'
  'backend/scripts/run_video_to_analysis_post_release_monitoring_closeout.py'
  'backend/scripts/run_video_to_analysis_post_release_monitoring_plan.py'
  'backend/scripts/run_video_to_analysis_post_release_monitoring_route_binding.py'
  'backend/scripts/run_video_to_analysis_product_hardening_backlog.py'
  'backend/scripts/run_video_to_analysis_product_lane_closeout.py'
  'backend/scripts/run_video_to_analysis_promoted_runtime_operational_completion_summary.py'
  'backend/scripts/run_video_to_analysis_promoted_runtime_operator_acceptance_trial.py'
  'backend/scripts/run_video_to_analysis_promoted_runtime_post_release_monitoring_execution.py'
  'backend/scripts/run_video_to_analysis_promoted_runtime_post_release_monitoring_plan.py'
  'backend/scripts/run_video_to_analysis_promoted_runtime_post_release_monitoring_route_binding.py'
  'backend/scripts/run_video_to_analysis_promoted_runtime_release_closeout.py'
  'backend/scripts/run_video_to_analysis_promotion_review_closeout.py'
  'backend/scripts/run_video_to_analysis_promotion_review_design.py'
  'backend/scripts/run_video_to_analysis_promotion_review_execution.py'
  'backend/scripts/run_video_to_analysis_promotion_review_report_binding.py'
  'backend/scripts/run_video_to_analysis_promotion_review_report_route_binding.py'
  'backend/scripts/run_video_to_analysis_real_video_scaleout_bounded_execution.py'
  'backend/scripts/run_video_to_analysis_real_video_scaleout_execution_approval.py'
  'backend/scripts/run_video_to_analysis_real_video_scaleout_lane_closeout.py'
  'backend/scripts/run_video_to_analysis_real_video_scaleout_plan.py'
  'backend/scripts/run_video_to_analysis_real_video_scaleout_plan_refresh.py'
  'backend/scripts/run_video_to_analysis_real_video_scaleout_report_route_binding.py'
  'backend/scripts/run_video_to_analysis_real_video_scaleout_source_sampling_expansion.py'
  'backend/scripts/run_video_to_analysis_release_acceptance_archive.py'
  'backend/scripts/run_video_to_analysis_release_candidate_closeout.py'
  'backend/scripts/run_video_to_analysis_release_completion_summary.py'
  'backend/scripts/run_video_to_analysis_release_readout_pack.py'
  'backend/scripts/run_video_to_analysis_release_readout_route_binding.py'
  'backend/scripts/run_video_to_analysis_roadmap_state_reconciliation.py'
  'backend/scripts/run_video_to_analysis_scaleout_or_backlog_decision_snapshot.py'
  'backend/scripts/run_video_to_analysis_source_and_artifact_cleanup_map.py'
  'backend/scripts/run_video_to_analysis_source_pool_replenishment_approval.py'
  'backend/scripts/run_video_to_analysis_source_pool_replenishment_plan.py'
  'backend/scripts/run_video_to_analysis_steady_state_monitoring_cycle.py'
  'backend/scripts/run_video_to_analysis_steady_state_monitoring_recurring_schedule.py'
  'backend/scripts/run_video_to_analysis_storage_cleanup_approval.py'
  'backend/scripts/run_video_to_analysis_storage_cleanup_bounded_execution.py'
  'backend/scripts/run_video_to_analysis_storage_cleanup_closeout.py'
  'backend/scripts/run_video_to_analysis_storage_cleanup_dry_run_execution.py'
  'backend/scripts/run_video_to_analysis_storage_cleanup_execution_approval.py'
  'backend/scripts/run_video_to_analysis_storage_retention_and_artifact_hygiene.py'
  'backend/scripts/run_video_to_analysis_upload_to_analysis_walkthrough.py'
  'backend/scripts/run_video_to_analysis_user_facing_release_readout.py'
  'backend/scripts/run_video_to_analysis_v7_3_release_packaging_and_worktree_triage.py'
  'backend/tests/test_run_video_to_analysis_acceptance_report_product_backlog.py'
  'backend/tests/test_run_video_to_analysis_acceptance_report_route_binding.py'
  'backend/tests/test_run_video_to_analysis_broader_real_video_acceptance_approval.py'
  'backend/tests/test_run_video_to_analysis_broader_real_video_acceptance_closeout.py'
  'backend/tests/test_run_video_to_analysis_broader_real_video_acceptance_execution.py'
  'backend/tests/test_run_video_to_analysis_broader_real_video_acceptance_suite_prep.py'
  'backend/tests/test_run_video_to_analysis_current_release_acceptance_decision_surface.py'
  'backend/tests/test_run_video_to_analysis_finish_line_completion_summary.py'
  'backend/tests/test_run_video_to_analysis_finish_line_execution_approval.py'
  'backend/tests/test_run_video_to_analysis_finish_line_normal_storage_closeout.py'
  'backend/tests/test_run_video_to_analysis_finish_line_normal_storage_execution_approval.py'
  'backend/tests/test_run_video_to_analysis_finish_line_operational_readiness.py'
  'backend/tests/test_run_video_to_analysis_finish_line_product_acceptance_closeout.py'
  'backend/tests/test_run_video_to_analysis_finish_line_product_execution_approval.py'
  'backend/tests/test_run_video_to_analysis_finish_line_route_polish.py'
  'backend/tests/test_run_video_to_analysis_finish_line_user_acceptance_trial.py'
  'backend/tests/test_run_video_to_analysis_growth_lane_closeout_readout.py'
  'backend/tests/test_run_video_to_analysis_manual_operator_release_decision.py'
  'backend/tests/test_run_video_to_analysis_next_strategic_lane_selection.py'
  'backend/tests/test_run_video_to_analysis_operational_backlog_prioritization.py'
  'backend/tests/test_run_video_to_analysis_operator_dashboard_polish.py'
  'backend/tests/test_run_video_to_analysis_operator_handoff_pack.py'
  'backend/tests/test_run_video_to_analysis_operator_handoff_route_binding.py'
  'backend/tests/test_run_video_to_analysis_post_release_monitoring_closeout.py'
  'backend/tests/test_run_video_to_analysis_post_release_monitoring_plan.py'
  'backend/tests/test_run_video_to_analysis_post_release_monitoring_route_binding.py'
  'backend/tests/test_run_video_to_analysis_product_hardening_backlog.py'
  'backend/tests/test_run_video_to_analysis_product_lane_closeout.py'
  'backend/tests/test_run_video_to_analysis_promoted_runtime_operator_acceptance_trial.py'
  'backend/tests/test_run_video_to_analysis_promoted_runtime_post_release_monitoring_chain.py'
  'backend/tests/test_run_video_to_analysis_release_acceptance_archive.py'
  'backend/tests/test_run_video_to_analysis_release_candidate_closeout.py'
  'backend/tests/test_run_video_to_analysis_release_readout_pack.py'
  'backend/tests/test_run_video_to_analysis_release_readout_route_binding.py'
  'backend/tests/test_run_video_to_analysis_roadmap_state_reconciliation.py'
  'backend/tests/test_run_video_to_analysis_source_pool_replenishment_plan.py'
  'backend/tests/test_run_video_to_analysis_steady_state_monitoring_cycle.py'
  'backend/tests/test_run_video_to_analysis_storage_cleanup_approval.py'
  'backend/tests/test_run_video_to_analysis_storage_cleanup_bounded_execution.py'
  'backend/tests/test_run_video_to_analysis_storage_cleanup_closeout.py'
  'backend/tests/test_run_video_to_analysis_storage_cleanup_dry_run_execution.py'
  'backend/tests/test_run_video_to_analysis_storage_cleanup_execution_approval.py'
  'backend/tests/test_run_video_to_analysis_storage_retention_and_artifact_hygiene.py'
  'backend/tests/test_run_video_to_analysis_upload_to_analysis_walkthrough.py'
  'backend/tests/test_run_video_to_analysis_user_facing_release_readout.py'
  'backend/tests/test_run_video_to_analysis_v7_3_release_packaging_and_worktree_triage.py'
)
git add -- "${paths[@]}"
```

- [ ] Run the reusable per-commit gate and the exact staged direct-test subset:

```bash
tests=()
fixture='backend/tests/test_run_video_to_analysis_promoted_runtime_post_release_monitoring_chain.py'
for path in "${paths[@]}"; do
  [[ "$path" == backend/tests/test_*.py && "$path" != "$fixture" ]] && tests+=("$path")
done
test "${#tests[@]}" -eq 45
python3 -m pytest -q "${tests[@]}"
```

Expected: all 45 focused test files pass and collect successfully through the staged promoted-runtime monitoring fixture; the 86 entrypoints are available before the remaining chain coverage is staged. The fixture's own tests run in the final backend baseline.

- [ ] Commit with `git commit -m "feat: preserve video analysis workflows"`.

### Task 11: Preserve chain tests after every imported script

**Commit subject:** `test: preserve workflow chain coverage`

- [ ] Only now, after Tasks 6-10 have committed every imported entrypoint and the shared monitoring fixture, stage the remaining eight multi-script tests:

```bash
paths=(
  'backend/tests/test_run_football_external_benchmark_real_evaluation_chain.py'
  'backend/tests/test_run_video_to_analysis_bounded_next_sample_execution_chain.py'
  'backend/tests/test_run_video_to_analysis_detector_evaluation_reentry_chain.py'
  'backend/tests/test_run_video_to_analysis_finish_line_closeout_chain.py'
  'backend/tests/test_run_video_to_analysis_operational_roadmap_sprint.py'
  'backend/tests/test_run_video_to_analysis_promoted_runtime_release_closeout_chain.py'
  'backend/tests/test_run_video_to_analysis_promotion_review_chain.py'
  'backend/tests/test_run_video_to_analysis_real_video_scaleout_execution_chain.py'
)
git add -- "${paths[@]}"
```

- [ ] Run the reusable per-commit gate, then `python3 -m pytest -q "${paths[@]}"`.

Expected: all eight chain-test files pass; no test collection error reports a missing imported script or test fixture.

- [ ] Commit with `git commit -m "test: preserve workflow chain coverage"`.

### Task 12: Archive and untrack regenerable truth; ignore local editor state

**Commit subject:** `chore: externalize regenerable recovery truth`

- [ ] Define the exact 11 regenerable tracked files and the one local-only editor file:

```bash
paths=(
  'backend/storage/automation/unattended_roadmap_loop_status.json'
  'backend/storage/trained_detector_candidates/touchline_detector_candidate_v7/football_external_benchmark_harness_prep_v1/batch_outcome_analysis.json'
  'backend/storage/trained_detector_candidates/touchline_detector_candidate_v7/football_external_benchmark_harness_prep_v1/batch_outcome_analysis.md'
  'backend/storage/trained_detector_candidates/touchline_detector_candidate_v7/football_external_benchmark_harness_prep_v1/benchmark_harness_readiness_audit.json'
  'backend/storage/trained_detector_candidates/touchline_detector_candidate_v7/football_external_benchmark_harness_prep_v1/benchmark_resource_inventory.json'
  'backend/storage/trained_detector_candidates/touchline_detector_candidate_v7/football_external_benchmark_harness_prep_v1/benchmark_split_plan.json'
  'backend/storage/trained_detector_candidates/touchline_detector_candidate_v7/football_external_benchmark_harness_prep_v1/dataset_adapter_contract.json'
  'backend/storage/trained_detector_candidates/touchline_detector_candidate_v7/football_external_benchmark_harness_prep_v1/decision_matrix.json'
  'backend/storage/trained_detector_candidates/touchline_detector_candidate_v7/football_external_benchmark_harness_prep_v1/external_benchmark_harness_summary.json'
  'backend/storage/trained_detector_candidates/touchline_detector_candidate_v7/football_external_benchmark_harness_prep_v1/failsafe_attempt_plan.json'
  'backend/storage/trained_detector_candidates/touchline_detector_candidate_v7/football_external_benchmark_harness_prep_v1/stage_gate_contract.json'
)
local_only_paths=(
  '.vscode/settings.json'
)
```

- [ ] Before archiving or changing the index, run the exact generators' tests:

```bash
python3 -m pytest -q backend/tests/test_run_football_external_benchmark_harness_prep.py backend/tests/test_unattended_roadmap_loop.py
```

Expected: both test files pass. They exercise regeneration of the benchmark-harness payloads and unattended-loop status using temporary output roots.

- [ ] Checksum and archive the current bytes outside Git before changing the index:

```bash
archive_root='/root/WorkSpace/fotball-analyst-recovery-archive/2026-08-19-current-regenerable-truth'
test ! -e "$archive_root"
mkdir -- "$archive_root"
sha256sum -- "${paths[@]}" > "$archive_root/current-bytes.sha256"
printf '%s\0' "${paths[@]}" | tar --no-recursion --null --files-from=- -czf "$archive_root/current-bytes.tar.gz"
sha256sum -- "$archive_root/current-bytes.tar.gz" > "$archive_root/archive.sha256"
sha256sum --check "$archive_root/current-bytes.sha256"
sha256sum --check "$archive_root/archive.sha256"
```

Expected: both checksum checks print `OK` and all source bytes remain in place.

- [ ] Verify a safe, exact 11-member archive and checksum every restored member from a private extraction root:

```bash
archive_verify=$(mktemp -d)
test -n "$archive_verify"
mkdir -- "$archive_verify/payload"
printf '%s\0' "${paths[@]}" > "$archive_verify/expected-paths.nul"
python3 - "$archive_root/current-bytes.tar.gz" "$archive_verify/expected-paths.nul" "$archive_verify/payload" <<'PY'
from pathlib import Path, PurePosixPath
import sys
import tarfile

archive = Path(sys.argv[1])
expected_file = Path(sys.argv[2])
destination = Path(sys.argv[3])
expected = [item.decode("utf-8") for item in expected_file.read_bytes().split(b"\0") if item]
if len(expected) != 11 or len(set(expected)) != 11:
    raise SystemExit("expected archive path set is not exactly 11 unique paths")
with tarfile.open(archive, "r:gz") as bundle:
    members = bundle.getmembers()
    names = [member.name for member in members]
    if len(names) != 11 or sorted(names) != sorted(expected):
        raise SystemExit("archive does not contain the exact 11-path set")
    for member in members:
        path = PurePosixPath(member.name)
        if path.is_absolute() or ".." in path.parts or not member.isfile():
            raise SystemExit(f"unsafe or non-regular archive member: {member.name}")
    bundle.extractall(destination, members=members, filter="data")
PY
(
  cd "$archive_verify/payload"
  sha256sum --check "$archive_root/current-bytes.sha256"
)
rm -rf -- "$archive_verify"
```

Expected: the member set equals the literal `paths` array, extraction cannot escape the private root, and all 11 extracted member checksums print `OK`.

- [ ] Record this exact fail-closed restore command. Do not run it now because the local bytes are intentionally retained; use it only when all 11 destination files are absent. It validates privately before any repository write and rolls back its own files/directories on installation failure:

```bash
set -euo pipefail
restore_repo='/root/WorkSpace/fotball-analyst'
archive_root='/root/WorkSpace/fotball-analyst-recovery-archive/2026-08-19-current-regenerable-truth'
inventory='/root/WorkSpace/fotball-analyst/docs/recovery/2026-08-19/current-tree-inventory.json'
jq -e '.rows | type == "array"' "$inventory" >/dev/null
mapfile -t paths < <(
  jq -r '.rows[] | select(.classification == "regenerable_truth") | .path' "$inventory"
)
test "${#paths[@]}" -eq 11
test "$(printf '%s\n' "${paths[@]}" | sort -u | wc -l)" -eq 11
sha256sum --check "$archive_root/archive.sha256"
restore_verify=$(mktemp -d)
test -n "$restore_verify"
trap 'rm -rf -- "$restore_verify"' EXIT
mkdir -- "$restore_verify/payload"
printf '%s\0' "${paths[@]}" > "$restore_verify/expected-paths.nul"
python3 - "$archive_root/current-bytes.tar.gz" "$restore_verify/expected-paths.nul" "$restore_verify/payload" "$archive_root/current-bytes.sha256" <<'PY'
from pathlib import Path, PurePosixPath
import re
import sys
import tarfile

archive = Path(sys.argv[1])
expected_file = Path(sys.argv[2])
destination = Path(sys.argv[3])
checksum_file = Path(sys.argv[4])
expected = [item.decode("utf-8") for item in expected_file.read_bytes().split(b"\0") if item]
if len(expected) != 11 or len(set(expected)) != 11:
    raise SystemExit("restore path set is not exactly 11 unique literal paths")
checksum_paths = []
for line in checksum_file.read_text(encoding="utf-8").splitlines():
    match = re.fullmatch(r"[0-9a-fA-F]{64}  (.+)", line)
    if match is None:
        raise SystemExit("invalid restore checksum-manifest line")
    checksum_paths.append(match.group(1))
if len(checksum_paths) != 11 or sorted(checksum_paths) != sorted(expected):
    raise SystemExit("restore checksum path set differs from inventory paths")
with tarfile.open(archive, "r:gz") as bundle:
    members = bundle.getmembers()
    names = [member.name for member in members]
    if len(names) != 11 or sorted(names) != sorted(expected):
        raise SystemExit("restore archive member set differs from literal paths")
    for member in members:
        path = PurePosixPath(member.name)
        if path.is_absolute() or ".." in path.parts or not member.isfile():
            raise SystemExit(f"unsafe or non-regular restore member: {member.name}")
    bundle.extractall(destination, members=members, filter="data")
PY
(
  cd "$restore_verify/payload"
  sha256sum --check "$archive_root/current-bytes.sha256"
)
for path in "${paths[@]}"; do test ! -e "$restore_repo/$path"; done
python3 - "$restore_repo" "$restore_verify/payload" "$restore_verify/expected-paths.nul" <<'PY'
from pathlib import Path, PurePosixPath
import filecmp
import os
import shutil
import stat
import sys

repository = Path(sys.argv[1])
payload = Path(sys.argv[2])
expected_file = Path(sys.argv[3])
expected = [item.decode("utf-8") for item in expected_file.read_bytes().split(b"\0") if item]
if len(expected) != 11 or len(set(expected)) != 11:
    raise SystemExit("install path set is not exactly 11 unique literal paths")
for item in expected:
    path = PurePosixPath(item)
    if path.is_absolute() or ".." in path.parts:
        raise SystemExit(f"unsafe install path: {item}")
    if not (payload / item).is_file():
        raise SystemExit(f"missing verified payload: {item}")
    if os.path.lexists(repository / item):
        raise SystemExit(f"restore destination already exists: {item}")

created_directories: list[Path] = []
installed_files: list[Path] = []

def ensure_parent(relative: PurePosixPath) -> None:
    current = repository
    for part in relative.parent.parts:
        current = current / part
        if os.path.lexists(current):
            mode = os.lstat(current).st_mode
            if stat.S_ISLNK(mode) or not stat.S_ISDIR(mode):
                raise RuntimeError(f"unsafe restore parent: {current}")
        else:
            os.mkdir(current, 0o755)
            created_directories.append(current)

try:
    for item in expected:
        relative = PurePosixPath(item)
        ensure_parent(relative)
        source = payload / item
        destination = repository / item
        flags = os.O_WRONLY | os.O_CREAT | os.O_EXCL
        if hasattr(os, "O_NOFOLLOW"):
            flags |= os.O_NOFOLLOW
        descriptor = os.open(destination, flags, source.stat().st_mode & 0o777)
        installed_files.append(destination)
        with os.fdopen(descriptor, "wb") as target, source.open("rb") as origin:
            shutil.copyfileobj(origin, target)
            target.flush()
            os.fsync(target.fileno())
            os.fchmod(target.fileno(), source.stat().st_mode & 0o777)
    for item in expected:
        if not filecmp.cmp(payload / item, repository / item, shallow=False):
            raise RuntimeError(f"installed payload differs: {item}")
except BaseException:
    for destination in reversed(installed_files):
        try:
            destination.unlink()
        except FileNotFoundError:
            pass
    for directory in reversed(created_directories):
        try:
            directory.rmdir()
        except OSError:
            pass
    raise
PY
(
  cd "$restore_repo"
  sha256sum --check "$archive_root/current-bytes.sha256"
)
trap - EXIT
rm -rf -- "$restore_verify"
```

Expected when restoration is needed: the archive digest, exact safe 11-member set, and private extracted payload all verify before repository mutation; installation uses `O_EXCL`/`O_NOFOLLOW`, writes only the literal 11 absent paths, rolls back its own partial writes on failure, and every installed checksum prints `OK`. Tar is never extracted directly into the repository.

- [ ] Add literal ignore rules with this exact patch; broad `backend/storage/` ignore remains, but the explicit rules document the 11 intentional local artifacts:

```diff
*** Begin Patch
*** Update File: .gitignore
@@
 aws/
 awscliv2.zip
+
+# Recovery-preserved local-only material (2026-08-19)
+.vscode/
+/backend/storage/automation/unattended_roadmap_loop_status.json
+/backend/storage/trained_detector_candidates/touchline_detector_candidate_v7/football_external_benchmark_harness_prep_v1/batch_outcome_analysis.json
+/backend/storage/trained_detector_candidates/touchline_detector_candidate_v7/football_external_benchmark_harness_prep_v1/batch_outcome_analysis.md
+/backend/storage/trained_detector_candidates/touchline_detector_candidate_v7/football_external_benchmark_harness_prep_v1/benchmark_harness_readiness_audit.json
+/backend/storage/trained_detector_candidates/touchline_detector_candidate_v7/football_external_benchmark_harness_prep_v1/benchmark_resource_inventory.json
+/backend/storage/trained_detector_candidates/touchline_detector_candidate_v7/football_external_benchmark_harness_prep_v1/benchmark_split_plan.json
+/backend/storage/trained_detector_candidates/touchline_detector_candidate_v7/football_external_benchmark_harness_prep_v1/dataset_adapter_contract.json
+/backend/storage/trained_detector_candidates/touchline_detector_candidate_v7/football_external_benchmark_harness_prep_v1/decision_matrix.json
+/backend/storage/trained_detector_candidates/touchline_detector_candidate_v7/football_external_benchmark_harness_prep_v1/external_benchmark_harness_summary.json
+/backend/storage/trained_detector_candidates/touchline_detector_candidate_v7/football_external_benchmark_harness_prep_v1/failsafe_attempt_plan.json
+/backend/storage/trained_detector_candidates/touchline_detector_candidate_v7/football_external_benchmark_harness_prep_v1/stage_gate_contract.json
*** End Patch
```

- [ ] Remove only the 11 files from the index, retain their local bytes, and stage only the policy change:

```bash
git rm --cached -- "${paths[@]}"
git add -- .gitignore
for path in "${paths[@]}" "${local_only_paths[@]}"; do test -f "$path"; git check-ignore -q -- "$path"; done
sha256sum --check "$archive_root/current-bytes.sha256"
```

- [ ] Focused staged-set verification:

```bash
expected=$(mktemp)
actual=$(mktemp)
printf '%s\n' .gitignore "${paths[@]}" | sort -u > "$expected"
git diff --cached --name-only | sort -u > "$actual"
diff -u "$expected" "$actual"
git diff --cached --check
rm -f -- "$expected" "$actual"
```

Expected: the staged set is exactly `.gitignore` plus the 11 index deletions; all 12 original local files still exist and are ignored; the 11 archived-file checksums still pass.

- [ ] Commit with `git commit -m "chore: externalize regenerable recovery truth"`, then repeat the existence, ignore, and checksum checks. Do not stage `.vscode/settings.json`.

### Task 13: Preserve release state and workflow chronology last

**Commit subject:** `docs: preserve v7.3 release chronology`

- [ ] Stage the four active release-state documents, seven manual-review documents, and 67 workflow plans only after all source and tests are committed:

```bash
paths=(
  'SESSION-HANDOFF.md'
  'docs/foot-soccer-deepresearch.md'
  'docs/goal-1-12april-00-1am.md'
  'docs/project-review-2026-07-06.md'
  'docs/superpowers/plans/2026-05-04-canonical-match-bundle-export.md'
  'docs/superpowers/plans/2026-05-04-football-external-soccernet-api-listing-probe.md'
  'docs/superpowers/plans/2026-05-04-football-external-soccernet-benchmark-adapter-contract-prep.md'
  'docs/superpowers/plans/2026-05-04-football-external-soccernet-bounded-analysis-execution-approval.md'
  'docs/superpowers/plans/2026-05-04-football-external-soccernet-bounded-analysis-execution.md'
  'docs/superpowers/plans/2026-05-04-football-external-soccernet-bounded-analysis-lane-closeout.md'
  'docs/superpowers/plans/2026-05-04-football-external-soccernet-bounded-analysis-report-smoke.md'
  'docs/superpowers/plans/2026-05-04-football-external-soccernet-controlled-label-metadata-probe.md'
  'docs/superpowers/plans/2026-05-04-football-external-soccernet-controlled-video-sample-fetch.md'
  'docs/superpowers/plans/2026-05-04-football-external-soccernet-event-adapter-smoke-test.md'
  'docs/superpowers/plans/2026-05-04-football-external-soccernet-event-benchmark-smoke.md'
  'docs/superpowers/plans/2026-05-04-football-external-soccernet-event-lane-closeout.md'
  'docs/superpowers/plans/2026-05-04-football-external-soccernet-event-report-product-integration.md'
  'docs/superpowers/plans/2026-05-04-football-external-soccernet-event-report-smoke.md'
  'docs/superpowers/plans/2026-05-04-football-external-soccernet-full-analysis-execution-approval.md'
  'docs/superpowers/plans/2026-05-04-football-external-soccernet-full-analysis-execution.md'
  'docs/superpowers/plans/2026-05-04-football-external-soccernet-full-analysis-lane-closeout.md'
  'docs/superpowers/plans/2026-05-04-football-external-soccernet-full-analysis-report-smoke.md'
  'docs/superpowers/plans/2026-05-04-football-external-soccernet-label-fetch-contract-repair.md'
  'docs/superpowers/plans/2026-05-04-football-external-soccernet-label-member-range-pipeline.md'
  'docs/superpowers/plans/2026-05-04-football-external-soccernet-split-archive-access-review.md'
  'docs/superpowers/plans/2026-05-04-football-external-soccernet-video-analysis-dry-run-approval.md'
  'docs/superpowers/plans/2026-05-04-football-external-soccernet-video-analysis-dry-run-product-bridge-smoke.md'
  'docs/superpowers/plans/2026-05-04-football-external-soccernet-video-analysis-dry-run.md'
  'docs/superpowers/plans/2026-05-04-football-external-soccernet-video-frame-probe.md'
  'docs/superpowers/plans/2026-05-04-football-external-soccernet-video-member-extract-approval.md'
  'docs/superpowers/plans/2026-05-04-football-external-soccernet-video-member-extract.md'
  'docs/superpowers/plans/2026-05-04-football-external-soccernet-video-product-path-smoke.md'
  'docs/superpowers/plans/2026-05-04-football-external-soccernet-video-sample-download-approval.md'
  'docs/superpowers/plans/2026-05-04-football-external-soccernet-video-sample-probe.md'
  'docs/superpowers/plans/2026-05-04-football-external-soccernet-video-to-analysis-bridge-prep.md'
  'docs/superpowers/plans/2026-05-04-product-video-to-analysis-smoke.md'
  'docs/superpowers/plans/2026-05-04-v7-2-runtime-registry-product-path-binding.md'
  'docs/superpowers/plans/2026-05-05-football-external-benchmark-bounded-execution-smoke.md'
  'docs/superpowers/plans/2026-05-05-football-external-benchmark-execution-approval.md'
  'docs/superpowers/plans/2026-05-05-football-external-benchmark-harness-prep.md'
  'docs/superpowers/plans/2026-05-05-football-external-benchmark-harness-smoke.md'
  'docs/superpowers/plans/2026-05-05-football-external-benchmark-lane-closeout.md'
  'docs/superpowers/plans/2026-05-05-football-external-benchmark-operationalization-plan.md'
  'docs/superpowers/plans/2026-05-05-football-external-benchmark-product-decision-route-implementation.md'
  'docs/superpowers/plans/2026-05-05-football-external-benchmark-product-decision-surface.md'
  'docs/superpowers/plans/2026-05-05-football-external-benchmark-product-ui-binding.md'
  'docs/superpowers/plans/2026-05-05-football-external-benchmark-product-ui-route-implementation.md'
  'docs/superpowers/plans/2026-05-05-football-external-benchmark-real-evaluation-chain.md'
  'docs/superpowers/plans/2026-05-05-football-external-benchmark-real-evaluation-design.md'
  'docs/superpowers/plans/2026-05-05-football-external-benchmark-report-smoke.md'
  'docs/superpowers/plans/2026-05-05-football-external-soccernet-analysis-product-lane-closeout.md'
  'docs/superpowers/plans/2026-05-05-football-external-soccernet-analysis-product-ui-route-implementation.md'
  'docs/superpowers/plans/2026-05-05-football-external-soccernet-full-analysis-product-integration.md'
  'docs/superpowers/plans/2026-05-05-football-external-soccertrack-authenticated-fixture-access-approval.md'
  'docs/superpowers/plans/2026-05-05-football-external-soccertrack-controlled-sample-fetch.md'
  'docs/superpowers/plans/2026-05-05-football-external-soccertrack-fixture-source-access-review.md'
  'docs/superpowers/plans/2026-05-05-football-external-soccertrack-sample-fixture-materialization-approval.md'
  'docs/superpowers/plans/2026-05-05-football-external-soccertrack-sample-ingestion-contract-prep.md'
  'docs/superpowers/plans/2026-05-05-football-external-soccertrack-sample-schema-probe.md'
  'docs/superpowers/plans/2026-05-05-football-external-soccertrack-schema-doc-fetch-approval.md'
  'docs/superpowers/plans/2026-05-05-football-external-soccertrack-schema-doc-fetch.md'
  'docs/superpowers/plans/2026-05-05-football-external-soccertrack-schema-doc-parse.md'
  'docs/superpowers/plans/2026-05-05-housekeeping-direction-snapshot.md'
  'docs/superpowers/plans/2026-05-09-video-to-analysis-growth-lane-finish-roadmap.md'
  'docs/superpowers/plans/2026-05-09-video-to-analysis-strategic-lane-priority-plan.md'
  'docs/superpowers/plans/2026-05-10-soccernet-real-sample-training-decision-cascade.md'
  'docs/superpowers/plans/2026-05-11-codex-goal-autonomous-video-to-analysis-growth-marathon.md'
  'docs/superpowers/plans/2026-05-11-codex-goal-video-to-analysis-bounded-chain-continuation.md'
  'docs/superpowers/plans/2026-05-11-codex-goal-video-to-analysis-finishline-push.md'
  'docs/superpowers/plans/2026-05-11-codex-goal-video-to-analysis-scaleout-followup-marathon.md'
  'docs/superpowers/plans/2026-05-11-codex-goal-video-to-analysis-total-finishline.md'
  'docs/video-to-analysis-finish-line-roadmap-completion-report-2026-05-08.md'
  'docs/video-to-analysis-finish-line-roadmap-guide.md'
  'docs/video-to-analysis-growth-lane-closeout-readout-2026-05-09.md'
  'docs/video-to-analysis-user-facing-release-readout-2026-05-09.md'
  'memorybank/activeContext.md'
  'memorybank/currentRoadmap.md'
  'memorybank/progress.md'
)
git add -- "${paths[@]}"
```

- [ ] Run the reusable per-commit gate. Focused verification is `git diff --cached --check` and `test "$(printf '%s\n' "${paths[@]}" | sort -u | wc -l)" -eq 78`.

Expected: the staged documentation has no whitespace errors, has exactly 78 unique paths, and no code or artifact path is staged.

- [ ] Commit with `git commit -m "docs: preserve v7.3 release chronology"`.

## Final mechanical reconciliation and clean-worktree gate

- [ ] Prove the frozen inventory still declares exactly 487 unique paths with the requested source categories:

```bash
inventory='docs/recovery/2026-08-19/current-tree-inventory.json'
preservation_start=$(cat /root/WorkSpace/fotball-analyst-recovery-archive/2026-08-19-preservation-start.commit)
test "$(jq '.totalPathCount' "$inventory")" -eq 487
test "$(jq '[.rows[].path] | unique | length' "$inventory")" -eq 487
test "$(jq '[.rows[] | select(.classification == "tracked_deletion")] | length' "$inventory")" -eq 14
test "$(jq '[.rows[] | select(.classification == "regenerable_truth")] | length' "$inventory")" -eq 11
test "$(jq '[.rows[] | select(.path == ".vscode/settings.json")] | length' "$inventory")" -eq 1
test "$(jq '[.rows[] | select(.classification != "tracked_deletion" and .classification != "regenerable_truth" and .path != ".vscode/settings.json")] | length' "$inventory")" -eq 461
test "$(jq '[.rows[] | select(.classification == "one_shot_batch_entrypoint")] | length' "$inventory")" -eq 199
```

Expected: every assertion exits 0.

- [ ] Prove the 487 rows have exactly one final disposition and no duplicate membership. The commit range covers the 461 current-byte paths; the three non-commit arrays are derived from the immutable inventory and checked disjointly:

```bash
committed=$(mktemp)
restored=$(mktemp)
external=$(mktemp)
local_only=$(mktemp)
all=$(mktemp)
git diff --name-only --diff-filter=AM "$preservation_start..HEAD" -- . ':(exclude).gitignore' > "$committed"
jq -r '.rows[] | select(.classification == "tracked_deletion") | .path' "$inventory" > "$restored"
jq -r '.rows[] | select(.classification == "regenerable_truth") | .path' "$inventory" > "$external"
printf '%s\n' '.vscode/settings.json' > "$local_only"
cat "$committed" "$restored" "$external" "$local_only" | sort > "$all"
test "$(wc -l < "$committed")" -eq 461
test "$(wc -l < "$restored")" -eq 14
test "$(wc -l < "$external")" -eq 11
test "$(wc -l < "$local_only")" -eq 1
test "$(wc -l < "$all")" -eq 487
test "$(sort -u "$all" | wc -l)" -eq 487
diff -u <(jq -r '.rows[].path' "$inventory" | sort) "$all"
rm -f -- "$committed" "$restored" "$external" "$local_only" "$all"
```

Expected: counts are exactly `461 + 14 + 11 + 1 = 487`, the unique count is 487, and `diff` prints nothing. `.gitignore` is intentionally excluded because it is policy authored during preservation, not one of the frozen 487.

- [ ] Verify repository and retained-local state:

```bash
test -z "$(git diff --cached --name-only)"
status_check_root=$(mktemp -d)
git status --porcelain=v1 --untracked-files=all > "$status_check_root/visible-status"
test ! -s "$status_check_root/visible-status"
rm -rf -- "$status_check_root"
sha256sum --check /root/WorkSpace/fotball-analyst-recovery-archive/2026-08-19-current-regenerable-truth/current-bytes.sha256
test -f .vscode/settings.json
git check-ignore -q .vscode/settings.json
```

Expected: the branch has no staged, modified, deleted, or visible untracked files; all 11 externalized local files still match the archive manifest; `.vscode/settings.json` remains present and ignored. If this preservation-plan file was not reviewed and committed before the recorded start point, the execution was invalid: stop and restart from a corrected start point rather than folding the plan into the 12 preservation commits.

- [ ] Repeat the secure archive-payload check independently of the retained local files:

```bash
archive_root='/root/WorkSpace/fotball-analyst-recovery-archive/2026-08-19-current-regenerable-truth'
final_archive_verify=$(mktemp -d)
test -n "$final_archive_verify"
mkdir -- "$final_archive_verify/payload"
sha256sum --check "$archive_root/archive.sha256"
python3 - "$archive_root/current-bytes.tar.gz" "$inventory" "$final_archive_verify/payload" <<'PY'
from pathlib import Path, PurePosixPath
import json
import sys
import tarfile

archive = Path(sys.argv[1])
inventory = json.loads(Path(sys.argv[2]).read_text(encoding="utf-8"))
destination = Path(sys.argv[3])
expected = sorted(
    row["path"] for row in inventory["rows"] if row["classification"] == "regenerable_truth"
)
if len(expected) != 11 or len(set(expected)) != 11:
    raise SystemExit("inventory does not define exactly 11 regenerable paths")
with tarfile.open(archive, "r:gz") as bundle:
    members = bundle.getmembers()
    names = [member.name for member in members]
    if len(names) != 11 or sorted(names) != expected:
        raise SystemExit("final archive member set differs from inventory")
    for member in members:
        path = PurePosixPath(member.name)
        if path.is_absolute() or ".." in path.parts or not member.isfile():
            raise SystemExit(f"unsafe or non-regular archive member: {member.name}")
    bundle.extractall(destination, members=members, filter="data")
PY
(
  cd "$final_archive_verify/payload"
  sha256sum --check "$archive_root/current-bytes.sha256"
)
rm -rf -- "$final_archive_verify"
```

Expected: the archive digest is valid, its exact 11-member set equals the inventory's regenerable paths, extraction stays inside a private directory, and all extracted payload checksums print `OK`.

- [ ] Run the preserved baseline before worktree creation:

```bash
python3 -m pytest -q backend/tests
sidecar_log_root=$(mktemp -d)
set +e
python3 -m pytest -q research-addon/tests | tee "$sidecar_log_root/normal-root.log"
sidecar_status=${PIPESTATUS[0]}
set -e
test "$sidecar_status" -eq 1
grep -Eq '2 failed, 35 passed' "$sidecar_log_root/normal-root.log"
rm -rf -- "$sidecar_log_root"
PYTHONPATH=research-addon python3 -m pytest -q research-addon/tests
npm --prefix frontend test -- --run
npm --prefix frontend run lint
npm --prefix frontend run typecheck
npm --prefix frontend run build
```

Expected: at least 1,486 backend tests pass; the normal-root sidecar run reproduces the audited 35-pass/2-fail packaging defect, then all 37 pass with the explicit audited `PYTHONPATH`; 46 frontend tests pass; lint, typecheck, and build exit 0. Record the sidecar packaging defect for the next stabilization plan; do not repair it by mutating frozen paths here.

- [ ] Only after the branch-clean check, archive checksum check, partition proof, and preservation review pass, create the clean branch worktree. Do not prune any existing worktree:

```bash
test -z "$(git status --porcelain=v1 --untracked-files=all)"
git check-ignore -q .worktrees/.ignore-probe
test ! -e .worktrees/preservation-stabilization
git show-ref --verify --quiet refs/heads/preservation-stabilization && exit 1 || true
git worktree add .worktrees/preservation-stabilization -b preservation-stabilization HEAD
git -C .worktrees/preservation-stabilization status --short --branch
```

Expected: a new clean `.worktrees/preservation-stabilization` exists on branch `preservation-stabilization`; its status shows only the branch header. No existing worktree or branch is removed, pruned, reset, or declared superseded.
