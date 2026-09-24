"""C05 explicit, source-bound replay of the existing pilot tracking scorer.

Inventory is read-only. Only verify_evaluation_manifest executes the scorer, in a
fresh local process. Acceptance concerns the supplied predictions in the declared
namespace, not a claim that a model was run or that its training history is known.
"""
from __future__ import annotations

import argparse
from copy import deepcopy
import hashlib
import json
import math
import os
from pathlib import Path, PurePosixPath
import stat
import subprocess
import sys
import tempfile

from .perception_identity import canonical_digest
from .workbench.evaluation import EvaluationGate, PROTOCOL_VERSION, FROZEN_TASK_COUNT, REQUIRED_MINUTES, score_hota_idf1
from .pilot_labels import parse_unique_json, validate_label_payload
from .pilot_tracking import TRACKEVAL_COMMIT, evaluation_frame_ids

_JSON_LIMIT = 64 * 1024 * 1024
_SCOPE = "image_space_tracking"


def _gate(**updates):
    return EvaluationGate(status="unknown", protocolVersion=PROTOCOL_VERSION,
        completeTasks=None, requiredTasks=FROZEN_TASK_COUNT, completeMinutes=None,
        requiredMinutes=REQUIRED_MINUTES, lockedLabelsPresent=False, nativePredictionsPresent=False,
        teamDeclarationsPresent=False, replayable=False, accepted=False, reasonCodes=[]).model_copy(update=updates)


def _require(condition, code):
    if not condition:
        raise ValueError(code)


def _read_file(root, descriptor, *, parse=False):
    """Read below a pinned directory using openat/no-follow, then verify bytes."""
    _require(isinstance(descriptor, dict) and set(descriptor) == {"path", "sha256", "byteSize"}, "ARTIFACT_DESCRIPTOR_INVALID")
    name, expected, size = descriptor["path"], descriptor["sha256"], descriptor["byteSize"]
    _require(isinstance(name, str) and name and "\\" not in name and not PurePosixPath(name).is_absolute()
        and all(p not in {"", ".", ".."} for p in name.split("/")), "ARTIFACT_PATH_UNSAFE")
    _require(isinstance(expected, str) and len(expected) == 64 and set(expected) <= set("0123456789abcdef")
        and expected != "0" * 64 and type(size) is int and size >= 0, "ARTIFACT_DESCRIPTOR_INVALID")
    _require(not parse or size <= _JSON_LIMIT, "EVALUATION_JSON_TOO_LARGE")
    flags = os.O_RDONLY | os.O_NOFOLLOW | os.O_NONBLOCK
    directory = os.open(root, flags | os.O_DIRECTORY)
    try:
        parts = name.split("/")
        for part in parts[:-1]:
            child = os.open(part, flags | os.O_DIRECTORY, dir_fd=directory)
            os.close(directory)
            directory = child
        fd = os.open(parts[-1], flags, dir_fd=directory)
        with os.fdopen(fd, "rb") as handle:
            before = os.fstat(handle.fileno())
            _require(stat.S_ISREG(before.st_mode) and before.st_size == size, "ARTIFACT_SIZE_MISMATCH")
            digest = hashlib.sha256()
            data = []
            count = 0
            for chunk in iter(lambda: handle.read(1024 * 1024), b""):
                count += len(chunk)
                _require(count <= size, "ARTIFACT_CHANGED")
                digest.update(chunk)
                if parse:
                    data.append(chunk)
            after = os.fstat(handle.fileno())
            _require((before.st_size, before.st_mtime_ns, before.st_ctime_ns) ==
                     (after.st_size, after.st_mtime_ns, after.st_ctime_ns) and digest.hexdigest() == expected,
                     "ARTIFACT_DIGEST_MISMATCH")
        return parse_unique_json(b"".join(data)) if parse else None
    finally:
        os.close(directory)


