from __future__ import annotations

from pathlib import Path
from typing import Any

from audio_division.album_integrity import album_integrity
from audio_division.album_presentation import album_presentation
from audio_division.artifacts import AlbumArtifacts, detect_artifacts
from audio_division.cover_widget import album_cover_info
from audio_division.playback import playback_summary
from audio_division.relationships import album_relationships, render_relationships

NFO_READ_LIMIT = 20000


def album_workspace(
    details: dict[str, Any],
    metadata: dict[str, Any] | None = None,
    collection_albums: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    presentation = album_presentation(details)
    archive_path = Path(details.get("archive_path", "")) if details.get("archive_path") else None
    detected = detect_artifacts(archive_path) if archive_path else None
    cover = cover_info(details, archive_path, detected)
    nfo = nfo_info(archive_path, detected)
    tracklist = tracklist_info(archive_path, details, metadata or {}, detected)
    files = filesystem_listing(archive_path)
    integrity = album_integrity(details, detected)
    relationships = album_relationships(details, collection_albums or [])
    status = details.get("album_status", {})
    readiness = details.get("archive_readiness", {})
    timeline = release_timeline(details, metadata or {}, detected, integrity)
    return {
        "presentation": presentation,
        "cover": cover,
        "status_glance": status_glance(status, readiness),
        "nfo": nfo,
        "tracklist": tracklist,
        "files": files,
        "integrity": integrity,
        "timeline": timeline,
        "timeline_text": render_timeline(timeline),
        "relationships": relationships,
        "relationships_text": render_relationships(relationships),
        "playback": playback_summary(details),
    }


def cover_info(
    details: dict[str, Any],
    archive_path: Path | None = None,
    detected: AlbumArtifacts | None = None,
) -> dict[str, Any]:
    return album_cover_info(details, archive_path, detected)


def nfo_info(archive_path: Path | None, detected: AlbumArtifacts | None = None) -> dict[str, Any]:
    nfo = (detected or detect_artifacts(archive_path)).first_file("nfo") if archive_path else None
    if not nfo:
        return {"status": "Missing", "path": "", "content": "No NFO found."}
    try:
        content = nfo.read_text(encoding="utf-8", errors="replace")[:NFO_READ_LIMIT]
    except OSError as exc:
        return {"status": "Unreadable", "path": str(nfo), "content": str(exc)}
    return {"status": "Present", "path": str(nfo), "content": content}


def tracklist_info(
    archive_path: Path | None,
    details: dict[str, Any],
    metadata: dict[str, Any],
    detected: AlbumArtifacts | None = None,
) -> dict[str, Any]:
    if archive_path:
        detected = detected or detect_artifacts(archive_path)
        playlist = detected.first_file("playlist")
        if playlist:
            tracks = parse_playlist(playlist)
            if tracks:
                return {"source": "playlist", "path": str(playlist), "tracks": tracks}

        tracks = filesystem_tracks(archive_path, detected)
        if tracks:
            return {"source": "filesystem", "path": str(archive_path), "tracks": tracks}

    tracks = metadata_tracks(details.get("album_id"), metadata)
    if tracks:
        return {"source": "metadata", "path": "", "tracks": tracks}

    count = details.get("track_count")
    if count:
        return {"source": "count_only", "path": "", "tracks": [f"{count} track(s) known, track order unavailable."]}
    return {"source": "missing", "path": "", "tracks": ["No tracklist evidence found."]}


def status_glance(status: dict[str, Any], readiness: dict[str, Any]) -> list[tuple[str, str]]:
    items = status.get("items", {})
    return [
        ("Validation", items.get("validation", "Unknown")),
        ("Validation Source", status.get("validation_source", "missing")),
        ("Validation Confidence", status.get("validation_confidence", "NONE")),
        ("NFO", items.get("nfo", "Unknown")),
        ("SFV", items.get("sfv", "Unknown")),
        ("Playlist", items.get("playlist", "Unknown")),
        ("Artwork", items.get("artwork", "Unknown")),
        ("Readiness", readiness.get("state", "UNKNOWN")),
        ("Health", f"{status.get('health_percent', 0)}%"),
    ]


def release_timeline(
    details: dict[str, Any],
    metadata: dict[str, Any] | None = None,
    detected: AlbumArtifacts | None = None,
    integrity: dict[str, Any] | None = None,
) -> list[dict[str, str]]:
    metadata = metadata or {}
    integrity = integrity or {}
    events: list[dict[str, str]] = []
    pipeline = details.get("pipeline_state", {}) if isinstance(details.get("pipeline_state"), dict) else {}
    evidence = set(pipeline.get("evidence", []))
    status = details.get("album_status", {}) if isinstance(details.get("album_status"), dict) else {}
    status_items = status.get("items", {}) if isinstance(status.get("items"), dict) else {}
    artifacts = details.get("artifacts", {}) if isinstance(details.get("artifacts"), dict) else {}
    album_id = str(details.get("album_id") or "")

    if album_id or "curator_state" in evidence:
        events.append(
            _timeline_event(
                "Curated",
                _first_timestamp(details, ("curated_at", "discovered_at", "last_updated")),
                _confidence(details.get("identity_confidence"), "MEDIUM" if "curator_state" in evidence else "LOW"),
                "Curator or identity evidence exists.",
                _source_list("curator_state" if "curator_state" in evidence else "", "album_id" if album_id else ""),
            )
        )

    if "download_folder" in evidence or details.get("folder"):
        events.append(
            _timeline_event(
                "Downloaded",
                _first_timestamp(details, ("downloaded_at",)),
                "HIGH",
                "Downloaded folder evidence exists.",
                _source_list("download_folder", details.get("folder")),
            )
        )

    if status_items.get("validation") == "Present" or details.get("validation_status") == "validated":
        events.append(
            _timeline_event(
                "Validated",
                _first_timestamp(details, ("validated_at",)),
                _confidence(status.get("validation_confidence") or details.get("validation_confidence"), "MEDIUM"),
                status.get("validation_reason") or details.get("validation_reason") or "Validation evidence exists.",
                _source_list(status.get("validation_source") or details.get("validation_source"), details.get("validation_log_path")),
            )
        )

    processed_sources = []
    for key in ("nfo", "sfv", "playlist"):
        if status_items.get(key) == "Present" or artifacts.get(key):
            processed_sources.append(key.upper() if key != "playlist" else "Playlist")
    if processed_sources:
        confidence = "HIGH" if {"NFO", "SFV"}.issubset(set(processed_sources)) else "MEDIUM"
        events.append(
            _timeline_event(
                "Processed",
                _first_timestamp(details, ("processed_at",)),
                confidence,
                "Archive documentation or playlist artifacts exist.",
                processed_sources,
            )
        )

    if details.get("archive_path") or pipeline.get("state") == "ARCHIVED" or "archive_filesystem" in evidence:
        events.append(
            _timeline_event(
                "Archived",
                _first_timestamp(details, ("archived_at",)),
                _confidence(details.get("archive_path_confidence"), "HIGH" if details.get("archive_path") else "MEDIUM"),
                "Archive location evidence exists.",
                _source_list("archive_filesystem" if "archive_filesystem" in evidence else "", details.get("archive_path")),
            )
        )

    metadata_album = metadata.get("albums", {}).get(album_id, {}) if album_id else {}
    if metadata_album or details.get("metadata_status") == "CACHED":
        events.append(
            _timeline_event(
                "Metadata Cached",
                _first_timestamp(metadata_album, ("cached_at", "updated_at", "release_date")) or _first_timestamp(details, ("metadata_cached_at",)),
                "HIGH" if metadata_album else "MEDIUM",
                "Metadata cache contains this album.",
                _source_list("metadata_cache", album_id),
            )
        )

    if _audit_passed(integrity, status):
        events.append(
            _timeline_event(
                "Audit Passed",
                _first_timestamp(details, ("audit_passed_at",)),
                "HIGH",
                "Integrity checks are healthy.",
                _source_list("album_integrity", f"{status.get('health_percent', 0)}% health"),
            )
        )

    return events


def render_timeline(events: list[dict[str, str]]) -> str:
    if not events:
        return "No timeline evidence found."
    lines = []
    for event in events:
        when = event.get("timestamp") or "Derived"
        sources = f" [{event['sources']}]" if event.get("sources") else ""
        reason = f" - {event['reason']}" if event.get("reason") else ""
        lines.append(f"{when} | {event['event']} | {event['confidence']}{sources}{reason}")
    return "\n".join(lines)


def parse_playlist(path: Path) -> list[str]:
    try:
        lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
    except OSError:
        return []
    tracks = []
    for line in lines:
        text = line.strip()
        if not text or text.startswith("#"):
            continue
        tracks.append(_display_track(text, len(tracks) + 1))
    return tracks


def filesystem_tracks(path: Path, detected: AlbumArtifacts | None = None) -> list[str]:
    detected = detected or detect_artifacts(path)
    if not detected.available:
        return []
    tracks = sorted(detected.direct_audio_files)
    return [_display_track(item.name, index) for index, item in enumerate(tracks, start=1)]


def filesystem_listing(path: Path | None) -> dict[str, Any]:
    if not path or not path.exists() or not path.is_dir():
        return {"source": "missing", "path": "", "items": ["No archive folder available."]}
    try:
        children = sorted(path.iterdir(), key=lambda item: (item.name.lower(), item.is_file()))
    except OSError as exc:
        return {"source": "unreadable", "path": str(path), "items": [str(exc)]}
    items: list[str] = []
    for child in children:
        items.extend(_filesystem_listing_lines(child, 0))
    if not items:
        items.append("Album folder is empty.")
    return {"source": "filesystem", "path": str(path), "items": items}


def _filesystem_listing_lines(path: Path, depth: int) -> list[str]:
    prefix = "  " * depth
    if path.is_file():
        return [f"{prefix}{path.name}"]
    if not path.is_dir():
        return [f"{prefix}{path.name}"]
    lines = [f"{prefix}{path.name}"]
    try:
        children = sorted(path.iterdir(), key=lambda item: (item.name.lower(), item.is_file()))
    except OSError as exc:
        lines.append(f"{prefix}  {exc}")
        return lines
    for child in children:
        lines.extend(_filesystem_listing_lines(child, depth + 1))
    return lines


def metadata_tracks(album_id: Any, metadata: dict[str, Any]) -> list[str]:
    album = metadata.get("albums", {}).get(str(album_id), {})
    track_ids = album.get("track_ids", [])
    tracks = metadata.get("tracks", {})
    rows = [tracks.get(str(track_id), {}) for track_id in track_ids]
    rows = [row for row in rows if row]
    rows.sort(key=lambda row: (int(row.get("disc_number") or 1), int(row.get("track_number") or 0)))
    out = []
    for row in rows:
        number = int(row.get("track_number") or len(out) + 1)
        title = row.get("title") or "(unknown)"
        out.append(f"{number:02d} - {title}")
    return out


def _timeline_event(
    event: str,
    timestamp: Any,
    confidence: Any,
    reason: Any,
    sources: list[Any],
) -> dict[str, str]:
    return {
        "event": event,
        "timestamp": str(timestamp or ""),
        "confidence": _confidence(confidence, "MEDIUM"),
        "reason": str(reason or ""),
        "sources": ", ".join(str(source) for source in sources if source),
    }


def _first_timestamp(row: dict[str, Any], keys: tuple[str, ...]) -> str:
    for key in keys:
        value = row.get(key)
        if value:
            return str(value)
    timestamps = row.get("timestamps")
    if isinstance(timestamps, dict):
        for key in keys:
            value = timestamps.get(key)
            if value:
                return str(value)
    return ""


def _confidence(value: Any, fallback: str) -> str:
    text = str(value or "").strip().upper()
    if text in {"HIGH", "MEDIUM", "LOW", "NONE", "UNKNOWN"}:
        return text
    return fallback


def _source_list(*values: Any) -> list[Any]:
    return [value for value in values if value]


def _audit_passed(integrity: dict[str, Any], status: dict[str, Any]) -> bool:
    health = status.get("health_percent")
    try:
        health_value = int(health)
    except (TypeError, ValueError):
        health_value = 0
    warnings = integrity.get("warnings") if isinstance(integrity.get("warnings"), list) else []
    checks = integrity.get("checks") if isinstance(integrity.get("checks"), list) else []
    if checks and all(check.get("status") == "Present" for check in checks) and not warnings:
        return True
    return health_value >= 100


def first_file(path: Path | None, suffixes: set[str]) -> Path | None:
    if not path or not path.exists() or not path.is_dir():
        return None
    matches = sorted(detect_artifacts(path).matching_files(suffixes))
    return matches[0] if matches else None


def _display_track(value: str, index: int) -> str:
    name = Path(value).name
    stem = Path(name).stem if Path(name).suffix else name
    return f"{index:02d} - {stem}"
