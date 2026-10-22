"""FastAPI application entry point."""
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from .database import init_db
from .p0_auth import P0AuthMiddleware
from .p0_routes import router as p0_router
from .p1_routes import router as p1_router

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

app.add_middleware(CORSMiddleware, allow_origins=["http://localhost:5173"], allow_credentials=False, allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"], allow_headers=["Content-Type", "X-Role", "X-Actor", "Authorization"])

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

app.add_middleware(SecurityHeadersMiddleware)
app.add_middleware(P0AuthMiddleware)

app.include_router(p0_router, prefix="/api/p0")
app.include_router(p1_router, prefix="/api/p1")



@app.get("/health")
async def health():
    return {"status": "ok"}
