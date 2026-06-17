import unittest

from audio_division.archive_readiness import (
    annotate_library_readiness,
    evaluate_album_readiness,
    readiness_summary,
    render_archive_readiness_report,
)
from audio_division.dashboard import compute_dashboard_summary


class ArchiveReadinessTests(unittest.TestCase):
    def ready_album(self):
        return {
            "album_id": "1",
            "artist": "Artist",
            "title": "Ready",
            "archive_path": "/archive/ready",
            "archive_path_confidence": "HIGH",
            "identity_confidence": "HIGH",
            "album_status": {
                "items": {
                    "validation": "Present",
                    "nfo": "Present",
                    "sfv": "Present",
                    "artwork": "Present",
                }
            },
        }

    def test_archive_ready_calculation(self):
        readiness = evaluate_album_readiness(self.ready_album())
        self.assertEqual(readiness["state"], "ARCHIVE_READY")
        self.assertEqual(readiness["confidence"], "HIGH")

    def test_rule_precedence_unknown_before_validation(self):
        album = self.ready_album()
        album["archive_path"] = ""
        album["archive_path_confidence"] = "UNKNOWN"
        album["album_status"]["items"]["validation"] = "Missing"
        readiness = evaluate_album_readiness(album)
        self.assertEqual(readiness["state"], "UNKNOWN")
        self.assertIn("archive_path_missing", readiness["explanation"])

    def test_validation_detection(self):
        album = self.ready_album()
        album["album_status"]["items"]["validation"] = "Missing"
        readiness = evaluate_album_readiness(album)
        self.assertEqual(readiness["state"], "NEEDS_VALIDATION")

    def test_documentation_detection(self):
        album = self.ready_album()
        album["album_status"]["items"]["nfo"] = "Missing"
        readiness = evaluate_album_readiness(album)
        self.assertEqual(readiness["state"], "NEEDS_DOCUMENTATION")
        self.assertIn("nfo_missing", readiness["explanation"])

    def test_needs_review_for_artwork(self):
        album = self.ready_album()
        album["album_status"]["items"]["artwork"] = "Missing"
        readiness = evaluate_album_readiness(album)
        self.assertEqual(readiness["state"], "NEEDS_REVIEW")

    def test_summary_report_and_dashboard(self):
        library = {"albums": [self.ready_album()]}
        annotate_library_readiness(library)
        summary = readiness_summary(library["albums"])
        report = render_archive_readiness_report(library, generated_at="2026-06-17T12:00:00")
        dashboard = compute_dashboard_summary(
            {"summary": {"total_albums": 1, "state_evidence_counts": {}}},
            {"summary": {"confidence_counts": {}}},
            {"summary": {}},
            readiness_summary=summary,
        )
        self.assertEqual(summary["counts"]["ARCHIVE_READY"], 1)
        self.assertIn("Archive Readiness Report", report)
        self.assertEqual(dashboard["archive_readiness"]["archive_ready"], 1)


if __name__ == "__main__":
    unittest.main()
