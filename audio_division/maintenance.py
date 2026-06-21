from __future__ import annotations

import re
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

from audio_division.library import album_archive_operation_target
from audio_division.lifecycle_state import (
    STATE_ARCHIVED,
    STATE_DOWNLOADED,
    STATE_READY_FOR_PROCESSING,
    STATE_VALIDATED,
)


MAINTENANCE_CATEGORIES = (
    ("archive_ready", "Archive Ready"),
    ("needs_validation", "Needs Validation"),
    ("needs_documentation", "Needs Documentation"),
    ("warnings", "Warnings"),
    ("needs_metadata", "Needs Metadata"),
)

MAINTENANCE_OPERATIONS = {
    "needs_validation": "validate_album",
    "needs_documentation": "generate_documentation",
}

DISC_FOLDER_PATTERN = re.compile(r"^(cd|disc)[ _-]?\d+$", re.IGNORECASE)
ALBUM_CATEGORIES = {"Albums", "EPs", "Singles", "Live"}


def maintenance_counts(albums: list[dict[str, Any]]) -> dict[str, Any]:
    total = len(albums)
    artists = {str(album.get("artist_key") or album.get("artist") or "").strip().lower() for album in albums}
    artists.discard("")
    validation_present = sum(1 for album in albums if _status(album, "validation") == "Present")
    documentation_present = sum(1 for album in albums if _documentation_present(album))
    lifecycle_counts = Counter(_pipeline_state(album) for album in albums)
    warnings = maintenance_warnings(albums)
    return {
        "albums": total,
        "artists": len(artists),
        "warnings": len(warnings),
        "validation_coverage": _percent(validation_present, total),
        "documentation_coverage": _percent(documentation_present, total),
        "downloaded": lifecycle_counts.get(STATE_DOWNLOADED, 0),
        "validated": lifecycle_counts.get(STATE_VALIDATED, 0),
        "ready_for_processing": lifecycle_counts.get(STATE_READY_FOR_PROCESSING, 0),
        "archived": lifecycle_counts.get(STATE_ARCHIVED, 0),
    }


