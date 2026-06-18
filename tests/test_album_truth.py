import tempfile
import unittest
from pathlib import Path

from audio_division.album_truth import album_status_from_truth, album_truth, truth_summary
from audio_division.dashboard import compute_dashboard_summary
from audio_division.selection_state import archive_album_key, capture_archive_selection, selected_album_index


class AlbumTruthTests(unittest.TestCase):
    def test_filesystem_artifacts_win_over_validator_and_registry(self):
        with tempfile.TemporaryDirectory() as tmp:
            album_dir = Path(tmp)
            (album_dir / "release.nfo").write_text("nfo")
            truth = album_truth(
                artist="Artist",
                album="Album",
                archive_path=album_dir,
                registry_artifacts={
                    "nfo": False,
                    "sfv": True,
                    "playlist": True,
                    "artwork": True,
                    "validation_log": True,
                },
                validator_evidence={"validation": True},
                metadata_state="CACHED",
                identity_confidence="HIGH",
            )

        self.assertEqual(truth.artist, "Artist")
        self.assertEqual(truth.album, "Album")
        self.assertEqual(truth.nfo.status, "Present")
        self.assertTrue(truth.nfo_present)
        self.assertEqual(truth.nfo.source, "filesystem")
        self.assertEqual(truth.validation.status, "Missing")
        self.assertEqual(truth.validation.source, "filesystem")
        self.assertEqual(truth.sfv.status, "Missing")
        self.assertEqual(truth.health, 33)
        self.assertEqual(truth.readiness, "NEEDS_VALIDATION")
        self.assertEqual(truth.processing_state, "PROCESSING")
        self.assertEqual(truth.source, "filesystem")

    def test_validator_evidence_wins_when_filesystem_is_unavailable(self):
        truth = album_truth(
            registry_artifacts={"validation_log": False},
            validator_evidence={"validation": True},
            metadata_state="AVAILABLE_NOT_CACHED",
        )

        self.assertEqual(truth.validation.status, "Present")
        self.assertEqual(truth.validation.source, "validator_evidence")
        self.assertEqual(truth.metadata.status, "Missing")
        self.assertEqual(truth.processing_state, "DISCOVERED")

    def test_archive_registry_used_after_validator_evidence(self):
        status = album_status_from_truth(
            registry_artifacts={
                "nfo": True,
                "sfv": True,
                "playlist": False,
                "artwork": True,
                "validation_log": True,
            },
            metadata_state="CACHED",
        )

        self.assertEqual(status["items"]["nfo"], "Present")
        self.assertEqual(status["items"]["playlist"], "Missing")
        self.assertEqual(status["items"]["metadata"], "Present")
        self.assertEqual(status["health_percent"], 83)

    def test_truth_summary_counts_statuses(self):
        summary = truth_summary(
            [
                {"album_status": {"items": {"validation": "Present", "metadata": "Present"}}},
                {"album_status": {"items": {"validation": "Missing", "metadata": "Missing"}}},
            ]
        )

        self.assertEqual(summary["counts"]["validation"]["Present"], 1)
        self.assertEqual(summary["counts"]["validation"]["Missing"], 1)
        self.assertEqual(summary["validation_coverage"], 0.5)

    def test_album_truth_archive_ready_and_processing_state(self):
        with tempfile.TemporaryDirectory() as tmp:
            album_dir = Path(tmp)
            (album_dir / "cover.jpg").write_text("cover")
            (album_dir / "release.nfo").write_text("nfo")
            (album_dir / "release.sfv").write_text("sfv")
            (album_dir / "playlist.m3u8").write_text("playlist")
            (album_dir / "STIGMA_VALIDATED.txt").write_text("validated")
            truth = album_truth(
                archive_path=album_dir,
                metadata_state="CACHED",
                identity_confidence="HIGH",
            )

        self.assertEqual(truth.health, 100)
        self.assertEqual(truth.readiness, "ARCHIVE_READY")
        self.assertEqual(truth.processing_state, "ARCHIVED")
        self.assertEqual(truth.to_dict()["validation_present"], True)

    def test_selection_preservation_helpers(self):
        selected = {
            "artist_key": "artist",
            "archive_path": "/archive/artist-album",
            "artist": "Artist",
            "title": "Album",
        }
        state = capture_archive_selection(selected, active_tab=".tabs.archive", album_yview=(0.4, 0.8))
        albums = [
            {"artist_key": "artist", "archive_path": "/archive/other"},
            selected,
        ]

        self.assertEqual(archive_album_key(selected), "/archive/artist-album")
        self.assertEqual(state.active_tab, ".tabs.archive")
        self.assertEqual(state.album_yview, 0.4)
        self.assertEqual(selected_album_index(albums, state), 1)

    def test_dashboard_can_use_album_truth_validation_coverage(self):
        summary = compute_dashboard_summary(
            {
                "summary": {
                    "total_albums": 2,
                    "state_evidence_counts": {"VALIDATED": 2},
                },
                "albums": [{"album_id": "1"}, {"album_id": "2"}],
            },
            {"summary": {"confidence_counts": {}}},
            {"summary": {}},
            album_truth_summary={
                "counts": {
                    "validation": {
                        "Present": 1,
                        "Missing": 1,
                        "Unknown": 0,
                    }
                }
            },
        )

        self.assertEqual(summary["lifecycle"]["validated"], 2)
        self.assertEqual(summary["validation"]["coverage_percent"], 0.5)


if __name__ == "__main__":
    unittest.main()
