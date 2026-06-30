import tempfile
import unittest
from pathlib import Path

from audio_division.album_workspace import (
    album_workspace,
    filesystem_listing,
    filesystem_tracks,
    metadata_tracks,
    nfo_info,
    parse_playlist,
    release_timeline,
    render_timeline,
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

    def test_filesystem_listing_preserves_multidisc_hierarchy(self):
        with tempfile.TemporaryDirectory() as tmp:
            album = Path(tmp)
            (album / "00-release.nfo").write_text("nfo")
            cd1 = album / "CD1"
            cd2 = album / "CD2"
            cd1.mkdir()
            cd2.mkdir()
            (cd1 / "01_song.flac").write_text("audio")
            (cd2 / "01_other.flac").write_text("audio")

            listing = filesystem_listing(album)

        self.assertEqual(listing["source"], "filesystem")
        self.assertIn("00-release.nfo", listing["items"])
        self.assertIn("CD1", listing["items"])
        self.assertIn("  01_song.flac", listing["items"])
        self.assertIn("CD2", listing["items"])
        self.assertIn("  01_other.flac", listing["items"])

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
        self.assertEqual(workspace["files"]["source"], "filesystem")
        self.assertIn("integrity", workspace)
        self.assertIn("relationships", workspace)
        self.assertIn(("Readiness", "ARCHIVE_READY"), workspace["status_glance"])
        self.assertIn("timeline", workspace)

    def test_album_workspace_includes_related_albums(self):
        details = self.details()
        details["label"] = "Virgin"
        details["genres"] = ["Electronic"]
        related = {
            "album_id": "999",
            "artist": "Daft Punk",
            "title": "Homework",
            "year": "1997",
            "label": "Virgin",
            "genres": ["Electronic"],
        }

        workspace = album_workspace(details, collection_albums=[details, related])

        self.assertEqual(workspace["relationships"]["groups"]["same_artist"][0]["title"], "Homework")
        self.assertIn("Same Artist: 1", workspace["relationships_text"])

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

    def test_release_timeline_derives_events_and_confidence(self):
        with tempfile.TemporaryDirectory() as tmp:
            album = Path(tmp)
            for name in ("release.nfo", "release.sfv", "album.m3u8", "cover.jpg", "STIGMA_VALIDATED.txt", "01.flac"):
                (album / name).write_text("evidence", encoding="utf-8")
            details = self.details(str(album))
            details.update(
                {
                    "metadata_status": "CACHED",
                    "identity_confidence": "HIGH",
                    "archive_path_confidence": "HIGH",
                    "pipeline_state": {
                        "state": "ARCHIVED",
                        "evidence": ["curator_state", "archive_filesystem"],
                        "confidence": "HIGH",
                    },
                    "album_status": {
                        "items": {
                            "validation": "Present",
                            "nfo": "Present",
                            "sfv": "Present",
                            "playlist": "Present",
                            "artwork": "Present",
                        },
                        "health_percent": 100,
                        "validation_source": "validated_index",
                        "validation_confidence": "HIGH",
                        "validation_reason": "Album ID is present in validated_albums.json.",
                    },
                }
            )

            workspace = album_workspace(details, {"albums": {"302127": {"cached_at": "2026-06-30T10:00:00"}}})

        events = {event["event"]: event for event in workspace["timeline"]}
        self.assertEqual(events["Curated"]["confidence"], "HIGH")
        self.assertEqual(events["Validated"]["confidence"], "HIGH")
        self.assertEqual(events["Metadata Cached"]["timestamp"], "2026-06-30T10:00:00")
        self.assertIn("Processed", events)
        self.assertIn("Archived", events)
        self.assertIn("Audit Passed", events)
        self.assertIn("Metadata Cached", workspace["timeline_text"])

    def test_release_timeline_is_empty_without_evidence(self):
        events = release_timeline({}, {})

        self.assertEqual(events, [])
        self.assertEqual(render_timeline(events), "No timeline evidence found.")


if __name__ == "__main__":
    unittest.main()
