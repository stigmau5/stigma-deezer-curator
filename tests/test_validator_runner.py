import json
import subprocess
import tempfile
import unittest
from pathlib import Path

from audio_division.validator_runner import run_validator_for_release


class ValidatorRunnerTests(unittest.TestCase):
    def test_validator_success_captures_evidence_and_refreshes_indexes(self):
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp)
            data_dir = project / "data"
            reports_dir = project / "reports"
            artists = data_dir / "artists"
            artists.mkdir(parents=True)
            album = project / "incoming" / "Example-Answer-2024-FLAC-STiGMA"
            album.mkdir(parents=True)
            (album / "01-answer.flac").write_text("audio", encoding="utf-8")
            (artists / "Example.txt").write_text(
                "\n".join(
                    [
                        "# Artist: Example",
                        "# Albums",
                        "https://www.deezer.com/album/42  # ALBUM | Answer | 2024 | 1 tracks",
                    ]
                ),
                encoding="utf-8",
            )

            def runner(command, capture_output, text, timeout):
                self.assertEqual(command, ["/tools/validator", str(album)])
                (album / "STIGMA_VALIDATED.txt").write_text(
                    json.dumps(
                        {
                            "album": album.name,
                            "validated_at": "2026-06-30T09:00:00",
                            "tracks": 1,
                            "warnings": [],
                            "completeness": {
                                "album_id": "42",
                                "hashes": {"01-answer.flac": "abc"},
                            },
                        }
                    ),
                    encoding="utf-8",
                )
                return subprocess.CompletedProcess(command, 0, stdout="validated", stderr="")

            result = run_validator_for_release(
                {"folder": str(album), "deezer_album_id": "42", "artist": "Example", "album": "Answer"},
                {
                    "tools": {"flac_validator_path": "/tools/validator"},
                    "validator": {"validated_index_path": "data/validated_albums.json", "validation_log_root": str(album)},
                    "reports": {"reports_directory": str(reports_dir)},
                },
                data_dir,
                reports_dir,
                data_dir / "operation_history.json",
                runner=runner,
            )

            validated = json.loads((data_dir / "validated_albums.json").read_text(encoding="utf-8"))
            lifecycle = json.loads((data_dir / "lifecycle_registry.json").read_text(encoding="utf-8"))
            identity = json.loads((data_dir / "identity_registry.json").read_text(encoding="utf-8"))
            runs = json.loads((data_dir / "validator_runs.json").read_text(encoding="utf-8"))
            history = json.loads((data_dir / "operation_history.json").read_text(encoding="utf-8"))
            report_exists = (reports_dir / "validation_evidence_report.md").exists()

            self.assertEqual(result["result"], "success")
            self.assertEqual(result["exit_code"], 0)
            self.assertEqual(result["validation_evidence"]["track_count"], 1)
            self.assertEqual(validated["42"]["source"], "stigma-flac-validator")
            self.assertTrue(lifecycle["albums"][0]["states"]["validated"])
            self.assertEqual(identity["releases"][0]["identity_confidence"], "HIGH")
            self.assertEqual(runs["runs"][0]["stdout"], "validated")
            self.assertEqual(history["history"][0]["operation"], "validate_downloaded_release")
            self.assertTrue(report_exists)

    def test_missing_validator_configuration_fails_without_mutating_indexes(self):
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp)
            data_dir = project / "data"
            album = project / "incoming" / "Example-Answer"
            album.mkdir(parents=True)

            result = run_validator_for_release({"folder": str(album)}, {"tools": {}}, data_dir)

        self.assertEqual(result["result"], "failure")
        self.assertIn("not configured", result["stderr"])
        self.assertFalse((data_dir / "validated_albums.json").exists())


if __name__ == "__main__":
    unittest.main()
