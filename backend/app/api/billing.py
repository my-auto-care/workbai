"""
Stripe subscription billing endpoints for Workbay AI.

Endpoints
---------
POST /billing/create-customer
    Creates a Stripe Customer for a shop.
    Body: { "shop_id": "<uuid>", "email": "...", "name": "..." }
    Returns: { "customer_id": "cus_..." }

POST /billing/create-subscription
    Creates a Stripe Subscription for an existing customer.
    Body: { "shop_id": "<uuid>", "customer_id": "cus_...", "price_id": "price_..." }
    Returns: { "subscription_id": "sub_...", "status": "..." }

POST /billing/webhook
    Handles Stripe webhook events (raw body, Stripe-Signature header required).
    Reads STRIPE_WEBHOOK_SECRET from env.
    Handled events:
      - checkout.session.completed       → shop.subscription_status = active
      - customer.subscription.updated    → shop.subscription_status synced to Stripe status
      - customer.subscription.deleted    → shop.subscription_status = canceled

GET /billing/subscription/{shop_id}
    Returns the current subscription status for a shop.
    Returns: { "shop_id": "...", "subscription_status": "...", "stripe_customer_id": "..." }
"""

import os
import logging
import uuid as _uuid
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
# Stripe helpers – resolved at request time so the module imports cleanly
# even before env vars are available (e.g. during test collection).
# ---------------------------------------------------------------------------

def _get_stripe() -> stripe:
    """Configure stripe with secret key and return the module."""
    api_key = os.getenv("STRIPE_SECRET_KEY")
    if not api_key:
        raise HTTPException(status_code=500, detail="STRIPE_SECRET_KEY is not configured")
    stripe.api_key = api_key
    return stripe


def _get_webhook_secret() -> str:
    secret = os.getenv("STRIPE_WEBHOOK_SECRET")
    if not secret:
        raise HTTPException(status_code=500, detail="STRIPE_WEBHOOK_SECRET is not configured")
    return secret


# ---------------------------------------------------------------------------
# DB helper
# ---------------------------------------------------------------------------

def _get_shop_or_404(shop_id: str, db: Session) -> Shop:
    try:
        uid = _uuid.UUID(shop_id)
    except ValueError:
        raise HTTPException(status_code=422, detail=f"Invalid shop_id UUID format: {shop_id!r}")
    shop = db.get(Shop, uid)
    if not shop:
        raise HTTPException(status_code=404, detail=f"Shop {shop_id} not found")
    return shop


# ---------------------------------------------------------------------------
# Pydantic schemas
# ---------------------------------------------------------------------------

class CreateCustomerRequest(BaseModel):
    shop_id: str
    email: str
    name: str


class CreateCustomerResponse(BaseModel):
    customer_id: str


class CreateSubscriptionRequest(BaseModel):
    shop_id: str
    customer_id: str
    price_id: str


class CreateSubscriptionResponse(BaseModel):
    subscription_id: str
    status: str


class SubscriptionStatusResponse(BaseModel):
    shop_id: str
    subscription_status: str
    stripe_customer_id: Optional[str] = None


# ---------------------------------------------------------------------------
# Stripe status -> SubscriptionStatus mapping
# ---------------------------------------------------------------------------

_STRIPE_STATUS_MAP: dict = {
    "active":             SubscriptionStatus.active,
    "trialing":           SubscriptionStatus.trial,
    "past_due":           SubscriptionStatus.past_due,
    "canceled":           SubscriptionStatus.canceled,
    "unpaid":             SubscriptionStatus.past_due,
    "incomplete":         SubscriptionStatus.past_due,
    "incomplete_expired": SubscriptionStatus.canceled,
    "paused":             SubscriptionStatus.past_due,
}


# ---------------------------------------------------------------------------
# POST /billing/create-customer
# ---------------------------------------------------------------------------

