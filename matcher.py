"""
matcher.py — Seat preference matching engine.
Scores available seats against config preferences, finds consecutive blocks.
"""

import logging
from dataclasses import dataclass
from scraper import SeatInfo, ShowResult

logger = logging.getLogger(__name__)


@dataclass
class SeatMatch:
    show: ShowResult
    seats: list[SeatInfo]          # The consecutive block found
    row: str
    priority: int                  # 0 = top preference, higher = lower preference
    category: str
    total_price: int
    booking_url: str
    is_top_row: bool               # True if in preferred_rows[0]


class SeatMatcher:
    def __init__(self, config: dict):
        self.config = config
        seat_cfg = config["seats"]
        self.preferred_rows: list[list[str]] = [
            [r.upper() for r in group]
            for group in seat_cfg["preferred_rows"]
        ]
        self.categories = [c.upper() for c in seat_cfg["categories"]]
        self.min_consec: int = seat_cfg["min_consecutive"]
        self.max_consec: int = seat_cfg["max_consecutive"]

    def find_matches(self, shows: list[ShowResult]) -> list[SeatMatch]:
        """Return all seat matches across shows, sorted by priority."""
        matches: list[SeatMatch] = []

        for show in shows:
            available = [s for s in show.seats if s.is_available]
            if not available:
                continue

            for priority, row_group in enumerate(self.preferred_rows):
                for row in row_group:
                    row_seats = sorted(
                        [s for s in available if s.row == row],
                        key=lambda s: s.number,
                    )
                    blocks = self._find_consecutive_blocks(row_seats)
                    for block in blocks:
                        category = block[0].category
                        if not self._category_ok(category):
                            continue
                        matches.append(
                            SeatMatch(
                                show=show,
                                seats=block,
                                row=row,
                                priority=priority,
                                category=category,
                                total_price=sum(s.price for s in block),
                                booking_url=self._build_deep_link(show, block),
                                is_top_row=(priority == 0),
                            )
                        )

        matches.sort(key=lambda m: (m.priority, m.show.show_date, m.show.show_time))
        return matches

    def _find_consecutive_blocks(self, row_seats: list[SeatInfo]) -> list[list[SeatInfo]]:
        """Find all consecutive seat blocks of acceptable size."""
        blocks: list[list[SeatInfo]] = []
        if not row_seats:
            return blocks

        current = [row_seats[0]]
        for seat in row_seats[1:]:
            if seat.number == current[-1].number + 1:
                current.append(seat)
            else:
                self._extract_blocks(current, blocks)
                current = [seat]
        self._extract_blocks(current, blocks)
        return blocks

    def _extract_blocks(self, run: list[SeatInfo], out: list[list[SeatInfo]]):
        for size in range(self.max_consec, self.min_consec - 1, -1):
            for start in range(len(run) - size + 1):
                out.append(run[start : start + size])

    def _category_ok(self, category: str) -> bool:
        if not self.categories:
            return True
        return any(c in category.upper() for c in self.categories)

    def _build_deep_link(self, show: ShowResult, seats: list[SeatInfo]) -> str:
        """
        Build a direct BookMyShow URL that pre-selects seats.
        BMS supports seat IDs in the URL fragment for some flows.
        Falls back to the show's booking URL.
        """
        seat_ids = ",".join(s.seat_id for s in seats if s.seat_id)
        base = show.booking_url
        if seat_ids:
            return f"{base}#seats={seat_ids}"
        return base
