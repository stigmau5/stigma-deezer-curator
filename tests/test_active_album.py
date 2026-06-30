import unittest

from audio_division.active_album import (
    ActiveAlbum,
    active_album_from_row,
    active_album_index,
    active_album_key,
    find_active_album,
    restore_active_album,
)


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


if __name__ == "__main__":
    unittest.main()
