from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

from audio_division.album_truth import album_truth
from audio_division.library import build_library, album_details
from audio_division.metadata_status import album_metadata_status
from audio_division.physical_archive import (
    archive_identity_for_row,
    artist_key,
    contributor_names,
    project_archive_album,
)
from audio_division.validation_truth import (
    merge_validation_evidence,
    validation_evidence_from_identity_release,
    validation_evidence_from_lifecycle_row,
)


@dataclass(frozen=True)
class AlbumRef:
    album_id: str = ""
    deezer_album_id: str = ""
    archive_path: str = ""
    archive_folder: str = ""
    artist: str = ""
    title: str = ""
    source: str = ""

    @classmethod
    def from_row(cls, row: dict[str, Any] | None, *, source: str = "") -> "AlbumRef":
        row = row or {}
        album_id = _text(row.get("album_id") or row.get("deezer_album_id"))
        return cls(
            album_id=album_id,
            deezer_album_id=_text(row.get("deezer_album_id") or album_id),
            archive_path=_text(row.get("archive_path") or row.get("folder")),
            archive_folder=_text(row.get("archive_folder") or row.get("name")),
            artist=_text(row.get("artist")),
            title=_text(row.get("title") or row.get("album")),
            source=source or _text(row.get("source")),
        )

    @property
    def provider_album_id(self) -> str:
        return self.album_id or self.deezer_album_id


@dataclass(frozen=True)
class CanonicalAlbum:
    details: dict[str, Any] = field(default_factory=dict)
    source: str = "missing"
    archive_row: dict[str, Any] = field(default_factory=dict)
    identity_release: dict[str, Any] = field(default_factory=dict)
    lifecycle_row: dict[str, Any] = field(default_factory=dict)
    metadata_album: dict[str, Any] = field(default_factory=dict)

    @property
    def present(self) -> bool:
        return bool(self.details)

    @property
    def filesystem_bound(self) -> bool:
        return bool(self.details.get("archive_path"))

    def to_dict(self) -> dict[str, Any]:
        return deepcopy(self.details)

    def get(self, key: str, default: Any = None) -> Any:
        return self.details.get(key, default)

    def __getitem__(self, key: str) -> Any:
        return self.details[key]


