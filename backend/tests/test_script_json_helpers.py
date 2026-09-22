from __future__ import annotations

import json
from pathlib import Path

import pytest

from backend.scripts.football_external_real_eval_chain_common import (
    load_json_dict_or_empty_existing,
    load_json_dict_or_empty_optional,
    load_json_dict_or_empty_required,
    load_json_object_at_strict,
    load_json_object_payload_strict,
    load_json_object_strict,
    write_json_sorted_no_newline,
    write_json_unsorted_newline,
    write_json_unsorted_no_newline,
)


def test_write_json_policy_variants_preserve_exact_bytes(tmp_path: Path) -> None:
    payload = {"b": 1, "a": 2}

    sorted_path = tmp_path / "sorted.json"
    write_json_sorted_no_newline(sorted_path, payload)
    assert sorted_path.read_text(encoding="utf-8") == json.dumps(payload, indent=2, sort_keys=True)

    unsorted_path = tmp_path / "unsorted.json"
    write_json_unsorted_no_newline(unsorted_path, payload)
    assert unsorted_path.read_text(encoding="utf-8") == json.dumps(payload, indent=2)

    newline_path = tmp_path / "newline.json"
    write_json_unsorted_newline(newline_path, payload)
    assert newline_path.read_text(encoding="utf-8") == json.dumps(payload, indent=2) + "\n"


def test_load_json_dict_or_empty_required_preserves_missing_and_non_object_behavior(tmp_path: Path) -> None:
    missing = tmp_path / "missing.json"
    with pytest.raises(FileNotFoundError) as exc_info:
        load_json_dict_or_empty_required(missing)
    assert exc_info.value.args == (str(missing),)

    missing_optional = load_json_dict_or_empty_required(missing, required=False)
    assert missing_optional == {}

    scalar = tmp_path / "scalar.json"
    scalar.write_text("[]", encoding="utf-8")
    assert load_json_dict_or_empty_required(scalar) == {}


def test_load_json_dict_or_empty_optional_preserves_path_exception_and_default(tmp_path: Path) -> None:
    missing = tmp_path / "missing.json"
    assert load_json_dict_or_empty_optional(missing) == {}

    with pytest.raises(FileNotFoundError) as exc_info:
        load_json_dict_or_empty_optional(missing, required=True)
    assert exc_info.value.args == (missing,)


def test_load_json_dict_or_empty_existing_requires_file_but_tolerates_non_object(tmp_path: Path) -> None:
    missing = tmp_path / "missing.json"
    with pytest.raises(FileNotFoundError):
        load_json_dict_or_empty_existing(missing)

    scalar = tmp_path / "scalar.json"
    scalar.write_text("[]", encoding="utf-8")
    assert load_json_dict_or_empty_existing(scalar) == {}


@pytest.mark.parametrize(
    ("loader", "expected_message"),
    [
        (load_json_object_payload_strict, "Expected object payload in"),
        (load_json_object_strict, "Expected JSON object in"),
        (load_json_object_at_strict, "Expected JSON object at"),
    ],
)
def test_strict_loaders_preserve_error_messages(tmp_path: Path, loader, expected_message: str) -> None:
    path = tmp_path / "scalar.json"
    path.write_text("[]", encoding="utf-8")

    with pytest.raises(ValueError, match=expected_message):
        loader(path)

    object_path = tmp_path / "object.json"
    object_path.write_text('{"ok": true}', encoding="utf-8")
    assert loader(object_path) == {"ok": True}
