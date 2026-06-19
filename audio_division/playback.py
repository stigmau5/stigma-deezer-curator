from __future__ import annotations

import shlex
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable

from audio_division.operation_runner import record_operation_history

PLAYBACK_OPERATIONS = {"play_album", "play_playlist"}
PLAYLIST_SUFFIXES = (".m3u8", ".m3u")


@dataclass(frozen=True)
class PlayerProvider:
    id: str
    executable: str
    args: tuple[str, ...] = ()

    def command(self, target: Path) -> list[str]:
        return [self.executable, *self.args, str(target)]


@dataclass(frozen=True)
class PlaybackTarget:
    path: Path
    kind: str
    source: str


def player_provider_from_settings(settings: dict[str, Any]) -> PlayerProvider:
    playback = settings.get("playback", {}) if isinstance(settings.get("playback"), dict) else {}
    provider_id = str(playback.get("provider") or "mpv").strip() or "mpv"
    executable = str(playback.get("player_path") or provider_id).strip()
    args = tuple(shlex.split(str(playback.get("player_args") or "")))
    return PlayerProvider(id=provider_id, executable=executable, args=args)


def first_playlist(album_path: Path) -> Path | None:
    if not album_path.exists() or not album_path.is_dir():
        return None
    playlists = [
        item
        for item in album_path.iterdir()
        if item.is_file() and item.suffix.lower() in PLAYLIST_SUFFIXES
    ]
    if not playlists:
        return None
    return sorted(playlists, key=lambda path: (_playlist_rank(path), path.name.lower()))[0]


def playback_target(operation_id: str, archive_path: str | Path) -> tuple[PlaybackTarget | None, str]:
    if operation_id not in PLAYBACK_OPERATIONS:
        return None, f"Unknown playback operation: {operation_id}"
    if not archive_path:
        return None, "Archive path is required"

    path = Path(archive_path)
    if not path.exists():
        return None, "Archive path does not exist"

    if path.is_file() and path.suffix.lower() in PLAYLIST_SUFFIXES:
        return PlaybackTarget(path=path, kind="playlist", source="explicit_playlist"), "ok"
    if not path.is_dir():
        return None, "Archive path must be an album folder or playlist"

    playlist = first_playlist(path)
    if operation_id == "play_playlist":
        if not playlist:
            return None, "No playlist available for this album"
        return PlaybackTarget(path=playlist, kind="playlist", source="album_playlist"), "ok"

    if playlist:
        return PlaybackTarget(path=playlist, kind="playlist", source="album_playlist"), "ok"
    return PlaybackTarget(path=path, kind="album_folder", source="album_folder"), "ok"


def prepare_playback_command(operation_id: str, archive_path: str | Path, settings: dict[str, Any]) -> tuple[list[str], str]:
    provider = player_provider_from_settings(settings)
    if not provider.executable:
        return [], "Player path is not configured"
    target, message = playback_target(operation_id, archive_path)
    if not target:
        return [], message
    return provider.command(target.path), "ok"


def run_playback_action(
    operation_id: str,
    archive_path: str | Path,
    settings: dict[str, Any],
    history_path: Path,
    *,
    runner: Callable[..., Any] = subprocess.Popen,
) -> dict[str, Any]:
    command, message = prepare_playback_command(operation_id, archive_path, settings)
    if not command:
        result = _result(operation_id, str(archive_path or ""), False, message)
        record_operation_history(history_path, result)
        return result

    try:
        process = runner(command)
        pid = getattr(process, "pid", "")
        detail = f"launched pid {pid}" if pid else "launched"
        result = _result(operation_id, command[-1], True, detail)
    except Exception as exc:
        result = _result(operation_id, command[-1], False, str(exc))
    record_operation_history(history_path, result)
    return result


def playback_summary(details: dict[str, Any]) -> dict[str, Any]:
    archive_path = details.get("archive_path", "")
    target, message = playback_target("play_album", archive_path)
    playlist, playlist_message = playback_target("play_playlist", archive_path)
    return {
        "album_available": target is not None,
        "album_target": str(target.path) if target else "",
        "album_source": target.source if target else "",
        "album_message": message,
        "playlist_available": playlist is not None,
        "playlist_target": str(playlist.path) if playlist else "",
        "playlist_message": playlist_message,
    }


def _playlist_rank(path: Path) -> int:
    try:
        return PLAYLIST_SUFFIXES.index(path.suffix.lower())
    except ValueError:
        return len(PLAYLIST_SUFFIXES)


def _result(operation_id: str, target: str, success: bool, message: str) -> dict[str, Any]:
    from datetime import datetime

    return {
        "timestamp": datetime.now().isoformat(timespec="seconds"),
        "operation": operation_id,
        "target": target,
        "result": "success" if success else "failure",
        "message": message,
    }
