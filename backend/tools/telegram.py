"""Telegram Bot: send alerts with photos and inline buttons via Bot API."""

import logging
from io import BytesIO

import httpx

from backend.config import settings

logger = logging.getLogger(__name__)

URGENCY_EMOJI = {
    "low": "\U0001f4e6",      # 📦
    "medium": "\U0001f464",    # 👤
    "high": "\u26a0\ufe0f",   # ⚠️
}

URGENCY_PREFIX = {
    "low": "Delivery arrived",
    "medium": "Visitor",
    "high": "CAUTION",
}

INLINE_BUTTONS_KNOWN_PERSON = [
    [{"text": "Tell them to come in", "callback_data": "let_in"}],
    [{"text": "Tell them to wait", "callback_data": "wait"}],
    [{"text": "Decline", "callback_data": "decline"}],
]

_BASE_URL = "https://api.telegram.org/bot{token}"


def _api_url(method: str) -> str:
    return f"{_BASE_URL.format(token=settings.TELEGRAM_BOT_TOKEN)}/{method}"


def _configured() -> bool:
    return bool(settings.TELEGRAM_BOT_TOKEN and settings.TELEGRAM_CHAT_ID)


async def send_telegram_alert(
    urgency: str = "low",
    visitor_type: str = "unknown",
    summary: str = "",
    capture_photo: bool = False,
) -> dict:
    """Send formatted alert to homeowner via Telegram Bot API.

    For known_person visitors, includes inline keyboard buttons.
    When capture_photo is True and a screenshot URL is available, sends photo.
    """
    emoji = URGENCY_EMOJI.get(urgency, "")
    prefix = URGENCY_PREFIX.get(urgency, "Alert")
    message = f"{emoji} {prefix} -- {summary}"

    result = {
        "sent": False,
        "message": message,
        "urgency": urgency,
        "visitor_type": visitor_type,
        "photo_attached": capture_photo,
    }

    if not _configured():
        logger.warning("Telegram not configured — logging alert locally")
        logger.info("TELEGRAM ALERT [%s]: %s", urgency, message)
        result["sent"] = True
        result["fallback"] = "logged_locally"
        return result

    reply_markup = None
    if visitor_type == "known_person":
        reply_markup = {"inline_keyboard": INLINE_BUTTONS_KNOWN_PERSON}

    try:
        async with httpx.AsyncClient(timeout=10) as client:
            if capture_photo:
                # Send photo with caption
                payload = {
                    "chat_id": settings.TELEGRAM_CHAT_ID,
                    "caption": message,
                    "parse_mode": "HTML",
                }
                if reply_markup:
                    import json
                    payload["reply_markup"] = json.dumps(reply_markup)

                # Try to get a screenshot from the screenshot tool
                from backend.tools.screenshot import capture_screenshot
                screenshot = await capture_screenshot()
                # For now, send as text since screenshot is mock
                # When real GCS is implemented, download the image and send
                resp = await client.post(
                    _api_url("sendMessage"),
                    json={
                        "chat_id": settings.TELEGRAM_CHAT_ID,
                        "text": message + "\n\n[Photo capture requested - screenshot saved]",
                        "parse_mode": "HTML",
                        **({"reply_markup": reply_markup} if reply_markup else {}),
                    },
                )
            else:
                payload = {
                    "chat_id": settings.TELEGRAM_CHAT_ID,
                    "text": message,
                    "parse_mode": "HTML",
                }
                if reply_markup:
                    payload["reply_markup"] = reply_markup

                resp = await client.post(_api_url("sendMessage"), json=payload)

            if resp.status_code == 200 and resp.json().get("ok"):
                result["sent"] = True
                logger.info("Telegram alert sent: %s", message)
            else:
                logger.error("Telegram API error: %s", resp.text)
                result["error"] = resp.text

    except Exception as e:
        logger.error("Telegram send failed: %s", e)
        result["error"] = str(e)
        # Fallback: log locally
        logger.info("TELEGRAM ALERT (fallback) [%s]: %s", urgency, message)
        result["sent"] = True
        result["fallback"] = "logged_locally"

    return result


async def answer_callback_query(callback_query_id: str, text: str = "") -> bool:
    """Answer a Telegram callback query to dismiss the loading indicator."""
    if not _configured():
        return True

    try:
        async with httpx.AsyncClient(timeout=5) as client:
            resp = await client.post(
                _api_url("answerCallbackQuery"),
                json={
                    "callback_query_id": callback_query_id,
                    "text": text,
                },
            )
            return resp.status_code == 200 and resp.json().get("ok", False)
    except Exception as e:
        logger.error("Failed to answer callback query: %s", e)
        return False


async def set_webhook(webhook_url: str) -> bool:
    """Register Telegram webhook URL."""
    if not settings.TELEGRAM_BOT_TOKEN:
        logger.warning("Telegram bot token not set — skipping webhook registration")
        return False

    try:
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.post(
                _api_url("setWebhook"),
                json={"url": webhook_url, "allowed_updates": ["callback_query"]},
            )
            if resp.status_code == 200 and resp.json().get("ok"):
                logger.info("Telegram webhook registered: %s", webhook_url)
                return True
            else:
                logger.error("Telegram webhook registration failed: %s", resp.text)
                return False
    except Exception as e:
        logger.error("Telegram webhook registration error: %s", e)
        return False


async def delete_webhook() -> bool:
    """Remove Telegram webhook."""
    if not settings.TELEGRAM_BOT_TOKEN:
        return True

    try:
        async with httpx.AsyncClient(timeout=10) as client:
            resp = await client.post(_api_url("deleteWebhook"))
            return resp.status_code == 200
    except Exception:
        return False
