# Guerilla Analytics v1.1 workbench implementation

> **For agentic workers:** this records the GA-01..GA-18 software contracts landed in `backend/app/workbench/`.

**Goal:** implement the v1.1 plan's work packages as testable application code without relaxing frozen evaluation gates or authorising provider mutation.

**Architecture:** Python workbench package behind `/api/workbench/*`, FrameSource adapters, sampling receipts on the unchanged Ultralytics track loop, React capability matrix.

**Tech stack:** FastAPI, Pydantic, React/TypeScript, pytest, vitest.

## Global Constraints

- Frozen protocol `football_analysis_pilot_labels_v3` remains authoritative.
- Export fps is not inference fps.
- Unknown metrics must not become measured zeros.
- Loopback-only until G-NETWORK.
- GA-17 may remain deferred without hardware.
- GA-18 stays inert without `GA18_NATIVE_APPROVAL=1`.
- Independent labels remain 0 / 18 unless a later authorised labelling run changes that evidence.
