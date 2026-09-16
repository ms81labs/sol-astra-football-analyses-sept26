from __future__ import annotations

import ast
import inspect
import json
import re
from dataclasses import replace
from pathlib import Path

import pytest
from jsonschema import Draft202012Validator
from packaging.requirements import Requirement
from packaging.specifiers import SpecifierSet
from packaging.version import Version

from backend.release.daytona_policy import (
    DaytonaPolicy,
    DaytonaPolicyError,
    load_daytona_policy,
)


ROOT = Path(__file__).resolve().parents[2]
POLICY_PATH = ROOT / "backend/release/daytona-v7.3.json"
SCHEMA_PATH = ROOT / "backend/release/daytona_execution_schema.json"
RUNTIME_REQUIREMENTS_PATH = ROOT / "backend/requirements-runtime.txt"

EXPECTED_POLICY = {
    "schemaVersion": 1,
    "sdkVersion": "0.207.0",
    "image": "docker.io/pytorch/pytorch@sha256:417bd75df6365104c283ea4c1651fb3530d9eb5a4c2fafa51943cff2a94e6385",
    "target": "us",
    "cpu": 4,
    "memoryGiB": 8,
    "diskGiB": 10,
    "gpu": 1,
    "gpuTypes": ["RTX-PRO-6000", "H100"],
    "spot": False,
    "public": False,
    "ephemeral": True,
    "networkBlockAll": True,
    "ttlMinutes": 180,
    "createTimeoutSeconds": 600,
    "executionTimeoutSeconds": 9000,
    "transferTimeoutSeconds": 1800,
    "deleteTimeoutSeconds": 120,
    "cleanupAttempts": 3,
}


def _canonical_bytes(value: object) -> bytes:
    return (
        json.dumps(
            value,
            allow_nan=False,
            ensure_ascii=False,
            separators=(",", ":"),
            sort_keys=True,
        )
        + "\n"
    ).encode("utf-8")


def _hostile_large_integer_bytes() -> bytes:
    raw = ('{"cpu":' + ("9" * 5_000) + "}\n").encode("ascii")
    assert len(raw) < 16_384
    return raw


def _error_chain_text(error: BaseException) -> str:
    pending = [error]
    seen: set[int] = set()
    rendered: list[str] = []
    while pending:
        current = pending.pop()
        if id(current) in seen:
            continue
        seen.add(id(current))
        rendered.append(f"{current!s} {current!r}")
        pending.extend(
            nested
            for nested in (current.__cause__, current.__context__)
            if nested is not None
        )
    return " ".join(rendered)


def _mutate(field: str, value: object) -> dict[str, object]:
    return {**EXPECTED_POLICY, field: value}


def _load_schema() -> dict[str, object]:
    return json.loads(SCHEMA_PATH.read_text(encoding="utf-8"))


def test_committed_policy_is_exact_canonical_json_and_loads_frozen() -> None:
    raw = POLICY_PATH.read_bytes()
    assert raw == _canonical_bytes(EXPECTED_POLICY)
    policy = load_daytona_policy()
    assert isinstance(policy, DaytonaPolicy)
    assert policy.to_mapping() == EXPECTED_POLICY
    assert policy.gpu_types == ("RTX-PRO-6000", "H100")
    with pytest.raises((AttributeError, TypeError)):
        policy.gpu = 2  # type: ignore[misc]


def test_direct_policy_construction_and_dataclass_replace_remain_fail_closed() -> None:
    policy = load_daytona_policy()
    with pytest.raises(DaytonaPolicyError, match="gpu"):
        replace(policy, gpu=2)
    with pytest.raises(DaytonaPolicyError, match="cpu"):
        replace(policy, cpu=True)
    with pytest.raises(DaytonaPolicyError, match="gpuTypes"):
        replace(policy, gpu_types=("H100", "RTX-PRO-6000"))


