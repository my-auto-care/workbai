"""Durable Current Visit retention worker entrypoint.

Run by the dedicated Compose service; it does not enable or release Current Visit.
"""

from __future__ import annotations

import logging
import sys

from app.api.current_visit import prune_expired_current_visit_records
from app.db.session import SessionLocal

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")
logger = logging.getLogger("workbay.current_visit_cleanup")


def main() -> int:
    db = SessionLocal()
    try:
        result = prune_expired_current_visit_records(db)
        logger.info("Current Visit retention cleanup completed: %d rate bucket(s), %d audit record(s).", result["rate_buckets"], result["public_audits"])
        return 0
    except Exception:
        logger.exception("Current Visit retention cleanup failed")
        return 1
    finally:
        db.close()


if __name__ == "__main__":
    sys.exit(main())
