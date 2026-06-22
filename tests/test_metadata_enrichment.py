import json
import tempfile
import unittest
from pathlib import Path

from audio_division.metadata_enrichment import (
    enrich_metadata,
    rebuild_metadata_enrichment,
    render_enrichment_report,
)


class MetadataEnrichmentTests(unittest.TestCase):
    def identity(self):
        return {
            "releases": [
                {
                    "archive_identity": {"folder": "Artist-Album-2004-FLAC"},
                    "discovery_identity": {
                        "deezer_album_id": "2",
                        "artist": "Artist",
                        "title": "Album",
                    },
                    "validation": {"track_count": 12},
                }
            ]
        }

    def lifecycle(self):
        return {
            "albums": [
                {"album_id": "1", "artist": "Cached", "title": "Existing"},
                {"album_id": "2", "artist": "Artist", "title": "Album"},
                {"album_id": "3", "artist": "No Identity", "title": "Missing"},
                {"album_id": "4", "artist": "Failed", "title": "Error"},
            ]
        }

    def cache(self):
        return {
            "albums": {"1": {"title": "Existing", "label": "Provider Label"}},
            "artists": {},
            "tracks": {},
            "errors": {"4": {"type": "album_fetch_failed"}},
        }

    def test_enriches_available_album_from_identity_without_replacing_cached_data(self):
        cache, result = enrich_metadata(
            self.identity(), self.lifecycle(), self.cache(), generated_at="2026-06-22T12:00:00"
        )

        album = cache["albums"]["2"]
        self.assertEqual(cache["albums"]["1"]["label"], "Provider Label")
        self.assertEqual(album["deezer_album_id"], "2")
        self.assertEqual(album["contributors"], [{"name": "Artist", "role": "Main"}])
        self.assertEqual(album["track_count"], 12)
        self.assertEqual(album["release_date"], "2004")
        self.assertEqual(album["record_type"], "album")
        self.assertEqual(album["genre"], "")
        self.assertEqual(album["genres"], [])
        self.assertEqual(album["label"], "")
        self.assertEqual(result["albums_evaluated"], 2)
        self.assertEqual(result["albums_enriched"], 1)
        self.assertEqual(result["albums_missing_metadata"], 1)
        self.assertEqual(result["coverage_percentage"], 50.0)

    def test_rebuild_removes_stale_enrichment_entries(self):
        cache = self.cache()
        cache["albums"]["9"] = {"title": "Stale", "metadata_source": "identity_registry"}

        rebuilt, _ = enrich_metadata(self.identity(), self.lifecycle(), cache)

        self.assertNotIn("9", rebuilt["albums"])
        self.assertIn("2", rebuilt["albums"])

    def test_writes_cache_and_report_without_touching_archive(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            data_dir = root / "data"
            reports_dir = root / "reports"
            archive_album = root / "archive" / "album" / "track.flac"
            archive_album.parent.mkdir(parents=True)
            archive_album.write_bytes(b"audio")
            data_dir.mkdir()
            (data_dir / "identity_registry.json").write_text(json.dumps(self.identity()))
            (data_dir / "lifecycle_registry.json").write_text(json.dumps(self.lifecycle()))
            (data_dir / "metadata_cache.json").write_text(json.dumps(self.cache()))

            result = rebuild_metadata_enrichment(data_dir, reports_dir)

            written = json.loads((data_dir / "metadata_cache.json").read_text())
            report = (reports_dir / "metadata_enrichment_report.md").read_text()
            self.assertIn("2", written["albums"])
            self.assertIn("Albums evaluated: `2`", report)
            self.assertEqual(result["albums_enriched"], 1)
            self.assertEqual(archive_album.read_bytes(), b"audio")

    def test_report_handles_no_candidates(self):
        report = render_enrichment_report(
            {
                "albums_evaluated": 0,
                "albums_enriched": 0,
                "albums_missing_metadata": 0,
                "coverage_percentage": 0,
            }
        )
        self.assertIn("Coverage percentage: `0.0%`", report)


if __name__ == "__main__":
    unittest.main()
