"""Reviewing retained matches does not require the detector worker package."""

import subprocess
import sys


def test_review_service_imports_without_ultralytics() -> None:
    script = """
import sys
sys.modules['ultralytics'] = None
from backend.app.review_service import ReviewService
from backend.run_guerilla import YOLO
assert ReviewService
try:
    YOLO('unused')
except ModuleNotFoundError:
    pass
else:
    raise AssertionError('detector fallback')
"""
    completed = subprocess.run(
        [sys.executable, "-c", script],
        capture_output=True, text=True, timeout=10,
    )
    assert completed.returncode == 0, completed.stderr
