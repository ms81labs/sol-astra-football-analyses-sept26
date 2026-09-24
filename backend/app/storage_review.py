"""Review bundle, annotation, and issue persistence implementation.

Storage remains the public compatibility facade. This component owns only the
review-oriented file persistence cluster and preserves the existing durable
delete semantics.
"""

from __future__ import annotations

import json
import os
import stat
import uuid
from contextlib import ExitStack, contextmanager
from datetime import datetime, timezone
from pathlib import Path
from typing import TYPE_CHECKING

from pydantic import ValidationError

from .schemas import (
    CreateAnnotationRequest,
    CreateIssueRequest,
    MatchIssueRecord,
    ReviewBundle,
    ReviewBundleItem,
    TacticalAnnotationRecord,
)

if TYPE_CHECKING:
    from .storage import Storage


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class ReviewStorage:
    def __init__(
        self,
        owner: "Storage",
        *,
        corrupt_error: type[RuntimeError],
        uncertain_delete_error: type[OSError],
    ) -> None:
        self._owner = owner
        self._corrupt_error = corrupt_error
        self._uncertain_delete_error = uncertain_delete_error

    def bundle_dir(self) -> Path:
        path = self._owner.storage_root / "bundles"
        path.mkdir(parents=True, exist_ok=True)
        return path

    def list_review_bundles(self, tags: list[str] | None = None) -> list[ReviewBundle]:
        with self._owner._review_bundle_lock:
            bundles = []
            for bundle_file in self.bundle_dir().glob("*.json"):
                try:
                    data = self._owner._read_json(bundle_file)
                    bundle = ReviewBundle.model_validate(data)
                except (json.JSONDecodeError, UnicodeDecodeError, ValidationError) as error:
                    raise self._corrupt_error(
                        f"review bundle {bundle_file.stem!r} is corrupt"
                    ) from error
                if tags and not any(tag in bundle.tags for tag in tags):
                    continue
                bundles.append(bundle)
        bundles.sort(key=lambda b: b.updatedAt, reverse=True)
        return bundles

    def get_review_bundle(self, bundle_id: str) -> ReviewBundle:
        bundle_path = self.bundle_dir() / f"{bundle_id}.json"
        if not bundle_path.exists():
            raise KeyError(bundle_id)
        return ReviewBundle.model_validate(self._owner._read_json(bundle_path))

    @contextmanager
    def bound_bundle_items(self, items):
        normalised = [ReviewBundleItem.model_validate(item) for item in items]
        with ExitStack() as pins:
            refs = {}
            for mid, gid in sorted(
                {(item.matchId, item.generationId) for item in normalised},
                key=lambda pair: (pair[0], pair[1] or ""),
            ):
                try:
                    self._owner.get_match(mid)
                    refs[mid, gid] = pins.enter_context(
                        self._owner.generation_snapshot(mid, generation_id=gid)
                    ).generationId
                except (KeyError, FileNotFoundError) as exc:
                    if gid is not None:
                        from .generations import GenerationRecoveryRequired

                        raise GenerationRecoveryRequired(
                            "Playlist source generation is unavailable"
                        ) from exc
                    refs[mid, gid] = None
            yield [
                item.model_copy(
                    update={
                        "generationId": refs[item.matchId, item.generationId],
                        "sourceStatus": (
                            "generation_bound"
                            if refs[item.matchId, item.generationId]
                            else "unverified"
                        ),
                    }
                )
                for item in normalised
            ]

    def create_review_bundle(
        self,
        name: str,
        description: str = "",
        items: list | None = None,
        tags: list[str] | None = None,
    ) -> ReviewBundle:
        with self.bound_bundle_items(items or []) as bound_items:
            bundle_id = uuid.uuid4().hex
            now = _utcnow().isoformat()
            bundle = ReviewBundle(
                id=bundle_id,
                name=name,
                description=description,
                items=bound_items,
                tags=tags or [],
                createdAt=now,
                updatedAt=now,
            )
            self._owner._write_json(
                self.bundle_dir() / f"{bundle_id}.json",
                bundle.model_dump(mode="json"),
            )
            return bundle

    def update_review_bundle(
        self,
        bundle_id: str,
        name: str | None = None,
        description: str | None = None,
        items: list | None = None,
        tags: list[str] | None = None,
    ) -> ReviewBundle:
        with self._owner._review_bundle_lock, self.bound_bundle_items(items or []) as bound_items:
            bundle = self.get_review_bundle(bundle_id)
            now = _utcnow().isoformat()
            if name is not None:
                bundle.name = name
            if description is not None:
                bundle.description = description
            if items is not None:
                bundle.items = bound_items
            if tags is not None:
                bundle.tags = tags
            bundle.updatedAt = now
            self._owner._write_json(
                self.bundle_dir() / f"{bundle_id}.json",
                bundle.model_dump(mode="json"),
            )
            return bundle

    def delete_review_bundle(self, bundle_id: str) -> None:
        with self._owner._review_bundle_lock:
            bundle_path = self.bundle_dir() / f"{bundle_id}.json"
            tombstone = bundle_path.with_name(
                f".{bundle_path.name}.{uuid.uuid4().hex}.deleted"
            )
            directory_fd = os.open(
                bundle_path.parent,
                os.O_RDONLY
                | getattr(os, "O_CLOEXEC", 0)
                | getattr(os, "O_DIRECTORY", 0),
            )
            renamed = committed = False
            try:
                try:
                    target = os.stat(bundle_path, follow_symlinks=False)
                except FileNotFoundError:
                    raise KeyError(bundle_id) from None
                if not stat.S_ISREG(target.st_mode):
                    raise OSError("review bundle is not a regular file")
                os.replace(bundle_path, tombstone)
                renamed = True
                os.fsync(directory_fd)
                committed = True
                try:
                    tombstone.unlink()
                    renamed = False
                    os.fsync(directory_fd)
                except OSError:
                    pass
            except BaseException as error:
                if renamed and not committed:
                    try:
                        os.replace(tombstone, bundle_path)
                        renamed = False
                        os.fsync(directory_fd)
                    except BaseException:
                        raise self._uncertain_delete_error(
                            "review bundle deletion outcome is uncertain; inspect before retrying"
                        ) from error
                raise
            finally:
                if committed and renamed:
                    try:
                        tombstone.unlink(missing_ok=True)
                    except OSError:
                        pass
                try:
                    os.close(directory_fd)
                except OSError:
                    pass

    def annotations_path(self, match_id: str) -> Path:
        self._owner.get_match(match_id)
        path = self._owner.storage_root / "matches" / match_id / "annotations.json"
        path.parent.mkdir(parents=True, exist_ok=True)
        return path

    def list_annotations(self, match_id: str) -> list[TacticalAnnotationRecord]:
        path = self.annotations_path(match_id)
        if not path.exists():
            return []
        data = self._owner._read_json(path)
        if not isinstance(data, list):
            raise TypeError("annotations must be a JSON array")
        return [TacticalAnnotationRecord.model_validate(a) for a in data]

    def create_annotation(
        self,
        match_id: str,
        payload: CreateAnnotationRequest,
    ) -> TacticalAnnotationRecord:
        now = _utcnow().isoformat()
        record = TacticalAnnotationRecord(
            id=uuid.uuid4().hex,
            matchId=match_id,
            createdAt=now,
            updatedAt=now,
            **{k: v for k, v in payload.model_dump().items() if v is not None},
        )
        with self._owner._annotation_issue_lock:
            annotations = self.list_annotations(match_id)
            annotations.append(record)
            self._owner._write_json(
                self.annotations_path(match_id),
                [a.model_dump(mode="json") for a in annotations],
            )
        return record

    def delete_annotation(self, match_id: str, annotation_id: str) -> None:
        with self._owner._annotation_issue_lock:
            annotations = [
                a for a in self.list_annotations(match_id) if a.id != annotation_id
            ]
            self._owner._write_json(
                self.annotations_path(match_id),
                [a.model_dump(mode="json") for a in annotations],
            )

    def issues_path(self, match_id: str) -> Path:
        self._owner.get_match(match_id)
        path = self._owner.storage_root / "matches" / match_id / "issues.json"
        path.parent.mkdir(parents=True, exist_ok=True)
        return path

    def list_issues(self, match_id: str) -> list[MatchIssueRecord]:
        path = self.issues_path(match_id)
        if not path.exists():
            return []
        data = self._owner._read_json(path)
        if not isinstance(data, list):
            raise TypeError("issues must be a JSON array")
        return [MatchIssueRecord.model_validate(i) for i in data]

    def create_issue(
        self,
        match_id: str,
        payload: CreateIssueRequest,
    ) -> MatchIssueRecord:
        now = _utcnow().isoformat()
        record = MatchIssueRecord(
            id=uuid.uuid4().hex,
            matchId=match_id,
            createdAt=now,
            updatedAt=now,
            **{k: v for k, v in payload.model_dump().items() if v is not None},
        )
        with self._owner._annotation_issue_lock:
            issues = self.list_issues(match_id)
            issues.append(record)
            self._owner._write_json(
                self.issues_path(match_id),
                [i.model_dump(mode="json") for i in issues],
            )
        return record

    def delete_issue(self, match_id: str, issue_id: str) -> None:
        with self._owner._annotation_issue_lock:
            issues = [i for i in self.list_issues(match_id) if i.id != issue_id]
            self._owner._write_json(
                self.issues_path(match_id),
                [i.model_dump(mode="json") for i in issues],
            )