@pytest.mark.parametrize(
    ("mapping", "match"),
    [
        ({key: value for key, value in EXPECTED_POLICY.items() if key != "gpu"}, "keys"),
        ({**EXPECTED_POLICY, "unexpected": True}, "keys"),
        (_mutate("gpu", 2), "gpu"),
        (_mutate("gpuTypes", ["H100", "RTX-PRO-6000"]), "gpuTypes"),
        (_mutate("gpuTypes", ["RTX-PRO-6000", "RTX-PRO-6000"]), "gpuTypes"),
        (_mutate("spot", True), "spot"),
        (_mutate("public", True), "public"),
        (_mutate("ephemeral", False), "ephemeral"),
        (_mutate("networkBlockAll", False), "networkBlockAll"),
        (_mutate("target", "eu"), "target"),
        (_mutate("cpu", 5), "cpu"),
        (_mutate("memoryGiB", 9), "memoryGiB"),
        (_mutate("diskGiB", 11), "diskGiB"),
        (_mutate("ttlMinutes", 181), "ttlMinutes"),
        (_mutate("createTimeoutSeconds", 601), "createTimeoutSeconds"),
        (_mutate("executionTimeoutSeconds", 9001), "executionTimeoutSeconds"),
        (_mutate("transferTimeoutSeconds", 1801), "transferTimeoutSeconds"),
        (_mutate("deleteTimeoutSeconds", 121), "deleteTimeoutSeconds"),
        (_mutate("cleanupAttempts", 4), "cleanupAttempts"),
    ],
)
def test_validator_rejects_policy_mutations(mapping: dict[str, object], match: str) -> None:
    with pytest.raises(DaytonaPolicyError, match=match):
        DaytonaPolicy.from_mapping(mapping)


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("schemaVersion", True),
        ("schemaVersion", 1.0),
        ("schemaVersion", 0),
        ("cpu", True),
        ("cpu", 4.0),
        ("cpu", 0),
        ("memoryGiB", -8),
        ("diskGiB", 10.0),
        ("gpu", True),
        ("ttlMinutes", 0),
        ("ttlMinutes", -1),
        ("ttlMinutes", True),
        ("ttlMinutes", 45.0),
        ("createTimeoutSeconds", 0),
        ("executionTimeoutSeconds", -1),
        ("transferTimeoutSeconds", True),
        ("deleteTimeoutSeconds", 120.0),
        ("cleanupAttempts", 0),
        ("cleanupAttempts", -1),
        ("cleanupAttempts", True),
        ("cleanupAttempts", 3.0),
    ],
)
def test_validator_rejects_type_hostile_and_unbounded_numbers(field: str, value: object) -> None:
    with pytest.raises(DaytonaPolicyError, match=field):
        DaytonaPolicy.from_mapping(_mutate(field, value))


@pytest.mark.parametrize(
    "image",
    [
        "pytorch/pytorch:2.8.0-cuda12.8-cudnn9-runtime",
        "pytorch/pytorch@sha256:417bd75df6365104c283ea4c1651fb3530d9eb5a4c2fafa51943cff2a94e6385",
        "docker.io/pytorch/pytorch@sha256:short",
        "docker.io/pytorch/pytorch@sha256:417BD75DF6365104C283EA4C1651FB3530D9EB5A4C2FAFA51943CFF2A94E6385",
        "docker.io/pytorch/pytorch@SHA256:417bd75df6365104c283ea4c1651fb3530d9eb5a4c2fafa51943cff2a94e6385",
        "docker.io/pytorch/pytorch:latest@sha256:417bd75df6365104c283ea4c1651fb3530d9eb5a4c2fafa51943cff2a94e6385",
    ],
)
def test_validator_requires_exact_registry_and_lowercase_immutable_digest(image: str) -> None:
    with pytest.raises(DaytonaPolicyError, match="image"):
        DaytonaPolicy.from_mapping(_mutate("image", image))


class _HostileMapping(dict[str, object]):
    pass


class _HostileInt(int):
    pass


class _HostileStr(str):
    pass


def test_validator_rejects_mapping_and_scalar_subclasses() -> None:
    with pytest.raises(DaytonaPolicyError, match="plain JSON object"):
        DaytonaPolicy.from_mapping(_HostileMapping(EXPECTED_POLICY))
    with pytest.raises(DaytonaPolicyError, match="cpu"):
        DaytonaPolicy.from_mapping(_mutate("cpu", _HostileInt(4)))
    with pytest.raises(DaytonaPolicyError, match="target"):
        DaytonaPolicy.from_mapping(_mutate("target", _HostileStr("us")))


