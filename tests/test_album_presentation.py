import tempfile
import unittest
from pathlib import Path

from audio_division.album_presentation import album_presentation, thumbnail_info


class AlbumPresentationTests(unittest.TestCase):
    def sample_details(self, artwork_path: str = ""):
        return {
            "album_id": "302127",
            "artist": "Daft Punk",
            "title": "Discovery",
            "year": 2001,
            "record_type": "album",
            "release_date": "2001-03-07",
            "label": "Virgin",
            "genres": ["House", "Dance"],
            "track_count": 14,
            "identity_confidence": "HIGH",
            "archive_path_confidence": "HIGH",
            "archive_folder": "Daft Punk - Discovery",
            "archive_path": "/archive/Daft Punk - Discovery",
            "metadata_status": "CACHED",
            "metadata_detail": {
                "cached_fields": {
                    "upc": True,
                    "label": True,
                    "genres": True,
                    "contributors": False,
                    "release_date": True,
                },
                "missing_fields": ["contributors"],
            },
            "album_status": {
                "items": {
                    "validation": "Present",
                    "nfo": "Present",
                    "sfv": "Present",
                    "artwork": "Present" if artwork_path else "Missing",
                },
                "health_percent": 83,
            },
            "archive_readiness": {
                "state": "NEEDS_REVIEW",
                "reason": "Artwork evidence is incomplete.",
                "confidence": "MEDIUM",
            },
            "artwork": {
                "local": artwork_path,
                "urls": {"medium": "https://example.test/cover.jpg"} if not artwork_path else {},
            },
        }

    def test_presentation_summaries(self):
        presentation = album_presentation(self.sample_details())
        overview = dict(presentation["sections"]["overview"])
        metadata = dict(presentation["sections"]["metadata"])
        identity = dict(presentation["sections"]["identity"])

        self.assertEqual(overview["Album title"], "Discovery")
        self.assertEqual(metadata["Genre"], "House, Dance")
        self.assertEqual(metadata["Missing fields"], "contributors")
        self.assertEqual(identity["Album ID"], "302127")

    def test_thumbnail_loading_prefers_existing_local_artwork(self):
        with tempfile.TemporaryDirectory() as tmp:
            artwork = Path(tmp) / "cover.png"
            artwork.write_bytes(
                b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01"
                b"\x08\x06\x00\x00\x00\x1f\x15\xc4\x89\x00\x00\x00\nIDATx\x9cc\x00\x01"
                b"\x00\x00\x05\x00\x01\r\n-\xb4\x00\x00\x00\x00IEND\xaeB`\x82"
            )
            info = thumbnail_info(self.sample_details(str(artwork)))

        self.assertEqual(info["status"], "Present")
        self.assertEqual(info["source"], "local")
        self.assertEqual(info["display"], "cover.png")

    def test_missing_artwork_handling(self):
        details = self.sample_details()
        details["artwork"] = {"local": "", "urls": {}}
        info = thumbnail_info(details)

        self.assertEqual(info["status"], "Missing")
        self.assertEqual(info["source"], "none")
        self.assertEqual(info["display"], "No artwork available")


if __name__ == "__main__":
    unittest.main()
