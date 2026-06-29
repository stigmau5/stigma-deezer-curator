from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path
from typing import Any

from curator.atomic import atomic_write_text


QUEUE_SCHEMA = 1

STATE_QUEUED = "Queued"
STATE_DOWNLOADING = "Downloading"
STATE_DOWNLOADED = "Downloaded"
STATE_WAITING_VALIDATION = "Waiting Validation"
STATE_READY_FOR_PROCESSING = "Ready For Processing"
STATE_ARCHIVED = "Archived"
STATE_FAILED = "Failed"
STATE_SKIPPED = "Skipped"

QUEUE_STATES = (
    STATE_QUEUED,
    STATE_DOWNLOADING,
    STATE_DOWNLOADED,
    STATE_WAITING_VALIDATION,
    STATE_READY_FOR_PROCESSING,
    STATE_ARCHIVED,
    STATE_FAILED,
    STATE_SKIPPED,
)

STATE_ACTIONS = {
    STATE_QUEUED: "Acquire Album",
    STATE_DOWNLOADING: "Wait",
    STATE_DOWNLOADED: "Validate",
    STATE_WAITING_VALIDATION: "Validate",
    STATE_READY_FOR_PROCESSING: "Process",
    STATE_ARCHIVED: "Open Archive",
    STATE_FAILED: "Review",
    STATE_SKIPPED: "Review",
}


def empty_acquisition_queue() -> dict[str, Any]:
    return {"schema": QUEUE_SCHEMA, "items": {}}


def load_acquisition_queue(path: Path) -> dict[str, Any]:
    if not path.exists():
        return empty_acquisition_queue()
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return empty_acquisition_queue()
    if not isinstance(data, dict):
        return empty_acquisition_queue()
    items = data.get("items", {})
    if isinstance(items, list):
        items = {
            queue_item_key(item): normalize_queue_item(item)
            for item in items
            if isinstance(item, dict) and queue_item_key(item)
        }
    if not isinstance(items, dict):
        return empty_acquisition_queue()
    return {
        "schema": QUEUE_SCHEMA,
        "items": {
            str(key): normalize_queue_item(item)
            for key, item in items.items()
            if isinstance(item, dict)
        },
    }


def save_acquisition_queue(path: Path, queue: dict[str, Any]) -> None:
    normalized = {
        "schema": QUEUE_SCHEMA,
        "items": {
            str(key): normalize_queue_item(item)
            for key, item in queue.get("items", {}).items()
            if isinstance(item, dict)
        },
    }
    atomic_write_text(path, json.dumps(normalized, ensure_ascii=False, indent=2, sort_keys=True) + "\n")


def queue_release(
    queue: dict[str, Any],
    release: Any,
    *,
    artist: str = "",
    queued_time: str | None = None,
) -> dict[str, Any]:
    return add_queue_item(
        queue,
        {
            "artist": artist,
            "album": getattr(release, "title", ""),
            "release_type": getattr(release, "type", ""),
            "deezer_album_id": getattr(release, "deezer_album_id", ""),
            "url": getattr(release, "url", ""),
            "current_state": STATE_QUEUED,
        },
        queued_time=queued_time,
    )


def add_queue_item(
    queue: dict[str, Any],
    item: dict[str, Any],
    *,
    queued_time: str | None = None,
) -> dict[str, Any]:
    updated = {"schema": QUEUE_SCHEMA, "items": dict(queue.get("items", {}))}
    normalized = normalize_queue_item(item)
    key = queue_item_key(normalized)
    if not key:
        return updated
    existing = dict(updated["items"].get(key, {}))
    normalized["queued_time"] = existing.get("queued_time") or queued_time or _now()
    if existing.get("current_state") and not item.get("current_state"):
        normalized["current_state"] = existing["current_state"]
    updated["items"][key] = normalized
    return updated


def remove_queue_item(queue: dict[str, Any], key: str) -> dict[str, Any]:
    updated = {"schema": QUEUE_SCHEMA, "items": dict(queue.get("items", {}))}
    updated["items"].pop(str(key), None)
    return updated


def update_queue_item_state(queue: dict[str, Any], key: str, state: str) -> dict[str, Any]:
    if state not in QUEUE_STATES:
        raise ValueError(f"Unknown acquisition queue state: {state}")
    updated = {"schema": QUEUE_SCHEMA, "items": dict(queue.get("items", {}))}
    item = dict(updated["items"].get(str(key), {}))
    if item:
        item["current_state"] = state
        updated["items"][str(key)] = normalize_queue_item(item)
    return updated


def queue_rows(queue: dict[str, Any]) -> list[dict[str, Any]]:
    rows = []
    for key, item in queue.get("items", {}).items():
        row = normalize_queue_item(item)
        row["key"] = str(key)
        row["action"] = action_for_state(row["current_state"])
        rows.append(row)
    return sorted(rows, key=lambda row: (row.get("queued_time", ""), row.get("artist", ""), row.get("album", "")))


def normalize_queue_item(item: dict[str, Any]) -> dict[str, str]:
    state = str(item.get("current_state") or item.get("state") or STATE_QUEUED)
    if state not in QUEUE_STATES:
        state = STATE_QUEUED
    return {
        "artist": str(item.get("artist") or ""),
        "album": str(item.get("album") or item.get("title") or ""),
        "release_type": str(item.get("release_type") or item.get("type") or ""),
        "deezer_album_id": str(item.get("deezer_album_id") or item.get("album_id") or ""),
        "url": str(item.get("url") or ""),
        "queued_time": str(item.get("queued_time") or item.get("queued_at") or ""),
        "current_state": state,
        "incoming_folder": str(item.get("incoming_folder") or item.get("folder") or ""),
    }


def queue_item_key(item: dict[str, Any]) -> str:
    album_id = str(item.get("deezer_album_id") or item.get("album_id") or "").strip()
    if album_id:
        return album_id
    return str(item.get("url") or "").strip()


def action_for_state(state: str) -> str:
    return STATE_ACTIONS.get(state, "Review")


def _now() -> str:
    return datetime.now().isoformat(timespec="seconds")
