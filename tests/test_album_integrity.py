import tempfile
import unittest
from pathlib import Path

from audio_division.album_integrity import album_integrity


class AlbumIntegrityTests(unittest.TestCase):
    def test_filesystem_evidence_drives_integrity(self):
        with tempfile.TemporaryDirectory() as tmp:
            album = Path(tmp)
            (album / "cover.jpg").write_text("cover")
            (album / "00-release.nfo").write_text("nfo")
            (album / "00-release.sfv").write_text("01_song.flac ABCD1234\n")
            (album / "00-release.m3u8").write_text("01_song.flac\n")
            (album / "STIGMA_VALIDATED.txt").write_text("validated")
            (album / "01_song.flac").write_text("audio")

            result = album_integrity({"archive_path": str(album)})

        checks = {item["id"]: item for item in result["checks"]}
        self.assertEqual(checks["artwork"]["status"], "Present")
        self.assertEqual(checks["validation"]["source"], "Filesystem")
        self.assertEqual(checks["audio_files"]["path"], "1 audio file(s)")
        self.assertEqual(result["health_score"], 100)
        self.assertEqual(result["warnings"], [])

    def test_missing_files_are_explained(self):
        with tempfile.TemporaryDirectory() as tmp:
            album = Path(tmp)
            (album / "album.m3u8").write_text("missing.flac\n")

            result = album_integrity({"archive_path": str(album)})

        checks = {item["id"]: item for item in result["checks"]}
        self.assertEqual(checks["playlist"]["status"], "Present")
        self.assertEqual(checks["audio_files"]["status"], "Missing")
        self.assertLess(result["health_score"], 100)
        self.assertIn("Artwork is missing.", result["warnings"])
        self.assertIn("Broken playlist reference: album.m3u8: missing.flac", result["warnings"])

    def test_albumtruth_fallback_when_archive_folder_is_unknown(self):
        result = album_integrity(
            {
                "album_status": {
                    "items": {"validation": "Present", "nfo": "Missing"},
                    "truth_sources": {"validation": "validator_evidence", "nfo": "none"},
                }
            }
        )

        checks = {item["id"]: item for item in result["checks"]}
        self.assertEqual(checks["validation"]["status"], "Present")
        self.assertEqual(checks["validation"]["source"], "Validated Index")
        self.assertEqual(checks["nfo"]["status"], "Missing")
        self.assertIn("Archive folder is unavailable", result["warnings"][0])


if __name__ == "__main__":
    unittest.main()
