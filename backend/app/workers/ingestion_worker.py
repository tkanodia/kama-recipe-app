"""Ingestion worker — runs the ingestion agent as an in-process async task.

Previously ran in a separate worker process; killing that process could
break the multiprocessing stdio pipes used for logging, causing
BrokenPipeError cascades on subsequent log calls.  Now runs on the
FastAPI event loop via ``background_runner.enqueue``.
"""

from __future__ import annotations

from datetime import UTC, datetime

import structlog
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.database import SessionLocal
from app.repositories import ingestion_job_repo, source_asset_repo
from app.services.background_runner import enqueue
from app.services.sse_service import next_sequence, publish_job_event

log = structlog.get_logger()


def run_ingestion_send(job_id: str) -> None:
    """Enqueue an ingestion job to run in the background.

    Drop-in replacement for the old ``run_ingestion.send(job_id)`` call.
    """
    enqueue(_run_ingestion, job_id, task_name=f"ingestion-{job_id}")


async def _run_ingestion(job_id: str) -> None:
    async with SessionLocal() as session:
        job = await ingestion_job_repo.get_job_by_id(session, job_id)
        if job is None:
            log.warning("ingestion_job_missing", job_id=job_id)
            return

        now = datetime.now(tz=UTC)
        await ingestion_job_repo.update_job_status(
            session,
            job_id,
            status="processing",
            internal_state="source_received",
            started_at=now,
            last_heartbeat_at=now,
        )
        await session.commit()

        seq = next_sequence(job_id)
        publish_job_event(
            job_id,
            {
                "eventType": "job.state_changed",
                "jobId": job_id,
                "sequence": seq,
                "timestamp": now.isoformat().replace("+00:00", "Z"),
                "status": "processing",
                "internalState": "source_received",
            },
        )

        source = await source_asset_repo.get_source_asset_by_id(session, job.source_asset_id)
        if source is None:
            log.error("source_asset_missing", job_id=job_id, source_asset_id=job.source_asset_id)
            await _mark_failed(session, job_id, "source_asset_missing")
            return

        meta = job.extra_metadata or {}
        model_override = meta.get("llmModel")

        try:
            from app.agents.ingestion_agent import run_ingestion_agent

            await run_ingestion_agent(
                session,
                job_id=job_id,
                user_id=job.user_id,
                source_asset_id=job.source_asset_id,
                source_type=source.source_type,
                url=source.original_url,
                raw_text=source.raw_text_input,
                file_asset_ref=source.file_asset_ref,
                model_override=model_override,
            )
            log.info("ingestion_worker_complete", job_id=job_id)
        except Exception as exc:
            log.error("ingestion_worker_error", job_id=job_id, error=str(exc), exc_info=True)
            await _mark_failed(session, job_id, str(exc)[:500])


async def _mark_failed(session: AsyncSession, job_id: str, reason: str) -> None:
    """Mark a job as failed in the DB and emit an SSE event."""
    try:
        now = datetime.now(tz=UTC)
        await ingestion_job_repo.update_job_status(
            session,
            job_id,
            status="failed",
            internal_state="error",
            internal_error_state="worker_error",
            error_type="internal",
            error_code="worker_exception",
            rerun_allowed=True,
            completed_at=now,
        )
        await session.commit()

        seq = next_sequence(job_id)
        publish_job_event(
            job_id,
            {
                "eventType": "job.failed",
                "jobId": job_id,
                "sequence": seq,
                "timestamp": now.isoformat().replace("+00:00", "Z"),
                "status": "failed",
                "errorType": "internal",
                "errorCode": "worker_exception",
                "message": reason,
                "rerunAllowed": True,
            },
        )
    except Exception:
        log.error("mark_failed_error", job_id=job_id, exc_info=True)
