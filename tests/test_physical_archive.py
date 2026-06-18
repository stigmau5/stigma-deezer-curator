import tempfile
import unittest
from pathlib import Path

from audio_division.album_workspace import album_workspace
from audio_division.physical_archive import (
    albums_for_archive_artist,
    archive_readiness,
    archive_tree,
    build_archive_albums,
    filter_archive_albums,
    project_archive_album,
)


class PhysicalArchiveTests(unittest.TestCase):
    def registry_row(
        self,
        path: str = "/archive/A/abba/Albums/abba-arrival-1976-WEB-FLAC-STiGMA",
        relative_path: str = "A/abba/Albums/abba-arrival-1976-WEB-FLAC-STiGMA",
    ):
        return {
            "name": "abba-arrival-1976-WEB-FLAC-STiGMA",
            "archive_path": path,
            "relative_path": relative_path,
            "track_count": 10,
            "artifacts": {
                "exists": True,
                "nfo": True,
                "sfv": True,
                "playlist": True,
                "artwork": True,
                "validation_log": True,
                "counts": {"nfo": 1, "sfv": 1, "playlist": 1, "artwork": 1, "validation_log": 1},
            },
        }

    def test_archive_album_projection(self):
        album = project_archive_album(self.registry_row())

        self.assertEqual(album["artist"], "abba")
        self.assertEqual(album["title"], "arrival-1976-WEB-FLAC-STiGMA")
        self.assertEqual(album["year"], "1976")
        self.assertEqual(album["archive_path_confidence"], "HIGH")
        self.assertEqual(album["album_status"]["items"]["nfo"], "Present")
        self.assertEqual(album["archive_readiness"]["state"], "ARCHIVE_READY")

    def test_archive_tree_generation_and_selection(self):
        registry = {
            "albums": [
                self.registry_row(),
                self.registry_row(
                    "/archive/B/beastie_boys/Albums/beastie_boys-check_your_head-1992-WEB-FLAC-STiGMA",
                    "B/beastie_boys/Albums/beastie_boys-check_your_head-1992-WEB-FLAC-STiGMA",
                ),
            ]
        }
        albums = build_archive_albums(registry)
        tree = archive_tree(albums)

        self.assertEqual([row["artist"] for row in tree], ["abba", "beastie_boys"])
        self.assertEqual(len(albums_for_archive_artist(albums, "abba")), 1)

    def test_filtering(self):
        albums = build_archive_albums({"albums": [self.registry_row()]})

        self.assertEqual(len(filter_archive_albums(albums, artist="abb")), 1)
        self.assertEqual(len(filter_archive_albums(albums, album="arrival")), 1)
        self.assertEqual(len(filter_archive_albums(albums, artist="clash")), 0)

    def test_readiness_display(self):
        status = {
            "items": {
                "validation": "Present",
                "nfo": "Missing",
                "sfv": "Present",
                "playlist": "Present",
                "artwork": "Present",
            }
        }

        self.assertEqual(archive_readiness(status)["state"], "NEEDS_DOCUMENTATION")

    def test_workspace_integration_uses_physical_files(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp)
            (path / "cover.jpg").write_text("cover")
            (path / "release.nfo").write_text("nfo body")
            (path / "album.m3u8").write_text("01 - Song.flac\n")
            row = self.registry_row(str(path))
            row["relative_path"] = "A/abba/Albums/abba-arrival-1976-WEB-FLAC-STiGMA"
            album = project_archive_album(row)
            workspace = album_workspace(album)

        self.assertEqual(workspace["cover"]["source"], "local")
        self.assertEqual(workspace["nfo"]["status"], "Present")
        self.assertEqual(workspace["tracklist"]["source"], "playlist")


if __name__ == "__main__":
    unittest.main()
