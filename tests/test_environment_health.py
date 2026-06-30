import tempfile
import unittest
from pathlib import Path

from audio_division.environment_health import (
    STATUS_FAIL,
    STATUS_PASS,
    STATUS_WARNING,
    environment_health_report,
)


class EnvironmentHealthTests(unittest.TestCase):
    def test_healthy_environment_passes_core_checks(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            archive = root / "archive"
            incoming = root / "incoming"
            reports = root / "reports"
            data = root / "data"
            for path in (archive, incoming, reports, data / "artists"):
                path.mkdir(parents=True)
            (data / "metadata_cache.json").write_text("{}", encoding="utf-8")
            (data / "validated_albums.json").write_text("{}", encoding="utf-8")
            (data / "artists" / "Example.txt").write_text("# source: https://www.deezer.com/artist/1\n", encoding="utf-8")
            audio = root / "audio-division"
            validator = root / "validator"
            manager = root / "file-manager"
            for tool in (audio, validator, manager):
                tool.write_text("#!/bin/sh\n", encoding="utf-8")

            report = environment_health_report(
                {
                    "archive_paths": {"main_archive_root": str(archive), "incoming_root": str(incoming)},
                    "reports": {"reports_directory": str(reports)},
                    "metadata": {"metadata_cache_path": str(data / "metadata_cache.json")},
                    "validator": {"validated_index_path": str(data / "validated_albums.json")},
                    "tools": {
                        "audio_division_path": str(audio),
                        "flac_validator_path": str(validator),
                        "file_manager_path": str(manager),
                    },
                },
                base_dir=root,
                data_dir=data,
                path_values="",
            )

        self.assertEqual(report.status, STATUS_PASS)
        self.assertEqual(report.summary[STATUS_FAIL], 0)
        self.assertTrue(all(check.evidence for check in report.checks))
        self.assertTrue(all(check.suggested_action for check in report.checks))

    def test_missing_required_settings_fail(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            report = environment_health_report(
                {"tools": {}},
                base_dir=root / "hub" / "app",
                data_dir=root / "data",
                home_dir=root / "home",
                path_values="",
            )

        names = {check.name: check for check in report.checks}
        self.assertEqual(report.status, STATUS_FAIL)
        self.assertEqual(names["Required setting: Main Archive Root"].status, STATUS_FAIL)
        self.assertEqual(names["Audio Division available"].status, STATUS_FAIL)

    def test_missing_local_indexes_are_warnings(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            archive = root / "archive"
            incoming = root / "incoming"
            reports = root / "reports"
            for path in (archive, incoming, reports):
                path.mkdir()
            tool = root / "tool"
            tool.write_text("#!/bin/sh\n", encoding="utf-8")
            report = environment_health_report(
                {
                    "archive_paths": {"main_archive_root": str(archive), "incoming_root": str(incoming)},
                    "reports": {"reports_directory": str(reports)},
                    "metadata": {"metadata_cache_path": str(root / "data" / "metadata_cache.json")},
                    "validator": {"validated_index_path": str(root / "data" / "validated_albums.json")},
                    "tools": {
                        "audio_division_path": str(tool),
                        "flac_validator_path": str(tool),
                        "file_manager_path": str(tool),
                    },
                },
                base_dir=root,
                data_dir=root / "data",
                path_values="",
            )

        checks = {check.name: check for check in report.checks}
        self.assertEqual(checks["Metadata cache readable"].status, STATUS_WARNING)
        self.assertEqual(checks["Validation index readable"].status, STATUS_WARNING)

    def test_report_serializes_to_structured_dict(self):
        report = environment_health_report({}, base_dir=Path("/tmp"), data_dir=Path("/tmp/data"), path_values="")
        payload = report.to_dict()

        self.assertIn("status", payload)
        self.assertIn("summary", payload)
        self.assertIn("checks", payload)
        self.assertIn("severity", payload["checks"][0])


if __name__ == "__main__":
    unittest.main()
