"""Global pytest fixtures and mocks — loaded before any test module is imported."""
from __future__ import annotations

import atexit
import os
import shutil
import sys
import tempfile
import types

import pytest


os.environ.setdefault("GA_FLAG_LEFTOVER_HTTP", "1")

_STORAGE_ROOT_ENV = "GUERILLA_STORAGE_ROOT"
_ORIGINAL_STORAGE_ROOT_PRESENT = _STORAGE_ROOT_ENV in os.environ
_ORIGINAL_STORAGE_ROOT = os.environ.get(_STORAGE_ROOT_ENV)
_PYTEST_STORAGE_ROOT = tempfile.mkdtemp(prefix="guerilla-pytest-storage-")
os.environ[_STORAGE_ROOT_ENV] = _PYTEST_STORAGE_ROOT


def _cleanup_pytest_storage_root() -> None:
    try:
        shutil.rmtree(_PYTEST_STORAGE_ROOT)
    except FileNotFoundError:
        pass
    finally:
        if _ORIGINAL_STORAGE_ROOT_PRESENT:
            assert _ORIGINAL_STORAGE_ROOT is not None
            os.environ[_STORAGE_ROOT_ENV] = _ORIGINAL_STORAGE_ROOT
        else:
            os.environ.pop(_STORAGE_ROOT_ENV, None)


atexit.register(_cleanup_pytest_storage_root)


def pytest_unconfigure() -> None:
    _cleanup_pytest_storage_root()
    atexit.unregister(_cleanup_pytest_storage_root)


import numpy as np


def _make_cv2_stub():
    """cv2 stub with a DLT-based findHomography that works without opencv."""

    class _MockVideoCapture:
        def isOpened(self):
            return False

        def read(self):
            return False, None

        def get(self, _prop):
            return 0.0

        def set(self, _prop, _val):
            pass

    def _dlt_homography(src, dst, _method=0, _ransacReprojThreshold=3.0, _maxIters=2000, confidence=0.995):
        src = np.array(src, dtype=np.float64)
        dst = np.array(dst, dtype=np.float64)
        if len(src) >= 4:
            area = abs(
                src[0][0] * (src[1][1] - src[2][1])
                + src[1][0] * (src[2][1] - src[0][1])
                + src[2][0] * (src[0][1] - src[1][1])
            )
            if area < 1e-6:
                return None
        n = len(src)
        A = np.zeros((2 * n, 9), dtype=np.float64)
        for i in range(n):
            sx, sy = src[i]
            dx, dy = dst[i]
            A[2 * i] = [-sx, -sy, -1, 0, 0, 0, sx * dx, sy * dx, dx]
            A[2 * i + 1] = [0, 0, 0, -sx, -sy, -1, sx * dy, sy * dy, dy]
        _, _, Vt = np.linalg.svd(A)
        H = Vt[-1].reshape(3, 3)
        H /= H[2, 2]
        return H, np.ones(n, dtype=np.uint8)

    m = types.ModuleType("cv2")
    m.findHomography = _dlt_homography
    m.circle = staticmethod(lambda *a, **k: None)
    m.imshow = staticmethod(lambda *a, **k: None)
    m.setMouseCallback = staticmethod(lambda *a, **k: None)
    m.waitKey = staticmethod(lambda *a, **k: -1)
    m.destroyAllWindows = staticmethod(lambda: None)
    m.resize = staticmethod(lambda img, _d, **k: img)
    m.VideoCapture = staticmethod(lambda *a, **k: _MockVideoCapture())
    m.EVENT_LBUTTONDOWN = 1
    m.FILLED = -1
    m.CAP_PROP_FPS = 5
    m.CAP_PROP_POS_FRAMES = 1
    m.CAP_PROP_POS_MSEC = 0
    return m


def _make_pandas_stub():
    """Minimal pandas stub so run_guerilla.py can be imported without pandas installed."""
    m = types.ModuleType("pandas")
    m.DataFrame = type("DataFrame", (), {"__init__": lambda self, *a, **k: None})
    m.to_parquet = staticmethod(lambda *a, **k: None)
    return m


def _make_ultralytics_stub():
    """Minimal ultralytics stub so run_guerilla.py can be imported without it."""
    m = types.ModuleType("ultralytics")
    m.__version__ = "0.0.0-test-stub"
    m.YOLO = type("YOLO", (), {"__init__": lambda self, *a, **k: None})
    return m


# Install stubs for any missing packages so their importers (e.g. run_guerilla.py) can load.
# All _make_* functions are defined above this loop to avoid NameError on forward reference.
for _mod_name, _make_stub in [
    ("cv2", _make_cv2_stub),
    ("pandas", _make_pandas_stub),
    ("ultralytics", _make_ultralytics_stub),
]:
    try:
        __import__(_mod_name)
    except ModuleNotFoundError:
        sys.modules[_mod_name] = _make_stub()


_RUNTIME_BOUNDARY_TEST_MODULES = frozenset(
    {
        "test_api",
        "test_gpu_contract",
        "test_processor",
        "test_run_benchmark_suite",
        "test_run_benchmarks",
        "test_run_clip_manifest_expansion",
        "test_run_source_robustness_batch",
    }
)


@pytest.fixture(autouse=True)
def _validated_release_runtime_defaults(request, tmp_path, monkeypatch):  # noqa: ANN001, ANN202
    """Keep runtime-boundary tests independent from post-S release metadata."""

    module_name = request.module.__name__.rsplit(".", 1)[-1]
    if module_name not in _RUNTIME_BOUNDARY_TEST_MODULES:
        return

    from backend.app import processor, run_benchmarks
    from backend.tests.runtime_manifest_fixture import install_minimal_runtime_manifest

    for runtime_module in (processor, run_benchmarks):
        install_minimal_runtime_manifest(tmp_path, monkeypatch, runtime_module)
