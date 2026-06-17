from __future__ import annotations

from datetime import datetime
from pathlib import Path
from time import monotonic
from typing import Any, Callable
from uuid import uuid4

from audio_division.library import album_archive_operation_target, album_details
from audio_division.operation_runner import run_operation, validate_operation_request
from curator.atomic import atomic_write_text

BATCH_OPERATION_CATEGORIES = {
    "missing_nfo": "generate_nfo",
    "missing_sfv": "generate_sfv",
    "missing_validation": "validate_album",
}

SUPPORTED_BATCH_OPERATIONS = ("generate_nfo", "generate_sfv", "validate_album", "open_album_folder")


def available_batch_operations(opportunities: list[dict[str, Any]]) -> dict[str, int]:
    counts = {operation: 0 for operation in SUPPORTED_BATCH_OPERATIONS}
    for opportunity in opportunities:
        operation = BATCH_OPERATION_CATEGORIES.get(opportunity.get("category"))
        if operation:
            counts[operation] += 1
    return counts


def collect_album_targets(
    operation_id: str,
    opportunities: list[dict[str, Any]],
    library: dict[str, Any],
) -> list[dict[str, Any]]:
    targets: list[dict[str, Any]] = []
    seen: set[str] = set()
    allowed_categories = {
        category for category, operation in BATCH_OPERATION_CATEGORIES.items() if operation == operation_id
    }
    if operation_id == "open_album_folder":
        allowed_categories = {str(item.get("category", "")) for item in opportunities}
    for opportunity in opportunities:
        if opportunity.get("category") not in allowed_categories:
            continue
        album_id = str(opportunity.get("album_id", ""))
        if not album_id or album_id in seen:
            continue
        album = album_details(library, album_id)
        target, reason = album_archive_operation_target(album)
        targets.append(
            {
                "album_id": album_id,
                "artist": opportunity.get("artist", ""),
                "album": opportunity.get("album", ""),
                "target": target,
                "eligible": bool(target),
                "reason": reason,
            }
        )
        seen.add(album_id)
    return targets


def validate_batch_targets(operation_id: str, targets: list[dict[str, Any]], settings: dict[str, Any]) -> list[dict[str, Any]]:
    validated = []
    for target in targets:
        if not target.get("eligible"):
            validated.append(target)
            continue
        ok, message = validate_operation_request(operation_id, target.get("target", ""), settings)
        next_target = dict(target)
        next_target["eligible"] = ok
        next_target["reason"] = message
        validated.append(next_target)
    return validated


def run_batch_operation(
    operation_id: str,
    targets: list[dict[str, Any]],
    settings: dict[str, Any],
    history_path: Path,
    *,
    batch_id: str | None = None,
    runner: Callable[..., Any] | None = None,
    progress: Callable[[dict[str, Any]], None] | None = None,
) -> dict[str, Any]:
    batch_id = batch_id or f"batch-{datetime.now().strftime('%Y%m%d%H%M%S')}-{uuid4().hex[:8]}"
    started = monotonic()
    results = []
    eligible_targets = [target for target in validate_batch_targets(operation_id, targets, settings) if target.get("eligible")]
    total = len(eligible_targets)

    for index, target in enumerate(eligible_targets, start=1):
        if progress:
            progress(_progress(batch_id, operation_id, total, index - 1, target))
        kwargs = {"batch_id": batch_id}
        if runner is not None:
            kwargs["runner"] = runner
        result = run_operation(operation_id, target["target"], settings, history_path, **kwargs)
        result.update({"album_id": target.get("album_id", ""), "artist": target.get("artist", ""), "album": target.get("album", "")})
        results.append(result)
        if progress:
            progress(_progress(batch_id, operation_id, total, index, target))

    summary = batch_summary(batch_id, operation_id, results, monotonic() - started)
    summary["skipped"] = len(targets) - total
    summary["results"] = results
    return summary


def batch_summary(batch_id: str, operation_id: str, results: list[dict[str, Any]], duration_seconds: float) -> dict[str, Any]:
    successes = sum(1 for result in results if result.get("result") == "success")
    failures = sum(1 for result in results if result.get("result") == "failure")
    return {
        "batch_id": batch_id,
        "operation": operation_id,
        "total": len(results),
        "successes": successes,
        "failures": failures,
        "duration_seconds": round(duration_seconds, 3),
    }


def render_batch_operation_report(summary: dict[str, Any]) -> str:
    lines = [
        "# Batch Operation Report",
        "",
        f"Batch ID: `{summary.get('batch_id', '')}`",
        f"Operation: `{summary.get('operation', '')}`",
        f"Total: `{summary.get('total', 0)}`",
        f"Successes: `{summary.get('successes', 0)}`",
        f"Failures: `{summary.get('failures', 0)}`",
        f"Skipped: `{summary.get('skipped', 0)}`",
        f"Duration seconds: `{summary.get('duration_seconds', 0)}`",
        "",
        "| Result | Album ID | Artist | Album | Target | Message |",
        "| --- | --- | --- | --- | --- | --- |",
    ]
    for result in summary.get("results", [])[:500]:
        lines.append(
            f"| {result.get('result', '')} | `{_escape(result.get('album_id'))}` | {_escape(result.get('artist'))} | "
            f"{_escape(result.get('album'))} | `{_escape(result.get('target'))}` | {_escape(result.get('message'))} |"
        )
    return "\n".join(lines) + "\n"


def write_batch_operation_report(summary: dict[str, Any], reports_dir: Path) -> None:
    reports_dir.mkdir(parents=True, exist_ok=True)
    atomic_write_text(reports_dir / "batch_operation_report.md", render_batch_operation_report(summary))


def _progress(batch_id: str, operation_id: str, total: int, completed: int, target: dict[str, Any]) -> dict[str, Any]:
    return {
        "batch_id": batch_id,
        "operation": operation_id,
        "total": total,
        "completed": completed,
        "current_item": target.get("album") or target.get("target", ""),
    }


def _escape(value: Any) -> str:
    return str(value or "").replace("|", "\\|").replace("\n", " ").strip()
