"""C05 final-review counterexamples; synthetic data and the real existing scorer."""
from copy import deepcopy
import json
from pathlib import Path
import subprocess
import sys

import pytest
from backend.tests.test_audit_v3_c05_evaluation import fixture, policy, scorer_root as scorer_root

pytestmark = pytest.mark.integration


def test_malformed_nested_labels_are_unverified_inventory_not_a_server_error(tmp_path):
    from backend.app.workbench.evaluation import current_repository_evaluation_gate
    path, manifest, save = fixture(tmp_path / 'case')
    labels = json.loads((path.parent / 'labels.json').read_text())
    labels['frames'][0] = None
    manifest['tasks'][0]['labels'] = save('labels.json', labels)
    path.write_text(json.dumps(manifest))
    gate = current_repository_evaluation_gate(manifest_path=path)
    assert gate.inventoryStatus == 'incomplete' and gate.executionStatus == 'not_run'
    assert gate.accepted is False


def test_explicit_invalid_policy_cli_is_not_a_success_exit(tmp_path, scorer_root):
    path, manifest, _ = fixture(tmp_path / 'case')
    p = policy(manifest)
    p['metrics']['HOTA']['units'] = 'guess'
    policy_path = path.parent / 'policy.json'
    policy_path.write_text(json.dumps(p))
    result = subprocess.run([sys.executable, '-m', 'backend.app.evaluation_verifier', str(path),
        '--trackeval-root', str(scorer_root), '--policy', str(policy_path)],
        cwd=Path(__file__).parents[2], capture_output=True, text=True, timeout=30)
    gate = json.loads(result.stdout)
    assert gate['scoreStatus'] == 'valid' and gate['accepted'] is False
    assert result.returncode != 0


def test_executed_scorer_retains_actual_command_and_output_hash(tmp_path, scorer_root):
    from backend.app.evaluation_verifier import verify_evaluation_manifest
    path, _, _ = fixture(tmp_path / 'case')
    gate = verify_evaluation_manifest(path, trackeval_root=scorer_root)
    evidence = gate.executionEvidence
    assert gate.scoreStatus == 'valid'
    assert evidence['command'][:3] == [sys.executable, '-m', 'backend.app.evaluation_verifier']
    assert '--worker-input' in evidence['command'] and evidence['exitCode'] == 0
    assert len(evidence['stdoutSha256']) == 64 and len(evidence['inputSha256']) == 64


def test_dirty_scorer_source_is_refused_without_executing(tmp_path, scorer_root):
    from backend.app.evaluation_verifier import verify_evaluation_manifest
    path, _, _ = fixture(tmp_path / 'case')
    copy = tmp_path / 'scorer'
    subprocess.run(['git', 'clone', '--quiet', '--shared', str(scorer_root), str(copy)], check=True)
    (copy / 'trackeval' / 'metrics' / 'hota.py').write_text("raise AssertionError('must not execute')\n")
    gate = verify_evaluation_manifest(path, trackeval_root=copy)
    assert not gate.accepted and gate.executionStatus == 'failed'
    assert 'SCORER_SOURCE_CHANGED' in gate.reasonCodes


def test_changed_artifact_after_real_replay_cannot_be_accepted(tmp_path, scorer_root, monkeypatch):
    from backend.app import evaluation_verifier as verifier
    path, manifest, _ = fixture(tmp_path / 'case')
    replay = verifier._replay
    def mutate(*args):
        result = replay(*args)
        (path.parent / 'predictions.json').write_bytes(b'changed')
        return result
    monkeypatch.setattr(verifier, '_replay', mutate)
    gate = verifier.verify_evaluation_manifest(path, trackeval_root=scorer_root, acceptance_policy=policy(manifest))
    assert gate.accepted is False and gate.executionStatus == 'failed'
    assert gate.scoreStatus == 'unavailable'


def test_favourable_pooled_mean_does_not_hide_one_failed_stratum(tmp_path, scorer_root):
    from backend.app.evaluation_verifier import verify_evaluation_manifest
    path, manifest, save = fixture(tmp_path / 'case')
    task = deepcopy(manifest['tasks'][0])
    task['task']['taskId'] = 't2'
    task['stratum'] = 'closeup'
    labels = json.loads((path.parent / 'labels.json').read_text())
    labels['taskId'] = 't2'
    task['labels'] = save('labels2.json', labels)
    task['predictions'] = save('predictions2.json', [])
    provenance = json.loads((path.parent / 'prediction-provenance.json').read_text())
    provenance.update(taskId='t2', predictionSha256=task['predictions']['sha256'])
    task['predictionProvenance'] = save('provenance2.json', provenance)
    manifest['tasks'].append(task)
    path.write_text(json.dumps(manifest))
    p = policy(manifest)
    p.update(requiredTaskIds=['t1', 't2'], requiredStrata=['wide', 'closeup'])
    gate = verify_evaluation_manifest(path, trackeval_root=scorer_root, acceptance_policy=p)
    assert gate.scoreStatus == 'valid'
    assert sum(value['HOTA'] for value in gate.scores.values()) / 2 == .5
    assert gate.acceptanceStatus == 'failed' and gate.accepted is False
    assert 'ACCEPTANCE_THRESHOLD_NOT_MET:HOTA' in gate.reasonCodes
