"""Security helpers for the default-off Current Visit release domain.

No caller may log a plaintext customer destination, public-link secret, or URL.
"""

from __future__ import annotations

import hashlib
import hmac
import ipaddress
import os
import re
import secrets
from urllib.parse import urlparse

from cryptography.fernet import Fernet, InvalidToken
from fastapi import HTTPException, status


_SMS = re.compile(r"^\+[1-9]\d{7,14}$")
_EMAIL = re.compile(r"^[^\s@]+@[^\s@]+\.[^\s@]+$")
_SECRET = re.compile(r"^[A-Za-z0-9_-]{32,256}$")


def current_visit_release_enabled() -> bool:
    return os.getenv("WORKBAI_ENABLE_CURRENT_VISIT_RELEASE", "false").strip().lower() in {"1", "true", "yes"}


def require_current_visit_release_enabled() -> None:
    if not current_visit_release_enabled():
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Current Visit release is not enabled for this environment")


def current_visit_public_edge_verified() -> bool:
    return os.getenv("WORKBAI_CURRENT_VISIT_EDGE_VERIFIED", "false").strip().lower() in {"1", "true", "yes"}


def require_current_visit_public_edge_verified() -> None:
    if not current_visit_public_edge_verified():
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Current Visit public edge verification is incomplete")


def _required(name: str) -> str:
    value = os.getenv(name, "").strip()
    if not value:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Current Visit security configuration is incomplete")
    return value


def normalize_contact(channel: str, value: str) -> str:
    normalized = value.strip().lower() if channel == "email" else value.strip().replace(" ", "").replace("-", "")
    valid = _EMAIL.fullmatch(normalized) if channel == "email" else _SMS.fullmatch(normalized)
    if channel not in {"sms", "email"} or not valid:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail="Enter a valid mobile number or email address")
    return normalized


def mask_contact(channel: str, normalized: str) -> str:
    if channel == "sms":
        return f"•••• {normalized[-4:]}"
    local, domain = normalized.split("@", 1)
    return f"{local[:1]}•••@{domain}"


def _fernet() -> Fernet:
    try:
        return Fernet(_required("WORKBAI_CONTACT_ENCRYPTION_KEY").encode())
    except (ValueError, TypeError) as exc:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Current Visit contact protection is unavailable") from exc


def contact_encryption_key_id() -> str:
    return _required("WORKBAI_CONTACT_ENCRYPTION_KEY_ID")


def encrypt_contact(normalized: str) -> str:
    return _fernet().encrypt(normalized.encode()).decode()


def decrypt_contact(ciphertext: str) -> str:
    try:
        return _fernet().decrypt(ciphertext.encode()).decode()
    except (InvalidToken, UnicodeDecodeError) as exc:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Current Visit contact protection is unavailable") from exc


def _hmac_hex(value: str, env_name: str) -> str:
    return hmac.new(_required(env_name).encode(), value.encode(), hashlib.sha256).hexdigest()


def contact_lookup_hmac(normalized: str) -> str:
    return _hmac_hex(normalized, "WORKBAI_CONTACT_LOOKUP_HMAC_PEPPER")


def public_link_hmac(secret: str) -> str:
    return _hmac_hex(secret, "WORKBAI_PUBLIC_LINK_HMAC_PEPPER")


def public_link_hmac_key_id() -> str:
    return _required("WORKBAI_PUBLIC_LINK_HMAC_KEY_ID")


def public_access_hmac(value: str) -> str:
    return _hmac_hex(f"ip:{value}", "WORKBAI_PUBLIC_ACCESS_AUDIT_PEPPER")


def valid_public_resolver_key(value: str | None) -> bool:
    expected = _required("WORKBAI_PUBLIC_RESOLVER_SHARED_SECRET")
    # Compare bytes: compare_digest raises TypeError on a non-ASCII str, which
    # turned a junk header into a 500 instead of the generic unavailable reply.
    return bool(value) and hmac.compare_digest(value.encode("utf-8"), expected.encode("utf-8"))


def new_public_secret() -> str:
    # token_urlsafe(32) yields 256 bits of CSPRNG entropy before URL-safe encoding.
    return secrets.token_urlsafe(32)


def valid_public_secret(value: str) -> bool:
    return bool(_SECRET.fullmatch(value))


def public_glovebox_origin() -> str:
    origin = _required("WORKBAI_PUBLIC_GLOVEBOX_ORIGIN").rstrip("/")
    parsed = urlparse(origin)
    if parsed.scheme != "https" or not parsed.netloc or parsed.path not in {"", "/"} or parsed.query or parsed.fragment:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Current Visit public origin is invalid")
    return origin


def public_support_phone() -> str:
    value = _required("WORKBAI_PUBLIC_SUPPORT_PHONE")
    if not _SMS.fullmatch(value):
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Current Visit store contact configuration is invalid")
    return value


def trusted_client_ip(value: str | None) -> str:
    candidate = (value or "").strip()
    try:
        return str(ipaddress.ip_address(candidate))
    except ValueError:
        return "unknown"
