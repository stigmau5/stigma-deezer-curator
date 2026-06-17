import subprocess
import tempfile
import unittest
from pathlib import Path

from audio_division.batch_operations import (
    available_batch_operations,
    collect_album_targets,
    render_batch_operation_report,
    run_batch_operation,
    validate_batch_targets,
)
from audio_division.operation_runner import load_operation_history


class BatchOperationTests(unittest.TestCase):
    def sample_library(self):
        return {
            "albums": [
                {
                    "album_id": "1",
                    "artist": "Alpha",
                    "title": "One",
                    "archive_path": "/archive/one",
                    "archive_path_confidence": "HIGH",
                },
                {
                    "album_id": "2",
                    "artist": "Beta",
                    "title": "Two",
                    "archive_path": "/archive/two",
                    "archive_path_confidence": "HIGH",
                },
                {
                    "album_id": "3",
                    "artist": "Gamma",
                    "title": "Three",
                    "archive_path": "",
                    "archive_path_confidence": "UNKNOWN",
                    "archive_path_reason": "no_archive_folder_evidence",
                },
            ]
        }

    def sample_opportunities(self):
        return [
            {"category": "missing_nfo", "album_id": "1", "artist": "Alpha", "album": "One"},
            {"category": "missing_nfo", "album_id": "2", "artist": "Beta", "album": "Two"},
            {"category": "missing_validation", "album_id": "3", "artist": "Gamma", "album": "Three"},
        ]

    def test_available_operations_and_target_collection(self):
        counts = available_batch_operations(self.sample_opportunities())
        targets = collect_album_targets("generate_nfo", self.sample_opportunities(), self.sample_library())
        self.assertEqual(counts["generate_nfo"], 2)
        self.assertEqual(len(targets), 2)
        self.assertEqual(targets[0]["target"], "/archive/one")

    def test_operation_eligibility(self):
        targets = collect_album_targets("validate_album", self.sample_opportunities(), self.sample_library())
        validated = validate_batch_targets("validate_album", targets, {"tools": {"flac_validator_path": "/bin/echo"}})
        self.assertFalse(validated[0]["eligible"])
        self.assertIn("No archive path", validated[0]["reason"])

    def test_success_history_and_summary(self):
        with tempfile.TemporaryDirectory() as tmp:
            history_path = Path(tmp) / "history.json"
            targets = collect_album_targets("generate_nfo", self.sample_opportunities(), self.sample_library())

            def runner(command, capture_output, text, timeout):
                return subprocess.CompletedProcess(command, 0, stdout="ok", stderr="")

            summary = run_batch_operation(
                "generate_nfo",
                targets,
                {"tools": {"nfo_generator_path": "/bin/echo"}},
                history_path,
                batch_id="batch-test",
                runner=runner,
            )
            history = load_operation_history(history_path)

        self.assertEqual(summary["successes"], 2)
        self.assertEqual(summary["failures"], 0)
        self.assertEqual(history["history"][0]["batch_id"], "batch-test")

    def test_partial_failure_continues(self):
        with tempfile.TemporaryDirectory() as tmp:
            history_path = Path(tmp) / "history.json"
            targets = collect_album_targets("generate_nfo", self.sample_opportunities(), self.sample_library())

            def runner(command, capture_output, text, timeout):
                if command[-1].endswith("two"):
                    return subprocess.CompletedProcess(command, 1, stdout="", stderr="bad")
                return subprocess.CompletedProcess(command, 0, stdout="ok", stderr="")

            summary = run_batch_operation(
                "generate_nfo",
                targets,
                {"tools": {"nfo_generator_path": "/bin/echo"}},
                history_path,
                batch_id="batch-partial",
                runner=runner,
            )

        self.assertEqual(summary["successes"], 1)
        self.assertEqual(summary["failures"], 1)

    def test_report_generation(self):
        report = render_batch_operation_report(
            {
                "batch_id": "batch",
                "operation": "generate_nfo",
                "total": 1,
                "successes": 1,
                "failures": 0,
                "skipped": 0,
                "duration_seconds": 0.1,
                "results": [{"result": "success", "album_id": "1", "artist": "A", "album": "B", "target": "/x", "message": "ok"}],
            }
        )
        self.assertIn("Batch Operation Report", report)
        self.assertIn("generate_nfo", report)


if __name__ == "__main__":
    unittest.main()
