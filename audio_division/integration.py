from __future__ import annotations

import subprocess
from datetime import datetime
from pathlib import Path
from typing import Any, Callable

from audio_division.action_routing import apply_guidance, command_failure_guidance, missing_tool_guidance
from audio_division.operation_runner import record_operation_history


AUDIO_DIVISION_OPERATION = "process_album"
AUDIO_DIVISION_SUBCOMMAND = "process-album"


def audio_division_path(settings: dict[str, Any]) -> str:
    return str(settings.get("tools", {}).get("audio_division_path", "")).strip()


def validate_process_album_request(album_path: str, settings: dict[str, Any]) -> tuple[bool, str]:
    if not str(album_path or "").strip():
        return False, "Album folder is required"
    if not audio_division_path(settings):
        guidance = missing_tool_guidance("audio_division")
        return False, f"{guidance.message} {guidance.suggested_action}"
    return True, "ok"


def audio_division_command(album_path: str, settings: dict[str, Any]) -> list[str]:
    return [audio_division_path(settings), AUDIO_DIVISION_SUBCOMMAND, str(album_path)]


def run_audio_division_process_album(
    album_path: str,
    settings: dict[str, Any],
    history_path: Path,
    *,
    runner: Callable[..., Any] = subprocess.run,
) -> dict[str, Any]:
    valid, message = validate_process_album_request(album_path, settings)
    if not valid:
        result = _result(album_path, False, message)
        if "not configured" in message:
            apply_guidance(result, missing_tool_guidance("audio_division"))
        record_operation_history(history_path, result)
        return result

    command = audio_division_command(album_path, settings)
    guidance = None
    try:
        completed = runner(command, capture_output=True, text=True, timeout=3600)
        success = completed.returncode == 0
        output = (completed.stdout or completed.stderr or "").strip()
        message = output or ("completed" if success else f"failed with exit code {completed.returncode}")
        if not success and "permission denied" in message.lower():
            guidance = command_failure_guidance("audio_division", command, message)
            message = guidance.message
    except Exception as exc:
        success = False
        guidance = command_failure_guidance("audio_division", command, exc)
        message = guidance.message

    result = _result(album_path, success, message)
    apply_guidance(result, guidance)
    record_operation_history(history_path, result)
    return result


def _result(album_path: str, success: bool, message: str) -> dict[str, Any]:
    return {
        "timestamp": datetime.now().isoformat(timespec="seconds"),
        "operation": AUDIO_DIVISION_OPERATION,
        "target": str(album_path),
        "result": "success" if success else "failure",
        "message": message,
    }
