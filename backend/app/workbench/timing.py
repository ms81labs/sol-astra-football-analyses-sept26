"""GA-15 stage timing. Overlapped stage durations are not additive wall time."""

from __future__ import annotations

from pydantic import Field

from .contracts import StrictModel


class StageTiming(StrictModel):
    decode: float
    preprocess: float
    transfer: float
    inference: float
    association: float
    recovery: float
    serialisation: float
    wallTime: float
    stageSum: float
    overlappedStagesAreAdditive: bool = False
    notes: list[str] = Field(default_factory=list)


def stage_timing(
    *,
    decode: float,
    preprocess: float,
    transfer: float,
    inference: float,
    association: float,
    recovery: float,
    serialisation: float,
    wall_time: float,
    overlapped: bool = True,
) -> StageTiming:
    stage_sum = round(decode + preprocess + transfer + inference + association + recovery + serialisation, 4)
    return StageTiming(
        decode=decode,
        preprocess=preprocess,
        transfer=transfer,
        inference=inference,
        association=association,
        recovery=recovery,
        serialisation=serialisation,
        wallTime=wall_time,
        stageSum=stage_sum,
        overlappedStagesAreAdditive=False if overlapped else stage_sum == wall_time,
        notes=["Overlapped stage durations are not additive wall time.", "Time completed work, not asynchronous submission."],
    )


def gpu_timing_scope(*, submission_ms: float, completed_ms: float | None, device_aware: bool) -> dict[str, object]:
    admitted = completed_ms is not None and device_aware
    return {
        "submissionMs": submission_ms,
        "completedMs": completed_ms,
        "deviceAware": device_aware,
        "usesSubmissionAsCompletedWork": False,
        "admitted": admitted,
        "reasonCodes": [] if admitted else ["GPU_TIMING_SUBMISSION_IS_NOT_COMPLETED_WORK"],
    }