def maintenance_summaries(albums: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [
        {"id": category_id, "name": name, "album_count": len(maintenance_albums(albums, category_id))}
        for category_id, name in MAINTENANCE_CATEGORIES
    ]


def maintenance_albums(albums: list[dict[str, Any]], category_id: str) -> list[dict[str, Any]]:
    warning_by_key = _warning_lookup(albums)
    rows = []
    for album in albums:
        warnings = warning_by_key.get(_album_key(album), [])
        if not _album_matches_category(album, category_id, warnings):
            continue
        row = dict(album)
        row["maintenance_reason"] = maintenance_reason(album, category_id, warnings)
        row["maintenance_priority"] = maintenance_priority(category_id, warnings)
        row["maintenance_warnings"] = warnings
        rows.append(row)
    return sorted(rows, key=lambda item: (_priority_sort(item), _sort_text(item.get("artist")), _sort_text(item.get("title"))))


def maintenance_warnings(albums: list[dict[str, Any]]) -> list[dict[str, Any]]:
    warnings = []
    seen_titles: dict[tuple[str, str], list[dict[str, Any]]] = defaultdict(list)
    for album in albums:
        seen_titles[(_sort_text(album.get("artist")), _normalized_title(album.get("title")))].append(album)
        path = Path(str(album.get("archive_path") or ""))
        if path.name and DISC_FOLDER_PATTERN.match(path.name):
            warnings.append(_warning(album, "unexpected_structure", "Disc folder is represented as an album."))
        elif path and not _has_album_category(path):
            warnings.append(_warning(album, "unexpected_structure", "Archive path does not match a formal album-root category."))
        metadata_status = str(album.get("metadata_status") or album.get("album_truth", {}).get("metadata_status") or "UNKNOWN")
        if metadata_status in {"MISSING", "UNKNOWN"}:
            warnings.append(_warning(album, "missing_metadata", f"Metadata status is {metadata_status}."))

    for duplicates in seen_titles.values():
        if len(duplicates) <= 1:
            continue
        for album in duplicates:
            warnings.append(_warning(album, "duplicate_album", "Artist and album title appear more than once."))
    return warnings


def grouped_warnings(albums: list[dict[str, Any]]) -> list[dict[str, Any]]:
    grouped = Counter(warning["type"] for warning in maintenance_warnings(albums))
    return [{"type": warning_type, "count": count} for warning_type, count in sorted(grouped.items())]


def maintenance_action_target(operation_id: str, album: dict[str, Any]) -> tuple[str, str, str]:
    target, reason = album_archive_operation_target(album)
    if not target:
        return operation_id, "", reason
    if operation_id == "generate_documentation":
        operation_id = documentation_operation_for_album(album)
    return operation_id, target, "ok"


def documentation_operation_for_album(album: dict[str, Any]) -> str:
    if _status(album, "nfo") != "Present":
        return "generate_nfo"
    if _status(album, "sfv") != "Present":
        return "generate_sfv"
    return "generate_nfo"


def maintenance_reason(album: dict[str, Any], category_id: str, warnings: list[dict[str, Any]] | None = None) -> str:
    if category_id == "archive_ready":
        return "Validation and documentation evidence are present."
    if category_id == "needs_validation":
        return (
            album.get("album_truth", {}).get("validation_reason")
            or album.get("album_status", {}).get("validation_reason")
            or "Validation evidence is missing."
        )
    if category_id == "needs_documentation":
        missing = [label for field, label in (("nfo", "NFO"), ("sfv", "SFV")) if _status(album, field) != "Present"]
        return f"Missing documentation: {', '.join(missing)}." if missing else "Documentation needs review."
    if category_id == "needs_metadata":
        status = album.get("metadata_status") or album.get("album_truth", {}).get("metadata_status") or "UNKNOWN"
        return f"Metadata status is {status}."
    if category_id == "warnings":
        warnings = warnings or []
        if warnings:
            return "; ".join(warning.get("message", "") for warning in warnings)
        return "Advisory warning."
    return ""


def maintenance_priority(category_id: str, warnings: list[dict[str, Any]] | None = None) -> str:
    if category_id in {"needs_validation", "warnings"}:
        return "HIGH"
    if category_id == "needs_documentation":
        return "MEDIUM"
    if category_id == "needs_metadata":
        return "LOW"
    return "INFO"


def _album_matches_category(album: dict[str, Any], category_id: str, warnings: list[dict[str, Any]]) -> bool:
    readiness = album.get("album_truth", {}).get("readiness") or album.get("archive_readiness", {}).get("state", "")
    if category_id == "archive_ready":
        return readiness == "ARCHIVE_READY"
    if category_id == "needs_validation":
        return _status(album, "validation") == "Missing"
    if category_id == "needs_documentation":
        return _status(album, "validation") == "Present" and not _documentation_present(album)
    if category_id == "warnings":
        return bool(warnings)
    if category_id == "needs_metadata":
        return str(album.get("metadata_status") or album.get("album_truth", {}).get("metadata_status") or "UNKNOWN") != "CACHED"
    return False


def _warning_lookup(albums: list[dict[str, Any]]) -> dict[str, list[dict[str, Any]]]:
    lookup: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for warning in maintenance_warnings(albums):
        lookup[warning["album_key"]].append(warning)
    return dict(lookup)


def _warning(album: dict[str, Any], warning_type: str, message: str) -> dict[str, Any]:
    return {
        "album_key": _album_key(album),
        "type": warning_type,
        "artist": album.get("artist", ""),
        "album": album.get("title") or album.get("album") or "",
        "archive_path": album.get("archive_path", ""),
        "message": message,
    }


def _status(album: dict[str, Any], field: str) -> str:
    return str(
        album.get("album_truth", {}).get("items", {}).get(field)
        or album.get("album_status", {}).get("items", {}).get(field)
        or "Unknown"
    )


def _documentation_present(album: dict[str, Any]) -> bool:
    return _status(album, "nfo") == "Present" and _status(album, "sfv") == "Present"


def _pipeline_state(album: dict[str, Any]) -> str:
    return str(album.get("pipeline_state", {}).get("state") or "UNKNOWN")


def _has_album_category(path: Path) -> bool:
    return any(part in ALBUM_CATEGORIES for part in path.parts)


def _album_key(album: dict[str, Any]) -> str:
    return str(album.get("album_id") or album.get("archive_path") or f"{album.get('artist', '')}:{album.get('title', '')}")


def _priority_sort(album: dict[str, Any]) -> int:
    order = {"HIGH": 0, "MEDIUM": 1, "LOW": 2, "INFO": 3}
    return order.get(str(album.get("maintenance_priority") or ""), 9)


def _normalized_title(value: Any) -> str:
    return " ".join(str(value or "").lower().split())


def _sort_text(value: Any) -> str:
    return str(value or "").lower()


def _percent(count: int, total: int) -> float:
    if not total:
        return 0.0
    return round((count / total) * 100, 1)
