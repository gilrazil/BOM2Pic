"""
PayPal webhook handlers for BOM2Pic.
Processes subscription events and updates user plans.
"""
import os
import logging
import json
from typing import Dict, Any
import httpx
from fastapi import Request, HTTPException, status

from ..auth.supabase_auth import supabase

logger = logging.getLogger(__name__)

PAYPAL_WEBHOOK_ID = os.getenv("PAYPAL_WEBHOOK_ID")
PAYPAL_CLIENT_ID = os.getenv("PAYPAL_CLIENT_ID")
PAYPAL_CLIENT_SECRET = os.getenv("PAYPAL_CLIENT_SECRET")
PAYPAL_ENVIRONMENT = os.getenv("PAYPAL_ENVIRONMENT", "sandbox")


async def handle_paypal_webhook(request: Request) -> Dict[str, str]:
    """
    Handle incoming PayPal webhook events.
    
    Args:
        request: FastAPI request object
        
    Returns:
        Success response
    """
    # Get headers and body
    headers = dict(request.headers)
    body = await request.body()
    
    try:
        # Parse the JSON payload
        event_data = json.loads(body.decode('utf-8'))
        event_type = event_data.get('event_type', '')
        
        logger.info(f"Received PayPal webhook: {event_type}")
        
        # For now, we'll handle basic subscription events
        # PayPal webhook verification is more complex and would require additional setup
        
        # Handle the event
        await process_paypal_webhook_event(event_data)
        logger.info(f"Successfully processed PayPal webhook event: {event_type}")
        return {"status": "success"}
        
    except json.JSONDecodeError:
        logger.error("Invalid JSON payload in PayPal webhook")
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Invalid JSON payload"
        )
    except Exception as e:
        logger.error(f"Failed to process PayPal webhook event: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="Failed to process webhook"
        )


async def process_paypal_webhook_event(event: Dict[str, Any]) -> None:
    """
    Process a specific webhook event.
    
    Args:
        event: Stripe webhook event
    """
    event_type = event['type']
    data = event['data']['object']
    
    if event_type == 'customer.subscription.created':
        await handle_subscription_created(data)
    elif event_type == 'customer.subscription.updated':
        await handle_subscription_updated(data)
    elif event_type == 'customer.subscription.deleted':
        await handle_subscription_deleted(data)
    elif event_type == 'invoice.payment_succeeded':
        await handle_payment_succeeded(data)
    elif event_type == 'invoice.payment_failed':
        await handle_payment_failed(data)
    else:
        logger.info(f"Unhandled webhook event type: {event_type}")


async def handle_subscription_created(subscription: Dict[str, Any]) -> None:
    """
    Handle subscription creation.
    
    Args:
        subscription: Stripe subscription object
    """
    customer_id = subscription['customer']
    subscription_id = subscription['id']
    status = subscription['status']
    
    # Get plan from metadata or price ID
    plan = get_plan_from_subscription(subscription)
    
    if plan:
        await update_user_subscription(
            customer_id=customer_id,
            subscription_id=subscription_id,
            plan=plan,
            status=status
        )
        logger.info(f"Created subscription {subscription_id} for customer {customer_id}, plan: {plan}")


async def handle_subscription_updated(subscription: Dict[str, Any]) -> None:
    """
    Handle subscription updates.
    
    Args:
        subscription: Stripe subscription object
    """
    customer_id = subscription['customer']
    subscription_id = subscription['id']
    status = subscription['status']
    
    # Get plan from subscription
    plan = get_plan_from_subscription(subscription)
    
    if plan:
        await update_user_subscription(
            customer_id=customer_id,
            subscription_id=subscription_id,
            plan=plan,
            status=status
        )
        logger.info(f"Updated subscription {subscription_id} for customer {customer_id}, plan: {plan}, status: {status}")


async def handle_subscription_deleted(subscription: Dict[str, Any]) -> None:
    """
    Handle subscription cancellation.
    
    Args:
        subscription: Stripe subscription object
    """
    customer_id = subscription['customer']
    subscription_id = subscription['id']
    
    # Revert to free plan
    await update_user_subscription(
        customer_id=customer_id,
        subscription_id=None,
        plan='free',
        status='cancelled'
    )
    logger.info(f"Cancelled subscription {subscription_id} for customer {customer_id}")


async def handle_payment_succeeded(invoice: Dict[str, Any]) -> None:
    """
    Handle successful payment.
    
    Args:
        invoice: Stripe invoice object
    """
    customer_id = invoice['customer']
    subscription_id = invoice['subscription']
    
    logger.info(f"Payment succeeded for customer {customer_id}, subscription {subscription_id}")
    
    # Could add logic here to send confirmation emails, etc.


async def handle_payment_failed(invoice: Dict[str, Any]) -> None:
    """
    Handle failed payment.
    
    Args:
        invoice: Stripe invoice object
    """
    customer_id = invoice['customer']
    subscription_id = invoice['subscription']
    
    logger.warning(f"Payment failed for customer {customer_id}, subscription {subscription_id}")
    
    # Could add logic here to send payment failure notifications, etc.


def get_plan_from_subscription(subscription: Dict[str, Any]) -> str:
    """
    Extract plan name from Stripe subscription.
    
    Args:
        subscription: Stripe subscription object
        
    Returns:
        Plan name or 'free' as default
    """
    # Try to get plan from metadata
    metadata = subscription.get('metadata', {})
    if 'plan' in metadata:
        return metadata['plan']
    
    # Try to get plan from price ID
    items = subscription.get('items', {}).get('data', [])
    if items:
        price_id = items[0].get('price', {}).get('id', '')
        
        # Map price IDs to plan names
        price_to_plan = {
            'price_basic_monthly': 'basic',
            'price_pro_monthly': 'pro',
            'price_pro_plus_monthly': 'pro_plus'
        }
        
        return price_to_plan.get(price_id, 'free')
    
    return 'free'


async def update_user_subscription(
    customer_id: str,
    subscription_id: str = None,
    plan: str = 'free',
    status: str = 'active'
) -> None:
    """
    Update user's subscription information in database.
    
    Args:
        customer_id: Stripe customer ID
        subscription_id: Stripe subscription ID
        plan: Plan name
        status: Subscription status
    """
    if not supabase:
        logger.error("Supabase client not configured")
        return
    
    try:
        # Update user record
        response = supabase.table("users").update({
            "plan": plan,
            "stripe_subscription_id": subscription_id,
            "subscription_status": status
        }).eq("stripe_customer_id", customer_id).execute()
        
        if response.data:
            logger.info(f"Updated user subscription: customer={customer_id}, plan={plan}, status={status}")
        else:
            logger.warning(f"No user found with stripe_customer_id: {customer_id}")
            
    except Exception as e:
        logger.error(f"Failed to update user subscription: {e}")
        raise
