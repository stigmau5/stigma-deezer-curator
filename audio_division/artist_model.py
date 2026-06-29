from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from audio_division.album_truth import album_truth
from audio_division.metadata_status import album_metadata_status
from audio_division.validation_truth import (
    merge_validation_evidence,
    validation_evidence_from_identity_release,
    validation_evidence_from_lifecycle_row,
    validation_evidence_from_validated_index,
)


SECTION_TYPES = {
    "Albums": "album",
    "EPs": "ep",
    "Singles": "single",
    "Live": "live",
    "Compilations": "compilation",
}
SECTION_NAMES = {f"# {name}": name for name in SECTION_TYPES}
ALBUM_ID_RE = re.compile(r"(?:/[a-z]{2})?/album/(\d+)", re.IGNORECASE)
ARTIST_ID_RE = re.compile(r"(?:/[a-z]{2})?/artist/(\d+)", re.IGNORECASE)


@dataclass(frozen=True)
class Release:
    deezer_album_id: str
    title: str
    year: str
    type: str
    url: str
    archive_status: str
    lifecycle_state: str
    validation_status: str
    metadata_status: str
    acquisition_status: str = "Needs Download"
    archive_path: str = ""
    identity_confidence: str = "UNKNOWN"
    album_truth: dict[str, Any] = field(default_factory=dict)
    source_section: str = ""
    source_line_number: int = 0
    source_line: str = ""
    flags: tuple[str, ...] = field(default_factory=tuple)

    @property
    def is_live(self) -> bool:
        return self.type == "live" or any(flag.upper().startswith("LIVE") for flag in self.flags)

    @property
    def is_compilation(self) -> bool:
        return self.type == "compilation" or any("COMPILATION" in flag.upper() for flag in self.flags)


@dataclass(frozen=True)
class Artist:
    artist_name: str
    deezer_artist_id: str | None
    albums: tuple[Release, ...]
    eps: tuple[Release, ...]
    singles: tuple[Release, ...]
    live: tuple[Release, ...]
    compilations: tuple[Release, ...]
    total_release_count: int
    last_updated: str
    source_file: Path
    releases: tuple[Release, ...] = field(default_factory=tuple)
    source_text: str = ""


def load_artist_file(path: Path, data_dir: Path | None = None) -> Artist:
    data_dir = Path(data_dir) if data_dir else path.parent.parent
    return parse_artist_text(
        path.read_text(encoding="utf-8"),
        source_file=path,
        lifecycle_registry=_load_json(data_dir / "lifecycle_registry.json"),
        metadata_cache=_load_json(data_dir / "metadata_cache.json"),
        validated_index=_load_json(data_dir / "validated_albums.json"),
        archive_registry=_load_json(data_dir / "archive_registry.json"),
        identity_registry=_load_json(data_dir / "identity_registry.json"),
    )


def parse_artist_text(
    text: str,
    *,
    source_file: Path,
    lifecycle_registry: dict[str, Any] | None = None,
    metadata_cache: dict[str, Any] | None = None,
    validated_index: dict[str, Any] | None = None,
    archive_registry: dict[str, Any] | None = None,
    identity_registry: dict[str, Any] | None = None,
) -> Artist:
    lifecycle_registry = lifecycle_registry or {}
    metadata_cache = metadata_cache or {}
    validated_index = validated_index or {}
    archive_registry = archive_registry or {}
    identity_registry = identity_registry or {}
    lifecycle_by_id = _lifecycle_by_album_id(lifecycle_registry)
    identity_by_id = _identity_by_album_id(identity_registry)
    archive_by_folder = _archive_by_folder(archive_registry)

    artist_name = _artist_name(text, source_file)
    deezer_artist_id = _deezer_artist_id(text)
    last_updated = _expanded_at(text)
    current_section = ""
    releases: list[Release] = []

    for line_number, line in enumerate(text.splitlines(), start=1):
        stripped = line.strip()
        if stripped in SECTION_NAMES:
            current_section = SECTION_NAMES[stripped]
            continue
        if not stripped.startswith("http"):
            continue
        release = parse_release_line(
            stripped,
            source_section=current_section,
            source_line_number=line_number,
            lifecycle_by_id=lifecycle_by_id,
            metadata_cache=metadata_cache,
            validated_index=validated_index,
            identity_by_id=identity_by_id,
            archive_by_folder=archive_by_folder,
        )
        if release:
            releases.append(release)

    albums = tuple(release for release in releases if release.source_section == "Albums")
    eps = tuple(release for release in releases if release.source_section == "EPs")
    singles = tuple(release for release in releases if release.source_section == "Singles")
    live = tuple(release for release in releases if release.is_live or release.source_section == "Live")
    compilations = tuple(
        release
        for release in releases
        if release.is_compilation or release.source_section == "Compilations"
    )
    return Artist(
        artist_name=artist_name,
        deezer_artist_id=deezer_artist_id,
        albums=albums,
        eps=eps,
        singles=singles,
        live=live,
        compilations=compilations,
        total_release_count=len(releases),
        last_updated=last_updated,
        source_file=source_file,
        releases=tuple(releases),
        source_text=text,
    )


