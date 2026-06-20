import tempfile
import unittest
from pathlib import Path

from audio_division.lifecycle_state import (
    STATE_ARCHIVED,
    STATE_DISCOVERED,
    STATE_DOWNLOADED,
    STATE_READY_FOR_PROCESSING,
    STATE_UNKNOWN,
    STATE_VALIDATED,
    attach_lifecycle_state,
    detect_lifecycle_state,
    lifecycle_state_summary,
    merge_lifecycle_rows,
    render_lifecycle_state_report,
)


class LifecycleStateTests(unittest.TestCase):
    def test_discovered_from_curator_album_id(self):
        state = detect_lifecycle_state({"album_id": "123", "lifecycle_state": "DISCOVERED"})

        self.assertEqual(state.state, STATE_DISCOVERED)
        self.assertIn("curator_state", state.evidence)

    def test_downloaded_from_existing_folder(self):
        with tempfile.TemporaryDirectory() as tmp:
            state = detect_lifecycle_state({"folder": tmp})

        self.assertEqual(state.state, STATE_DOWNLOADED)
        self.assertIn("download_folder", state.evidence)

    def test_validated_from_validator_evidence_without_folder(self):
        state = detect_lifecycle_state({"album_id": "123", "validation": {"available": True}})

        self.assertEqual(state.state, STATE_VALIDATED)
        self.assertIn("validated_without_album_folder", state.conflicts)

    def test_ready_for_processing_from_downloaded_validation_marker(self):
        with tempfile.TemporaryDirectory() as tmp:
            folder = Path(tmp)
            (folder / "STIGMA_VALIDATED.txt").write_text("ok", encoding="utf-8")

            state = detect_lifecycle_state({"folder": str(folder)})

        self.assertEqual(state.state, STATE_READY_FOR_PROCESSING)
        self.assertIn("validation_marker", state.evidence)

    def test_archived_precedence_over_other_evidence(self):
        with tempfile.TemporaryDirectory() as tmp:
            archive = Path(tmp) / "archive_album"
            download = Path(tmp) / "download_album"
            archive.mkdir()
            download.mkdir()
            album = {
                "album_id": "123",
                "archive_path": str(archive),
                "archive_path_reason": "archive_registry",
                "folder": str(download),
                "validation": {"available": True},
            }

            state = detect_lifecycle_state(album)

        self.assertEqual(state.state, STATE_ARCHIVED)
        self.assertIn("ready_for_processing_and_archived", state.conflicts)

    def test_unknown_without_evidence(self):
        state = detect_lifecycle_state({})

        self.assertEqual(state.state, STATE_UNKNOWN)

    def test_summary_and_report_rendering(self):
        rows = [
            attach_lifecycle_state({"album_id": "1"}),
            attach_lifecycle_state({"validation": {"available": True}}),
        ]

        summary = lifecycle_state_summary(rows)
        report = render_lifecycle_state_report(rows)

        self.assertEqual(summary["state_counts"][STATE_DISCOVERED], 1)
        self.assertEqual(summary["state_counts"][STATE_VALIDATED], 1)
        self.assertIn("validated_without_album_folder", report)

    def test_merge_prefers_highest_state_for_same_album(self):
        rows = merge_lifecycle_rows(
            [attach_lifecycle_state({"album_id": "1", "lifecycle_state": "DISCOVERED"})],
            [attach_lifecycle_state({"album_id": "1", "validation": {"available": True}})],
        )

        self.assertEqual(len(rows), 1)
        self.assertEqual(rows[0]["pipeline_state"]["state"], STATE_VALIDATED)


if __name__ == "__main__":
    unittest.main()
