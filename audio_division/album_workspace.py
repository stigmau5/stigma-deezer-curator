from __future__ import annotations

from pathlib import Path
from typing import Any

from audio_division.album_presentation import album_presentation
from audio_division.archive_registry import AUDIO_SUFFIXES
from audio_division.cover_widget import album_cover_info
from audio_division.playback import playback_summary

PLAYLIST_SUFFIXES = {".m3u", ".m3u8"}
NFO_READ_LIMIT = 20000


def album_workspace(details: dict[str, Any], metadata: dict[str, Any] | None = None) -> dict[str, Any]:
    presentation = album_presentation(details)
    archive_path = Path(details.get("archive_path", "")) if details.get("archive_path") else None
    cover = cover_info(details, archive_path)
    nfo = nfo_info(archive_path)
    tracklist = tracklist_info(archive_path, details, metadata or {})
    files = filesystem_listing(archive_path)
    status = details.get("album_status", {})
    readiness = details.get("archive_readiness", {})
    return {
        "presentation": presentation,
        "cover": cover,
        "status_glance": status_glance(status, readiness),
        "nfo": nfo,
        "tracklist": tracklist,
        "files": files,
        "playback": playback_summary(details),
    }


def cover_info(details: dict[str, Any], archive_path: Path | None = None) -> dict[str, Any]:
    return album_cover_info(details, archive_path)


def nfo_info(archive_path: Path | None) -> dict[str, Any]:
    nfo = first_file(archive_path, {".nfo"}) if archive_path else None
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
) -> dict[str, Any]:
    if archive_path:
        playlist = first_file(archive_path, PLAYLIST_SUFFIXES)
        if playlist:
            tracks = parse_playlist(playlist)
            if tracks:
                return {"source": "playlist", "path": str(playlist), "tracks": tracks}

        tracks = filesystem_tracks(archive_path)
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
        ("NFO", items.get("nfo", "Unknown")),
        ("SFV", items.get("sfv", "Unknown")),
        ("Playlist", items.get("playlist", "Unknown")),
        ("Artwork", items.get("artwork", "Unknown")),
        ("Readiness", readiness.get("state", "UNKNOWN")),
        ("Health", f"{status.get('health_percent', 0)}%"),
    ]


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


def filesystem_tracks(path: Path) -> list[str]:
    if not path.exists() or not path.is_dir():
        return []
    tracks = sorted(item for item in path.iterdir() if item.is_file() and item.suffix.lower() in AUDIO_SUFFIXES)
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


def first_file(path: Path | None, suffixes: set[str]) -> Path | None:
    if not path or not path.exists() or not path.is_dir():
        return None
    matches = sorted(item for item in path.iterdir() if item.is_file() and item.suffix.lower() in suffixes)
    return matches[0] if matches else None


def _display_track(value: str, index: int) -> str:
    name = Path(value).name
    stem = Path(name).stem if Path(name).suffix else name
    return f"{index:02d} - {stem}"
