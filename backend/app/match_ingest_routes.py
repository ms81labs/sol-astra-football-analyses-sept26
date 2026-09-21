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
    async def create_match(
        request: Request,
        name: str = Form(...),
        inputMode: str = Form(...),
        config: str = Form("{}"),
        budget: float = Form(0.0),
        file: UploadFile = File(...),
        idempotency_key: str | None = Header(default=None, alias="Idempotency-Key"),
    ) -> dict:
        if not math.isfinite(budget) or budget < 0:
            raise HTTPException(status_code=422, detail="budget must be finite and non-negative")
        if runner.settings.processing_backend == "daytona" and budget <= 0:
            raise HTTPException(
                status_code=422,
                detail="Daytona processing requires a positive authorised budget",
            )
        if idempotency_key is not None and _IDEMPOTENCY_KEY.fullmatch(idempotency_key) is None:
            raise HTTPException(status_code=400, detail="Invalid Idempotency-Key")
        admission_token = idempotency_key or uuid.uuid4().hex
    
        def response(job, *, outcome: str, reused: bool) -> dict:
            return {
                "matchId": job.matchId,
                "jobId": job.id,
                "status": job.status,
                "admissionToken": admission_token,
                "dispatchOutcome": outcome,
                "reused": reused,
            }
    
        admitted = await run_in_threadpool(storage.get_admission_by_token, admission_token)
        if admitted is not None:
            return response(admitted[1], outcome="reused", reused=True)
    
        if inputMode not in {"tracking_json", "video"}:
            raise HTTPException(status_code=422, detail="Invalid inputMode")
        try:
            config_model = MatchConfig.model_validate_json(config)
        except Exception as exc:  # pragma: no cover - FastAPI validation path
            raise HTTPException(status_code=400, detail=f"Invalid config payload: {exc}") from exc
        if settings.deployment_mode == "hosted":
            config_model = config_model.model_copy(
                update={"rights": config_model.rights.model_copy(update={"audience": request.state.tenant})}
            )
    
        if (
            inputMode == "video"
            and not config_model.autoHomography
            and len(config_model.manualHomographyPoints) != 4
        ):
            raise HTTPException(
                status_code=400,
                detail="manualHomographyPoints must contain exactly 4 points for video input, or set autoHomography=True.",
            )
    
        try:
            upload_path = await run_in_threadpool(
                storage.save_upload_stream,
                file.filename or "upload.bin",
                file.file,
                runner.settings.max_upload_bytes,
            )
        except UploadTooLargeError as exc:
            raise HTTPException(status_code=413, detail=str(exc)) from exc
        match_id = uuid.uuid4().hex
        job_id = uuid.uuid4().hex
        try:
            match, job, created = await run_in_threadpool(
                storage.admit_match_job,
                match_id=match_id,
                job_id=job_id,
                admission_token=admission_token,
                name=name,
                input_mode=inputMode,
                original_filename=file.filename or "upload.bin",
                input_path=upload_path,
                config=config_model,
            )
        except AdmissionOutcomeUncertainError as exc:
            raise HTTPException(
                status_code=503,
                detail={
                    "code": "admission_outcome_uncertain",
                    "matchId": match_id,
                    "jobId": job_id,
                    "admissionToken": admission_token,
                },
            ) from exc
        except Exception as exc:
            raise HTTPException(status_code=500, detail="Match admission failed") from exc
        if not created:
            return response(job, outcome="reused", reused=True)
    
        try:
            runner.admit(
                job.id,
                match_id=match.id,
                source_sha256=storage.source_sha256(match.id),
                budget=budget,
            )
        except IdempotencyConflict:
            pass
    
        dispatch_outcome = "started"
        dispatch_error: str | None = None
        try:
            await run_in_threadpool(runner.start, job.id)
        except JobDispatchError as exc:
            if exc.child_may_have_started:
                dispatch_outcome = "uncertain"
                dispatch_error = _DISPATCH_UNCERTAIN
            else:
                dispatch_outcome = "failed"
                dispatch_error = _DISPATCH_FAILED
        except Exception as exc:
            LOGGER.warning(
                "job dispatch outcome uncertain match=%s job=%s error=%s",
                match.id,
                job.id,
                type(exc).__name__,
            )
            dispatch_outcome = "uncertain"
            dispatch_error = _DISPATCH_UNCERTAIN
    
        if dispatch_error is None:
            try:
                job = await run_in_threadpool(storage.mark_dispatched, job.id)
            except Exception as exc:
                LOGGER.warning(
                    "failed to persist dispatched state match=%s job=%s error=%s",
                    match.id,
                    job.id,
                    type(exc).__name__,
                )
        else:
            try:
                job = await run_in_threadpool(storage.mark_dispatch_failed, match.id, job.id, error=dispatch_error)
            except Exception as exc:
                LOGGER.warning(
                    "failed to persist dispatch failure match=%s job=%s error=%s",
                    match.id,
                    job.id,
                    type(exc).__name__,
                )
        return response(job, outcome=dispatch_outcome, reused=False)
    

    return router
