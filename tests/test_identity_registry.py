import json
import tempfile
import unittest
from pathlib import Path

from curator.identity import (
    build_identity_registry,
    manifest_hash_from_hashes,
    render_identity_resolution_report,
    render_unresolved_identity_report,
    split_archive_folder,
)


class IdentityRegistryTests(unittest.TestCase):
    def test_manifest_hash_is_stable(self):
        left = manifest_hash_from_hashes({"02.flac": "bbb", "01.flac": "aaa"})
        right = manifest_hash_from_hashes({"01.flac": "aaa", "02.flac": "bbb"})
        self.assertEqual(left, right)
        self.assertEqual(len(left), 64)

    def test_split_archive_folder(self):
        parsed = split_archive_folder("Artist-Album Title-2026-FLAC-STiGMA")
        self.assertEqual(parsed["artist"], "Artist")
        self.assertEqual(parsed["title"], "Album Title")
        self.assertEqual(parsed["year"], "2026")

    def test_confidence_scoring_and_projection(self):
        registry = build_identity_registry(
            {
                "generated_at": "2026-06-15T12:00:00",
                "albums": [
                    {
                        "album_id": "302127",
                        "artist": "Daft Punk",
                        "title": "Discovery",
                        "highest_state": "VALIDATED",
                        "states": {"validated": True},
                        "sources": ["validated_albums.json"],
                        "details": {"validated_folder": "Daft Punk-Discovery-2001-FLAC-STiGMA"},
                        "validation_evidence": {
                            "available": True,
                            "available_evidence": ["validated_index"],
                            "folder": "Daft Punk-Discovery-2001-FLAC-STiGMA",
                            "track_count": 14,
                        },
                    },
                    {
                        "album_id": "999",
                        "artist": "Unvalidated Artist",
                        "title": "Waiting",
                        "highest_state": "DISCOVERED",
                        "states": {"validated": False},
                        "sources": ["artists/Unvalidated.txt"],
                        "details": {},
                        "validation_evidence": {"available": False},
                    },
                ],
            },
            generated_at="2026-06-15T12:01:00",
        )

        self.assertEqual(registry["summary"]["total_releases"], 2)
        self.assertEqual(registry["summary"]["confidence_counts"]["HIGH"], 1)
        self.assertEqual(registry["summary"]["confidence_counts"]["UNKNOWN"], 1)
        high = registry["releases"][0]
        self.assertEqual(high["identity_confidence"], "HIGH")
        self.assertIn("validated_index", high["evidence"])

    def test_unresolved_detection_with_medium_candidate(self):
        with tempfile.TemporaryDirectory() as tmp:
            log_path = Path(tmp) / "Ronny & Ragge-Let's Pok-1993-FLAC-STiGMA" / "STIGMA_VALIDATED.txt"
            log_path.parent.mkdir()
            log_path.write_text(
                json.dumps(
                    {
                        "album": "Ronny & Ragge-Let's Pok-1993-FLAC-STiGMA",
                        "validated_at": "2026-03-06T19:00:00",
                        "tracks": 10,
                        "warnings": [],
                        "completeness": {
                            "album": "Let's Pok",
                            "album_artist": "Ronny & Ragge",
                            "missing_album_id_tracks": 10,
                            "album_id": None,
                            "hashes": {"01.flac": "abc"},
                        },
                    }
                ),
                encoding="utf-8",
            )

            registry = build_identity_registry(
                {
                    "generated_at": "2026-06-15T12:00:00",
                    "albums": [
                        {
                            "album_id": "1135101",
                            "artist": "Ronny and Ragge",
                            "title": "Let's Pok",
                            "highest_state": "DISCOVERED",
                            "states": {"validated": False},
                            "sources": ["artists/Ronny_and_Ragge.txt"],
                            "details": {},
                            "validation_evidence": {"available": False},
                        }
                    ],
                    "unmatched_validation_logs": [
                        {
                            "path": str(log_path),
                            "folder": "Ronny & Ragge-Let's Pok-1993-FLAC-STiGMA",
                            "reason": "no_album_id_or_index_folder_match",
                        }
                    ],
                },
                generated_at="2026-06-15T12:01:00",
            )

        self.assertEqual(registry["summary"]["unresolved_validator_logs"], 1)
        self.assertEqual(registry["summary"]["unresolved_with_candidates"], 1)
        unresolved = registry["unresolved"][0]
        self.assertEqual(unresolved["identity_confidence"], "MEDIUM")
        self.assertEqual(unresolved["reason"], "all_tracks_missing_album_id")
        self.assertEqual(unresolved["candidates"][0]["deezer_album_id"], "1135101")
        self.assertEqual(len(unresolved["validation"]["manifest_hash"]), 64)

    def test_report_rendering(self):
        registry = build_identity_registry(
            {
                "generated_at": "2026-06-15T12:00:00",
                "albums": [],
                "unmatched_validation_logs": [],
            },
            generated_at="2026-06-15T12:01:00",
        )
        self.assertIn("Identity Resolution Report", render_identity_resolution_report(registry))
        self.assertIn("Unresolved Identity Report", render_unresolved_identity_report(registry))


if __name__ == "__main__":
    unittest.main()
