import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock

from audio_division.dashboard import compute_dashboard_summary
from audio_division.operation_runner import (
    load_operation_history,
    prepare_command,
    run_operation,
    validate_operation_request,
)
from audio_division.settings import load_audio_division_settings, save_audio_division_settings


class OperationRunnerTests(unittest.TestCase):
    def test_operation_validation(self):
        settings = {"tools": {"nfo_generator_path": "/bin/echo"}}
        ok, message = validate_operation_request("generate_nfo", "/tmp/album", settings)
        self.assertTrue(ok)
        self.assertEqual(message, "ok")

        ok, message = validate_operation_request("generate_nfo", "", settings)
        self.assertFalse(ok)
        self.assertIn("Target", message)

        ok, message = validate_operation_request("generate_sfv", "/tmp/album", settings)
        self.assertFalse(ok)
        self.assertIn("not configured", message)

    def test_prepare_command(self):
        settings = {"tools": {"nfo_generator_path": "/tools/nfo", "file_manager_path": "open-folder"}}
        self.assertEqual(prepare_command("generate_nfo", "/tmp/album", settings), ["/tools/nfo", "/tmp/album"])
        self.assertEqual(
            prepare_command("open_album_folder", "/tmp/album", settings),
            ["open-folder", "/tmp/album"],
        )

    def test_execution_wrapper_and_history(self):
        with tempfile.TemporaryDirectory() as tmp:
            history_path = Path(tmp) / "operation_history.json"

            def runner(command, capture_output, text, timeout):
                self.assertEqual(command, ["/bin/echo", "/tmp/album"])
                return subprocess.CompletedProcess(command, 0, stdout="done", stderr="")

            result = run_operation(
                "generate_nfo",
                "/tmp/album",
                {"tools": {"nfo_generator_path": "/bin/echo"}},
                history_path,
                runner=runner,
            )
            history = load_operation_history(history_path)

        self.assertEqual(result["result"], "success")
        self.assertEqual(history["history"][0]["operation"], "generate_nfo")

    def test_album_operation_invocation_records_target(self):
        with tempfile.TemporaryDirectory() as tmp:
            album = Path(tmp) / "Artist - Album"
            album.mkdir()
            history_path = Path(tmp) / "operation_history.json"

            def runner(command, capture_output, text, timeout):
                self.assertEqual(command, ["/bin/echo", str(album)])
                return subprocess.CompletedProcess(command, 0, stdout="album ok", stderr="")

            result = run_operation(
                "validate_album",
                str(album),
                {"tools": {"flac_validator_path": "/bin/echo"}},
                history_path,
                runner=runner,
            )
            history = load_operation_history(history_path)

        self.assertEqual(result["result"], "success")
        self.assertEqual(result["message"], "album ok")
        self.assertEqual(history["history"][0]["target"], str(album))

    def test_revalidate_uses_validator_tool_and_records_distinct_operation(self):
        with tempfile.TemporaryDirectory() as tmp:
            album = Path(tmp) / "Artist - Album"
            album.mkdir()
            history_path = Path(tmp) / "operation_history.json"

            def runner(command, capture_output, text, timeout):
                self.assertEqual(command, ["/bin/echo", str(album)])
                return subprocess.CompletedProcess(command, 0, stdout="validated again", stderr="")

            result = run_operation(
                "revalidate_album",
                str(album),
                {"tools": {"flac_validator_path": "/bin/echo"}},
                history_path,
                runner=runner,
            )
            history = load_operation_history(history_path)

        self.assertEqual(result["result"], "success")
        self.assertEqual(result["operation"], "revalidate_album")
        self.assertEqual(history["history"][0]["operation"], "revalidate_album")

    def test_failure_handling_records_history(self):
        with tempfile.TemporaryDirectory() as tmp:
            history_path = Path(tmp) / "operation_history.json"
            result = run_operation("validate_album", "/tmp/album", {"tools": {}}, history_path)
            history = load_operation_history(history_path)

        self.assertEqual(result["result"], "failure")
        self.assertEqual(result["message"], "FLAC Validator is not configured.")
        self.assertEqual(result["guidance"]["suggested_action"], "Open Settings > Tools and set Validator.")
        self.assertEqual(history["history"][0]["result"], "failure")

    def test_permission_failure_records_actionable_guidance(self):
        with tempfile.TemporaryDirectory() as tmp:
            history_path = Path(tmp) / "operation_history.json"
            result = run_operation(
                "validate_album",
                "/tmp/album",
                {"tools": {"flac_validator_path": "/tools/validator"}},
                history_path,
                runner=Mock(side_effect=PermissionError("Permission denied")),
            )

        self.assertEqual(result["result"], "failure")
        self.assertIn("FLAC Validator", result["message"])
        self.assertIn("Permission denied", result["message"])
        self.assertIn("Command attempted: /tools/validator /tmp/album", result["message"])
        self.assertEqual(result["guidance"]["settings_route"], "settings.tools")
        self.assertEqual(result["guidance"]["action_label"], "Open Settings")

    def test_settings_integration(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "settings.json"
            settings = load_audio_division_settings(path)
            settings["tools"]["flac_validator_path"] = "/tools/validator"
            save_audio_division_settings(path, settings)
            loaded = load_audio_division_settings(path)

        self.assertEqual(loaded["tools"]["flac_validator_path"], "/tools/validator")
        self.assertEqual(loaded["tools"]["file_manager_path"], "xdg-open")

    def test_dashboard_recent_operations(self):
        summary = compute_dashboard_summary(
            {"summary": {"total_albums": 0, "state_evidence_counts": {}}},
            {"summary": {"confidence_counts": {}}, "unresolved": []},
            {"summary": {}},
            {"history": [{"timestamp": "2026-06-17T12:00:00", "operation": "generate_nfo", "result": "success"}]},
        )
        self.assertEqual(summary["recent_operations"]["operation_count"], 1)
        self.assertEqual(summary["recent_operations"]["items"][0]["operation"], "generate_nfo")


if __name__ == "__main__":
    unittest.main()
