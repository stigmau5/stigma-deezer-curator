from __future__ import annotations

import json
import re
from collections import Counter
from datetime import datetime
from pathlib import Path
from typing import Any

from audio_division.album_truth import album_truth
from audio_division.archive_registry import AUDIO_SUFFIXES
from audio_division.artifacts import ARTIFACT_TYPES, detect_album_artifacts
from curator.atomic import atomic_write_text

ALBUM_CATEGORIES = {"Albums", "EPs", "Singles", "Live"}
DISC_FOLDER_PATTERN = re.compile(r"^(cd|disc)[ _-]?\d+$", re.IGNORECASE)
REPORT_LIMIT = 200


def reconcile_archive(archive_root: Path, archive_registry: dict[str, Any]) -> dict[str, Any]:
    reality_roots = discover_album_roots(archive_root)
    reality_entries = {str(path): reality_album_entry(path, archive_root) for path in reality_roots}
    registry_entries = {
        str(row.get("archive_path")): row
        for row in archive_registry.get("albums", [])
        if row.get("archive_path")
    }

    reality_paths = set(reality_entries)
    registry_paths = set(registry_entries)
    found_paths = sorted(reality_paths & registry_paths)
    missing_paths = sorted(reality_paths - registry_paths)
    added_paths = sorted(registry_paths - reality_paths)
    changed = changed_entries(found_paths, reality_entries, registry_entries)
    disc_rows = disc_folder_registry_rows(registry_entries)

    artifact_counts = artifact_summary(reality_entries.values())
    health = health_summary(missing_paths, added_paths, changed, disc_rows, archive_root)
    return {
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "archive_root": str(archive_root),
        "summary": {
            "albums_found": len(found_paths),
            "albums_missing": len(missing_paths),
            "albums_added": len(added_paths),
            "albums_changed": len(changed),
            "disc_folder_album_rows": len(disc_rows),
        },
        "artifact_counts": artifact_counts,
        "health": health,
        "albums_found": [reality_entries[path] for path in found_paths[:REPORT_LIMIT]],
        "albums_missing": [reality_entries[path] for path in missing_paths[:REPORT_LIMIT]],
        "albums_added": [registry_entry_summary(registry_entries[path], archive_root) for path in added_paths[:REPORT_LIMIT]],
        "albums_changed": changed[:REPORT_LIMIT],
        "disc_folder_album_rows": disc_rows[:REPORT_LIMIT],
    }


def discover_album_roots(archive_root: Path) -> list[Path]:
    if not archive_root.exists() or not archive_root.is_dir():
        return []
    roots = []
    for path in archive_root.rglob("*"):
        if path.is_dir() and is_album_root(path, archive_root):
            roots.append(path)
    return sorted(roots)


def is_album_root(path: Path, archive_root: Path) -> bool:
    if is_disc_folder(path):
        return False
    try:
        parts = path.relative_to(archive_root).parts
    except ValueError:
        return False
    category_indexes = [index for index, part in enumerate(parts) if part in ALBUM_CATEGORIES]
    if not category_indexes:
        return False
    category_index = category_indexes[-1]
    if len(parts) != category_index + 2:
        return False
    return has_album_evidence(path)


def has_album_evidence(path: Path) -> bool:
    try:
        children = list(path.iterdir())
    except OSError:
        return False
    return (
        has_direct_audio(path)
        or has_album_artifacts(path)
        or any(child.is_dir() and is_disc_folder(child) and has_direct_audio(child) for child in children)
    )


def is_disc_folder(path: Path) -> bool:
    return bool(DISC_FOLDER_PATTERN.match(path.name.strip()))


def reality_album_entry(album_path: Path, archive_root: Path) -> dict[str, Any]:
    artifacts = detect_album_artifacts(album_path)
    truth = album_truth(archive_path=album_path, registry_artifacts=artifacts)
    return {
        "name": album_path.name,
        "archive_path": str(album_path),
        "relative_path": relative_path(album_path, archive_root),
        "track_count": count_album_tracks(album_path),
        "disc_folders": [child.name for child in disc_folders(album_path)],
        "artifacts": artifacts,
        "album_truth": truth.to_dict(),
    }


