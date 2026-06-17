from __future__ import annotations

from collections import Counter
from datetime import datetime
from pathlib import Path
from typing import Any

from curator.atomic import atomic_write_text

ARTIFACT_TYPES = ("nfo", "sfv", "playlist", "artwork", "validation_log")
ARTWORK_SUFFIXES = {".jpg", ".jpeg", ".png", ".webp"}


def detect_album_artifacts(album_path: Path) -> dict[str, Any]:
    files = list(album_path.iterdir()) if album_path.exists() and album_path.is_dir() else []
    nfo_files = [path for path in files if path.is_file() and path.suffix.lower() == ".nfo"]
    sfv_files = [path for path in files if path.is_file() and path.suffix.lower() == ".sfv"]
    playlist_files = [path for path in files if path.is_file() and path.suffix.lower() in {".m3u", ".m3u8"}]
    artwork_files = [path for path in files if path.is_file() and path.suffix.lower() in ARTWORK_SUFFIXES]
    validation_files = [path for path in files if path.is_file() and path.name == "STIGMA_VALIDATED.txt"]
    return {
        "folder": str(album_path),
        "exists": album_path.exists(),
        "nfo": bool(nfo_files),
        "sfv": bool(sfv_files),
        "playlist": bool(playlist_files),
        "artwork": bool(artwork_files),
        "validation_log": bool(validation_files),
        "counts": {
            "nfo": len(nfo_files),
            "sfv": len(sfv_files),
            "playlist": len(playlist_files),
            "artwork": len(artwork_files),
            "validation_log": len(validation_files),
        },
    }


def scan_archive_artifacts(album_paths: list[Path]) -> dict[str, Any]:
    albums = [detect_album_artifacts(path) for path in album_paths]
    counts = Counter()
    for album in albums:
        for artifact in ARTIFACT_TYPES:
            if album.get(artifact):
                counts[f"with_{artifact}"] += 1
            else:
                counts[f"missing_{artifact}"] += 1
    return {
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "total_albums_scanned": len(albums),
        "summary": dict(counts),
        "albums": albums,
    }


def album_paths_from_identity_registry(identity: dict[str, Any]) -> list[Path]:
    paths: list[Path] = []
    for row in identity.get("releases", []):
        path = row.get("validation", {}).get("validation_log_path")
        if path:
            paths.append(Path(path).parent)
    for row in identity.get("unresolved", []):
        path = row.get("path")
        if path:
            paths.append(Path(path).parent)
    return sorted(set(paths))


def render_archive_artifact_report(report: dict[str, Any]) -> str:
    summary = report.get("summary", {})
    lines = [
        "# Archive Artifact Report",
        "",
        f"Generated: {report.get('generated_at', 'unknown')}",
        "",
        f"Albums scanned: `{report.get('total_albums_scanned', 0)}`",
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
        lines.append(
            f"| {labels[artifact]} | {summary.get(f'with_{artifact}', 0)} | {summary.get(f'missing_{artifact}', 0)} |"
        )

    lines.extend(["", "## Albums", "", "| Folder | NFO | SFV | Playlist | Validation |", "| --- | --- | --- | --- | --- |"])
    for album in report.get("albums", [])[:500]:
        lines.append(
            f"| `{_escape(album.get('folder'))}` | {_yes(album.get('nfo'))} | {_yes(album.get('sfv'))} | "
            f"{_yes(album.get('playlist'))} | {_yes(album.get('validation_log'))} |"
        )
    return "\n".join(lines) + "\n"


def write_archive_artifact_report(report: dict[str, Any], reports_dir: Path) -> None:
    reports_dir.mkdir(parents=True, exist_ok=True)
    atomic_write_text(reports_dir / "archive_artifact_report.md", render_archive_artifact_report(report))


def _yes(value: Any) -> str:
    return "yes" if value else "no"


def _escape(value: Any) -> str:
    return str(value or "").replace("|", "\\|").replace("\n", " ").strip()