@router.post("/create-customer", response_model=CreateCustomerResponse, status_code=201)
async def create_customer(
    body: CreateCustomerRequest,
    db: Session = Depends(get_db),
):
    """
    Create a Stripe Customer for the given shop and persist the customer_id.

    Idempotent: if the shop already has a stripe_customer_id the existing id
    is returned without creating a duplicate in Stripe.
    """
    _get_stripe()
    shop = _get_shop_or_404(body.shop_id, db)

    # Idempotency guard
    if shop.stripe_customer_id:
        logger.info(
            "Shop %s already has Stripe customer %s — returning existing id",
            body.shop_id,
            shop.stripe_customer_id,
        )
        return CreateCustomerResponse(customer_id=shop.stripe_customer_id)

    try:
        customer = stripe.Customer.create(
            email=body.email,
            name=body.name,
            metadata={"shop_id": str(shop.id)},
        )
    except stripe.StripeError as exc:
        logger.error("Stripe customer creation failed for shop %s: %s", body.shop_id, exc)
        raise HTTPException(status_code=502, detail=f"Stripe error: {exc.user_message}")

    shop.stripe_customer_id = customer.id
    db.commit()

    logger.info("Created Stripe customer %s for shop %s", customer.id, body.shop_id)
    return CreateCustomerResponse(customer_id=customer.id)


# ---------------------------------------------------------------------------
# POST /billing/create-subscription
# ---------------------------------------------------------------------------

