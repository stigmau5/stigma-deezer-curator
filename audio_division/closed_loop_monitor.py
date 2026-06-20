from __future__ import annotations

import re
import unicodedata
from pathlib import Path
from typing import Any

from audio_division.lifecycle_state import (
    STATE_ARCHIVED,
    STATE_DOWNLOADED,
    STATE_READY_FOR_PROCESSING,
    STATE_UNKNOWN,
    detect_lifecycle_state,
)
from audio_division.physical_archive import split_folder_name


DEFAULT_SOURCE = "Deezer"
STATE_NEEDS_PROCESSING = STATE_READY_FOR_PROCESSING
STATE_PROCESSING = STATE_READY_FOR_PROCESSING


def incoming_sources(settings: dict[str, Any]) -> list[dict[str, str]]:
    roots = []
    incoming_root = settings.get("archive_paths", {}).get("incoming_root", "")
    if incoming_root:
        roots.append({"source": DEFAULT_SOURCE, "root": str(incoming_root)})
    return roots


def discover_incoming_albums(
    settings: dict[str, Any],
    archive_albums: list[dict[str, Any]],
    queue: dict[str, Any] | None = None,
) -> list[dict[str, Any]]:
    queue = queue or {}
    archived = archived_folder_keys(archive_albums)
    rows = []
    for source in incoming_sources(settings):
        root = Path(source["root"]).expanduser()
        rows.extend(discover_source(root, source["source"], archived, queue))
    return sorted(rows, key=lambda row: (_sort_text(row.get("source")), _sort_text(row.get("album"))))


def discover_source(
    root: Path,
    source: str,
    archived_keys: set[str],
    queue: dict[str, Any] | None = None,
) -> list[dict[str, Any]]:
    if not root.exists() or not root.is_dir():
        return []
    rows = []
    for folder in sorted((item for item in root.iterdir() if item.is_dir()), key=lambda item: item.name.lower()):
        artist, album = split_folder_name(folder.name)
        key = folder_identity_key(folder.name)
        if key in archived_keys:
            continue
        pipeline = detect_lifecycle_state(
            {
                "artist": artist,
                "album": album,
                "folder": str(folder),
                "archive_path": "",
            },
            (queue or {}).get("albums", {}).get(str(folder), {}),
        )
        rows.append(
            {
                "key": str(folder),
                "artist": artist,
                "album": album,
                "source": source,
                "folder": str(folder),
                "state": pipeline.state,
                "pipeline_state": pipeline.to_dict(),
                "identity_key": key,
            }
        )
    return rows


def incoming_state(folder: Path | str, queue: dict[str, Any]) -> str:
    entry = queue.get("albums", {}).get(str(folder), {})
    pipeline = detect_lifecycle_state({"folder": str(folder)}, entry)
    return pipeline.state


def has_processing_evidence(folder: Path) -> bool:
    if not folder.exists() or not folder.is_dir():
        return False
    try:
        return any(item.is_file() and item.suffix.lower() in {".flac", ".mp3", ".m4a", ".wav"} for item in folder.iterdir())
    except OSError:
        return False


def archived_folder_keys(archive_albums: list[dict[str, Any]]) -> set[str]:
    keys = set()
    for album in archive_albums:
        for value in (album.get("archive_folder"), Path(str(album.get("archive_path") or "")).name):
            key = folder_identity_key(value)
            if key:
                keys.add(key)
    return keys


def closed_loop_summary(rows: list[dict[str, Any]]) -> dict[str, Any]:
    counts = {
        STATE_DOWNLOADED: 0,
        STATE_READY_FOR_PROCESSING: 0,
        STATE_ARCHIVED: 0,
        STATE_UNKNOWN: 0,
    }
    sources: set[str] = set()
    for row in rows:
        state = row.get("state", STATE_DOWNLOADED)
        counts[state if state in counts else STATE_UNKNOWN] += 1
        if row.get("source"):
            sources.add(str(row["source"]))
    return {"incoming_albums": len(rows), "sources": len(sources), "states": counts}


def queue_album_payload(row: dict[str, Any]) -> dict[str, Any]:
    return {
        "album_id": "",
        "artist": row.get("artist", ""),
        "title": row.get("album", ""),
        "archive_path": row.get("folder", ""),
    }


def folder_identity_key(value: Any) -> str:
    text = unicodedata.normalize("NFKD", str(value or ""))
    text = text.encode("ascii", "ignore").decode("ascii").lower()
    tokens = [token for token in re.split(r"[^a-z0-9]+", text) if token]
    return "".join(tokens)


def _sort_text(value: Any) -> str:
    return str(value or "").lower()
