import json
import tempfile
import unittest
from pathlib import Path

from audio_division.dashboard import compute_dashboard_summary, dashboard_summary, load_dashboard_sources
from audio_division.settings import load_audio_division_settings, save_audio_division_settings


class AudioDivisionDashboardTests(unittest.TestCase):
    def test_missing_files_return_zero_summary(self):
        with tempfile.TemporaryDirectory() as tmp:
            summary = dashboard_summary(Path(tmp))
        self.assertEqual(summary["archive_overview"]["albums"], 0)
        self.assertEqual(summary["metadata"]["coverage_percent"], 0.0)
        self.assertEqual(summary["validation"]["coverage_percent"], 0.0)

    def test_registry_loading(self):
        with tempfile.TemporaryDirectory() as tmp:
            data_dir = Path(tmp)
            (data_dir / "lifecycle_registry.json").write_text('{"summary": {"total_albums": 2}}')
            sources = load_dashboard_sources(data_dir)
        self.assertEqual(sources["lifecycle"]["summary"]["total_albums"], 2)
        self.assertEqual(sources["identity"], {})

    def test_dashboard_summary_calculations(self):
        lifecycle = {
            "summary": {
                "total_albums": 10,
                "state_evidence_counts": {
                    "DISCOVERED": 9,
                    "ATTEMPTED": 7,
                    "SHIPPED": 4,
                    "VALIDATED": 3,
                    "CONFIRMED": 2,
                },
                "gaps": {
                    "shipped_not_validated": 1,
                    "confirmed_not_validated": 1,
                },
            },
            "validation_evidence_summary": {"albums_with_evidence": 3},
            "albums": [{"album_id": str(idx)} for idx in range(1, 11)],
        }
        identity = {
            "summary": {
                "confidence_counts": {"HIGH": 3, "MEDIUM": 1, "UNKNOWN": 6},
                "unresolved_validator_logs": 2,
            }
        }
        metadata = {
            "summary": {
                "albums_with_metadata": 2,
                "artists_cached": 5,
                "tracks_cached": 20,
                "coverage_percent": 0.2,
            },
            "albums": {"1": {}, "2": {}},
            "errors": {"3": {"type": "album_fetch_failed"}},
        }

        summary = compute_dashboard_summary(lifecycle, identity, metadata)

        self.assertEqual(summary["archive_overview"]["albums"], 10)
        self.assertEqual(summary["archive_overview"]["artists"], 5)
        self.assertEqual(summary["lifecycle"]["validated"], 3)
        self.assertEqual(summary["identity"]["unresolved_logs"], 2)
        self.assertEqual(summary["metadata"]["tracks_cached"], 20)
        self.assertEqual(summary["validation"]["coverage_percent"], 0.3)
        self.assertEqual(summary["archive_health"]["attempted_not_shipped"], 3)
        self.assertEqual(summary["metadata"]["cached"], 2)
        self.assertEqual(summary["metadata"]["missing"], 1)
        self.assertEqual(summary["metadata"]["available_not_cached"], 7)

    def test_settings_save_and_load(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "audio_division_settings.json"
            settings = load_audio_division_settings(path)
            settings["archive_paths"]["main_archive_root"] = "/archive/music"
            settings["metadata"]["metadata_cache_path"] = "data/metadata_cache.json"
            save_audio_division_settings(path, settings)
            loaded = load_audio_division_settings(path)

            self.assertEqual(loaded["archive_paths"]["main_archive_root"], "/archive/music")
            self.assertEqual(loaded["metadata"]["metadata_cache_path"], "data/metadata_cache.json")
            self.assertTrue(path.exists())
            self.assertEqual(json.loads(path.read_text())["archive_paths"]["main_archive_root"], "/archive/music")


if __name__ == "__main__":
    unittest.main()
