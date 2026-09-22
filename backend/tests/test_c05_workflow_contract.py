from pathlib import Path

import yaml


WORKFLOW = Path(__file__).parents[2] / ".github/workflows/c05-regressions.yml"
TRACKEVAL_COMMIT = "12c8791b303e0a0b50f753af204249e622d0281a"


def test_c05_workflow_covers_determining_changes_without_paid_execution() -> None:
    workflow = yaml.load(WORKFLOW.read_text(), Loader=yaml.BaseLoader)
    events = workflow["on"]

    assert {"main", "agent/c05-identity-evaluation"} <= set(
        events["push"]["branches"]
    )
    required_paths = {"backend/**", "pyproject.toml", "scripts/**", ".github/workflows/**"}
    assert required_paths <= set(events["push"]["paths"])
    assert required_paths <= set(events["pull_request"]["paths"])
    assert "workflow_dispatch" in events
    assert workflow["permissions"] == {"contents": "read"}

    source = WORKFLOW.read_text()
    assert f"ref: {TRACKEVAL_COMMIT}" in source
    assert "backend/tests/test_audit_v3_c05*.py" in source
    assert "event-name.txt" in source
    assert "event-base-sha.txt" in source
    assert "event-head-sha.txt" in source
    assert "pytest-runs" in source

    job = workflow["jobs"]["source"]
    test_step = next(
        step for step in job["steps"] if step.get("name", "").startswith("Verify C05")
    )
    assert test_step["env"]["VERIFY_DAYTONA"] == "0"
    assert test_step["env"]["ALLOW_DAYTONA_MUTATION"] == "0"
    assert test_step["env"]["GA_VERIFICATION_RUN"] == "1"
    assert all("gpu" not in key.lower() for key in test_step["env"])


def test_final_journey_has_a_pinned_cpu_execution_home() -> None:
    workflow = yaml.load(WORKFLOW.read_text(), Loader=yaml.BaseLoader)
    steps = workflow["jobs"]["source"]["steps"]
    assert "agent/backend-bounded-completion-2026-09-22" in workflow["on"]["push"]["branches"]
    journey = next(step for step in steps if step.get("name") == "Verify final composed journey")
    assert "backend/tests/test_audit_v3_final_journey.py" in journey["run"]
    assert "--junitxml=.c05-evidence/v3t50.xml" in journey["run"]
    assert journey["env"]["C05_TRACKEVAL_ROOT"] == "${{ github.workspace }}/.deps/trackeval"
    assert journey["env"]["VERIFY_DAYTONA"] == journey["env"]["ALLOW_DAYTONA_MUTATION"] == "0"
    assert 'test "$(git -C "$C05_TRACKEVAL_ROOT" rev-parse HEAD)"' in journey["run"]
    assert TRACKEVAL_COMMIT in journey["run"]
    media_setup = next(i for i, step in enumerate(steps) if "apt-get install -y ffmpeg" in step.get("run", ""))
    assert media_setup < steps.index(journey)
    capture = next(step for step in steps if step.get("name") == "Retain per-invocation evidence")
    assert capture["if"] == "always()"
    assert ".verification/pytest-runs" in capture["run"]
