# Raw recovery freeze manifest

Created at `2026-08-19T15:20:37Z` on branch `recovery-history-batch-current`. The audited base is `bc4f4e30f765b203eed4292f9e8127468f05fee9`; the pre-task head is `94a48a14915a37f451e463ae797813351654e468`, whose parent is the audited base.

The canonical original status contains exactly 487 paths: 30 modified, 14 deleted, and 443 untracked. Its NUL-delimited path list is `archive/2026-08-19-recovery-freeze/original-paths.nul` with SHA-256 `c0b698f2f3acc8680d9b70c936a3afed3b3c9aaacf6f40eb97f7f769a84029b9`. A fresh file-expanded porcelain status, after removing the three untracked plan paths below, has the same exact path set and counts.

The archived `original-status.nul` was captured with Git's collapsed untracked-directory display. It names `.vscode/` and `backend/review_ui/football_external_soccernet_detector_miss_review/`; the canonical expanded list and tar instead name the sole file in each directory, `.vscode/settings.json` and `backend/review_ui/football_external_soccernet_detector_miss_review/index.html`. Those two substitutions fully explain the representational difference.

## Agent-authored paths outside the original 487

All four agent-authored paths are outside the original 487. The approved design was already committed before the raw freeze; the three plans were untracked and therefore are the only paths subtracted from the live pre-freeze status comparison.

- Approved design, committed at `94a48a14915a37f451e463ae797813351654e468`: `docs/superpowers/specs/2026-08-19-preservation-first-stabilization-design.md` — 14,825 bytes, SHA-256 `58c49fc358c77c28b10f172b849fb8a0ddad17b52c38cc55622072cd16e76815`
- Untracked plan: `docs/superpowers/plans/2026-08-19-project-operability-verification.md` — `8015b30da62d2640d37635ec80dab6221cca4bd2901829f075befa94010b95bf`
- Untracked plan: `docs/superpowers/plans/2026-08-19-recovery-preservation.md` — `45e39fe03cd61ca7c8503904fff872a7800869d124b90a3d9b020c9af4658873`
- Untracked plan: `docs/superpowers/plans/2026-08-19-release-runtime-reproducibility.md` — `da1b577a9f9a29a2adfec4ba933d047ea01eb5fde7357131342307c02691acc2`

## Freeze archive

The ignored archive has 13 files totaling 2,891,543 bytes. `SHA256SUMS` has 12 verified entries; the checksum file itself is 1,109 bytes with SHA-256 `8ad7c9b7f1ed0ffee3ad685049f69d7dadb83374648dbcc8624f17b3fad676b1`.

- `original-tracked.patch`: 1,916,655 bytes, SHA-256 `44c8985feaeb67bd42e20d470cf21da30d6579df7952932e8963df3e5e653b2d`, exactly 44 paths. Its path set equals the original tracked dirty set relative to the audited base and excludes the committed approved spec.
- `original-untracked.tar.gz`: 569,626 bytes, SHA-256 `39101ac534d59c5a8abc333f186d67224e83b70fb93ddb690ce2f58982476506`, exactly 443 non-directory members. The normalized member path set equals the canonical untracked path set. There are no absolute or parent-traversal names, no directory display members, and no symlink dereference mismatches.
- `ignored-path-inventory.nul.gz`: 51,134 path-only entries, 265,065 bytes, SHA-256 `68a9d4c69c4c7d997295410aba3448317466016aa232a2b48a1430198a47f36a`. It exactly matches the ordered live ignored-path listing after excluding top-level `.git`, `.worktrees`, and `archive`. No file bodies, environment-file contents, or credential contents were copied.
- `tracked-but-ignored-path-inventory.nul.gz`: 3,850 path-only entries, 17,823 bytes, SHA-256 `e45b46ae09f98e5be4fdf798f42443be88a77ed4825cbd23f77e2a0849428dfb`.

## Required retained artifacts

- `yolov10n-base-model`: `yolov10n.pt`, 5,860,383 bytes, SHA-256 `11287ed0735678e7ba1ac2a9b3098c049155b3fde123992e724c1264bcc16b6f`. Origin: the pre-existing local base model referenced by the v7.3 training configuration. Retention: required local ignored model; retain in place and do not archive or commit.
- `touchline-detector-v7.3-bounded-retrain-best`: `backend/storage/trained_detector_candidates/touchline_detector_candidate_v7/v7_3_bounded_retrain_v1/train_run/weights/best.pt`, 5,711,162 bytes, SHA-256 `e7724403223429691e051ef946af1808413808349d6730bdca935da743d79cc0`. Origin: the completed RTX 3090 bounded retrain recorded in `training_run_summary.json`, using source export batch `v7_3_export_label_overlay_audit_v1` and the local YOLOv10n base model. Retention: required local ignored checkpoint; retain in place and do not archive or commit.

## Branch and worktree snapshot

`local-branch-heads.txt` (`4d907639beec8ca206b977c3dd68202ef67d773fb88ca1af05c25581d498dfb2`) and `worktree-list.txt` (`ba28cbd0b2a488f2314e6eab751a34bd7e892e4cb5bdc53839ebcef28b767412`) matched live state before this manifest commit. Local heads were:

- `feat/observed-anchor-corridor-recovery`, `hybrid-staged-recovery`, `master`, `recovery-history-batch`, and `reusable-pod-lane`: `6991eddf6fd81f5960fed1638d77158123c6618a`
- `feature/pdf-report-export`: `5db94e50ffa1945e46f88ed4c8acd1ae1963ee97`
- `proposal-support-bridge`: `3897c7c75dd0d758372a08697923f95337d5fc34`
- `recovery-history-batch-current`: `94a48a14915a37f451e463ae797813351654e468`

Read-only, file-expanded status summaries were:

- main worktree: 490 total = 30 modified + 14 deleted + 446 untracked, including the original 487 and three plan paths
- `hybrid-staged-recovery`: 33,047 total = 7 modified + 32,974 deleted + 66 untracked
- `proposal-support-bridge`: 33 total = 20 modified + 13 untracked
- `recovery-history-batch`: 32,974 deleted
- `reusable-pod-lane`: 33,020 total = 6 modified + 32,974 deleted + 40 untracked

## Verification and safeguards

Verification used NUL-delimited Git lists and set equality, `git apply --numstat -z` for patch paths, Python tar metadata inspection for normalized safe member names and entry types, fresh SHA-256 calculations for every checksum entry and both model files, and read-only live comparisons for branch/worktree snapshots. All checks passed.

No original recovery path was edited, staged, moved, or deleted. No paused worktree was modified. No deployment was attempted. The only ignored-archive mutation was regeneration of the path-only ignored inventory and its checksum entry.

The JSON manifest beside this file is the authoritative machine-readable record.
