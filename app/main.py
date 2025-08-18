from typing import List

from fastapi import FastAPI, File, UploadFile, Form, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, StreamingResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from .config.settings import settings, STATIC_DIR, LOGO_DIR
from .services.image_processor import ImageProcessor
from .utils.excel_image_extractor import column_letter_to_index
from .models.schemas import HealthResponse

# Initialize FastAPI app
app = FastAPI(title="BOM2Pic", version="0.1.0")

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.get_allowed_origins(),
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount static files
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")
if LOGO_DIR.exists():
    app.mount("/Logo", StaticFiles(directory=LOGO_DIR), name="logo")


@app.get("/", include_in_schema=False)
def root() -> FileResponse:
    """Serve the main application page."""
    index_path = STATIC_DIR / "index.html"
    return FileResponse(index_path)


@app.get("/favicon.ico", include_in_schema=False)
def favicon() -> FileResponse:
    """Serve favicon using the logo."""
    logo_png = LOGO_DIR / "BOM2Pic_Logo.png"
    if logo_png.exists():
        return FileResponse(logo_png)
    raise HTTPException(status_code=404, detail="favicon not available")


@app.get("/health", include_in_schema=False, response_model=HealthResponse)
def health() -> JSONResponse:
    """Health check endpoint."""
    return JSONResponse(content={"status": "ok"})


@app.post("/process")
async def process(
    files: List[UploadFile] = File(..., description="One or more Excel .xlsx files"),
    imageColumn: str = Form(..., min_length=1, max_length=2, description="Column letter containing images"),
    nameColumn: str = Form(..., min_length=1, max_length=2, description="Column letter containing names/IDs"),
):
    """Process Excel files and extract images."""
    
    # Validate request
    _validate_request(files, imageColumn, nameColumn)
    
    # Initialize processor
    processor = ImageProcessor()
    processed_files = []
    
    # Process each file
    for upload in files:
        original_name = upload.filename or "uploaded.xlsx"
        
        # Validate file
        if not original_name.lower().endswith(".xlsx"):
            raise HTTPException(status_code=400, detail=f"Only .xlsx files are supported (got {original_name})")
        
        contents = await upload.read()
        size_mb = len(contents) / (1024 * 1024)
        if size_mb > settings.MAX_UPLOAD_MB:
            raise HTTPException(status_code=400, detail=f"{original_name}: File too large. Max {settings.MAX_UPLOAD_MB}MB")
        
        # Process file
        try:
            file_items = processor.process_excel_file(contents, original_name, imageColumn, nameColumn)
            if file_items:
                processed_files.append(file_items)
        except ValueError as ve:
            raise HTTPException(status_code=400, detail=f"{original_name}: {ve}")
        except Exception as exc:
            return JSONResponse(status_code=500, content={"detail": f"Processing failed for {original_name}: {exc}"})
    
    # Check if any images were found
    if processor.total_images == 0:
        raise HTTPException(status_code=400, detail="No images found in the selected column(s) across uploaded files")
    
    # Create ZIP and return response
    zip_buffer = processor.create_zip(processed_files)
    headers = processor.get_response_headers()
    
    return StreamingResponse(zip_buffer, media_type="application/zip", headers=headers)


def _validate_request(files: List[UploadFile], image_column: str, name_column: str):
    """Validate the processing request."""
    if not files:
        raise HTTPException(status_code=400, detail="No files uploaded")
    
    if settings.MAX_FILES and settings.MAX_FILES > 0 and len(files) > settings.MAX_FILES:
        raise HTTPException(status_code=400, detail=f"Too many files. Max {settings.MAX_FILES}")
    
    # Validate column letters
    try:
        column_letter_to_index(image_column)
        column_letter_to_index(name_column)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid column letter(s)")


if __name__ == "__main__":  # pragma: no cover
    import uvicorn
    uvicorn.run("app.main:app", host="0.0.0.0", port=8000, reload=True)