def parse_release_line(
    line: str,
    *,
    source_section: str,
    source_line_number: int,
    lifecycle_by_id: dict[str, dict[str, Any]] | None = None,
    metadata_cache: dict[str, Any] | None = None,
    validated_index: dict[str, Any] | None = None,
    identity_by_id: dict[str, dict[str, Any]] | None = None,
    archive_by_folder: dict[str, dict[str, Any]] | None = None,
) -> Release | None:
    url = line.split()[0]
    album_id = _album_id(url)
    if not album_id:
        return None
    annotation = line.split("#", 1)[1] if "#" in line else ""
    parts = [part.strip() for part in annotation.split("|")]
    release_type = _release_type(parts[0] if parts else "", source_section)
    title = parts[1] if len(parts) > 1 and parts[1] else url
    year = _year(parts[2] if len(parts) > 2 else "")
    flags = tuple(part for part in parts[4:] if part)

    lifecycle_by_id = lifecycle_by_id or {}
    metadata_cache = metadata_cache or {}
    validated_index = validated_index or {}
    identity_by_id = identity_by_id or {}
    archive_by_folder = archive_by_folder or {}
    lifecycle = lifecycle_by_id.get(album_id, {})
    identity_release = identity_by_id.get(album_id, {})
    archive_row = _archive_row_for_release(identity_release, archive_by_folder)
    metadata_state = album_metadata_status(album_id, metadata_cache)["state"]
    truth = _release_truth(
        artist=str(identity_release.get("discovery_identity", {}).get("artist") or ""),
        title=title,
        album_id=album_id,
        lifecycle=lifecycle,
        identity_release=identity_release,
        archive_row=archive_row,
        metadata_state=metadata_state,
        metadata_cache=metadata_cache,
        validated_index=validated_index,
    )
    lifecycle_state = str(lifecycle.get("highest_state") or "DISCOVERED")
    validation_status = _validation_status(album_id, lifecycle, validated_index, identity_release)
    return Release(
        deezer_album_id=album_id,
        title=title,
        year=year,
        type=release_type,
        url=url,
        archive_status=_archive_status(lifecycle, archive_row),
        lifecycle_state=lifecycle_state,
        validation_status=validation_status,
        metadata_status=metadata_state,
        acquisition_status=_acquisition_status(
            archive_row=archive_row,
            lifecycle=lifecycle,
            validation_status=validation_status,
            metadata_status=metadata_state,
            identity_release=identity_release,
            truth=truth,
        ),
        archive_path=str(archive_row.get("archive_path") or ""),
        identity_confidence=str(identity_release.get("identity_confidence") or "UNKNOWN"),
        album_truth=truth,
        source_section=source_section,
        source_line_number=source_line_number,
        source_line=line,
        flags=flags,
    )


def render_artist_text(artist: Artist) -> str:
    return artist.source_text


def release_line_map(artist: Artist) -> dict[int, Release]:
    return {
        release.source_line_number: release
        for release in artist.releases
        if release.source_line_number > 0
    }


def releases_for_section(artist: Artist, section_name: str) -> tuple[Release, ...]:
    if section_name == "Albums":
        return artist.albums
    if section_name == "EPs":
        return artist.eps
    if section_name == "Singles":
        return artist.singles
    if section_name == "Live":
        return artist.live
    if section_name == "Compilations":
        return artist.compilations
    return tuple()


def _artist_name(text: str, source_file: Path) -> str:
    for line in text.splitlines():
        if line.startswith("# Artist:"):
            name = line.split(":", 1)[1].strip()
            if name:
                return name
    return source_file.stem.replace("_", " ")


def _deezer_artist_id(text: str) -> str | None:
    for line in text.splitlines():
        if "deezer.com" not in line or "/artist/" not in line:
            continue
        match = ARTIST_ID_RE.search(line)
        if match:
            return match.group(1)
    return None


def _expanded_at(text: str) -> str:
    for line in text.splitlines():
        if line.startswith("# expanded_at:"):
            return line.split(":", 1)[1].strip()
    return ""


def _album_id(url: str) -> str | None:
    match = ALBUM_ID_RE.search(url)
    return match.group(1) if match else None


def _release_type(raw_type: str, source_section: str) -> str:
    value = raw_type.strip().lower()
    if value in {"album", "ep", "single", "live", "compilation"}:
        return value
    return SECTION_TYPES.get(source_section, "album")


