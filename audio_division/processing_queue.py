from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any

from audio_division.selection_state import archive_album_key
from curator.atomic import atomic_write_text


QUEUE_SCHEMA = 1
PROCESSING_STATES = ("DISCOVERED", "DOWNLOADED", "PROCESSING", "ARCHIVED")
STATE_LABELS = {
    "DISCOVERED": "Discovered",
    "DOWNLOADED": "Downloaded",
    "NEEDS_PROCESSING": "Needs Processing",
    "PROCESSING": "Processing",
    "ARCHIVED": "Archived",
}


def empty_processing_queue() -> dict[str, Any]:
    return {"schema": QUEUE_SCHEMA, "albums": {}}


def load_processing_queue(path: Path) -> dict[str, Any]:
    if not path.exists():
        return empty_processing_queue()
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return empty_processing_queue()
    if not isinstance(data, dict) or not isinstance(data.get("albums"), dict):
        return empty_processing_queue()
    return {"schema": QUEUE_SCHEMA, "albums": data.get("albums", {})}


def save_processing_queue(path: Path, queue: dict[str, Any]) -> None:
    normalized = {
        "schema": QUEUE_SCHEMA,
        "albums": dict(queue.get("albums", {})),
    }
    atomic_write_text(path, json.dumps(normalized, ensure_ascii=False, indent=2, sort_keys=True) + "\n")


def queue_for_processing(queue: dict[str, Any], album: dict[str, Any], *, source: str = "archive") -> dict[str, Any]:
    updated = {"schema": QUEUE_SCHEMA, "albums": dict(queue.get("albums", {}))}
    key = archive_album_key(album)
    now = datetime.now().isoformat(timespec="seconds")
    existing = dict(updated["albums"].get(key, {}))
    existing.update(
        {
            "album_id": str(album.get("album_id") or existing.get("album_id") or ""),
            "artist": str(album.get("artist") or existing.get("artist") or ""),
            "album": str(album.get("title") or album.get("album") or existing.get("album") or ""),
            "archive_path": str(album.get("archive_path") or existing.get("archive_path") or ""),
            "source": source,
            "state": "PROCESSING",
            "updated_at": now,
        }
    )
    existing.setdefault("queued_at", now)
    updated["albums"][key] = existing
    return updated


def processing_rows(albums: list[dict[str, Any]], queue: dict[str, Any]) -> list[dict[str, Any]]:
    rows_by_key: dict[str, dict[str, Any]] = {}
    for album in albums:
        if not album.get("archive_path") and not album.get("album_truth"):
            continue
        row = processing_row(album, queue)
        if row["current_state"] != "Discovered":
            rows_by_key[row["key"]] = row

    for key, entry in queue.get("albums", {}).items():
        rows_by_key.setdefault(
            key,
            {
                "key": key,
                "album": entry.get("album", ""),
                "artist": entry.get("artist", ""),
                "source": entry.get("source", "manual"),
                "current_state": STATE_LABELS.get(entry.get("state", ""), entry.get("state", "")),
                "archive_path": entry.get("archive_path", ""),
            },
        )
    return sorted(rows_by_key.values(), key=lambda row: (row.get("artist", "").lower(), row.get("album", "").lower()))


def processing_row(album: dict[str, Any], queue: dict[str, Any]) -> dict[str, Any]:
    key = archive_album_key(album)
    entry = queue.get("albums", {}).get(key, {})
    truth = album.get("album_truth", {})
    truth_state = truth.get("processing_state") or album.get("processing_state") or "DISCOVERED"
    state = queue_state(truth_state, entry)
    return {
        "key": key,
        "album": album.get("title") or album.get("album") or entry.get("album", ""),
        "artist": album.get("artist") or entry.get("artist", ""),
        "source": entry.get("source") or "archive",
        "current_state": STATE_LABELS.get(state, state),
        "archive_path": album.get("archive_path") or entry.get("archive_path", ""),
    }


def queue_state(truth_state: str, queue_entry: dict[str, Any] | None = None) -> str:
    if truth_state == "ARCHIVED":
        return "ARCHIVED"
    if queue_entry and queue_entry.get("state") == "PROCESSING":
        return "PROCESSING"
    if truth_state == "PROCESSING":
        return "NEEDS_PROCESSING"
    if truth_state == "DOWNLOADED":
        return "DOWNLOADED"
    return "DISCOVERED"
