---
name: research-addon-worker
description: Build and verify isolated supported-coverage autoresearch addon features without touching core product code.
---

# Research Addon Worker

NOTE: Startup and cleanup are handled by `worker-base`. This skill defines the work procedure for addon-lane features only.

## When to Use This Skill

Use this skill for features that create or update the isolated `research-addon/` lane, addon-owned tests, addon CLI surfaces, registry/state files, or `.factory/` knowledge needed by the addon mission.

Do not use this skill for core product implementation in `backend/**` or `frontend/**`.

## Required Skills

- `test-driven-development` — invoke before changing addon code so tests are written first.
- `systematic-debugging` — invoke if proof wrappers, targeted pytest suites, or path guards fail unexpectedly.
- `verification-before-completion` — invoke before finalizing the handoff so command evidence is real and current.

## Work Procedure

1. Read the assigned feature, `mission.md`, `AGENTS.md`, `.factory/library/architecture.md`, `.factory/library/environment.md`, `.factory/library/user-testing.md`, `.factory/services.yaml`, and `.factory/init.sh`.
2. Reconfirm the boundary before editing anything:
   - writable: `research-addon/**`, `research-addon/tests/**`, `.factory/**` only when the feature explicitly requires it
   - read-only: `backend/**`, `frontend/**`, live storage, truth-gate logic, detector/recovery/analytics implementation
3. Invoke `test-driven-development` before writing implementation code.
4. Add or update failing addon-focused tests first. Prefer narrow, feature-owned tests under `research-addon/tests/`. If the feature wraps an existing backend script, add tests that prove delegation/contract behavior without modifying the wrapped script.
5. Implement the minimum addon-side code/config needed to make the failing tests pass.
6. Manually verify the feature from the CLI:
   - use explicit temp roots
   - prefix proof/diagnosis commands with `QT_QPA_PLATFORM=offscreen` in this headless environment
   - capture resolved output/state paths
   - capture an exact path/write audit command (for example `git status --porcelain` plus temp-root listings)
   - capture an exact listener/process snapshot command when proving no services started
   - capture refusal behavior for unsafe or out-of-scope paths/tracks when relevant
   - verify no dev server, browser flow, or remote job is started
7. Run the relevant validators from `.factory/services.yaml`, plus any narrower feature-specific pytest command you added.
8. Invoke `verification-before-completion` before handoff. Re-run any stale command if the evidence predates your final code changes.
9. In the handoff, be explicit about:
   - exact files added/changed
   - exact tests added
   - exact commands run and what they proved
   - whether the feature touched only addon-owned paths
   - exact listener/path audit commands used for non-start and isolation claims

## Example Handoff

```json
{
  "salientSummary": "Built the addon registry/path-guard skeleton for the supported-coverage lane and proved that only addon-owned or temp roots are writable. Added failing tests first, then implemented the CLI/state helpers to make them pass. Verified the lane stays CLI-only and does not start services.",
  "whatWasImplemented": "Added research-addon registry/config modules, temp-root resolution helpers, and CLI entrypoints for listing tracks and resolving safe execution roots. Added addon tests covering supported-coverage as the only executable track, rejection of planned tracks, and rejection of unsafe write-path overrides into backend/storage or core source paths.",
  "whatWasLeftUndone": "",
  "verification": {
    "commandsRun": [
      {
        "command": ".factory/runtime/research-addon-venv/bin/python -m pytest research-addon/tests/test_registry.py research-addon/tests/test_paths.py -q",
        "exitCode": 0,
        "observation": "6 tests passed; addon registry and path-guard behavior matched the feature contract."
      },
      {
        "command": ".factory/runtime/research-addon-venv/bin/python -m pytest backend/tests/test_run_local_app_path_proof.py backend/tests/test_compare_local_remote_proof.py backend/tests/test_compare_ball_pipeline_trace.py -q",
        "exitCode": 0,
        "observation": "Existing proof/diagnosis wrapper suite still passed without any backend edits."
      },
      {
        "command": ".factory/runtime/research-addon-venv/bin/python -m research_addon.cli tracks list",
        "exitCode": 0,
        "observation": "Only supported-coverage was marked executable; deferred tracks were listed as planned."
      }
    ],
    "interactiveChecks": [
      {
        "action": "Ran the addon with an unsafe override pointing at backend/storage and inspected stdout/stderr plus filesystem state.",
        "observed": "Command failed fast before execution, reported the unsafe path, and no files were created outside research-addon or /tmp."
      },
      {
        "action": "Captured listener snapshots before and after CLI verification.",
        "observed": "No new listening ports appeared; verification stayed shell-only."
      }
    ]
  },
  "tests": {
    "added": [
      {
        "file": "research-addon/tests/test_registry.py",
        "cases": [
          {
            "name": "supported_coverage_is_only_executable_track",
            "verifies": "planned and unknown tracks are rejected before any trial artifacts are created"
          }
        ]
      },
      {
        "file": "research-addon/tests/test_paths.py",
        "cases": [
          {
            "name": "unsafe_override_is_rejected",
            "verifies": "output/state overrides cannot target backend/storage or core source paths"
          }
        ]
      }
    ]
  },
  "discoveredIssues": [
    {
      "severity": "medium",
      "description": "The existing backend proof scripts expose compact JSON but do not currently advertise a shared contract document, so the addon must define and maintain that contract itself."
    }
  ]
}
```

## When to Return to Orchestrator

- The feature cannot be completed without editing `backend/**` or `frontend/**`.
- The required wrapper target in `backend/scripts/` is missing, broken, or cannot be exercised from a temp root.
- The feature needs a new executable track beyond `supported-coverage`.
- Existing repo changes outside addon-owned paths are interfering with verification and cannot be isolated safely.