@router.post("/create-subscription", response_model=CreateSubscriptionResponse, status_code=201)
async def create_subscription(
    body: CreateSubscriptionRequest,
    db: Session = Depends(get_db),
):
    """
    Create a Stripe Subscription for an existing customer / price combination.

    The shop's subscription_status is updated to reflect the Stripe status
    returned at creation time.  The latest_invoice.payment_intent is expanded
    so callers can complete 3DS authentication if required.
    """
    _get_stripe()
    shop = _get_shop_or_404(body.shop_id, db)

    try:
        subscription = stripe.Subscription.create(
            customer=body.customer_id,
            items=[{"price": body.price_id}],
            metadata={"shop_id": str(shop.id)},
            expand=["latest_invoice.payment_intent"],
        )
    except stripe.StripeError as exc:
        logger.error(
            "Stripe subscription creation failed for shop %s / customer %s: %s",
            body.shop_id,
            body.customer_id,
            exc,
        )
        raise HTTPException(status_code=502, detail=f"Stripe error: {exc.user_message}")

    # Persist customer_id if not already stored
    if not shop.stripe_customer_id:
        shop.stripe_customer_id = body.customer_id

    # Sync subscription status from Stripe
    new_status = _STRIPE_STATUS_MAP.get(subscription.status, SubscriptionStatus.trial)
    shop.subscription_status = new_status
    db.commit()

    logger.info(
        "Created Stripe subscription %s (status=%s) for shop %s",
        subscription.id,
        subscription.status,
        body.shop_id,
    )
    return CreateSubscriptionResponse(
        subscription_id=subscription.id,
        status=subscription.status,
    )


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

    STRIPE_WEBHOOK_SECRET is read from the environment to verify the
    Stripe-Signature header before any event data is processed.

    Handled events
    ~~~~~~~~~~~~~~
    checkout.session.completed
        Stores stripe_customer_id on the shop and sets
        subscription_status -> active.

    customer.subscription.updated
        Syncs subscription_status to the current Stripe subscription status.

    customer.subscription.deleted
        Sets subscription_status -> canceled.
    """
    _get_stripe()
    payload = await request.body()

    # ── Signature verification ────────────────────────────────────────────
    try:
        event = stripe.Webhook.construct_event(
            payload=payload,
            sig_header=stripe_signature or "",
            secret=_get_webhook_secret(),
        )
    except stripe.SignatureVerificationError as exc:
        logger.warning("Stripe webhook signature verification failed: %s", exc)
        raise HTTPException(status_code=400, detail="Invalid Stripe signature")
    except Exception as exc:
        logger.error("Stripe webhook construction error: %s", exc)
        raise HTTPException(status_code=400, detail="Webhook payload error")

    event_type: str = event["type"]
    data_obj = event["data"]["object"]
    logger.info("Received Stripe event: %s  id=%s", event_type, event["id"])

    # ── checkout.session.completed ────────────────────────────────────────
    if event_type == "checkout.session.completed":
        shop_id: Optional[str] = (
            (data_obj.get("metadata") or {}).get("shop_id")
            or data_obj.get("client_reference_id")
        )
        customer_id: Optional[str] = data_obj.get("customer")

        if not shop_id:
            logger.error("checkout.session.completed: missing shop_id in metadata")
            return {"received": True, "warning": "missing shop_id"}

        try:
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
            "Shop %s activated via checkout.session.completed (customer: %s)",
            shop_id,
            customer_id,
        )

    # ── customer.subscription.updated ────────────────────────────────────
    elif event_type == "customer.subscription.updated":
        stripe_status: str = data_obj.get("status", "")
        customer_id: Optional[str] = data_obj.get("customer")
        shop_id_meta: Optional[str] = (data_obj.get("metadata") or {}).get("shop_id")

        shop = _resolve_shop(db, shop_id_meta, customer_id)
        if not shop:
            logger.warning(
                "customer.subscription.updated: cannot resolve shop "
                "(customer=%s, meta_shop_id=%s)",
                customer_id,
                shop_id_meta,
            )
            return {"received": True, "warning": "shop not found"}

        new_status = _STRIPE_STATUS_MAP.get(stripe_status, SubscriptionStatus.trial)
        shop.subscription_status = new_status
        db.commit()
        logger.info(
            "Shop %s subscription updated -> %s (Stripe status: %s)",
            shop.id,
            new_status,
            stripe_status,
        )

    # ── customer.subscription.deleted ────────────────────────────────────
    elif event_type == "customer.subscription.deleted":
        customer_id: Optional[str] = data_obj.get("customer")
        shop_id_meta: Optional[str] = (data_obj.get("metadata") or {}).get("shop_id")

        shop = _resolve_shop(db, shop_id_meta, customer_id)
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
            "Shop %s marked canceled via customer.subscription.deleted (customer: %s)",
            shop.id,
            customer_id,
        )

    else:
        logger.debug("Unhandled Stripe event type: %s", event_type)

    return {"received": True}


def _resolve_shop(
    db: Session,
    shop_id_meta: Optional[str],
    customer_id: Optional[str],
) -> Optional[Shop]:
    """
    Resolve a Shop from subscription metadata shop_id or Stripe customer_id.
    Metadata lookup is attempted first (O(1) PK lookup); falls back to
    stripe_customer_id column query.
    """
    if shop_id_meta:
        try:
            shop = db.get(Shop, _uuid.UUID(shop_id_meta))
            if shop:
                return shop
        except Exception:
            pass

    if customer_id:
        return (
            db.query(Shop)
            .filter(Shop.stripe_customer_id == customer_id)
            .first()
        )

    return None


# ---------------------------------------------------------------------------
# GET /billing/subscription/{shop_id}
# ---------------------------------------------------------------------------

@router.get("/subscription/{shop_id}", response_model=SubscriptionStatusResponse)
async def get_subscription_status(
    shop_id: str,
    db: Session = Depends(get_db),
):
    """
    Return the current subscription status for a shop.

    Status is persisted in the database and kept in sync by Stripe webhooks.
    Possible values: trial | active | past_due | canceled.
    """
    shop = _get_shop_or_404(shop_id, db)

    return SubscriptionStatusResponse(
        shop_id=str(shop.id),
        subscription_status=(
            shop.subscription_status.value
            if shop.subscription_status
            else SubscriptionStatus.trial.value
        ),
        stripe_customer_id=shop.stripe_customer_id,
    )
