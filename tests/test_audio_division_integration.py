import tempfile
import unittest
from pathlib import Path
from unittest.mock import Mock

from audio_division.integration import (
    AUDIO_DIVISION_OPERATION,
    audio_division_command,
    audio_division_path,
    run_audio_division_process_album,
    validate_process_album_request,
)
from audio_division.operation_runner import load_operation_history
from audio_division.processing_queue import processing_row, queue_for_processing
from audio_division.settings import load_audio_division_settings, save_audio_division_settings


class Completed:
    returncode = 0
    stdout = "processed"
    stderr = ""


class AudioDivisionIntegrationTests(unittest.TestCase):
    def settings(self):
        return {"tools": {"audio_division_path": "/usr/local/bin/stigma_audio_division"}}

    def test_settings_support_audio_division_path(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "settings.json"
            settings = load_audio_division_settings(path)
            settings["tools"]["audio_division_path"] = "/tools/stigma_audio_division"
            settings["tools"]["nfo_generator_path"] = "/tools/legacy_nfo"
            save_audio_division_settings(path, settings)
            loaded = load_audio_division_settings(path)

        self.assertEqual(loaded["tools"]["audio_division_path"], "/tools/stigma_audio_division")
        self.assertEqual(loaded["tools"]["nfo_generator_path"], "/tools/legacy_nfo")

    def test_command_generation(self):
        command = audio_division_command("/archive/Artist-Album", self.settings())

        self.assertEqual(audio_division_path(self.settings()), "/usr/local/bin/stigma_audio_division")
        self.assertEqual(command, ["/usr/local/bin/stigma_audio_division", "process-album", "/archive/Artist-Album"])

    def test_request_validation(self):
        self.assertEqual(validate_process_album_request("", self.settings()), (False, "Album folder is required"))
        self.assertEqual(
            validate_process_album_request("/archive/Album", {"tools": {}}),
            (False, "Audio Division is not configured. Open Settings > Tools and set Audio Division."),
        )
        self.assertEqual(validate_process_album_request("/archive/Album", self.settings()), (True, "ok"))

    def test_execution_wrapper_records_history(self):
        calls = []

        def runner(command, **kwargs):
            calls.append((command, kwargs))
            return Completed()

        with tempfile.TemporaryDirectory() as tmp:
            history_path = Path(tmp) / "operation_history.json"
            result = run_audio_division_process_album(
                "/archive/Artist-Album",
                self.settings(),
                history_path,
                runner=runner,
            )
            history = load_operation_history(history_path)

        self.assertEqual(calls[0][0], ["/usr/local/bin/stigma_audio_division", "process-album", "/archive/Artist-Album"])
        self.assertEqual(result["operation"], AUDIO_DIVISION_OPERATION)
        self.assertEqual(result["result"], "success")
        self.assertEqual(history["history"][0]["operation"], AUDIO_DIVISION_OPERATION)

    def test_permission_failure_names_tool_and_command(self):
        with tempfile.TemporaryDirectory() as tmp:
            history_path = Path(tmp) / "operation_history.json"
            result = run_audio_division_process_album(
                "/archive/Artist-Album",
                self.settings(),
                history_path,
                runner=Mock(side_effect=PermissionError("Permission denied")),
            )

        self.assertEqual(result["result"], "failure")
        self.assertIn("Audio Division", result["message"])
        self.assertIn("Command attempted:", result["message"])
        self.assertIn("process-album", result["message"])
        self.assertEqual(result["guidance"]["action_label"], "Open Settings")

    def test_processing_queue_state_before_execution(self):
        album = {
            "artist": "Artist",
            "title": "Album",
            "archive_path": "/archive/Artist-Album",
            "album_truth": {"processing_state": "DOWNLOADED"},
        }
        queue = queue_for_processing({"albums": {}}, album)
        row = processing_row(album, queue)

        self.assertEqual(row["current_state"], "Processing")


if __name__ == "__main__":
    unittest.main()
