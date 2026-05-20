"""
Workbay AI Voice Agent
LiveKit Agents v1.x + AssemblyAI STT + ElevenLabs TTS + Claude Sonnet
"""
import os
import logging
import asyncio
import httpx
import json
from typing import Annotated

from livekit.agents import AutoSubscribe, JobContext, WorkerOptions, cli, RoomInputOptions
from livekit.agents import Agent, AgentSession, function_tool
from livekit.plugins import assemblyai, elevenlabs, silero
from livekit.plugins import anthropic as lk_anthropic

from app.voice.prompts import SYSTEM_PROMPT_EN, SYSTEM_PROMPT_ES, AUTOMOTIVE_TERMS_EN, AUTOMOTIVE_TERMS_ES

logger = logging.getLogger("workbay.voice")
BACKEND_URL = os.getenv("BACKEND_URL", "http://localhost:8000")


class WorkbayInspectionAgent(Agent):
    def __init__(self, session_id: str, language: str = "en", room=None):
        prompt = (SYSTEM_PROMPT_EN if language == "en" else SYSTEM_PROMPT_ES).replace(
            "Current session context will be injected at runtime.",
            f"Session ID: {session_id}"
        )
        super().__init__(instructions=prompt)
        self.session_id = session_id
        self.language = language
        self._item_index = 0
        self._room = room
        self._checklist_items = []

    async def on_enter(self):
        await self._load_checklist()
        greeting = (
            "Workbay inspection ready. Tell me the vehicle year, make, and model to begin."
            if self.language == "en"
            else "Inspección Workbay lista. Dígame el año, marca y modelo del vehículo para comenzar."
        )
        await self.session.say(greeting, allow_interruptions=True)

    async def _load_checklist(self):
        try:
            async with httpx.AsyncClient(base_url=BACKEND_URL, timeout=10.0) as client:
                r = await client.get(f"/sessions/{self.session_id}")
                if r.status_code == 200:
                    data = r.json()
                    template_id = data.get("checklist_template_id")
                    if template_id:
                        cr = await client.get(f"/checklists/{template_id}")
                        if cr.status_code == 200:
                            items = cr.json().get("items", {}).get("items", [])
                            self._checklist_items = items
                            logger.info(f"Loaded {len(items)} checklist items for session {self.session_id}")
        except Exception as e:
            logger.warning(f"Could not load checklist: {e}")

    async def _send_photo_request(self, item_id: str, reason: str, auto: bool = False):
        """Send photo request data message to mobile app."""
        if self._room:
            try:
                payload = json.dumps({
                    "type": "photo_request",
                    "item_id": item_id,
                    "reason": reason,
                    "session_id": self.session_id,
                    "auto": auto,
                }).encode()
                await self._room.local_participant.publish_data(payload, reliable=True)
                logger.info(f"Photo request sent for {item_id} (auto={auto}): {reason}")
            except Exception as e:
                logger.warning(f"Failed to send photo request: {e}")

    @function_tool
    async def save_finding(
        self,
        item_id: Annotated[str, "The checklist item ID being recorded"],
        transcript: Annotated[str, "Exactly what the technician said about this item"],
        condition: Annotated[str, "Condition: good, fair, poor, or na"],
        structured_data: Annotated[dict, "Any extracted measurements or ratings"] = {},
    ) -> str:
        """Save a technician finding for a checklist item to the database. Automatically requests a photo if condition is poor or fair."""
        try:
            async with httpx.AsyncClient(base_url=BACKEND_URL, timeout=10.0) as client:
                r = await client.post(f"/sessions/{self.session_id}/findings", json={
                    "checklist_item_id": item_id,
                    "transcript": transcript,
                    "condition": condition,
                    "structured_data": structured_data,
                })
                if r.status_code == 201:
                    result = f"Finding saved for {item_id}: {condition}"
                    # Auto-request photo whenever an issue is detected (poor or fair)
                    if condition in ("poor", "fair"):
                        await self._send_photo_request(
                            item_id,
                            f"Issue detected ({condition} condition) — photo required for documentation",
                            auto=True,
                        )
                        result += ". Photo automatically requested."
                    return result
                return f"Error saving finding: {r.status_code}"
        except Exception as e:
            return f"Error: {e}"

    @function_tool
    async def get_current_item(self) -> str:
        """Get the current checklist item to inspect."""
        if not self._checklist_items:
            return "No checklist loaded. Proceed with general inspection."
        if self._item_index >= len(self._checklist_items):
            return "All checklist items complete."
        item = self._checklist_items[self._item_index]
        total = len(self._checklist_items)
        return f"Item {self._item_index + 1} of {total}: {item.get('label', item.get('name', 'Unknown'))} (ID: {item.get('id', str(self._item_index))}) — Category: {item.get('category', 'General')}"

    @function_tool
    async def advance_checklist(self) -> str:
        """Move to the next checklist item."""
        self._item_index += 1
        if self._item_index >= len(self._checklist_items):
            return "All items complete. Ready to finish inspection."
        item = self._checklist_items[self._item_index]
        return f"Next item ({self._item_index + 1}/{len(self._checklist_items)}): {item.get('label', item.get('name', 'Unknown'))}"

    @function_tool
    async def go_back(self) -> str:
        """Go back to the previous checklist item."""
        if self._item_index > 0:
            self._item_index -= 1
        item = self._checklist_items[self._item_index]
        return f"Back to item {self._item_index + 1}: {item.get('label', item.get('name', 'Unknown'))}"

    @function_tool
    async def request_photo(
        self,
        item_id: Annotated[str, "The checklist item ID requiring a photo"],
        reason: Annotated[str, "Why a photo is needed"],
    ) -> str:
        """Signal the mobile app that a photo is needed for this item."""
        logger.info(f"Manual photo requested for item {item_id}: {reason}")
        await self._send_photo_request(item_id, reason, auto=False)
        return f"Photo request sent for {item_id}. Waiting for technician to capture image."

    @function_tool
    async def mark_complete(self) -> str:
        """Mark the inspection session as complete and generate the report."""
        try:
            async with httpx.AsyncClient(base_url=BACKEND_URL, timeout=10.0) as client:
                r = await client.post(f"/sessions/{self.session_id}/complete")
                if r.status_code == 200:
                    return "Inspection complete. Report is ready."
                return f"Error completing session: {r.status_code}"
        except Exception as e:
            return f"Error: {e}"


