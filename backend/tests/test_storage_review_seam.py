from pathlib import Path


STORAGE = Path(__file__).resolve().parents[1] / "app/storage.py"
REVIEW_STORAGE = Path(__file__).resolve().parents[1] / "app/storage_review.py"


def test_storage_review_persistence_is_behind_storage_facade() -> None:
    storage = STORAGE.read_text(encoding="utf-8")
    review = REVIEW_STORAGE.read_text(encoding="utf-8")

    assert "self._review_storage = ReviewStorage(" in storage
    assert "return self._review_storage.list_review_bundles(tags)" in storage
    assert "self._review_storage.delete_review_bundle(bundle_id)" in storage
    assert "os.replace(bundle_path, tombstone)" not in storage
    assert "os.replace(bundle_path, tombstone)" in review
    assert "os.fsync(directory_fd)" in review
    assert "outcome is uncertain; inspect before retrying" in review
