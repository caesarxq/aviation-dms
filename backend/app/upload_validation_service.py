"""Private, stateless PDF/image validator service for a restricted container."""
from __future__ import annotations

import asyncio

from fastapi import FastAPI, HTTPException, Query, Request
from fastapi.responses import Response

from .upload_validation import (
    UploadContentInvalid,
    UploadValidationUnavailable,
    validate_upload_content_local,
)

MAX_CONCURRENT_VALIDATIONS = 2
_VALIDATION_SLOTS = asyncio.Semaphore(MAX_CONCURRENT_VALIDATIONS)
_SUPPORTED_EXTENSIONS = {".pdf", ".png", ".jpg", ".jpeg"}
app = FastAPI(docs_url=None, redoc_url=None, openapi_url=None)


@app.get("/health")
async def health():
    return {"status": "ok"}


@app.post("/validate", status_code=204)
async def validate(
    request: Request,
    extension: str = Query(...),
    max_bytes: int = Query(..., ge=1),
    max_image_pixels: int = Query(default=40_000_000, ge=1),
):
    if extension not in _SUPPORTED_EXTENSIONS:
        raise HTTPException(status_code=400, detail="Unsupported validation format")
    raw_length = request.headers.get("content-length")
    if raw_length:
        try:
            if int(raw_length) > max_bytes:
                raise HTTPException(status_code=413, detail="Validation payload exceeds its declared limit")
        except ValueError as exc:
            raise HTTPException(status_code=400, detail="Invalid Content-Length") from exc

    content = bytearray()
    async with _VALIDATION_SLOTS:
        async for chunk in request.stream():
            if len(content) + len(chunk) > max_bytes:
                raise HTTPException(status_code=413, detail="Validation payload exceeds its declared limit")
            content.extend(chunk)
        try:
            await validate_upload_content_local(bytes(content), extension, max_bytes, max_image_pixels)
        except UploadContentInvalid as exc:
            raise HTTPException(status_code=422, detail="File is structurally invalid") from exc
        except UploadValidationUnavailable as exc:
            raise HTTPException(status_code=503, detail="Isolated parser is unavailable") from exc
    return Response(status_code=204)
