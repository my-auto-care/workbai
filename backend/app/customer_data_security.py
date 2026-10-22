"""Internal customer-data encryption and blind-index helpers.

This module is deliberately separate from Current Visit release security. It is
for staff-only customer profiles, searchable contact fields, and visit-bound
context records. It must never be used to make a customer visible publicly.
"""

from __future__ import annotations

import hashlib
import hmac
import os
import re
import unicodedata
from collections.abc import Iterable

from cryptography.fernet import Fernet, InvalidToken
from fastapi import HTTPException, status

from app.current_visit_security import normalize_contact

_WORD = re.compile(r"[a-z0-9]+")


def _required(name: str) -> str:
    value = os.getenv(name, "").strip()
    if not value:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Customer-data protection is not configured")
    return value


def customer_data_enabled() -> bool:
    return bool(
        os.getenv("WORKBAI_CUSTOMER_DATA_ENCRYPTION_KEY", "").strip()
        and os.getenv("WORKBAI_CUSTOMER_DATA_ENCRYPTION_KEY_ID", "").strip()
        and os.getenv("WORKBAI_CUSTOMER_SEARCH_HMAC_PEPPER", "").strip()
    )


def require_customer_data_enabled() -> None:
    if not customer_data_enabled():
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="Customer profiles are not enabled for this environment")


def _fernet() -> Fernet:
    try:
        return Fernet(_required("WORKBAI_CUSTOMER_DATA_ENCRYPTION_KEY").encode())
    except (ValueError, TypeError) as exc:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Customer-data protection is unavailable") from exc


def customer_data_encryption_key_id() -> str:
    return _required("WORKBAI_CUSTOMER_DATA_ENCRYPTION_KEY_ID")


def encrypt_customer_data(value: str) -> str:
    return _fernet().encrypt(value.encode()).decode()


def decrypt_customer_data(ciphertext: str) -> str:
    try:
        return _fernet().decrypt(ciphertext.encode()).decode()
    except (InvalidToken, UnicodeDecodeError) as exc:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Customer-data protection is unavailable") from exc


def normalize_search_text(value: str) -> str:
    folded = unicodedata.normalize("NFKD", value).encode("ascii", "ignore").decode("ascii").lower()
    return " ".join(_WORD.findall(folded))


def _token_hmac(shop_id: object, field: str, token: str) -> str:
    payload = f"{shop_id}:{field}:{token}".encode()
    return hmac.new(_required("WORKBAI_CUSTOMER_SEARCH_HMAC_PEPPER").encode(), payload, hashlib.sha256).hexdigest()


def customer_search_token(shop_id: object, field: str, token: str) -> str:
    normalized = normalize_search_text(token) if field not in {"phone", "vin", "customer_number"} else re.sub(r"[^A-Za-z0-9]", "", token).lower()
    if not normalized:
        raise ValueError("Search token cannot be empty")
    return _token_hmac(shop_id, field, normalized)


def _prefixes(value: str, *, minimum: int = 2, maximum: int = 32) -> set[str]:
    return {value[:length] for length in range(minimum, min(len(value), maximum) + 1)}


def _search_words(value: str) -> set[str]:
    return {word for word in normalize_search_text(value).split() if len(word) >= 2}


def customer_blind_index_tokens(shop_id: object, field: str, value: str) -> set[str]:
    """Return field- and shop-bound blind-index values; never plaintext search text."""
    if field == "phone":
        digits = re.sub(r"\D", "", value)
        if len(digits) < 4:
            return set()
        # Exact full number and suffixes support normal staff phone lookup without
        # a broad substring index over a sensitive telephone number.
        pieces = {digits} | {digits[-length:] for length in range(4, min(15, len(digits)) + 1)}
    elif field == "vin":
        vin = re.sub(r"[^A-Za-z0-9]", "", value).upper()
        pieces = {vin} | ({vin[-8:]} if len(vin) >= 8 else set())
    elif field == "customer_number":
        value = re.sub(r"[^A-Za-z0-9]", "", value).lower()
        pieces = _prefixes(value, minimum=2) if len(value) >= 2 else set()
    else:
        pieces = set()
        for word in _search_words(value):
            pieces.update(_prefixes(word))
    return {_token_hmac(shop_id, field, piece) for piece in pieces}


def query_blind_index_tokens(shop_id: object, query: str) -> set[str]:
    """Return candidate HMACs for staff typeahead; short queries intentionally return no result."""
    text = query.strip()
    compact = re.sub(r"[^A-Za-z0-9]", "", text)
    result: set[str] = set()
    if compact.isdigit() and len(compact) >= 4:
        result.add(_token_hmac(shop_id, "phone", compact))
    if len(compact) >= 6:
        result.add(_token_hmac(shop_id, "vin", compact.upper()))
        result.add(_token_hmac(shop_id, "customer_number", compact.lower()))
    for word in _search_words(text):
        for field in ("name", "email", "customer_number"):
            result.add(_token_hmac(shop_id, field, word))
    return result


def normalize_customer_contact(channel: str, destination: str) -> str:
    return normalize_contact(channel, destination)


def safe_excerpt(value: str, limit: int = 280) -> str:
    """Keep staff-facing suggestion labels bounded; source text remains encrypted."""
    collapsed = " ".join(value.split())
    return collapsed[:limit].rstrip()


def has_any_value(values: Iterable[str | None]) -> bool:
    return any(bool((value or "").strip()) for value in values)
