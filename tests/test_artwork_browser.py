import tempfile
import unittest
from pathlib import Path

from audio_division.artwork_browser import (
    artwork_items,
    artwork_summary,
    filter_artwork_items,
    first_artwork_path,
    grid_rows,
    render_artwork_coverage_report,
    split_archive_folder,
)
from audio_division.library import build_library


class ArtworkBrowserTests(unittest.TestCase):
    def sample_lifecycle(self):
        return {
            "albums": [
                {
                    "album_id": "1",
                    "artist": "Alpha Artist",
                    "title": "Local Cover",
                    "highest_state": "VALIDATED",
                    "states": {"validated": True},
                    "details": {},
                },
                {
                    "album_id": "2",
                    "artist": "Beta Artist",
                    "title": "Missing Cover",
                    "highest_state": "DISCOVERED",
                    "states": {"validated": False},
                    "details": {},
                },
                {
                    "album_id": "3",
                    "artist": "Alpha Artist",
                    "title": "Metadata Cover",
                    "highest_state": "DISCOVERED",
                    "states": {"validated": False},
                    "details": {},
                },
            ]
        }

    def sample_identity(self):
        return {
            "releases": [
                {
                    "discovery_identity": {"deezer_album_id": "1"},
                    "archive_identity": {"folder": "Alpha Artist - Local Cover"},
                    "identity_confidence": "HIGH",
                }
            ]
        }

    def sample_metadata(self):
        return {
            "summary": {"coverage_percent": 0.33},
            "artists": {},
            "tracks": {},
            "albums": {
                "3": {
                    "title": "Metadata Cover",
                    "year": 2002,
                    "artist": {"name": "Alpha Artist"},
                    "covers": {"medium": "https://example.test/cover.jpg"},
                }
            },
        }

    def test_artwork_discovery_and_missing_artwork(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            album = root / "Alpha Artist - Local Cover"
            album.mkdir()
            (album / "track.flac").write_text("audio")
            (album / "cover.jpg").write_text("cover")
            library = build_library(self.sample_lifecycle(), self.sample_identity(), self.sample_metadata(), root)
            items = artwork_items(library)

        by_id = {item["album_id"]: item for item in items}
        self.assertEqual(by_id["1"]["artwork_source"], "local")
        self.assertEqual(by_id["2"]["artwork_source"], "none")
        self.assertEqual(by_id["3"]["artwork_source"], "metadata_url")

    def test_archive_registry_artwork_discovery(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            album = root / "Gamma Artist - Registry Cover"
            album.mkdir()
            cover = album / "folder.jpg"
            cover.write_text("cover")
            registry = {"albums": [{"name": album.name, "archive_path": str(album)}]}
            items = artwork_items({"albums": []}, registry)

        self.assertEqual(items[0]["artist"], "Gamma Artist")
        self.assertEqual(items[0]["album"], "Registry Cover")
        self.assertEqual(items[0]["artwork_source"], "local")
        self.assertEqual(items[0]["thumbnail_display"], "folder.jpg")

    def test_filtering_and_grid_population(self):
        items = [
            {"artist": "Alpha Artist", "album": "One"},
            {"artist": "Alpha Artist", "album": "Two"},
            {"artist": "Beta Artist", "album": "Three"},
        ]

        self.assertEqual(len(filter_artwork_items(items, artist="alpha")), 2)
        self.assertEqual(len(filter_artwork_items(items, album="three")), 1)
        self.assertEqual([len(row) for row in grid_rows(items, columns=2)], [2, 1])

    def test_summary_and_report_generation(self):
        items = [
            {"artwork_source": "local"},
            {"artwork_source": "metadata_url"},
            {"artwork_source": "none"},
        ]
        summary = artwork_summary(items)
        self.assertEqual(summary["local_artwork"], 1)
        self.assertEqual(summary["missing_artwork"], 1)
        self.assertEqual(summary["coverage_percent"], 0.6667)

        library = build_library(self.sample_lifecycle(), self.sample_identity(), self.sample_metadata())
        report = render_artwork_coverage_report(library)
        self.assertIn("Artwork Coverage Report", report)
        self.assertIn("Metadata Cover", report)

    def test_thumbnail_helpers(self):
        with tempfile.TemporaryDirectory() as tmp:
            album = Path(tmp)
            (album / "cover.webp").write_text("cover")
            self.assertEqual(first_artwork_path(album).name, "cover.webp")
        self.assertEqual(split_archive_folder("Artist - Album"), ("Artist", "Album"))


if __name__ == "__main__":
    unittest.main()
