from __future__ import annotations

import json
import subprocess
from datetime import datetime
from pathlib import Path
from typing import Any, Callable

from audio_division.action_routing import command_failure_guidance, missing_tool_guidance
from audio_division.operation_runner import record_operation_history
from curator.atomic import atomic_write_text
from curator.identity import build_identity_registry, write_identity_registry, write_identity_reports
from curator.lifecycle import build_lifecycle_registry, write_registry, write_reports
from curator.validator_evidence import collect_validation_evidence, parse_validation_log, write_validation_reports


VALIDATOR_RUNS_SCHEMA = 1
VALIDATOR_LOG_NAME = "STIGMA_VALIDATED.txt"


def run_validator_for_release(
    release: dict[str, Any],
    settings: dict[str, Any],
    data_dir: Path,
    reports_dir: Path | None = None,
    history_path: Path | None = None,
    *,
    runner: Callable[..., Any] = subprocess.run,
) -> dict[str, Any]:
    folder = Path(str(release.get("folder") or release.get("archive_path") or "")).expanduser()
    validator = str(settings.get("tools", {}).get("flac_validator_path") or "").strip()
    started_at = datetime.now().isoformat(timespec="seconds")

    if not folder:
        return _failure("Release folder is required.", folder="", started_at=started_at)
    if not folder.exists() or not folder.is_dir():
        return _failure("Release folder does not exist.", folder=str(folder), started_at=started_at)
    if not validator:
        guidance = missing_tool_guidance("validator")
        return _failure(
            f"{guidance.message} {guidance.suggested_action}",
            folder=str(folder),
            started_at=started_at,
            guidance=guidance.to_dict(),
        )

    command = [validator, str(folder)]
    guidance = None
    try:
        completed = runner(command, capture_output=True, text=True, timeout=3600)
        exit_code = int(getattr(completed, "returncode", 1))
        stdout = str(getattr(completed, "stdout", "") or "")
        stderr = str(getattr(completed, "stderr", "") or "")
        if exit_code != 0 and "permission denied" in (stdout + stderr).lower():
            guidance = command_failure_guidance("validator", command, stdout or stderr)
            stderr = guidance.message
    except Exception as exc:
        exit_code = 1
        stdout = ""
        guidance = command_failure_guidance("validator", command, exc)
        stderr = guidance.message

    finished_at = datetime.now().isoformat(timespec="seconds")
    log_path = folder / VALIDATOR_LOG_NAME
    log_evidence = parse_validation_log(log_path) if log_path.exists() else None
    success = exit_code == 0
    album_id = str(
        release.get("deezer_album_id")
        or release.get("album_id")
        or (log_evidence or {}).get("album_id")
        or ""
    )

    if success and album_id:
        _record_validated_album(
            _resolve_data_path(settings, data_dir, "validator", "validated_index_path", "validated_albums.json"),
            album_id,
            release=release,
            folder=folder,
            log_path=log_path if log_path.exists() else None,
            log_evidence=log_evidence or {},
            validated_at=(log_evidence or {}).get("validated_at") or finished_at,
        )

    refreshed = _refresh_validation_indexes(
        data_dir=data_dir,
        reports_dir=reports_dir or _reports_dir(settings, data_dir),
        settings=settings,
        release_folder=folder,
    )

    result = {
        "operation": "validate_downloaded_release",
        "target": str(folder),
        "command": command,
        "exit_code": exit_code,
        "result": "success" if success else "failure",
        "started_at": started_at,
        "finished_at": finished_at,
        "stdout": stdout,
        "stderr": stderr,
        "log_path": str(log_path) if log_path.exists() else "",
        "validation_evidence": log_evidence or {},
        "album_id": album_id,
        "refreshed": refreshed,
    }
    if guidance is not None:
        result["guidance"] = guidance.to_dict()
    _record_validator_run(data_dir / "validator_runs.json", result)
    if history_path is not None:
        record_operation_history(
            history_path,
            {
                "timestamp": finished_at,
                "operation": "validate_downloaded_release",
                "target": str(folder),
                "result": result["result"],
                "message": _summary_message(result),
            },
        )
    return result


