import unittest

from audio_division.opportunities import (
    derive_hub_opportunities,
    filter_opportunities,
    generate_opportunities,
    group_hub_opportunities,
    hub_opportunity_summary,
    opportunity_summary,
    render_archive_ready_report,
    render_hub_opportunities_report,
    render_opportunities_report,
    render_review_candidates_report,
)


class ArchiveOpportunitiesTests(unittest.TestCase):
    def sample_library(self):
        return {
            "albums": [
                {
                    "album_id": "1",
                    "artist": "Alpha Artist",
                    "title": "Validated Album",
                    "validation_status": "validated",
                    "identity_confidence": "HIGH",
                    "album_status": {
                        "health_percent": 67,
                        "items": {
                            "validation": "Present",
                            "nfo": "Missing",
                            "sfv": "Missing",
                            "playlist": "Missing",
                            "artwork": "Present",
                            "metadata": "Present",
                        },
                    },
                    "archive_readiness": {"state": "NEEDS_DOCUMENTATION"},
                },
                {
                    "album_id": "2",
                    "artist": "Beta Artist",
                    "title": "Unknown Album",
                    "validation_status": "not_validated",
                    "identity_confidence": "UNKNOWN",
                    "album_status": {
                        "health_percent": 25,
                        "items": {
                            "validation": "Missing",
                            "nfo": "Unknown",
                            "sfv": "Unknown",
                            "playlist": "Unknown",
                            "artwork": "Missing",
                            "metadata": "Missing",
                        },
                    },
                    "archive_readiness": {"state": "UNKNOWN"},
                },
            ]
        }

    def test_opportunity_generation_and_priority(self):
        opportunities = generate_opportunities(self.sample_library())
        categories = [item["category"] for item in opportunities]
        self.assertIn("missing_nfo", categories)
        self.assertIn("missing_validation", categories)
        self.assertIn("identity_review", categories)
        nfo = next(item for item in opportunities if item["category"] == "missing_nfo")
        self.assertEqual(nfo["priority"], "HIGH")
        self.assertEqual(nfo["recommended_action"], "Generate NFO")

    def test_filtering(self):
        opportunities = generate_opportunities(self.sample_library())
        filtered = filter_opportunities(opportunities, category="missing_metadata", artist="beta")
        self.assertEqual(len(filtered), 1)
        self.assertEqual(filtered[0]["album_id"], "2")

        high = filter_opportunities(opportunities, priority="HIGH")
        self.assertTrue(all(item["priority"] == "HIGH" for item in high))

    def test_album_linkage(self):
        opportunities = generate_opportunities(self.sample_library())
        linked = next(item for item in opportunities if item["album_id"] == "1")
        self.assertEqual(linked["artist"], "Alpha Artist")
        self.assertEqual(linked["album"], "Validated Album")

    def test_summary_and_report_generation(self):
        opportunities = generate_opportunities(self.sample_library())
        summary = opportunity_summary(opportunities)
        report = render_opportunities_report(opportunities, generated_at="2026-06-17T12:00:00")
        self.assertEqual(summary["total"], len(opportunities))
        self.assertGreater(summary["high"], 0)
        self.assertGreater(summary["by_readiness"]["UNKNOWN"], 0)
        self.assertIn("Archive Opportunities Report", report)
        self.assertIn("Validated Album", report)

    def test_hub_opportunity_classification_priority_and_grouping(self):
        library = {
            "albums": [
                {
                    "album_id": "1",
                    "artist": "Artist",
                    "title": "Ready",
                    "lifecycle_state": "VALIDATED",
                    "identity_confidence": "HIGH",
                    "metadata_status": "CACHED",
                    "archive_readiness": {"state": "ARCHIVE_READY", "reason": "Ready"},
                },
                {
                    "album_id": "2",
                    "artist": "Artist",
                    "title": "Validation",
                    "lifecycle_state": "SHIPPED",
                    "identity_confidence": "HIGH",
                    "metadata_status": "CACHED",
                    "archive_readiness": {"state": "NEEDS_VALIDATION", "reason": "Validation missing"},
                },
                {
                    "album_id": "3",
                    "artist": "Artist",
                    "title": "Docs",
                    "lifecycle_state": "VALIDATED",
                    "identity_confidence": "HIGH",
                    "metadata_status": "CACHED",
                    "archive_readiness": {"state": "NEEDS_DOCUMENTATION", "reason": "Docs missing"},
                },
                {
                    "album_id": "4",
                    "artist": "Artist",
                    "title": "Metadata",
                    "lifecycle_state": "VALIDATED",
                    "identity_confidence": "HIGH",
                    "metadata_status": "AVAILABLE_NOT_CACHED",
                    "metadata_detail": {"state": "AVAILABLE_NOT_CACHED", "reason": "Not imported"},
                    "archive_readiness": {"state": "OTHER", "reason": ""},
                },
                {
                    "album_id": "5",
                    "artist": "Artist",
                    "title": "Review",
                    "lifecycle_state": "DISCOVERED",
                    "identity_confidence": "UNKNOWN",
                    "metadata_status": "AVAILABLE_NOT_CACHED",
                    "archive_readiness": {"state": "UNKNOWN", "reason": "Path unknown"},
                },
            ]
        }
        opportunities = derive_hub_opportunities(library)
        grouped = group_hub_opportunities(opportunities)
        categories = {item["category"] for item in opportunities}
        self.assertEqual(categories, {"ARCHIVE_READY", "NEEDS_VALIDATION", "NEEDS_DOCUMENTATION", "NEEDS_METADATA", "NEEDS_REVIEW"})
        self.assertEqual(grouped["NEEDS_VALIDATION"][0]["priority"], "HIGH")
        self.assertEqual(grouped["NEEDS_DOCUMENTATION"][0]["priority"], "MEDIUM")
        self.assertEqual(grouped["NEEDS_METADATA"][0]["priority"], "LOW")

    def test_hub_summary_and_reports(self):
        opportunities = derive_hub_opportunities(self.sample_library())
        summary = hub_opportunity_summary(opportunities)
        report = render_hub_opportunities_report(opportunities, generated_at="2026-06-17T12:00:00")
        ready = render_archive_ready_report(opportunities)
        review = render_review_candidates_report(opportunities)
        self.assertEqual(summary["total"], len(opportunities))
        self.assertIn("NEEDS_REVIEW", summary["by_category"])
        self.assertIn("Opportunities Report", report)
        self.assertIn("Archive Ready Report", ready)
        self.assertIn("Review Candidates Report", review)


if __name__ == "__main__":
    unittest.main()
