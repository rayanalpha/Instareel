"""FastAPI entrypoint: middleware, error envelope, health, routers, startup init."""
import logging
import os

from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from slowapi import _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded

from app.api.deps import limiter
from app.api.router import router, ws_mount
from app.config import settings
from app.core.exceptions import AppError
from app.core.middleware import setup_middleware
from app.database import Base, engine

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(name)s %(levelname)s %(message)s")
log = logging.getLogger("igfunnel")

app = FastAPI(title="IG Funnel API", version="1.0.0")
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
setup_middleware(app)


@app.exception_handler(AppError)
async def app_error_handler(request: Request, exc: AppError):
    return JSONResponse(
        status_code=exc.status_code,
        content={"error": exc.code, "message": exc.message, "details": exc.details},
    )


@app.get("/health")
async def health():
    return {"ok": True, "env": settings.ENV}


app.include_router(router)
app.include_router(ws_mount)


@app.on_event("startup")
async def startup():
    os.makedirs(settings.MEDIA_ROOT, exist_ok=True)
    for sub in ("raw", "processed", "thumbnails", "watermarks", "sessions", "audio"):
        os.makedirs(os.path.join(settings.MEDIA_ROOT, sub), exist_ok=True)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    log.info("IG Funnel API ready (env=%s)", settings.ENV)
