"""Auth0 bearer-token checks on a protected route (GET /sessions)."""

import time

import jwt
import pytest

import app.auth as auth_module


def test_valid_token_is_accepted(client, world, bearer):
    response = client.get("/sessions", headers=bearer(world.tech_a1))
    assert response.status_code == 200, response.text


def test_missing_token_is_rejected(client, world):
    assert client.get("/sessions").status_code == 401


@pytest.mark.parametrize("value", ["Bearer not-a-jwt", "Bearer a.b.c", "Basic dXNlcjpwYXNz"])
def test_malformed_credentials_are_rejected(client, world, value):
    assert client.get("/sessions", headers={"Authorization": value}).status_code == 401


def test_wrong_audience_is_rejected(client, world, bearer):
    response = client.get("/sessions", headers=bearer(world.tech_a1, aud="odoPUeNefjahtA3mXsNiSKoZzNSORQ6u"))
    assert response.status_code == 401


def test_wrong_issuer_is_rejected(client, world, bearer):
    response = client.get("/sessions", headers=bearer(world.tech_a1, iss="https://evil.example.auth0.com/"))
    assert response.status_code == 401


def test_expired_token_is_rejected(client, world, bearer):
    past = int(time.time()) - 3600
    response = client.get("/sessions", headers=bearer(world.tech_a1, iat=past - 600, exp=past))
    assert response.status_code == 401


@pytest.mark.parametrize("claim", ["exp", "aud", "iss", "sub"])
def test_token_missing_a_required_claim_is_rejected(client, world, bearer, claim):
    assert client.get("/sessions", headers=bearer(world.tech_a1, drop=(claim,))).status_code == 401


def test_token_signed_by_another_key_with_a_known_kid_is_rejected(client, world, bearer, other_signing_key):
    assert client.get("/sessions", headers=bearer(world.tech_a1, key=other_signing_key)).status_code == 401


def test_hs256_token_using_the_public_key_as_secret_is_rejected(client, world, signing_key):
    """Algorithm-confusion forgery: HMAC-sign with the public key as the secret."""
    import base64
    import hashlib
    import hmac
    import json

    from cryptography.hazmat.primitives import serialization

    public_pem = signing_key.public_key().public_bytes(
        serialization.Encoding.PEM, serialization.PublicFormat.SubjectPublicKeyInfo
    )

    def b64(data: bytes) -> str:
        return base64.urlsafe_b64encode(data).rstrip(b"=").decode()

    header = b64(json.dumps({"alg": "HS256", "typ": "JWT", "kid": "workbai-test-key"}).encode())
    payload = b64(
        json.dumps(
            {
                "iss": "https://workbai-tests.example.auth0.com/",
                "aud": "https://api.workbai.test",
                "sub": world.tech_a1.auth0_id,
                "exp": int(time.time()) + 600,
            }
        ).encode()
    )
    signature = b64(hmac.new(public_pem, f"{header}.{payload}".encode(), hashlib.sha256).digest())
    forged = f"{header}.{payload}.{signature}"
    assert client.get("/sessions", headers={"Authorization": f"Bearer {forged}"}).status_code == 401


def test_unsigned_alg_none_token_is_rejected(client, world):
    token = jwt.encode(
        {"iss": "https://workbai-tests.example.auth0.com/", "aud": "https://api.workbai.test", "sub": world.tech_a1.auth0_id, "exp": int(time.time()) + 600},
        key=None,
        algorithm="none",
        headers={"kid": "workbai-test-key"},
    )
    assert client.get("/sessions", headers={"Authorization": f"Bearer {token}"}).status_code == 401


@pytest.mark.parametrize("kid", [["workbai-test-key"], {"x": 1}, 7, ""])
def test_non_string_or_empty_kid_is_401_not_500(client, world, make_token, kid):
    import base64
    import json

    # PyJWT will not encode a non-string kid, so swap the header by hand.
    _, payload, signature = make_token(world.tech_a1.auth0_id).split(".")
    header = base64.urlsafe_b64encode(json.dumps({"alg": "RS256", "typ": "JWT", "kid": kid}).encode()).rstrip(b"=").decode()
    response = client.get("/sessions", headers={"Authorization": f"Bearer {header}.{payload}.{signature}"})
    assert response.status_code == 401


def test_unknown_kid_refetches_jwks_at_most_once_per_minute(client, world, bearer, jwks):
    for _ in range(5):
        assert client.get("/sessions", headers=bearer(world.tech_a1, kid="not-a-real-key")).status_code == 401
    # One initial load plus at most one forced refresh, not one fetch per request.
    assert jwks.calls <= 2


def test_cached_keys_survive_an_auth0_outage(client, world, bearer, jwks):
    assert client.get("/sessions", headers=bearer(world.tech_a1)).status_code == 200
    jwks.fail = True
    auth_module._jwks_cache["expires_at"] = 0.0  # cache expired while Auth0 is down
    assert client.get("/sessions", headers=bearer(world.tech_a1)).status_code == 200


def test_valid_token_for_unknown_user_is_forbidden(client, world, bearer):
    assert client.get("/sessions", headers=bearer("auth0|someone-else")).status_code == 403


def test_valid_token_for_inactive_user_is_forbidden(client, world, bearer):
    assert client.get("/sessions", headers=bearer(world.inactive_tech_a)).status_code == 403


@pytest.mark.parametrize("missing", ["AUTH0_DOMAIN", "AUTH0_API_AUDIENCE"])
def test_missing_auth0_configuration_fails_closed(client, world, bearer, monkeypatch, missing):
    headers = bearer(world.tech_a1)
    monkeypatch.delenv(missing)
    assert client.get("/sessions", headers=headers).status_code == 503