def _load_inputs(path):
    path = Path(path)
    _require(not path.is_symlink() and path.stat().st_size <= 1024 * 1024, "EVALUATION_MANIFEST_INVALID")
    raw = path.read_bytes()
    manifest = parse_unique_json(raw)
    _require(isinstance(manifest, dict) and set(manifest) == {"schemaVersion", "scope", "namespace",
        "scorerCommit", "protocol", "checkpoint", "trainingSplit", "tasks"}, "EVALUATION_MANIFEST_INVALID")
    _require(manifest["schemaVersion"] == 2 and manifest["scope"] == _SCOPE
        and manifest["namespace"] in {"synthetic", "held_out"}
        and manifest["scorerCommit"] == TRACKEVAL_COMMIT, "EVALUATION_SCOPE_INVALID")
    root = path.parent
    protocol = _read_file(root, manifest["protocol"], parse=True)
    _require(isinstance(protocol, dict) and protocol.get("version") == 3
        and isinstance(protocol.get("evaluationFrames"), dict)
        and type(protocol["evaluationFrames"].get("targetFps")) is int
        and protocol["evaluationFrames"]["targetFps"] > 0, "SCORER_PROTOCOL_INVALID")
    _read_file(root, manifest["checkpoint"])
    split = _read_file(root, manifest["trainingSplit"], parse=True)
    _require(isinstance(split, dict) and set(split) == {"schemaVersion", "trainingSources", "validationSources"}
        and split["schemaVersion"] == 1, "TRAINING_SPLIT_INVALID")
    split_hashes = []
    for key in ("trainingSources", "validationSources"):
        _require(isinstance(split[key], list), "TRAINING_SPLIT_INVALID")
        hashes = set()
        for descriptor in split[key]:
            _read_file(root, descriptor)
            hashes.add(descriptor["sha256"])
        split_hashes.append(hashes)
    _require(not split_hashes[0] & split_hashes[1], "TRAIN_VALIDATION_OVERLAP")
    _require(isinstance(manifest["tasks"], list) and 0 < len(manifest["tasks"]) <= 1000, "EVALUATION_TASKS_INVALID")
    cases, ids, minutes = [], set(), 0.0
    for item in manifest["tasks"]:
        _require(isinstance(item, dict) and set(item) == {"task", "stratum", "source", "labels", "predictions", "predictionProvenance"}, "EVALUATION_TASK_INVALID")
        task = item["task"]
        _require(isinstance(task, dict) and isinstance(task.get("taskId"), str) and task["taskId"]
            and task["taskId"] not in ids and isinstance(item["stratum"], str) and item["stratum"], "TASK_SCOPE_INVALID")
        ids.add(task["taskId"])
        _read_file(root, item["source"])
        _require(task.get("videoSha256") == item["source"]["sha256"], "SOURCE_BINDING_MISMATCH")
        _require(item["source"]["sha256"] not in (split_hashes[0] | split_hashes[1]), "HELD_OUT_SPLIT_OVERLAP")
        for key in ("sourceStartFrame", "sourceEndFrameExclusive", "sourceWidth", "sourceHeight", "evaluationFrameCount", "evaluationFrameStep"):
            _require(type(task.get(key)) is int and task[key] >= 0, "TASK_FRAME_SCOPE_INVALID")
        _require(0 < task["sourceEndFrameExclusive"] - task["sourceStartFrame"] <= 10_000_000
            and 0 < task["evaluationFrameCount"] <= 1_000_000 and task["evaluationFrameStep"] > 0
            and task["sourceWidth"] > 0 and task["sourceHeight"] > 0
            and type(task.get("sourceFps")) in (int, float) and math.isfinite(task["sourceFps"])
            and task["sourceFps"] > 0, "TASK_FRAME_SCOPE_INVALID")
        evaluation_frame_ids(task, protocol)
        labels = _read_file(root, item["labels"], parse=True)
        denominators = validate_label_payload(task, labels)
        predictions = _read_file(root, item["predictions"], parse=True)
        _require(isinstance(predictions, list), "NATIVE_PREDICTIONS_INVALID")
        seen = set()
        for row in predictions:
            _require(isinstance(row, dict) and row.get("Entity_Type") in {"player", "my_team", "enemy", "home", "away", "referee", "ball"}, "NATIVE_PREDICTIONS_INVALID")
            _require(type(row.get("Frame_ID")) is int and task["sourceStartFrame"] <= row["Frame_ID"] < task["sourceEndFrameExclusive"]
                and type(row.get("Track_ID")) is int, "PREDICTION_FRAME_SCOPE_INVALID")
            bbox = [row.get(k) for k in ("Source_X1", "Source_Y1", "Source_X2", "Source_Y2")]
            _require(all(type(v) in (int, float) and math.isfinite(v) for v in bbox)
                and 0 <= bbox[0] < bbox[2] <= task["sourceWidth"] and 0 <= bbox[1] < bbox[3] <= task["sourceHeight"], "PREDICTION_COORDINATES_INVALID")
            key = (row["Frame_ID"], row["Track_ID"])
            _require(row["Track_ID"] < 0 or key not in seen, "DUPLICATE_TRACK_OBSERVATION")
            seen.add(key)
        provenance = _read_file(root, item["predictionProvenance"], parse=True)
        _require(isinstance(provenance, dict) and type(provenance.get("schemaVersion")) is int
            and provenance.get("handEdited") is False and provenance == dict(schemaVersion=1, kind="native_image_space_predictions",
            taskId=task["taskId"], sourceSha256=item["source"]["sha256"],
            predictionSha256=item["predictions"]["sha256"], checkpointSha256=manifest["checkpoint"]["sha256"],
            coordinates="source_pixels", namespace=manifest["namespace"], handEdited=False), "PREDICTION_PROVENANCE_MISMATCH")
        minutes += denominators["durationSeconds"] / 60
        cases.append({"task": task, "labels": labels, "predictions": predictions, "stratum": item["stratum"]})
    return manifest, {"protocol": protocol, "cases": cases}, hashlib.sha256(raw).hexdigest(), minutes


