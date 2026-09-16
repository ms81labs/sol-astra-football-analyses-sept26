# Project Cleanup Report — 2026-04-21

## Summary

This cleanup pass realigned the repo around `origin/main`, kept the active football product path intact, isolated the research lane, archived confirmed-unused fork residue, and removed tracked runtime junk from source control.

## Mainline Scope Preserved

- `backend/app`, `backend/scripts`, `backend/tests`
- `backend/runpod_handler`
- `backend/benchmark_suites`
- `frontend/src`
- live operating docs under `docs/`
- `research-addon/` and tracked `.factory/` as an isolated research lane
- `lap.py` because `backend/runpod_handler/Dockerfile` still references it

## Archived During This Cleanup

- `archive/2026-04-21-mainline-reset/code/frontend/src/App.css`
  Reason: `knip` reported the file unused and no live import remained after verification
- `archive/2026-04-21-mainline-reset/code/frontend/src/components/Timeline.legacy.tsx`
  Reason: no live imports or references in the frontend product path
- `archive/2026-04-21-mainline-reset/code/frontend/src/features/playback/usePlaybackController.ts`
  Reason: `knip` reported the file unused and `rg` found no live references
- `archive/2026-04-21-mainline-reset/code/frontend/src/features/review/eventPivots.ts`
  Reason: `knip` reported the file unused and `rg` found no live references
- `archive/2026-04-21-mainline-reset/code/frontend/src/features/review/shotPivots.ts`
  Reason: `knip` reported the file unused and `rg` found no live references
- `archive/2026-04-21-mainline-reset/code/frontend/src/features/workspace/model.ts`
  Reason: `knip` reported the file unused and `rg` found no live references
- `archive/2026-04-21-mainline-reset/code/frontend/src/utils/dataLoader.ts`
  Reason: `knip` reported the file unused and `rg` found no live references
- `archive/2026-04-21-mainline-reset/code/frontend/src/utils/llm.ts`
  Reason: `knip` reported the file unused and `rg` found no live references
- `archive/2026-04-21-mainline-reset/docs/superpowers/plans/2026-04-16-primary-pitch-gate-geometry-consistency-batch-analysis.md`
  Reason: worktree-bound historical plan tied to the retired fork lane
- `archive/2026-04-21-mainline-reset/notes/root/Guerilla Analytics V1 - PRD.txt`
  Reason: root-level product note preserved outside the active product path
- `archive/2026-04-21-mainline-reset/notes/root/improvements-1.md`
  Reason: root-level cleanup note preserved outside the active product path
- `archive/2026-04-21-mainline-reset/notes/root/improvements-2.txt`
  Reason: root-level cleanup note preserved outside the active product path
- `archive/2026-04-21-mainline-reset/notes/root/README.md`
  Reason: stray local mission note outside the product path

## Removed From Source Control

- tracked `backend/venv/`
- tracked backend cache directories under `backend/**/__pycache__/`
- tracked `backend/storage/` runtime artifacts

These paths remain local-only and ignored.

## Local-Only Runtime Hygiene

- `.gitignore` now keeps `backend/storage/`, `backend/venv/`, `.worktrees/`, `videos/`, caches, and model weights out of source control
- the ignored runtime manifest at `backend/storage/housekeeping/2026-04-17-safe-pass/manifest.json` was normalized so the live repo no longer treats the retired worktree path as active state

## Live Doc Realignment

- `README.md` now describes one active mainline plus a separate research lane
- `SESSION-HANDOFF.md` now points to the mainline reset instead of the retired fork
- live roadmap and current-state docs no longer present the retired fork worktree as active truth
- benchmark defaults now resolve clip and storage paths from the repo root instead of a live `.worktrees/` path

## Dead-Code And Lint Findings

- frontend dead-file cleanup was driven by `knip`, then confirmed with `rg`
- unused frontend exports were reduced in place instead of deleting live API surface
- `backend/pitch_detector.py` was cleaned so repo-wide `ruff` now passes without changing detector behavior
- the current hygiene policy expects `ruff` to stay clean on `backend`, `research-addon`, and `lap.py`
- `vulture` is treated as actionable only at `--min-confidence 80`
- lower-confidence `vulture` hits are still expected around FastAPI routes, Pydantic schema fields, and dynamically reached proof/runtime helpers
- because those lower-confidence hits are high-risk false-positive territory, they remain advisory and are not deleted in this pass

## Verification

- `git ls-files | rg '^backend/venv/'`
  Result: no output
- grep for the retired fork worktree path across `README.md`, `SESSION-HANDOFF.md`, `docs/`, `frontend/`, `backend/`, and `archive/`
  Result: matches remain only inside `archive/2026-04-21-mainline-reset/...`
- `/tmp/fotball-cleanup-tools/bin/ruff check backend research-addon`
  Result: `All checks passed!`
- `/tmp/fotball-cleanup-tools/bin/vulture backend/app backend/scripts research-addon/research_addon --sort-by-size --min-confidence 80`
  Result: clean exit expected after removing any 80%+ confidence dead-code hits
- `npx --yes knip@latest --directory frontend --include files,exports`
  Result: clean exit with no unused files or exports reported
- `python3 -m pytest backend/tests -q`
  Result: `402 passed in 9.54s`
- `npm --prefix frontend test`
  Result: `15` test files passed, `46` tests passed
- `npm --prefix frontend run build`
  Result: production build succeeded and emitted `dist/index.html`, `dist/assets/index-rsVtXKLv.css`, and `dist/assets/index-D2_L0TtF.js`
- `/tmp/fotball-cleanup-tools/bin/vulture backend/app backend/scripts research-addon/research_addon --sort-by-size`
  Result: lower-confidence output remains advisory and still includes dynamic-entrypoint false positives such as FastAPI routes in `backend/app/main.py`, Pydantic schema fields in `backend/app/schemas.py`, and optional research helpers like `research-addon/research_addon/corpus.py:reload`

## Remaining Risks

- the branch still contains substantial pre-existing product work outside this cleanup pass, so history remains noisy even though the live path is cleaner
- `vulture` output still needs human judgment before any more backend deletions
- ignored runtime evidence under `backend/storage/` still matters for proof reproducibility, even though it is now intentionally outside source control
