"""
Authentication middleware for BOM2Pic.
Handles JWT verification and user context.
"""
import logging
from typing import Optional
from fastapi import Request, HTTPException, status
from starlette.middleware.base import BaseHTTPMiddleware

from .supabase_auth import verify_supabase_jwt, create_user_if_not_exists

logger = logging.getLogger(__name__)


class AuthMiddleware(BaseHTTPMiddleware):
    """
    Middleware to handle authentication for protected routes.
    """
    
    def __init__(self, app, protected_paths: list = None):
        super().__init__(app)
        self.protected_paths = protected_paths or ["/process"]
    
    async def dispatch(self, request: Request, call_next):
        """
        Process request and add user context if authenticated.
        """
        # Skip auth for non-protected paths
        if not any(request.url.path.startswith(path) for path in self.protected_paths):
            return await call_next(request)
        
        # Initialize user context
        request.state.user = None
        request.state.authenticated = False
        
        # Check for Authorization header
        auth_header = request.headers.get("Authorization")
        if auth_header:
            user_info = verify_supabase_jwt(auth_header)
            
            if user_info:
                try:
                    # Ensure user exists in our database
                    user = create_user_if_not_exists(
                        user_info["user_id"], 
                        user_info["email"]
                    )
                    
                    # Add user context to request
                    request.state.user = user
                    request.state.authenticated = True
                    request.state.user_id = user["id"]
                    
                    logger.debug(f"Authenticated user: {user['email']}")
                    
                except Exception as e:
                    logger.error(f"Error setting up user context: {e}")
                    # Continue as unauthenticated user
        
        # Continue with request
        return await call_next(request)


def get_current_user(request: Request) -> Optional[dict]:
    """
    Get current authenticated user from request state.
    
    Args:
        request: FastAPI request object
        
    Returns:
        User dict if authenticated, None otherwise
    """
    return getattr(request.state, "user", None)


def get_current_user_id(request: Request) -> Optional[str]:
    """
    Get current user ID from request state.
    
    Args:
        request: FastAPI request object
        
    Returns:
        User ID string if authenticated, None otherwise
    """
    return getattr(request.state, "user_id", None)


def is_authenticated(request: Request) -> bool:
    """
    Check if request is from authenticated user.
    
    Args:
        request: FastAPI request object
        
    Returns:
        True if authenticated, False otherwise
    """
    return getattr(request.state, "authenticated", False)
