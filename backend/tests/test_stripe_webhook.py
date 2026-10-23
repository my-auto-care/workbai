"""Stripe webhooks are processed only when Stripe's signature verifies."""

import hashlib
import hmac
import json
import time

from app.db.models import Shop, SubscriptionStatus

from .conftest import STRIPE_WEBHOOK_SECRET


def _event(shop_id) -> str:
    return json.dumps(
        {
            "id": "evt_test_1",
            "object": "event",
            "type": "customer.subscription.deleted",
            "data": {"object": {"object": "subscription", "customer": "cus_x", "metadata": {"shop_id": str(shop_id)}}},
        }
    )


def _signature(payload: str, secret: str = STRIPE_WEBHOOK_SECRET, timestamp: int | None = None) -> str:
    timestamp = int(time.time()) if timestamp is None else timestamp
    digest = hmac.new(secret.encode(), f"{timestamp}.{payload}".encode(), hashlib.sha256).hexdigest()
    return f"t={timestamp},v1={digest}"


def _status(db, shop_id):
    db.expire_all()
    return db.get(Shop, shop_id).subscription_status


def _post(client, payload, signature=None):
    headers = {"Content-Type": "application/json"}
    if signature is not None:
        headers["Stripe-Signature"] = signature
    return client.post("/billing/webhook", content=payload, headers=headers)


def test_unsigned_event_is_rejected_and_not_processed(client, world, db):
    before = _status(db, world.shop_a.id)
    response = _post(client, _event(world.shop_a.id))
    assert response.status_code == 400
    assert _status(db, world.shop_a.id) == before


def test_badly_signed_event_is_rejected(client, world, db):
    payload = _event(world.shop_a.id)
    response = _post(client, payload, _signature(payload, secret="whsec_attacker"))
    assert response.status_code == 400
    assert _status(db, world.shop_a.id) != SubscriptionStatus.canceled


def test_tampered_payload_is_rejected(client, world, db):
    signed = _event(world.shop_b.id)
    response = _post(client, _event(world.shop_a.id), _signature(signed))
    assert response.status_code == 400
    assert _status(db, world.shop_a.id) != SubscriptionStatus.canceled


def test_replayed_old_signature_is_rejected(client, world, db):
    payload = _event(world.shop_a.id)
    response = _post(client, payload, _signature(payload, timestamp=int(time.time()) - 3600))
    assert response.status_code == 400
    assert _status(db, world.shop_a.id) != SubscriptionStatus.canceled


def test_correctly_signed_event_is_processed(client, world, db):
    payload = _event(world.shop_a.id)
    response = _post(client, payload, _signature(payload))
    assert response.status_code == 200, response.text
    assert _status(db, world.shop_a.id) == SubscriptionStatus.canceled
    assert _status(db, world.shop_b.id) != SubscriptionStatus.canceled


def test_missing_signing_secret_fails_closed(client, world, db, monkeypatch):
    payload = _event(world.shop_a.id)
    signature = _signature(payload)
    monkeypatch.delenv("STRIPE_WEBHOOK_SECRET")
    response = _post(client, payload, signature)
    assert response.status_code == 503
    assert _status(db, world.shop_a.id) != SubscriptionStatus.canceled


def test_webhook_does_not_need_the_stripe_api_key(client, world, db, monkeypatch):
    monkeypatch.delenv("STRIPE_SECRET_KEY")
    payload = _event(world.shop_a.id)
    assert _post(client, payload, _signature(payload)).status_code == 200
