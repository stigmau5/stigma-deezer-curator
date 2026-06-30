import tempfile
import unittest
from pathlib import Path

from audio_division.settings import load_audio_division_settings
from audio_division.tool_discovery import (
    TOOL_AUDIO_DIVISION,
    TOOL_VALIDATOR,
    apply_tool_discovery,
    discover_tool,
)


class ToolDiscoveryTests(unittest.TestCase):
    def test_single_audio_division_candidate_is_applied(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            tool = root / "apps" / "audio-division" / "bin" / "audio-division"
            tool.parent.mkdir(parents=True)
            tool.write_text("#!/bin/sh\n")
            settings = {"tools": {"audio_division_path": "", "flac_validator_path": ""}}

            updated = apply_tool_discovery(settings, base_dir=root / "hub" / "app", home_dir=root, path_values="")

        self.assertEqual(updated["tools"]["audio_division_path"], str(tool))

    def test_multiple_candidates_keep_manual_configuration(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            first = root / "apps" / "audio-division" / "bin" / "audio-division"
            second = root / "projects" / "audio-division" / "bin" / "audio-division"
            first.parent.mkdir(parents=True)
            second.parent.mkdir(parents=True)
            first.write_text("#!/bin/sh\n")
            second.write_text("#!/bin/sh\n")
            settings = {"tools": {"audio_division_path": ""}}

            discovery = discover_tool(
                TOOL_AUDIO_DIVISION,
                settings,
                base_dir=root / "hub" / "app",
                home_dir=root,
                path_values="",
            )
            updated = apply_tool_discovery(settings, base_dir=root / "hub" / "app", home_dir=root, path_values="")

        self.assertEqual(discovery.status, "Multiple Found")
        self.assertEqual(updated["tools"]["audio_division_path"], "")

    def test_configured_missing_tool_reports_not_found(self):
        discovery = discover_tool(
            TOOL_VALIDATOR,
            {"tools": {"flac_validator_path": "/missing/validator"}},
            base_dir=Path("/tmp/hub"),
            home_dir=Path("/tmp/home"),
            path_values="",
        )

        self.assertEqual(discovery.status, "Not Found")
        self.assertEqual(discovery.resolved_path, "")

    def test_settings_loader_preserves_legacy_tool_keys(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "data" / "audio_division_settings.json"
            path.parent.mkdir()
            path.write_text(
                '{"tools": {"nfo_generator_path": "/legacy/nfo", "sfv_generator_path": "/legacy/sfv"}}',
                encoding="utf-8",
            )

            settings = load_audio_division_settings(path)

        self.assertEqual(settings["tools"]["nfo_generator_path"], "/legacy/nfo")
        self.assertEqual(settings["tools"]["sfv_generator_path"], "/legacy/sfv")


if __name__ == "__main__":
    unittest.main()
