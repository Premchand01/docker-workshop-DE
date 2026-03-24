"""
notifier.py — Telegram bot notification sender.
Sends rich seat-match alerts with inline deep-link buttons.
"""

import logging
import aiohttp
from matcher import SeatMatch

logger = logging.getLogger(__name__)

TELEGRAM_API = "https://api.telegram.org/bot{token}/{method}"


class TelegramNotifier:
    def __init__(self, config: dict):
        tg = config["telegram"]
        self.token: str = tg["bot_token"]
        self.chat_id: str = str(tg["chat_id"])

    async def send_match(self, match: SeatMatch):
        """Send a formatted seat-match alert with a Book Now button."""
        seats_label = ", ".join(
            f"{match.row}{s.number}" for s in match.seats
        )
        priority_emoji = ["🥇", "🥈", "🥉"].get(match.priority, "✅") \
            if match.priority < 3 else "✅"
        top_row_tag = " 🔥 *TOP ROW*" if match.is_top_row else ""

        text = (
            f"{priority_emoji} *Seats Found!*{top_row_tag}\n\n"
            f"🎬 *{match.show.show.theatre if hasattr(match.show, 'show') else match.show.theatre}*\n"
            f"📅 {match.show.show_date} · {match.show.show_time}\n"
            f"💺 Row *{match.row}* — Seats `{seats_label}`\n"
            f"🏷️ {match.category}\n"
            f"💰 ₹{match.total_price:,}\n\n"
            f"⏱️ _Tap below to book before they're gone!_"
        )

        keyboard = {
            "inline_keyboard": [[
                {"text": "🎟️ Book Now →", "url": match.booking_url}
            ]]
        }

        await self._send_message(text, reply_markup=keyboard)
        logger.info(f"Alert sent: Row {match.row} seats {seats_label}")

    async def send_status(self, message: str):
        """Send a plain status message (startup, errors, etc.)."""
        await self._send_message(f"ℹ️ {message}")

    async def send_error(self, error: str):
        await self._send_message(f"⚠️ Agent error: {error}")

    async def _send_message(self, text: str, reply_markup: dict = None):
        url = TELEGRAM_API.format(token=self.token, method="sendMessage")
        payload = {
            "chat_id": self.chat_id,
            "text": text,
            "parse_mode": "Markdown",
            "disable_web_page_preview": False,
        }
        if reply_markup:
            import json
            payload["reply_markup"] = json.dumps(reply_markup)

        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(url, json=payload, timeout=aiohttp.ClientTimeout(total=10)) as resp:
                    if resp.status != 200:
                        body = await resp.text()
                        logger.error(f"Telegram API error {resp.status}: {body}")
        except Exception as e:
            logger.error(f"Failed to send Telegram message: {e}")
