"""Periodic ask cleanup — closes idle sessions and deletes old ones.

Runs as a periodic in-process background task (asyncio loop from app lifespan).
Started by the app lifespan.
"""

from __future__ import annotations

import asyncio
from datetime import timedelta

import structlog

from app.core.database import SessionLocal
from app.repositories import ask_session_repo

log = structlog.get_logger()

CLEANUP_INTERVAL_SECONDS = 900  # 15 minutes
IDLE_THRESHOLD = timedelta(minutes=15)
DELETE_THRESHOLD = timedelta(days=7)


async def run_ask_cleanup_loop() -> None:
    """Periodically close idle sessions and purge old ones."""
    while True:
        try:
            await _cleanup()
        except Exception:
            log.error("ask_cleanup_error", exc_info=True)
        await asyncio.sleep(CLEANUP_INTERVAL_SECONDS)


async def _cleanup() -> None:
    async with SessionLocal() as session:
        expired = await ask_session_repo.find_expired_sessions(
            session, inactive_threshold=IDLE_THRESHOLD,
        )
        for s in expired:
            await ask_session_repo.close_session(session, s.id)
            log.info("ask_session_auto_closed", session_id=s.id)

        deleted = await ask_session_repo.delete_old_sessions(
            session, older_than=DELETE_THRESHOLD,
        )
        if deleted:
            log.info("ask_sessions_purged", count=deleted)

        await session.commit()
