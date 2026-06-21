import unittest

from audio_division.actions import action_summary, generate_archive_actions, render_archive_actions_report
from audio_division.dashboard import compute_dashboard_summary


class ArchiveActionsTests(unittest.TestCase):
    def test_action_generation_and_priority(self):
        lifecycle = {
            "albums": [
                {
                    "album_id": "1",
                    "artist": "Artist",
                    "title": "Validated",
                    "states": {"validated": True, "shipped": True},
                },
                {
                    "album_id": "2",
                    "artist": "Artist",
                    "title": "Needs Validation",
                    "states": {"validated": False, "shipped": True},
                },
            ]
        }
        identity = {
            "unresolved": [
                {
                    "reason": "all_tracks_missing_album_id",
                    "folder": "Artist-Unknown-2026-FLAC-STiGMA",
                    "parsed_folder": {"artist": "Artist", "title": "Unknown"},
                    "candidates": [{"deezer_album_id": "3", "artist": "Artist", "title": "Unknown"}],
                }
            ]
        }
        metadata = {"albums": {"1": {"covers": {}}}}

        actions = generate_archive_actions(lifecycle, identity, metadata)
        categories = {action["type"] for action in actions}

        self.assertIn("missing_nfo", categories)
        self.assertIn("missing_sfv", categories)
        self.assertIn("missing_validation", categories)
        self.assertEqual(categories, {"missing_nfo", "missing_sfv", "missing_validation"})
        self.assertEqual(actions[0]["priority"], "high")

    def test_action_grouping(self):
        summary = action_summary(
            [
                {"type": "missing_nfo", "priority": "medium"},
                {"type": "missing_nfo", "priority": "medium"},
                {"type": "identity_review", "priority": "high"},
            ]
        )
        self.assertEqual(summary["total_actions"], 3)
        self.assertEqual(summary["by_category"]["missing_nfo"], 2)
        self.assertEqual(summary["by_priority"]["high"], 1)

    def test_dashboard_integration(self):
        summary = compute_dashboard_summary(
            {
                "summary": {"total_albums": 1, "state_evidence_counts": {"VALIDATED": 1}},
                "albums": [
                    {
                        "album_id": "1",
                        "artist": "Artist",
                        "title": "Album",
                        "states": {"validated": True},
                    }
                ],
            },
            {"summary": {"confidence_counts": {}}, "unresolved": []},
            {"summary": {"albums_with_metadata": 0, "coverage_percent": 0.0}, "albums": {}},
        )
        self.assertGreater(summary["archive_actions"]["action_count"], 0)
        self.assertEqual(summary["archive_actions"]["missing_nfo"], 1)

    def test_dashboard_actions_delegate_to_maintenance_when_albumtruth_is_available(self):
        album = {
            "album_id": "1",
            "artist": "Artist",
            "title": "Album",
            "archive_path": "/archive/Album",
            "metadata_status": "CACHED",
            "identity_confidence": "HIGH",
            "album_truth": {
                "items": {
                    "validation": "Present",
                    "nfo": "Missing",
                    "sfv": "Present",
                    "metadata": "Present",
                },
                "readiness": "NEEDS_DOCUMENTATION",
                "metadata_status": "CACHED",
                "identity_confidence": "HIGH",
            },
            "pipeline_state": {"state": "ARCHIVED"},
        }

        summary = compute_dashboard_summary(
            {"summary": {"total_albums": 1, "state_evidence_counts": {"VALIDATED": 1}}},
            {"summary": {"confidence_counts": {}}},
            {"summary": {}, "albums": {}},
            maintenance_albums=[album],
        )

        self.assertEqual(summary["maintenance"]["categories"]["needs_documentation"], 1)
        self.assertEqual(summary["top_opportunities"]["needs_documentation"], 1)
        self.assertEqual(summary["archive_actions"]["missing_nfo"], 1)
        self.assertEqual(summary["archive_actions"]["missing_sfv"], 0)

    def test_report_generation(self):
        report = render_archive_actions_report(
            [
                {
                    "type": "missing_validation",
                    "album_id": "2",
                    "artist": "Artist",
                    "title": "Needs Validation",
                    "priority": "high",
                    "description": "Album was shipped but has no validation evidence.",
                    "evidence": ["shipped_not_validated"],
                }
            ],
            generated_at="2026-06-16T12:00:00",
        )
        self.assertIn("Archive Actions Report", report)
        self.assertIn("missing_validation", report)


if __name__ == "__main__":
    unittest.main()
