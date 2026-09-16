# R13 — Exclude enemy passes from the home-only network

## RED

Added regressions for overlapping track IDs and an enemy-only stream. The focused test failed as expected:

- mixed home/enemy `7 -> 11`: received count `2`, expected `1`
- enemy-only `7 -> 11`: received one edge, expected none

Command: `npm --prefix frontend test -- --run src/utils/analytics.test.ts`

## GREEN

Filtered non-home events in `buildPassingNetwork` before edge aggregation.

Commands:

- `npm --prefix frontend test -- --run src/utils/analytics.test.ts` — 10 passed
- `npm --prefix frontend test -- --run` — 18 files, 56 tests passed

## Commit

`fix: exclude enemy passes from home network` (this commit)

## Concerns

None. The network remains intentionally home-only; a both-team model and renderer are out of scope.
