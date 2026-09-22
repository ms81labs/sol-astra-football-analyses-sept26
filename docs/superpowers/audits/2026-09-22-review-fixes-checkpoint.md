# Review-fix checkpoint — 22 September 2026

This is the current bounded follow-up to the review at `ae8ffee`, not an instruction to restart C01–C06 or the historical code-quality audit. Read actual remote source and run state before resuming. Earlier main-only instructions and old checkpoint heads are historical for this follow-up.

## Source and authority

- Authorized target: `agent/backend-bounded-completion-2026-09-22` only.
- Starting reviewed commit: `ae8ffeec3a2a2eb4736b1751600396c2f6c30a28`.
- CI-home commit: `7daf87e51e516ad03f66d495f6b125e154dd0d94`.
- Fixed code commit: `54f906f2ac1e49613952d311ab12b30d54582b30`.
- Fixed code tree: `8d07bc884d6f3fcdc8425c36ef26f9514ff645ef`.
- Main last observed: `c685640a897c16669e3b1848d77bf9e6e5d7e8cf`; no merge, force-push, branch deletion, live-store mutation or paid/model execution performed.
- This checkpoint commit is documentation-only and skips redundant CI. It is not a claim that tests ran on the documentation SHA.

## Implemented and focused-verified

1. Direct pytest receipt leaf now uses existing no-follow/confinement/atomic helpers. Existing and dangling symlinks cannot overwrite/create their targets.
2. Final code-only evidence binds the unique backend gate invocation, actual source before/after testing, profile, arguments, selected nodes, exit and raw log hashes. UUID ordering no longer selects authority. Backend stubs and dirty-source identity survive the final summary.
3. Existing pinned C05 CPU workflow explicitly executes final journey tests and has FFmpeg, working-branch coverage, scorer pin checks and always-retained invocation records.
4. Both composed modes use the real provider gateway with a fake post-dispatch timeout and actual shared ledger reconciliation/idempotency. Recovery twice and final reopen execute in fresh guarded child processes, not only a new object in the parent.

No new runtime dependency/framework or application architecture change was introduced. Full-mode shell behavior and command/tee failure safeguards remain covered. Review was self-review, not an invented independent agent review.

## Verified execution, kept separate

- Receipt RED: 21 intended counterexamples before the fixes. Gateway/parent-recovery and CRLF regressions also retained.
- Focused selection: 89 passed on available Python 3.13.5; exact tested file blobs subsequently matched the fixed code tree. Not relabelled as locked Python 3.11.
- Neighboring selection on fixed code: 123 passed.
- Canonical C05 run `35783957026`: success at fixed code; 46 scorer tests and 3 final-journey tests passed separately, no skips. Python 3.11.16 and repository dev lock; ultralytics stub disclosed. Artifact `10719447031`, SHA256 `eed546991aab2b8147c0247983b4f43cd9700670bf1fc383c1a4533c77ca7513` verified.
- Canonical CI `35783956961`: quality, API, excluded-backend, integration, real-media and macOS dependency dry-run completed successfully. At this checkpoint the canonical verify job `106936066539` is still running; do not mark it passed.
- Canonical excluded complement: 594 passed. Integration: 357 passed, 15 skipped. Real-media: 23 passed, 4 skipped. Scorer/journey skips in ordinary lanes are executed in the separate pinned job; counts overlap and are not summed.
- Local C06 ordinary: 69 passed, 1 opt-in skip, 3 failures. All three failures reproduced on unchanged `c685640` in this available Python 3.13.5 container: 150ms decoder-start timing, 160MiB address-space hash child, and cancellation before the second export process. Tests were not weakened. This local run remains qualified, not green.
- Local opt-in long decode: 1 passed, 1,500 generated frames and more than 8GiB decoded with bounded buffering. Synthetic, not full-match performance evidence.
- True legacy fixture/migration selection: 13 passed, 23 deselected on fixed code in the local available profile.
- Copied-store compatibility: actual c685640 video/tracking stores were copied, opened/edited/reopened by fixed code; original source hashes and SQLite integrity preserved. Untouched backup copies reopened with matching old source. Not an in-place downgrade.

## Historical evidence recovered

The original audit archive was recovered from the user's Library. Its SHA256 is `7f86b4dcb53ca0522da490ca79c4bd3a1d6657b803581c4b2d6650fcba940424`, matching the original kit. All 51 archived content checksums and 12 kit-file checks verified. The unchanged original four probes ran on exact c685640 and produced four intended assertion failures, not import/collection failures. That replay used available Python 3.13.5; it is not a canonical locked baseline run.

## Durable evidence and exact next action

Current session evidence: `/mnt/data/fix-evidence`; original kit/archive: `/mnt/data/recovered-history`. Do not assume these local paths exist in another environment. Canonical repository/scorer bundles and run receipts are retained in the C05 artifact above. Final downloadable handoff must retain local logs, checksums, compatibility driver, qualifications and the execution index.

Next: inspect CI `35783956961` job `106936066539` at exact fixed source, download its final artifact, validate receipt/run/log bindings and inspect actual failure or completion. Then finish the qualified evidence handoff. Do not rerun already-proven fixes, create another branch, or merge to main automatically. Main-push rollout, real browser, macOS runtime, GPU, real billing, model accuracy and deployment remain separate unexecuted qualifications.
