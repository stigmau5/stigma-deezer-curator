from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from audio_division.metadata_status import album_metadata_status


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
    )


def parse_artist_text(
    text: str,
    *,
    source_file: Path,
    lifecycle_registry: dict[str, Any] | None = None,
    metadata_cache: dict[str, Any] | None = None,
    validated_index: dict[str, Any] | None = None,
) -> Artist:
    lifecycle_registry = lifecycle_registry or {}
    metadata_cache = metadata_cache or {}
    validated_index = validated_index or {}
    lifecycle_by_id = _lifecycle_by_album_id(lifecycle_registry)

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
    lifecycle = lifecycle_by_id.get(album_id, {})
    lifecycle_state = str(lifecycle.get("highest_state") or "DISCOVERED")
    validation_status = _validation_status(album_id, lifecycle, validated_index)
    return Release(
        deezer_album_id=album_id,
        title=title,
        year=year,
        type=release_type,
        url=url,
        archive_status=_archive_status(lifecycle),
        lifecycle_state=lifecycle_state,
        validation_status=validation_status,
        metadata_status=album_metadata_status(album_id, metadata_cache)["state"],
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


def _archive_status(lifecycle: dict[str, Any]) -> str:
    states = lifecycle.get("states") if isinstance(lifecycle.get("states"), dict) else {}
    if states.get("validated"):
        return "archived"
    if states.get("shipped"):
        return "shipped"
    if lifecycle:
        return "known"
    return "not_archived"


def _validation_status(
    album_id: str,
    lifecycle: dict[str, Any],
    validated_index: dict[str, Any],
) -> str:
    states = lifecycle.get("states") if isinstance(lifecycle.get("states"), dict) else {}
    evidence = lifecycle.get("validation_evidence") if isinstance(lifecycle.get("validation_evidence"), dict) else {}
    if states.get("validated") or evidence.get("available") or album_id in validated_index:
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


def _load_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}
    return data if isinstance(data, dict) else {}
