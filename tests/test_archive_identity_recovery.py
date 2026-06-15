import unittest

from curator.archive_identity_recovery import (
    archive_strength,
    build_archive_identity_recovery,
    recovery_candidates_for_unresolved,
    recovery_level,
    render_archive_identity_recovery_report,
    render_archive_strength_report,
    render_recoverable_identity_report,
    render_unrecoverable_identity_report,
)


class ArchiveIdentityRecoveryTests(unittest.TestCase):
    def test_recovery_level_high(self):
        level, reasons = recovery_level(
            {"artist": "Artist", "title": "Album", "year": "2026"},
            {
                "normalized_artist": "artist",
                "normalized_title": "album",
                "year": "2026",
                "track_count": 10,
            },
            {"track_count": 10},
        )
        self.assertEqual(level, "RECOVERABLE_HIGH")
        self.assertIn("matching_year", reasons)
        self.assertIn("matching_track_count", reasons)

    def test_recovery_level_medium(self):
        level, reasons = recovery_level(
            {"artist": "Artist", "title": "Album", "year": "2026"},
            {
                "normalized_artist": "artist",
                "normalized_title": "album",
                "year": None,
                "track_count": None,
            },
            {"track_count": 10},
        )
        self.assertEqual(level, "RECOVERABLE_MEDIUM")
        self.assertEqual(reasons, ["exact_artist", "exact_title"])

    def test_recovery_level_low(self):
        level, reasons = recovery_level(
            {"artist": "Artist", "title": "Album Deluxe", "year": "2026"},
            {
                "normalized_artist": "artist",
                "normalized_title": "album deluxe edition",
                "year": None,
                "track_count": None,
            },
            {},
        )
        self.assertEqual(level, "RECOVERABLE_LOW")
        self.assertIn("exact_artist", reasons)

    def test_candidate_generation_and_unresolved_detection(self):
        candidates = [
            {
                "deezer_album_id": "1",
                "artist": "Artist",
                "title": "Album",
                "normalized_artist": "artist",
                "normalized_title": "album",
                "year": "2026",
                "track_count": 10,
                "highest_lifecycle_state": "DISCOVERED",
            }
        ]
        unresolved = {
            "parsed_folder": {"artist": "Artist", "title": "Album", "year": "2026"},
            "validation": {"track_count": 10},
        }
        matches = recovery_candidates_for_unresolved(unresolved, candidates)
        self.assertEqual(matches[0]["recovery_level"], "RECOVERABLE_HIGH")
        self.assertEqual(matches[0]["deezer_album_id"], "1")

        no_matches = recovery_candidates_for_unresolved(
            {"parsed_folder": {"artist": "Other", "title": "Missing"}, "validation": {}},
            candidates,
        )
        self.assertEqual(no_matches, [])

    def test_recovery_registry_and_reports(self):
        identity_registry = {
            "releases": [
                {
                    "identity_confidence": "HIGH",
                    "discovery_identity": {"deezer_album_id": "1"},
                    "validation": {"available": True},
                },
                {
                    "identity_confidence": "UNKNOWN",
                    "discovery_identity": {"deezer_album_id": "2"},
                    "validation": {"available": False},
                },
            ],
            "unresolved": [
                {
                    "folder": "Artist-Album-2026-FLAC-STiGMA",
                    "parsed_folder": {"artist": "Artist", "title": "Album", "year": "2026"},
                    "reason": "all_tracks_missing_album_id",
                    "validation": {"track_count": 10},
                },
                {
                    "folder": "Other-Missing-2026-FLAC-STiGMA",
                    "parsed_folder": {"artist": "Other", "title": "Missing", "year": "2026"},
                    "reason": "all_tracks_missing_album_id",
                    "validation": {"track_count": 9},
                },
            ],
        }
        lifecycle_registry = {
            "albums": [
                {
                    "album_id": "2",
                    "artist": "Artist",
                    "title": "Album",
                    "highest_state": "DISCOVERED",
                    "details": {"year": "2026", "validated_tracks": 10},
                    "validation_evidence": {},
                }
            ]
        }
        registry = build_archive_identity_recovery(
            identity_registry,
            lifecycle_registry,
            generated_at="2026-06-15T12:00:00",
        )

        self.assertEqual(registry["summary"]["recoverable_total"], 1)
        self.assertEqual(registry["summary"]["unrecoverable_total"], 1)
        self.assertEqual(registry["summary"]["recovery_counts"]["RECOVERABLE_HIGH"], 1)
        self.assertIn("Archive Identity Recovery Report", render_archive_identity_recovery_report(registry))
        self.assertIn("Recoverable Identity Report", render_recoverable_identity_report(registry))
        self.assertIn("Unrecoverable Identity Report", render_unrecoverable_identity_report(registry))
        self.assertIn("Archive Strength Report", render_archive_strength_report(registry))

    def test_archive_strength_calculation(self):
        strength = archive_strength(
            {
                "releases": [
                    {
                        "identity_confidence": "HIGH",
                        "discovery_identity": {"deezer_album_id": "1"},
                        "validation": {"available": True},
                    },
                    {
                        "identity_confidence": "UNKNOWN",
                        "discovery_identity": {"deezer_album_id": "2"},
                        "validation": {"available": False},
                    },
                ]
            },
            {"albums": []},
        )
        self.assertEqual(strength["categories"]["lifecycle_coverage"], 1.0)
        self.assertEqual(strength["categories"]["identity_coverage"], 0.5)
        self.assertEqual(strength["categories"]["validation_coverage"], 0.5)
        self.assertEqual(strength["overall_archive_strength_score"], 0.4)


if __name__ == "__main__":
    unittest.main()
