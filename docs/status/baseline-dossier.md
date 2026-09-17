# Baseline dossier (GA-01)

Selected commit: git HEAD of this candidate (feature base `5fa98440c09cabdbc5847920cea097268c5a5171`; plan source snapshot `5099e1fd50d856a7cd0449f1ef4b1695d8f930c3`).
Plan version: 1.1 (16 September 2026).
Protocol: `football_analysis_pilot_labels_v3`.
Declared camera profile: **stitched panoramic/tactical view** (development profile; not certified).
Declared first workflow: upload supported footage, calibrate, review, correct, playlist, deterministic report.

## Provenance rule

Each result below is labelled reproduced, imported from historical evidence, or proposed. This dossier does not rerun sealed inference, Daytona jobs, or independent labelling.

## Evidence classes

| Class | Current record | Consequence |
|---|---|---|
| Software verification | Imported historical: provider-disabled gates passed for a recorded release source that is not identical to this inspected SHA. | Keep source-bound receipts. |
| Pipeline execution | Imported historical: earlier-source sealed CPU/GPU short-clip runs completed. | Prove the exact candidate source before product acceptance. |
| Independent accuracy | Reproduced current-state: 0 / 18 locked tasks, no HOTA/IDF1/visible-ball/pitch/possession/event acceptance. | Automatic outputs remain review-only. |
| Capacity | Imported historical: two-half end-to-end times 8378.199 s and 8145.772 s. | Diagnostic only, not current throughput or billing. |
| Analyst acceptance | Reproduced current-state: no declared-camera pilot accepted. | Unproven. |

## Capability matrix

See `docs/status/capability-matrix.json` and `GET /api/workbench/capabilities`. Manual review is usable. Team estimates, event suggestions and incident review are review-only or experimental. Player attribution is unproven. Physical metrics are unavailable.

## Unresolved gates

- independent labels 0 / 18
- no declared-camera analyst acceptance
- no acceptance-qualified HOTA/IDF1
- no current-source sealed inference
- G-NETWORK required before non-loopback deployment

## Permitted next actions

Implement evidence/availability contracts and review UI; instrument sampling counters on fixtures without a new cloud run; complete the independent annotation/declaration plan under frozen protocol v3.

## Forbidden actions

No new Daytona/GPU job without source-bound approval. Do not convert historical G-CAPACITY or G-PRODUCT success into current-source acceptance. Do not relax frozen protocol v3. Do not treat export fps as inference fps. Custom Rust/C++ remains gated (GA-18).
