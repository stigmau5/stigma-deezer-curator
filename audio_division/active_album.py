from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class ActiveAlbum:
    album_id: str = ""
    archive_path: str = ""
    deezer_album_id: str = ""
    artist_key: str = ""
    title: str = ""

    @property
    def present(self) -> bool:
        return bool(self.album_id or self.archive_path or self.deezer_album_id)

    def to_dict(self) -> dict[str, str]:
        return {
            "album_id": self.album_id,
            "archive_path": self.archive_path,
            "deezer_album_id": self.deezer_album_id,
            "artist_key": self.artist_key,
            "title": self.title,
        }


def active_album_from_row(album: dict[str, Any] | None) -> ActiveAlbum:
    album = album or {}
    album_id = str(album.get("album_id") or "").strip()
    deezer_album_id = str(album.get("deezer_album_id") or "").strip()
    return ActiveAlbum(
        album_id=album_id,
        archive_path=str(album.get("archive_path") or "").strip(),
        deezer_album_id=deezer_album_id or album_id,
        artist_key=str(album.get("artist_key") or "").strip(),
        title=str(album.get("title") or album.get("album") or "").strip(),
    )


def active_album_key(album: dict[str, Any] | ActiveAlbum | None) -> str:
    active = album if isinstance(album, ActiveAlbum) else active_album_from_row(album)
    if active.album_id:
        return f"album_id:{active.album_id}"
    if active.archive_path:
        return f"archive_path:{active.archive_path}"
    if active.deezer_album_id:
        return f"deezer_album_id:{active.deezer_album_id}"
    return ""


def find_active_album(albums: list[dict[str, Any]], active: ActiveAlbum) -> dict[str, Any] | None:
    if not active.present:
        return None
    for matcher in (_album_id_matches, _archive_path_matches, _deezer_album_id_matches):
        for album in albums:
            if matcher(album, active):
                return album
    return None


def restore_active_album(
    albums: list[dict[str, Any]],
    active: ActiveAlbum,
    previous_album: dict[str, Any] | None = None,
) -> dict[str, Any] | None:
    return find_active_album(albums, active) or previous_album


def active_album_index(albums: list[dict[str, Any]], active: ActiveAlbum) -> int | None:
    found = find_active_album(albums, active)
    if found is None:
        return None
    for index, album in enumerate(albums):
        if album is found:
            return index
    return None


def _album_id_matches(album: dict[str, Any], active: ActiveAlbum) -> bool:
    return bool(active.album_id and str(album.get("album_id") or "").strip() == active.album_id)


def _archive_path_matches(album: dict[str, Any], active: ActiveAlbum) -> bool:
    return bool(active.archive_path and str(album.get("archive_path") or "").strip() == active.archive_path)


def _deezer_album_id_matches(album: dict[str, Any], active: ActiveAlbum) -> bool:
    if not active.deezer_album_id:
        return False
    return str(album.get("deezer_album_id") or album.get("album_id") or "").strip() == active.deezer_album_id
