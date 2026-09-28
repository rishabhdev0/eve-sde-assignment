import logging
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse
from sqlalchemy import text
from starlette.middleware.sessions import SessionMiddleware
from app.core.config import settings
from app.core.logging import setup_logging, request_id_ctx
from app.core.middleware import RequestContextMiddleware
from app.core.exceptions import AppException
from app.core.redis_client import redis_client
from app.db.session import engine
from app.api.v1.router import api_router

setup_logging()
logger = logging.getLogger("unhandled_exception")

app = FastAPI(title="EVE Healthcare Diagnostic Booking API")

app.add_middleware(SessionMiddleware, secret_key=settings.SESSION_SECRET)
app.add_middleware(RequestContextMiddleware)

app.include_router(api_router, prefix="/api/v1")


@app.exception_handler(AppException)
def handle_app_exception(request: Request, exc: AppException):
    return JSONResponse(status_code=exc.status_code, content={"detail": exc.detail})


@app.exception_handler(Exception)
def handle_unexpected_exception(request: Request, exc: Exception):
    logger.exception(
        f"Unhandled exception on {request.method} {request.url.path}",
        extra={"request_id": request_id_ctx.get()},
    )
    return JSONResponse(
        status_code=500,
        content={"detail": "An unexpected error occurred. Please try again or contact support."},
    )


@app.get("/health")
def health():
    checks = {"database": "unreachable", "redis": "unreachable"}

    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        checks["database"] = "ok"
    except Exception:
        pass

    try:
        redis_client.ping()
        checks["redis"] = "ok"
    except Exception:
        pass

    healthy = all(v == "ok" for v in checks.values())
    return JSONResponse(
        status_code=200 if healthy else 503,
        content={"status": "ok" if healthy else "degraded", "checks": checks},
    )