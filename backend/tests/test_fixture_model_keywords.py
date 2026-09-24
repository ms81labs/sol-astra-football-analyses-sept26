"""Do not imply fixture coverage using fields that Pydantic silently discards."""

import ast
from pathlib import Path

import pytest

from backend.app.schemas import MatchConfig, ShotAnalytics


@pytest.mark.parametrize(
    "filename,model",
    [
        ("test_run_benchmark_suite.py", ShotAnalytics),
        ("test_run_benchmarks.py", ShotAnalytics),
        ("test_run_clip_manifest_expansion.py", ShotAnalytics),
        ("test_video_pipeline.py", MatchConfig),
    ],
)
def test_fixture_constructor_keywords_belong_to_the_model(filename, model):
    # These four fixtures import the named model directly, without aliases.
    source = Path(__file__).with_name(filename).read_text(encoding="utf-8")
    calls = [
        node
        for node in ast.walk(ast.parse(source))
        if isinstance(node, ast.Call)
        and isinstance(node.func, ast.Name)
        and node.func.id == model.__name__
    ]
    assert calls, (filename, model.__name__)
    for call in calls:
        supplied = {keyword.arg for keyword in call.keywords}
        assert None not in supplied, (
            "Expanded fixture keywords require explicit validation"
        )
        assert supplied <= model.model_fields.keys(), (
            filename,
            call.lineno,
            supplied - model.model_fields.keys(),
        )
