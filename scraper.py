"""
scraper.py — BookMyShow seat map scraper using Playwright
Handles JS-rendered seat maps, bot-detection avoidance basics.
"""

import asyncio
import logging
import re
from dataclasses import dataclass
from typing import Optional
from playwright.async_api import async_playwright, Page, BrowserContext

logger = logging.getLogger(__name__)


@dataclass
class SeatInfo:
    row: str
    number: int
    category: str
    price: int
    is_available: bool
    seat_id: str  # BMS internal ID for deep-link generation


@dataclass
class ShowResult:
    theatre: str
    show_date: str
    show_time: str
    seats: list[SeatInfo]
    booking_url: str  # Direct URL to seat selection page


class BMSScraper:
    USER_AGENT = (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/121.0.0.0 Safari/537.36"
    )

    def __init__(self, config: dict):
        self.config = config
        self._browser = None
        self._context: Optional[BrowserContext] = None

    async def __aenter__(self):
        self._playwright = await async_playwright().start()
        self._browser = await self._playwright.chromium.launch(
            headless=True,
            args=["--no-sandbox", "--disable-blink-features=AutomationControlled"],
        )
        self._context = await self._browser.new_context(
            user_agent=self.USER_AGENT,
            viewport={"width": 1280, "height": 800},
            locale="en-IN",
            timezone_id="Asia/Kolkata",
        )
        # Mask webdriver flag
        await self._context.add_init_script(
            "Object.defineProperty(navigator, 'webdriver', {get: () => undefined})"
        )
        return self

    async def __aexit__(self, *args):
        if self._context:
            await self._context.close()
        if self._browser:
            await self._browser.close()
        await self._playwright.stop()

    async def fetch_shows(self) -> list[ShowResult]:
        """Main entry point — returns available shows matching config."""
        movie_url = self.config["movie"]["url"]
        results = []

        page = await self._context.new_page()
        try:
            logger.info(f"Navigating to: {movie_url}")
            await page.goto(movie_url, wait_until="networkidle", timeout=30_000)
            await asyncio.sleep(2)  # Let JS settle

            # Find shows for configured theatres + dates
            for theatre_cfg in self.config["theatres"]:
                theatre_name = theatre_cfg["name"]
                shows = await self._get_shows_for_theatre(page, theatre_name)
                results.extend(shows)

        except Exception as e:
            logger.error(f"Error fetching shows: {e}")
        finally:
            await page.close()

        return results

    async def _get_shows_for_theatre(
        self, page: Page, theatre_name: str
    ) -> list[ShowResult]:
        """Find show slots for a specific theatre on configured dates."""
        results = []
        target_dates = self.config["shows"]["dates"]
        target_times = self.config["shows"]["times"]
        preferred_categories = [c.upper() for c in self.config["seats"]["categories"]]

        for date_str in target_dates:
            # Click the date tab
            try:
                await self._select_date(page, date_str)
                await asyncio.sleep(1)
            except Exception:
                logger.debug(f"Could not select date {date_str}")
                continue

            # Find theatre row
            theatre_rows = await page.query_selector_all(
                f'[data-theatre-name*="{theatre_name}"], '
                f'.venue-name:has-text("{theatre_name}")'
            )
            if not theatre_rows:
                logger.debug(f"Theatre not found: {theatre_name}")
                continue

            for theatre_row in theatre_rows:
                # Find show time buttons within this theatre
                show_btns = await theatre_row.query_selector_all(
                    ".show-time-btn, [data-showtime], .showtime"
                )
                for btn in show_btns:
                    time_text = (await btn.inner_text()).strip()
                    if not any(t in time_text for t in target_times):
                        continue

                    # Click the show button to get seat map
                    category_url = await self._click_show_and_get_url(
                        page, btn, preferred_categories
                    )
                    if not category_url:
                        continue

                    seats = await self._parse_seat_map(page)
                    if seats:
                        results.append(
                            ShowResult(
                                theatre=theatre_name,
                                show_date=date_str,
                                show_time=time_text,
                                seats=seats,
                                booking_url=page.url,
                            )
                        )

        return results

    async def _select_date(self, page: Page, date_str: str):
        """Click the date tab matching date_str (YYYY-MM-DD)."""
        # BMS uses short date labels — convert "2025-01-15" → "15 Jan"
        from datetime import datetime
        dt = datetime.strptime(date_str, "%Y-%m-%d")
        label = dt.strftime("%-d %b")  # "15 Jan"
        date_btn = page.locator(f'[data-date="{date_str}"], .date-tab:has-text("{label}")')
        await date_btn.first.click(timeout=5000)

    async def _click_show_and_get_url(
        self, page: Page, btn, categories: list[str]
    ) -> Optional[str]:
        """Click a show time button and navigate to the best available category."""
        try:
            async with page.expect_navigation(timeout=15_000):
                await btn.click()
        except Exception:
            pass

        await asyncio.sleep(2)
        current_url = page.url

        # If a category selection page appeared, pick the best matching category
        for cat in categories:
            cat_btn = page.locator(f'text="{cat}"').first
            if await cat_btn.count() > 0:
                try:
                    async with page.expect_navigation(timeout=10_000):
                        await cat_btn.click()
                    return page.url
                except Exception:
                    pass

        return current_url

    async def _parse_seat_map(self, page: Page) -> list[SeatInfo]:
        """Parse the interactive seat map and return SeatInfo objects."""
        seats: list[SeatInfo] = []

        await page.wait_for_selector(".seat, [data-seatid], .seat-block", timeout=15_000)

        # BMS seat elements typically have data attributes with row, number, status
        seat_elements = await page.query_selector_all(
            ".seat[data-row][data-seatnumber], "
            "[data-seatid][data-status], "
            ".seat-block[data-row]"
        )

        for el in seat_elements:
            try:
                row = (await el.get_attribute("data-row") or "").upper()
                number_str = await el.get_attribute("data-seatnumber") or "0"
                seat_id = await el.get_attribute("data-seatid") or ""
                status = (await el.get_attribute("data-status") or "").lower()
                category = (await el.get_attribute("data-category") or "STANDARD").upper()
                price_str = await el.get_attribute("data-price") or "0"

                # Also check CSS class for availability
                class_attr = await el.get_attribute("class") or ""
                is_booked = "booked" in class_attr or "blocked" in class_attr
                is_available = (
                    status in ("available", "open", "1")
                    and not is_booked
                )

                price = int(re.sub(r"[^\d]", "", price_str)) if price_str else 0
                number = int(re.sub(r"[^\d]", "", number_str)) if number_str else 0

                if row:
                    seats.append(
                        SeatInfo(
                            row=row,
                            number=number,
                            category=category,
                            price=price,
                            is_available=is_available,
                            seat_id=seat_id,
                        )
                    )
            except Exception as e:
                logger.debug(f"Seat parse error: {e}")

        logger.info(f"Parsed {len(seats)} seats from map")
        return seats
