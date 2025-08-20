"""
PayPal integration for BOM2Pic billing.
Handles subscription management and payments.
"""
import os
import logging
import base64
from typing import Dict, Any, Optional
import httpx
from fastapi import HTTPException, status

logger = logging.getLogger(__name__)

# PayPal configuration
PAYPAL_CLIENT_ID = os.getenv("PAYPAL_CLIENT_ID")
PAYPAL_CLIENT_SECRET = os.getenv("PAYPAL_CLIENT_SECRET")
PAYPAL_ENVIRONMENT = os.getenv("PAYPAL_ENVIRONMENT", "sandbox")  # sandbox or live

# PayPal API URLs
PAYPAL_BASE_URL = {
    "sandbox": "https://api-m.sandbox.paypal.com",
    "live": "https://api-m.paypal.com"
}

if not all([PAYPAL_CLIENT_ID, PAYPAL_CLIENT_SECRET]):
    logger.warning("PayPal credentials not fully configured")

# Plan configuration matching our pricing
PAYPAL_PLANS = {
    "basic": {
        "name": "Basic",
        "price": 9,
        "monthly_images": 5000,
        "features": [
            "5,000 images per month",
            "Unlimited file uploads",
            "Email support"
        ]
    },
    "pro": {
        "name": "Pro",
        "price": 29,
        "monthly_images": 25000,
        "features": [
            "25,000 images per month",
            "Unlimited file uploads",
            "Priority processing",
            "Email support"
        ]
    },
    "pro_plus": {
        "name": "Pro+",
        "price": 49,
        "monthly_images": 999999,  # Unlimited
        "features": [
            "Unlimited images",
            "Unlimited file uploads",
            "Priority processing",
            "Priority email support",
            "Advanced features"
        ]
    }
}


async def get_paypal_access_token() -> str:
    """
    Get PayPal access token for API requests.
    
    Returns:
        Access token string
    """
    if not all([PAYPAL_CLIENT_ID, PAYPAL_CLIENT_SECRET]):
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="PayPal credentials not configured"
        )
    
    # Create basic auth header
    auth_string = f"{PAYPAL_CLIENT_ID}:{PAYPAL_CLIENT_SECRET}"
    auth_bytes = auth_string.encode('ascii')
    auth_header = base64.b64encode(auth_bytes).decode('ascii')
    
    headers = {
        "Accept": "application/json",
        "Accept-Language": "en_US",
        "Authorization": f"Basic {auth_header}"
    }
    
    data = "grant_type=client_credentials"
    
    try:
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{PAYPAL_BASE_URL[PAYPAL_ENVIRONMENT]}/v1/oauth2/token",
                headers=headers,
                content=data
            )
            
            if response.status_code == 200:
                token_data = response.json()
                return token_data["access_token"]
            else:
                logger.error(f"Failed to get PayPal access token: {response.text}")
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail="Failed to authenticate with PayPal"
                )
                
    except httpx.RequestError as e:
        logger.error(f"PayPal authentication request failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to connect to PayPal"
        )


def create_paypal_customer(email: str, name: str = None) -> Dict[str, Any]:
    """
    Create a PayPal customer (for compatibility with Stripe interface).
    PayPal doesn't require pre-creating customers, so we return a mock customer.
    
    Args:
        email: Customer email
        name: Customer name (optional)
        
    Returns:
        Mock customer object for compatibility
    """
    logger.info(f"Creating PayPal customer for {email}")
    
    # PayPal doesn't require pre-creating customers like Stripe
    # We return a mock customer object for compatibility
    return {
        "id": f"paypal_customer_{email.replace('@', '_').replace('.', '_')}",
        "email": email,
        "name": name,
        "created": True
    }


