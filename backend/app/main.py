"""FastAPI application entry point."""
import os
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from .database import get_db, init_db
from .p0_auth import P0AuthMiddleware, DEV_MODE
from .p0_routes import router as p0_router
from .p1_routes import router as p1_router
from .p2_routes import router as p2_router
from .p3_routes import router as p3_router

from contextlib import asynccontextmanager

@asynccontextmanager
async def lifespan(app):
    await init_db()
    try:
        from .notifications import NotificationScheduler
        scheduler = NotificationScheduler(interval_seconds=3600)
        await scheduler.start()
        app.state.scheduler = scheduler
    except Exception as e:
        print(f"Scheduler start failed: {e}")
    yield
    if hasattr(app.state, "scheduler"):
        await app.state.scheduler.stop()

app = FastAPI(title="KFL Aviation DMS", version="1.0.0", lifespan=lifespan)

_cors_origins = [origin.strip() for origin in os.getenv("CORS_ORIGINS", "http://localhost:5173" if DEV_MODE else "").split(",") if origin.strip()]
_auth_headers = ["Content-Type", "X-CSRF-Token"]
if DEV_MODE:
    _auth_headers.extend(["X-Role", "X-Actor"])
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import Response
from starlette.requests import Request

class SecurityHeadersMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        response = await call_next(request)
        response.headers["Content-Security-Policy"] = "default-src 'self'; script-src 'self' 'unsafe-eval'; style-src 'self' 'unsafe-inline'; img-src 'self' data:; font-src 'self'; connect-src 'self'; frame-ancestors 'none'"
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["X-Frame-Options"] = "DENY"
        response.headers["Referrer-Policy"] = "no-referrer"
        return response

from .rate_limiter import RateLimitMiddleware

# Starlette executes the last-added middleware outermost. Keep CORS and security
# headers outside the limiter so 429 responses retain browser-facing headers;
# the limiter still runs before auth and covers unauthorized requests.
app.add_middleware(P0AuthMiddleware)
app.add_middleware(RateLimitMiddleware)
app.add_middleware(SecurityHeadersMiddleware)
app.add_middleware(
    CORSMiddleware,
    allow_origins=_cors_origins,
    allow_credentials=True,
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=_auth_headers,
)

app.include_router(p0_router, prefix="/api/p0")
app.include_router(p1_router, prefix="/api/p1")
app.include_router(p2_router, prefix="/api/p2")
app.include_router(p3_router, prefix="/api/p3")


@app.get("/health")
async def health():
    db = await get_db()
    try:
        await db.execute("SELECT 1")
    except Exception as exc:
        raise HTTPException(status_code=503, detail="Database is not ready") from exc
    finally:
        await db.close()
    return {"status": "ok"}
