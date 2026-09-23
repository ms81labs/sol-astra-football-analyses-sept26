"""Required full-suite evidence has a locked CPU home, without paid dispatch."""
from pathlib import Path

import yaml

ROOT = Path(__file__).parents[2]


def test_full_backend_lane_retains_actual_selection_and_results():
    workflow = yaml.load((ROOT / '.github/workflows/ci.yml').read_text(), Loader=yaml.BaseLoader)
    job = workflow['jobs'].get('complete-backend')
    assert job is not None, 'complete backend selection has no canonical execution home'
    assert job['runs-on'] == 'ubuntu-latest'
    step = next(s for s in job['steps'] if s.get('name') == 'Run complete CPU backend')
    assert 'python -m pytest -q -ra backend/tests' in step['run']
    assert '--junitxml=.verification/backend-all.xml' in step['run']
    assert 'GA_VERIFICATION_RUN' in step['env']
    assert step['env']['VERIFY_DAYTONA'] == step['env']['ALLOW_DAYTONA_MUTATION'] == '0'
    assert not any('secrets.' in str(value) for value in job.values())
    uploader = next(s for s in job['steps'] if s.get('uses', '').startswith('actions/upload-artifact'))
    assert uploader['if'] == 'always()'
    assert uploader['with']['include-hidden-files'] == 'true'
    assert uploader['with']['path'] == '.verification/'


def test_c06_evidence_is_run_before_and_after_authorized_integration():
    workflow = yaml.load((ROOT / '.github/workflows/c06-regressions.yml').read_text(), Loader=yaml.BaseLoader)
    assert workflow['on']['push']['branches'] == ['main']
    assert {'backend/**', 'pyproject.toml', '.github/workflows/c06-regressions.yml'} <= set(workflow['on']['push']['paths'])
    assert workflow['permissions'] == {'contents': 'read'}
