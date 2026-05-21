from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.api import sessions, checklists, media, voice, vehicle_intel, transcript_processor, vehicle_lookup

app = FastAPI(title="Workbay AI", version="0.2.0")

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

@app.get("/health")
async def health():
    return {"status": "ok", "service": "workbay-backend", "version": "0.2.0"}
