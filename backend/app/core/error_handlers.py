"""Centralized exception handlers that produce a standard error envelope."""

import traceback

try:
    import sentry_sdk
except ImportError:
    sentry_sdk = None  # type: ignore[assignment]
import structlog
from fastapi import FastAPI, HTTPException, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

log = structlog.get_logger()

_USER_MESSAGES: dict[str, str] = {
    "source_access": "We couldn't access that source. Please check the URL and try again.",
    "source_quality": "The source didn't contain enough information to extract a recipe.",
    "parseability": "We couldn't identify a recipe in that content.",
    "internal": "Something went wrong on our end. Please try again.",
    "qdrant_unavailable": "Search is temporarily unavailable. Please try again shortly.",
    "session_closed": "This session has been closed. Start a new conversation.",
    "artifact_generation_failed": "Failed to generate artifact. Please try again.",
}


def _error_body(code: str, message: str, details: dict | None = None) -> dict:
    body: dict = {"error": {"code": code, "message": message}}
    if details is not None:
        body["error"]["details"] = details
    return body


async def http_exception_handler(_request: Request, exc: HTTPException) -> JSONResponse:
    code = _code_for_status(exc.status_code)
    message = _USER_MESSAGES.get(code, str(exc.detail))
    return JSONResponse(
        status_code=exc.status_code,
        content=_error_body(code, message),
    )


async def validation_exception_handler(
    _request: Request, exc: RequestValidationError
) -> JSONResponse:
    field_errors: dict[str, list[str]] = {}
    for err in exc.errors():
        loc = ".".join(str(part) for part in err["loc"] if part != "body")
        field_errors.setdefault(loc, []).append(err["msg"])

    return JSONResponse(
        status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
        content=_error_body(
            code="validation_error",
            message="One or more fields failed validation.",
            details={"fields": field_errors},
        ),
    )


async def unhandled_exception_handler(_request: Request, exc: Exception) -> JSONResponse:
    if sentry_sdk:
        sentry_sdk.capture_exception(exc)
    log.error(
        "unhandled_exception",
        exc_type=type(exc).__name__,
        exc_message=str(exc),
        traceback=traceback.format_exc(),
    )
    return JSONResponse(
        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
        content=_error_body("internal", _USER_MESSAGES["internal"]),
    )


def _code_for_status(status_code: int) -> str:
    return {
        400: "bad_request",
        401: "unauthorized",
        403: "forbidden",
        404: "not_found",
        409: "conflict",
        422: "validation_error",
        429: "rate_limited",
        503: "service_unavailable",
    }.get(status_code, "internal")


def register_error_handlers(app: FastAPI) -> None:
    app.add_exception_handler(HTTPException, http_exception_handler)  # type: ignore[arg-type]
    app.add_exception_handler(RequestValidationError, validation_exception_handler)  # type: ignore[arg-type]
    app.add_exception_handler(Exception, unhandled_exception_handler)  # type: ignore[arg-type]
