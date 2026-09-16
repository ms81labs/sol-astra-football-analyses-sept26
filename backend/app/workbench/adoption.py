"""1.2 dependency adoption records. Adapters stay replaceable."""

from __future__ import annotations

from typing import Any


def dependency_register() -> dict[str, Any]:
    return {
        "ultralytics": {
            "job": "player_ball_baseline",
            "owner": "cv",
            "licence": "review_exact_code_and_weights",
            "rollbackPath": "pinned_previous_detector_adapter",
            "fashionableOnly": False,
        },
        "opencv": {
            "job": "cpu_decode_reference",
            "owner": "media",
            "rollbackPath": "fixture_frame_source",
            "fashionableOnly": False,
        },
        "ffmpeg": {
            "job": "probe_proxy_export",
            "owner": "media",
            "rollbackPath": "opencv_cpu_fallback",
            "fashionableOnly": False,
        },
    }
