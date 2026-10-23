"""HTTP client the voice worker uses to call the Workbai API.

Every request carries the worker's service credential in its own header
(never as a bearer token). The API accepts it only on the few routes the
worker needs, and only for an active legacy inspection.
"""

from __future__ import annotations

import logging
import os

import httpx

logger = logging.getLogger("workbay.voice")

# Must match app.auth.SERVICE_TOKEN_HEADER / VOICE_AGENT_TOKEN_ENV (a test checks this).
SERVICE_TOKEN_HEADER = "X-Workbai-Service-Token"
VOICE_AGENT_TOKEN_ENV = "WORKBAI_VOICE_AGENT_TOKEN"


def backend_url() -> str:
    return os.getenv("BACKEND_URL", "http://localhost:8000")


def service_headers() -> dict[str, str]:
    token = os.getenv(VOICE_AGENT_TOKEN_ENV, "").strip()
    if not token:
        logger.error("%s is not set; every Workbai API call from the voice worker will be rejected (401)", VOICE_AGENT_TOKEN_ENV)
        return {}
    return {SERVICE_TOKEN_HEADER: token}


def backend_client(timeout: float = 10.0) -> httpx.AsyncClient:
    return httpx.AsyncClient(base_url=backend_url(), headers=service_headers(), timeout=timeout)
