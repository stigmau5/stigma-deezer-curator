import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from audio_division.active_album import (
    ActiveAlbum,
    active_album_from_row,
    active_album_index,
    active_album_key,
    find_active_album,
    restore_active_album,
)
from audio_division.album_workspace import album_workspace


class ActiveAlbumTests(unittest.TestCase):
    def test_key_prefers_album_id_then_archive_path_then_deezer_id(self):
        self.assertEqual(active_album_key({"album_id": "1", "archive_path": "/a", "deezer_album_id": "9"}), "album_id:1")
        self.assertEqual(active_album_key({"archive_path": "/a", "deezer_album_id": "9"}), "archive_path:/a")
        self.assertEqual(active_album_key({"deezer_album_id": "9"}), "deezer_album_id:9")

    def test_finds_by_album_id_before_archive_path(self):
        active = ActiveAlbum(album_id="42", archive_path="/old")
        albums = [
            {"album_id": "1", "archive_path": "/old", "title": "Old"},
            {"album_id": "42", "archive_path": "/new", "title": "New"},
        ]

        self.assertEqual(find_active_album(albums, active)["title"], "New")
        self.assertEqual(active_album_index(albums, active), 1)

    def test_falls_back_to_archive_path_and_deezer_id(self):
        self.assertEqual(
            find_active_album([{"archive_path": "/archive/album", "title": "Path"}], ActiveAlbum(archive_path="/archive/album"))["title"],
            "Path",
        )
        self.assertEqual(
            find_active_album([{"album_id": "77", "title": "Deezer"}], ActiveAlbum(deezer_album_id="77"))["title"],
            "Deezer",
        )

    def test_active_album_from_row_normalizes_identity(self):
        active = active_album_from_row({"album_id": "12", "artist_key": "artist", "title": "Album"})

        self.assertTrue(active.present)
        self.assertEqual(active.deezer_album_id, "12")
        self.assertEqual(active.to_dict()["title"], "Album")

    def test_restore_keeps_previous_workspace_when_album_is_not_in_refreshed_model(self):
        previous = {"album_id": "12", "title": "Workspace"}

        restored = restore_active_album([], active_album_from_row(previous), previous)

        self.assertEqual(restored, previous)

    def test_operation_refreshes_restore_active_album_by_stable_identity(self):
        operations = ("validation", "process", "refresh", "audit", "metadata refresh", "archive reload")
        active = ActiveAlbum(album_id="12", archive_path="/old")
        refreshed = [{"album_id": "12", "archive_path": "/new", "title": "Restored"}]

        for operation in operations:
            with self.subTest(operation=operation):
                self.assertEqual(restore_active_album(refreshed, active)["title"], "Restored")

    def test_refresh_rebinds_presentation_album_to_physical_archive_row(self):
        with TemporaryDirectory() as tmp:
            album_path = Path(tmp) / "Artist - Album"
            album_path.mkdir()
            (album_path / "01.flac").write_bytes(b"audio")
            (album_path / "release.nfo").write_text("nfo", encoding="utf-8")
            (album_path / "release.sfv").write_text("01.flac 00000000", encoding="utf-8")
            (album_path / "album.m3u8").write_text("#EXTM3U\n01.flac\n", encoding="utf-8")
            (album_path / "cover.jpg").write_bytes(b"cover")
            (album_path / "STIGMA_VALIDATED.txt").write_text("validated", encoding="utf-8")

            selected = {
                "album_id": "42",
                "artist_key": "artist",
                "artist": "Artist",
                "title": "Album",
                "archive_path": str(album_path),
                "identity_confidence": "HIGH",
            }
            active = active_album_from_row(selected)
            presentation_only = {
                "album_id": "42",
                "artist_key": "artist",
                "artist": "Artist",
                "title": "Album",
                "identity_confidence": "HIGH",
            }

            restored = restore_active_album([selected], active, presentation_only)
            workspace = album_workspace(restored)
            integrity = {check["id"]: check for check in workspace["integrity"]["checks"]}

            self.assertEqual(restored["archive_path"], str(album_path))
            self.assertEqual(restored["album_id"], presentation_only["album_id"])
            self.assertEqual(workspace["cover"]["status"], "Present")
            self.assertEqual(workspace["files"]["source"], "filesystem")
            self.assertIn("01.flac", workspace["files"]["items"])
            self.assertEqual(workspace["nfo"]["status"], "Present")
            self.assertEqual(workspace["tracklist"]["source"], "playlist")
            self.assertEqual(integrity["artwork"]["status"], "Present")
            self.assertEqual(integrity["nfo"]["status"], "Present")
            self.assertEqual(integrity["playlist"]["status"], "Present")
            self.assertEqual(integrity["audio_files"]["status"], "Present")


if __name__ == "__main__":
    unittest.main()
