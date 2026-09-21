"""Match upload and admission API route."""

from __future__ import annotations

import logging
import math
import re
import uuid

from fastapi import APIRouter, File, Form, Header, HTTPException, Request, UploadFile
from starlette.concurrency import run_in_threadpool

from .jobs import JobDispatchError, JobRunner
from .schemas import MatchConfig
from .settings import ProcessingSettings
from .storage import AdmissionOutcomeUncertainError, Storage, UploadTooLargeError
from .workbench.errors import IdempotencyConflict

LOGGER = logging.getLogger(__name__)
_IDEMPOTENCY_KEY = re.compile(r"[A-Za-z0-9._:-]{1,128}\\Z")
_DISPATCH_FAILED = "Job dispatch failed before processing started."
_DISPATCH_UNCERTAIN = "Job dispatch outcome is uncertain; automatic retry is disabled."


def create_match_ingest_router(
    storage: Storage,
    runner: JobRunner,
    settings: ProcessingSettings,
) -> APIRouter:
    router = APIRouter()

    @router.post("/api/matches", status_code=202)

    return router
