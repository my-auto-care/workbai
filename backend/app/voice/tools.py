"""
Voice agent tool definitions — called by Claude during inspection sessions.
These are the tool schemas passed to the LLM and the handler functions.
"""
import httpx
import os
from typing import Optional

BACKEND_URL = os.getenv("BACKEND_URL", "http://localhost:8000")

# Tool schemas for Claude
TOOL_DEFINITIONS = [
    {
        "name": "get_checklist",
        "description": "Get the checklist items for the current inspection session",
        "input_schema": {
            "type": "object",
            "properties": {
                "session_id": {"type": "string", "description": "The inspection session UUID"}
            },
            "required": ["session_id"]
        }
    },
    {
        "name": "get_current_item",
        "description": "Get the current checklist item being inspected",
        "input_schema": {
            "type": "object",
            "properties": {
                "session_id": {"type": "string", "description": "The inspection session UUID"}
            },
            "required": ["session_id"]
        }
    },
    {
        "name": "save_finding",
        "description": "Save a technician finding for the current checklist item",
        "input_schema": {
            "type": "object",
            "properties": {
                "session_id": {"type": "string"},
                "item_id": {"type": "string", "description": "Checklist item ID"},
                "transcript": {"type": "string", "description": "What the technician said"},
                "condition": {"type": "string", "enum": ["good", "fair", "poor", "na"]},
                "structured_data": {"type": "object", "description": "Extracted measurements or ratings"}
            },
            "required": ["session_id", "item_id", "transcript", "condition"]
        }
    },
    {
        "name": "advance_checklist",
        "description": "Move to the next checklist item",
        "input_schema": {
            "type": "object",
            "properties": {
                "session_id": {"type": "string"}
            },
            "required": ["session_id"]
        }
    },
    {
        "name": "request_photo",
        "description": "Ask the technician to take a photo of the current item",
        "input_schema": {
            "type": "object",
            "properties": {
                "session_id": {"type": "string"},
                "item_id": {"type": "string"},
                "reason": {"type": "string", "description": "Why a photo is needed"}
            },
            "required": ["session_id", "item_id", "reason"]
        }
    },
    {
        "name": "mark_complete",
        "description": "Mark the inspection session as complete",
        "input_schema": {
            "type": "object",
            "properties": {
                "session_id": {"type": "string"}
            },
            "required": ["session_id"]
        }
    }
]


async def handle_tool_call(tool_name: str, tool_input: dict, session_state: dict) -> str:
    """Execute a tool call and return the result as a string."""
    session_id = tool_input.get("session_id") or session_state.get("session_id")

    async with httpx.AsyncClient(base_url=BACKEND_URL, timeout=10.0) as client:

        if tool_name == "get_checklist":
            r = await client.get(f"/sessions/{session_id}")
            if r.status_code == 200:
                data = r.json()
                template_id = data.get("checklist_template_id")
                if template_id:
                    cr = await client.get(f"/checklists/{template_id}")
                    if cr.status_code == 200:
                        return str(cr.json().get("items", {}))
            return "Checklist not found"

        elif tool_name == "get_current_item":
            idx = session_state.get("current_item_index", 0)
            items = session_state.get("checklist_items", [])
            if idx < len(items):
                item = items[idx]
                return f"Current item: {item.get('name')} (ID: {item.get('id')})"
            return "No more items"

        elif tool_name == "save_finding":
            payload = {
                "checklist_item_id": tool_input.get("item_id"),
                "transcript": tool_input.get("transcript"),
                "condition": tool_input.get("condition", "na"),
                "structured_data": tool_input.get("structured_data", {})
            }
            r = await client.post(f"/sessions/{session_id}/findings", json=payload)
            if r.status_code == 201:
                return f"Finding saved: {r.json().get('id')}"
            return f"Error saving finding: {r.status_code}"

        elif tool_name == "advance_checklist":
            session_state["current_item_index"] = session_state.get("current_item_index", 0) + 1
            idx = session_state["current_item_index"]
            items = session_state.get("checklist_items", [])
            if idx < len(items):
                return f"Advanced to item {idx + 1}: {items[idx].get('name')}"
            return "All items complete"

        elif tool_name == "request_photo":
            return f"Photo requested for item {tool_input.get('item_id')}: {tool_input.get('reason')}"

        elif tool_name == "mark_complete":
            r = await client.post(f"/sessions/{session_id}/complete")
            if r.status_code == 200:
                return "Session marked complete"
            return f"Error completing session: {r.status_code}"

    return "Unknown tool"
