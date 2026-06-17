from __future__ import annotations

from collections import Counter
from pathlib import Path
from typing import Any

from curator.atomic import atomic_write_text

METADATA_STATES = ("CACHED", "AVAILABLE_NOT_CACHED", "MISSING", "UNKNOWN")
ALBUM_FIELDS = ("upc", "label", "genres", "contributors", "release_date")


def album_metadata_status(album_id: Any, metadata: dict[str, Any]) -> dict[str, Any]:
    album_id = str(album_id or "")
    albums = metadata.get("albums", {})
    errors = metadata.get("errors", {})
    if not album_id:
        return _status("UNKNOWN", "No album id is available for metadata lookup.", {}, ALBUM_FIELDS)
    if album_id in albums:
        cached = cached_album_fields(albums[album_id])
        missing = [field for field in ALBUM_FIELDS if not cached[field]]
        return _status("CACHED", "Album metadata is cached.", cached, missing)
    if album_id in errors:
        return _status("MISSING", "Metadata import was attempted and failed.", {}, ALBUM_FIELDS)
    return _status("AVAILABLE_NOT_CACHED", "Album has a provider id but has not been imported into the metadata cache.", {}, ALBUM_FIELDS)


def cached_album_fields(album: dict[str, Any]) -> dict[str, bool]:
    return {
        "upc": bool(album.get("upc")),
        "label": bool(album.get("label")),
        "genres": bool(album.get("genres")),
        "contributors": bool(album.get("contributors")),
        "release_date": bool(album.get("release_date")),
    }


def metadata_coverage(lifecycle: dict[str, Any], metadata: dict[str, Any]) -> dict[str, Any]:
    statuses = [album_metadata_status(row.get("album_id"), metadata) for row in lifecycle.get("albums", [])]
    counts = Counter(status["state"] for status in statuses)
    total = len(statuses)
    return {
        "total_albums": total,
        "states": {state: counts.get(state, 0) for state in METADATA_STATES},
        "coverage_percent": _ratio(counts.get("CACHED", 0), total),
        "cached_albums": counts.get("CACHED", 0),
        "cached_artists": len(metadata.get("artists", {})),
        "cached_tracks": len(metadata.get("tracks", {})),
    }


def collection_statistics(metadata: dict[str, Any]) -> dict[str, Any]:
    albums = metadata.get("albums", {})
    tracks = metadata.get("tracks", {})
    return {
        "top_labels": _counter(album.get("label") for album in albums.values()).most_common(20),
        "release_years": sorted(_counter(album.get("year") for album in albums.values()).items()),
        "genres": _counter(genre.get("name") for album in albums.values() for genre in album.get("genres", []) if isinstance(genre, dict)).most_common(50),
        "record_types": _counter(album.get("record_type") for album in albums.values()).most_common(),
        "artist_counts": _counter((album.get("artist") or {}).get("name") for album in albums.values() if isinstance(album.get("artist"), dict)).most_common(50),
        "track_counts": _counter(album.get("track_count") for album in albums.values()).most_common(30),
        "total_cached_duration": sum(int(album.get("duration") or 0) for album in albums.values()),
        "tracks_with_isrc": sum(1 for track in tracks.values() if track.get("isrc")),
    }


def render_metadata_status_report(lifecycle: dict[str, Any], metadata: dict[str, Any]) -> str:
    coverage = metadata_coverage(lifecycle, metadata)
    lines = [
        "# Metadata Status Report",
        "",
        "Metadata status is derived from lifecycle ids and the existing metadata cache. No network calls are made.",
        "",
        f"- Total albums: `{coverage['total_albums']}`",
        f"- Cached albums: `{coverage['cached_albums']}`",
        f"- Cached artists: `{coverage['cached_artists']}`",
        f"- Cached tracks: `{coverage['cached_tracks']}`",
        f"- Coverage: `{coverage['coverage_percent']:.1%}`",
        "",
        "| State | Count |",
        "| --- | ---: |",
    ]
    for state in METADATA_STATES:
        lines.append(f"| {state} | {coverage['states'].get(state, 0)} |")
    return "\n".join(lines) + "\n"


def render_collection_intelligence_report(metadata: dict[str, Any]) -> str:
    stats = collection_statistics(metadata)
    lines = [
        "# Collection Intelligence Report",
        "",
        "Collection intelligence uses cached metadata only.",
        "",
        f"- Total cached duration: `{stats['total_cached_duration']}` seconds",
        f"- Tracks with ISRC: `{stats['tracks_with_isrc']}`",
        "",
        "## Record Types",
        "",
        *_table("Record Type", stats["record_types"]),
        "",
        "## Top Labels",
        "",
        *_table("Label", stats["top_labels"]),
        "",
        "## Genres",
        "",
        *_table("Genre", stats["genres"]),
    ]
    return "\n".join(lines) + "\n"


def render_simple_counter_report(title: str, heading: str, rows: list[tuple[Any, int]]) -> str:
    return "\n".join([f"# {title}", "", *_table(heading, rows)]) + "\n"


def write_metadata_reports(lifecycle: dict[str, Any], metadata: dict[str, Any], reports_dir: Path) -> None:
    reports_dir.mkdir(parents=True, exist_ok=True)
    stats = collection_statistics(metadata)
    atomic_write_text(reports_dir / "metadata_status_report.md", render_metadata_status_report(lifecycle, metadata))
    atomic_write_text(reports_dir / "collection_intelligence_report.md", render_collection_intelligence_report(metadata))
    atomic_write_text(reports_dir / "genre_report.md", render_simple_counter_report("Genre Report", "Genre", stats["genres"]))
    atomic_write_text(reports_dir / "label_report.md", render_simple_counter_report("Label Report", "Label", stats["top_labels"]))
    atomic_write_text(reports_dir / "release_year_report.md", render_simple_counter_report("Release Year Report", "Year", stats["release_years"]))


def _status(state: str, reason: str, cached_fields: dict[str, bool], missing_fields: list[str]) -> dict[str, Any]:
    return {
        "state": state,
        "reason": reason,
        "cached_fields": cached_fields,
        "missing_fields": missing_fields,
    }


def _counter(values: Any) -> Counter:
    return Counter(value for value in values if value not in (None, "", []))


def _table(label: str, rows: list[tuple[Any, int]]) -> list[str]:
    lines = [f"| {label} | Count |", "| --- | ---: |"]
    for value, count in rows:
        lines.append(f"| {_escape(value)} | {count} |")
    return lines


def _ratio(count: int, total: int) -> float:
    if total == 0:
        return 0.0
    return round(count / total, 4)


def _escape(value: Any) -> str:
    return str(value or "").replace("|", "\\|").replace("\n", " ").strip()
