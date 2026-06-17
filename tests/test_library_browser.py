import json
import tempfile
import unittest
from pathlib import Path

from audio_division.library import (
    album_status,
    album_details,
    albums_for_artist,
    build_library,
    library_from_data_dir,
)


class LibraryBrowserTests(unittest.TestCase):
    def sample_lifecycle(self):
        return {
            "generated_at": "2026-06-17T12:00:00",
            "albums": [
                {
                    "album_id": "1",
                    "artist": "Beta Artist",
                    "title": "Fallback Album",
                    "highest_state": "DISCOVERED",
                    "states": {"validated": False},
                    "details": {},
                },
                {
                    "album_id": "2",
                    "artist": "Alpha Artist",
                    "title": "Cached Album",
                    "highest_state": "VALIDATED",
                    "states": {"validated": True},
                    "details": {"validated_tracks": 10},
                },
            ],
        }

    def sample_identity(self):
        return {
            "releases": [
                {
                    "discovery_identity": {"deezer_album_id": "2"},
                    "archive_identity": {"folder": "Alpha Artist - Cached Album"},
                    "identity_confidence": "HIGH",
                }
            ]
        }

    def sample_metadata(self):
        return {
            "summary": {"coverage_percent": 0.5},
            "artists": {"27": {"name": "Alpha Artist", "album_count": 4}},
            "tracks": {"100": {"title": "Track"}},
            "albums": {
                "2": {
                    "title": "Cached Album",
                    "year": 2001,
                    "release_date": "2001-03-07",
                    "record_type": "album",
                    "label": "Label",
                    "genres": [{"name": "Dance"}],
                    "track_count": 1,
                    "duration": 226,
                    "artist": {"name": "Alpha Artist"},
                    "cover_identity": "cover",
                    "covers": {"medium": "https://example.test/cover.jpg"},
                }
            },
        }

    def test_artist_indexing_and_sorting(self):
        library = build_library(self.sample_lifecycle(), self.sample_identity(), self.sample_metadata())
        names = [artist["name"] for artist in library["artists"]]
        self.assertEqual(names, ["Alpha Artist", "Beta Artist"])
        self.assertEqual(library["artists"][0]["album_count"], 1)

    def test_album_indexing_for_artist(self):
        library = build_library(self.sample_lifecycle(), self.sample_identity(), self.sample_metadata())
        albums = albums_for_artist(library, "alpha artist")
        self.assertEqual(len(albums), 1)
        self.assertEqual(albums[0]["title"], "Cached Album")

    def test_album_detail_generation(self):
        library = build_library(self.sample_lifecycle(), self.sample_identity(), self.sample_metadata())
        details = album_details(library, "2")
        self.assertEqual(details["release_date"], "2001-03-07")
        self.assertEqual(details["identity_confidence"], "HIGH")
        self.assertEqual(details["validation_status"], "validated")
        self.assertEqual(details["metadata_status"], "cached")
        self.assertEqual(details["genres"], ["Dance"])
        self.assertEqual(details["album_status"]["items"]["metadata"], "Present")

    def test_missing_metadata_fallback(self):
        library = build_library(self.sample_lifecycle(), self.sample_identity(), {"albums": {}, "artists": {}, "tracks": {}})
        details = album_details(library, "1")
        self.assertEqual(details["artist"], "Beta Artist")
        self.assertEqual(details["title"], "Fallback Album")
        self.assertEqual(details["metadata_status"], "missing")

    def test_album_status_calculation(self):
        details = {
            "validation_status": "validated",
            "metadata_status": "cached",
            "artifacts": {
                "exists": True,
                "nfo": True,
                "sfv": False,
                "playlist": True,
                "artwork": True,
            },
            "artwork": {"cover_identity": "cover", "urls": {}},
        }
        status = album_status(details)
        self.assertEqual(status["items"]["validation"], "Present")
        self.assertEqual(status["items"]["sfv"], "Missing")
        self.assertEqual(status["health_percent"], 83)

    def test_artifact_detection_in_library(self):
        with tempfile.TemporaryDirectory() as tmp:
            archive_root = Path(tmp)
            album_dir = archive_root / "Alpha Artist - Cached Album"
            album_dir.mkdir()
            (album_dir / "album.nfo").write_text("nfo")
            (album_dir / "album.sfv").write_text("sfv")
            (album_dir / "playlist.m3u8").write_text("playlist")
            (album_dir / "cover.jpg").write_text("artwork")
            (album_dir / "STIGMA_VALIDATED.txt").write_text("validated")

            library = build_library(
                self.sample_lifecycle(),
                self.sample_identity(),
                self.sample_metadata(),
                archive_root,
            )
            details = album_details(library, "2")

        self.assertTrue(details["artifacts"]["nfo"])
        self.assertEqual(details["artifacts"]["counts"]["playlist"], 1)
        self.assertEqual(details["album_status"]["health_percent"], 100)

    def test_registry_loading(self):
        with tempfile.TemporaryDirectory() as tmp:
            data_dir = Path(tmp)
            (data_dir / "lifecycle_registry.json").write_text(json.dumps(self.sample_lifecycle()))
            (data_dir / "identity_registry.json").write_text(json.dumps(self.sample_identity()))
            (data_dir / "metadata_cache.json").write_text(json.dumps(self.sample_metadata()))
            library = library_from_data_dir(data_dir)
        self.assertEqual(library["summary"]["artists"], 2)
        self.assertEqual(library["summary"]["albums"], 2)
        self.assertEqual(library["summary"]["tracks"], 1)


if __name__ == "__main__":
    unittest.main()
