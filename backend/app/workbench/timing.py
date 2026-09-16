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
