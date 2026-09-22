"""Spawn-safe entry: install no-model guards before importing journey helpers."""
from backend.tests.test_audit_v3_c01_generations import _child_setup


def guarded_journey_child(action, root, match_id, pipe):
    _child_setup()
    import pytest
    from backend.app import processor, remote_worker
    from backend.app.provider_gateway import ProviderGateway
    from backend.tests.test_audit_v3_c02_journey import _held_reader
    from backend.tests.test_audit_v3_c03_journey import _crashing_configuration
    from backend.tests.test_audit_v3_final_journey import _recover_twice, _fresh_state

    def forbidden(*args, **kwargs):
        raise AssertionError("unexpected child model/provider/Daytona dispatch")

    targets = {"held_reader": _held_reader, "crashing_writer": _crashing_configuration,
               "recover": _recover_twice, "state": _fresh_state}
    with pytest.MonkeyPatch.context() as patch:
        patch.setattr(processor, "process_video_input", forbidden)
        patch.setattr(remote_worker, "execute_daytona_job", forbidden)
        patch.setattr(ProviderGateway, "execute", forbidden)
        targets[action](root, match_id, pipe)
