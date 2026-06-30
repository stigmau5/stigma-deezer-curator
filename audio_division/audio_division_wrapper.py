from __future__ import annotations

from pathlib import Path
from typing import Any, Callable

from audio_division.archive_registry import build_archive_registry, write_archive_registry
from audio_division.integration import run_audio_division_process_album
from audio_division.revalidation import revalidate_archive, write_archive_revalidation_report
from curator.lifecycle import build_lifecycle_registry, write_registry, write_reports
from curator.validator_evidence import collect_validation_evidence, write_validation_reports


def process_validated_release(
    release_folder: str | Path,
    settings: dict[str, Any],
    data_dir: Path,
    reports_dir: Path,
    history_path: Path,
    *,
    runner: Callable[..., Any] | None = None,
) -> dict[str, Any]:
    target = str(Path(release_folder).expanduser())
    process_kwargs = {"runner": runner} if runner is not None else {}
    process_result = run_audio_division_process_album(target, settings, history_path, **process_kwargs)
    if process_result.get("result") != "success":
        return {
            "result": "failure",
            "message": process_result.get("message", ""),
            "guidance": process_result.get("guidance", {}),
            "process": process_result,
            "archive_refresh": {},
            "verification": {},
            "lifecycle_update": {},
        }

    archive_refresh = refresh_archive(settings, data_dir, reports_dir)
    verification = verify_archive(archive_refresh.get("registry", {}), settings, reports_dir)
    lifecycle_update = refresh_lifecycle(settings, data_dir, reports_dir, release_folder=Path(target))
    return {
        "result": "success",
        "message": process_result.get("message", ""),
        "process": process_result,
        "archive_refresh": archive_refresh,
        "verification": verification,
        "lifecycle_update": lifecycle_update,
    }


def refresh_archive(settings: dict[str, Any], data_dir: Path, reports_dir: Path) -> dict[str, Any]:
    archive_root = _archive_root(settings)
    if not archive_root:
        return {"result": "skipped", "reason": "Main Archive Root is not configured", "registry": {}}
    registry = build_archive_registry(archive_root)
    write_archive_registry(registry, data_dir, reports_dir)
    return {
        "result": "success",
        "archive_root": str(archive_root),
        "album_folders": registry.get("summary", {}).get("album_folders", 0),
        "registry": registry,
    }


def verify_archive(registry: dict[str, Any], settings: dict[str, Any], reports_dir: Path) -> dict[str, Any]:
    archive_root = Path(str(registry.get("archive_root") or _archive_root(settings) or ""))
    if not registry or not archive_root:
        return {"result": "skipped", "reason": "Archive registry is unavailable"}
    report = revalidate_archive(registry, archive_root)
    write_archive_revalidation_report(report, reports_dir)
    summary = report.get("summary", {})
    return {
        "result": "success",
        "albums_scanned": summary.get("albums_scanned", 0),
        "healthy": summary.get("healthy", 0),
        "warnings": summary.get("warnings", 0),
        "errors": summary.get("errors", 0),
    }


def refresh_lifecycle(
    settings: dict[str, Any],
    data_dir: Path,
    reports_dir: Path,
    *,
    release_folder: Path | None = None,
) -> dict[str, Any]:
    roots = _validation_roots(settings, data_dir, release_folder)
    evidence = collect_validation_evidence(data_dir, roots)
    registry = build_lifecycle_registry(data_dir, validation_evidence=evidence)
    write_registry(registry, data_dir / "lifecycle_registry.json")
    write_reports(registry, reports_dir)
    write_validation_reports(registry, reports_dir)
    return {
        "result": "success",
        "albums": len(registry.get("albums", [])),
        "validation_logs_found": registry.get("validation_evidence_summary", {}).get("validation_logs_found", 0),
    }


def _archive_root(settings: dict[str, Any]) -> Path | None:
    value = str(settings.get("archive_paths", {}).get("main_archive_root") or "").strip()
    return Path(value).expanduser() if value else None


def _validation_roots(settings: dict[str, Any], data_dir: Path, release_folder: Path | None) -> list[Path]:
    roots: list[Path] = []
    if release_folder:
        roots.append(release_folder)
    configured = str(settings.get("validator", {}).get("validation_log_root") or "").strip()
    if configured:
        path = Path(configured).expanduser()
        roots.append(path if path.is_absolute() else data_dir.parent / path)
    unique: list[Path] = []
    seen = set()
    for root in roots:
        key = str(root)
        if key not in seen:
            seen.add(key)
            unique.append(root)
    return unique
