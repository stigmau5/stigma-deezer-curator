import unittest

from audio_division.metadata_status import (
    album_metadata_status,
    collection_statistics,
    metadata_coverage,
    render_collection_intelligence_report,
    render_metadata_status_report,
)


class MetadataStatusTests(unittest.TestCase):
    def sample_lifecycle(self):
        return {
            "albums": [
                {"album_id": "1"},
                {"album_id": "2"},
                {"album_id": "3"},
                {"album_id": ""},
            ]
        }

    def sample_metadata(self):
        return {
            "albums": {
                "1": {
                    "upc": "123",
                    "label": "Label A",
                    "genres": [{"name": "Rock"}],
                    "contributors": [{"name": "Artist"}],
                    "release_date": "2001-01-01",
                    "year": 2001,
                    "record_type": "album",
                    "artist": {"name": "Artist"},
                    "track_count": 10,
                    "duration": 3000,
                }
            },
            "artists": {"a": {"name": "Artist"}},
            "tracks": {"t": {"isrc": "ISRC"}},
            "errors": {"2": {"type": "album_fetch_failed"}},
        }

    def test_metadata_state_classification(self):
        metadata = self.sample_metadata()
        self.assertEqual(album_metadata_status("1", metadata)["state"], "CACHED")
        self.assertEqual(album_metadata_status("2", metadata)["state"], "MISSING")
        self.assertEqual(album_metadata_status("3", metadata)["state"], "AVAILABLE_NOT_CACHED")
        self.assertEqual(album_metadata_status("", metadata)["state"], "UNKNOWN")

    def test_missing_field_handling(self):
        metadata = {"albums": {"1": {"label": "Label A"}}, "errors": {}}
        status = album_metadata_status("1", metadata)
        self.assertEqual(status["state"], "CACHED")
        self.assertIn("upc", status["missing_fields"])
        self.assertTrue(status["cached_fields"]["label"])

    def test_coverage_calculations(self):
        coverage = metadata_coverage(self.sample_lifecycle(), self.sample_metadata())
        self.assertEqual(coverage["states"]["CACHED"], 1)
        self.assertEqual(coverage["states"]["MISSING"], 1)
        self.assertEqual(coverage["states"]["AVAILABLE_NOT_CACHED"], 1)
        self.assertEqual(coverage["states"]["UNKNOWN"], 1)
        self.assertEqual(coverage["coverage_percent"], 0.25)

    def test_collection_statistics(self):
        stats = collection_statistics(self.sample_metadata())
        self.assertEqual(stats["top_labels"][0], ("Label A", 1))
        self.assertEqual(stats["genres"][0], ("Rock", 1))
        self.assertEqual(stats["record_types"][0], ("album", 1))
        self.assertEqual(stats["tracks_with_isrc"], 1)

    def test_report_generation(self):
        status_report = render_metadata_status_report(self.sample_lifecycle(), self.sample_metadata())
        collection_report = render_collection_intelligence_report(self.sample_metadata())
        self.assertIn("Metadata Status Report", status_report)
        self.assertIn("AVAILABLE_NOT_CACHED", status_report)
        self.assertIn("Collection Intelligence Report", collection_report)


if __name__ == "__main__":
    unittest.main()
