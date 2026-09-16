# Verification Workflow

## Principle

Use evidence before claims. The repo already has a lot of truth surfaces, so verification should be fresh and explicit.

## Core Verification Commands

Backend targeted tests:

```bash
python3 -m pytest backend/tests -q
```

Frontend:

```bash
npm --prefix frontend test
npm --prefix frontend build
```

Memory bank structure check:

```bash
python3 -m pytest backend/tests/test_memory_bank_structure.py -q
```

## Artifact Verification

When the active lane changes, verify these files agree:

- `backend/storage/benchmark_suites/frozen-viable-baseline-slice-suite/suite_summary.json`
- `backend/storage/benchmark_suites/frozen-viable-baseline-slice-suite/active_lane_snapshot.json`
- `backend/storage/benchmark_suites/frozen-viable-baseline-slice-suite/suite_robustness_diagnosis.json`
- any lane-specific matrix such as `detector_breadth_matrix.json`

## Remote Closeout Verification

After RunPod work:

```bash
runpodctl pod list --all -o json
```

The expected normal-state result is an empty list.

## Practical Guidance

- prefer targeted test runs when touching a narrow slice
- run broader verification before claiming a lane is complete
- do not trust a batch result until the generated artifact files actually exist and match the claimed next lever
