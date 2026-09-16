"""4.5A challenger adapters. None of these become production defaults."""

from __future__ import annotations

from typing import Any


def _inert(name: str) -> dict[str, Any]:
    return {"name": name, "default": False, "enabled": False, "role": "challenger"}


def onnx_runtime_adapter() -> dict[str, Any]:
    return _inert("onnx_runtime")


def tensorrt_adapter() -> dict[str, Any]:
    return _inert("tensorrt")


def pynv_adapter() -> dict[str, Any]:
    return _inert("pynvvideocodec")


def gstreamer_adapter() -> dict[str, Any]:
    return _inert("gstreamer")


def roboflow_trackers_adapter() -> dict[str, Any]:
    return _inert("roboflow_trackers")


def mcbyte_adapter() -> dict[str, Any]:
    return _inert("mcbyte_plus_plus")


def kloppy_boundary() -> dict[str, Any]:
    return {
        "name": "kloppy",
        "role": "import_export_boundary",
        "replacesInternalProvenance": False,
        "enabled": False,
        "default": False,
    }


def trackeval_adapter() -> dict[str, Any]:
    return _inert("trackeval")
