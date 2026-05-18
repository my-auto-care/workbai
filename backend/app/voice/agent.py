"""
Workbay AI Voice Agent
LiveKit Agents v1.x + AssemblyAI STT + ElevenLabs TTS + Claude Sonnet
"""
import os
import logging
import asyncio

from livekit.agents import AutoSubscribe, JobContext, WorkerOptions, cli, RoomInputOptions
from livekit.agents import Agent, AgentSession
from livekit.plugins import assemblyai, elevenlabs, silero
from livekit.plugins import anthropic as lk_anthropic

from app.voice.prompts import SYSTEM_PROMPT_EN, SYSTEM_PROMPT_ES, AUTOMOTIVE_TERMS_EN, AUTOMOTIVE_TERMS_ES

logger = logging.getLogger("workbay.voice")


class WorkbayInspectionAgent(Agent):
    def __init__(self, language: str = "en"):
        prompt = SYSTEM_PROMPT_EN if language == "en" else SYSTEM_PROMPT_ES
        super().__init__(instructions=prompt)
        self.language = language

    async def on_enter(self):
        greeting = (
            "Workbay inspection ready. Tell me the vehicle year, make, and model to begin."
            if self.language == "en"
            else "Inspección Workbay lista. Dígame el año, marca y modelo del vehículo para comenzar."
        )
        await self.session.say(greeting, allow_interruptions=True)


async def entrypoint(ctx: JobContext):
    await ctx.connect(auto_subscribe=AutoSubscribe.AUDIO_ONLY)

    room_name = ctx.room.name
    session_id = room_name.replace("inspection-", "")
    language = "en"

    logger.info(f"Voice agent started for session {session_id}")

    session = AgentSession(
        vad=silero.VAD.load(),
        stt=assemblyai.STT(
            api_key=os.getenv("ASSEMBLYAI_API_KEY"),
            word_boost=AUTOMOTIVE_TERMS_EN if language == "en" else AUTOMOTIVE_TERMS_ES,
        ),
        llm=lk_anthropic.LLM(
            model="claude-sonnet-4-5",
            api_key=os.getenv("ANTHROPIC_API_KEY"),
        ),
        tts=elevenlabs.TTS(
            api_key=os.getenv("ELEVENLABS_API_KEY"),
            voice_id="21m00Tcm4TlvDq8ikWAM",
            model_id="eleven_turbo_v2",
        ),
    )

    await session.start(
        room=ctx.room,
        agent=WorkbayInspectionAgent(language=language),
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
