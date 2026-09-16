# Task 7 R07 report

## Scope

- Added one `pendingAction` boolean and local control toggling to each R03 legacy review page.
- A pending decision or resolver disables all native form/action controls, marks the review region `aria-busy`, and makes canvas, navigation, filter, reason, and keyboard handlers no-ops.
- Decision and resolver boundaries now catch request, JSON, response-status, and reload failures, retain the visible draft/item/bbox on failure, and unlock in `finally`.
- Existing decision URLs, resolver URLs, request payloads, auto-advance behavior, resolver success text, and R03 text-only metadata rendering are retained.

## TDD evidence

RED: `npm --prefix frontend test -- --run src/legacyReviewUi.test.ts` initially ran 9 tests with 6 failures: no `aria-busy`/control lock, navigation could run during a pending save, and three rejected save requests were reported as unhandled rejections.

GREEN: the focused command now passes 11 tests. The tests execute all three real inline scripts in jsdom and cover deferred save/reload, duplicate decision/navigation/shortcut prevention, every native control disabled, rejected fetch, invalid JSON, draft retention, and duplicate resolver prevention.

## Verification

- `npm --prefix frontend test -- --run src/legacyReviewUi.test.ts` — pass, 11 tests.
- `npm run lint` (in `frontend`) — pass.
- `npx tsc --noEmit -p tsconfig.app.json` (in `frontend`) — pass.
- `npx tsc --noEmit -p tsconfig.node.json` (in `frontend`) — pass.
- `npm run build` (in `frontend`) — pass; `tsc -b && vite build`.
- `git diff --check` — pass.

## Files

- `backend/review_ui/promoted_v6_manual_review/index.html`
- `backend/review_ui/v7_1_positive_diversity_review/index.html`
- `backend/review_ui/football_external_soccernet_detector_miss_review/index.html`
- `frontend/src/legacyReviewUi.test.ts`

## Self-review and concerns

Reviewed the full diff for control coverage, safe async boundaries, unchanged endpoints/payloads, retained auto-advance/status text, and R03 text rendering. No provider/cloud/smoke/install/real-data operations occurred. An unrelated untracked `.verification/` directory was left untouched and is excluded from the commit.

## Reviewer fix round 1

### Root cause and RED evidence

The pending guard on `mouseup` in promoted-v6 and v7.1 returned before clearing `dragMode` and `dragStart`; detector-miss did the same for `dragStart`. A keyboard save during a canvas drag could therefore receive a pending `mouseup`, unlock after completion, and let the next `mousemove` apply the stale drag state.

Added real-script jsdom regressions for drag then keyboard-save (decision-button save for detector-miss, which has no shortcut), pending `mouseup`, rejected and successful completion, post-unlock mousemove, and a second saved bbox. The RED focused run had 16 tests with 2 failures: the second bbox was mutated to `{ x1: 637.2, y1: 372.8, x2: 657.2, y2: 392.8 }` instead of the original `{ x1: 10, y1: 20, x2: 30, y2: 40 }`.

Also added accepted-decision reload-boundary regressions for rejected, non-OK, and invalid-JSON `/api/review-state` responses across all three pages. They assert three requests, preserved item/notes/reason/bbox, safe error text, and unlocked controls. Pending coverage now explicitly attempts notes/reason keys, reason-chip, auto-advance, canvas, navigation, and shortcuts.

### Fix and GREEN evidence

Each page now clears only transient drag state at `mouseup` before its pending return; no draft, bbox, API path, or payload changed. The final focused command passes 16 tests with no unhandled rejections. Refreshed lint, both TypeScript checks, and production build all pass. `git diff --check` is clean.

## Reviewer fix round 2

Replaced the pending-canvas test's unobservable pointer dispatch with a real-script behavioral regression. Each page now starts from the literal `{ x1: 10, y1: 20, x2: 30, y2: 40 }` fixture bbox, begins a save, dispatches the pending canvas events, rejects that save, retries, and asserts the retry payload preserves that same bbox. Removing a pending canvas pointer guard would mutate the retained client-side bbox and fail this retry assertion.

No production change was needed. `npm --prefix frontend test -- --run src/legacyReviewUi.test.ts` passes 16 tests; frontend lint and `tsconfig.app.json` TypeScript checks pass; `git diff --check` is clean. The round changes only `frontend/src/legacyReviewUi.test.ts` and this report.
