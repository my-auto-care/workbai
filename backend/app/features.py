"""Environment feature switches.

An unset or blank variable means "use the default". Any explicit value other
than 1/true/yes/on (case-insensitive) turns the feature off.
"""

from __future__ import annotations

import os

_TRUE = {"1", "true", "yes", "on"}


def feature_enabled(name: str, default: bool) -> bool:
    raw = os.getenv(name)
    if raw is None or not raw.strip():
        return default
    return raw.strip().lower() in _TRUE


def legacy_mobile_sessions_enabled() -> bool:
    """Technician self-started (non-template) inspections used by the mobile app."""
    return feature_enabled("WORKBAI_ENABLE_LEGACY_MOBILE_SESSIONS", True)
