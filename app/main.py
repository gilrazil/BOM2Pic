from typing import List
import logging

from fastapi import FastAPI, File, UploadFile, Form, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, StreamingResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from .config.settings import settings, STATIC_DIR, LOGO_DIR
from .services.image_processor import ImageProcessor
from .utils.excel_image_extractor import column_letter_to_index
from .models.schemas import HealthResponse
from .auth.middleware import AuthMiddleware, get_current_user_id, is_authenticated, get_current_user
from .auth.supabase_auth import get_user_plan_limits
from .billing.stripe_client import create_checkout_session, create_billing_portal_session, get_all_plans, create_paypal_customer
from .billing.webhooks import handle_paypal_webhook

logger = logging.getLogger(__name__)

# Initialize FastAPI app
app = FastAPI(title="BOM2Pic", version="0.1.0")

# Add authentication middleware
app.add_middleware(AuthMiddleware, protected_paths=["/process"])

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


@app.get("/api/plans")
def get_plans():
    """Get available subscription plans."""
    return {"plans": get_all_plans()}


@app.post("/api/create-checkout-session")
async def create_checkout(request: Request):
    """Create PayPal checkout session for subscription."""
    user = get_current_user(request)
    if not user:
        raise HTTPException(status_code=401, detail="Authentication required")
    
    data = await request.json()
    plan = data.get("plan")
    
    if not plan:
        raise HTTPException(status_code=400, detail="Plan is required")
    
    # Create PayPal customer if needed
    paypal_customer_id = user.get("stripe_customer_id")  # Reusing field for compatibility
    if not paypal_customer_id:
        customer = create_paypal_customer(user["email"])
        paypal_customer_id = customer["id"]
        
        # Update user with customer ID (simplified - should use proper update function)
        # TODO: Implement proper user update function
    
    # Create checkout session
    success_url = f"{request.url.scheme}://{request.url.netloc}/?session_id={{CHECKOUT_SESSION_ID}}"
    cancel_url = f"{request.url.scheme}://{request.url.netloc}/"
    
    session = await create_checkout_session(
        customer_id=paypal_customer_id,
        plan=plan,
        success_url=success_url,
        cancel_url=cancel_url
    )
    
    return {"checkout_url": session["url"]}


@app.post("/api/create-portal-session")
async def create_portal(request: Request):
    """Create PayPal billing portal session."""
    user = get_current_user(request)
    if not user:
        raise HTTPException(status_code=401, detail="Authentication required")
    
    paypal_customer_id = user.get("stripe_customer_id")  # Reusing field for compatibility
    if not paypal_customer_id:
        raise HTTPException(status_code=400, detail="No billing account found")
    
    return_url = f"{request.url.scheme}://{request.url.netloc}/"
    
    session = create_billing_portal_session(
        customer_id=paypal_customer_id,
        return_url=return_url
    )
    
    return {"portal_url": session["url"]}


@app.post("/webhooks/paypal")
async def paypal_webhook(request: Request):
    """Handle PayPal webhook events."""
    return await handle_paypal_webhook(request)


@app.post("/process")
async def process(
    request: Request,
    files: List[UploadFile] = File(..., description="One or more Excel .xlsx files"),
    imageColumn: str = Form(..., min_length=1, max_length=2, description="Column letter containing images"),
    nameColumn: str = Form(..., min_length=1, max_length=2, description="Column letter containing names/IDs"),
):
    """Process Excel files and extract images."""
    
    # Validate request
    _validate_request(files, imageColumn, nameColumn)
    
    # Get user context and plan limits
    user_id = get_current_user_id(request)
    authenticated = is_authenticated(request)
    
    if authenticated and user_id:
        # Get user's plan limits
        plan_info = get_user_plan_limits(user_id)
        monthly_limit = plan_info["monthly_images"]
        plan_name = plan_info["name"].lower()
        
        # TODO: Check current monthly usage and enforce limits
        # For now, we'll implement the basic quota system
        logger.info(f"Processing for authenticated user {user_id}, plan: {plan_name}, limit: {monthly_limit}")
    else:
        # Anonymous user - demo limits (will be implemented)
        plan_name = "demo"
        monthly_limit = 10  # Demo: 10 images per file
        logger.info("Processing for anonymous user (demo mode)")
    
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
    
    # Add plan information to headers
    headers["X-B2P-Plan"] = plan_name
    headers["X-B2P-User-Authenticated"] = str(authenticated).lower()
    
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