from __future__ import annotations

from collections import defaultdict
from pathlib import Path
from typing import Any

from audio_division.dashboard import load_json


def load_library_sources(data_dir: Path) -> dict[str, dict[str, Any]]:
    return {
        "lifecycle": load_json(data_dir / "lifecycle_registry.json"),
        "identity": load_json(data_dir / "identity_registry.json"),
        "metadata": load_json(data_dir / "metadata_cache.json"),
    }


def build_library(lifecycle: dict[str, Any], identity: dict[str, Any], metadata: dict[str, Any]) -> dict[str, Any]:
    identity_by_album = {
        row.get("discovery_identity", {}).get("deezer_album_id"): row
        for row in identity.get("releases", [])
        if row.get("discovery_identity", {}).get("deezer_album_id")
    }
    metadata_albums = metadata.get("albums", {})
    lifecycle_rows = lifecycle.get("albums", [])
    albums = [_album_record(row, metadata_albums.get(str(row.get("album_id")), {}), identity_by_album) for row in lifecycle_rows]
    artists = build_artist_index(albums, metadata)

    return {
        "summary": library_summary(artists, albums, metadata, lifecycle),
        "artists": artists,
        "albums": sorted(albums, key=lambda item: (_sort_text(item["artist"]), _sort_text(item["title"]), item["album_id"])),
        "albums_by_artist": _albums_by_artist(albums),
    }


def library_from_data_dir(data_dir: Path) -> dict[str, Any]:
    sources = load_library_sources(data_dir)
    return build_library(sources["lifecycle"], sources["identity"], sources["metadata"])


def build_artist_index(albums: list[dict[str, Any]], metadata: dict[str, Any]) -> list[dict[str, Any]]:
    counts: dict[str, int] = defaultdict(int)
    display: dict[str, str] = {}
    for album in albums:
        key = _artist_key(album.get("artist"))
        counts[key] += 1
        display.setdefault(key, album.get("artist") or "(unknown)")

    for artist in metadata.get("artists", {}).values():
        name = artist.get("name")
        if not name:
            continue
        key = _artist_key(name)
        display.setdefault(key, name)
        counts.setdefault(key, 0)

    return [
        {"artist_key": key, "name": display[key], "album_count": counts[key]}
        for key in sorted(display, key=lambda item: display[item].lower())
    ]


def albums_for_artist(library: dict[str, Any], artist_key: str) -> list[dict[str, Any]]:
    return library.get("albums_by_artist", {}).get(artist_key, [])


def album_details(library: dict[str, Any], album_id: str) -> dict[str, Any]:
    for album in library.get("albums", []):
        if str(album.get("album_id")) == str(album_id):
            return album
    return {}


def library_summary(
    artists: list[dict[str, Any]],
    albums: list[dict[str, Any]],
    metadata: dict[str, Any],
    lifecycle: dict[str, Any],
) -> dict[str, Any]:
    total = len(albums)
    validated = sum(1 for album in albums if album.get("validation_status") == "validated")
    metadata_summary = metadata.get("summary", {})
    return {
        "artists": len(artists),
        "albums": total,
        "tracks": len(metadata.get("tracks", {})),
        "metadata_coverage": metadata_summary.get("coverage_percent", _ratio(metadata_summary.get("albums_with_metadata", 0), total)),
        "validation_coverage": _ratio(validated, total),
        "source_lifecycle_generated_at": lifecycle.get("generated_at"),
    }


def _album_record(
    lifecycle_row: dict[str, Any],
    metadata_album: dict[str, Any],
    identity_by_album: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    album_id = str(lifecycle_row.get("album_id"))
    identity = identity_by_album.get(album_id, {})
    artist = _metadata_artist(metadata_album) or lifecycle_row.get("artist") or "(unknown)"
    title = metadata_album.get("title") or lifecycle_row.get("title") or "(unknown)"
    states = lifecycle_row.get("states", {})
    validation_status = "validated" if states.get("validated") else "not_validated"
    covers = metadata_album.get("covers", {}) if isinstance(metadata_album.get("covers"), dict) else {}

    return {
        "album_id": album_id,
        "artist_key": _artist_key(artist),
        "artist": artist,
        "title": title,
        "year": metadata_album.get("year"),
        "release_date": metadata_album.get("release_date"),
        "record_type": metadata_album.get("record_type"),
        "label": metadata_album.get("label"),
        "genres": [item.get("name") for item in metadata_album.get("genres", []) if isinstance(item, dict) and item.get("name")],
        "track_count": metadata_album.get("track_count") or lifecycle_row.get("details", {}).get("validated_tracks"),
        "duration": metadata_album.get("duration"),
        "lifecycle_state": lifecycle_row.get("highest_state"),
        "identity_confidence": identity.get("identity_confidence", "UNKNOWN"),
        "validation_status": validation_status,
        "metadata_status": "cached" if metadata_album else "missing",
        "archive_strength_signals": {
            "has_identity": identity.get("identity_confidence") == "HIGH",
            "has_validation": validation_status == "validated",
            "has_metadata": bool(metadata_album),
        },
        "artwork": {
            "cover_identity": metadata_album.get("cover_identity"),
            "urls": covers,
            "local": None,
        },
    }


def _albums_by_artist(albums: list[dict[str, Any]]) -> dict[str, list[dict[str, Any]]]:
    out: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for album in albums:
        out[album["artist_key"]].append(album)
    for key in out:
        out[key].sort(key=lambda item: (_sort_year(item.get("year")), _sort_text(item.get("title"))))
    return dict(out)


def _metadata_artist(metadata_album: dict[str, Any]) -> str | None:
    artist = metadata_album.get("artist")
    if isinstance(artist, dict):
        return artist.get("name")
    return None


def _artist_key(name: Any) -> str:
    text = str(name or "(unknown)").strip().lower()
    return " ".join(text.split())


def _sort_text(value: Any) -> str:
    return str(value or "").lower()


def _sort_year(value: Any) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return 9999


def _ratio(count: int, total: int) -> float:
    if total == 0:
        return 0.0
    return round(count / total, 4)
