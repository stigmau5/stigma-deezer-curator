from __future__ import annotations

import re
from collections import Counter
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

from curator.atomic import atomic_write_text

ARTIFACT_TYPES = ("nfo", "sfv", "playlist", "artwork", "validation_log")
CANONICAL_ARTIFACT_TYPES = ("audio", "artwork", "nfo", "sfv", "playlist", "validation")
AUDIO_SUFFIXES = {".flac", ".mp3", ".m4a", ".ogg", ".opus", ".wav", ".aiff"}
ARTWORK_SUFFIXES = {".jpg", ".jpeg", ".png", ".webp"}
PLAYLIST_SUFFIXES = {".m3u", ".m3u8"}
PREFERRED_ARTWORK_FILENAMES = ("cover.jpg", "folder.jpg", "front.jpg", "cover.png", "folder.png")
VALIDATION_MARKER_FILENAME = "STIGMA_VALIDATED.txt"
DISC_FOLDER_PATTERN = re.compile(r"^(cd|disc)[ _-]?\d+$", re.IGNORECASE)


@dataclass(frozen=True)
class AlbumArtifacts:
    folder: Path
    exists: bool
    available: bool
    files: dict[str, tuple[Path, ...]]
    root_files: tuple[Path, ...]
    direct_audio_files: tuple[Path, ...]
    selected_artwork: Path | None

    def files_for(self, artifact: str) -> tuple[Path, ...]:
        return self.files.get(artifact, ())

    def present(self, artifact: str) -> bool:
        return bool(self.files_for(artifact))

    def count(self, artifact: str) -> int:
        return len(self.files_for(artifact))

    def first_file(self, artifact: str) -> Path | None:
        files = self.files_for(artifact)
        return sorted(files)[0] if files else None

    def preferred_file(self, artifact: str, filenames: tuple[str, ...] = ()) -> Path | None:
        files = self.files_for(artifact)
        by_name = {path.name.lower(): path for path in files}
        for filename in filenames:
            selected = by_name.get(filename.lower())
            if selected:
                return selected
        return self.first_file(artifact)

    def named_file(self, filename: str, *, case_sensitive: bool = True) -> Path | None:
        if case_sensitive:
            return next((path for path in self.root_files if path.name == filename), None)
        by_name = {path.name.lower(): path for path in self.root_files}
        return by_name.get(filename.lower())

    def matching_files(self, suffixes: set[str]) -> list[Path]:
        normalized = {suffix.lower() for suffix in suffixes}
        return sorted(
            (path for paths in self.files.values() for path in paths if path.parent == self.folder and path.suffix.lower() in normalized),
            key=lambda path: path.name.lower(),
        )

    def to_dict(self) -> dict[str, Any]:
        validation_count = self.count("validation")
        return {
            "folder": str(self.folder),
            "exists": self.exists,
            "nfo": self.present("nfo"),
            "sfv": self.present("sfv"),
            "playlist": self.present("playlist"),
            "artwork": self.present("artwork"),
            "artwork_path": str(self.selected_artwork) if self.selected_artwork else "",
            "artwork_name": self.selected_artwork.name if self.selected_artwork else "",
            "validation_log": bool(validation_count),
            "counts": {
                "nfo": self.count("nfo"),
                "sfv": self.count("sfv"),
                "playlist": self.count("playlist"),
                "artwork": self.count("artwork"),
                "validation_log": validation_count,
            },
        }

    def to_canonical_dict(self) -> dict[str, Any]:
        return {
            "folder": str(self.folder),
            "exists": self.exists,
            "available": self.available,
            "artifacts": {
                artifact: {
                    "present": self.present(artifact),
                    "count": self.count(artifact),
                    "paths": [str(path) for path in sorted(self.files_for(artifact))],
                }
                for artifact in CANONICAL_ARTIFACT_TYPES
            },
            "selected_artwork": str(self.selected_artwork) if self.selected_artwork else "",
        }


def detect_artifacts(album_path: str | Path | None) -> AlbumArtifacts:
    path = Path(album_path) if album_path else Path("")
    exists = bool(album_path) and path.exists()
    available = exists and path.is_dir()
    try:
        root_files = tuple(item for item in path.iterdir() if item.is_file()) if available else ()
    except OSError:
        root_files = ()
    direct_audio = tuple(item for item in root_files if item.suffix.lower() in AUDIO_SUFFIXES)
    disc_audio: list[Path] = []
    if available:
        for folder in _disc_folders(path):
            try:
                disc_audio.extend(item for item in folder.iterdir() if item.is_file() and item.suffix.lower() in AUDIO_SUFFIXES)
            except OSError:
                continue
    files = {
        "audio": direct_audio + tuple(disc_audio),
        "artwork": tuple(item for item in root_files if item.suffix.lower() in ARTWORK_SUFFIXES),
        "nfo": tuple(item for item in root_files if item.suffix.lower() == ".nfo"),
        "sfv": tuple(item for item in root_files if item.suffix.lower() == ".sfv"),
        "playlist": tuple(item for item in root_files if item.suffix.lower() in PLAYLIST_SUFFIXES),
        "validation": tuple(item for item in root_files if item.name == VALIDATION_MARKER_FILENAME),
    }
    artwork = _select_preferred(files["artwork"], PREFERRED_ARTWORK_FILENAMES, casefold_sort=True)
    return AlbumArtifacts(path, exists, available, files, root_files, direct_audio, artwork)


def detect_album_artifacts(album_path: Path) -> dict[str, Any]:
    return detect_artifacts(album_path).to_dict()


def select_artwork_file(album_path: Path, artwork_files: list[Path] | None = None) -> Path | None:
    if not album_path.exists() or not album_path.is_dir():
        return None
    if artwork_files is None:
        return detect_artifacts(album_path).selected_artwork
    return _select_preferred(tuple(artwork_files), PREFERRED_ARTWORK_FILENAMES, casefold_sort=True)


def is_disc_folder(path: Path) -> bool:
    return bool(DISC_FOLDER_PATTERN.match(path.name.strip()))


def _disc_folders(album_path: Path) -> list[Path]:
    try:
        return sorted(
            (path for path in album_path.iterdir() if path.is_dir() and is_disc_folder(path)),
            key=lambda path: path.name.lower(),
        )
    except OSError:
        return []


def _select_preferred(
    files: tuple[Path, ...],
    filenames: tuple[str, ...],
    *,
    casefold_sort: bool = False,
) -> Path | None:
    by_name = {path.name.lower(): path for path in files}
    for filename in filenames:
        selected = by_name.get(filename.lower())
        if selected:
            return selected
    if not files:
        return None
    return sorted(files, key=lambda path: path.name.lower())[0] if casefold_sort else sorted(files)[0]


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
