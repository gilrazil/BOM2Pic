from pathlib import Path
import os
import re
from io import BytesIO
from typing import List

from fastapi import FastAPI, File, UploadFile, Form, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, StreamingResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from .utils.excel_image_extractor import (
    extract_images_by_column,
    column_letter_to_index,
)


APP_DIR = Path(__file__).parent
STATIC_DIR = APP_DIR / "static"
LOGO_DIR = APP_DIR.parent / "Logo"

# Limits can be overridden via environment variables
MAX_UPLOAD_MB = int(os.getenv("MAX_UPLOAD_MB", "20"))
MAX_IMAGES = int(os.getenv("MAX_IMAGES", "50"))
MAX_FILES = int(os.getenv("MAX_FILES", "10"))


app = FastAPI(title="BOM2Pic", version="0.1.0")


def get_allowed_origins() -> list[str]:
    """Return allowed CORS origins.

    Priority:
    1. `ALLOWED_ORIGINS` env var (comma-separated)
    2. `RENDER_EXTERNAL_URL` env var (automatically set on Render)
    3. Local development defaults
    """
    env_origins = os.getenv("ALLOWED_ORIGINS")
    if env_origins:
        return [origin.strip().rstrip("/") for origin in env_origins.split(",") if origin.strip()]

    render_url = os.getenv("RENDER_EXTERNAL_URL")
    origins: list[str] = []
    if render_url:
        origins.append(render_url.rstrip("/"))

    # Local development defaults
    origins.extend([
        "http://localhost:8000",
        "http://127.0.0.1:8000",
        "http://localhost:3000",
    ])
    return origins

app.add_middleware(
    CORSMiddleware,
    allow_origins=get_allowed_origins(),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")
if LOGO_DIR.exists():
    app.mount("/Logo", StaticFiles(directory=LOGO_DIR), name="logo")


@app.get("/", include_in_schema=False)
def root() -> FileResponse:
    index_path = STATIC_DIR / "index.html"
    return FileResponse(index_path)


@app.get("/favicon.ico", include_in_schema=False)
def favicon() -> FileResponse:
    # Serve the logo PNG as favicon to avoid 404s; modern browsers accept PNG
    logo_png = LOGO_DIR / "BOM2Pic_Logo.png"
    if logo_png.exists():
        return FileResponse(logo_png)
    # Fallback to 404 if the logo is missing
    raise HTTPException(status_code=404, detail="favicon not available")


@app.get("/health", include_in_schema=False)
def health() -> JSONResponse:
    return JSONResponse(content={"status": "ok"})


@app.post("/process")
async def process(
    files: List[UploadFile] = File(..., description="One or more Excel .xlsx files"),
    imageColumn: str = Form(..., min_length=1, max_length=2),
    nameColumn: str = Form(..., min_length=1, max_length=2),
):
    # Validate files
    if not files:
        raise HTTPException(status_code=400, detail="No files uploaded")
    if len(files) > MAX_FILES:
        raise HTTPException(status_code=400, detail=f"Too many files. Max {MAX_FILES}")

    # Validate columns
    try:
        img_col_idx = column_letter_to_index(imageColumn)
        name_col_idx = column_letter_to_index(nameColumn)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid column letter(s)")

    # Helper for safe folder names derived from workbook filenames
    def _safe_folder_name(name: str) -> str:
        stem = Path(name).stem
        stem = re.sub(r"[^A-Za-z0-9._-]+", "_", stem).strip("._-")
        return stem or "workbook"

    # Create ZIP in-memory aggregating all files
    import zipfile

    total_images = 0
    zip_buffer = BytesIO()
    with zipfile.ZipFile(zip_buffer, mode="w", compression=zipfile.ZIP_DEFLATED) as zf:
        for upload in files:
            original_name = upload.filename or "uploaded.xlsx"
            if not original_name.lower().endswith(".xlsx"):
                raise HTTPException(status_code=400, detail=f"Only .xlsx files are supported (got {original_name})")

            contents = await upload.read()
            size_mb = len(contents) / (1024 * 1024)
            if size_mb > MAX_UPLOAD_MB:
                raise HTTPException(status_code=400, detail=f"{original_name}: File too large. Max {MAX_UPLOAD_MB}MB")

            try:
                images = extract_images_by_column(
                    xlsx_bytes=contents,
                    image_col_letter=imageColumn,
                    name_col_letter=nameColumn,
                    max_images=MAX_IMAGES,
                )
            except ValueError as ve:
                raise HTTPException(status_code=400, detail=f"{original_name}: {ve}")
            except Exception as exc:  # pragma: no cover - generic safety net
                return JSONResponse(status_code=500, content={"detail": f"Processing failed for {original_name}: {exc}"})

            if not images:
                # Skip empty files but continue others
                continue

            folder = _safe_folder_name(original_name)
            for img_filename, png_bytes in images:
                zf.writestr(f"{folder}/{img_filename}", png_bytes)
            total_images += len(images)

    if total_images == 0:
        raise HTTPException(status_code=400, detail="No images found in the selected column(s) across uploaded files")

    zip_buffer.seek(0)
    headers = {
        "Content-Disposition": "attachment; filename=Bom2Pic_Images.zip",
        "X-Content-Type-Options": "nosniff",
    }
    return StreamingResponse(zip_buffer, media_type="application/zip", headers=headers)


if __name__ == "__main__":  # pragma: no cover
    import uvicorn

    uvicorn.run("app.main:app", host="0.0.0.0", port=8000, reload=True)


