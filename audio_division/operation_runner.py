from __future__ import annotations

import json
import subprocess
from datetime import datetime
from pathlib import Path
from typing import Any, Callable

from audio_division.operations import default_operations
from curator.atomic import atomic_write_text

HISTORY_SCHEMA = 1
SUPPORTED_EXECUTION_OPERATIONS = {"generate_nfo", "generate_sfv", "validate_album", "open_album_folder"}


def load_operation_history(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {"schema": HISTORY_SCHEMA, "history": []}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {"schema": HISTORY_SCHEMA, "history": []}
    if not isinstance(data, dict) or not isinstance(data.get("history"), list):
        return {"schema": HISTORY_SCHEMA, "history": []}
    data.setdefault("schema", HISTORY_SCHEMA)
    return data


def save_operation_history(path: Path, history: dict[str, Any]) -> None:
    normalized = {
        "schema": HISTORY_SCHEMA,
        "history": list(history.get("history", [])),
    }
    atomic_write_text(path, json.dumps(normalized, ensure_ascii=False, indent=2, sort_keys=True) + "\n")


def record_operation_history(path: Path, entry: dict[str, Any]) -> None:
    history = load_operation_history(path)
    history["history"].insert(0, entry)
    history["history"] = history["history"][:200]
    save_operation_history(path, history)


def validate_operation_request(operation_id: str, target: str, settings: dict[str, Any]) -> tuple[bool, str]:
    operations = default_operations()
    if operation_id not in operations:
        return False, f"Unknown operation: {operation_id}"
    if operation_id not in SUPPORTED_EXECUTION_OPERATIONS:
        return False, f"Operation is not executable yet: {operation_id}"
    if not target:
        return False, "Target folder is required"
    if operation_id != "open_album_folder" and not _tool_path(operation_id, settings):
        return False, f"Tool path is not configured for {operation_id}"
    return True, "ok"


def prepare_command(operation_id: str, target: str, settings: dict[str, Any]) -> list[str]:
    if operation_id == "open_album_folder":
        opener = settings.get("tools", {}).get("file_manager_path") or "xdg-open"
        return [opener, target]
    return [_tool_path(operation_id, settings), target]


def run_operation(
    operation_id: str,
    target: str,
    settings: dict[str, Any],
    history_path: Path,
    *,
    runner: Callable[..., Any] = subprocess.run,
) -> dict[str, Any]:
    valid, message = validate_operation_request(operation_id, target, settings)
    if not valid:
        result = _result(operation_id, target, False, message)
        record_operation_history(history_path, result)
        return result

    command = prepare_command(operation_id, target, settings)
    try:
        completed = runner(command, capture_output=True, text=True, timeout=3600)
        success = completed.returncode == 0
        output = (completed.stdout or completed.stderr or "").strip()
        message = output or ("completed" if success else f"failed with exit code {completed.returncode}")
    except Exception as exc:
        success = False
        message = str(exc)

    result = _result(operation_id, target, success, message)
    record_operation_history(history_path, result)
    return result


def _tool_path(operation_id: str, settings: dict[str, Any]) -> str:
    tools = settings.get("tools", {})
    keys = {
        "generate_nfo": "nfo_generator_path",
        "generate_sfv": "sfv_generator_path",
        "validate_album": "flac_validator_path",
    }
    return str(tools.get(keys.get(operation_id, ""), "")).strip()


def _result(operation_id: str, target: str, success: bool, message: str) -> dict[str, Any]:
    return {
        "timestamp": datetime.now().isoformat(timespec="seconds"),
        "operation": operation_id,
        "target": target,
        "result": "success" if success else "failure",
        "message": message,
    }
