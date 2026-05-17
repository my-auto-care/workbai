from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from app.api import sessions, checklists, media

app = FastAPI(title="Workbay AI", version="0.1.0")

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

@app.get("/health")
async def health():
    return {"status": "ok", "service": "workbay-backend"}
