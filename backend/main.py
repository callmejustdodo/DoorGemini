"""FastAPI backend for AI Doorbell — WebSocket streaming + REST endpoints."""

import asyncio
import json
import logging
import uuid
from contextlib import asynccontextmanager
from datetime import datetime
from pathlib import Path

from fastapi import FastAPI, Request, WebSocket, WebSocketDisconnect
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from backend.config import settings
from backend.gemini_session import GeminiSession
from backend.models import DoorbellSession, Notification
from backend.tools.screenshot import set_last_frame
from backend.tools.telegram import (
    answer_callback_query,
    download_telegram_photo,
    send_telegram_message,
    set_webhook,
)

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)

# In-memory state
active_session: GeminiSession | None = None
doorbell_state = DoorbellSession(id=str(uuid.uuid4()))
notifications: list[Notification] = []

# WebSocket binary frame prefixes
FRAME_AUDIO = 0x01
FRAME_VIDEO = 0x02
FRAME_CONTROL = 0x03


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("AI Doorbell starting up")
    # Register Telegram webhook if configured
    if settings.WEBHOOK_BASE_URL and settings.TELEGRAM_BOT_TOKEN:
        webhook_url = f"{settings.WEBHOOK_BASE_URL.rstrip('/')}/api/telegram/webhook"
        await set_webhook(webhook_url)
    yield
    # Cleanup on shutdown
    global active_session
    if active_session:
        await active_session.disconnect()
        active_session = None
    logger.info("AI Doorbell shut down")


app = FastAPI(title="AI Doorbell", lifespan=lifespan)

# Serve static frontend files
static_dir = Path(__file__).parent / "static"
if static_dir.exists():
    app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")


@app.get("/")
async def index():
    """Serve the frontend HTML page."""
    index_path = static_dir / "index.html"
    if index_path.exists():
        return HTMLResponse(content=index_path.read_text())
    return HTMLResponse(content="<h1>AI Doorbell</h1><p>Frontend not found.</p>")


@app.websocket("/ws/doorbell")
async def doorbell_websocket(ws: WebSocket):
    """Main doorbell WebSocket: binary framing protocol for audio/video/control."""
    global active_session, doorbell_state

    await ws.accept()
    logger.info("WebSocket client connected")

    # Lazy-import tool handlers to avoid circular imports
    from backend.tools import TOOL_HANDLERS

    session = GeminiSession(tool_handlers=TOOL_HANDLERS)

    # Wire up callbacks to forward Gemini output to the WebSocket client
    async def on_audio(data: bytes):
        frame = bytes([FRAME_AUDIO]) + data
        try:
            await ws.send_bytes(frame)
        except Exception:
            pass

    async def on_subtitle(text: str, speaker: str):
        msg = json.dumps({"type": "subtitle", "text": text, "speaker": speaker})
        frame = bytes([FRAME_CONTROL]) + msg.encode("utf-8")
        try:
            await ws.send_bytes(frame)
        except Exception:
            pass

    async def on_interrupted():
        msg = json.dumps({"type": "status", "status": "interrupted"})
        frame = bytes([FRAME_CONTROL]) + msg.encode("utf-8")
        try:
            await ws.send_bytes(frame)
        except Exception:
            pass

    async def on_tool_call_start(tool_name: str):
        logger.info("Tool call: %s", tool_name)
        friendly = tool_name.replace("_", " ").title()
        msg = json.dumps({"type": "tool_call", "tool": tool_name, "label": friendly})
        frame = bytes([FRAME_CONTROL]) + msg.encode("utf-8")
        try:
            await ws.send_bytes(frame)
        except Exception:
            pass

    session.on_audio = on_audio
    session.on_subtitle = on_subtitle
    session.on_interrupted = on_interrupted
    session.on_tool_call_start = on_tool_call_start

    active_session = session

    try:
        await session.connect()

        # Send session connected status
        status_msg = json.dumps(
            {"type": "session_state", "connected": True, "resumable": True}
        )
        await ws.send_bytes(
            bytes([FRAME_CONTROL]) + status_msg.encode("utf-8")
        )

        doorbell_state.status = "active"
        doorbell_state.started_at = datetime.now()

        # Main receive loop: read binary frames from the client
        while True:
            data = await ws.receive_bytes()
            if len(data) < 2:
                continue

            frame_type = data[0]
            payload = data[1:]

            if frame_type == FRAME_AUDIO:
                await session.send_audio(payload)

            elif frame_type == FRAME_VIDEO:
                set_last_frame(payload)
                await session.send_video(payload)

            elif frame_type == FRAME_CONTROL:
                try:
                    control = json.loads(payload.decode("utf-8"))
                    action = control.get("action", "")

                    if action == "stop":
                        break
                    elif action == "mic_pause":
                        await session.send_audio_stream_end()
                    elif action == "mic_resume":
                        pass  # Audio will resume on next audio frame

                except json.JSONDecodeError:
                    logger.warning("Invalid control frame")

    except WebSocketDisconnect:
        logger.info("WebSocket client disconnected")
    except Exception as e:
        logger.error("WebSocket error: %s", e)
        try:
            error_msg = json.dumps({"type": "error", "message": str(e)})
            await ws.send_bytes(
                bytes([FRAME_CONTROL]) + error_msg.encode("utf-8")
            )
        except Exception:
            pass
    finally:
        await session.disconnect()
        active_session = None
        doorbell_state.status = "idle"
        doorbell_state.ended_at = datetime.now()
        logger.info("Doorbell session ended")


