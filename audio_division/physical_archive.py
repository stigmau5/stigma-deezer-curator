from __future__ import annotations

import re
from collections import defaultdict
from pathlib import Path
from typing import Any


READINESS_STATES = ("ARCHIVE_READY", "NEEDS_VALIDATION", "NEEDS_DOCUMENTATION", "NEEDS_REVIEW", "UNKNOWN")


def build_archive_albums(archive_registry: dict[str, Any]) -> list[dict[str, Any]]:
    albums = [project_archive_album(row) for row in archive_registry.get("albums", [])]
    return sorted(albums, key=lambda item: (_sort_text(item["artist"]), _sort_text(item["title"]), _sort_text(item["archive_path"])))


def project_archive_album(row: dict[str, Any]) -> dict[str, Any]:
    artifacts = row.get("artifacts", {})
    artist = archive_artist(row)
    title = archive_title(row, artist)
    status = archive_album_status(artifacts)
    readiness = archive_readiness(status)
    return {
        "album_id": "",
        "artist_key": artist_key(artist),
        "artist": artist,
        "title": title,
        "year": archive_year(row),
        "release_date": "",
        "record_type": "archive_folder",
        "label": "",
        "genres": [],
        "track_count": row.get("track_count", 0),
        "duration": "",
        "lifecycle_state": "ARCHIVED",
        "identity_confidence": "UNKNOWN",
        "validation_status": "validated" if artifacts.get("validation_log") else "not_validated",
        "metadata_status": "UNKNOWN",
        "metadata_detail": {"cached_fields": {}, "missing_fields": []},
        "archive_folder": row.get("name", ""),
        "archive_path": row.get("archive_path", ""),
        "archive_path_confidence": "HIGH" if row.get("archive_path") else "UNKNOWN",
        "archive_path_reason": "archive_registry",
        "artifacts": artifacts,
        "album_status": status,
        "archive_readiness": readiness,
        "archive_strength_signals": {
            "has_identity": False,
            "has_validation": artifacts.get("validation_log", False),
            "has_metadata": False,
            "has_nfo": artifacts.get("nfo", False),
            "has_sfv": artifacts.get("sfv", False),
            "has_playlist": artifacts.get("playlist", False),
            "has_artwork": artifacts.get("artwork", False),
        },
        "artwork": {"cover_identity": "", "urls": {}, "local": artifacts.get("artwork", False)},
    }


def archive_tree(albums: list[dict[str, Any]]) -> list[dict[str, Any]]:
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for album in albums:
        grouped[album["artist"]].append(album)
    rows = []
    for artist in sorted(grouped, key=_sort_text):
        letter = first_letter(artist)
        rows.append({"letter": letter, "artist": artist, "artist_key": artist_key(artist), "album_count": len(grouped[artist])})
    return rows


def albums_for_archive_artist(albums: list[dict[str, Any]], selected_artist_key: str) -> list[dict[str, Any]]:
    return [album for album in albums if album.get("artist_key") == selected_artist_key]


def filter_archive_albums(
    albums: list[dict[str, Any]],
    *,
    artist: str = "",
    album: str = "",
) -> list[dict[str, Any]]:
    artist_query = artist.strip().lower()
    album_query = album.strip().lower()
    out = []
    for row in albums:
        if artist_query and artist_query not in str(row.get("artist", "")).lower():
            continue
        if album_query and album_query not in str(row.get("title", "")).lower():
            continue
        out.append(row)
    return out


def archive_album_status(artifacts: dict[str, Any]) -> dict[str, Any]:
    items = {
        "validation": "Present" if artifacts.get("validation_log") else "Missing",
        "nfo": "Present" if artifacts.get("nfo") else "Missing",
        "sfv": "Present" if artifacts.get("sfv") else "Missing",
        "playlist": "Present" if artifacts.get("playlist") else "Missing",
        "artwork": "Present" if artifacts.get("artwork") else "Missing",
        "metadata": "Unknown",
    }
    known = [value for value in items.values() if value != "Unknown"]
    present = sum(1 for value in known if value == "Present")
    return {"items": items, "health_percent": round((present / len(known)) * 100) if known else 0}


def archive_readiness(status: dict[str, Any]) -> dict[str, Any]:
    items = status.get("items", {})
    if items.get("validation") != "Present":
        return _readiness("NEEDS_VALIDATION", "Validation evidence is missing.", "HIGH", ["validation_missing"])
    missing_docs = [name for name in ("nfo", "sfv") if items.get(name) != "Present"]
    if missing_docs:
        return _readiness(
            "NEEDS_DOCUMENTATION",
            "Validation is present but archive documentation is incomplete.",
            "HIGH",
            [f"{name}_missing" for name in missing_docs],
        )
    if items.get("artwork") != "Present" or items.get("playlist") != "Present":
        return _readiness("NEEDS_REVIEW", "Artwork or playlist evidence is incomplete.", "MEDIUM", ["archive_artifacts_incomplete"])
    return _readiness("ARCHIVE_READY", "Validation, documentation, playlist, and artwork are present.", "HIGH", ["ready"])


def archive_artist(row: dict[str, Any]) -> str:
    parts = Path(row.get("relative_path") or row.get("archive_path") or "").parts
    if "Albums" in parts:
        index = parts.index("Albums")
        if index > 0:
            return parts[index - 1]
    if len(parts) >= 2:
        return parts[-2]
    return split_folder_name(row.get("name", ""))[0]


def archive_title(row: dict[str, Any], artist: str = "") -> str:
    folder = str(row.get("name") or "").strip()
    _, title = split_folder_name(folder)
    prefix = f"{artist}-"
    if artist and title.lower().startswith(prefix.lower()):
        title = title[len(prefix) :]
    return title or folder or "(unknown)"


def archive_year(row: dict[str, Any]) -> str:
    match = re.search(r"(19|20)\d{2}", str(row.get("name") or ""))
    return match.group(0) if match else ""


def split_folder_name(folder: str) -> tuple[str, str]:
    text = str(folder or "").strip()
    if "-" not in text:
        return "(unknown)", text or "(unknown)"
    artist, title = text.split("-", 1)
    return artist.strip() or "(unknown)", title.strip() or text


def first_letter(artist: str) -> str:
    text = str(artist or "#").strip()
    first = text[0].upper() if text else "#"
    return first if first.isalpha() else "#"


def artist_key(name: Any) -> str:
    return " ".join(str(name or "(unknown)").strip().lower().split())


def _readiness(state: str, reason: str, confidence: str, explanation: list[str]) -> dict[str, Any]:
    return {"state": state, "reason": reason, "confidence": confidence, "explanation": explanation}


def _sort_text(value: Any) -> str:
    return str(value or "").lower()
