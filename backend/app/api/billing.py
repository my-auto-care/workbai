"""
Stripe subscription billing endpoints for Workbay AI.

Endpoints
---------
POST /billing/create-checkout-session
    Creates a Stripe Checkout Session for a shop subscription.
    Body: { "shop_id": "<uuid>", "success_url": "...", "cancel_url": "..." }

POST /billing/webhook
    Handles Stripe webhook events (raw body, Stripe-Signature header required).
    - checkout.session.completed  → sets shop.subscription_status = active
                                    stores stripe_customer_id on shop
    - customer.subscription.deleted → sets shop.subscription_status = canceled

GET /billing/portal/{shop_id}
    Returns a Stripe Customer Portal URL so the shop can manage their subscription.
"""

import os
import logging
from typing import Optional

import stripe
from fastapi import APIRouter, Depends, HTTPException, Request, Header
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.db.models import Shop, SubscriptionStatus

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/billing", tags=["billing"])

# ---------------------------------------------------------------------------
# Stripe configuration – keys are resolved at request time so the module can
# be imported even before the env vars are set (e.g. during test collection).
# ---------------------------------------------------------------------------

def _stripe_client() -> stripe:
    api_key = os.getenv("STRIPE_SECRET_KEY")
    if not api_key:
        raise HTTPException(status_code=500, detail="STRIPE_SECRET_KEY not configured")
    stripe.api_key = api_key
    return stripe


def _price_id() -> str:
    price_id = os.getenv("STRIPE_PRICE_ID")
    if not price_id:
        raise HTTPException(status_code=500, detail="STRIPE_PRICE_ID not configured")
    return price_id


def _webhook_secret() -> str:
    secret = os.getenv("STRIPE_WEBHOOK_SECRET")
    if not secret:
        raise HTTPException(status_code=500, detail="STRIPE_WEBHOOK_SECRET not configured")
    return secret


# ---------------------------------------------------------------------------
# Request / Response schemas
# ---------------------------------------------------------------------------

class CheckoutRequest(BaseModel):
    shop_id: str
    success_url: str = "https://app.workbay.ai/billing/success"
    cancel_url: str = "https://app.workbay.ai/billing/cancel"


class CheckoutResponse(BaseModel):
    checkout_url: str
    session_id: str


class PortalResponse(BaseModel):
    portal_url: str


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _get_shop_or_404(shop_id: str, db: Session) -> Shop:
    import uuid as _uuid
    try:
        uid = _uuid.UUID(shop_id)
    except ValueError:
        raise HTTPException(status_code=422, detail="Invalid shop_id UUID format")
    shop = db.get(Shop, uid)
    if not shop:
        raise HTTPException(status_code=404, detail=f"Shop {shop_id} not found")
    return shop


# ---------------------------------------------------------------------------
# POST /billing/create-checkout-session
# ---------------------------------------------------------------------------

@router.post("/create-checkout-session", response_model=CheckoutResponse, status_code=201)
async def create_checkout_session(
    body: CheckoutRequest,
    db: Session = Depends(get_db),
):
    """
    Create a Stripe Checkout Session for the given shop.

    If the shop already has a stripe_customer_id we attach it so Stripe
    pre-fills the customer details. The shop_id is stored in the session
    metadata so the webhook can look it up on completion.
    """
    _stripe_client()
    shop = _get_shop_or_404(body.shop_id, db)

    checkout_kwargs = dict(
        mode="subscription",
        line_items=[{"price": _price_id(), "quantity": 1}],
        success_url=body.success_url + "?session_id={CHECKOUT_SESSION_ID}",
        cancel_url=body.cancel_url,
        metadata={"shop_id": str(shop.id)},
        subscription_data={"metadata": {"shop_id": str(shop.id)}},
        client_reference_id=str(shop.id),
    )

    # Attach existing Stripe customer if we have one
    if shop.stripe_customer_id:
        checkout_kwargs["customer"] = shop.stripe_customer_id
    else:
        checkout_kwargs["customer_creation"] = "always"

    try:
        session = stripe.checkout.Session.create(**checkout_kwargs)
    except stripe.StripeError as exc:
        logger.error("Stripe checkout creation failed: %s", exc)
        raise HTTPException(status_code=502, detail=f"Stripe error: {exc.user_message}")

    logger.info("Created Stripe checkout session %s for shop %s", session.id, shop.id)
    return CheckoutResponse(checkout_url=session.url, session_id=session.id)


# ---------------------------------------------------------------------------
# POST /billing/webhook
# ---------------------------------------------------------------------------