def inspect_evaluation_manifest(path):
    manifest, inputs, digest, minutes = _load_inputs(path)
    return _gate(status="prerequisites_ok", inventoryStatus="verified", completeTasks=len(inputs["cases"]),
        completeMinutes=minutes, lockedLabelsPresent=True, nativePredictionsPresent=True,
        teamDeclarationsPresent=True, scope=_SCOPE, namespace=manifest["namespace"],
        reasonCodes=["SCORER_NOT_EXECUTED"], executionEvidence={"manifestSha256": digest})


def _check_scorer(root):
    """Verify executed Python bytes, not just a checkout's advertised HEAD."""
    root = Path(root).resolve()
    def git(*args):
        result = subprocess.run(["git", "-C", str(root), *args], capture_output=True, check=True, timeout=20)
        return result.stdout
    _require(git("rev-parse", "HEAD").decode().strip() == TRACKEVAL_COMMIT, "SCORER_REVISION_MISMATCH")
    expected = {}
    for record in git("ls-tree", "-rz", TRACKEVAL_COMMIT, "trackeval").split(b"\0"):
        if not record:
            continue
        header, name = record.split(b"\t", 1)
        if name.endswith(b".py"):
            mode, kind, digest = header.split()
            _require(mode == b"100644" and kind == b"blob", "SCORER_SOURCE_INVALID")
            expected[name.decode()] = digest.decode()
    actual = {p.relative_to(root).as_posix() for p in (root / "trackeval").rglob("*.py")}
    _require(actual == set(expected), "SCORER_SOURCE_CHANGED")
    for name, digest in expected.items():
        path = root / name
        _require(not path.is_symlink() and path.resolve().is_relative_to(root), "SCORER_SOURCE_CHANGED")
        data = path.read_bytes()
        _require(hashlib.sha1(b"blob " + str(len(data)).encode() + b"\0" + data).hexdigest() == digest, "SCORER_SOURCE_CHANGED")
    return canonical_digest(expected)