def _failure(message: str, *, folder: str, started_at: str, guidance: dict[str, Any] | None = None) -> dict[str, Any]:
    finished_at = datetime.now().isoformat(timespec="seconds")
    result = {
        "operation": "validate_downloaded_release",
        "target": folder,
        "command": [],
        "exit_code": 1,
        "result": "failure",
        "started_at": started_at,
        "finished_at": finished_at,
        "stdout": "",
        "stderr": message,
        "log_path": "",
        "validation_evidence": {},
        "album_id": "",
        "refreshed": {},
    }
    if guidance:
        result["guidance"] = guidance
    return result


def _record_validated_album(
    path: Path,
    album_id: str,
    *,
    release: dict[str, Any],
    folder: Path,
    log_path: Path | None,
    log_evidence: dict[str, Any],
    validated_at: str,
) -> None:
    data = _load_json(path)
    payload = dict(data.get(album_id, {})) if isinstance(data.get(album_id), dict) else {}
    payload.update(
        {
            "folder": folder.name,
            "source": "stigma-flac-validator",
            "validated_at": validated_at,
            "validation_log_path": str(log_path) if log_path else payload.get("validation_log_path", ""),
        }
    )
    if log_evidence.get("track_count") is not None:
        payload["tracks"] = log_evidence.get("track_count")
    if release.get("artist"):
        payload["artist"] = release.get("artist")
    if release.get("album") or release.get("title"):
        payload["title"] = release.get("album") or release.get("title")
    data[album_id] = payload
    path.parent.mkdir(parents=True, exist_ok=True)
    atomic_write_text(path, json.dumps(data, ensure_ascii=False, indent=2, sort_keys=True) + "\n")


def _refresh_validation_indexes(
    *,
    data_dir: Path,
    reports_dir: Path,
    settings: dict[str, Any],
    release_folder: Path,
) -> dict[str, Any]:
    evidence_roots = _validation_evidence_roots(settings, data_dir, release_folder)
    evidence = collect_validation_evidence(data_dir, evidence_roots)
    lifecycle = build_lifecycle_registry(data_dir, validation_evidence=evidence)
    write_registry(lifecycle, data_dir / "lifecycle_registry.json")
    write_reports(lifecycle, reports_dir)
    write_validation_reports(lifecycle, reports_dir)

    identity = build_identity_registry(lifecycle)
    write_identity_registry(identity, data_dir / "identity_registry.json")
    write_identity_reports(identity, reports_dir)
    return {
        "validation_logs_found": evidence.get("summary", {}).get("validation_logs_found", 0),
        "lifecycle_albums": len(lifecycle.get("albums", [])),
        "identity_releases": len(identity.get("releases", [])),
    }


def _validation_evidence_roots(settings: dict[str, Any], data_dir: Path, release_folder: Path) -> list[Path]:
    roots = [release_folder]
    configured = settings.get("validator", {}).get("validation_log_root")
    if configured:
        roots.append(_resolve_path(str(configured), data_dir.parent))
    unique = []
    seen = set()
    for root in roots:
        key = str(root)
        if key not in seen:
            seen.add(key)
            unique.append(root)
    return unique


def _resolve_data_path(settings: dict[str, Any], data_dir: Path, section: str, key: str, fallback: str) -> Path:
    configured = str(settings.get(section, {}).get(key) or fallback)
    return _resolve_path(configured, data_dir.parent)


def _reports_dir(settings: dict[str, Any], data_dir: Path) -> Path:
    configured = str(settings.get("reports", {}).get("reports_directory") or "reports")
    return _resolve_path(configured, data_dir.parent)


def _resolve_path(value: str, base: Path) -> Path:
    path = Path(value).expanduser()
    return path if path.is_absolute() else base / path


def _record_validator_run(path: Path, result: dict[str, Any]) -> None:
    data = _load_json(path)
    runs = data.get("runs", []) if isinstance(data.get("runs"), list) else []
    runs.insert(0, result)
    normalized = {"schema": VALIDATOR_RUNS_SCHEMA, "runs": runs[:200]}
    path.parent.mkdir(parents=True, exist_ok=True)
    atomic_write_text(path, json.dumps(normalized, ensure_ascii=False, indent=2, sort_keys=True) + "\n")


def _summary_message(result: dict[str, Any]) -> str:
    if result.get("result") == "success":
        return f"Validator completed for {Path(str(result.get('target') or '')).name}"
    return str(result.get("stderr") or f"Validator failed with exit code {result.get('exit_code')}")


def _load_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}
    return data if isinstance(data, dict) else {}