@router.post("/webhook", status_code=200)
async def stripe_webhook(
    request: Request,
    stripe_signature: Optional[str] = Header(None, alias="stripe-signature"),
    db: Session = Depends(get_db),
):
    """
    Receive and verify Stripe webhook events.

    Handled events
    ~~~~~~~~~~~~~~
    checkout.session.completed
        * Stores the Stripe customer_id on the shop record.
        * Sets subscription_status -> active.

    customer.subscription.deleted
        * Sets subscription_status -> canceled.
    """
    _stripe_client()
    payload = await request.body()

    # Verify webhook signature
    try:
        event = stripe.Webhook.construct_event(
            payload=payload,
            sig_header=stripe_signature or "",
            secret=_webhook_secret(),
        )
    except stripe.SignatureVerificationError as exc:
        logger.warning("Stripe webhook signature verification failed: %s", exc)
        raise HTTPException(status_code=400, detail="Invalid Stripe signature")
    except Exception as exc:
        logger.error("Stripe webhook construction error: %s", exc)
        raise HTTPException(status_code=400, detail="Webhook payload error")

    event_type: str = event["type"]
    data_object = event["data"]["object"]

    logger.info("Received Stripe event: %s  id=%s", event_type, event["id"])

    # ------------------------------------------------------------------
    # checkout.session.completed
    # ------------------------------------------------------------------
    if event_type == "checkout.session.completed":
        shop_id: Optional[str] = (
            (data_object.get("metadata") or {}).get("shop_id")
            or data_object.get("client_reference_id")
        )
        customer_id: Optional[str] = data_object.get("customer")

        if not shop_id:
            logger.error("checkout.session.completed missing shop_id in metadata")
            return {"received": True, "warning": "missing shop_id"}

        try:
            import uuid as _uuid
            shop = db.get(Shop, _uuid.UUID(shop_id))
        except Exception:
            shop = None

        if not shop:
            logger.error("checkout.session.completed: shop %s not found", shop_id)
            return {"received": True, "warning": "shop not found"}

        if customer_id and not shop.stripe_customer_id:
            shop.stripe_customer_id = customer_id

        shop.subscription_status = SubscriptionStatus.active
        db.commit()
        logger.info(
            "Shop %s marked active (Stripe customer: %s)", shop_id, customer_id
        )

    # ------------------------------------------------------------------
    # customer.subscription.deleted
    # ------------------------------------------------------------------
    elif event_type == "customer.subscription.deleted":
        customer_id: Optional[str] = data_object.get("customer")
        shop_id_meta: Optional[str] = (
            (data_object.get("metadata") or {}).get("shop_id")
        )

        shop = None

        # Try metadata first (fastest path)
        if shop_id_meta:
            try:
                import uuid as _uuid
                shop = db.get(Shop, _uuid.UUID(shop_id_meta))
            except Exception:
                pass

        # Fall back to customer_id lookup
        if not shop and customer_id:
            shop = (
                db.query(Shop)
                .filter(Shop.stripe_customer_id == customer_id)
                .first()
            )

        if not shop:
            logger.warning(
                "customer.subscription.deleted: cannot resolve shop "
                "(customer=%s, meta_shop_id=%s)",
                customer_id,
                shop_id_meta,
            )
            return {"received": True, "warning": "shop not found"}

        shop.subscription_status = SubscriptionStatus.canceled
        db.commit()
        logger.info(
            "Shop %s marked canceled (Stripe customer: %s)", shop.id, customer_id
        )

    else:
        logger.debug("Unhandled Stripe event type: %s", event_type)

    return {"received": True}


# ---------------------------------------------------------------------------
# GET /billing/portal/{shop_id}
# ---------------------------------------------------------------------------

@router.get("/portal/{shop_id}", response_model=PortalResponse)
async def customer_portal(
    shop_id: str,
    return_url: str = "https://app.workbay.ai/settings/billing",
    db: Session = Depends(get_db),
):
    """
    Return a Stripe Customer Portal URL for the given shop.

    The portal lets shop admins update payment methods, view invoices,
    and cancel their subscription without contacting support.
    """
    _stripe_client()
    shop = _get_shop_or_404(shop_id, db)

    if not shop.stripe_customer_id:
        raise HTTPException(
            status_code=400,
            detail="Shop has no associated Stripe customer. "
                   "Complete a checkout session first.",
        )

    try:
        portal_session = stripe.billing_portal.Session.create(
            customer=shop.stripe_customer_id,
            return_url=return_url,
        )
    except stripe.StripeError as exc:
        logger.error("Stripe portal creation failed: %s", exc)
        raise HTTPException(status_code=502, detail=f"Stripe error: {exc.user_message}")

    logger.info(
        "Created Stripe portal session for shop %s (customer %s)",
        shop_id,
        shop.stripe_customer_id,
    )
    return PortalResponse(portal_url=portal_session.url)