async def entrypoint(ctx: JobContext):
    await ctx.connect(auto_subscribe=AutoSubscribe.AUDIO_ONLY)

    room_name = ctx.room.name
    session_id = room_name.replace("inspection-", "")
    language = ctx.room.metadata if ctx.room.metadata in ("en", "es") else "en"

    logger.info(f"Voice agent started for session {session_id}, language={language}")

    agent_session = AgentSession(
        vad=silero.VAD.load(),
        stt=assemblyai.STT(
            api_key=os.getenv("ASSEMBLYAI_API_KEY"),
        ),
        llm=lk_anthropic.LLM(
            model="claude-sonnet-4-5",
            api_key=os.getenv("ANTHROPIC_API_KEY"),
        ),
        tts=elevenlabs.TTS(
            api_key=os.getenv("ELEVENLABS_API_KEY"),
            voice_id="21m00Tcm4TlvDq8ikWAM",
            model="eleven_turbo_v2",
        ),
    )

    await agent_session.start(
        room=ctx.room,
        agent=WorkbayInspectionAgent(session_id=session_id, language=language, room=ctx.room),
        room_input_options=RoomInputOptions(),
    )

    await asyncio.sleep(float("inf"))


if __name__ == "__main__":
    cli.run_app(
        WorkerOptions(
            entrypoint_fnc=entrypoint,
            api_key=os.getenv("LIVEKIT_API_KEY"),
            api_secret=os.getenv("LIVEKIT_API_SECRET"),
            ws_url=os.getenv("LIVEKIT_URL"),
        )
    )
