from __future__ import annotations

import os

import pytest


@pytest.mark.gpu
@pytest.mark.skipif(
    os.environ.get("GA_VERIFICATION_PROFILE") != "cuda-linux",
    reason="runs only in the explicit GPU acceptance profile",
)
def test_gpu_acceptance_runner_has_usable_cuda() -> None:
    import torch

    assert torch.cuda.is_available(), "GPU acceptance requires CUDA; do not report a skipped CPU run as green"
    assert torch.cuda.device_count() > 0
    assert torch.empty(1, device="cuda").device.type == "cuda"
