"""
Workbay AI Voice Agent
LiveKit Agents v1.x + AssemblyAI STT + ElevenLabs TTS + Claude Sonnet 4.6
"""
import os
import logging
import asyncio

from livekit.agents import AutoSubscribe, JobContext, WorkerOptions, cli, llm
from livekit.agents.voice_assistant import VoiceAssistant
from livekit.plugins import assemblyai, elevenlabs
from livekit.plugins import anthropic as lk_anthropic
from livekit.plugins import silero

from app.voice.prompts import SYSTEM_PROMPT_EN, SYSTEM_PROMPT_ES, AUTOMOTIVE_TERMS_EN, AUTOMOTIVE_TERMS_ES
from app.voice.tools import handle_tool_call

logger = logging.getLogger("workbay.voice")

session_states: dict = {}


async def entrypoint(ctx: JobContext):
    await ctx.connect(auto_subscribe=AutoSubscribe.AUDIO_ONLY)

    room_name = ctx.room.name
    session_id = room_name.replace("inspection-", "")
    language = "en"

    session_states[session_id] = {
        "session_id": session_id,
        "current_item_index": 0,
        "checklist_items": [],
        "language": language
    }

    logger.info(f"Voice agent started for session {session_id}")

    initial_ctx = llm.ChatContext().append(
        role="system",
        text=SYSTEM_PROMPT_EN if language == "en" else SYSTEM_PROMPT_ES
    )

    assistant = VoiceAssistant(
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
        chat_ctx=initial_ctx,
    )

    assistant.start(ctx.room)

    greeting = (
        "Workbay inspection ready. Tell me the vehicle year, make, and model to begin."
        if language == "en"
        else "Inspección Workbay lista. Dígame el año, marca y modelo del vehículo para comenzar."
    )
    await asyncio.sleep(1)
    await assistant.say(greeting, allow_interruptions=True)
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
