from __future__ import annotations

import pytest
from pydantic import ValidationError

from backend.app.workbench import contracts


def test_phase_zero_shared_contracts_are_strict_and_preserve_unknowns() -> None:
    """Phase 0: shared contracts reject extra data and keep unknown measurements null."""
    generation_type = getattr(contracts, "GenerationManifest", None)
    metric_type = getattr(contracts, "CanonicalMetricRecord", None)
    budget_type = getattr(contracts, "JobBudgetSnapshot", None)
    receipt_type = getattr(contracts, "MeasuredRuntimeReceipt", None)
    assert all((generation_type, metric_type, budget_type, receipt_type)), "shared remediation contracts are missing"

    manifest = generation_type(
        generationId="gen_abc",
        matchId="match-1",
        observationDigest="a" * 64,
        correctionHead="cmd-1",
        algorithmVersions={"analytics": "1"},
        files={"frames.json": "b" * 64},
        publishedAt="2026-09-18T00:00:00Z",
    )
    metric = metric_type(
        metric="distance",
        definitionVersion="1",
        scope={"team": "my_team", "player": None, "interval": None},
        generationId=manifest.generationId,
        value=None,
        unit="m",
        availability="unknown",
        status="observed",
        eligibleSeconds=None,
        requestedSeconds=90.0,
        algorithmRevision="analytics-1",
        reasonCodes=["CALIBRATION_UNAVAILABLE"],
    )
    budget = budget_type(
        requestId="request-1",
        authorisedBudget=1.25,
        settledTotal=0.5,
        reservedTotal=0.75,
        unsettledTotal=0.0,
        actualTotal=0.5,
    )
    receipt = receipt_type(
        sourceIdentity="source-1",
        modelIdentity=None,
        runtimeBuild="runtime-1",
        decodedFrames=10,
        inferenceCalls=2,
        batchSizes=[5, 5],
        recoveryCalls=0,
        trackerUpdates=10,
        exportedSamples=2,
        timestampPolicy="source_pts",
        timeBase=(1, 30),
        timingBoundaries={},
        peakMemoryBytes=None,
        transferredBytes=None,
        committedGeneration=None,
    )

    assert metric.value is None
    assert budget.actualTotal == 0.5
    assert receipt.peakMemoryBytes is None
    with pytest.raises(ValidationError):
        generation_type(**manifest.model_dump(), unexpected=True)
