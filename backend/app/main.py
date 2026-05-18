from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.api import sessions, checklists, media, voice

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

@app.get("/health")
async def health():
    return {"status": "ok", "service": "workbay-backend", "version": "0.2.0"}