def _replay(inputs, root):
    with tempfile.TemporaryDirectory(prefix="c05-scorer-") as temp:
        path = Path(temp) / "inputs.json"
        path.write_text(json.dumps(inputs, allow_nan=False))
        command = [sys.executable, "-m", "backend.app.evaluation_verifier", "--worker-input", str(path),
                   "--trackeval-root", str(Path(root).resolve())]
        result = subprocess.run(command, cwd=Path(__file__).parents[2], text=True, capture_output=True,
                                timeout=120, check=False)
        _require(result.returncode == 0, "SCORER_EXECUTION_FAILED")
        return parse_unique_json(result.stdout), {"command": command, "exitCode": result.returncode,
            "stdoutSha256": hashlib.sha256(result.stdout.encode()).hexdigest(),
            "inputSha256": hashlib.sha256(path.read_bytes()).hexdigest()}


def _accept(policy, manifest, inputs, scores, minutes):
    _require(isinstance(policy, dict) and set(policy) == {"policyId", "scope", "namespace", "protocolSha256",
        "checkpointSha256", "requiredTaskIds", "requiredStrata", "minimumMinutes", "minimumFramesPerTask", "metrics"}, "ACCEPTANCE_POLICY_INVALID")
    _require(isinstance(policy["policyId"], str) and policy["policyId"] and policy["scope"] == _SCOPE
        and policy["namespace"] == manifest["namespace"] and policy["protocolSha256"] == manifest["protocol"]["sha256"]
        and policy["checkpointSha256"] == manifest["checkpoint"]["sha256"], "ACCEPTANCE_POLICY_SCOPE_MISMATCH")
    for key in ("requiredTaskIds", "requiredStrata"):
        _require(isinstance(policy[key], list) and policy[key] and all(isinstance(v, str) and v for v in policy[key])
            and len(set(policy[key])) == len(policy[key]), "ACCEPTANCE_POLICY_INVALID")
    _require(type(policy["minimumMinutes"]) in (int, float) and math.isfinite(policy["minimumMinutes"]) and policy["minimumMinutes"] >= 0
        and type(policy["minimumFramesPerTask"]) is int and policy["minimumFramesPerTask"] > 0
        and isinstance(policy["metrics"], dict) and set(policy["metrics"]) == {"HOTA", "IDF1"}, "ACCEPTANCE_POLICY_INVALID")
    reasons = []
    if set(scores) != set(policy["requiredTaskIds"]) or not set(policy["requiredStrata"]) <= {v["stratum"] for v in inputs["cases"]}:
        reasons.append("REQUIRED_EVALUATION_COVERAGE_MISSING")
    if minutes < policy["minimumMinutes"] or any(v["task"]["evaluationFrameCount"] < policy["minimumFramesPerTask"] for v in inputs["cases"]):
        reasons.append("REQUIRED_EVALUATION_COVERAGE_MISSING")
    for metric, rule in policy["metrics"].items():
        _require(isinstance(rule, dict) and set(rule) == {"minimum", "units"} and rule["units"] in {"fraction", "percentage"}
            and type(rule["minimum"]) in (int, float) and math.isfinite(rule["minimum"])
            and 0 <= rule["minimum"] <= (1 if rule["units"] == "fraction" else 100), "ACCEPTANCE_POLICY_UNITS_INVALID")
        threshold = rule["minimum"] / (100 if rule["units"] == "percentage" else 1)
        if any(value[metric] < threshold for value in scores.values()):
            reasons.append("ACCEPTANCE_THRESHOLD_NOT_MET:" + metric)
    return sorted(set(reasons))


