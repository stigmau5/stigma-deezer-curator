from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from curator.lifecycle import (
    build_lifecycle_registry,
    highest_state,
    render_discovery_gap_report,
    render_lifecycle_summary,
    render_shipment_gap_report,
    render_validation_gap_report,
    write_registry,
    write_reports,
)


class LifecycleRegistryTests(unittest.TestCase):
    def _write_synthetic_data(self, data_dir: Path) -> None:
        artists = data_dir / "artists"
        artists.mkdir(parents=True)
        (artists / "Daft_Punk.txt").write_text(
            "\n".join(
                [
                    "# Artist: Daft Punk",
                    "",
                    "# Albums",
                    "https://www.deezer.com/album/302127  # ALBUM | Discovery | 2001 | 14 tracks",
                    "https://www.deezer.com/album/999999  # ALBUM | Backlog | 2026 | 9 tracks",
                    "https://www.deezer.com/album/555555  # ALBUM | Confirmed Gap | 2026 | 5 tracks",
                ]
            )
            + "\n",
            encoding="utf-8",
        )

        (data_dir / "attempted_albums.json").write_text(
            json.dumps(
                {
                    "302127": {
                        "album_url": "https://www.deezer.com/album/302127",
                        "attempts": 2,
                        "last_attempt": "2026-06-15T10:00:00",
                    }
                }
            ),
            encoding="utf-8",
        )
        (data_dir / "shipped_jobs.json").write_text(
            json.dumps(
                {
                    "schema": 1,
                    "shipped": {
                        "302127": {
                            "album_id": "302127",
                            "url": "https://www.deezer.com/album/302127",
                            "jobname": "job-302127",
                            "remote_job": "/pending/job-302127.job",
                            "shipped_at_utc": "2026-06-15T11:00:00Z",
                        },
                        "777777": {
                            "album_id": "777777",
                            "url": "https://www.deezer.com/album/777777",
                            "jobname": "job-777777",
                            "remote_job": "/pending/job-777777.job",
                            "shipped_at_utc": "2026-06-14T11:00:00Z",
                        },
                    },
                }
            ),
            encoding="utf-8",
        )
        (data_dir / "validated_albums.json").write_text(
            json.dumps(
                {
                    "302127": {
                        "folder": "Daft Punk-Discovery-2001-FLAC-STiGMA",
                        "tracks": 14,
                        "validated_at": "2026-06-15T12:00:00",
                    },
                    "888888": {
                        "folder": "Archive Only-Album-2026-FLAC-STiGMA",
                        "tracks": 8,
                        "validated_at": "2026-06-13T12:00:00",
                    },
                }
            ),
            encoding="utf-8",
        )
        (data_dir / "confirmed_albums.json").write_text(
            json.dumps(
                {
                    "302127": {
                        "album_url": "https://www.deezer.com/album/302127",
                        "confirmed_at": "2026-06-15T13:00:00",
                        "artist_file": "Daft_Punk.txt",
                    },
                    "555555": {
                        "album_url": "https://www.deezer.com/album/555555",
                        "confirmed_at": "2026-06-15T14:00:00",
                        "artist_file": "Daft_Punk.txt",
                    },
                }
            ),
            encoding="utf-8",
        )

    def test_highest_state_calculation(self) -> None:
        self.assertEqual(
            highest_state(
                {
                    "discovered": True,
                    "attempted": True,
                    "shipped": False,
                    "validated": True,
                    "confirmed": False,
                }
            ),
            "VALIDATED",
        )
        self.assertEqual(
            highest_state(
                {
                    "discovered": True,
                    "attempted": False,
                    "shipped": False,
                    "validated": False,
                    "confirmed": True,
                }
            ),
            "CONFIRMED",
        )
        self.assertIsNone(highest_state({}))

    def test_registry_generation_projects_states(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            data_dir = Path(tmp)
            self._write_synthetic_data(data_dir)

            registry = build_lifecycle_registry(
                data_dir, generated_at="2026-06-15T15:00:00"
            )
            albums = {row["album_id"]: row for row in registry["albums"]}

            self.assertEqual(registry["summary"]["total_albums"], 5)
            self.assertEqual(albums["302127"]["artist"], "Daft Punk")
            self.assertEqual(albums["302127"]["title"], "Discovery")
            self.assertEqual(albums["302127"]["highest_state"], "CONFIRMED")
            self.assertTrue(albums["302127"]["states"]["validated"])
            self.assertEqual(albums["999999"]["highest_state"], "DISCOVERED")
            self.assertEqual(albums["777777"]["highest_state"], "SHIPPED")
            self.assertEqual(albums["888888"]["highest_state"], "VALIDATED")
            self.assertEqual(albums["555555"]["highest_state"], "CONFIRMED")

    def test_report_generation(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            data_dir = base / "data"
            data_dir.mkdir()
            self._write_synthetic_data(data_dir)
            registry = build_lifecycle_registry(
                data_dir, generated_at="2026-06-15T15:00:00"
            )

            summary = render_lifecycle_summary(registry)
            discovery = render_discovery_gap_report(registry)
            shipment = render_shipment_gap_report(registry)
            validation = render_validation_gap_report(registry)

            self.assertIn("Total albums: `5`", summary)
            self.assertIn("Daft Punk", discovery)
            self.assertIn("`999999`", discovery)
            self.assertIn("job-777777", shipment)
            self.assertIn("Confirmed But Not Validated", validation)
            self.assertIn("`555555`", validation)
            self.assertIn("`888888`", validation)

    def test_registry_and_reports_are_written(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            data_dir = base / "data"
            reports_dir = base / "reports"
            data_dir.mkdir()
            self._write_synthetic_data(data_dir)
            registry = build_lifecycle_registry(
                data_dir, generated_at="2026-06-15T15:00:00"
            )

            write_registry(registry, data_dir / "lifecycle_registry.json")
            write_reports(registry, reports_dir)

            written = json.loads((data_dir / "lifecycle_registry.json").read_text())
            self.assertEqual(written["summary"]["total_albums"], 5)
            self.assertTrue((reports_dir / "lifecycle_summary.md").exists())
            self.assertTrue((reports_dir / "discovery_gap_report.md").exists())
            self.assertTrue((reports_dir / "shipment_gap_report.md").exists())
            self.assertTrue((reports_dir / "validation_gap_report.md").exists())


if __name__ == "__main__":
    unittest.main()
