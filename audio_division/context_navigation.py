from __future__ import annotations

from pathlib import Path
from typing import Any


def context_actions(row: dict[str, Any] | None) -> dict[str, bool]:
    row = row or {}
    archive_path = _path_text(row.get("archive_path"))
    folder = _path_text(row.get("folder") or row.get("incoming_folder"))
    deezer_link = _deezer_link(row)
    album_id = _album_id(row)
    identity_confidence = str(row.get("identity_confidence") or "").strip().upper()
    validation_status = str(row.get("validation_status") or "").strip().lower()
    state = str(row.get("state") or row.get("current_state") or row.get("lifecycle_state") or "").strip().upper()

    has_archive = bool(archive_path)
    has_folder = bool(folder or archive_path)
    return {
        "jump_to_archive": has_archive,
        "jump_to_curator": bool(album_id or deezer_link),
        "open_folder": has_folder,
        "open_parent_folder": has_folder,
        "copy_album_id": bool(album_id),
        "copy_deezer_link": bool(deezer_link),
        "revalidate": has_archive,
        "process_album": has_folder and (has_archive or validation_status == "validated" or state in {"VALIDATED", "READY_FOR_PROCESSING"}),
        "reveal_incoming_folder": bool(folder),
        "show_identity": bool(album_id or identity_confidence),
    }


def context_album_id(row: dict[str, Any] | None) -> str:
    return _album_id(row or {})


def context_deezer_link(row: dict[str, Any] | None) -> str:
    return _deezer_link(row or {})


def context_folder(row: dict[str, Any] | None) -> str:
    row = row or {}
    return _path_text(row.get("folder") or row.get("incoming_folder") or row.get("archive_path"))


def context_parent_folder(row: dict[str, Any] | None) -> str:
    folder = context_folder(row)
    return str(Path(folder).expanduser().parent) if folder else ""


def _album_id(row: dict[str, Any]) -> str:
    return str(row.get("deezer_album_id") or row.get("album_id") or "").strip()


def _deezer_link(row: dict[str, Any]) -> str:
    link = str(row.get("url") or row.get("deezer_url") or row.get("link") or "").strip()
    if link:
        return link
    album_id = _album_id(row)
    return f"https://www.deezer.com/album/{album_id}" if album_id else ""


def _path_text(value: Any) -> str:
    return str(value or "").strip()
