from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from audio_division.closed_loop_monitor import DEFAULT_SOURCE, folder_identity_key, incoming_sources
from audio_division.lifecycle_state import (
    STATE_READY_FOR_PROCESSING,
    STATE_VALIDATED,
    detect_lifecycle_state,
)
from audio_division.physical_archive import split_folder_name


STATUS_DOWNLOADED = "Downloaded"
STATUS_ALREADY_ARCHIVED = "Already Archived"
STATUS_ALREADY_VALIDATED = "Already Validated"
STATUS_READY_TO_VALIDATE = "Ready To Validate"
STATUS_DUPLICATE_DOWNLOAD = "Duplicate Download"
STATUS_UNKNOWN = "Unknown"

INCOMING_STATUSES = (
    STATUS_DOWNLOADED,
    STATUS_ALREADY_ARCHIVED,
    STATUS_ALREADY_VALIDATED,
    STATUS_READY_TO_VALIDATE,
    STATUS_DUPLICATE_DOWNLOAD,
    STATUS_UNKNOWN,
)


@dataclass(frozen=True)
class IncomingRelease:
    artist: str
    title: str
    folder: str
    source: str = DEFAULT_SOURCE
    deezer_album_id: str = ""
    release_type: str = ""
    year: str = ""
    url: str = ""
    status: str = STATUS_UNKNOWN
    lifecycle_state: str = ""
    archive_path: str = ""
    metadata_status: str = ""
    identity_confidence: str = "UNKNOWN"
    identity_key: str = ""
    duplicate_key: str = ""
    evidence: tuple[str, ...] = field(default_factory=tuple)

    @property
    def album(self) -> str:
        return self.title

    def to_row(self) -> dict[str, Any]:
        return {
            "artist": self.artist,
            "album": self.title,
            "title": self.title,
            "folder": self.folder,
            "source": self.source,
            "album_id": self.deezer_album_id,
            "deezer_album_id": self.deezer_album_id,
            "release_type": self.release_type,
            "year": self.year,
            "url": self.url,
            "state": self.status,
            "status": self.status,
            "lifecycle_state": self.lifecycle_state,
            "archive_path": self.archive_path,
            "metadata_status": self.metadata_status,
            "identity_confidence": self.identity_confidence,
            "identity_key": self.identity_key,
            "duplicate_key": self.duplicate_key,
            "evidence": list(self.evidence),
        }


def incoming_releases(
    settings: dict[str, Any],
    *,
    identity_registry: dict[str, Any] | None = None,
    lifecycle_registry: dict[str, Any] | None = None,
    archive_registry: dict[str, Any] | None = None,
    metadata_cache: dict[str, Any] | None = None,
    processing_queue: dict[str, Any] | None = None,
) -> list[IncomingRelease]:
    identity_registry = identity_registry or {}
    lifecycle_registry = lifecycle_registry or {}
    archive_registry = archive_registry or {}
    metadata_cache = metadata_cache or {}
    processing_queue = processing_queue or {}

    context = _ProjectionContext(
        identities=_identity_candidates(identity_registry),
        lifecycle_by_id=_lifecycle_by_id(lifecycle_registry),
        archive_by_folder=_archive_by_folder(archive_registry),
        archive_by_album_id=_archive_by_album_id(archive_registry, identity_registry),
        metadata=metadata_cache.get("albums", {}) if isinstance(metadata_cache.get("albums"), dict) else {},
        queue=processing_queue,
    )

    releases: list[IncomingRelease] = []
    for source in incoming_sources(settings):
        root = Path(source["root"]).expanduser()
        releases.extend(_scan_source(root, source.get("source") or DEFAULT_SOURCE, context))
    return _mark_duplicates(sorted(releases, key=lambda item: (item.source.lower(), item.artist.lower(), item.title.lower(), item.folder.lower())))


@dataclass(frozen=True)
class _ProjectionContext:
    identities: list[dict[str, Any]]
    lifecycle_by_id: dict[str, dict[str, Any]]
    archive_by_folder: dict[str, dict[str, Any]]
    archive_by_album_id: dict[str, dict[str, Any]]
    metadata: dict[str, Any]
    queue: dict[str, Any]


def _scan_source(root: Path, source: str, context: _ProjectionContext) -> list[IncomingRelease]:
    if not root.exists() or not root.is_dir():
        return []
    rows = []
    for folder in sorted((item for item in root.iterdir() if item.is_dir()), key=lambda item: item.name.lower()):
        rows.append(_project_folder(folder, source, context))
    return rows