class CanonicalAlbumResolver:
    """Resolve any album entry point into one album record for the workspace.

    Resolution is intentionally read-only. It reuses the existing Archive and
    Library projections, then makes precedence explicit:
    Archive Registry, Identity Registry, Lifecycle Registry, Metadata Cache.
    """

    def __init__(
        self,
        *,
        archive_registry: dict[str, Any] | None = None,
        identity_registry: dict[str, Any] | None = None,
        lifecycle_registry: dict[str, Any] | None = None,
        metadata_cache: dict[str, Any] | None = None,
        archive_root: Path | str | None = None,
    ):
        self.archive_registry = archive_registry or {}
        self.identity_registry = identity_registry or {}
        self.lifecycle_registry = lifecycle_registry or {}
        self.metadata_cache = metadata_cache or {}
        self.archive_root = Path(archive_root) if archive_root else None
        self._library: dict[str, Any] | None = None

    def resolve(self, album_ref: AlbumRef | dict[str, Any] | None) -> CanonicalAlbum:
        ref = album_ref if isinstance(album_ref, AlbumRef) else AlbumRef.from_row(album_ref)
        archive_row, identity_release = self._resolve_archive_binding(ref)
        if archive_row:
            return self._from_archive(ref, archive_row, identity_release)

        identity_release = identity_release or self._identity_for_ref(ref)
        album_id = ref.provider_album_id or _identity_album_id(identity_release)
        lifecycle_row = self._lifecycle_for_album_id(album_id)
        catalog = self._catalog_record(ref, album_id, identity_release, lifecycle_row)
        if catalog:
            return catalog
        return CanonicalAlbum()

    def _from_archive(
        self,
        ref: AlbumRef,
        archive_row: dict[str, Any],
        identity_release: dict[str, Any] | None = None,
    ) -> CanonicalAlbum:
        identity_release = identity_release or self._identity_for_archive_row(ref, archive_row)
        details = project_archive_album(archive_row, identity_release, self.metadata_cache)
        album_id = details.get("album_id") or ref.provider_album_id or _identity_album_id(identity_release)
        lifecycle_row = self._lifecycle_for_album_id(album_id)
        metadata_album = self._metadata_album(album_id)
        self._overlay_sources(details, album_id, identity_release, lifecycle_row, metadata_album)
        self._refresh_truth(details, identity_release, lifecycle_row, metadata_album)
        details["canonical_source"] = "archive_registry"
        details["canonical_filesystem_bound"] = bool(details.get("archive_path"))
        return CanonicalAlbum(
            details=details,
            source="archive_registry",
            archive_row=deepcopy(archive_row),
            identity_release=deepcopy(identity_release or {}),
            lifecycle_row=deepcopy(lifecycle_row or {}),
            metadata_album=deepcopy(metadata_album or {}),
        )

    def _catalog_record(
        self,
        ref: AlbumRef,
        album_id: str,
        identity_release: dict[str, Any],
        lifecycle_row: dict[str, Any],
    ) -> CanonicalAlbum:
        if album_id and lifecycle_row:
            library_record = album_details(self._library_projection(), album_id)
            if library_record:
                details = deepcopy(library_record)
                metadata_album = self._metadata_album(album_id)
                self._overlay_sources(details, album_id, identity_release, lifecycle_row, metadata_album)
                details["canonical_source"] = "lifecycle_registry"
                details["canonical_filesystem_bound"] = bool(details.get("archive_path"))
                return CanonicalAlbum(
                    details=details,
                    source="lifecycle_registry",
                    identity_release=deepcopy(identity_release or {}),
                    lifecycle_row=deepcopy(lifecycle_row or {}),
                    metadata_album=deepcopy(metadata_album or {}),
                )

        metadata_album = self._metadata_album(album_id)
        if metadata_album:
            details = self._metadata_only_record(ref, album_id, identity_release, metadata_album)
            details["canonical_source"] = "metadata_cache"
            details["canonical_filesystem_bound"] = False
            return CanonicalAlbum(
                details=details,
                source="metadata_cache",
                identity_release=deepcopy(identity_release or {}),
                metadata_album=deepcopy(metadata_album),
            )

        if identity_release:
            details = self._identity_only_record(ref, identity_release)
            details["canonical_source"] = "identity_registry"
            details["canonical_filesystem_bound"] = False
            return CanonicalAlbum(
                details=details,
                source="identity_registry",
                identity_release=deepcopy(identity_release),
            )

        return CanonicalAlbum()

    def _resolve_archive_binding(self, ref: AlbumRef) -> tuple[dict[str, Any], dict[str, Any]]:
        row = self._archive_row_by_path(ref.archive_path)
        if row:
            return row, self._identity_for_archive_row(ref, row)

        identity_release = self._identity_for_ref(ref)
        row = self._archive_row_for_identity(identity_release)
        if row:
            return row, identity_release

        row = self._archive_row_by_folder(ref.archive_folder)
        if row:
            return row, self._identity_for_archive_row(ref, row)

        row = self._archive_row_by_artist_title(ref.artist, ref.title)
        if row:
            return row, self._identity_for_archive_row(ref, row)
        return {}, identity_release

    def _identity_for_ref(self, ref: AlbumRef) -> dict[str, Any]:
        album_id = ref.provider_album_id
        if album_id:
            for release in self._identity_releases():
                if _identity_album_id(release) == album_id:
                    return release
        if ref.archive_path or ref.archive_folder:
            for release in self._identity_releases():
                if self._identity_matches_folder(release, ref.archive_path or ref.archive_folder):
                    return release
        return {}

    def _identity_for_archive_row(self, ref: AlbumRef, row: dict[str, Any]) -> dict[str, Any]:
        by_ref = self._identity_for_ref(ref)
        if by_ref and self._archive_row_matches_identity(row, by_ref):
            return by_ref
        return archive_identity_for_row(row, self.identity_registry)

    def _archive_row_for_identity(self, identity_release: dict[str, Any]) -> dict[str, Any]:
        if not identity_release:
            return {}
        for row in self.archive_registry.get("albums", []):
            if self._archive_row_matches_identity(row, identity_release):
                return row
        return {}

    def _archive_row_by_path(self, archive_path: str) -> dict[str, Any]:
        wanted = _path_key(archive_path)
        if not wanted:
            return {}
        for row in self.archive_registry.get("albums", []):
            if _path_key(row.get("archive_path")) == wanted:
                return row
        return {}

    def _archive_row_by_folder(self, folder: str) -> dict[str, Any]:
        wanted = _folder_key(folder)
        if not wanted:
            return {}
        for row in self.archive_registry.get("albums", []):
            if _folder_key(row.get("name")) == wanted or _folder_key(row.get("relative_path")) == wanted:
                return row
        return {}

    def _archive_row_by_artist_title(self, artist: str, title: str) -> dict[str, Any]:
        artist = _text_key(artist)
        title = _text_key(title)
        if not artist or not title:
            return {}
        for row in self.archive_registry.get("albums", []):
            projected = project_archive_album(row, self._identity_for_archive_row(AlbumRef(), row), self.metadata_cache)
            if _text_key(projected.get("artist")) == artist and _text_key(projected.get("title")) == title:
                return row
        return {}

    def _archive_row_matches_identity(self, row: dict[str, Any], identity_release: dict[str, Any]) -> bool:
        folder = identity_release.get("archive_identity", {}).get("folder") or ""
        if not folder:
            return False
        if _path_key(folder) and Path(str(folder)).is_absolute():
            return _path_key(row.get("archive_path")) == _path_key(folder)
        if self.archive_root:
            resolved = self.archive_root / str(folder)
            if _path_key(row.get("archive_path")) == _path_key(resolved):
                return True
        return _folder_key(row.get("name")) == _folder_key(folder)

    def _identity_matches_folder(self, identity_release: dict[str, Any], value: str) -> bool:
        folder = identity_release.get("archive_identity", {}).get("folder") or ""
        if not folder or not value:
            return False
        return _path_key(folder) == _path_key(value) or _folder_key(folder) == _folder_key(value)

    def _lifecycle_for_album_id(self, album_id: str) -> dict[str, Any]:
        if not album_id:
            return {}
        for row in self.lifecycle_registry.get("albums", []):
            if _text(row.get("album_id")) == album_id:
                return row
        return {}

    def _metadata_album(self, album_id: str) -> dict[str, Any]:
        return deepcopy(self.metadata_cache.get("albums", {}).get(str(album_id), {})) if album_id else {}

    def _library_projection(self) -> dict[str, Any]:
        if self._library is None:
            self._library = build_library(
                self.lifecycle_registry,
                self.identity_registry,
                self.metadata_cache,
                self.archive_root,
            )
        return self._library

    def _identity_releases(self) -> list[dict[str, Any]]:
        return list(self.identity_registry.get("releases", []))

    def _overlay_sources(
        self,
        details: dict[str, Any],
        album_id: str,
        identity_release: dict[str, Any],
        lifecycle_row: dict[str, Any],
        metadata_album: dict[str, Any],
    ) -> None:
        if album_id and not details.get("album_id"):
            details["album_id"] = album_id
        if identity_release:
            details["identity_release"] = deepcopy(identity_release)
            details["identity_confidence"] = identity_release.get("identity_confidence", details.get("identity_confidence", "UNKNOWN"))
        if lifecycle_row:
            details["lifecycle_row"] = deepcopy(lifecycle_row)
            details["catalog_lifecycle_state"] = lifecycle_row.get("highest_state", "")
        if metadata_album:
            details["metadata_album"] = deepcopy(metadata_album)
            details["metadata_detail"] = album_metadata_status(album_id, self.metadata_cache)
            details["metadata_status"] = details["metadata_detail"]["state"]
        details["canonical_sources"] = {
            "archive_registry": bool(details.get("archive_path")),
            "identity_registry": bool(identity_release),
            "lifecycle_registry": bool(lifecycle_row),
            "metadata_cache": bool(metadata_album),
        }

    def _refresh_truth(
        self,
        details: dict[str, Any],
        identity_release: dict[str, Any],
        lifecycle_row: dict[str, Any],
        metadata_album: dict[str, Any],
    ) -> None:
        truth = album_truth(
            artist=details.get("artist"),
            album=details.get("title"),
            archive_path=details.get("archive_path"),
            registry_artifacts=details.get("artifacts", {}),
            validator_evidence=merge_validation_evidence(
                validation_evidence_from_lifecycle_row(lifecycle_row or {}),
                validation_evidence_from_identity_release(identity_release or {}),
            ),
            metadata_state=details.get("metadata_status"),
            metadata_album=metadata_album,
            identity_confidence=details.get("identity_confidence", "UNKNOWN"),
        )
        details["album_truth"] = truth.to_dict()
        details["album_status"] = truth.to_album_status()
        details["validation_status"] = "validated" if truth.validation.present else "not_validated"
        details["validation_source"] = truth.validation_source
        details["validation_confidence"] = truth.validation_confidence
        details["validation_reason"] = truth.validation_reason
        details["processing_state"] = truth.processing_state

    def _metadata_only_record(
        self,
        ref: AlbumRef,
        album_id: str,
        identity_release: dict[str, Any],
        metadata_album: dict[str, Any],
    ) -> dict[str, Any]:
        artist = _metadata_artist(metadata_album) or _identity_artist(identity_release) or ref.artist or "(unknown)"
        title = metadata_album.get("title") or _identity_title(identity_release) or ref.title or "(unknown)"
        genres = [item.get("name") for item in metadata_album.get("genres", []) if isinstance(item, dict) and item.get("name")]
        metadata_detail = album_metadata_status(album_id, self.metadata_cache)
        truth = album_truth(
            artist=artist,
            album=title,
            metadata_state=metadata_detail["state"],
            metadata_album=metadata_album,
            identity_confidence=identity_release.get("identity_confidence", "UNKNOWN"),
        )
        return {
            "album_id": album_id,
            "artist_key": artist_key(artist),
            "artist": artist,
            "title": title,
            "year": metadata_album.get("year"),
            "release_date": metadata_album.get("release_date", ""),
            "record_type": metadata_album.get("record_type", ""),
            "label": metadata_album.get("label", ""),
            "genres": genres,
            "contributors": contributor_names(metadata_album.get("contributors", [])),
            "track_count": metadata_album.get("track_count", 0),
            "duration": metadata_album.get("duration", ""),
            "lifecycle_state": "",
            "identity_confidence": identity_release.get("identity_confidence", "UNKNOWN"),
            "validation_status": "not_validated",
            "validation_source": truth.validation_source,
            "validation_confidence": truth.validation_confidence,
            "validation_reason": truth.validation_reason,
            "metadata_status": metadata_detail["state"],
            "metadata_detail": metadata_detail,
            "archive_folder": "",
            "archive_path": "",
            "archive_path_confidence": "UNKNOWN",
            "archive_path_reason": "no_archive_folder_evidence",
            "artifacts": {},
            "album_status": truth.to_album_status(),
            "album_truth": truth.to_dict(),
            "processing_state": truth.processing_state,
            "artwork": {
                "cover_identity": metadata_album.get("cover_identity", ""),
                "urls": metadata_album.get("covers", {}) if isinstance(metadata_album.get("covers"), dict) else {},
                "local": "",
            },
        }

    def _identity_only_record(self, ref: AlbumRef, identity_release: dict[str, Any]) -> dict[str, Any]:
        album_id = _identity_album_id(identity_release) or ref.provider_album_id
        artist = _identity_artist(identity_release) or ref.artist or "(unknown)"
        title = _identity_title(identity_release) or ref.title or "(unknown)"
        metadata_detail = album_metadata_status(album_id, self.metadata_cache)
        truth = album_truth(
            artist=artist,
            album=title,
            metadata_state=metadata_detail["state"],
            identity_confidence=identity_release.get("identity_confidence", "UNKNOWN"),
        )
        return {
            "album_id": album_id,
            "artist_key": artist_key(artist),
            "artist": artist,
            "title": title,
            "year": "",
            "record_type": "",
            "lifecycle_state": "",
            "identity_confidence": identity_release.get("identity_confidence", "UNKNOWN"),
            "validation_status": "not_validated",
            "validation_source": truth.validation_source,
            "validation_confidence": truth.validation_confidence,
            "validation_reason": truth.validation_reason,
            "metadata_status": metadata_detail["state"],
            "metadata_detail": metadata_detail,
            "archive_folder": identity_release.get("archive_identity", {}).get("folder", ""),
            "archive_path": "",
            "archive_path_confidence": "UNKNOWN",
            "archive_path_reason": "no_archive_folder_evidence",
            "artifacts": {},
            "album_status": truth.to_album_status(),
            "album_truth": truth.to_dict(),
            "processing_state": truth.processing_state,
            "artwork": {"cover_identity": "", "urls": {}, "local": ""},
        }


def _identity_album_id(release: dict[str, Any]) -> str:
    return _text(release.get("discovery_identity", {}).get("deezer_album_id"))


def _identity_artist(release: dict[str, Any]) -> str:
    return _text(release.get("discovery_identity", {}).get("artist"))


def _identity_title(release: dict[str, Any]) -> str:
    return _text(release.get("discovery_identity", {}).get("title"))


def _metadata_artist(metadata_album: dict[str, Any]) -> str:
    artist = metadata_album.get("artist")
    if isinstance(artist, dict):
        return _text(artist.get("name"))
    return _text(artist)


def _text(value: Any) -> str:
    return str(value or "").strip()


def _text_key(value: Any) -> str:
    return " ".join(_text(value).replace("_", " ").replace("-", " ").lower().split())


def _path_key(value: Any) -> str:
    text = _text(value)
    if not text:
        return ""
    return str(Path(text)).rstrip("/")


def _folder_key(value: Any) -> str:
    text = _text(value)
    if not text:
        return ""
    return _text_key(Path(text).name)
