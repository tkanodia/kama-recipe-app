"""In-process background tasks (asyncio).

Long-running work is scheduled via ``app.services.background_runner.enqueue``
from API routes or other call sites. Periodic loops (reaper, ask cleanup)
start from FastAPI lifespan in ``app.main``.
"""
