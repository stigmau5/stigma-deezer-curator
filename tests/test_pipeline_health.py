import unittest
from datetime import datetime

from audio_division.lifecycle_state import (
    STATE_ARCHIVED,
    STATE_DISCOVERED,
    STATE_DOWNLOADED,
    STATE_READY_FOR_PROCESSING,
    STATE_UNKNOWN,
    STATE_VALIDATED,
)
from audio_division.pipeline_health import pipeline_health_report


def release(state: str, **extra):
    row = {
        "artist": "Example",
        "title": f"{state} Album",
        "album_id": extra.pop("album_id", state.lower()),
        "pipeline_state": {
            "state": state,
            "evidence": ["test"],
            "reason": "test",
            "confidence": "HIGH",
            "conflicts": extra.pop("conflicts", []),
        },
        "identity_confidence": extra.pop("identity_confidence", "HIGH"),
    }
    row.update(extra)
    return row


class PipelineHealthTests(unittest.TestCase):
    def test_counts_canonical_lifecycle_states(self):
        report = pipeline_health_report(
            [
                release(STATE_DISCOVERED),
                release(STATE_DOWNLOADED),
                release(STATE_VALIDATED),
                release(STATE_READY_FOR_PROCESSING),
                release(STATE_ARCHIVED),
                release(STATE_UNKNOWN),
            ]
        )

        self.assertEqual(report.discovered, 1)
        self.assertEqual(report.downloaded, 1)
        self.assertEqual(report.validated, 1)
        self.assertEqual(report.ready_to_process, 1)
        self.assertEqual(report.archived, 1)
        self.assertEqual(report.unknown, 1)
        self.assertEqual(report.total_releases, 6)

    def test_needs_review_uses_conflicts_and_identity(self):
        report = pipeline_health_report(
            [
                release(STATE_DOWNLOADED, conflicts=["validated_without_album_folder"]),
                release(STATE_VALIDATED, identity_confidence="UNKNOWN"),
            ]
        )

        self.assertEqual(report.needs_review, 2)
        self.assertEqual(report.downloaded, 0)
        self.assertEqual(report.validated, 0)

    def test_operational_risk_counts(self):
        report = pipeline_health_report(
            [
                release(STATE_DOWNLOADED, status="Downloaded", archive_path=""),
                release(STATE_DOWNLOADED, status="Duplicate Download", evidence=["duplicate_download"]),
                release(STATE_DOWNLOADED, validation_status="failed", exit_code=1),
                release(STATE_VALIDATED),
                release(STATE_READY_FOR_PROCESSING),
            ]
        )

        self.assertEqual(report.stalled_downloads, 2)
        self.assertEqual(report.duplicate_downloads, 1)
        self.assertEqual(report.validation_failures, 1)
        self.assertEqual(report.ready_to_archive, 2)

    def test_recently_archived_uses_archive_timestamps(self):
        report = pipeline_health_report(
            [
                release(STATE_ARCHIVED, archived_at="2026-06-20T12:00:00"),
                release(STATE_ARCHIVED, archived_at="2026-04-01T12:00:00"),
            ],
            reference_time=datetime(2026, 6, 30, 12, 0, 0),
            recent_days=30,
        )

        self.assertEqual(report.recently_archived, 1)

    def test_legacy_lifecycle_rows_are_normalized(self):
        report = pipeline_health_report(
            [
                {"artist": "A", "title": "Shipped", "album_id": "1", "highest_state": "SHIPPED"},
                {"artist": "B", "title": "Validated", "album_id": "2", "highest_state": "VALIDATED"},
            ]
        )

        self.assertEqual(report.downloaded, 1)
        self.assertEqual(report.validated, 1)

    def test_report_serializes_to_dict(self):
        payload = pipeline_health_report([release(STATE_DISCOVERED)]).to_dict()

        self.assertEqual(payload["discovered"], 1)
        self.assertIn("ready_to_archive", payload)


if __name__ == "__main__":
    unittest.main()