async def create_checkout_session(
    customer_id: str, 
    plan: str, 
    success_url: str, 
    cancel_url: str
) -> Dict[str, Any]:
    """
    Create a PayPal subscription for the user.
    
    Args:
        customer_id: Customer identifier (email-based for PayPal)
        plan: Plan name (basic, pro, pro_plus)
        success_url: URL to redirect after successful payment
        cancel_url: URL to redirect after cancelled payment
        
    Returns:
        PayPal subscription approval URL
    """
    if plan not in PAYPAL_PLANS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid plan: {plan}"
        )
    
    plan_info = PAYPAL_PLANS[plan]
    access_token = await get_paypal_access_token()
    
    # Create subscription payload
    subscription_data = {
        "plan_id": f"P-{plan.upper()}-BOM2PIC",  # We'll create these plan IDs
        "start_time": "2024-01-01T00:00:00Z",  # Immediate start
        "quantity": "1",
        "shipping_amount": {
            "currency_code": "USD",
            "value": "0.00"
        },
        "subscriber": {
            "name": {
                "given_name": customer_id.split('@')[0],
                "surname": "User"
            },
            "email_address": customer_id if '@' in customer_id else f"{customer_id}@example.com"
        },
        "application_context": {
            "brand_name": "BOM2Pic",
            "locale": "en-US",
            "shipping_preference": "NO_SHIPPING",
            "user_action": "SUBSCRIBE_NOW",
            "payment_method": {
                "payer_selected": "PAYPAL",
                "payee_preferred": "IMMEDIATE_PAYMENT_REQUIRED"
            },
            "return_url": success_url,
            "cancel_url": cancel_url
        }
    }
    
    headers = {
        "Content-Type": "application/json",
        "Authorization": f"Bearer {access_token}",
        "Accept": "application/json",
        "PayPal-Request-Id": f"BOM2PIC-{plan}-{hash(customer_id)}"
    }
    
    try:
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{PAYPAL_BASE_URL[PAYPAL_ENVIRONMENT]}/v1/billing/subscriptions",
                json=subscription_data,
                headers=headers
            )
            
            if response.status_code in [200, 201]:
                subscription = response.json()
                
                # Find approval URL
                approval_url = None
                for link in subscription.get("links", []):
                    if link.get("rel") == "approve":
                        approval_url = link.get("href")
                        break
                
                if approval_url:
                    logger.info(f"Created PayPal subscription: {subscription.get('id')} for plan: {plan}")
                    return {
                        "url": approval_url,
                        "id": subscription.get("id"),
                        "status": subscription.get("status")
                    }
                else:
                    raise HTTPException(
                        status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                        detail="PayPal subscription created but no approval URL found"
                    )
            else:
                logger.error(f"Failed to create PayPal subscription: {response.text}")
                raise HTTPException(
                    status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                    detail="Failed to create PayPal subscription"
                )
                
    except httpx.RequestError as e:
        logger.error(f"PayPal subscription request failed: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to connect to PayPal"
        )


def create_billing_portal_session(customer_id: str, return_url: str) -> Dict[str, Any]:
    """
    Create a PayPal billing management URL for customer.
    
    Args:
        customer_id: Customer identifier
        return_url: URL to return to after managing subscription
        
    Returns:
        PayPal billing management URL
    """
    # PayPal doesn't have a centralized billing portal like Stripe
    # Users manage subscriptions through their PayPal account
    logger.info(f"Directing customer {customer_id} to PayPal account management")
    
    return {
        "url": f"https://www.paypal.com/myaccount/autopay/?return_url={return_url}",
        "message": "Manage your subscription through your PayPal account"
    }


async def get_customer_subscriptions(customer_id: str) -> list:
    """
    Get active subscriptions for a customer.
    Note: PayPal doesn't provide easy customer-based subscription lookup.
    This is a simplified implementation.
    
    Args:
        customer_id: Customer identifier
        
    Returns:
        List of active subscriptions (simplified for PayPal)
    """
    logger.info(f"Getting subscriptions for customer: {customer_id}")
    
    # PayPal's subscription API is different - we'd need to store subscription IDs
    # For now, return empty list - this would be enhanced with proper storage
    return []


async def cancel_subscription(subscription_id: str) -> bool:
    """
    Cancel a PayPal subscription.
    
    Args:
        subscription_id: PayPal subscription ID
        
    Returns:
        True if cancelled successfully
    """
    try:
        access_token = await get_paypal_access_token()
        
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {access_token}",
            "Accept": "application/json"
        }
        
        cancel_data = {
            "reason": "User requested cancellation"
        }
        
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{PAYPAL_BASE_URL[PAYPAL_ENVIRONMENT]}/v1/billing/subscriptions/{subscription_id}/cancel",
                json=cancel_data,
                headers=headers
            )
            
            if response.status_code == 204:
                logger.info(f"Cancelled PayPal subscription: {subscription_id}")
                return True
            else:
                logger.error(f"Failed to cancel PayPal subscription: {response.text}")
                return False
                
    except Exception as e:
        logger.error(f"Failed to cancel PayPal subscription: {e}")
        return False


def get_plan_info(plan: str) -> Optional[Dict[str, Any]]:
    """
    Get information about a specific plan.
    
    Args:
        plan: Plan name
        
    Returns:
        Plan information dict or None
    """
    return PAYPAL_PLANS.get(plan)


def get_all_plans() -> Dict[str, Any]:
    """
    Get information about all available plans.
    
    Returns:
        Dict of all plans
    """
    return PAYPAL_PLANS


# Compatibility aliases for existing code
create_stripe_customer = create_paypal_customer
