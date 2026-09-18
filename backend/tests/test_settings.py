from __future__ import annotations

import dataclasses
import json
import sys

import pytest

from backend.app.settings import ProcessingSettings, SettingsError
from backend.release.daytona_policy import DaytonaPolicy, load_daytona_policy


DAYTONA_ENV_KEYS = (
    "PROCESSING_BACKEND",
    "DAYTONA_API_KEY",
    "DAYTONA_POLICY_PATH",
    "MATCH_UPLOAD_MAX_BYTES",
    "TRUSTED_FRONTEND_ORIGINS",
    "GA_CLOUD_PROVIDER_ENABLED",
    "GA_PROVIDER_CALL_RESERVATION",
    "GA_PROVIDER_BUDGET_LIMIT",
)


@pytest.fixture(autouse=True)
def _clean_processing_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    for key in DAYTONA_ENV_KEYS:
        monkeypatch.delenv(key, raising=False)


def test_default_settings_are_local_and_do_not_load_daytona(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import backend.app.settings as module

    monkeypatch.setattr(
        module,
        "load_daytona_policy",
        lambda: (_ for _ in ()).throw(AssertionError("local mode loaded Daytona policy")),
    )
    before = set(sys.modules)
    settings = ProcessingSettings.from_env()
    assert settings.processing_backend == "local"
    assert settings.daytona_api_key is None
    assert settings.daytona_policy is None
    assert settings.max_upload_bytes == 8 * 1024**3
    assert settings.remote_enabled is False
    assert "daytona" not in set(sys.modules) - before


def test_upload_limit_loads_from_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("MATCH_UPLOAD_MAX_BYTES", "123456")

    assert ProcessingSettings.from_env().max_upload_bytes == 123456


def test_cloud_provider_requires_and_loads_meaningful_budget(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("GA_CLOUD_PROVIDER_ENABLED", "1")
    with pytest.raises(SettingsError, match="positive per-call reservation"):
        ProcessingSettings.from_env()

    monkeypatch.setenv("GA_PROVIDER_CALL_RESERVATION", "0.25")
    monkeypatch.setenv("GA_PROVIDER_BUDGET_LIMIT", "1")
    settings = ProcessingSettings.from_env()
    assert settings.provider_call_reservation == 0.25
    assert settings.provider_budget_limit == 1.0


def test_frontend_origins_default_and_canonical_environment(monkeypatch):
    assert ProcessingSettings.from_env().trusted_frontend_origins == (
        "http://localhost:5173", "http://127.0.0.1:5173", "http://[::1]:5173",
    )
    monkeypatch.setenv("TRUSTED_FRONTEND_ORIGINS", " HTTP://LOCALHOST:80,https://LOCALHOST:443,http://[::1]:5173,http://localhost ")
    assert ProcessingSettings.from_env().trusted_frontend_origins == (
        "http://localhost", "https://localhost", "http://[::1]:5173",
    )


@pytest.mark.parametrize("value", [
    "", " ", ",", "*", "null", "http://*.example", "ftp://localhost",
    "http://", "localhost:5173", "http://user:pass@localhost", "http://localhost/",
    "http://localhost/path", "http://localhost?", "http://localhost#", "http://localhost?x=1",
    "http://localhost#x", "http://localhost:bad", "http://localhost:65536",
    "http://localhost:", "http://local host", "http://local\thost", "http://localhost\\evil",
    "http://localhost,", "http://localhost,,https://localhost",
    "http://[::1]evil:5173", "http://[::1]evil", "http://localhost..",
])
def test_frontend_origins_reject_invalid_environment(monkeypatch, value):
    monkeypatch.setenv("TRUSTED_FRONTEND_ORIGINS", value)
    with pytest.raises(SettingsError, match="trusted_frontend_origins"):
        ProcessingSettings.from_env()


@pytest.mark.parametrize("origins", [(), ("*",), ("null",), ("http://localhost/",), "http://localhost", (None,)])
def test_direct_settings_reject_invalid_frontend_origins(origins):
    with pytest.raises(SettingsError, match="trusted_frontend_origins"):
        ProcessingSettings(trusted_frontend_origins=origins)


@pytest.mark.parametrize("value", ["", "0", "-1", "1.5", "many"])
def test_upload_limit_rejects_non_positive_or_non_integer_environment_values(
    monkeypatch: pytest.MonkeyPatch,
    value: str,
) -> None:
    monkeypatch.setenv("MATCH_UPLOAD_MAX_BYTES", value)

    with pytest.raises(SettingsError, match="MATCH_UPLOAD_MAX_BYTES"):
        ProcessingSettings.from_env()


def test_selected_daytona_loads_exact_policy(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("PROCESSING_BACKEND", "daytona")
    monkeypatch.setenv("DAYTONA_API_KEY", "host-only-secret")
    settings = ProcessingSettings.from_env()
    assert settings.processing_backend == "daytona"
    assert settings.daytona_api_key == "host-only-secret"
    assert isinstance(settings.daytona_policy, DaytonaPolicy)
    assert settings.remote_enabled is True


@pytest.mark.parametrize("backend", ["runpod", "DAYTONA", "Local", "", " daytona", "daytona "])
def test_from_env_rejects_unknown_empty_and_case_changed_backends(
    monkeypatch: pytest.MonkeyPatch,
    backend: str,
) -> None:
    monkeypatch.setenv("PROCESSING_BACKEND", backend)
    monkeypatch.setenv("DAYTONA_API_KEY", "never-disclose-me")
    with pytest.raises(SettingsError, match="PROCESSING_BACKEND") as caught:
        ProcessingSettings.from_env()
    assert "never-disclose-me" not in str(caught.value)


@pytest.mark.parametrize("key", [None, "", " ", "\t\r\n"])
def test_daytona_backend_requires_nonblank_key(
    monkeypatch: pytest.MonkeyPatch,
    key: str | None,
) -> None:
    monkeypatch.setenv("PROCESSING_BACKEND", "daytona")
    if key is None:
        monkeypatch.delenv("DAYTONA_API_KEY", raising=False)
    else:
        monkeypatch.setenv("DAYTONA_API_KEY", key)
    with pytest.raises(SettingsError, match="DAYTONA_API_KEY"):
        ProcessingSettings.from_env()


@pytest.mark.parametrize("backend", ["runpod", "DAYTONA", "", "local "])
def test_direct_settings_construction_validates_backend_at_runtime(backend: str) -> None:
    with pytest.raises(SettingsError, match="processing_backend"):
        ProcessingSettings(processing_backend=backend)  # type: ignore[arg-type]


def test_direct_daytona_construction_requires_key_and_policy() -> None:
    with pytest.raises(SettingsError, match="daytona_api_key"):
        ProcessingSettings(processing_backend="daytona")
    with pytest.raises(SettingsError, match="daytona_policy"):
        ProcessingSettings(processing_backend="daytona", daytona_api_key="secret")


def test_direct_local_construction_rejects_daytona_credentials_or_policy() -> None:
    policy = load_daytona_policy()
    with pytest.raises(SettingsError, match="local"):
        ProcessingSettings(processing_backend="local", daytona_api_key="secret")
    with pytest.raises(SettingsError, match="local"):
        ProcessingSettings(processing_backend="local", daytona_policy=policy)


def test_invalid_policy_is_wrapped_without_fallback(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import backend.app.settings as module

    sentinel = "key-must-not-leak-6103"
    monkeypatch.setenv("PROCESSING_BACKEND", "daytona")
    monkeypatch.setenv("DAYTONA_API_KEY", sentinel)
    monkeypatch.setattr(
        module,
        "load_daytona_policy",
        lambda: (_ for _ in ()).throw(module.DaytonaPolicyError("invalid policy")),
    )
    with pytest.raises(SettingsError, match="Daytona policy") as caught:
        ProcessingSettings.from_env()
    assert sentinel not in str(caught.value)


def test_hostile_large_integer_policy_is_wrapped_without_secret_leak(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path,
) -> None:
    import backend.release.daytona_policy as policy_module

    sentinel = "host-only-daytona-key-873120"
    hostile = ('{"cpu":' + ("9" * 5_000) + "}\n").encode("ascii")
    assert len(hostile) < 16_384
    monkeypatch.setenv("PROCESSING_BACKEND", "daytona")
    monkeypatch.setenv("DAYTONA_API_KEY", sentinel)
    monkeypatch.setattr(policy_module, "_RELEASE_DIR", tmp_path)
    monkeypatch.setattr(
        policy_module,
        "_POLICY_PATH",
        tmp_path / "daytona-v7.3.json",
    )
    policy_module._POLICY_PATH.write_bytes(hostile)

    with pytest.raises(SettingsError, match="Daytona policy") as caught:
        ProcessingSettings.from_env()

    assert len(str(caught.value)) < 256
    assert len(repr(caught.value)) < 256
    pending = [caught.value]
    seen: set[int] = set()
    while pending:
        error = pending.pop()
        if id(error) in seen:
            continue
        seen.add(id(error))
        rendered = f"{error!s} {error!r}"
        assert sentinel not in rendered
        pending.extend(
            nested
            for nested in (error.__cause__, error.__context__)
            if nested is not None
        )


def test_runpod_environment_is_inactive(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("RUNPOD_API_KEY", "legacy-secret")
    monkeypatch.setenv("RUNPOD_ENDPOINT_ID", "legacy-endpoint")
    settings = ProcessingSettings.from_env()
    assert settings.processing_backend == "local"
    assert all(not field.name.startswith("runpod_") for field in dataclasses.fields(settings))
    assert "legacy-secret" not in repr(settings)


def test_daytona_secret_is_excluded_from_repr_and_safe_serialization(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    secret = "daytona-host-secret-48812"
    monkeypatch.setenv("PROCESSING_BACKEND", "daytona")
    monkeypatch.setenv("DAYTONA_API_KEY", secret)
    settings = ProcessingSettings.from_env()
    assert secret not in repr(settings)
    safe = settings.to_safe_mapping()
    assert secret not in json.dumps(safe, sort_keys=True)
    assert "daytona_api_key" not in safe
    assert safe["processingBackend"] == "daytona"
    assert safe["remoteEnabled"] is True


def test_settings_are_frozen_and_slots_based(monkeypatch: pytest.MonkeyPatch) -> None:
    settings = ProcessingSettings.from_env()
    assert not hasattr(settings, "__dict__")
    with pytest.raises((AttributeError, dataclasses.FrozenInstanceError)):
        settings.processing_backend = "daytona"  # type: ignore[misc]
