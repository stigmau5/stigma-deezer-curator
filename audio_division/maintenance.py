from __future__ import annotations

import re
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

from audio_division.album_truth import (
    MAINTENANCE_NEEDS_DOCUMENTATION as CATEGORY_NEEDS_DOCUMENTATION,
    MAINTENANCE_NEEDS_METADATA as CATEGORY_NEEDS_METADATA,
    MAINTENANCE_NEEDS_REVIEW as CATEGORY_NEEDS_REVIEW,
    MAINTENANCE_NEEDS_VALIDATION as CATEGORY_NEEDS_VALIDATION,
    MAINTENANCE_PRIORITIES,
    MAINTENANCE_READY as CATEGORY_READY,
    MAINTENANCE_WARNINGS as CATEGORY_WARNINGS,
    maintenance_value_from_album,
)
from audio_division.library import album_archive_operation_target
from audio_division.lifecycle_state import (
    STATE_ARCHIVED,
    STATE_DOWNLOADED,
    STATE_READY_FOR_PROCESSING,
    STATE_VALIDATED,
)


MAINTENANCE_CATEGORIES = (
    (CATEGORY_NEEDS_VALIDATION, "Needs Validation"),
    (CATEGORY_NEEDS_DOCUMENTATION, "Needs Documentation"),
    (CATEGORY_NEEDS_METADATA, "Needs Metadata"),
    (CATEGORY_NEEDS_REVIEW, "Needs Review"),
    (CATEGORY_WARNINGS, "Warnings"),
    (CATEGORY_READY, "Ready"),
)

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
    category_counts = Counter(record["maintenance_category"] for record in maintenance_records(albums))
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
        "categories": {category_id: category_counts.get(category_id, 0) for category_id, _ in MAINTENANCE_CATEGORIES},
    }


def maintenance_summaries(albums: list[dict[str, Any]]) -> list[dict[str, Any]]:
    counts = Counter(record["maintenance_category"] for record in maintenance_records(albums))
    return [{"id": category_id, "name": name, "album_count": counts.get(category_id, 0)} for category_id, name in MAINTENANCE_CATEGORIES]


def maintenance_albums(albums: list[dict[str, Any]], category_id: str) -> list[dict[str, Any]]:
    category_id = CATEGORY_READY if category_id == "archive_ready" else category_id
    return [record for record in maintenance_records(albums) if record["maintenance_category"] == category_id]


def maintenance_records(albums: list[dict[str, Any]]) -> list[dict[str, Any]]:
    warning_by_key = _warning_lookup(albums)
    rows = [maintenance_record(album, warning_by_key.get(_album_key(album), [])) for album in albums]
    return sorted(rows, key=lambda item: (_priority_sort(item), _sort_text(item.get("artist")), _sort_text(item.get("title"))))


def maintenance_record(album: dict[str, Any], warnings: list[dict[str, Any]] | None = None) -> dict[str, Any]:
    warnings = warnings or []
    warning_reason = "; ".join(item.get("message", "") for item in warnings if item.get("message"))
    state = maintenance_value_from_album(album, warning_reason)
    row = dict(album)
    row["maintenance_category"] = state.category
    row["maintenance_label"] = state.label
    row["maintenance_reason"] = state.reason
    row["maintenance_priority"] = state.priority
    row["maintenance_operation"] = state.operation
    row["maintenance_warnings"] = warnings
    return row


def maintenance_category(album: dict[str, Any], warnings: list[dict[str, Any]] | None = None) -> str:
    warnings = warnings or []
    warning_reason = "; ".join(item.get("message", "") for item in warnings if item.get("message"))
    return maintenance_value_from_album(album, warning_reason).category


def maintenance_warnings(albums: list[dict[str, Any]]) -> list[dict[str, Any]]:
    warnings = []
    seen_titles: dict[tuple[str, str], list[dict[str, Any]]] = defaultdict(list)
    for album in albums:
        seen_titles[(_sort_text(album.get("artist")), _normalized_title(album.get("title")))].append(album)
        path_text = str(album.get("archive_path") or "").strip()
        if path_text:
            path = Path(path_text)
            if path.name and DISC_FOLDER_PATTERN.match(path.name):
                warnings.append(_warning(album, "unexpected_structure", "Disc folder is represented as an album."))
            elif not _has_album_category(path):
                warnings.append(_warning(album, "unexpected_structure", "Archive path does not match a formal album-root category."))
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
    operation_id = operation_id or maintenance_operation_for_album(album)
    if operation_id == "refresh_metadata":
        album_id = str(album.get("album_id") or "").strip()
        return (operation_id, album_id, "ok") if album_id else (operation_id, "", "No album ID available for metadata refresh.")
    target, reason = album_archive_operation_target(album)
    if not target:
        return operation_id, "", reason
    if operation_id == "generate_documentation":
        operation_id = documentation_operation_for_album(album)
    return operation_id, target, "ok"


def maintenance_operation_for_album(album: dict[str, Any]) -> str:
    return str(album.get("maintenance_operation") or maintenance_value_from_album(album).operation)


def documentation_operation_for_album(album: dict[str, Any]) -> str:
    if _status(album, "nfo") != "Present":
        return "generate_nfo"
    if _status(album, "sfv") != "Present":
        return "generate_sfv"
    return "generate_nfo"


def maintenance_reason(album: dict[str, Any], category_id: str, warnings: list[dict[str, Any]] | None = None) -> str:
    state = maintenance_value_from_album(album)
    if category_id == state.category:
        return state.reason
    if category_id == CATEGORY_READY:
        return "Validation and documentation evidence are present."
    if category_id == CATEGORY_NEEDS_VALIDATION:
        return (
            album.get("album_truth", {}).get("validation_reason")
            or album.get("album_status", {}).get("validation_reason")
            or "Validation evidence is missing."
        )
    if category_id == CATEGORY_NEEDS_DOCUMENTATION:
        missing = [label for field, label in (("nfo", "NFO"), ("sfv", "SFV")) if _status(album, field) != "Present"]
        return f"Missing documentation: {', '.join(missing)}." if missing else "Documentation needs review."
    if category_id == CATEGORY_NEEDS_METADATA:
        status = album.get("metadata_status") or album.get("album_truth", {}).get("metadata_status") or "UNKNOWN"
        return f"Metadata status is {status}."
    if category_id == CATEGORY_NEEDS_REVIEW:
        truth = album.get("album_truth", {})
        return str(truth.get("readiness_reason") or "AlbumTruth requires review.")
    if category_id == CATEGORY_WARNINGS:
        warnings = warnings or []
        if warnings:
            return "; ".join(warning.get("message", "") for warning in warnings)
        return "Advisory warning."
    return ""


def maintenance_priority(category_id: str, warnings: list[dict[str, Any]] | None = None) -> str:
    if category_id in MAINTENANCE_PRIORITIES:
        return MAINTENANCE_PRIORITIES[category_id]
    if category_id in {CATEGORY_NEEDS_VALIDATION, CATEGORY_NEEDS_REVIEW, CATEGORY_WARNINGS}:
        return "HIGH"
    if category_id == CATEGORY_NEEDS_DOCUMENTATION:
        return "MEDIUM"
    if category_id == CATEGORY_NEEDS_METADATA:
        return "LOW"
    return "INFO"


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
