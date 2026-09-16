"""GA-17 GPU capability probes and GA-18 native-code gate."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from .contracts import StrictModel

NATIVE_APPROVAL_NAME = "GA18_NATIVE_APPROVAL"
DEFAULT_NATIVE_DIR = Path("native")


class GpuCapability(StrictModel):
    available: bool
    backend: str | None
    reasonCodes: list[str]
    canPromoteDefault: bool = False


class NativeGate(StrictModel):
    approved: bool
    reasonCodes: list[str]
    nativeDirPresent: bool
    owner: str | None = None
    bottleneck: str | None = None


def probe_gpu(*, nvidia_smi_ok: bool | None = None, torch_cuda: bool | None = None) -> GpuCapability:
    if nvidia_smi_ok is None and torch_cuda is None:
        detected = _detect_cuda()
        nvidia_smi_ok = detected["nvidia"]
        torch_cuda = detected["torch"]
    available = bool(nvidia_smi_ok and torch_cuda)
    if not available:
        return GpuCapability(
            available=False,
            backend=None,
            reasonCodes=["HARDWARE_UNAVAILABLE"],
            canPromoteDefault=False,
        )
    return GpuCapability(
        available=True,
        backend="cuda",
        reasonCodes=[],
        canPromoteDefault=False,
    )


def native_gate(*, repo_root: Path, approval_env: dict[str, str] | None = None) -> NativeGate:
    env = approval_env if approval_env is not None else {}
    native_dir = repo_root / DEFAULT_NATIVE_DIR
    approved = env.get(NATIVE_APPROVAL_NAME) == "1"
    if not approved:
        return NativeGate(
            approved=False,
            reasonCodes=["NATIVE_GATE_CLOSED"],
            nativeDirPresent=native_dir.exists(),
        )
    return NativeGate(
        approved=True,
        reasonCodes=[],
        nativeDirPresent=native_dir.exists(),
        owner=env.get("GA18_OWNER"),
        bottleneck=env.get("GA18_BOTTLENECK"),
    )


def _detect_cuda() -> dict[str, bool]:
    nvidia = False
    torch_cuda = False
    try:
        import shutil
        import subprocess

        binary = shutil.which("nvidia-smi")
        if binary:
            completed = subprocess.run([binary, "-L"], capture_output=True, check=False, timeout=5)
            nvidia = completed.returncode == 0 and bool(completed.stdout.strip())
    except Exception:
        nvidia = False
    try:
        import torch  # type: ignore

        torch_cuda = bool(getattr(torch, "cuda", None) and torch.cuda.is_available())
    except Exception:
        torch_cuda = False
    return {"nvidia": nvidia, "torch": torch_cuda}
