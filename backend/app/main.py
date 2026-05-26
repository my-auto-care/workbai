from contextlib import asynccontextmanager
import logging

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.interval import IntervalTrigger

from app.api import sessions, checklists, media, voice, vehicle_intel, transcript_processor, vehicle_lookup
from app.api import billing
from app.db.session import SessionLocal

logger = logging.getLogger("workbay.scheduler")

# ---------------------------------------------------------------------------
# APScheduler – hourly session auto-expiry
# ---------------------------------------------------------------------------

scheduler = AsyncIOScheduler()

def _run_expiry_job():
    """Synchronous job called by APScheduler every hour."""
    db = SessionLocal()
    try:
        result = sessions.expire_stale_sessions(db)
        logger.info(
            "Auto-expiry job completed: %d session(s) marked abandoned. IDs: %s",
            result["expired_count"],
            result["expired_ids"],
        )
    except Exception as exc:
        logger.exception("Auto-expiry job failed: %s", exc)
    finally:
        db.close()


@asynccontextmanager
async def lifespan(app: FastAPI):
    # ── startup ──────────────────────────────────────────────────────────────
    scheduler.add_job(
        _run_expiry_job,
        trigger=IntervalTrigger(hours=1),
        id="expire_stale_sessions",
        replace_existing=True,
        max_instances=1,
    )
    scheduler.start()
    logger.info("APScheduler started – session auto-expiry runs every hour.")
    yield
    # ── shutdown ─────────────────────────────────────────────────────────────
    scheduler.shutdown(wait=False)
    logger.info("APScheduler shut down.")


# ---------------------------------------------------------------------------
# App
# ---------------------------------------------------------------------------

app = FastAPI(title="Workbay AI", version="0.2.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(sessions.router, tags=["sessions"])
app.include_router(checklists.router, tags=["checklists"])
app.include_router(media.router, tags=["media"])
app.include_router(voice.router, tags=["voice"])
app.include_router(vehicle_intel.router, tags=["vehicle-intelligence"])
app.include_router(transcript_processor.router, tags=["transcript"])
app.include_router(vehicle_lookup.router, tags=["vehicle-lookup"])
app.include_router(billing.router)

@app.get("/health")
async def health():
    return {"status": "ok", "service": "workbay-backend", "version": "0.2.0"}
