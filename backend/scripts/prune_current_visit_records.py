"""Durable Current Visit retention worker entrypoint.

Run by the dedicated Compose service; it does not enable or release Current Visit.
"""

from __future__ import annotations

import logging
import sys
from pathlib import Path

# Direct script execution sets sys.path to /app/scripts; retain /app so this
# durable worker also works when invoked manually for a supervised recovery.
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.api.checkin import prune_expired_customer_context_records
from app.api.current_visit import prune_expired_current_visit_records
from app.db.session import SessionLocal

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")
logger = logging.getLogger("workbay.current_visit_cleanup")


def main() -> int:
    db = SessionLocal()
    try:
        current_visit = prune_expired_current_visit_records(db)
        customer_context = prune_expired_customer_context_records(db)
        logger.info(
            "Retention cleanup completed: %d rate bucket(s), %d public audit record(s), %d raw customer-context record(s).",
            current_visit["rate_buckets"],
            current_visit["public_audits"],
            customer_context["raw_context_purged"],
        )
        return 0
    except Exception:
        logger.exception("Current Visit retention cleanup failed")
        return 1
    finally:
        db.close()


if __name__ == "__main__":
    sys.exit(main())
