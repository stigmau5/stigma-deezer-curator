from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from curator.atomic import atomic_write_text

DEFAULT_SETTINGS = {
    "archive_paths": {
        "main_archive_root": "",
        "incoming_root": "",
        "problematic_root": "",
        "needs_validation_root": "",
    },
    "validator": {
        "validated_index_path": "data/validated_albums.json",
        "validation_log_root": str(Path.home() / "StreamripDownloads"),
    },
    "metadata": {
        "metadata_cache_path": "data/metadata_cache.json",
    },
    "reports": {
        "reports_directory": "reports",
    },
    "tools": {
        "audio_division_path": "",
        "nfo_generator_path": "",
        "sfv_generator_path": "",
        "flac_validator_path": "",
        "file_manager_path": "xdg-open",
    },
    "playback": {
        "provider": "mpv",
        "player_path": "mpv",
        "player_args": "",
    },
    "ui": {
        "window_geometry": "",
        "archive_main_panes": "",
        "archive_workspace_panes": "",
        "archive_evidence_panes": "",
        "library_main_panes": "",
        "library_workspace_panes": "",
        "library_evidence_panes": "",
    },
}


def default_settings() -> dict[str, Any]:
    return json.loads(json.dumps(DEFAULT_SETTINGS))


def load_audio_division_settings(path: Path) -> dict[str, Any]:
    settings = default_settings()
    if not path.exists():
        return settings

    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return settings

    if not isinstance(data, dict):
        return settings

    for section, defaults in DEFAULT_SETTINGS.items():
        incoming = data.get(section, {})
        if not isinstance(incoming, dict):
            continue
        settings[section].update({key: str(value) for key, value in incoming.items() if key in defaults})
    return settings


def save_audio_division_settings(path: Path, settings: dict[str, Any]) -> None:
    normalized = default_settings()
    for section, defaults in DEFAULT_SETTINGS.items():
        incoming = settings.get(section, {})
        if not isinstance(incoming, dict):
            continue
        normalized[section].update({key: str(value) for key, value in incoming.items() if key in defaults})

    path.parent.mkdir(parents=True, exist_ok=True)
    atomic_write_text(path, json.dumps(normalized, ensure_ascii=False, indent=2, sort_keys=True) + "\n")
