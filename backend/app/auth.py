"""Auth0 verification and database-derived staff access for Workbai APIs.

Browser clients never choose a shop or role. A valid Auth0 JWT is resolved to an
active Workbai user, and every route uses that server-derived scope.
"""

from __future__ import annotations

import json
import os
import threading
import time
from dataclasses import dataclass
from typing import Callable, Iterable
from uuid import UUID

import httpx
import jwt
from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from jwt import InvalidTokenError
from sqlalchemy.orm import Session

from app.db.models import User, UserRole
from app.db.session import get_db

_bearer = HTTPBearer(auto_error=False)
_jwks_lock = threading.Lock()
_jwks_cache: dict[str, object] = {"expires_at": 0.0, "keys": {}}
_JWKS_TTL_SECONDS = 3600


@dataclass(frozen=True)
class StaffActor:
    """Authenticated Workbai staff identity, derived entirely on the server."""

    user_id: UUID
    shop_id: UUID
    role: UserRole
    name: str
    auth0_id: str


def _domain() -> str:
    value = os.getenv("AUTH0_DOMAIN", "").strip().rstrip("/")
    if not value:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Authentication is not configured",
        )
    return value.removeprefix("https://").removeprefix("http://")


def _audience() -> str:
    value = os.getenv("AUTH0_API_AUDIENCE", "").strip()
    if not value:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Authentication audience is not configured",
        )
    return value


def _issuer() -> str:
    return f"https://{_domain()}/"


def _jwks() -> dict[str, dict]:
    now = time.monotonic()
    cached = _jwks_cache["keys"]
    if isinstance(cached, dict) and now < float(_jwks_cache["expires_at"]):
        return cached

    with _jwks_lock:
        cached = _jwks_cache["keys"]
        if isinstance(cached, dict) and now < float(_jwks_cache["expires_at"]):
            return cached
        try:
            response = httpx.get(f"{_issuer()}.well-known/jwks.json", timeout=5.0)
            response.raise_for_status()
            keys = {key["kid"]: key for key in response.json().get("keys", []) if key.get("kid")}
        except (httpx.HTTPError, ValueError, KeyError) as exc:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Authentication key service is unavailable",
            ) from exc
        if not keys:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail="Authentication key service returned no usable keys",
            )
        _jwks_cache["keys"] = keys
        _jwks_cache["expires_at"] = now + _JWKS_TTL_SECONDS
        return keys


def _claims(token: str) -> dict:
    try:
        kid = jwt.get_unverified_header(token).get("kid")
    except InvalidTokenError as exc:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid access token") from exc

    jwk = _jwks().get(kid)
    if not jwk:
        # Rotate once before rejecting a token signed by a recently issued key.
        _jwks_cache["expires_at"] = 0.0
        jwk = _jwks().get(kid)
    if not jwk:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Unknown access token key")

    try:
        public_key = jwt.algorithms.RSAAlgorithm.from_jwk(json.dumps(jwk))
        return jwt.decode(
            token,
            public_key,
            algorithms=["RS256"],
            audience=_audience(),
            issuer=_issuer(),
        )
    except InvalidTokenError as exc:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid or expired access token") from exc


def get_current_actor(
    credentials: HTTPAuthorizationCredentials | None = Depends(_bearer),
    db: Session = Depends(get_db),
) -> StaffActor:
    if not credentials or credentials.scheme.lower() != "bearer":
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Authentication required")

    subject = _claims(credentials.credentials).get("sub")
    if not isinstance(subject, str) or not subject:
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Access token has no subject")

    user = db.query(User).filter(User.auth0_id == subject, User.active.is_(True)).one_or_none()
    if not user:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="No active Workbai staff access")

    return StaffActor(
        user_id=user.id,
        shop_id=user.shop_id,
        role=user.role,
        name=user.name,
        auth0_id=user.auth0_id,
    )


def require_roles(*roles: UserRole) -> Callable[[StaffActor], StaffActor]:
    """Return a FastAPI dependency that accepts only named staff roles."""

    allowed = set(roles)

    def dependency(actor: StaffActor = Depends(get_current_actor)) -> StaffActor:
        if actor.role not in allowed:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Insufficient staff role")
        return actor

    return dependency


def scoped_session_or_404(session, actor: StaffActor, *, require_assigned_technician: bool = False):
    """Ensure an inspection session is in the actor's shop and, when needed, their assignment."""

    if not session or session.shop_id != actor.shop_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Inspection session not found")

    if require_assigned_technician and actor.role == UserRole.technician:
        assigned = {session.technician_id, session.assigned_technician_id}
        if actor.user_id not in assigned:
            raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Inspection is not assigned to this technician")
    return session


def require_internal_scheduler(secret: str | None) -> None:
    expected = os.getenv("WORKBAI_SCHEDULER_SECRET", "")
    if not expected:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Scheduler credential is not configured")
    if not secret or not __import__("hmac").compare_digest(secret, expected):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Internal scheduler authentication required")
