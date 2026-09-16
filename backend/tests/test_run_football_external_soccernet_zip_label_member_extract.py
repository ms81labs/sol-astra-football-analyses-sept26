from __future__ import annotations

import json
from pathlib import Path
import sys

import backend.scripts.run_football_external_soccernet_zip_label_member_extract as extract


def _write_json(path: Path, payload: dict[str, object]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def _write_short_stream_pyzipper_shim(root: Path) -> None:
    root.mkdir(parents=True, exist_ok=True)
    (root / "pyzipper.py").write_text(
        """
import io

class _Info:
    file_size = 4

class AESZipFile:
    def __init__(self, _path):
        self.pwd = None
    def __enter__(self):
        return self
    def __exit__(self, *_args):
        return False
    def getinfo(self, _member):
        return _Info()
    def open(self, _member):
        return io.BytesIO(b'abc')
""",
        encoding="utf-8",
    )


def _write_extract_inputs(tmp_path: Path, *, approval_goal: bool = True) -> Path:
    candidate_root = tmp_path / "trained_detector_candidates" / "touchline_detector_candidate_v7"
    approval_root = candidate_root / "football_external_soccernet_zip_label_member_extract_approval_v1"
    range_root = candidate_root / "football_external_soccernet_split_archive_range_index_probe_v1"
    label_path = "england_efl/2019-2020/game/Labels-ball.json"
    _write_json(
        approval_root / "zip_label_member_extract_approval_summary.json",
        {
            "batchName": "football_external_soccernet_zip_label_member_extract_approval",
            "goalAchieved": approval_goal,
            "primaryBlocker": None if approval_goal else "football_external_soccernet_zip_label_member_range_index_missing",
            "labelMemberExtractionApproved": approval_goal,
            "approvedLabelMemberCount": 1 if approval_goal else 0,
            "credentialRequired": True,
            "credentialPersisted": False,
            "fullArchiveDownloadApproved": False,
            "archiveDownloadExecuted": False,
            "videoMemberDownloadAllowed": False,
            "videoMemberDownloadExecuted": False,
            "trainingExecuted": False,
            "nextRecommendedNextLever": "football_external_soccernet_zip_label_member_extract",
        },
    )
    _write_json(
        approval_root / "zip_label_member_extract_contract.json",
        {
            "contractName": "football_external_soccernet_zip_label_member_extract",
            "sourceBatch": "football_external_soccernet_zip_label_member_extract_approval",
            "selectedArchiveTask": "spotting-ball-2025",
            "selectedArchivePath": "valid.zip",
            "labelMemberExtractionApproved": True,
            "labelMemberRangeExtractionOnly": True,
            "approvedLabelMemberCount": 1,
            "labelMembers": [
                {
                    "path": label_path,
                    "isDirectory": False,
                    "compressionMethod": 99,
                    "compressedSizeBytes": 12880,
                    "uncompressedSizeBytes": 312333,
                    "localHeaderOffset": 2042217249,
                }
            ],
            "credentialRequired": True,
            "credentialEnvVar": "SOCCERNET_PASSWORD",
            "credentialPersisted": False,
            "fullArchiveDownloadApproved": False,
            "videoMemberDownloadAllowed": False,
            "trainingUseAllowed": False,
        },
    )
    _write_json(
        range_root / "zip_central_directory_audit.json",
        {
            "archiveSizeBytes": 2042230928,
            "centralDirectoryOffset": 2042230255,
            "centralDirectorySizeBytes": 651,
            "zipCentralDirectoryParsed": True,
            "zipEntries": [
                {"path": label_path, "localHeaderOffset": 2042217249, "compressedSizeBytes": 12880, "compressionMethod": 99, "isDirectory": False}
            ],
        },
    )
    return candidate_root


def test_zip_label_member_extract_writes_label_file_from_injected_payload(tmp_path: Path) -> None:
    candidate_root = _write_extract_inputs(tmp_path)
    label_path = "england_efl/2019-2020/game/Labels-ball.json"

    payload = extract.run_football_external_soccernet_zip_label_member_extract(
        storage_root=tmp_path,
        label_member_payloads={label_path: b'{"annotations":[{"gameTime":"1 - 00:01"}]}'},
    )

    output_root = candidate_root / "football_external_soccernet_zip_label_member_extract_v1"
    inventory = json.loads((output_root / "extracted_label_inventory.json").read_text(encoding="utf-8"))
    schema = json.loads((output_root / "label_schema_preview_audit.json").read_text(encoding="utf-8"))

    assert payload["goalAchieved"] is True
    assert payload["primaryBlocker"] is None
    assert payload["downloadedLabelFileCount"] == 1
    assert payload["archiveDownloadExecuted"] is False
    assert payload["videoMemberDownloadExecuted"] is False
    assert payload["nextRecommendedNextLever"] == "football_external_soccernet_label_schema_ingestion_probe"
    assert inventory["extractedLabelFileCount"] == 1
    assert schema["jsonParseSucceeded"] is True
    assert schema["annotationCount"] == 1


def test_zip_label_member_extract_blocks_without_approval_truth(tmp_path: Path) -> None:
    _write_extract_inputs(tmp_path, approval_goal=False)

    payload = extract.run_football_external_soccernet_zip_label_member_extract(
        storage_root=tmp_path,
        label_member_payloads={},
    )

    assert payload["goalAchieved"] is False
    assert payload["primaryBlocker"] == "football_external_soccernet_zip_label_member_extract_approval_missing"
    assert payload["nextRecommendedNextLever"] == "football_external_soccernet_zip_label_member_extract_approval"
    assert payload["archiveDownloadExecuted"] is False


def test_zip_label_member_extract_blocks_without_runtime_credential_when_real_extract_needed(tmp_path: Path) -> None:
    _write_extract_inputs(tmp_path)

    payload = extract.run_football_external_soccernet_zip_label_member_extract(
        storage_root=tmp_path,
        env={},
    )

    assert payload["goalAchieved"] is False
    assert payload["primaryBlocker"] == "football_external_soccernet_zip_label_member_credential_missing"
    assert payload["nextRecommendedNextLever"] == "football_external_soccernet_secret_env_setup"
    assert payload["credentialPersisted"] is False


def test_zip_label_member_extract_contains_three_adaptive_attempts(tmp_path: Path) -> None:
    _write_extract_inputs(tmp_path)

    payload = extract.run_football_external_soccernet_zip_label_member_extract(
        storage_root=tmp_path,
        label_member_payloads={"england_efl/2019-2020/game/Labels-ball.json": b'{"annotations":[]}'},
    )

    assert payload["attemptPlanFamilies"] == [
        "soccernet_zip_label_member_range_extract",
        "soccernet_encrypted_label_member_extract_repair",
        "soccernet_label_member_extract_blocker_summary",
    ]


def test_zip_label_member_extract_rejects_short_stream(tmp_path: Path) -> None:
    shim = tmp_path / "shim"
    _write_short_stream_pyzipper_shim(shim)
    output_dir = tmp_path / "output"
    member = "game/Labels-ball.json"

    result = extract._extract_with_pyzipper(
        python_executable=sys.executable,
        sparse_zip_path=tmp_path / "unused.zip",
        member_paths=[member],
        expected_size_bytes_by_member={member: 4},
        output_dir=output_dir,
        env={"PYTHONPATH": str(shim), "SOCCERNET_PASSWORD": "runtime-only"},
        credential_env_var="SOCCERNET_PASSWORD",
    )

    assert result["returnCode"] != 0
    assert not (output_dir / member).exists()
