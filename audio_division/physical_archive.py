from __future__ import annotations

import re
import unicodedata
from collections import defaultdict
from pathlib import Path
from typing import Any

from audio_division.album_truth import album_truth
from audio_division.lifecycle_state import attach_lifecycle_state
from audio_division.metadata_status import album_metadata_status


READINESS_STATES = ("ARCHIVE_READY", "NEEDS_VALIDATION", "NEEDS_DOCUMENTATION", "NEEDS_REVIEW", "UNKNOWN")
RELEASE_TAG_TOKENS = {"web", "flac", "stigma"}


def build_archive_albums(
    archive_registry: dict[str, Any],
    identity_registry: dict[str, Any] | None = None,
    metadata: dict[str, Any] | None = None,
) -> list[dict[str, Any]]:
    identity_registry = identity_registry or {}
    metadata = metadata or {}
    identity_lookup = build_identity_lookup(identity_registry)
    albums = [
        project_archive_album(row, archive_identity_for_row(row, identity_lookup), metadata)
        for row in archive_registry.get("albums", [])
    ]
    return sorted(albums, key=lambda item: (_sort_text(item["artist"]), _sort_text(item["title"]), _sort_text(item["archive_path"])))


def build_identity_lookup(identity_registry: dict[str, Any]) -> dict[str, Any]:
    releases = identity_registry.get("releases", [])
    by_folder = {
        _release_folder_key(release.get("archive_identity", {}).get("folder")): release
        for release in releases
        if _release_folder_key(release.get("archive_identity", {}).get("folder"))
    }
    by_artist: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for release in releases:
        discovery = release.get("discovery_identity", {})
        artist_key_value = _identity_text_key(discovery.get("artist"))
        if artist_key_value:
            by_artist[artist_key_value].append(release)
    return {"_identity_lookup": True, "by_folder": by_folder, "by_artist": dict(by_artist)}


def archive_identity_for_row(row: dict[str, Any], identity_registry: dict[str, Any]) -> dict[str, Any]:
    lookup = identity_registry if identity_registry.get("_identity_lookup") else build_identity_lookup(identity_registry)
    folder_key = _release_folder_key(row.get("name"))
    release = lookup.get("by_folder", {}).get(folder_key)
    if release:
        return release

    row_artist = _identity_text_key(archive_artist(row))
    row_name = _identity_text_key(row.get("name"))
    row_year = archive_year(row)
    for release in lookup.get("by_artist", {}).get(row_artist, []):
        discovery = release.get("discovery_identity", {})
        title_key = _identity_text_key(discovery.get("title"))
        if len(title_key) < 6 or title_key not in row_name:
            continue
        release_year = _release_year(release)
        if row_year and release_year and row_year != release_year:
            continue
        return release
    return {}


def project_archive_album(
    row: dict[str, Any],
    identity_release: dict[str, Any] | None = None,
    metadata: dict[str, Any] | None = None,
) -> dict[str, Any]:
    artifacts = row.get("artifacts", {})
    artist = archive_artist(row)
    title = archive_title(row, artist)
    identity_release = identity_release or {}
    metadata = metadata or {}
    discovery = identity_release.get("discovery_identity", {})
    album_id = str(discovery.get("deezer_album_id") or "")
    metadata_album = metadata.get("albums", {}).get(album_id, {}) if album_id else {}
    metadata_detail = album_metadata_status(album_id, metadata)
    contributors = contributor_names(metadata_album.get("contributors", []))
    covers = metadata_album.get("covers", {}) if isinstance(metadata_album.get("covers"), dict) else {}
    genres = [item.get("name") for item in metadata_album.get("genres", []) if isinstance(item, dict) and item.get("name")]
    truth = album_truth(
        artist=artist,
        album=title,
        archive_path=row.get("archive_path"),
        registry_artifacts=artifacts,
        metadata_state=metadata_detail["state"],
        metadata_album=metadata_album,
        identity_confidence=identity_release.get("identity_confidence", "UNKNOWN"),
    )
    status = truth.to_album_status()
    readiness = archive_readiness(status)
    projected = {
        "album_id": album_id,
        "artist_key": artist_key(artist),
        "artist": artist,
        "title": title,
        "year": archive_year(row) or metadata_album.get("year"),
        "release_date": metadata_album.get("release_date") or "",
        "record_type": metadata_album.get("record_type") or "archive_folder",
        "label": metadata_album.get("label") or "",
        "genres": genres,
        "contributors": contributors,
        "track_count": row.get("track_count", 0) or metadata_album.get("track_count") or 0,
        "duration": metadata_album.get("duration") or "",
        "lifecycle_state": "ARCHIVED",
        "identity_confidence": identity_release.get("identity_confidence", "UNKNOWN"),
        "validation_status": "validated" if truth.validation.present else "not_validated",
        "metadata_status": metadata_detail["state"],
        "metadata_detail": metadata_detail,
        "archive_folder": row.get("name", ""),
        "archive_path": row.get("archive_path", ""),
        "archive_path_confidence": "HIGH" if row.get("archive_path") else "UNKNOWN",
        "archive_path_reason": "archive_registry",
        "artifacts": artifacts,
        "album_status": status,
        "album_truth": truth.to_dict(),
        "processing_state": truth.processing_state,
        "archive_readiness": readiness,
        "archive_strength_signals": {
            "has_identity": bool(album_id),
            "has_validation": truth.validation.present,
            "has_metadata": bool(metadata_album),
            "has_nfo": truth.nfo.present,
            "has_sfv": truth.sfv.present,
            "has_playlist": truth.playlist.present,
            "has_artwork": truth.artwork.present,
        },
        "artwork": {"cover_identity": metadata_album.get("cover_identity", ""), "urls": covers, "local": artifacts.get("artwork_path", "")},
    }
    return attach_lifecycle_state(projected)


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


def contributor_names(contributors: Any) -> list[str]:
    if not isinstance(contributors, list):
        return []
    names = []
    for contributor in contributors:
        if not isinstance(contributor, dict):
            continue
        name = contributor.get("name")
        role = contributor.get("role")
        if name and role:
            names.append(f"{name} ({role})")
        elif name:
            names.append(str(name))
    return names


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


def _release_year(release: dict[str, Any]) -> str:
    folder = release.get("archive_identity", {}).get("folder")
    if folder:
        match = re.search(r"(19|20)\d{2}", str(folder))
        if match:
            return match.group(0)
    return ""


def _release_folder_key(value: Any) -> str:
    tokens = [token for token in _text_tokens(value) if token not in RELEASE_TAG_TOKENS]
    return "".join(tokens)


def _identity_text_key(value: Any) -> str:
    return "".join(_text_tokens(value))


def _text_tokens(value: Any) -> list[str]:
    text = unicodedata.normalize("NFKD", str(value or ""))
    text = text.encode("ascii", "ignore").decode("ascii").lower()
    return [token for token in re.split(r"[^a-z0-9]+", text) if token]


def _readiness(state: str, reason: str, confidence: str, explanation: list[str]) -> dict[str, Any]:
    return {"state": state, "reason": reason, "confidence": confidence, "explanation": explanation}


def _sort_text(value: Any) -> str:
    return str(value or "").lower()
