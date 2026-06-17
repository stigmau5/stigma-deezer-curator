from __future__ import annotations

import json
from collections import Counter
from datetime import datetime
from pathlib import Path
from typing import Any

from audio_division.artifacts import ARTIFACT_TYPES, detect_album_artifacts
from curator.atomic import atomic_write_text

AUDIO_SUFFIXES = {".flac", ".mp3", ".m4a", ".ogg", ".opus", ".wav", ".aiff"}
REGISTRY_SCHEMA = 1


def discover_album_folders(archive_root: Path) -> list[Path]:
    if not archive_root.exists() or not archive_root.is_dir():
        return []
    return sorted(path for path in archive_root.rglob("*") if path.is_dir() and _looks_like_album_folder(path))


def build_archive_registry(archive_root: Path) -> dict[str, Any]:
    albums = [album_entry(path, archive_root) for path in discover_album_folders(archive_root)]
    return {
        "schema": REGISTRY_SCHEMA,
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "archive_root": str(archive_root),
        "summary": archive_registry_summary(albums),
        "albums": albums,
    }


def album_entry(album_path: Path, archive_root: Path) -> dict[str, Any]:
    artifacts = detect_album_artifacts(album_path)
    track_count = count_audio_tracks(album_path)
    return {
        "name": album_path.name,
        "archive_path": str(album_path),
        "relative_path": _relative(album_path, archive_root),
        "track_count": track_count,
        "artifacts": artifacts,
    }


def count_audio_tracks(album_path: Path) -> int:
    if not album_path.exists() or not album_path.is_dir():
        return 0
    return sum(1 for path in album_path.iterdir() if path.is_file() and path.suffix.lower() in AUDIO_SUFFIXES)


def archive_registry_summary(albums: list[dict[str, Any]]) -> dict[str, Any]:
    artifacts = Counter()
    total_tracks = 0
    for album in albums:
        total_tracks += int(album.get("track_count") or 0)
        album_artifacts = album.get("artifacts", {})
        for artifact in ARTIFACT_TYPES:
            if album_artifacts.get(artifact):
                artifacts[f"with_{artifact}"] += 1
            else:
                artifacts[f"missing_{artifact}"] += 1
    return {
        "album_folders": len(albums),
        "total_tracks": total_tracks,
        "artifacts": dict(artifacts),
    }


def render_archive_registry_report(registry: dict[str, Any]) -> str:
    summary = registry.get("summary", {})
    lines = [
        "# Archive Registry Report",
        "",
        f"Generated: {registry.get('generated_at', 'unknown')}",
        f"Archive root: `{_escape(registry.get('archive_root'))}`",
        "",
        f"- Album folders: `{summary.get('album_folders', 0)}`",
        f"- Audio tracks: `{summary.get('total_tracks', 0)}`",
        "",
        "| Album | Tracks | Path |",
        "| --- | ---: | --- |",
    ]
    for album in registry.get("albums", [])[:500]:
        lines.append(f"| {_escape(album.get('name'))} | {album.get('track_count', 0)} | `{_escape(album.get('relative_path'))}` |")
    return "\n".join(lines) + "\n"


def render_artifact_coverage_report(registry: dict[str, Any]) -> str:
    artifacts = registry.get("summary", {}).get("artifacts", {})
    lines = [
        "# Archive Artifact Coverage Report",
        "",
        f"Album folders: `{registry.get('summary', {}).get('album_folders', 0)}`",
        "",
        "| Artifact | Present | Missing |",
        "| --- | ---: | ---: |",
    ]
    labels = {
        "nfo": "NFO",
        "sfv": "SFV",
        "playlist": "Playlist",
        "artwork": "Artwork",
        "validation_log": "Validation Evidence",
    }
    for artifact in ARTIFACT_TYPES:
        lines.append(f"| {labels[artifact]} | {artifacts.get(f'with_{artifact}', 0)} | {artifacts.get(f'missing_{artifact}', 0)} |")
    return "\n".join(lines) + "\n"


def write_archive_registry(registry: dict[str, Any], data_dir: Path, reports_dir: Path) -> None:
    data_dir.mkdir(parents=True, exist_ok=True)
    reports_dir.mkdir(parents=True, exist_ok=True)
    atomic_write_text(data_dir / "archive_registry.json", json.dumps(registry, ensure_ascii=False, indent=2, sort_keys=True) + "\n")
    atomic_write_text(reports_dir / "archive_registry_report.md", render_archive_registry_report(registry))
    atomic_write_text(reports_dir / "archive_artifact_coverage_report.md", render_artifact_coverage_report(registry))


def _looks_like_album_folder(path: Path) -> bool:
    try:
        files = list(path.iterdir())
    except OSError:
        return False
    return any(item.is_file() and item.suffix.lower() in AUDIO_SUFFIXES for item in files)


def _relative(path: Path, root: Path) -> str:
    try:
        return str(path.relative_to(root))
    except ValueError:
        return str(path)


def _escape(value: Any) -> str:
    return str(value or "").replace("|", "\\|").replace("\n", " ").strip()
