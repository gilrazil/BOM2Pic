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
    extract_images_details,
)


APP_DIR = Path(__file__).parent
STATIC_DIR = APP_DIR / "static"
LOGO_DIR = APP_DIR.parent / "Logo"

# Limits can be overridden via environment variables
MAX_UPLOAD_MB = int(os.getenv("MAX_UPLOAD_MB", "20"))
# Unlimited images/files by default; enable limits only if env vars are set to positive integers
MAX_IMAGES_ENV = os.getenv("MAX_IMAGES")
MAX_IMAGES = int(MAX_IMAGES_ENV) if (MAX_IMAGES_ENV and MAX_IMAGES_ENV.isdigit()) else 0
MAX_FILES_ENV = os.getenv("MAX_FILES")
MAX_FILES = int(MAX_FILES_ENV) if (MAX_FILES_ENV and MAX_FILES_ENV.isdigit()) else 0


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
    if MAX_FILES and MAX_FILES > 0 and len(files) > MAX_FILES:
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

    # Create ZIP in-memory aggregating all files into a single images/ folder
    import zipfile
    import csv
    import hashlib
    from datetime import datetime

    def sha1hex(b: bytes) -> str:
        return hashlib.sha1(b).hexdigest()

    def detect_extension(image_bytes: bytes) -> str:
        try:
            from PIL import Image

            with Image.open(BytesIO(image_bytes)) as im:
                fmt = (im.format or "PNG").lower()
        except Exception:
            fmt = "png"
        # Normalize common formats
        mapping = {
            "jpeg": "jpg",
            "jpg": "jpg",
            "png": "png",
            "webp": "webp",
            "gif": "gif",
            "tiff": "tif",
            "bmp": "bmp",
        }
        return mapping.get(fmt, "png")

    def normalize(name: str) -> str:
        # Trim and replace spaces
        n = (name or "").strip()
        n = n.replace(" ", "_")
        # Remove illegal characters \/:*?"<>|
        n = re.sub(r"[\\/:*?\"<>|]+", "", n)
        # Collapse repeated underscores
        n = re.sub(r"_+", "_", n)
        # Lowercase
        n = n.lower()
        # Limit to 80 characters
        return n[:80] or "image"

    total_images = 0
    written = overwritten_same = overwritten_diff = 0
    seen: dict[str, str] = {}
    manifest_rows: list[tuple[str, str, int, str, str, str]] = []

    zip_buffer = BytesIO()
    with zipfile.ZipFile(zip_buffer, mode="w", compression=zipfile.ZIP_DEFLATED, compresslevel=7) as zf:
        # Add a placeholder so images/ exists early (not strictly required)
        images_dir = "images/"
        # Process in the order provided by the user; fallback to filename alphabetical
        ordered_uploads = files if files else []
        if not ordered_uploads:
            pass
        else:
            # Ensure stable fallback if client reorders: use original list, otherwise sort by filename
            try:
                ordered_uploads = files
            except Exception:
                ordered_uploads = sorted(files, key=lambda u: (u.filename or ""))

        for upload in ordered_uploads:
            original_name = upload.filename or "uploaded.xlsx"
            if not original_name.lower().endswith(".xlsx"):
                raise HTTPException(status_code=400, detail=f"Only .xlsx files are supported (got {original_name})")

            contents = await upload.read()
            size_mb = len(contents) / (1024 * 1024)
            if size_mb > MAX_UPLOAD_MB:
                raise HTTPException(status_code=400, detail=f"{original_name}: File too large. Max {MAX_UPLOAD_MB}MB")

            try:
                details = extract_images_details(
                    xlsx_bytes=contents,
                    image_col_letter=imageColumn,
                    name_col_letter=nameColumn,
                    max_images=MAX_IMAGES if MAX_IMAGES > 0 else None,
                )
            except ValueError as ve:
                raise HTTPException(status_code=400, detail=f"{original_name}: {ve}")
            except Exception as exc:  # pragma: no cover - generic safety net
                return JSONResponse(status_code=500, content={"detail": f"Processing failed for {original_name}: {exc}"})

            if not details:
                # Skip empty files but continue others
                continue

            for item in details:
                # Normalize name and detect extension
                base = normalize(item.name_raw)
                ext = detect_extension(item.image_bytes)
                final_name = f"{base}.{ext}"
                digest = sha1hex(item.image_bytes)
                action = "written"
                if final_name in seen:
                    if seen[final_name] == digest:
                        action = "overwritten_same"
                        overwritten_same += 1
                    else:
                        action = "overwritten_diff"
                        overwritten_diff += 1
                else:
                    written += 1
                seen[final_name] = digest

                zf.writestr(f"{images_dir}{final_name}", item.image_bytes)
                manifest_rows.append((original_name, item.sheet, item.row, final_name, digest, action))
                total_images += 1

    if total_images == 0:
        raise HTTPException(status_code=400, detail="No images found in the selected column(s) across uploaded files")

    # Write report.csv at root
    # Reopen in append mode to add the manifest after iterating
    with zipfile.ZipFile(zip_buffer, mode="a", compression=zipfile.ZIP_DEFLATED, compresslevel=7) as zf:
        output = []
        output.append("source_file,sheet,row,final_name,hash,action\n")
        for r in manifest_rows:
            source_file, sheet, rownum, final_name, digest, action = r
            output.append(f"{source_file},{sheet},{rownum},{final_name},{digest},{action}\n")
        zf.writestr("report.csv", "".join(output))

    # Timestamped filename
    timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
    zip_buffer.seek(0)
    headers = {
        "Content-Disposition": f"attachment; filename=bom2pic_{timestamp}.zip",
        "X-Content-Type-Options": "nosniff",
        # Summary counts for UI
        "X-B2P-Written": str(written),
        "X-B2P-Overwritten-Same": str(overwritten_same),
        "X-B2P-Overwritten-Diff": str(overwritten_diff),
        "X-B2P-Total": str(total_images),
    }
    return StreamingResponse(zip_buffer, media_type="application/zip", headers=headers)


if __name__ == "__main__":  # pragma: no cover
    import uvicorn

    uvicorn.run("app.main:app", host="0.0.0.0", port=8000, reload=True)


