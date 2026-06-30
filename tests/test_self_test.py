import json
import tempfile
import unittest
from pathlib import Path

from audio_division.environment_health import STATUS_FAIL, STATUS_PASS, STATUS_WARNING
from audio_division.self_test import SelfTestRunner, render_self_test_markdown


def healthy_album():
    items = {
        "artwork": "Present",
        "nfo": "Present",
        "playlist": "Present",
        "sfv": "Present",
        "validation": "Present",
        "metadata": "Present",
    }
    return {
        "album_id": "1",
        "artist": "Artist",
        "artist_key": "artist",
        "title": "Album",
        "archive_path": "/archive/A/Artist/Albums/Artist-album-2024-WEB-FLAC-STiGMA",
        "metadata_status": "CACHED",
        "identity_confidence": "HIGH",
        "album_truth": {"items": items, "readiness": "ARCHIVE_READY", "identity_confidence": "HIGH"},
        "album_status": {"items": items},
        "pipeline_state": {"state": "ARCHIVED", "evidence": ["test"], "reason": "test", "confidence": "HIGH", "conflicts": []},
    }


class SelfTestTests(unittest.TestCase):
    def settings(self, root: Path, reports: Path) -> dict:
        archive = root / "archive"
        incoming = root / "incoming"
        data = root / "data"
        for path in (archive, incoming, reports, data / "artists"):
            path.mkdir(parents=True, exist_ok=True)
        metadata = data / "metadata_cache.json"
        validated = data / "validated_albums.json"
        metadata.write_text("{}", encoding="utf-8")
        validated.write_text("{}", encoding="utf-8")
        (data / "artists" / "Example.txt").write_text("# source: https://www.deezer.com/artist/1\n", encoding="utf-8")
        tool = root / "tool"
        tool.write_text("#!/bin/sh\n", encoding="utf-8")
        return {
            "archive_paths": {"main_archive_root": str(archive), "incoming_root": str(incoming)},
            "reports": {"reports_directory": str(reports)},
            "metadata": {"metadata_cache_path": str(metadata)},
            "validator": {"validated_index_path": str(validated)},
            "tools": {
                "audio_division_path": str(tool),
                "flac_validator_path": str(tool),
                "file_manager_path": str(tool),
            },
        }

    def test_self_test_passes_when_all_health_reports_are_clean(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            reports = root / "reports"
            runner = SelfTestRunner(base_dir=root, data_dir=root / "data", reports_dir=reports, settings=self.settings(root, reports))

            result = runner.run(archive_albums=[healthy_album()], pipeline_releases=[healthy_album()])

        self.assertEqual(result.overall_status, STATUS_PASS)
        self.assertEqual(result.failing_checks, ())

    def test_self_test_collects_failing_checks_and_actions(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            runner = SelfTestRunner(base_dir=root, data_dir=root / "data", reports_dir=root / "reports", settings={"tools": {}})

            result = runner.run(archive_albums=[], pipeline_releases=[])

        self.assertEqual(result.overall_status, STATUS_FAIL)
        self.assertTrue(result.failing_checks)
        self.assertTrue(all(check["suggested_action"] for check in result.failing_checks))

    def test_write_reports_creates_markdown_and_json(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            reports = root / "reports"
            runner = SelfTestRunner(base_dir=root, data_dir=root / "data", reports_dir=reports, settings=self.settings(root, reports))
            result = runner.run(archive_albums=[healthy_album()], pipeline_releases=[healthy_album()])

            runner.write_reports(result)

            markdown = (reports / "self_test.md").read_text(encoding="utf-8")
            payload = json.loads((reports / "self_test.json").read_text(encoding="utf-8"))

        self.assertIn("# STiGMA Self Test", markdown)
        self.assertEqual(payload["overall_status"], STATUS_PASS)
        self.assertIn("archive", payload)
        self.assertIn("pipeline", payload)

    def test_warning_overall_status_for_pipeline_risks(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            reports = root / "reports"
            runner = SelfTestRunner(base_dir=root, data_dir=root / "data", reports_dir=reports, settings=self.settings(root, reports))
            stalled = {
                "artist": "Artist",
                "title": "Download",
                "album_id": "2",
                "pipeline_state": {"state": "DOWNLOADED", "evidence": ["test"], "reason": "test", "confidence": "HIGH", "conflicts": []},
                "identity_confidence": "HIGH",
            }

            result = runner.run(archive_albums=[healthy_album()], pipeline_releases=[healthy_album(), stalled])

        self.assertEqual(result.overall_status, STATUS_WARNING)
        self.assertIn("Stalled Downloads", render_self_test_markdown(result))


if __name__ == "__main__":
    unittest.main()
