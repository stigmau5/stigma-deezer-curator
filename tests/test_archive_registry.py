import tempfile
import unittest
from pathlib import Path

from audio_division.archive_registry import (
    album_entry,
    build_archive_registry,
    count_audio_tracks,
    discover_album_folders,
    render_archive_registry_report,
    render_artifact_coverage_report,
)


class ArchiveRegistryTests(unittest.TestCase):
    def test_archive_scanning_and_track_counts(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            album = root / "Artist-Album-2026-FLAC-STiGMA"
            album.mkdir()
            (album / "01.flac").write_text("audio")
            (album / "02.flac").write_text("audio")
            ignored = root / "Docs"
            ignored.mkdir()
            (ignored / "readme.txt").write_text("docs")

            folders = discover_album_folders(root)
            tracks = count_audio_tracks(album)

        self.assertEqual(folders, [album])
        self.assertEqual(tracks, 2)

    def test_artifact_detection_in_registry_entry(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            album = root / "Artist-Album-2026-FLAC-STiGMA"
            album.mkdir()
            (album / "01.flac").write_text("audio")
            (album / "album.nfo").write_text("nfo")
            (album / "album.sfv").write_text("sfv")
            (album / "playlist.m3u8").write_text("playlist")
            (album / "cover.jpg").write_text("cover")
            (album / "STIGMA_VALIDATED.txt").write_text("validated")

            entry = album_entry(album, root)

        self.assertEqual(entry["track_count"], 1)
        self.assertTrue(entry["artifacts"]["nfo"])
        self.assertTrue(entry["artifacts"]["validation_log"])
        self.assertEqual(entry["relative_path"], "Artist-Album-2026-FLAC-STiGMA")

    def test_registry_generation_and_reports(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            album = root / "Artist-Album-2026-FLAC-STiGMA"
            album.mkdir()
            (album / "01.flac").write_text("audio")

            registry = build_archive_registry(root)
            registry_report = render_archive_registry_report(registry)
            coverage_report = render_artifact_coverage_report(registry)

        self.assertEqual(registry["summary"]["album_folders"], 1)
        self.assertEqual(registry["summary"]["total_tracks"], 1)
        self.assertIn("Archive Registry Report", registry_report)
        self.assertIn("Archive Artifact Coverage Report", coverage_report)
        self.assertEqual(registry["summary"]["artifacts"]["missing_nfo"], 1)


if __name__ == "__main__":
    unittest.main()
