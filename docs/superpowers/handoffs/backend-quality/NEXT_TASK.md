# Next task: choose the next bounded batch

**No saved draft.** `REPORT_STORE_STRUCTURE` is applied and accepted at `1dd6bdd` (see ACCEPTANCE.json `subsequentAcceptances`). Do not re-apply `unpublished/report-store-extraction.patch`; it is kept only for provenance.

Pick one bounded batch from the open packages in [COMPLETED_AND_OPEN.md](COMPLETED_AND_OPEN.md), reconcile live main first, and follow [VERIFICATION_RUNBOOK.md](VERIFICATION_RUNBOOK.md). Reasonable next candidates:

- **BQ04, storage:** continue extracting from `backend/app/storage.py`, preserving transactions, rollback, generations, lock spans and publication side effects. Characterize before moving code.
- **BQ02, catapult debt:** the catapult merge recorded 23 C901 and 7 BLE001 entries, most in `segmentation_worker.py`, `provider_gateway.py`, `provider_images.py` and `workbench/assistance.py`. The BLE001 handlers are deliberate fail-closed normalizations; review each boundary rather than narrowing blindly.
- **BQ03, routes:** `create_leftover_get_routers` and `create_leftover_post_router` remain the largest route factories.

For whichever batch you choose, record the original and candidate evidence, run mutation or differential checks where a refactor claims equivalence, publish through a PR merged into main, and accept only after completed normal CI plus C05/C06 on the merged SHA.