def _project_folder(folder: Path, source: str, context: _ProjectionContext) -> IncomingRelease:
    parsed_artist, parsed_title = split_folder_name(folder.name)
    identity_key = folder_identity_key(folder.name)
    identity = _match_identity(context.identities, identity_key, parsed_artist, parsed_title)
    discovery = identity.get("discovery_identity", {})
    album_id = str(discovery.get("deezer_album_id") or "")
    artist = str(discovery.get("artist") or parsed_artist or "")
    title = str(discovery.get("title") or parsed_title or folder.name)
    archive_row = context.archive_by_album_id.get(album_id, {}) if album_id else {}
    archive_row = archive_row or context.archive_by_folder.get(identity_key, {})
    lifecycle = context.lifecycle_by_id.get(album_id, {}) if album_id else {}
    metadata_status = "CACHED" if album_id and album_id in context.metadata else ("AVAILABLE_NOT_CACHED" if album_id else "")
    pipeline = detect_lifecycle_state(
        {
            "artist": artist,
            "album": title,
            "album_id": album_id,
            "folder": str(folder),
            "archive_path": "",
            "validation_evidence": lifecycle.get("validation_evidence", {}),
        },
        context.queue.get("albums", {}).get(str(folder), {}),
    )
    evidence = set(pipeline.evidence)
    if identity:
        evidence.add("identity_registry")
    if archive_row:
        evidence.add("archive_registry")
    if lifecycle:
        evidence.add("lifecycle")
    if metadata_status == "CACHED":
        evidence.add("metadata")
    status = _incoming_status(
        folder=folder,
        artist=artist,
        title=title,
        archive_row=archive_row,
        lifecycle=lifecycle,
        pipeline_state=pipeline.state,
        identity_key=identity_key,
    )
    duplicate_key = album_id or folder_identity_key(f"{artist}-{title}") or identity_key
    return IncomingRelease(
        artist=artist,
        title=title,
        folder=str(folder),
        source=source,
        deezer_album_id=album_id,
        release_type=str(discovery.get("type") or ""),
        year=_release_year(discovery, lifecycle),
        url=f"https://www.deezer.com/album/{album_id}" if album_id else "",
        status=status,
        lifecycle_state=str(lifecycle.get("highest_state") or pipeline.state),
        archive_path=str(archive_row.get("archive_path") or ""),
        metadata_status=metadata_status,
        identity_confidence=str(identity.get("identity_confidence") or "UNKNOWN"),
        identity_key=identity_key,
        duplicate_key=duplicate_key,
        evidence=tuple(sorted(evidence)),
    )


def _incoming_status(
    *,
    folder: Path,
    artist: str,
    title: str,
    archive_row: dict[str, Any],
    lifecycle: dict[str, Any],
    pipeline_state: str,
    identity_key: str,
) -> str:
    if archive_row.get("archive_path"):
        return STATUS_ALREADY_ARCHIVED
    lifecycle_state = str(lifecycle.get("highest_state") or "").upper()
    if lifecycle_state in {STATE_VALIDATED, STATE_READY_FOR_PROCESSING} or pipeline_state == STATE_READY_FOR_PROCESSING:
        return STATUS_ALREADY_VALIDATED
    if not artist or not title or not identity_key:
        return STATUS_UNKNOWN
    if _has_audio(folder):
        return STATUS_READY_TO_VALIDATE
    return STATUS_DOWNLOADED


def _mark_duplicates(releases: list[IncomingRelease]) -> list[IncomingRelease]:
    counts: dict[str, int] = {}
    for release in releases:
        if release.duplicate_key:
            counts[release.duplicate_key] = counts.get(release.duplicate_key, 0) + 1
    marked = []
    for release in releases:
        if release.duplicate_key and counts.get(release.duplicate_key, 0) > 1 and release.status not in {
            STATUS_ALREADY_ARCHIVED,
            STATUS_ALREADY_VALIDATED,
        }:
            marked.append(
                IncomingRelease(
                    **{
                        **release.__dict__,
                        "status": STATUS_DUPLICATE_DOWNLOAD,
                        "evidence": tuple(sorted(set(release.evidence) | {"duplicate_download"})),
                    }
                )
            )
        else:
            marked.append(release)
    return marked


def _identity_candidates(identity_registry: dict[str, Any]) -> list[dict[str, Any]]:
    return [release for release in identity_registry.get("releases", []) if isinstance(release, dict)]


def _match_identity(candidates: list[dict[str, Any]], folder_key: str, artist: str, title: str) -> dict[str, Any]:
    artist_key = folder_identity_key(artist)
    title_key = folder_identity_key(title)
    for candidate in candidates:
        archive_folder = candidate.get("archive_identity", {}).get("folder")
        if folder_key and folder_identity_key(archive_folder) == folder_key:
            return candidate
    for candidate in candidates:
        discovery = candidate.get("discovery_identity", {})
        candidate_artist = folder_identity_key(discovery.get("artist"))
        candidate_title = folder_identity_key(discovery.get("title"))
        if artist_key and candidate_artist != artist_key:
            continue
        if title_key and (candidate_title == title_key or candidate_title in folder_key):
            return candidate
    return {}


def _lifecycle_by_id(lifecycle_registry: dict[str, Any]) -> dict[str, dict[str, Any]]:
    rows = lifecycle_registry.get("albums", [])
    return {
        str(row.get("album_id")): row
        for row in rows
        if isinstance(row, dict) and row.get("album_id")
    }


def _archive_by_folder(archive_registry: dict[str, Any]) -> dict[str, dict[str, Any]]:
    rows = archive_registry.get("albums", [])
    lookup = {}
    for row in rows:
        if not isinstance(row, dict):
            continue
        for value in (row.get("archive_folder"), row.get("name"), Path(str(row.get("archive_path") or "")).name):
            key = folder_identity_key(value)
            if key:
                lookup[key] = row
    return lookup


def _archive_by_album_id(archive_registry: dict[str, Any], identity_registry: dict[str, Any]) -> dict[str, dict[str, Any]]:
    by_folder = _archive_by_folder(archive_registry)
    lookup = {}
    for identity in identity_registry.get("releases", []):
        if not isinstance(identity, dict):
            continue
        album_id = str(identity.get("discovery_identity", {}).get("deezer_album_id") or "")
        folder_key = folder_identity_key(identity.get("archive_identity", {}).get("folder"))
        if album_id and folder_key in by_folder:
            lookup[album_id] = by_folder[folder_key]
    return lookup


def _release_year(discovery: dict[str, Any], lifecycle: dict[str, Any]) -> str:
    for value in (discovery.get("year"), lifecycle.get("year")):
        text = str(value or "")
        if len(text) >= 4:
            return text[:4]
    return ""


def _has_audio(folder: Path) -> bool:
    audio_suffixes = {".flac", ".mp3", ".m4a", ".wav", ".aiff", ".alac"}
    try:
        return any(item.is_file() and item.suffix.lower() in audio_suffixes for item in folder.rglob("*"))
    except OSError:
        return False
