"""Periodic reaper — finds stuck ingestion jobs and marks them failed.

Runs as a periodic in-process background task (asyncio loop from app lifespan).
Started by the app lifespan.
"""

from __future__ import annotations

import asyncio
from datetime import UTC, datetime, timedelta

import structlog

from app.core.database import SessionLocal
from app.repositories import ingestion_job_repo
from app.services.sse_service import next_sequence, publish_job_event

log = structlog.get_logger()

STUCK_THRESHOLD_SECONDS = 300  # 5 minutes
REAP_INTERVAL_SECONDS = 60


async def run_reaper_loop() -> None:
    """Periodically scan for stuck jobs. Designed to be run as a background task."""
    while True:
        try:
            await _reap_stuck_jobs()
        except Exception:
            log.error("reaper_error", exc_info=True)
        await asyncio.sleep(REAP_INTERVAL_SECONDS)


async def _reap_stuck_jobs() -> None:
    async with SessionLocal() as session:
        stuck = await ingestion_job_repo.find_stuck_jobs(
            session, older_than=timedelta(seconds=STUCK_THRESHOLD_SECONDS)
        )
        if not stuck:
            return

        log.info("reaper_found_stuck", count=len(stuck))
        now = datetime.now(tz=UTC)
        for job in stuck:
            await ingestion_job_repo.update_job_status(
                session,
                job.id,
                status="failed",
                internal_state="error",
                internal_error_state="heartbeat_timeout",
                error_type="internal",
                error_code="worker_timeout",
                rerun_allowed=True,
                completed_at=now,
                last_heartbeat_at=now,
            )
            seq = next_sequence(job.id)
            publish_job_event(
                job.id,
                {
                    "eventType": "job.failed",
                    "jobId": job.id,
                    "sequence": seq,
                    "timestamp": now.isoformat().replace("+00:00", "Z"),
                    "status": "failed",
                    "errorType": "internal",
                    "errorCode": "worker_timeout",
                    "rerunAllowed": True,
                },
            )
            log.warning("reaper_marked_failed", job_id=job.id)

        await session.commit()
