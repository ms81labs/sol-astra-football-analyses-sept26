"""Supplemental source-only review; never a behavioral or CI acceptance gate.

Example from a complete checkout (before applying the application patch):
  python docs/superpowers/handoffs/backend-quality/verification/verify_saved_report_store_extraction.py \
    --source backend/app/report_store.py

Only a temporary fixture is modified. No workflow, repository source, dependency,
provider, GPU, or live store is changed. Python 3.11+ and Git are sufficient.
"""
from __future__ import annotations

import argparse
import ast
import copy
import hashlib
import json
import subprocess
import tempfile
from pathlib import Path

SOURCE_BLOB = "8c319d0eaa675e7c2e930662a77003ac5e2ea046"
CANDIDATE_BLOB = "7a0daca35bb0b13363421b334b7e618914160c74"
PATCH_SHA256 = "8ba72cfb2dde0ff31f5747e1e1688bf0fed1e134f52137c34dea7962ca31d651"
HELPERS = {
    "_validate_record_metadata", "_validate_deterministic_payload",
    "_narrative_draft_base", "_strip_claim_metadata", "_verified_candidates",
}


def git_blob(data: bytes) -> str:
    return hashlib.sha1(b"blob " + str(len(data)).encode() + b"\0" + data).hexdigest()


def function_body(node: ast.FunctionDef) -> list[ast.stmt]:
    body = copy.deepcopy(node.body)
    if (body and isinstance(body[0], ast.Expr)
            and isinstance(body[0].value, ast.Constant)
            and isinstance(body[0].value.value, str)):
        body = body[1:]
    if body and isinstance(body[-1], ast.Return):
        body = body[:-1]
    return body


class InlineSavedHelpers(ast.NodeTransformer):
    def __init__(self, functions: dict[str, ast.FunctionDef]):
        self.functions = functions

    def visit_Expr(self, node: ast.Expr):
        call = node.value
        if isinstance(call, ast.Call) and isinstance(call.func, ast.Name) and call.func.id in HELPERS:
            return function_body(self.functions[call.func.id])
        return self.generic_visit(node)

    def visit_Assign(self, node: ast.Assign):
        if isinstance(node.value, ast.Call):
            function = node.value.func
            name = function.id if isinstance(function, ast.Name) else function.attr if isinstance(function, ast.Attribute) else None
            if name in {"_narrative_draft_base", "_verified_candidates"}:
                return function_body(self.functions[name])
        return self.generic_visit(node)

    def visit_FunctionDef(self, node: ast.FunctionDef):
        if node.name in HELPERS:
            return None
        return self.generic_visit(node)


def verify(source: Path, patch: Path) -> dict:
    old_bytes = source.read_bytes()
    patch_bytes = patch.read_bytes()
    if git_blob(old_bytes) != SOURCE_BLOB:
        raise ValueError("Source changed: reconcile main; this proof only covers the recorded base blob")
    if hashlib.sha256(patch_bytes).hexdigest() != PATCH_SHA256:
        raise ValueError("Saved patch hash mismatch")
    with tempfile.TemporaryDirectory(prefix="report-store-source-review-") as directory:
        fixture = Path(directory)
        target = fixture / "backend/app/report_store.py"
        target.parent.mkdir(parents=True)
        target.write_bytes(old_bytes)
        subprocess.run(["git", "init", "-q", str(fixture)], check=True, capture_output=True)
        command = ["git", "-C", str(fixture), "apply", "--include=backend/app/report_store.py"]
        subprocess.run([*command, "--check", str(patch.resolve())], check=True, capture_output=True)
        subprocess.run([*command, str(patch.resolve())], check=True, capture_output=True)
        new_bytes = target.read_bytes()
    if git_blob(new_bytes) != CANDIDATE_BLOB:
        raise ValueError("Candidate application blob mismatch")
    old = ast.parse(old_bytes)
    new = ast.parse(new_bytes)
    functions = {node.name: node for node in new.body if isinstance(node, ast.FunctionDef)}
    store = next(node for node in new.body if isinstance(node, ast.ClassDef) and node.name == "ReportStore")
    functions.update({node.name: node for node in store.body if isinstance(node, ast.FunctionDef)})
    if not HELPERS <= functions.keys():
        raise ValueError("An expected extraction helper is missing")
    reconstructed = InlineSavedHelpers(functions).visit(copy.deepcopy(new))
    old_dump = ast.dump(old, include_attributes=False)
    if ast.dump(reconstructed, include_attributes=False) != old_dump:
        raise ValueError("Whole-module reconstruction differs from the original")
    mutated = copy.deepcopy(reconstructed)
    transaction = next(node for node in ast.walk(mutated) if isinstance(node, ast.Constant) and node.value == "BEGIN IMMEDIATE")
    transaction.value = "BEGIN"
    if ast.dump(mutated, include_attributes=False) == old_dump:
        raise ValueError("Negative control did not detect the transaction mutation")
    baseline_patch = patch_bytes.decode().split("diff --git a/backend/quality/ruff-baseline.json", 1)[1]
    added = [line for line in baseline_patch.splitlines() if line.startswith("+") and not line.startswith("+++")]
    removed = [json.loads(json.loads(line[1:].strip().removesuffix(",")))
               for line in baseline_patch.splitlines() if line.startswith("-    ")]
    expected = [("backend/app/report_store.py", name, "C901")
                for name in ("ReportStore.view", "_validate_narrative_payload", "validate_record")]
    if added or [tuple(row[:3]) for row in removed] != expected:
        raise ValueError("Unexpected baseline patch identity delta")
    return {
        "kind": "supplemental-source-only-review",
        "sourceBlob": SOURCE_BLOB, "candidateApplicationBlob": CANDIDATE_BLOB,
        "patchSha256": PATCH_SHA256,
        "sourceOnlyGitApplyCheckExit": 0, "sourceOnlyGitApplyExit": 0,
        "wholeModuleAstReconstruction": "equal after inlining all five extracted helpers",
        "transactionMutationDetected": True,
        "baselinePatchRemoved": removed, "baselinePatchAdded": 0,
        "fullBaselineBlobReconstruction": "not performed",
        "behavioralTestsRun": False, "pinnedQualityGatesRun": False,
        "applicationAccepted": False,
        "limitations": [
            "This is a one-file temporary fixture, not a complete source checkout.",
            "AST reconstruction is not proof over arbitrary custom objects, object lifetimes, or concurrent mutation.",
            "The runbook's behavioral, quality, full-project and new-SHA CI requirements still apply.",
        ],
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--patch", type=Path, default=Path(__file__).resolve().parent.parent / "unpublished/report-store-extraction.patch")
    args = parser.parse_args()
    print(json.dumps(verify(args.source, args.patch), indent=2))


if __name__ == "__main__":
    main()
