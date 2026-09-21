from backend.app.storage import (
    AdmissionOutcomeUncertainError,
    JobCancellationRequested,
    Storage,
)
from backend.app.storage_jobs import (
    AdmissionOutcomeUncertainError as JobsAdmissionOutcomeUncertainError,
    JobCancellationRequested as JobsJobCancellationRequested,
    _JobStorageMixin,
)


def test_storage_keeps_job_persistence_behind_facade() -> None:
    assert issubclass(Storage, _JobStorageMixin)
    for name in (
        "ensure_job",
        "admit_match_job",
        "update_job",
        "get_job",
    ):
        assert name in _JobStorageMixin.__dict__
        assert name not in Storage.__dict__


def test_storage_reexports_job_exceptions() -> None:
    assert AdmissionOutcomeUncertainError is JobsAdmissionOutcomeUncertainError
    assert JobCancellationRequested is JobsJobCancellationRequested
