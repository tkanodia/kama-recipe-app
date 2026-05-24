"""In-process async background task runner.

Schedules work as ``asyncio`` tasks on the FastAPI event loop: same process,
same DB pool and logging as HTTP handlers—no separate worker subprocess and
no broker.  Avoids multiprocessing-related stdio pipe issues that broke
logging when a forked worker process was killed during development.

For production at scale, you can swap the implementation behind ``enqueue``
for a distributed queue (Celery, RQ, a managed broker, etc.) while keeping
the same call-site API.
"""

from __future__ import annotations

import asyncio
import traceback
from datetime import UTC, datetime
from typing import Any

import structlog

log = structlog.get_logger()

_tasks: set[asyncio.Task[Any]] = set()


def enqueue(coro_func, *args: Any, task_name: str | None = None, **kwargs: Any) -> None:
    """Schedule an async function to run in the background.

    The coroutine function is called with *args/**kwargs inside a new
    asyncio Task.  If no event loop is running yet (e.g. during tests),
    falls back to creating one.
    """
    try:
        loop = asyncio.get_running_loop()
    except RuntimeError:
        loop = None

    if loop and loop.is_running():
        task = loop.create_task(
            _safe_run(coro_func, *args, **kwargs),
            name=task_name or coro_func.__name__,
        )
        _tasks.add(task)
        task.add_done_callback(_tasks.discard)
    else:
        asyncio.run(_safe_run(coro_func, *args, **kwargs))


async def _safe_run(coro_func, *args: Any, **kwargs: Any) -> None:
    """Run the coroutine with top-level exception protection."""
    try:
        await coro_func(*args, **kwargs)
    except Exception:
        log.error(
            "background_task_failed",
            task=coro_func.__name__,
            traceback=traceback.format_exc(),
        )


async def drain(timeout: float = 30.0) -> None:
    """Wait for all in-flight background tasks to complete (for graceful shutdown)."""
    if not _tasks:
        return
    log.info("background_drain_start", pending=len(_tasks))
    done, pending = await asyncio.wait(_tasks, timeout=timeout)
    if pending:
        log.warning("background_drain_timeout", timed_out=len(pending))
        for t in pending:
            t.cancel()
