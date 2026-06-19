import tempfile
import unittest
from pathlib import Path

from audio_division.closed_loop_monitor import (
    STATE_DOWNLOADED,
    STATE_NEEDS_PROCESSING,
    STATE_PROCESSING,
    archived_folder_keys,
    closed_loop_summary,
    discover_incoming_albums,
    incoming_sources,
    incoming_state,
    queue_album_payload,
)


class ClosedLoopMonitorTests(unittest.TestCase):
    def settings(self, root: Path):
        return {"archive_paths": {"incoming_root": str(root)}}

    def test_incoming_sources_are_source_agnostic_deezer_today(self):
        sources = incoming_sources({"archive_paths": {"incoming_root": "/downloads"}})

        self.assertEqual(sources, [{"source": "Deezer", "root": "/downloads"}])

    def test_incoming_discovery_skips_archived_albums(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "artist-one_album-2024-WEB-FLAC-STiGMA").mkdir()
            (root / "artist-two_album-2024-WEB-FLAC-STiGMA").mkdir()
            archive_albums = [{"archive_folder": "artist-two_album-2024-WEB-FLAC-STiGMA"}]

            rows = discover_incoming_albums(self.settings(root), archive_albums, {"albums": {}})

        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["source"], "Deezer")
        self.assertIn("artist-one", rows[0]["folder"])
        self.assertEqual(rows[0]["state"], STATE_DOWNLOADED)

    def test_state_detection_uses_queue_and_folder_evidence(self):
        with tempfile.TemporaryDirectory() as tmp:
            folder = Path(tmp) / "artist-album"
            folder.mkdir()
            self.assertEqual(incoming_state(folder, {"albums": {}}), STATE_DOWNLOADED)

            (folder / "01-track.flac").write_text("audio", encoding="utf-8")
            self.assertEqual(incoming_state(folder, {"albums": {}}), STATE_NEEDS_PROCESSING)

            queue = {"albums": {str(folder): {"state": "PROCESSING"}}}
            self.assertEqual(incoming_state(folder, queue), STATE_PROCESSING)

    def test_archived_folder_keys_normalize_names(self):
        keys = archived_folder_keys(
            [{"archive_folder": "Artist - Album (Deluxe)"}, {"archive_path": "/archive/A/Artist/Albums/Other Album"}]
        )

        self.assertIn("artistalbumdeluxe", keys)
        self.assertIn("otheralbum", keys)

    def test_summary_and_queue_payload(self):
        rows = [
            {"source": "Deezer", "state": STATE_DOWNLOADED, "artist": "A", "album": "One", "folder": "/in/one"},
            {"source": "Manual Import", "state": STATE_PROCESSING, "artist": "B", "album": "Two", "folder": "/in/two"},
        ]

        summary = closed_loop_summary(rows)
        payload = queue_album_payload(rows[0])

        self.assertEqual(summary["incoming_albums"], 2)
        self.assertEqual(summary["sources"], 2)
        self.assertEqual(summary["states"][STATE_PROCESSING], 1)
        self.assertEqual(payload["archive_path"], "/in/one")
        self.assertEqual(payload["title"], "One")


if __name__ == "__main__":
    unittest.main()
