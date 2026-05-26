import asyncio
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api import sessions, checklists, media, voice, vehicle_intel, transcript_processor, vehicle_lookup
from app.api import billing
from app.db.session import SessionLocal

logger = logging.getLogger("workbay.scheduler")

# ---------------------------------------------------------------------------
# Background asyncio task – session auto-expiry every 6 hours
# ---------------------------------------------------------------------------

EXPIRY_INTERVAL_HOURS = 6


async def _expiry_loop():
    """
    Infinite asyncio loop that calls expire_stale_sessions() every 6 hours.
    Runs as a background task attached to the FastAPI lifespan.
    The first run is intentionally deferred by the full interval so startup
    is not blocked; use POST /sessions/expire-stale for an immediate run.
    """
    logger.info(
        "Session auto-expiry loop started – will run every %d hours.",
        EXPIRY_INTERVAL_HOURS,
    )
    while True:
        await asyncio.sleep(EXPIRY_INTERVAL_HOURS * 3600)
        db = SessionLocal()
        try:
            result = sessions.expire_stale_sessions(db)
            logger.info(
                "Auto-expiry completed: %d session(s) marked abandoned. IDs: %s",
                result["expired_count"],
                result["expired_ids"],
            )
        except Exception as exc:
            logger.exception("Auto-expiry job failed: %s", exc)
        finally:
            db.close()


# ---------------------------------------------------------------------------
# FastAPI lifespan
# ---------------------------------------------------------------------------

@asynccontextmanager
async def lifespan(app: FastAPI):
    # ── startup ──────────────────────────────────────────────────────────────
    task = asyncio.create_task(_expiry_loop())
    logger.info("Session auto-expiry background task created.")
    yield
    # ── shutdown ─────────────────────────────────────────────────────────────
    task.cancel()
    try:
        await task
    except asyncio.CancelledError:
        pass
    logger.info("Session auto-expiry background task cancelled.")


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
