"""
Supabase authentication utilities for BOM2Pic.
Handles JWT verification and user management.
"""
import os
import logging
from typing import Optional, Dict, Any
from jose import jwt, JWTError
from supabase import create_client, Client
from fastapi import HTTPException, status

logger = logging.getLogger(__name__)

# Supabase configuration
SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_SERVICE_ROLE_KEY = os.getenv("SUPABASE_SERVICE_ROLE_KEY") 
SUPABASE_ANON_KEY = os.getenv("SUPABASE_ANON_KEY")
SUPABASE_JWT_SECRET = os.getenv("SUPABASE_JWT_SECRET")

if not all([SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY, SUPABASE_ANON_KEY]):
    logger.warning("Supabase environment variables not fully configured")

# Create Supabase client with service role (for server-side operations)
supabase: Optional[Client] = None
if SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY:
    supabase = create_client(SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY)


def verify_supabase_jwt(token: str) -> Optional[Dict[str, Any]]:
    """
    Verify Supabase JWT token and return user info.
    
    Args:
        token: JWT token from Authorization header
        
    Returns:
        User info dict if valid, None if invalid
    """
    if not token or not SUPABASE_JWT_SECRET:
        return None
        
    try:
        # Remove 'Bearer ' prefix if present
        if token.startswith('Bearer '):
            token = token[7:]
            
        # Decode JWT
        payload = jwt.decode(
            token,
            SUPABASE_JWT_SECRET,
            algorithms=["HS256"],
            audience="authenticated"
        )
        
        return {
            "user_id": payload.get("sub"),
            "email": payload.get("email"),
            "role": payload.get("role", "authenticated")
        }
        
    except JWTError as e:
        logger.warning(f"JWT verification failed: {e}")
        return None


def get_user_from_db(user_id: str) -> Optional[Dict[str, Any]]:
    """
    Get user information from database.
    
    Args:
        user_id: User UUID
        
    Returns:
        User data dict or None if not found
    """
    if not supabase:
        return None
        
    try:
        response = supabase.table("users").select("*").eq("id", user_id).execute()
        
        if response.data:
            return response.data[0]
        return None
        
    except Exception as e:
        logger.error(f"Error fetching user {user_id}: {e}")
        return None


def create_user_if_not_exists(user_id: str, email: str) -> Dict[str, Any]:
    """
    Create user record if it doesn't exist.
    
    Args:
        user_id: User UUID from Supabase auth
        email: User email
        
    Returns:
        User data dict
    """
    if not supabase:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Database not configured"
        )
    
    try:
        # Try to get existing user
        existing_user = get_user_from_db(user_id)
        if existing_user:
            return existing_user
            
        # Create new user with free plan
        user_data = {
            "id": user_id,
            "email": email,
            "plan": "free",
            "stripe_customer_id": None,
            "stripe_subscription_id": None,
            "subscription_status": "inactive"
        }
        
        response = supabase.table("users").insert(user_data).execute()
        
        if response.data:
            logger.info(f"Created new user: {email}")
            return response.data[0]
        else:
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail="Failed to create user"
            )
            
    except Exception as e:
        logger.error(f"Error creating user {email}: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to create user"
        )


def get_user_plan_limits(user_id: str) -> Dict[str, Any]:
    """
    Get user's current plan and limits.
    
    Args:
        user_id: User UUID
        
    Returns:
        Dict with plan info and limits
    """
    # Plan limits configuration
    PLAN_LIMITS = {
        "free": {
            "monthly_images": 200,
            "name": "Free",
            "price": 0
        },
        "basic": {
            "monthly_images": 5000,
            "name": "Basic",
            "price": 9
        },
        "pro": {
            "monthly_images": 25000,
            "name": "Pro", 
            "price": 29
        },
        "pro_plus": {
            "monthly_images": 999999,  # Unlimited
            "name": "Pro+",
            "price": 49
        }
    }
    
    user = get_user_from_db(user_id)
    if not user:
        # Default to free plan for unknown users
        return PLAN_LIMITS["free"]
    
    plan = user.get("plan", "free")
    return PLAN_LIMITS.get(plan, PLAN_LIMITS["free"])
