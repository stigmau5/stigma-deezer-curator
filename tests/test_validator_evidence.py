from __future__ import annotations

import json
import tempfile
import unittest
from datetime import datetime
from pathlib import Path

from curator.lifecycle import build_lifecycle_registry
from curator.validator_evidence import (
    attach_validation_evidence,
    collect_validation_evidence,
    parse_validation_log,
    render_validation_age_report,
    render_validation_confidence_report,
    render_validation_coverage_report,
    render_validation_evidence_report,
    validation_age_buckets,
    write_validation_reports,
)


class ValidatorEvidenceTests(unittest.TestCase):
    def _write_data(self, base: Path) -> tuple[Path, Path]:
        data_dir = base / "data"
        artists = data_dir / "artists"
        evidence_root = base / "archive"
        album_dir = evidence_root / "Daft Punk-Discovery-2001-FLAC-STiGMA"
        artists.mkdir(parents=True)
        album_dir.mkdir(parents=True)

        (artists / "Daft_Punk.txt").write_text(
            "# Artist: Daft Punk\n"
            "https://www.deezer.com/album/302127  # ALBUM | Discovery | 2001 | 14 tracks\n",
            encoding="utf-8",
        )
        (data_dir / "attempted_albums.json").write_text("{}", encoding="utf-8")
        (data_dir / "shipped_jobs.json").write_text(
            json.dumps({"schema": 1, "shipped": {}}),
            encoding="utf-8",
        )
        (data_dir / "confirmed_albums.json").write_text("{}", encoding="utf-8")
        (data_dir / "validated_albums.json").write_text(
            json.dumps(
                {
                    "302127": {
                        "folder": "Daft Punk-Discovery-2001-FLAC-STiGMA",
                        "source": "stigma-flac-validator",
                        "tracks": 14,
                        "validated_at": "2026-06-15T12:00:00",
                    }
                }
            ),
            encoding="utf-8",
        )
        (album_dir / "STIGMA_VALIDATED.txt").write_text(
            json.dumps(
                {
                    "album": "Daft Punk-Discovery-2001-FLAC-STiGMA",
                    "validated_at": "2026-06-15T12:00:00",
                    "tracks": 14,
                    "warnings": [],
                    "completeness": {
                        "mode": "album-wide",
                        "album": "Discovery",
                        "album_artist": "Daft Punk",
                        "expected_tracks": 14,
                        "found_tracks": 14,
                        "missing_tracks": [],
                        "notes": [],
                        "missing_album_id_tracks": 0,
                        "album_id": "302127",
                        "hashes": {"01.flac": "abc"},
                    },
                }
            ),
            encoding="utf-8",
        )
        return data_dir, evidence_root

    def test_parse_validation_log(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            data_dir, evidence_root = self._write_data(Path(tmp))
            log_path = evidence_root / "Daft Punk-Discovery-2001-FLAC-STiGMA" / "STIGMA_VALIDATED.txt"

            parsed = parse_validation_log(log_path)

            self.assertEqual(parsed["album_id"], "302127")
            self.assertEqual(parsed["track_count"], 14)
            self.assertEqual(parsed["integrity_status"], "passed")
            self.assertEqual(parsed["hashes_count"], 1)
            self.assertEqual(parsed["completeness"]["found_tracks"], 14)

    def test_collect_and_attach_validation_evidence(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            data_dir, evidence_root = self._write_data(Path(tmp))
            evidence = collect_validation_evidence(data_dir, [evidence_root])
            registry = build_lifecycle_registry(data_dir)

            attach_validation_evidence(registry, evidence)
            row = registry["albums"][0]

            self.assertTrue(row["validation_evidence"]["available"])
            self.assertEqual(row["validation_evidence"]["confidence"], "detailed_log")
            self.assertEqual(row["validation_evidence"]["track_count"], 14)
            self.assertEqual(registry["validation_evidence_summary"]["validation_logs_found"], 1)

    def test_validation_age_buckets(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            data_dir, evidence_root = self._write_data(Path(tmp))
            evidence = collect_validation_evidence(data_dir, [evidence_root])
            registry = build_lifecycle_registry(data_dir, validation_evidence=evidence)

            buckets = validation_age_buckets(
                registry,
                now=datetime.fromisoformat("2026-07-01T00:00:00"),
            )

            self.assertEqual(buckets["last_30_days"], 1)

    def test_report_rendering_and_writing(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            data_dir, evidence_root = self._write_data(base)
            evidence = collect_validation_evidence(data_dir, [evidence_root])
            registry = build_lifecycle_registry(data_dir, validation_evidence=evidence)

            self.assertIn("Albums with validation evidence: `1`", render_validation_evidence_report(registry))
            self.assertIn("Detailed validation logs matched", render_validation_coverage_report(registry))
            self.assertIn("Last 30 days", render_validation_age_report(registry))
            self.assertIn("detailed_log", render_validation_confidence_report(registry))

            reports_dir = base / "reports"
            write_validation_reports(registry, reports_dir)

            self.assertTrue((reports_dir / "validation_evidence_report.md").exists())
            self.assertTrue((reports_dir / "validation_coverage_report.md").exists())
            self.assertTrue((reports_dir / "validation_age_report.md").exists())
            self.assertTrue((reports_dir / "validation_confidence_report.md").exists())


if __name__ == "__main__":
    unittest.main()
