import json
import subprocess
import tempfile
import unittest
from pathlib import Path

from audio_division.audio_division_wrapper import process_validated_release
from audio_division.operation_runner import load_operation_history


class AudioDivisionWrapperTests(unittest.TestCase):
    def test_success_refreshes_archive_verification_and_lifecycle(self):
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp)
            data_dir = project / "data"
            reports_dir = project / "reports"
            incoming = project / "incoming" / "Example-Answer-2024-FLAC-STiGMA"
            archive_root = project / "archive"
            incoming.mkdir(parents=True)
            (incoming / "STIGMA_VALIDATED.txt").write_text(
                json.dumps(
                    {
                        "album": incoming.name,
                        "validated_at": "2026-06-30T10:00:00",
                        "tracks": 1,
                        "warnings": [],
                        "completeness": {"album_id": "42", "hashes": {"01-answer.flac": "abc"}},
                    }
                ),
                encoding="utf-8",
            )
            artists = data_dir / "artists"
            artists.mkdir(parents=True)
            (artists / "Example.txt").write_text(
                "# Artist: Example\n# Albums\nhttps://www.deezer.com/album/42  # ALBUM | Answer | 2024 | 1 tracks\n",
                encoding="utf-8",
            )

            def runner(command, capture_output, text, timeout):
                self.assertEqual(command, ["/tools/audio-division", "process-album", str(incoming)])
                album = archive_root / "E" / "Example" / "Albums" / "Example-Answer-2024-FLAC-STiGMA"
                album.mkdir(parents=True)
                (album / "01-answer.flac").write_text("audio", encoding="utf-8")
                (album / "00-example-answer.nfo").write_text("nfo", encoding="utf-8")
                (album / "00-example-answer.sfv").write_text("sfv", encoding="utf-8")
                (album / "00-example-answer.m3u8").write_text("playlist", encoding="utf-8")
                (album / "STIGMA_VALIDATED.txt").write_text("validated", encoding="utf-8")
                return subprocess.CompletedProcess(command, 0, stdout="processed", stderr="")

            result = process_validated_release(
                incoming,
                {
                    "tools": {"audio_division_path": "/tools/audio-division"},
                    "archive_paths": {"main_archive_root": str(archive_root)},
                    "validator": {"validation_log_root": str(incoming)},
                },
                data_dir,
                reports_dir,
                data_dir / "operation_history.json",
                runner=runner,
            )
            archive_registry = json.loads((data_dir / "archive_registry.json").read_text(encoding="utf-8"))
            lifecycle = json.loads((data_dir / "lifecycle_registry.json").read_text(encoding="utf-8"))
            history = load_operation_history(data_dir / "operation_history.json")
            revalidation_report_exists = (reports_dir / "archive_revalidation_report.md").exists()

            self.assertEqual(result["result"], "success")
            self.assertEqual(result["archive_refresh"]["album_folders"], 1)
            self.assertEqual(result["verification"]["albums_scanned"], 1)
            self.assertEqual(result["lifecycle_update"]["validation_logs_found"], 1)
            self.assertEqual(archive_registry["summary"]["album_folders"], 1)
            self.assertTrue(lifecycle["albums"][0]["validation_evidence"]["available"])
            self.assertEqual(history["history"][0]["operation"], "process_album")
            self.assertTrue(revalidation_report_exists)

    def test_failure_returns_without_refresh_outputs(self):
        with tempfile.TemporaryDirectory() as tmp:
            project = Path(tmp)
            data_dir = project / "data"
            incoming = project / "incoming" / "Example-Answer"
            incoming.mkdir(parents=True)

            def runner(command, capture_output, text, timeout):
                return subprocess.CompletedProcess(command, 1, stdout="", stderr="failed")

            result = process_validated_release(
                incoming,
                {"tools": {"audio_division_path": "/tools/audio-division"}},
                data_dir,
                project / "reports",
                data_dir / "operation_history.json",
                runner=runner,
            )

        self.assertEqual(result["result"], "failure")
        self.assertEqual(result["archive_refresh"], {})
        self.assertFalse((data_dir / "archive_registry.json").exists())


if __name__ == "__main__":
    unittest.main()
