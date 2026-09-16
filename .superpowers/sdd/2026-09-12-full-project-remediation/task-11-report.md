# Task 11 report — R11 frontend toolchain security refresh

## Status

DONE

## What changed

- Removed the proven-unused direct development declarations `@testing-library/jest-dom`, `autoprefixer`, and `postcss`.
- Upgraded direct `vitest` from `^3.2.4` to `^4.1.11`; the resolved version is 4.1.11 and its Node engine includes CI's Node 22.
- Refreshed only the affected compatible transitive locks needed to remove the current advisories. Among direct resolved packages, only Vitest changed; Vite remains 7.3.6 and the prior React, Tailwind, ESLint, TypeScript, and type-package resolutions are preserved.
- Pinned the existing direct `eslint-plugin-react-hooks` declaration to exact 7.0.1. An initial broad compatible refresh selected 7.1.1, whose newly enabled rules rejected two existing hooks; keeping the already-tested 7.0.1 avoids changing product source for an unrelated lint-policy upgrade.
- Added `node` to `tsconfig.app.json`'s explicit `types`. Vitest 4 no longer supplies the implicit Node type reference on which `src/legacyReviewUi.test.ts` relied for `node:fs`; this one-line configuration correction restores explicit ownership of the already-direct `@types/node` package.

No product source, CI, verification script, provider, cloud resource, or real data was changed.

## TDD evidence

### RED

The controller-authorized recorded registry audit was the RED state:

- `npm --prefix frontend audit --json`
- Result: 11 development vulnerabilities — 1 critical, 6 high, 3 moderate, 1 low.
- Direct `vitest@3.2.4` was affected and all recorded findings had fixes available.
- `npm --prefix frontend audit --omit=dev --json`: 0 vulnerabilities.

The RED audit was explicitly accepted as recorded evidence, so it was not repeated before editing.

### GREEN

After the final targeted lock refresh:

- `npm --prefix frontend audit --json`: 0 vulnerabilities at every severity.
- `npm --prefix frontend audit --omit=dev --json`: 0 vulnerabilities at every severity.

The current registry briefly exposed nine additional fixable development advisories after only the Vitest upgrade. They traced through existing direct tools rather than a new direct dependency. The final compatible lock resolves the affected packages to:

- `@babel/core` 7.29.7
- `@humanfs/node` 0.16.8
- `baseline-browser-mapping` 2.11.22
- `brace-expansion` 1.1.18 and 2.1.4
- `browserslist` 4.28.9
- `flatted` 3.4.4
- `js-yaml` 4.3.2
- `minimatch` 3.1.5 and 9.0.9
- `ws` 8.21.3

No override, forced audit fix, or new direct dependency was used.

## Verification

Final evidence was run from a clean install against the final lockfile:

1. `npm ci --prefix frontend`
   - Added 273 packages; audit summary 0 vulnerabilities.
   - npm emitted its install-script policy notice for transitive `esbuild@0.28.2`; no script approval or global mutation was performed.
2. `npm --prefix frontend audit --json`
   - 0 info, 0 low, 0 moderate, 0 high, 0 critical; total 0.
3. `npm --prefix frontend audit --omit=dev --json`
   - 0 info, 0 low, 0 moderate, 0 high, 0 critical; total 0.
4. `npm --prefix frontend test -- --run`
   - Vitest 4.1.11; 19 files passed, 80 tests passed.
5. `npm --prefix frontend run lint`
   - Exit 0, no findings.
6. `npx --prefix frontend tsc --noEmit -p frontend/tsconfig.app.json`
   - Exit 0.
7. `npx --prefix frontend tsc --noEmit -p frontend/tsconfig.node.json`
   - Exit 0.
8. `npm --prefix frontend run build`
   - TypeScript build and Vite 7.3.6 production build passed; 56 modules transformed.
9. `git diff --check`
   - Exit 0.

## Files changed

- `frontend/package.json`
- `frontend/package-lock.json`
- `frontend/tsconfig.app.json`
- `.superpowers/sdd/2026-09-12-full-project-remediation/task-11-report.md`

## Self-review

- Confirmed the root dependency declarations removed only the three approved unused packages.
- Confirmed `postcss` remains legitimately transitive through Vite/Tailwind rather than direct.
- Confirmed Vitest resolves to 4.1.11, not V5, and Vite remains on V7.
- Rejected a broad all-package lock refresh during self-review because it advanced unrelated direct runtime/tool resolutions; regenerated from the base lock and refreshed only the traced vulnerable packages.
- Confirmed `.verification/` remains untouched and uncommitted.

## Concerns

None. The npm install-script policy notice for esbuild is an environment/tooling notice, not a vulnerability or test failure.
