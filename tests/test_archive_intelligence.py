from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from curator.archive_intelligence import (
    calculate_artist_coverage,
    calculate_backlog,
    calculate_gaps,
    render_archive_health_report,
    render_artist_coverage_report,
    render_backlog_report,
    render_gap_analysis_report,
    write_archive_intelligence_reports,
)


def album(album_id: str, artist: str, title: str, **states: bool) -> dict:
    base_states = {
        "discovered": False,
        "attempted": False,
        "shipped": False,
        "validated": False,
        "confirmed": False,
    }
    base_states.update(states)
    order = [
        ("DISCOVERED", "discovered"),
        ("ATTEMPTED", "attempted"),
        ("SHIPPED", "shipped"),
        ("VALIDATED", "validated"),
        ("CONFIRMED", "confirmed"),
    ]
    highest = None
    for label, key in order:
        if base_states[key]:
            highest = label
    return {
        "album_id": album_id,
        "artist": artist,
        "title": title,
        "states": base_states,
        "highest_state": highest,
        "sources": [],
        "timestamps": {},
        "details": {},
    }


def synthetic_registry() -> dict:
    return {
        "schema": 1,
        "generated_at": "2026-06-15T16:00:00",
        "albums": [
            album(
                "1",
                "Artist A",
                "Validated Album",
                discovered=True,
                attempted=True,
                shipped=True,
                validated=True,
            ),
            album("2", "Artist A", "Backlog Album", discovered=True),
            album(
                "3",
                "Artist B",
                "Confirmed Gap",
                discovered=True,
                attempted=True,
                confirmed=True,
            ),
            album("4", "Artist C", "Shipment Gap", attempted=True, shipped=True),
            album("5", "Artist D", "Validation Orphan", validated=True),
        ],
    }


class ArchiveIntelligenceTests(unittest.TestCase):
    def test_artist_coverage_calculation(self) -> None:
        coverage = calculate_artist_coverage(synthetic_registry())
        by_artist = {row["artist"]: row for row in coverage}

        self.assertEqual(by_artist["Artist A"]["discovered"], 2)
        self.assertEqual(by_artist["Artist A"]["validated"], 1)
        self.assertEqual(by_artist["Artist A"]["confirmed"], 0)
        self.assertEqual(by_artist["Artist A"]["coverage_percent"], 50.0)
        self.assertEqual(by_artist["Artist B"]["coverage_percent"], 0.0)

    def test_backlog_calculation(self) -> None:
        backlog = calculate_backlog(synthetic_registry())

        self.assertEqual(backlog["total"], 1)
        self.assertEqual(backlog["by_artist"]["Artist A"], 1)
        self.assertEqual(backlog["by_artist"]["Artist B"], 0)
        self.assertEqual([row["album_id"] for row in backlog["albums"]], ["2"])

    def test_gap_calculation(self) -> None:
        gaps = calculate_gaps(synthetic_registry())

        self.assertEqual([row["album_id"] for row in gaps["shipped_not_validated"]], ["4"])
        self.assertEqual(
            [row["album_id"] for row in gaps["attempted_not_shipped"]],
            ["3"],
        )
        self.assertEqual(
            [row["album_id"] for row in gaps["confirmed_not_validated"]],
            ["3"],
        )
        self.assertEqual(
            [row["album_id"] for row in gaps["validated_not_discovered"]],
            ["5"],
        )

    def test_report_rendering(self) -> None:
        registry = synthetic_registry()

        self.assertIn("Total albums: `5`", render_archive_health_report(registry))
        self.assertIn("Artist A", render_artist_coverage_report(registry))
        self.assertIn("Backlog Album", render_backlog_report(registry))
        self.assertIn("Shipment Gap", render_gap_analysis_report(registry))
        self.assertIn("Validation Orphan", render_gap_analysis_report(registry))

    def test_reports_are_written(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            reports_dir = Path(tmp) / "reports"

            write_archive_intelligence_reports(synthetic_registry(), reports_dir)

            self.assertTrue((reports_dir / "archive_health_report.md").exists())
            self.assertTrue((reports_dir / "artist_coverage_report.md").exists())
            self.assertTrue((reports_dir / "backlog_report.md").exists())
            self.assertTrue((reports_dir / "gap_analysis_report.md").exists())


if __name__ == "__main__":
    unittest.main()
