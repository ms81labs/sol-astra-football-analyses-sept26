"""Runtime evaluation must not need research command modules to be installed."""
import os
from pathlib import Path
import shutil
import subprocess
import sys
import zipfile

RUNTIME_PROBE = r'''
import importlib.abc
import sys
class RejectResearch(importlib.abc.MetaPathFinder):
    def find_spec(self, fullname, path=None, target=None):
        if fullname == "backend.scripts" or fullname.startswith("backend.scripts."):
            raise ImportError("runtime imported research: " + fullname)
sys.meta_path.insert(0, RejectResearch())
from backend.app import evaluation_verifier as verifier
assert verifier.parse_unique_json(b'{"frames": []}') == {"frames": []}
try:
    verifier.parse_unique_json(b'{"frames": [], "frames": []}')
except ValueError:
    pass
else:
    raise AssertionError("duplicate label keys accepted")
from backend.app.pilot_tracking import build_trackeval_sequence_data, evaluate_tracking
from pathlib import Path
task = dict(sourceFps=25, sourceStartFrame=0, sourceEndFrameExclusive=10,
            evaluationFrameStep=5, evaluationFrameCount=2)
protocol = {"evaluationFrames": {"targetFps": 5}}
labels = {"frames": [{"frameId": i, "entities": []} for i in (0, 5)]}
assert verifier.evaluation_frame_ids(task, protocol) == [0, 5]
data = build_trackeval_sequence_data(task, labels, [], protocol)
assert data["num_timesteps"] == 2 and data["num_gt_dets"] == 0
assert [matrix.shape for matrix in data["similarity_scores"]] == [(0, 0), (0, 0)]
try:
    evaluate_tracking(data, trackeval_root=Path("/definitely-not-a-pinned-scorer"))
except ValueError as error:
    assert "pinned TrackEval commit" in str(error)
else:
    raise AssertionError("unpinned scorer accepted")
assert not any(name == "backend.scripts" or name.startswith("backend.scripts.") for name in sys.modules)
'''


def test_runtime_evaluation_without_research_imports(tmp_path):
    root = Path(__file__).resolve().parents[2]
    result = subprocess.run(
        [sys.executable, "-c", RUNTIME_PROBE], cwd=tmp_path,
        env={**os.environ, "PYTHONPATH": str(root)},
        capture_output=True, text=True, timeout=30, check=False,
    )
    assert result.returncode == 0, result.stdout + result.stderr


def test_research_commands_reexport_the_runtime_implementations():
    from backend.app import pilot_labels, pilot_tracking
    from backend.scripts import evaluate_football_analysis_pilot as scorer
    from backend.scripts import validate_football_analysis_pilot_labels as labels
    for name in ("parse_unique_json", "parse_utc_timestamp", "validate_label_payload"):
        assert getattr(labels, name) is getattr(pilot_labels, name)
    for name in ("evaluation_frame_ids", "build_trackeval_sequence_data", "evaluate_tracking"):
        assert getattr(scorer, name) is getattr(pilot_tracking, name)
    assert scorer.TRACKEVAL_COMMIT == pilot_tracking.TRACKEVAL_COMMIT


def test_built_runtime_wheel_excludes_research_and_still_evaluates(tmp_path):
    root = Path(__file__).resolve().parents[2]
    source = tmp_path / "build-source"
    source.mkdir()
    for name in ("pyproject.toml", "README.md", "lap.py"):
        shutil.copy2(root / name, source / name)
    shutil.copytree(root / "backend", source / "backend", ignore=shutil.ignore_patterns("__pycache__", "storage", "venv", ".pytest_cache"))
    built = subprocess.run(
        [sys.executable, "-m", "pip", "wheel", "--no-deps", "--no-build-isolation", "--no-index", ".", "-w", "dist"],
        cwd=source, capture_output=True, text=True, timeout=90, check=False,
    )
    assert built.returncode == 0, built.stdout + built.stderr
    wheel = next((source / "dist").glob("*.whl"))
    installed = tmp_path / "installed"
    with zipfile.ZipFile(wheel) as archive:
        assert not any(name.startswith("backend/scripts/") for name in archive.namelist())
        archive.extractall(installed)
    probe = "from pathlib import Path\nimport backend\nassert Path(backend.__file__).resolve().is_relative_to(Path(" + repr(str(installed)) + "))\n" + RUNTIME_PROBE
    result = subprocess.run(
        [sys.executable, "-c", probe], cwd=tmp_path,
        env={**os.environ, "PYTHONPATH": str(installed)}, capture_output=True,
        text=True, timeout=30, check=False,
    )
    assert result.returncode == 0, result.stdout + result.stderr
