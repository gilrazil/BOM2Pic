from pathlib import Path
from io import BytesIO
from typing import Optional

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

MAX_UPLOAD_MB = 20
MAX_IMAGES = 50


app = FastAPI(title="BOM2Pic", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
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


@app.post("/process")
async def process(
    file: UploadFile = File(..., description="Excel .xlsx file"),
    imageColumn: str = Form(..., min_length=1, max_length=2),
    nameColumn: str = Form(..., min_length=1, max_length=2),
):
    # Validate file extension
    filename = file.filename or "uploaded.xlsx"
    if not filename.lower().endswith(".xlsx"):
        raise HTTPException(status_code=400, detail="Only .xlsx files are supported")

    # Read content and check size
    contents = await file.read()
    size_mb = len(contents) / (1024 * 1024)
    if size_mb > MAX_UPLOAD_MB:
        raise HTTPException(status_code=400, detail=f"File too large. Max {MAX_UPLOAD_MB}MB")

    # Validate columns
    try:
        img_col_idx = column_letter_to_index(imageColumn)
        name_col_idx = column_letter_to_index(nameColumn)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid column letter(s)")

    try:
        images = extract_images_by_column(
            xlsx_bytes=contents,
            image_col_letter=imageColumn,
            name_col_letter=nameColumn,
            max_images=MAX_IMAGES,
        )
    except ValueError as ve:
        raise HTTPException(status_code=400, detail=str(ve))
    except Exception as exc:  # pragma: no cover - generic safety net
        return JSONResponse(status_code=500, content={"detail": f"Processing failed: {exc}"})

    if not images:
        raise HTTPException(status_code=400, detail="No images found in the selected column")

    # Create ZIP in-memory
    import zipfile

    zip_buffer = BytesIO()
    with zipfile.ZipFile(zip_buffer, mode="w", compression=zipfile.ZIP_DEFLATED) as zf:
        for filename, png_bytes in images:
            zf.writestr(filename, png_bytes)

    zip_buffer.seek(0)
    headers = {
        "Content-Disposition": "attachment; filename=Bom2Pic_Images.zip",
        "X-Content-Type-Options": "nosniff",
    }
    return StreamingResponse(zip_buffer, media_type="application/zip", headers=headers)


if __name__ == "__main__":  # pragma: no cover
    import uvicorn

    uvicorn.run("app.main:app", host="0.0.0.0", port=8000, reload=True)


