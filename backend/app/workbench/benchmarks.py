"""GA-15/17/18 experiment receipts. Hardware and native work stay fail-closed."""

from __future__ import annotations

from pydantic import Field

from .contracts import StrictModel

EXPERIMENTS = ("B0", "B1", "B2", "B3", "B4", "B5")


class ExperimentReceipt(StrictModel):
    experiment: str
    promoted: bool = False
    status: str
    exportFpsEqualsInferenceFps: bool = False
    reasonCodes: list[str] = Field(default_factory=list)
    hardwareVerified: bool = False


def experiment_receipt(
    experiment: str,
    *,
    hardware_verified: bool = False,
    bottleneck_documented: bool = False,
) -> ExperimentReceipt:
    if experiment == "B5" and not bottleneck_documented:
        return ExperimentReceipt(
            experiment=experiment,
            promoted=False,
            status="inert",
            hardwareVerified=hardware_verified,
            reasonCodes=["NATIVE_GATE_CLOSED"],
        )
    if experiment in {"B2", "B3"} and not hardware_verified:
        return ExperimentReceipt(
            experiment=experiment,
            promoted=False,
            status="experimental",
            hardwareVerified=False,
            reasonCodes=["HARDWARE_UNAVAILABLE"],
        )
    return ExperimentReceipt(
        experiment=experiment,
        promoted=False,
        status="baseline" if experiment == "B0" else "recorded",
        hardwareVerified=hardware_verified,
        reasonCodes=["EXPORT_FPS_IS_NOT_INFERENCE_FPS"],
    )
