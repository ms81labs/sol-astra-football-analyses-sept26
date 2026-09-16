from __future__ import annotations

from pathlib import Path

import backend.scripts.run_v7_1_tiny_overfit_sanity_train as tiny_train


def test_tiny_overfit_checkpoint_resolver_refuses_remote_only_paths() -> None:
    path, usable = tiny_train._resolve_inference_weights_path(
        {
            "trainingCompleted": True,
            "bestWeightsPath": "/workspace/remote/best.pt",
            "lastWeightsPath": "/workspace/remote/last.pt",
        }
    )

    assert path == Path("")
    assert usable is False