def _year(raw_year: str) -> str:
    match = re.search(r"(?:19|20)\d{2}", raw_year or "")
    return match.group(0) if match else ""


def _archive_status(lifecycle: dict[str, Any], archive_row: dict[str, Any] | None = None) -> str:
    if archive_row and archive_row.get("archive_path"):
        return "archived"
    states = lifecycle.get("states") if isinstance(lifecycle.get("states"), dict) else {}
    if states.get("validated"):
        return "validated"
    if states.get("shipped"):
        return "downloaded"
    if lifecycle:
        return "known"
    return "not_archived"


def _validation_status(
    album_id: str,
    lifecycle: dict[str, Any],
    validated_index: dict[str, Any],
    identity_release: dict[str, Any] | None = None,
) -> str:
    states = lifecycle.get("states") if isinstance(lifecycle.get("states"), dict) else {}
    evidence = lifecycle.get("validation_evidence") if isinstance(lifecycle.get("validation_evidence"), dict) else {}
    identity_validation = identity_release.get("validation", {}) if isinstance(identity_release, dict) else {}
    if states.get("validated") or evidence.get("available") or identity_validation.get("available") or album_id in validated_index:
        return "validated"
    return "not_validated"


def _lifecycle_by_album_id(registry: dict[str, Any]) -> dict[str, dict[str, Any]]:
    albums = registry.get("albums", [])
    if isinstance(albums, dict):
        albums = albums.values()
    return {
        str(album.get("album_id")): album
        for album in albums
        if isinstance(album, dict) and album.get("album_id")
    }


def _identity_by_album_id(registry: dict[str, Any]) -> dict[str, dict[str, Any]]:
    releases = registry.get("releases", [])
    if isinstance(releases, dict):
        releases = releases.values()
    return {
        str(release.get("discovery_identity", {}).get("deezer_album_id")): release
        for release in releases
        if isinstance(release, dict) and release.get("discovery_identity", {}).get("deezer_album_id")
    }


def _archive_by_folder(registry: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {
        _folder_key(row.get("name")): row
        for row in registry.get("albums", [])
        if isinstance(row, dict) and _folder_key(row.get("name"))
    }


def _archive_row_for_release(
    identity_release: dict[str, Any],
    archive_by_folder: dict[str, dict[str, Any]],
) -> dict[str, Any]:
    folder = identity_release.get("archive_identity", {}).get("folder") if identity_release else ""
    if not folder:
        return {}
    return archive_by_folder.get(_folder_key(folder), {})


def _release_truth(
    *,
    artist: str,
    title: str,
    album_id: str,
    lifecycle: dict[str, Any],
    identity_release: dict[str, Any],
    archive_row: dict[str, Any],
    metadata_state: str,
    metadata_cache: dict[str, Any],
    validated_index: dict[str, Any],
) -> dict[str, Any]:
    evidence = merge_validation_evidence(
        validation_evidence_from_validated_index(album_id, validated_index),
        validation_evidence_from_lifecycle_row(lifecycle),
        validation_evidence_from_identity_release(identity_release),
    )
    metadata_album = metadata_cache.get("albums", {}).get(album_id, {})
    truth = album_truth(
        artist=artist,
        album=title,
        archive_path=archive_row.get("archive_path"),
        registry_artifacts=archive_row.get("artifacts", {}),
        validator_evidence=evidence,
        metadata_state=metadata_state,
        metadata_album=metadata_album,
        identity_confidence=identity_release.get("identity_confidence", "UNKNOWN"),
    )
    return truth.to_dict()


def _acquisition_status(
    *,
    archive_row: dict[str, Any],
    lifecycle: dict[str, Any],
    validation_status: str,
    metadata_status: str,
    identity_release: dict[str, Any],
    truth: dict[str, Any],
) -> str:
    if archive_row.get("archive_path"):
        return "Archived"
    states = lifecycle.get("states") if isinstance(lifecycle.get("states"), dict) else {}
    lifecycle_state = str(lifecycle.get("highest_state") or "").upper()
    if states.get("shipped") or lifecycle_state == "SHIPPED":
        return "Downloaded"
    if validation_status == "validated":
        return "Validated"
    if metadata_status != "CACHED" and lifecycle:
        return "Needs Metadata"
    confidence = str(identity_release.get("identity_confidence") or "UNKNOWN")
    maintenance = truth.get("maintenance") if isinstance(truth.get("maintenance"), dict) else {}
    if confidence not in {"HIGH", "MEDIUM"} or maintenance.get("category") == "needs_review":
        return "Needs Review"
    return "Needs Download"


def _folder_key(value: Any) -> str:
    return str(value or "").strip().casefold()


def _load_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}
    return data if isinstance(data, dict) else {}
