import tempfile
import unittest
from pathlib import Path

from audio_division.artifacts import detect_album_artifacts, render_archive_artifact_report, scan_archive_artifacts
from audio_division.dashboard import compute_dashboard_summary
from audio_division.operations import default_operations, operation_candidate_counts
from audio_division.tool_registry import default_tool_registry, tools_with_capability


class ToolIntegrationTests(unittest.TestCase):
    def test_tool_registration(self):
        registry = default_tool_registry()
        self.assertIn("stigma_flac_validator", registry)
        self.assertEqual(tools_with_capability(registry, "validate_album")[0].id, "stigma_flac_validator")
        self.assertIn("generate_nfo", registry["stigma_nfo_generator"].capabilities)

    def test_operation_registration(self):
        operations = default_operations()
        self.assertIn("validate_album", operations)
        self.assertEqual(operations["generate_nfo"].capability, "generate_nfo")
        self.assertEqual(operations["generate_sfv"].action_type, "missing_sfv")

    def test_operation_candidate_counts(self):
        counts = operation_candidate_counts(
            [
                {"type": "missing_nfo", "priority": "medium"},
                {"type": "missing_validation", "priority": "high"},
                {"type": "missing_validation", "priority": "high"},
            ]
        )
        self.assertEqual(counts["generate_nfo"], 1)
        self.assertEqual(counts["validate_album"], 2)

    def test_artifact_detection(self):
        with tempfile.TemporaryDirectory() as tmp:
            album = Path(tmp) / "Artist-Album-2026-FLAC-STiGMA"
            album.mkdir()
            (album / "release.nfo").write_text("nfo")
            (album / "release.sfv").write_text("sfv")
            (album / "playlist.m3u8").write_text("playlist")
            (album / "STIGMA_VALIDATED.txt").write_text("{}")
            artifacts = detect_album_artifacts(album)

        self.assertTrue(artifacts["nfo"])
        self.assertTrue(artifacts["sfv"])
        self.assertTrue(artifacts["playlist"])
        self.assertTrue(artifacts["validation_log"])

    def test_missing_artifact_handling_and_report(self):
        with tempfile.TemporaryDirectory() as tmp:
            album = Path(tmp) / "Artist-Album-2026-FLAC-STiGMA"
            album.mkdir()
            report = scan_archive_artifacts([album])

        self.assertEqual(report["summary"]["missing_nfo"], 1)
        self.assertEqual(report["summary"]["missing_sfv"], 1)
        self.assertIn("Archive Artifact Report", render_archive_artifact_report(report))

    def test_dashboard_operation_summary(self):
        summary = compute_dashboard_summary(
            {
                "summary": {"total_albums": 1, "state_evidence_counts": {"SHIPPED": 1, "VALIDATED": 0}},
                "albums": [
                    {
                        "album_id": "1",
                        "artist": "Artist",
                        "title": "Album",
                        "states": {"shipped": True, "validated": False},
                    }
                ],
            },
            {"summary": {"confidence_counts": {}}, "unresolved": []},
            {"summary": {"albums_with_metadata": 0}, "albums": {}},
        )
        self.assertEqual(summary["archive_operations"]["operation_count"], 5)
        self.assertEqual(summary["archive_operations"]["validate_album"], 1)


if __name__ == "__main__":
    unittest.main()
