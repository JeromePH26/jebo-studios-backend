from __future__ import annotations

import io
import os
import time
import uuid
from typing import Final

from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import Response
from PIL import Image, ImageEnhance, ImageOps, UnidentifiedImageError

APP_VERSION: Final[str] = "0.1.0"
MAX_UPLOAD_BYTES: Final[int] = int(os.getenv("MAX_UPLOAD_BYTES", str(20 * 1024 * 1024)))
MAX_EDGE: Final[int] = int(os.getenv("MAX_EDGE", "2400"))
JPEG_QUALITY: Final[int] = int(os.getenv("JPEG_QUALITY", "92"))

app = FastAPI(title="JeBo Studios Backend", version=APP_VERSION)

allowed_origins = [
    origin.strip()
    for origin in os.getenv("CORS_ORIGINS", "*").split(",")
    if origin.strip()
]

app.add_middleware(
    CORSMiddleware,
    allow_origins=allowed_origins,
    allow_credentials=False,
    allow_methods=["GET", "POST", "OPTIONS"],
    allow_headers=["*"],
)


@app.get("/health")
def health() -> dict[str, str]:
    return {
        "status": "ok",
        "service": "jebo-studios-backend",
        "version": APP_VERSION,
    }


def _validate_content_type(content_type: str | None) -> None:
    if content_type not in {"image/jpeg", "image/png", "image/webp"}:
        raise HTTPException(
            status_code=415,
            detail="Unsupported image type. Use JPEG, PNG or WebP.",
        )


def _fit_image(image: Image.Image) -> Image.Image:
    if max(image.size) <= MAX_EDGE:
        return image
    resized = image.copy()
    resized.thumbnail((MAX_EDGE, MAX_EDGE), Image.Resampling.LANCZOS)
    return resized


def _conservative_auto_studio(image: Image.Image) -> Image.Image:
    """Non-generative, conservative tonal cleanup.

    No object synthesis, no inpainting and no structural edits are performed.
    """
    image = ImageOps.exif_transpose(image).convert("RGB")
    image = _fit_image(image)

    # Keep the adjustments intentionally mild so product condition remains visible.
    image = ImageOps.autocontrast(image, cutoff=0.5)
    image = ImageEnhance.Brightness(image).enhance(1.02)
    image = ImageEnhance.Contrast(image).enhance(1.03)
    image = ImageEnhance.Sharpness(image).enhance(1.06)
    return image


@app.post("/api/v1/process")
async def process_image(file: UploadFile = File(...)) -> Response:
    request_id = str(uuid.uuid4())
    started = time.perf_counter()

    _validate_content_type(file.content_type)
    payload = await file.read(MAX_UPLOAD_BYTES + 1)

    if len(payload) > MAX_UPLOAD_BYTES:
        raise HTTPException(status_code=413, detail="Image upload is too large.")
    if not payload:
        raise HTTPException(status_code=400, detail="Empty image upload.")

    try:
        with Image.open(io.BytesIO(payload)) as source:
            result = _conservative_auto_studio(source)
            output = io.BytesIO()
            result.save(
                output,
                format="JPEG",
                quality=JPEG_QUALITY,
                optimize=True,
                subsampling=0,
            )
    except UnidentifiedImageError as exc:
        raise HTTPException(status_code=400, detail="Invalid image file.") from exc
    except Image.DecompressionBombError as exc:
        raise HTTPException(status_code=413, detail="Image dimensions are too large.") from exc

    duration_ms = int((time.perf_counter() - started) * 1000)
    return Response(
        content=output.getvalue(),
        media_type="image/jpeg",
        headers={
            "X-Request-ID": request_id,
            "X-Processing-Time-Ms": str(duration_ms),
            "Cache-Control": "no-store",
        },
    )
