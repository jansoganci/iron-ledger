from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from slowapi.errors import RateLimitExceeded

from backend import messages
from backend.api.middleware import TraceIdMiddleware
from backend.api.rate_limit import limiter
from backend.api.routes import router
from backend.domain.errors import (
    DuplicateEntryError,
    FileHasNoValidColumns,
    InvalidRunTransition,
    MappingAmbiguous,
    RLSForbiddenError,
    TransientIOError,
)
from backend.logger import configure_logging, get_logger, get_trace_id
from backend.settings import get_settings

logger = get_logger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    configure_logging()
    logger.info("IronLedger starting up")
    yield
    logger.info("IronLedger shutting down")


def create_app() -> FastAPI:
    settings = get_settings()

    app = FastAPI(
        title="IronLedger",
        version="0.1.0",
        lifespan=lifespan,
    )

    # Rate limiter state
    app.state.limiter = limiter

    # CORS
    origins = [
        "http://localhost:5173",
        settings.frontend_url,
    ]
    app.add_middleware(
        CORSMiddleware,
        allow_origins=[o for o in origins if o],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Trace-id stamping
    app.add_middleware(TraceIdMiddleware)

    # ------------------------------------------------------------------ #
    # Exception handlers — most specific first                             #
    # ------------------------------------------------------------------ #

    @app.exception_handler(RateLimitExceeded)
    async def rate_limit_handler(request: Request, exc: RateLimitExceeded):
        retry_after = getattr(exc, "retry_after", 60)
        return JSONResponse(
            status_code=429,
            headers={"Retry-After": str(retry_after)},
            content={
                "error": "rate_limited",
                "message": messages.RATE_LIMITED.format(
                    retry_after_seconds=retry_after
                ),
                "retry_after_seconds": retry_after,
                "trace_id": get_trace_id(),
            },
        )

    @app.exception_handler(FileHasNoValidColumns)
    async def file_no_columns_handler(request: Request, exc: FileHasNoValidColumns):
        return JSONResponse(
            status_code=422,
            content={
                "error": "parse_failed",
                "message": messages.FILE_HAS_NO_VALID_COLUMNS,
                "trace_id": get_trace_id(),
            },
        )

    @app.exception_handler(MappingAmbiguous)
    async def mapping_ambiguous_handler(request: Request, exc: MappingAmbiguous):
        return JSONResponse(
            status_code=422,
            content={
                "error": "mapping_failed",
                "message": messages.MAPPING_FAILED.format(columns=str(exc)),
                "trace_id": get_trace_id(),
            },
        )

    @app.exception_handler(DuplicateEntryError)
    async def duplicate_entry_handler(request: Request, exc: DuplicateEntryError):
        return JSONResponse(
            status_code=409,
            content={
                "error": "duplicate_entry",
                "message": messages.DUPLICATE_ENTRY,
                "trace_id": get_trace_id(),
            },
        )

    @app.exception_handler(RLSForbiddenError)
    async def rls_forbidden_handler(request: Request, exc: RLSForbiddenError):
        return JSONResponse(
            status_code=403,
            content={
                "error": "forbidden",
                "message": messages.FORBIDDEN,
                "trace_id": get_trace_id(),
            },
        )

    @app.exception_handler(TransientIOError)
    async def transient_io_handler(request: Request, exc: TransientIOError):
        return JSONResponse(
            status_code=503,
            content={
                "error": "service_unavailable",
                "message": messages.UPLOAD_FAILED,
                "trace_id": get_trace_id(),
            },
        )

    @app.exception_handler(InvalidRunTransition)
    async def invalid_transition_handler(request: Request, exc: InvalidRunTransition):
        logger.error(
            "invalid_run_transition",
            extra={"error": str(exc), "trace_id": get_trace_id()},
            exc_info=True,
        )
        return JSONResponse(
            status_code=500,
            content={
                "error": "internal_error",
                "message": messages.INTERNAL_ERROR,
                "trace_id": get_trace_id(),
            },
        )

    @app.exception_handler(Exception)
    async def unhandled_exception_handler(request: Request, exc: Exception):
        logger.error(
            "unhandled_exception",
            extra={
                "error": str(exc),
                "path": str(request.url.path),
                "trace_id": get_trace_id(),
            },
            exc_info=True,
        )
        return JSONResponse(
            status_code=500,
            content={
                "error": "internal_error",
                "message": messages.INTERNAL_ERROR,
                "trace_id": get_trace_id(),
            },
        )

    app.include_router(router)
    return app


app = create_app()