def changed_entries(
    found_paths: list[str],
    reality_entries: dict[str, dict[str, Any]],
    registry_entries: dict[str, dict[str, Any]],
) -> list[dict[str, Any]]:
    changed = []
    for path in found_paths:
        reality = reality_entries[path]
        registry = registry_entries[path]
        differences = {}
        if int(reality.get("track_count") or 0) != int(registry.get("track_count") or 0):
            differences["track_count"] = {
                "filesystem": int(reality.get("track_count") or 0),
                "registry": int(registry.get("track_count") or 0),
            }
        for artifact in ARTIFACT_TYPES:
            key = "validation_log" if artifact == "validation_log" else artifact
            filesystem_value = bool(reality.get("artifacts", {}).get(key))
            registry_value = bool(registry.get("artifacts", {}).get(key))
            if filesystem_value != registry_value:
                differences[key] = {"filesystem": filesystem_value, "registry": registry_value}
        if differences:
            changed.append(
                {
                    "archive_path": path,
                    "relative_path": reality.get("relative_path", path),
                    "differences": differences,
                }
            )
    return changed


def disc_folder_registry_rows(registry_entries: dict[str, dict[str, Any]]) -> list[dict[str, Any]]:
    rows = []
    registry_paths = set(registry_entries)
    for path_text, row in registry_entries.items():
        path = Path(path_text)
        if not is_disc_folder(path):
            continue
        parent = path.parent
        rows.append(
            {
                "archive_path": path_text,
                "relative_path": row.get("relative_path", path_text),
                "disc_folder": path.name,
                "album_root": str(parent),
                "album_root_in_registry": str(parent) in registry_paths,
                "registry_artifacts": row.get("artifacts", {}),
            }
        )
    return sorted(rows, key=lambda item: item["archive_path"])


def artifact_summary(entries: Any) -> dict[str, Any]:
    counts = Counter()
    for entry in entries:
        artifacts = entry.get("artifacts", {})
        for artifact in ARTIFACT_TYPES:
            if artifacts.get(artifact):
                counts[f"with_{artifact}"] += 1
            else:
                counts[f"missing_{artifact}"] += 1
    return dict(counts)


def health_summary(
    missing_paths: list[str],
    added_paths: list[str],
    changed: list[dict[str, Any]],
    disc_rows: list[dict[str, Any]],
    archive_root: Path,
) -> dict[str, Any]:
    failures = []
    warnings = []
    if not archive_root.exists() or not archive_root.is_dir():
        failures.append("archive_root_unavailable")
    if missing_paths:
        warnings.append("filesystem_album_roots_missing_from_registry")
    if added_paths:
        warnings.append("registry_entries_not_album_roots")
    if changed:
        warnings.append("registry_entries_differ_from_filesystem")
    if disc_rows:
        warnings.append("disc_folders_projected_as_albums")
    return {
        "state": "FAILURES" if failures else ("WARNINGS" if warnings else "HEALTHY"),
        "healthy": not failures and not warnings,
        "warnings": warnings,
        "failures": failures,
    }


def render_archive_reconciliation_report(report: dict[str, Any]) -> str:
    summary = report.get("summary", {})
    health = report.get("health", {})
    lines = [
        "# Archive Reconciliation Report",
        "",
        "Read-only comparison of filesystem reality, Archive Registry, and AlbumTruth.",
        "",
        f"Generated: `{report.get('generated_at', 'unknown')}`",
        f"Archive root: `{escape(report.get('archive_root'))}`",
        "",
        "## Health",
        "",
        f"- State: `{health.get('state', 'UNKNOWN')}`",
        f"- Healthy: `{health.get('healthy', False)}`",
        f"- Warnings: `{', '.join(health.get('warnings', [])) or 'none'}`",
        f"- Failures: `{', '.join(health.get('failures', [])) or 'none'}`",
        "",
        "## Summary",
        "",
        f"- Albums Found: `{summary.get('albums_found', 0)}`",
        f"- Albums Missing: `{summary.get('albums_missing', 0)}`",
        f"- Albums Added: `{summary.get('albums_added', 0)}`",
        f"- Albums Changed: `{summary.get('albums_changed', 0)}`",
        f"- Disc folders represented as albums: `{summary.get('disc_folder_album_rows', 0)}`",
        "",
    ]
    lines.extend(render_artifact_counts(report.get("artifact_counts", {})))
    lines.extend(render_album_table("Albums Missing From Registry", report.get("albums_missing", [])))
    lines.extend(render_album_table("Registry Entries Not Album Roots", report.get("albums_added", [])))
    lines.extend(render_changed_table(report.get("albums_changed", [])))
    lines.extend(render_disc_table(report.get("disc_folder_album_rows", [])))
    return "\n".join(lines) + "\n"


