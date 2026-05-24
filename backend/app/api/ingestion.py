import json
from collections.abc import AsyncIterator

import structlog
from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.auth import get_current_user_id, verify_bearer_token
from app.core.config import get_settings
from app.core.redis import get_redis
from app.core.database import get_db
from app.domain.ids import new_id
from app.core.rate_limit import limiter
from app.models.tables import IngestionJob
from app.repositories import ingestion_job_repo, source_asset_repo
from app.schemas.ingestion import (
    IngestionJobResponse,
    RerunIngestionResponse,
    SubmitIngestionBody,
    SubmitIngestionResponse,
)
from app.core.llm import AVAILABLE_MODELS, MODEL_REGISTRY
from app.services.sse_service import channel_for_job
from app.workers.ingestion_worker import run_ingestion_send

log = structlog.get_logger()
_settings = get_settings()
router = APIRouter(prefix="/ingestion", tags=["ingestion"])


def _processor_family(source_type: str) -> str:
    return source_type


def _job_to_response(job: IngestionJob) -> IngestionJobResponse:
    return IngestionJobResponse(
        id=job.id,
        sourceAssetId=job.source_asset_id,
        status=job.status,
        internalState=job.internal_state,
        internalErrorState=job.internal_error_state,
        processorFamily=job.processor_family,
        processorVariant=job.processor_variant,
        reviewMode=job.review_mode,
        candidateId=job.candidate_id,
        normalizedArtifactIds=list(job.normalized_artifact_ids or []),
        errorType=job.error_type,
        errorCode=job.error_code,
        rerunAllowed=job.rerun_allowed,
        userRecoverable=job.user_recoverable,
        extractionPlan=list(job.extraction_plan or []),
        stateHistory=list(job.state_history or []),
        job_metadata=dict(job.extra_metadata or {}),
        createdAt=job.created_at,
        startedAt=job.started_at,
        completedAt=job.completed_at,
        updatedAt=job.updated_at,
        lastHeartbeatAt=job.last_heartbeat_at,
    )


@router.post("", status_code=status.HTTP_201_CREATED)
@limiter.limit("10/minute")
async def submit_ingestion(
    request: Request,
    body: SubmitIngestionBody,
    db: AsyncSession = Depends(get_db),
    user_id: str = Depends(get_current_user_id),
) -> SubmitIngestionResponse:
    if body.source_type == "url" and not body.url:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="url required")
    if body.source_type == "image" and not body.file_asset_ref:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="fileAssetRef required")
    if body.source_type == "text" and not body.raw_text_input:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="rawTextInput required")
    if body.llm_model and body.llm_model not in MODEL_REGISTRY:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Unknown llmModel. Must be one of: {sorted(MODEL_REGISTRY)}",
        )

    src_id = new_id("src")
    job_id = new_id("job")

    job_metadata: dict | None = None
    if body.llm_model:
        job_metadata = {"llmModel": body.llm_model}

    await source_asset_repo.create_source_asset(
        db,
        id=src_id,
        user_id=user_id,
        source_type=body.source_type,
        original_url=body.url,
        raw_text_input=body.raw_text_input,
        file_asset_ref=body.file_asset_ref,
        context_note=body.context_note,
    )
    await ingestion_job_repo.create_ingestion_job(
        db,
        id=job_id,
        user_id=user_id,
        source_asset_id=src_id,
        status="queued",
        internal_state="source_received",
        processor_family=_processor_family(body.source_type),
        extra_metadata=job_metadata,
    )
    await db.commit()

    run_ingestion_send(job_id)
    log.info("ingestion_queued", job_id=job_id, user_id=user_id)

    return SubmitIngestionResponse(
        sourceAssetId=src_id,
        ingestionJobId=job_id,
        status="queued",
        sseUrl=f"/api/ingestion/jobs/{job_id}/events",
    )


@router.get("/jobs/{job_id}", response_model=IngestionJobResponse)
@limiter.limit("120/minute")
async def get_job(
    request: Request,
    job_id: str,
    db: AsyncSession = Depends(get_db),
    user_id: str = Depends(get_current_user_id),
) -> IngestionJobResponse:
    job = await ingestion_job_repo.get_job_by_id(db, job_id)
    if job is None or job.user_id != user_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Job not found")
    return _job_to_response(job)


@router.post("/jobs/{job_id}/rerun", status_code=status.HTTP_201_CREATED)
@limiter.limit("60/minute")
async def rerun_job(
    request: Request,
    job_id: str,
    db: AsyncSession = Depends(get_db),
    user_id: str = Depends(get_current_user_id),
) -> RerunIngestionResponse:
    old = await ingestion_job_repo.get_job_by_id(db, job_id)
    if old is None or old.user_id != user_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Job not found")
    if not old.rerun_allowed:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Rerun not allowed")

    new_job_id = new_id("job")
    await ingestion_job_repo.create_ingestion_job(
        db,
        id=new_job_id,
        user_id=user_id,
        source_asset_id=old.source_asset_id,
        status="queued",
        internal_state="source_received",
        processor_family=old.processor_family,
    )
    await db.commit()
    run_ingestion_send(new_job_id)
    return RerunIngestionResponse(
        originalJobId=job_id,
        newJobId=new_job_id,
        sourceAssetId=old.source_asset_id,
        status="queued",
        sseUrl=f"/api/ingestion/jobs/{new_job_id}/events",
    )


@router.get("/models")
async def list_models() -> list[dict[str, str]]:
    """Return the available LLM models the frontend can offer in its picker."""
    return AVAILABLE_MODELS


@router.get("/jobs/{job_id}/events")
async def job_events(
    job_id: str,
    request: Request,
    db: AsyncSession = Depends(get_db),
    token: str | None = Query(default=None),
) -> StreamingResponse:
    if _settings.disable_auth:
        user_id = "user_dev"
    else:
        auth_token = token
        if not auth_token:
            auth = request.headers.get("authorization")
            if auth and auth.lower().startswith("bearer "):
                auth_token = auth.split(" ", 1)[1].strip()
        if not auth_token:
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Not authenticated")
        user_id = verify_bearer_token(auth_token)

    job = await ingestion_job_repo.get_job_by_id(db, job_id)
    if job is None or job.user_id != user_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Job not found")

    async def gen() -> AsyncIterator[bytes]:
        r = get_redis()
        pubsub = r.pubsub()
        await pubsub.subscribe(channel_for_job(job_id))
        try:
            async for message in pubsub.listen():
                if message["type"] != "message":
                    continue
                raw = message["data"]
                if isinstance(raw, bytes):
                    raw = raw.decode("utf-8")
                payload = json.loads(raw)
                event_name = payload.get("eventType", "job.message")
                yield f"event: {event_name}\ndata: {json.dumps(payload)}\n\n".encode("utf-8")
        finally:
            await pubsub.unsubscribe(channel_for_job(job_id))
            await pubsub.close()

    return StreamingResponse(
        gen(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )
