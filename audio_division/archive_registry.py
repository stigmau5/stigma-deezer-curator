from __future__ import annotations

import json
import re
from collections import Counter
from datetime import datetime
from pathlib import Path
from typing import Any

from audio_division.artifacts import ARTIFACT_TYPES, detect_album_artifacts
from curator.atomic import atomic_write_text

AUDIO_SUFFIXES = {".flac", ".mp3", ".m4a", ".ogg", ".opus", ".wav", ".aiff"}
ALBUM_CATEGORIES = {"Albums", "EPs", "Singles", "Live"}
DISC_FOLDER_PATTERN = re.compile(r"^(cd|disc)[ _-]?\d+$", re.IGNORECASE)
REGISTRY_SCHEMA = 1


def discover_album_folders(archive_root: Path) -> list[Path]:
    if not archive_root.exists() or not archive_root.is_dir():
        return []
    return sorted(path for path in archive_root.rglob("*") if path.is_dir() and is_album_root(path, archive_root))


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
    total = count_direct_audio_tracks(album_path)
    for folder in disc_folders(album_path):
        total += count_direct_audio_tracks(folder)
    return total


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


def is_album_root(path: Path, archive_root: Path) -> bool:
    if is_disc_folder(path):
        return False
    try:
        parts = path.relative_to(archive_root).parts
    except ValueError:
        return False
    category_indexes = [index for index, part in enumerate(parts) if part in ALBUM_CATEGORIES]
    if not category_indexes:
        return False
    category_index = category_indexes[-1]
    if len(parts) != category_index + 2:
        return False
    return has_album_evidence(path)


def has_album_evidence(path: Path) -> bool:
    try:
        children = list(path.iterdir())
    except OSError:
        return False
    return (
        count_direct_audio_tracks(path) > 0
        or has_album_artifacts(path)
        or any(child.is_dir() and is_disc_folder(child) and count_direct_audio_tracks(child) > 0 for child in children)
    )


def is_disc_folder(path: Path) -> bool:
    return bool(DISC_FOLDER_PATTERN.match(path.name.strip()))


def disc_folders(album_path: Path) -> list[Path]:
    try:
        return sorted(
            (path for path in album_path.iterdir() if path.is_dir() and is_disc_folder(path)),
            key=lambda path: path.name.lower(),
        )
    except OSError:
        return []


def count_direct_audio_tracks(path: Path) -> int:
    try:
        return sum(1 for item in path.iterdir() if item.is_file() and item.suffix.lower() in AUDIO_SUFFIXES)
    except OSError:
        return 0


def has_album_artifacts(path: Path) -> bool:
    artifacts = detect_album_artifacts(path)
    return any(artifacts.get(name) for name in ARTIFACT_TYPES)


def _relative(path: Path, root: Path) -> str:
    try:
        return str(path.relative_to(root))
    except ValueError:
        return str(path)


def _escape(value: Any) -> str:
    return str(value or "").replace("|", "\\|").replace("\n", " ").strip()
