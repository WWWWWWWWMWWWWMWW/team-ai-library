#!/usr/bin/env python3
"""Offline regression tests for dlt_analyzer.py."""

from __future__ import annotations

import tempfile
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
import dlt_analyzer as dlt  # noqa: E402


def official_payload() -> dict:
    return {
        "errorCode": "0",
        "value": {
            "list": [
                {
                    "lotteryDrawNum": "26096",
                    "lotteryDrawTime": "2026-08-24",
                    "lotteryDrawResult": "08 09 10 11 25 04 12",
                },
                {
                    "lotteryDrawNum": "26095",
                    "lotteryDrawTime": "2026-08-22",
                    "lotteryDrawResult": "01 07 13 20 35 02 09",
                },
            ]
        },
    }


class DltAnalyzerTests(unittest.TestCase):
    def test_official_payload_and_analysis(self) -> None:
        draws = dlt.parse_official_payload(official_payload(), source_url=dlt.OFFICIAL_API)
        result = dlt.analyze(draws, window=2)
        self.assertEqual(result["latest_issue"], "26096")
        self.assertEqual(result["front_frequency"]["08"], 1)
        self.assertEqual(result["random_baseline"]["single_ticket_combinations"], 21425712)

    def test_invalid_draw_is_rejected(self) -> None:
        with self.assertRaises(dlt.DataError):
            dlt.validate_draw("26096", "2026-08-24", [1, 1, 2, 3, 4], [1, 2], source="test", source_url="")

    def test_official_and_secondary_conflict_is_rejected(self) -> None:
        official = dlt.parse_official_payload(official_payload(), source_url=dlt.OFFICIAL_API)[0]
        secondary = dlt.Draw(
            issue=official.issue,
            date=official.date,
            front=(1, 2, 3, 4, 5),
            back=official.back,
            source="mirror",
            source_url="https://datachart.500.com/dlt/history/newinc/history.php",
            fetched_at=official.fetched_at,
        )
        with self.assertRaises(dlt.DataError):
            dlt.cross_validate(official, secondary)

    def test_official_prize_rules_are_seven_levels(self) -> None:
        self.assertEqual(dlt.prize_grade(5, 2), 1)
        self.assertEqual(dlt.prize_grade(4, 2), 3)
        self.assertEqual(dlt.prize_grade(0, 2), 7)
        self.assertIsNone(dlt.prize_grade(1, 1))

    def test_recommendation_is_reproducible_and_valid(self) -> None:
        draws = dlt.parse_official_payload(official_payload(), source_url=dlt.OFFICIAL_API)
        left = dlt.recommend(draws, count=4, window=2, seed=7)
        right = dlt.recommend(draws, count=4, window=2, seed=7)
        self.assertEqual(left, right)
        for ticket in left["tickets"]:
            dlt.validate_ticket(ticket["front"], ticket["back"])

    def test_explicit_json_cache_round_trip(self) -> None:
        draws = dlt.parse_official_payload(official_payload(), source_url=dlt.OFFICIAL_API)
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "draws.json"
            dlt.save_draws(path, draws)
            loaded = dlt.load_draws(path)
        self.assertEqual([item.issue for item in loaded], ["26096", "26095"])


if __name__ == "__main__":
    unittest.main()
