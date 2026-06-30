import tempfile
import unittest
from pathlib import Path

from audio_division.incoming_projection import (
    STATUS_ALREADY_ARCHIVED,
    STATUS_ALREADY_VALIDATED,
    STATUS_DUPLICATE_DOWNLOAD,
    STATUS_READY_TO_VALIDATE,
    incoming_releases,
)


class IncomingProjectionTests(unittest.TestCase):
    def settings(self, root: Path):
        return {"archive_paths": {"incoming_root": str(root)}}

    def test_ready_to_validate_release_uses_identity_and_metadata(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            folder = root / "Example-Answer-2024-FLAC-STiGMA"
            folder.mkdir()
            (folder / "01-answer.flac").write_text("audio", encoding="utf-8")

            rows = incoming_releases(
                self.settings(root),
                identity_registry={
                    "releases": [
                        {
                            "archive_identity": {"folder": "Example-Answer-2024-FLAC-STiGMA"},
                            "discovery_identity": {
                                "artist": "Example",
                                "title": "Answer",
                                "deezer_album_id": "42",
                                "type": "album",
                            },
                            "identity_confidence": "HIGH",
                        }
                    ]
                },
                metadata_cache={"albums": {"42": {"release_date": "2024-01-01"}}},
            )

        self.assertEqual(len(rows), 1)
        release = rows[0]
        self.assertEqual(release.status, STATUS_READY_TO_VALIDATE)
        self.assertEqual(release.deezer_album_id, "42")
        self.assertEqual(release.metadata_status, "CACHED")
        self.assertEqual(release.identity_confidence, "HIGH")
        self.assertIn("identity_registry", release.evidence)

    def test_archive_correlation_keeps_download_visible_as_already_archived(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "Example-Answer-2024-FLAC-STiGMA").mkdir()

            rows = incoming_releases(
                self.settings(root),
                archive_registry={
                    "albums": [
                        {
                            "name": "Example-Answer-2024-FLAC-STiGMA",
                            "archive_path": "/archive/E/Example/Example-Answer-2024-FLAC-STiGMA",
                        }
                    ]
                },
            )

        self.assertEqual(rows[0].status, STATUS_ALREADY_ARCHIVED)
        self.assertEqual(rows[0].archive_path, "/archive/E/Example/Example-Answer-2024-FLAC-STiGMA")

    def test_lifecycle_validation_marks_already_validated(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "Example-Answer-2024-FLAC-STiGMA").mkdir()

            rows = incoming_releases(
                self.settings(root),
                identity_registry={
                    "releases": [
                        {
                            "archive_identity": {"folder": "Example-Answer-2024-FLAC-STiGMA"},
                            "discovery_identity": {"artist": "Example", "title": "Answer", "deezer_album_id": "42"},
                        }
                    ]
                },
                lifecycle_registry={"albums": [{"album_id": "42", "highest_state": "VALIDATED"}]},
            )

        self.assertEqual(rows[0].status, STATUS_ALREADY_VALIDATED)
        self.assertEqual(rows[0].lifecycle_state, "VALIDATED")

    def test_duplicate_downloads_are_marked(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "Example-Answer-2024-FLAC-STiGMA").mkdir()
            (root / "Example-Answer-2024-REPACK-FLAC-STiGMA").mkdir()

            rows = incoming_releases(
                self.settings(root),
                identity_registry={
                    "releases": [
                        {
                            "discovery_identity": {"artist": "Example", "title": "Answer", "deezer_album_id": "42"},
                        }
                    ]
                },
            )

        self.assertEqual({row.status for row in rows}, {STATUS_DUPLICATE_DOWNLOAD})
        self.assertTrue(all("duplicate_download" in row.evidence for row in rows))


if __name__ == "__main__":
    unittest.main()
