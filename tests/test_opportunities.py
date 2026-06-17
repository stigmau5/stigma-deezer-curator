import unittest

from audio_division.opportunities import (
    filter_opportunities,
    generate_opportunities,
    opportunity_summary,
    render_opportunities_report,
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
        self.assertIn("Archive Opportunities Report", report)
        self.assertIn("Validated Album", report)


if __name__ == "__main__":
    unittest.main()