# --- REST Endpoints ---


@app.post("/api/doorbell/start")
async def start_session():
    """Start a doorbell session (WebSocket is the primary interface)."""
    return JSONResponse({"status": doorbell_state.status, "id": doorbell_state.id})


@app.post("/api/doorbell/stop")
async def stop_session():
    """Stop the active doorbell session."""
    global active_session
    if active_session:
        await active_session.disconnect()
        active_session = None
    doorbell_state.status = "idle"
    return JSONResponse({"status": "stopped"})


@app.get("/api/notifications")
async def get_notifications():
    """Get notification history."""
    return [n.model_dump() for n in notifications]


async def _handle_telegram_message(message: dict, chat_id: str):
    """Handle Telegram messages for face registration.

    Commands (via photo caption):
      add <Name> <relation> <memo>   — register face with photo
      remove <Name>                  — remove face from DB

    Text-only commands:
      remove <Name>                  — remove face from DB
    """
    from backend.tools.face_registration import register_face, remove_face

    caption = message.get("caption", "").strip()
    text = message.get("text", "").strip()
    photos = message.get("photo", [])

    # Photo + caption starting with "add"
    if photos and caption.lower().startswith("add "):
        parts = caption[4:].strip().split(None, 2)
        if not parts:
            await send_telegram_message(chat_id, "Usage: add <Name> <relation> <memo>")
            return

        name = parts[0]
        relation = parts[1] if len(parts) > 1 else "unknown"
        memo = parts[2] if len(parts) > 2 else ""

        # Download the largest photo
        file_id = photos[-1]["file_id"]
        try:
            photo_bytes = await download_telegram_photo(file_id)
            result = await register_face(photo_bytes, name, relation, memo)
            status = result["status"]
            await send_telegram_message(
                chat_id, f"Face {status}: {name} ({relation})"
            )
        except Exception as e:
            logger.error("Face registration failed: %s", e)
            await send_telegram_message(chat_id, f"Registration failed: {e}")
        return

    # Text command: "remove <Name>"
    cmd = caption or text
    if cmd.lower().startswith("remove "):
        name = cmd[7:].strip()
        if name:
            result = await remove_face(name)
            await send_telegram_message(chat_id, f"Face {result['status']}: {name}")
        return


@app.post("/api/telegram/webhook")
async def telegram_webhook(request: Request):
    """Telegram webhook endpoint — handles callback_query from inline buttons.

    Flow: Owner taps button -> Telegram sends callback_query -> we inject text
    into the active Gemini session via send_realtime_input(text=...).
    """
    global active_session

    payload = await request.json()

    # Handle message (photo registration via caption)
    message = payload.get("message")
    if message:
        chat_id = str(message.get("chat", {}).get("id", ""))
        # Security: only accept from configured chat
        if chat_id == settings.TELEGRAM_CHAT_ID:
            await _handle_telegram_message(message, chat_id)
        return JSONResponse({"ok": True})

    # Handle callback_query (inline button press)
    callback_query = payload.get("callback_query")
    if not callback_query:
        return JSONResponse({"ok": True})

    callback_data = callback_query.get("data", "")
    callback_query_id = callback_query.get("id", "")

    command_map = {
        "let_in": "The homeowner says: Tell them to come in, they are welcome.",
        "wait": "The homeowner says: Please ask them to wait a moment.",
        "decline": "The homeowner says: Please politely decline and ask them to leave.",
    }

    text = command_map.get(callback_data)

    if text and active_session:
        await active_session.inject_text(text)
        # Answer callback to dismiss Telegram loading indicator
        await answer_callback_query(callback_query_id, f"Command sent: {callback_data}")
        logger.info("Owner command relayed: %s", callback_data)
        return JSONResponse({"ok": True, "relayed": callback_data})

    if callback_query_id:
        await answer_callback_query(callback_query_id, "No active session")

    return JSONResponse({"ok": True, "relayed": None})


@app.post("/api/owner/command")
async def owner_command(payload: dict):
    """Direct owner command endpoint (for testing without Telegram).

    Uses send_realtime_input(text=...) — this is new user input, not conversation history.
    """
    global active_session

    command = payload.get("command", "")
    text = payload.get("text", "")

    command_map = {
        "let_in": "The homeowner says: Tell them to come in, they are welcome.",
        "wait": "The homeowner says: Please ask them to wait a moment.",
        "decline": "The homeowner says: Please politely decline and ask them to leave.",
    }

    inject_text = command_map.get(command, text)
    if inject_text and active_session:
        await active_session.inject_text(inject_text)
        return JSONResponse({"status": "relayed", "command": command or "custom"})

    return JSONResponse({"status": "no_active_session"}, status_code=404)


@app.get("/api/config")
async def get_config():
    """Get current doorbell configuration."""
    return {
        "owner_name": settings.OWNER_NAME,
        "language": settings.LANGUAGE,
        "delivery_instructions": settings.DELIVERY_INSTRUCTIONS,
    }
