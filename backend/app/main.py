import asyncio
import logging
import os
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api import advisor_review, billing, checkin, checklists, current_visit, media, sessions, transcript_processor, vehicle_intel, vehicle_lookup, voice
from app.db.session import SessionLocal
from app.features import feature_enabled

logger = logging.getLogger("workbay.scheduler")
EXPIRY_INTERVAL_HOURS = 6


def _cors_origins() -> list[str]:
    """Return only explicit browser origins; native apps do not need browser CORS."""
    configured = os.getenv("CORS_ALLOWED_ORIGINS", "")
    return [value.strip().rstrip("/") for value in configured.split(",") if value.strip()]


# Routers production already serves to the mobile app, the voice worker and
# Stripe. Every route in them now requires staff Auth0, the voice-agent service
# credential or (webhook) a valid Stripe signature, so they default ON: an
# unset variable keeps today's behaviour. Set one to "false" to unmount it
# (the test stack does this explicitly).
OPTIONAL_ROUTER_FLAGS = (
    "WORKBAI_ENABLE_VOICE_INSPECTION",
    "WORKBAI_ENABLE_VEHICLE_LOOKUP",
    "WORKBAI_ENABLE_EXPERIMENTAL_VEHICLE_AI",
    "WORKBAI_ENABLE_BILLING",
)


def _enabled(name: str) -> bool:
    return feature_enabled(name, True)


async def _expiry_loop():
    logger.info("Session auto-expiry loop started – will run every %d hours.", EXPIRY_INTERVAL_HOURS)
    while True:
        await asyncio.sleep(EXPIRY_INTERVAL_HOURS * 3600)
        db = SessionLocal()
        try:
            result = sessions.expire_stale_sessions(db)
            current_visit_cleanup = current_visit.prune_expired_current_visit_records(db)
            customer_context_cleanup = checkin.prune_expired_customer_context_records(db)
            logger.info("Auto-expiry completed: %d session(s) marked abandoned; %d public rate bucket(s), %d public audit record(s), and %d raw customer-context record(s) pruned.", result["expired_count"], current_visit_cleanup["rate_buckets"], current_visit_cleanup["public_audits"], customer_context_cleanup["raw_context_purged"])
        except Exception as exc:
            logger.exception("Session auto-expiry job failed: %s", exc)
        finally:
            db.close()


@asynccontextmanager
async def lifespan(app: FastAPI):
    task = asyncio.create_task(_expiry_loop())
    logger.info("Session auto-expiry background task created.")
    yield
    task.cancel()
    try:
        await task
    except asyncio.CancelledError:
        pass
    logger.info("Session auto-expiry background task cancelled.")


def create_app() -> FastAPI:
    application = FastAPI(title="Workbay AI", version="0.3.0", lifespan=lifespan)
    application.add_middleware(
        CORSMiddleware,
        allow_origins=_cors_origins(),
        allow_credentials=True,
        allow_methods=["GET", "POST", "PATCH", "OPTIONS"],
        allow_headers=["Authorization", "Content-Type", "X-Workbai-Scheduler-Secret"],
    )

    application.include_router(sessions.router, tags=["sessions"])
    application.include_router(checkin.router)
    application.include_router(advisor_review.router)
    application.include_router(current_visit.router)
    application.include_router(checklists.router, tags=["checklists"])
    application.include_router(media.router, tags=["media"])
    mounted = []
    if _enabled("WORKBAI_ENABLE_VOICE_INSPECTION"):
        application.include_router(voice.router, tags=["voice"])
        mounted.append("voice")
    if _enabled("WORKBAI_ENABLE_VEHICLE_LOOKUP"):
        application.include_router(vehicle_lookup.router, tags=["vehicle-lookup"])
        mounted.append("vehicle-lookup")
    if _enabled("WORKBAI_ENABLE_EXPERIMENTAL_VEHICLE_AI"):
        application.include_router(vehicle_intel.router, tags=["vehicle-intelligence"])
        application.include_router(transcript_processor.router, tags=["transcript"])
        mounted.append("vehicle-intelligence+transcript")
    if _enabled("WORKBAI_ENABLE_BILLING"):
        application.include_router(billing.router)
        mounted.append("billing")
    # uvicorn.error is the logger uvicorn configures at INFO, so this line
    # reaches `docker compose logs backend` (app loggers default to WARNING).
    logging.getLogger("uvicorn.error").info("Optional routers mounted: %s", ", ".join(mounted) or "none")

    @application.get("/health")
    async def health():
        return {"status": "ok", "service": "workbay-backend", "version": "0.3.0"}

    return application


app = create_app()
