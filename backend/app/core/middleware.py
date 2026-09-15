"""CORS + request logging. Auth is enforced per-route via dependencies."""
import logging
import time
import uuid

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings

log = logging.getLogger("igfunnel.http")


def setup_middleware(app: FastAPI) -> None:
    origins = [o.strip() for o in settings.CORS_ORIGINS.split(",") if o.strip()]
    app.add_middleware(
        CORSMiddleware,
        allow_origins=origins,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    @app.middleware("http")
    async def request_logging(request: Request, call_next):
        request_id = uuid.uuid4().hex[:8]
        started = time.perf_counter()
        try:
            response = await call_next(request)
            log.info(
                "%s %s -> %s (%.1fms) [%s]",
                request.method,
                request.url.path,
                response.status_code,
                (time.perf_counter() - started) * 1000,
                request_id,
            )
            response.headers["X-Request-ID"] = request_id
            return response
        except Exception:
            log.exception("Unhandled error for %s %s [%s]", request.method, request.url.path, request_id)
            raise