def test_validator_rejects_non_plain_gpu_type_collection_and_items() -> None:
    with pytest.raises(DaytonaPolicyError, match="gpuTypes"):
        DaytonaPolicy.from_mapping(_mutate("gpuTypes", ("RTX-PRO-6000", "H100")))
    with pytest.raises(DaytonaPolicyError, match="gpuTypes"):
        DaytonaPolicy.from_mapping(
            _mutate("gpuTypes", [_HostileStr("RTX-PRO-6000"), "H100"])
        )


def test_policy_loader_has_no_path_override_and_ignores_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    assert list(inspect.signature(load_daytona_policy).parameters) == []
    monkeypatch.setenv("DAYTONA_POLICY_PATH", "../../attacker-policy.json")
    assert load_daytona_policy().to_mapping() == EXPECTED_POLICY


def test_policy_loader_rejects_duplicate_keys_and_noncanonical_bytes(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    import backend.release.daytona_policy as module

    duplicate = _canonical_bytes(EXPECTED_POLICY).replace(
        b'"gpu":1,', b'"gpu":1,"gpu":1,', 1
    )
    monkeypatch.setattr(module, "_RELEASE_DIR", tmp_path)
    monkeypatch.setattr(module, "_POLICY_PATH", tmp_path / "daytona-v7.3.json")
    module._POLICY_PATH.write_bytes(duplicate)
    with pytest.raises(DaytonaPolicyError, match="duplicate"):
        load_daytona_policy()

    noncanonical_path = tmp_path / "daytona-v7.3.json"
    noncanonical_path.write_text(json.dumps(EXPECTED_POLICY, indent=2), encoding="utf-8")
    monkeypatch.setattr(module, "_POLICY_PATH", noncanonical_path)
    with pytest.raises(DaytonaPolicyError, match="canonical"):
        load_daytona_policy()


def test_policy_decoder_normalizes_python_integer_digit_limit_failure() -> None:
    import backend.release.daytona_policy as module

    hostile = _hostile_large_integer_bytes()
    with pytest.raises(DaytonaPolicyError, match="valid JSON") as caught:
        module._decode_policy(hostile)
    rendered = _error_chain_text(caught.value)
    assert len(rendered) < 256
    assert "Exceeds the limit" not in rendered
    assert "9" * 100 not in rendered


def test_public_policy_loader_normalizes_python_integer_digit_limit_failure(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    import backend.release.daytona_policy as module

    monkeypatch.setattr(module, "_RELEASE_DIR", tmp_path)
    monkeypatch.setattr(module, "_POLICY_PATH", tmp_path / "daytona-v7.3.json")
    module._POLICY_PATH.write_bytes(_hostile_large_integer_bytes())
    with pytest.raises(DaytonaPolicyError, match="valid JSON") as caught:
        load_daytona_policy()
    rendered = _error_chain_text(caught.value)
    assert len(rendered) < 256
    assert "Exceeds the limit" not in rendered
    assert "9" * 100 not in rendered


def test_committed_policy_path_is_not_a_symlink(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    import backend.release.daytona_policy as module

    target = tmp_path / "target.json"
    target.write_bytes(_canonical_bytes(EXPECTED_POLICY))
    link = tmp_path / "daytona-v7.3.json"
    link.symlink_to(target)
    monkeypatch.setattr(module, "_RELEASE_DIR", tmp_path)
    monkeypatch.setattr(module, "_POLICY_PATH", link)
    with pytest.raises(DaytonaPolicyError, match="regular file"):
        load_daytona_policy()


def test_committed_policy_path_cannot_traverse_outside_release_directory(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    import backend.release.daytona_policy as module

    outside = tmp_path / "outside" / "daytona-v7.3.json"
    outside.parent.mkdir()
    outside.write_bytes(_canonical_bytes(EXPECTED_POLICY))
    monkeypatch.setattr(module, "_POLICY_PATH", outside)
    with pytest.raises(DaytonaPolicyError, match="committed policy path"):
        load_daytona_policy()


def test_schema_is_draft_2020_12_valid_and_accepts_exact_policy() -> None:
    schema = _load_schema()
    assert schema["$schema"] == "https://json-schema.org/draft/2020-12/schema"
    Draft202012Validator.check_schema(schema)
    errors = list(Draft202012Validator(schema).iter_errors(EXPECTED_POLICY))
    assert errors == []


def test_schema_has_exact_closed_contract_and_digest_pattern() -> None:
    schema = _load_schema()
    assert schema["type"] == "object"
    assert schema["additionalProperties"] is False
    assert set(schema["required"]) == set(EXPECTED_POLICY)
    assert set(schema["properties"]) == set(EXPECTED_POLICY)
    image_schema = schema["properties"]["image"]
    assert image_schema["const"] == EXPECTED_POLICY["image"]
    assert re.fullmatch(image_schema["pattern"], EXPECTED_POLICY["image"])


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("gpu", 2),
        ("gpuTypes", ["H100", "RTX-PRO-6000"]),
        ("spot", True),
        ("public", True),
        ("ephemeral", False),
        ("networkBlockAll", False),
        ("cpu", 5),
        ("ttlMinutes", 0),
        ("ttlMinutes", 46),
        ("cleanupAttempts", True),
        ("image", "docker.io/pytorch/pytorch:latest"),
    ],
)
def test_schema_and_python_validator_both_reject_adversarial_mutations(
    field: str,
    value: object,
) -> None:
    mapping = _mutate(field, value)
    assert list(Draft202012Validator(_load_schema()).iter_errors(mapping))
    with pytest.raises(DaytonaPolicyError):
        DaytonaPolicy.from_mapping(mapping)


def test_schema_and_python_validator_reject_missing_and_extra_keys() -> None:
    schema_validator = Draft202012Validator(_load_schema())
    missing = {key: value for key, value in EXPECTED_POLICY.items() if key != "target"}
    extra = {**EXPECTED_POLICY, "extra": "unsafe"}
    for mapping in (missing, extra):
        assert list(schema_validator.iter_errors(mapping))
        with pytest.raises(DaytonaPolicyError):
            DaytonaPolicy.from_mapping(mapping)


def test_integral_float_requires_python_validation_beyond_json_schema() -> None:
    mapping = _mutate("cpu", 4.0)
    assert list(Draft202012Validator(_load_schema()).iter_errors(mapping)) == []
    with pytest.raises(DaytonaPolicyError, match="cpu"):
        DaytonaPolicy.from_mapping(mapping)


@pytest.mark.parametrize(
    "relative_path",
    ["backend/app/settings.py", "backend/release/daytona_policy.py"],
)
def test_configuration_modules_do_not_import_daytona_sdk_root(relative_path: str) -> None:
    source = (ROOT / relative_path).read_text(encoding="utf-8")
    tree = ast.parse(source, filename=relative_path)
    imported_roots = {
        alias.name.split(".", 1)[0]
        for node in ast.walk(tree)
        if isinstance(node, ast.Import)
        for alias in node.names
    }
    imported_roots.update(
        node.module.split(".", 1)[0]
        for node in ast.walk(tree)
        if isinstance(node, ast.ImportFrom) and node.module is not None
    )
    assert "daytona" not in imported_roots


def test_runtime_requirement_pin_matches_policy_and_has_no_runpod_sdk() -> None:
    requirements = RUNTIME_REQUIREMENTS_PATH.read_text(encoding="utf-8").splitlines()
    assert requirements.count(f"daytona=={EXPECTED_POLICY['sdkVersion']}") == 1
    assert all("runpod" not in line.casefold() for line in requirements)


def test_runtime_multipart_pin_satisfies_daytona_sdk_metadata_constraint() -> None:
    direct_requirements = {
        Requirement(line).name: Requirement(line)
        for line in RUNTIME_REQUIREMENTS_PATH.read_text(encoding="utf-8").splitlines()
        if line and not line.startswith("#")
    }
    multipart = direct_requirements["python-multipart"]
    assert str(multipart.specifier) == "==0.0.32"
    assert Version("0.0.32") in SpecifierSet(">=0.0.31,<0.1.0")
    pydantic = direct_requirements["pydantic"]
    assert str(pydantic.specifier) == "==2.13.5"
    assert Version("2.13.5") in SpecifierSet(">=2.13.4,<3.0.0")


def test_policy_errors_and_serialization_are_secret_free() -> None:
    secret = "daytona-secret-sentinel-9417"
    mapping = _mutate("target", secret)
    with pytest.raises(DaytonaPolicyError) as caught:
        DaytonaPolicy.from_mapping(mapping)
    assert secret not in str(caught.value)
    valid = load_daytona_policy()
    assert secret not in repr(valid)
    assert secret not in json.dumps(valid.to_mapping(), sort_keys=True)
