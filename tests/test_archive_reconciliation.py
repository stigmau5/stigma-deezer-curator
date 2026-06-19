import tempfile
import unittest
from pathlib import Path

from audio_division.archive_registry import album_entry
from audio_division.archive_reconciliation import (
    count_album_tracks,
    discover_album_roots,
    is_album_root,
    is_disc_folder,
    reconcile_archive,
    render_archive_reconciliation_report,
)


class ArchiveReconciliationTests(unittest.TestCase):
    def test_album_root_detection_for_direct_album(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            album = root / "A" / "artist" / "Albums" / "artist-album-2026-WEB-FLAC-STiGMA"
            album.mkdir(parents=True)
            (album / "01-track.flac").write_text("audio")

            self.assertTrue(is_album_root(album, root))
            self.assertEqual(discover_album_roots(root), [album])

    def test_disc_folder_exclusion_for_multi_disc_album(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            album = root / "A" / "artist" / "Albums" / "artist-box-2026-WEB-FLAC-STiGMA"
            cd1 = album / "CD1"
            cd2 = album / "Disc 2"
            cd1.mkdir(parents=True)
            cd2.mkdir()
            (album / "00-artist-box-2026-WEB-FLAC-STiGMA.nfo").write_text("nfo")
            (album / "00-artist-box-2026-WEB-FLAC-STiGMA.sfv").write_text("sfv")
            (album / "00-artist-box-2026-WEB-FLAC-STiGMA.m3u8").write_text("playlist")
            (cd1 / "01-track.flac").write_text("audio")
            (cd2 / "01-track.flac").write_text("audio")

            roots = discover_album_roots(root)
            track_count = count_album_tracks(album)

            self.assertTrue(is_disc_folder(cd1))
            self.assertTrue(is_disc_folder(cd2))
            self.assertEqual(roots, [album])
            self.assertEqual(track_count, 2)

    def test_reconciliation_detects_disc_rows_and_missing_album_root(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            album = root / "A" / "artist" / "Albums" / "artist-box-2026-WEB-FLAC-STiGMA"
            cd1 = album / "CD1"
            cd2 = album / "CD2"
            cd1.mkdir(parents=True)
            cd2.mkdir()
            (album / "00-artist-box-2026-WEB-FLAC-STiGMA.nfo").write_text("nfo")
            (album / "00-artist-box-2026-WEB-FLAC-STiGMA.sfv").write_text("sfv")
            (album / "00-artist-box-2026-WEB-FLAC-STiGMA.m3u8").write_text("playlist")
            (album / "cover.jpg").write_text("cover")
            (cd1 / "01-track.flac").write_text("audio")
            (cd2 / "01-track.flac").write_text("audio")
            registry = {"albums": [album_entry(cd1, root), album_entry(cd2, root)]}

            report = reconcile_archive(root, registry)

        self.assertEqual(report["summary"]["albums_missing"], 1)
        self.assertEqual(report["summary"]["albums_added"], 2)
        self.assertEqual(report["summary"]["disc_folder_album_rows"], 2)
        self.assertEqual(report["artifact_counts"]["with_nfo"], 1)
        self.assertEqual(report["artifact_counts"]["with_sfv"], 1)
        self.assertEqual(report["artifact_counts"]["with_playlist"], 1)
        self.assertEqual(report["artifact_counts"]["with_artwork"], 1)

    def test_reconciliation_detects_changed_artifacts(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            album = root / "A" / "artist" / "Albums" / "artist-album-2026-WEB-FLAC-STiGMA"
            album.mkdir(parents=True)
            (album / "01-track.flac").write_text("audio")
            (album / "release.nfo").write_text("nfo")
            row = album_entry(album, root)
            row["artifacts"]["nfo"] = False
            registry = {"albums": [row]}

            report = reconcile_archive(root, registry)

        self.assertEqual(report["summary"]["albums_found"], 1)
        self.assertEqual(report["summary"]["albums_changed"], 1)
        self.assertIn("nfo", report["albums_changed"][0]["differences"])

    def test_reconciliation_report_rendering(self):
        report = {
            "generated_at": "2026-06-19T12:00:00",
            "archive_root": "/archive",
            "summary": {
                "albums_found": 1,
                "albums_missing": 1,
                "albums_added": 2,
                "albums_changed": 0,
                "disc_folder_album_rows": 2,
            },
            "artifact_counts": {"with_nfo": 1, "missing_nfo": 0},
            "health": {"state": "WARNINGS", "healthy": False, "warnings": ["disc_folders_projected_as_albums"], "failures": []},
            "albums_missing": [{"name": "Album", "track_count": 2, "relative_path": "A/artist/Albums/Album"}],
            "albums_added": [],
            "albums_changed": [],
            "disc_folder_album_rows": [{"relative_path": "A/artist/Albums/Album/CD1", "album_root": "/archive/A/artist/Albums/Album", "album_root_in_registry": False}],
        }

        rendered = render_archive_reconciliation_report(report)

        self.assertIn("Archive Reconciliation Report", rendered)
        self.assertIn("Albums Incorrectly Represented By Disc Folders", rendered)
        self.assertIn("disc_folders_projected_as_albums", rendered)


if __name__ == "__main__":
    unittest.main()
