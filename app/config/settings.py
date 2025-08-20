from pathlib import Path
import os
from typing import List

# Directory paths
APP_DIR = Path(__file__).parent.parent
STATIC_DIR = APP_DIR / "static"
LOGO_DIR = APP_DIR.parent / "Logo"

# Configuration settings
class Settings:
    # File limits
    MAX_UPLOAD_MB: int = int(os.getenv("MAX_UPLOAD_MB", "20"))
    
    # Image/file limits (0 = unlimited)
    MAX_IMAGES: int = 0
    MAX_FILES: int = 0
    
    # Supabase configuration
    SUPABASE_URL: str = os.getenv("SUPABASE_URL", "")
    SUPABASE_SERVICE_ROLE_KEY: str = os.getenv("SUPABASE_SERVICE_ROLE_KEY", "")
    SUPABASE_ANON_KEY: str = os.getenv("SUPABASE_ANON_KEY", "")
    SUPABASE_JWT_SECRET: str = os.getenv("SUPABASE_JWT_SECRET", "")
    
    # PayPal configuration (replacing Stripe)
    PAYPAL_CLIENT_ID: str = os.getenv("PAYPAL_CLIENT_ID", "")
    PAYPAL_CLIENT_SECRET: str = os.getenv("PAYPAL_CLIENT_SECRET", "")
    PAYPAL_ENVIRONMENT: str = os.getenv("PAYPAL_ENVIRONMENT", "sandbox")
    PAYPAL_WEBHOOK_ID: str = os.getenv("PAYPAL_WEBHOOK_ID", "")
    
    def __init__(self):
        # Parse MAX_IMAGES
        max_images_env = os.getenv("MAX_IMAGES")
        if max_images_env and max_images_env.isdigit():
            self.MAX_IMAGES = int(max_images_env)
            
        # Parse MAX_FILES  
        max_files_env = os.getenv("MAX_FILES")
        if max_files_env and max_files_env.isdigit():
            self.MAX_FILES = int(max_files_env)
    
    def get_allowed_origins(self) -> List[str]:
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
        origins: List[str] = []
        if render_url:
            origins.append(render_url.rstrip("/"))

        # Local development defaults
        origins.extend([
            "http://localhost:8000",
            "http://127.0.0.1:8000",
            "http://localhost:3000",
        ])
        return origins

# Global settings instance
settings = Settings()
