from contextlib import asynccontextmanager

try:
    import sentry_sdk
except ImportError:
    sentry_sdk = None  # type: ignore[assignment]
import structlog
from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from slowapi.errors import RateLimitExceeded

from app.api import admin, artifacts, ask, candidates, drafts, ingredients, ingestion, journal, media, pantry, recipes, search, tags
from app.core.config import get_settings
from app.core.error_handlers import register_error_handlers
from app.core.logging import configure_logging
from app.core.rate_limit import _rate_limit_key, limiter

configure_logging()
log = structlog.get_logger()
settings = get_settings()

if settings.sentry_dsn and sentry_sdk:
    sentry_sdk.init(
        dsn=settings.sentry_dsn,
        environment=settings.app_env,
        traces_sample_rate=0.2 if settings.app_env == "production" else 1.0,
        profiles_sample_rate=0.1 if settings.app_env == "production" else 0.0,
        send_default_pii=False,
    )
    log.info("sentry_initialized", environment=settings.app_env)


def _rate_limit_exceeded_handler(request: Request, exc: RateLimitExceeded) -> JSONResponse:
    retry_after = getattr(exc, "retry_after", None)
    headers = {"Retry-After": str(retry_after)} if retry_after else {}
    log.warning("rate_limit_exceeded", path=request.url.path, key=_rate_limit_key(request))
    return JSONResponse(
        status_code=429,
        content={"error": {"code": "rate_limited", "message": "Rate limit exceeded. Please try again later."}},
        headers=headers,
    )


@asynccontextmanager
async def lifespan(_: FastAPI):
    import asyncio
    from app.core.qdrant import close_qdrant, init_collection
    from app.services.background_runner import drain
    from app.workers.ask_cleanup_worker import run_ask_cleanup_loop
    from app.workers.reaper_worker import run_reaper_loop

    log.info("app_startup")
    try:
        await init_collection()
    except Exception:
        log.warning("qdrant_init_failed", exc_info=True)
    reaper_task = asyncio.create_task(run_reaper_loop(), name="reaper")
    ask_cleanup_task = asyncio.create_task(run_ask_cleanup_loop(), name="ask_cleanup")
    yield
    reaper_task.cancel()
    ask_cleanup_task.cancel()
    log.info("app_shutdown_draining_tasks")
    await drain(timeout=30.0)
    await close_qdrant()
    log.info("app_shutdown")


app = FastAPI(title="Kama API", lifespan=lifespan)
register_error_handlers(app)
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


@app.get("/health/ready")
async def health_ready() -> dict[str, str]:
    """Readiness probe — verifies database connectivity."""
    from sqlalchemy import text
    from app.core.database import SessionLocal

    try:
        async with SessionLocal() as session:
            await session.execute(text("SELECT 1"))
        return {"status": "ready"}
    except Exception:
        log.warning("health_ready_failed", exc_info=True)
        raise HTTPException(status_code=503, detail="not_ready")


app.include_router(artifacts.router, prefix="/api")
app.include_router(ask.router, prefix="/api")
app.include_router(ingestion.router, prefix="/api")
app.include_router(candidates.router, prefix="/api")
app.include_router(recipes.router, prefix="/api")
app.include_router(drafts.router, prefix="/api")
app.include_router(journal.router, prefix="/api")
app.include_router(media.router, prefix="/api")
app.include_router(ingredients.router, prefix="/api")
app.include_router(pantry.router, prefix="/api")
app.include_router(tags.router, prefix="/api")
app.include_router(search.router, prefix="/api")
app.include_router(admin.router, prefix="/api")
