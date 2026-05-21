"""
Workbay AI Voice Agent
LiveKit Agents v1.x + AssemblyAI STT + ElevenLabs TTS + Claude Sonnet

AI-powered vehicle-specific inspection:
- Detects year/make/model/mileage from technician speech
- Fetches vehicle intelligence (known failure areas, TSBs, mileage alerts)
- Injects that intel into the agent context so all questions are vehicle-specific
- Auto-prompts photos on poor/fair findings
"""
import os
import logging
import asyncio
import httpx
import json
from typing import Annotated, Optional

from livekit.agents import AutoSubscribe, JobContext, WorkerOptions, cli, RoomInputOptions
from livekit.agents import Agent, AgentSession, function_tool
from livekit.plugins import assemblyai, elevenlabs, silero
from livekit.plugins import anthropic as lk_anthropic

from app.voice.prompts import SYSTEM_PROMPT_EN, SYSTEM_PROMPT_ES

logger = logging.getLogger("workbay.voice")
BACKEND_URL = os.getenv("BACKEND_URL", "http://localhost:8000")


class WorkbayInspectionAgent(Agent):
    def __init__(self, session_id: str, language: str = "en", room=None):
        self.session_id = session_id
        self.language = language
        self._item_index = 0
        self._room = room
        self._checklist_items = []
        self._vehicle_intel: Optional[dict] = None
        self._vehicle_info: Optional[dict] = None

        base_prompt = SYSTEM_PROMPT_EN if language == "en" else SYSTEM_PROMPT_ES
        prompt = base_prompt.replace(
            "Current session context will be injected at runtime.",
            f"Session ID: {session_id}"
        )
        super().__init__(instructions=prompt)

    async def on_enter(self):
        await self._load_session_data()
        greeting = (
            "Workbay inspection ready. Tell me the vehicle year, make, model, and mileage to begin."
            if self.language == "en"
            else "Inspección Workbay lista. Dígame el año, marca, modelo y millaje del vehículo para comenzar."
        )
        await self.session.say(greeting, allow_interruptions=True)

    async def _load_session_data(self):
        """Load checklist and any pre-existing vehicle data from the session."""
        try:
            async with httpx.AsyncClient(base_url=BACKEND_URL, timeout=10.0) as client:
                r = await client.get(f"/sessions/{self.session_id}")
                if r.status_code == 200:
                    data = r.json()

                    # Load checklist
                    template_id = data.get("checklist_template_id")
                    if template_id:
                        cr = await client.get(f"/checklists/{template_id}")
                        if cr.status_code == 200:
                            items = cr.json().get("items", {}).get("items", [])
                            self._checklist_items = items
                            logger.info(f"Loaded {len(items)} checklist items")

                    # If vehicle info already on session, pre-fetch intel
                    year = data.get("vehicle_year")
                    make = data.get("vehicle_make")
                    model = data.get("vehicle_model")
                    mileage = data.get("vehicle_mileage")
                    if year and make and model:
                        self._vehicle_info = {"year": year, "make": make, "model": model, "mileage": mileage}
                        await self._fetch_vehicle_intel(year, make, model, mileage, data.get("customer_concern"))
        except Exception as e:
            logger.warning(f"Could not load session data: {e}")

    async def _fetch_vehicle_intel(self, year, make, model, mileage=None, concern=None):
        """Call the vehicle intelligence endpoint and update agent instructions."""
        try:
            payload = {"year": int(year), "make": make, "model": model}
            if mileage:
                payload["mileage"] = int(mileage)
            if concern:
                payload["customer_concern"] = concern

            async with httpx.AsyncClient(base_url=BACKEND_URL, timeout=30.0) as client:
                r = await client.post("/vehicle-intelligence", json=payload)
                if r.status_code == 200:
                    self._vehicle_intel = r.json()
                    logger.info(f"Vehicle intel loaded for {year} {make} {model}")
                    # Inject intel into agent instructions
                    await self._inject_vehicle_context()
                else:
                    logger.warning(f"Vehicle intel returned {r.status_code}")
        except Exception as e:
            logger.warning(f"Could not fetch vehicle intel: {e}")

    async def _inject_vehicle_context(self):
        """Update the agent's system prompt with vehicle-specific intelligence."""
        if not self._vehicle_intel:
            return

        intel = self._vehicle_intel
        v = intel.get("vehicle", {})
        mileage_str = f"{v.get('mileage'):,} miles" if v.get('mileage') else "unknown mileage"

        lines = [
            f"\n\n=== VEHICLE INTELLIGENCE: {v.get('year')} {v.get('make')} {v.get('model')} ({mileage_str}) ===",
            "\nINSPECTION FOCUS:",
            intel.get("inspection_focus", ""),
            "\nKNOWN ISSUES FOR THIS VEHICLE (check these specifically):",
        ]
        for issue in intel.get("known_issues", []):
            priority = issue.get("priority", "").upper()
            lines.append(f"  [{priority}] {issue.get('area')}: {issue.get('description')}")
            lines.append(f"    → What to check: {issue.get('what_to_check', '')}")

        lines.append("\nMILEAGE ALERTS:")
        for alert in intel.get("mileage_alerts", []):
            lines.append(f"  [{alert.get('status', '').upper()}] {alert.get('item')}: {alert.get('notes', '')}")

        lines.append("\nPRIORITY QUESTIONS TO ASK THIS TECHNICIAN:")
        for q in intel.get("priority_questions", []):
            lines.append(f"  - {q}")

        lines.append("\nTSB / RECALL NOTES:")
        for tsb in intel.get("tsb_notes", []):
            lines.append(f"  - {tsb}")

        lines.append("\nCRITICAL: Use this vehicle intelligence to ask SPECIFIC questions during inspection.")
        lines.append("Do NOT ask generic questions. Reference the known issues above when checking each area.")
        lines.append("=== END VEHICLE INTELLIGENCE ===")

        intel_block = "\n".join(lines)

        # Update instructions on the live session
        base_prompt = SYSTEM_PROMPT_EN if self.language == "en" else SYSTEM_PROMPT_ES
        new_instructions = base_prompt.replace(
            "Current session context will be injected at runtime.",
            f"Session ID: {self.session_id}{intel_block}"
        )
        self._instructions = new_instructions
        # Notify the session to update context
        if hasattr(self, 'session') and self.session:
            try:
                await self.session.update_agent(self)
            except Exception:
                pass  # update_agent may not exist in all versions — instructions still used on next turn

        logger.info("Agent instructions updated with vehicle intelligence")

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
                logger.info(f"Photo request sent for {item_id} (auto={auto})")
            except Exception as e:
                logger.warning(f"Failed to send photo request: {e}")

    # ─── TOOLS ────────────────────────────────────────────────────────────────

    @function_tool
    async def set_vehicle_info(
        self,
        year: Annotated[int, "Vehicle model year (e.g. 2018)"],
        make: Annotated[str, "Vehicle manufacturer (e.g. Ford)"],
        model: Annotated[str, "Vehicle model name (e.g. F-150)"],
        mileage: Annotated[Optional[int], "Current odometer reading in miles"] = None,
    ) -> str:
        """Record the vehicle year, make, model, and mileage. Call this as soon as the technician provides vehicle info. This triggers AI analysis of known failure areas for this specific vehicle."""
        self._vehicle_info = {"year": year, "make": make, "model": model, "mileage": mileage}

        # Save to session
        try:
            async with httpx.AsyncClient(base_url=BACKEND_URL, timeout=10.0) as client:
                session_data = await client.get(f"/sessions/{self.session_id}")
                if session_data.status_code == 200:
                    concern = session_data.json().get("customer_concern")

                await client.patch(f"/sessions/{self.session_id}", json={
                    "vehicle_year": year,
                    "vehicle_make": make,
                    "vehicle_model": model,
                    "vehicle_mileage": mileage,
                })
        except Exception as e:
            logger.warning(f"Could not save vehicle info: {e}")
            concern = None

        # Fetch vehicle intelligence asynchronously
        await self._fetch_vehicle_intel(year, make, model, mileage, concern if 'concern' in dir() else None)

        mileage_str = f" at {mileage:,} miles" if mileage else ""
        intel_summary = ""
        if self._vehicle_intel:
            issues = self._vehicle_intel.get("known_issues", [])
            critical = [i for i in issues if i.get("priority") == "critical"]
            intel_summary = f" Found {len(issues)} known issues"
            if critical:
                intel_summary += f" including {len(critical)} critical areas"
            intel_summary += ". Inspection questions tailored to this vehicle."

        return f"Vehicle set: {year} {make} {model}{mileage_str}.{intel_summary} Ready to begin inspection."

    @function_tool
    async def get_vehicle_intelligence_summary(self) -> str:
        """Get a summary of known issues and priority areas for the current vehicle."""
        if not self._vehicle_intel:
            if not self._vehicle_info:
                return "No vehicle set yet. Ask for year, make, model, and mileage first."
            return "Vehicle intelligence not yet loaded. Try again in a moment."

        intel = self._vehicle_intel
        v = intel.get("vehicle", {})
        lines = [f"Intelligence for {v.get('year')} {v.get('make')} {v.get('model')}:"]
        lines.append(intel.get("inspection_focus", ""))

        critical = [i for i in intel.get("known_issues", []) if i.get("priority") == "critical"]
        if critical:
            lines.append(f"CRITICAL areas: {', '.join(i.get('area') for i in critical)}")

        overdue = [a for a in intel.get("mileage_alerts", []) if a.get("status") == "overdue"]
        if overdue:
            lines.append(f"Overdue maintenance: {', '.join(a.get('item') for a in overdue)}")

        return "\n".join(lines)

    @function_tool
    async def save_finding(
        self,
        item_id: Annotated[str, "The checklist item ID being recorded"],
        transcript: Annotated[str, "Exactly what the technician said about this item"],
        condition: Annotated[str, "Condition: good, fair, poor, or na"],
        structured_data: Annotated[dict, "Any extracted measurements or ratings"] = {},
    ) -> str:
        """Save a technician finding. Automatically requests photo if condition is poor or fair."""
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
        """Get the current checklist item to inspect. Returns vehicle-specific guidance if available."""
        if not self._checklist_items:
            return "No checklist loaded. Proceed with general inspection."
        if self._item_index >= len(self._checklist_items):
            return "All checklist items complete."
        item = self._checklist_items[self._item_index]
        total = len(self._checklist_items)
        label = item.get('label', item.get('name', 'Unknown'))
        item_id = item.get('id', str(self._item_index))
        category = item.get('category', 'General')

        base = f"Item {self._item_index + 1} of {total}: {label} (ID: {item_id}) — Category: {category}"

        # Append vehicle-specific guidance if intel is available
        if self._vehicle_intel:
            guidance = self._get_item_specific_guidance(label, category)
            if guidance:
                base += f"\nVehicle-specific note: {guidance}"

        return base

    def _get_item_specific_guidance(self, item_label: str, category: str) -> str:
        """Match checklist item to vehicle intel and return specific guidance."""
        if not self._vehicle_intel:
            return ""

        label_lower = item_label.lower()
        category_lower = category.lower()

        for issue in self._vehicle_intel.get("known_issues", []):
            area_lower = issue.get("area", "").lower()
            # Fuzzy match on keywords
            keywords = area_lower.split()
            if any(kw in label_lower or kw in category_lower for kw in keywords if len(kw) > 3):
                priority = issue.get("priority", "").upper()
                check = issue.get("what_to_check", "")
                return f"[{priority} RISK] {issue.get('description')}. {check}"

        for alert in self._vehicle_intel.get("mileage_alerts", []):
            item_name_lower = alert.get("item", "").lower()
            keywords = item_name_lower.split()
            if any(kw in label_lower for kw in keywords if len(kw) > 3):
                status = alert.get("status", "").upper()
                return f"[{status}] {alert.get('notes', '')}"

        return ""

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
        await self._send_photo_request(item_id, reason, auto=False)
        return f"Photo request sent for {item_id}."

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
