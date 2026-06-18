import tempfile
import unittest
from pathlib import Path

from audio_division.processing_queue import (
    load_processing_queue,
    processing_row,
    processing_rows,
    queue_for_processing,
    queue_state,
    save_processing_queue,
)


class ProcessingQueueTests(unittest.TestCase):
    def album(self, state="DOWNLOADED"):
        return {
            "album_id": "1",
            "artist": "Artist",
            "title": "Album",
            "archive_path": "/archive/Artist-Album",
            "album_truth": {"processing_state": state},
        }

    def test_state_transitions_from_truth_and_queue(self):
        self.assertEqual(queue_state("DISCOVERED"), "DISCOVERED")
        self.assertEqual(queue_state("DOWNLOADED"), "DOWNLOADED")
        self.assertEqual(queue_state("PROCESSING"), "NEEDS_PROCESSING")
        self.assertEqual(queue_state("PROCESSING", {"state": "PROCESSING"}), "PROCESSING")
        self.assertEqual(queue_state("ARCHIVED", {"state": "PROCESSING"}), "ARCHIVED")

    def test_queue_for_processing_records_album(self):
        queue = queue_for_processing({"albums": {}}, self.album(), source="deezer")
        entry = queue["albums"]["/archive/Artist-Album"]

        self.assertEqual(entry["artist"], "Artist")
        self.assertEqual(entry["album"], "Album")
        self.assertEqual(entry["source"], "deezer")
        self.assertEqual(entry["state"], "PROCESSING")
        self.assertIn("queued_at", entry)

    def test_queue_persistence_roundtrip(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "processing_queue.json"
            queue = queue_for_processing({"albums": {}}, self.album())
            save_processing_queue(path, queue)
            loaded = load_processing_queue(path)

        self.assertEqual(loaded["schema"], 1)
        self.assertEqual(loaded["albums"]["/archive/Artist-Album"]["state"], "PROCESSING")

    def test_status_display_rows(self):
        album = self.album("PROCESSING")
        row = processing_row(album, {"albums": {}})
        queued = queue_for_processing({"albums": {}}, album)
        queued_row = processing_row(album, queued)
        archived_row = processing_row(self.album("ARCHIVED"), queued)

        self.assertEqual(row["current_state"], "Needs Processing")
        self.assertEqual(queued_row["current_state"], "Processing")
        self.assertEqual(archived_row["current_state"], "Archived")

    def test_processing_rows_include_queue_only_entries(self):
        queue = {
            "albums": {
                "/archive/manual": {
                    "artist": "Manual",
                    "album": "Entry",
                    "archive_path": "/archive/manual",
                    "source": "manual",
                    "state": "PROCESSING",
                }
            }
        }
        rows = processing_rows([self.album("DOWNLOADED")], queue)

        self.assertEqual([row["current_state"] for row in rows], ["Downloaded", "Processing"])


if __name__ == "__main__":
    unittest.main()
