"""
agent.py — BookMyShow Seat-Sniper Agent
Main orchestrator: scheduler + scraper + matcher + notifier.

Usage:
    python agent.py                  # uses config.yaml in same directory
    python agent.py --config path/to/config.yaml
"""

import asyncio
import argparse
import logging
import sys
import webbrowser
from datetime import datetime, date
from pathlib import Path

import yaml
from scraper import BMSScraper
from matcher import SeatMatcher, SeatMatch
from notifier import TelegramNotifier


def setup_logging(config: dict):
    log_cfg = config.get("logging", {})
    level = getattr(logging, log_cfg.get("level", "INFO"))
    log_file = log_cfg.get("log_file", "bms_agent.log")
    handlers = [
        logging.StreamHandler(sys.stdout),
        logging.FileHandler(log_file),
    ]
    logging.basicConfig(
        level=level,
        format="%(asctime)s [%(levelname)s] %(name)s — %(message)s",
        handlers=handlers,
    )


def load_config(path: str) -> dict:
    with open(path) as f:
        return yaml.safe_load(f)


def is_week1(config: dict) -> bool:
    """Returns True if today is within 7 days of the movie's release date."""
    release_str = config["movie"].get("release_date")
    if not release_str:
        return False
    release = date.fromisoformat(release_str)
    today = date.today()
    delta = (today - release).days
    return 0 <= delta <= 6


def get_poll_interval(config: dict) -> int:
    polling = config.get("polling", {})
    if is_week1(config):
        interval = polling.get("interval_week1_sec", 10)
        logging.getLogger(__name__).info(
            f"🚀 Week-1 mode active — polling every {interval}s"
        )
        return interval
    return polling.get("interval_normal_sec", 45)


class BMSAgent:
    def __init__(self, config: dict):
        self.config = config
        self.matcher = SeatMatcher(config)
        self.notifier = TelegramNotifier(config)
        self.logger = logging.getLogger("BMSAgent")
        # Track already-alerted seat combos to avoid spam
        self._alerted: dict[str, float] = {}  # key → last_alert_epoch
        self._repeat_interval = config.get("notifications", {}).get(
            "repeat_alert_interval_sec", 120
        )

    def _alert_key(self, match: SeatMatch) -> str:
        seats = ",".join(f"{match.row}{s.number}" for s in match.seats)
        return f"{match.show.theatre}|{match.show.show_date}|{match.show.show_time}|{seats}"

    def _should_alert(self, match: SeatMatch) -> bool:
        key = self._alert_key(match)
        now = datetime.now().timestamp()
        last = self._alerted.get(key, 0)
        if now - last >= self._repeat_interval:
            self._alerted[key] = now
            return True
        return False

    def _week1_top_rows_only(self) -> bool:
        return (
            is_week1(self.config)
            and self.config.get("polling", {}).get("week1_rows_only", True)
        )

    async def run_once(self):
        self.logger.info("🔍 Polling BookMyShow...")
        try:
            async with BMSScraper(self.config) as scraper:
                shows = await scraper.fetch_shows()

            if not shows:
                self.logger.info("No matching shows found this cycle.")
                return

            matches = self.matcher.find_matches(shows)

            # Week-1 filter: only top-row alerts
            if self._week1_top_rows_only():
                matches = [m for m in matches if m.is_top_row]
                if not matches:
                    self.logger.info("Week-1 mode: no top-row seats yet.")
                    return

            if not matches:
                self.logger.info("Shows found but no seats match preferences.")
                return

            best = matches[0]
            self.logger.info(
                f"✅ Match: {best.show.theatre} · {best.show.show_date} · "
                f"Row {best.row} · {len(best.seats)} seat(s)"
            )

            for match in matches[:3]:  # Alert up to 3 best options
                if self._should_alert(match):
                    await self.notifier.send_match(match)

            # Open browser if configured
            if self.config.get("notifications", {}).get("open_browser_on_match"):
                webbrowser.open(best.booking_url)

        except Exception as e:
            self.logger.error(f"Poll cycle error: {e}", exc_info=True)
            await self.notifier.send_error(str(e))

    async def run(self):
        movie = self.config["movie"]["name"]
        self.logger.info(f"🎬 BMS Agent started — watching: {movie}")
        await self.notifier.send_status(
            f"Agent started for *{movie}*. I'll alert you when preferred seats open up!"
        )

        while True:
            await self.run_once()
            interval = get_poll_interval(self.config)
            self.logger.info(f"⏳ Next poll in {interval}s...")
            await asyncio.sleep(interval)


async def main():
    parser = argparse.ArgumentParser(description="BookMyShow Seat-Sniper Agent")
    parser.add_argument("--config", default="config.yaml", help="Path to config.yaml")
    args = parser.parse_args()

    config_path = Path(args.config)
    if not config_path.exists():
        print(f"Config not found: {config_path}")
        sys.exit(1)

    config = load_config(str(config_path))
    setup_logging(config)

    agent = BMSAgent(config)
    try:
        await agent.run()
    except KeyboardInterrupt:
        logging.getLogger(__name__).info("Agent stopped by user.")


if __name__ == "__main__":
    asyncio.run(main())