def verify_evaluation_manifest(path: Path, *, trackeval_root: Path, acceptance_policy: dict | None = None) -> EvaluationGate:
    """Explicit local scoring. policy is trusted operator input, not manifest data."""
    gate = _gate()
    try:
        manifest, inputs, digest, minutes = _load_inputs(path)
        gate = inspect_evaluation_manifest(path)
    except (OSError, ValueError, KeyError, TypeError, AttributeError) as exc:
        return gate.model_copy(update={"reasonCodes": ["EVALUATION_INPUTS_UNVERIFIED", str(exc)]})
    policy = deepcopy(acceptance_policy)
    try:
        scorer_digest = _check_scorer(trackeval_root)
        scores, execution = _replay(inputs, trackeval_root)
        _, _, after, _ = _load_inputs(path)
        _require(after == digest and _check_scorer(trackeval_root) == scorer_digest, "INPUT_CHANGED_DURING_SCORING")
    except (OSError, ValueError, KeyError, TypeError, subprocess.SubprocessError) as exc:
        return gate.model_copy(update={"executionStatus": "failed", "reasonCodes": ["SCORER_REPLAY_UNVERIFIED", str(exc)]})
    gate = gate.model_copy(update={"status": "executed", "executionStatus": "completed", "replayable": True,
        "scope": _SCOPE, "namespace": manifest["namespace"], "reasonCodes": [],
        "executionEvidence": {"manifestSha256": digest, "scorerCommit": TRACKEVAL_COMMIT,
            "scorerSourceSha256": scorer_digest, "scorerEntryPoint": "evaluate_football_analysis_pilot.evaluate_tracking",
            "checkpointSha256": manifest["checkpoint"]["sha256"], "protocolSha256": manifest["protocol"]["sha256"],
            **execution, "units": "fraction", "modelInferenceExecuted": False,
            "checkpointAssociation": "verified_declared_artifact_binding_not_inference_replay"}})
    if not isinstance(scores, dict) or set(scores) != {item["task"]["taskId"] for item in inputs["cases"]}:
        return gate.model_copy(update={"scoreStatus": "invalid", "reasonCodes": ["SCORER_OUTPUT_INVALID"]})
    for item in manifest["tasks"]:
        value = scores[item["task"]["taskId"]]
        checked = score_hota_idf1(label_space="image_space", hand_edited_summary=False,
            native_predictions_present=True, scorer_executed=True,
            hota=value.get("HOTA") if isinstance(value, dict) else None,
            idf1=value.get("IDF1") if isinstance(value, dict) else None, units="fraction",
            prediction_digest=item["predictions"]["sha256"], label_digest=item["labels"]["sha256"],
            scorer_version=TRACKEVAL_COMMIT, source_identity=item["source"]["sha256"])
        if not checked["scored"]:
            return gate.model_copy(update={"scoreStatus": "invalid", "reasonCodes": checked["reasonCodes"]})
    gate = gate.model_copy(update={"status": "scored", "scoreStatus": "valid", "scores": scores})
    if policy is None:
        return gate.model_copy(update={"reasonCodes": ["ACCEPTANCE_POLICY_MISSING"]})
    try:
        reasons = _accept(policy, manifest, inputs, scores, minutes)
    except (ValueError, KeyError, TypeError) as exc:
        return gate.model_copy(update={"reasonCodes": [str(exc)]})
    return gate.model_copy(update={"accepted": not reasons, "acceptanceStatus": "failed" if reasons else "passed",
        "acceptancePolicyIdentity": canonical_digest(policy), "requiredTasks": len(policy["requiredTaskIds"]),
        "requiredMinutes": float(policy["minimumMinutes"]), "reasonCodes": reasons})


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("manifest", type=Path, nargs="?")
    parser.add_argument("--trackeval-root", required=True, type=Path)
    parser.add_argument("--policy", type=Path, help="Explicit operator-approved policy; no default thresholds")
    parser.add_argument("--worker-input", type=Path, help=argparse.SUPPRESS)
    args = parser.parse_args()
    if args.worker_input:
        from .pilot_tracking import build_trackeval_sequence_data, evaluate_tracking
        _check_scorer(args.trackeval_root)
        inputs = parse_unique_json(args.worker_input.read_bytes())
        scores = {case["task"]["taskId"]: evaluate_tracking(build_trackeval_sequence_data(case["task"], case["labels"],
            case["predictions"], inputs["protocol"]), trackeval_root=args.trackeval_root) for case in inputs["cases"]}
        _check_scorer(args.trackeval_root)
        print(json.dumps(scores, allow_nan=False))
        return 0
    if not args.manifest:
        parser.error("manifest is required")
    policy = parse_unique_json(args.policy.read_bytes()) if args.policy else None
    gate = verify_evaluation_manifest(args.manifest, trackeval_root=args.trackeval_root, acceptance_policy=policy)
    print(gate.model_dump_json(indent=2))
    return 0 if gate.scoreStatus == "valid" and (args.policy is None or gate.accepted) else 1


if __name__ == "__main__":
    raise SystemExit(main())