def render_artifact_counts(counts: dict[str, Any]) -> list[str]:
    labels = {
        "nfo": "NFO",
        "sfv": "SFV",
        "playlist": "Playlist",
        "artwork": "Artwork",
        "validation_log": "Validation",
    }
    lines = ["## Artifact Counts", "", "| Artifact | Present | Missing |", "| --- | ---: | ---: |"]
    for artifact in ARTIFACT_TYPES:
        lines.append(
            f"| {labels[artifact]} | {counts.get(f'with_{artifact}', 0)} | {counts.get(f'missing_{artifact}', 0)} |"
        )
    lines.append("")
    return lines


def render_album_table(title: str, rows: list[dict[str, Any]]) -> list[str]:
    lines = [f"## {title}", "", "| Album | Tracks | Path |", "| --- | ---: | --- |"]
    if not rows:
        lines.append("| none | 0 |  |")
    for row in rows:
        lines.append(
            f"| {escape(row.get('name'))} | {row.get('track_count', '')} | `{escape(row.get('relative_path') or row.get('archive_path'))}` |"
        )
    lines.append("")
    return lines


def render_changed_table(rows: list[dict[str, Any]]) -> list[str]:
    lines = ["## Albums Changed", "", "| Path | Differences |", "| --- | --- |"]
    if not rows:
        lines.append("| none |  |")
    for row in rows:
        differences = ", ".join(row.get("differences", {}).keys())
        lines.append(f"| `{escape(row.get('relative_path') or row.get('archive_path'))}` | {escape(differences)} |")
    lines.append("")
    return lines


def render_disc_table(rows: list[dict[str, Any]]) -> list[str]:
    lines = ["## Albums Incorrectly Represented By Disc Folders", "", "| Disc Row | Album Root | Root In Registry |", "| --- | --- | --- |"]
    if not rows:
        lines.append("| none |  |  |")
    for row in rows:
        lines.append(
            f"| `{escape(row.get('relative_path'))}` | `{escape(row.get('album_root'))}` | {row.get('album_root_in_registry')} |"
        )
    lines.append("")
    return lines


def write_archive_reconciliation_report(report: dict[str, Any], reports_dir: Path) -> None:
    reports_dir.mkdir(parents=True, exist_ok=True)
    atomic_write_text(reports_dir / "archive_reconciliation_report.md", render_archive_reconciliation_report(report))


def registry_entry_summary(row: dict[str, Any], archive_root: Path) -> dict[str, Any]:
    path = Path(row.get("archive_path", ""))
    return {
        "name": row.get("name") or path.name,
        "archive_path": str(path),
        "relative_path": row.get("relative_path") or relative_path(path, archive_root),
        "track_count": row.get("track_count", ""),
        "artifacts": row.get("artifacts", {}),
    }


def has_direct_audio(path: Path) -> bool:
    try:
        return any(item.is_file() and item.suffix.lower() in AUDIO_SUFFIXES for item in path.iterdir())
    except OSError:
        return False


def has_album_artifacts(path: Path) -> bool:
    artifacts = detect_album_artifacts(path)
    return any(artifacts.get(name) for name in ARTIFACT_TYPES)


def disc_folders(path: Path) -> list[Path]:
    try:
        return sorted(child for child in path.iterdir() if child.is_dir() and is_disc_folder(child))
    except OSError:
        return []


def count_album_tracks(album_path: Path) -> int:
    total = direct_track_count(album_path)
    for disc in disc_folders(album_path):
        total += direct_track_count(disc)
    return total


def direct_track_count(path: Path) -> int:
    try:
        return sum(1 for child in path.iterdir() if child.is_file() and child.suffix.lower() in AUDIO_SUFFIXES)
    except OSError:
        return 0


def relative_path(path: Path, root: Path) -> str:
    try:
        return str(path.relative_to(root))
    except ValueError:
        return str(path)


def escape(value: Any) -> str:
    return str(value or "").replace("|", "\\|").replace("\n", " ").strip()
