import tempfile
import unittest
from pathlib import Path

from audio_division.album_workspace import (
    album_workspace,
    filesystem_tracks,
    metadata_tracks,
    nfo_info,
    parse_playlist,
    tracklist_info,
)


class AlbumWorkspaceTests(unittest.TestCase):
    def details(self, path: str = ""):
        return {
            "album_id": "302127",
            "artist": "Daft Punk",
            "title": "Discovery",
            "archive_path": path,
            "track_count": 2,
            "album_status": {
                "items": {
                    "validation": "Present",
                    "nfo": "Present",
                    "sfv": "Present",
                    "playlist": "Present",
                    "artwork": "Present",
                },
                "health_percent": 100,
            },
            "archive_readiness": {"state": "ARCHIVE_READY"},
            "artwork": {"local": "", "urls": {}},
        }

    def test_nfo_contents_are_read(self):
        with tempfile.TemporaryDirectory() as tmp:
            album = Path(tmp)
            (album / "release.nfo").write_text("STIGMA AUDIO DIVISION\nArtist: Daft Punk")
            result = nfo_info(album)

        self.assertEqual(result["status"], "Present")
        self.assertIn("STIGMA AUDIO DIVISION", result["content"])

    def test_playlist_track_order_is_preferred(self):
        with tempfile.TemporaryDirectory() as tmp:
            album = Path(tmp)
            playlist = album / "album.m3u8"
            playlist.write_text("#EXTM3U\n02 - Second.flac\n01 - First.flac\n")
            (album / "01 - First.flac").write_text("audio")
            tracks = tracklist_info(album, self.details(str(album)), {})

        self.assertEqual(tracks["source"], "playlist")
        self.assertEqual(tracks["tracks"], ["01 - 02 - Second", "02 - 01 - First"])

    def test_filesystem_tracks_are_second_choice(self):
        with tempfile.TemporaryDirectory() as tmp:
            album = Path(tmp)
            (album / "02 - Second.flac").write_text("audio")
            (album / "01 - First.flac").write_text("audio")
            tracks = filesystem_tracks(album)

        self.assertEqual(tracks, ["01 - 01 - First", "02 - 02 - Second"])

    def test_metadata_tracks_are_fallback(self):
        metadata = {
            "albums": {"302127": {"track_ids": ["2", "1"]}},
            "tracks": {
                "1": {"title": "First", "track_number": 1, "disc_number": 1},
                "2": {"title": "Second", "track_number": 2, "disc_number": 1},
            },
        }

        self.assertEqual(metadata_tracks("302127", metadata), ["01 - First", "02 - Second"])

    def test_album_workspace_summary(self):
        with tempfile.TemporaryDirectory() as tmp:
            album = Path(tmp)
            (album / "cover.png").write_text("cover")
            (album / "release.nfo").write_text("nfo")
            (album / "01 - First.flac").write_text("audio")
            workspace = album_workspace(self.details(str(album)))

        self.assertEqual(workspace["cover"]["source"], "local")
        self.assertEqual(workspace["nfo"]["status"], "Present")
        self.assertEqual(workspace["tracklist"]["source"], "filesystem")
        self.assertIn(("Readiness", "ARCHIVE_READY"), workspace["status_glance"])

    def test_cover_info_prefers_named_album_artwork(self):
        with tempfile.TemporaryDirectory() as tmp:
            album = Path(tmp)
            (album / "z-random.jpg").write_text("art")
            (album / "folder.jpg").write_text("art")
            workspace = album_workspace(self.details(str(album)))

        self.assertEqual(workspace["cover"]["source"], "local")
        self.assertEqual(workspace["cover"]["display"], "folder.jpg")

    def test_parse_playlist_ignores_comments(self):
        with tempfile.TemporaryDirectory() as tmp:
            playlist = Path(tmp) / "album.m3u"
            playlist.write_text("#EXTM3U\n\n# comment\ntrack one.flac\n")

            self.assertEqual(parse_playlist(playlist), ["01 - track one"])


if __name__ == "__main__":
    unittest.main()
