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
