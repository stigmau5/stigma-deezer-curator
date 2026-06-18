from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class ArchiveSelectionState:
    artist_key: str = ""
    album_key: str = ""
    active_tab: str = ""
    album_yview: float = 0.0


def archive_album_key(album: dict[str, Any]) -> str:
    return str(album.get("archive_path") or album.get("album_id") or f"{album.get('artist', '')}|{album.get('title', '')}")


def capture_archive_selection(
    album: dict[str, Any],
    *,
    active_tab: str = "",
    album_yview: tuple[float, float] | list[float] | None = None,
) -> ArchiveSelectionState:
    yview = float(album_yview[0]) if album_yview else 0.0
    return ArchiveSelectionState(
        artist_key=str(album.get("artist_key", "")),
        album_key=archive_album_key(album),
        active_tab=active_tab,
        album_yview=yview,
    )


def selected_album_index(albums: list[dict[str, Any]], state: ArchiveSelectionState) -> int | None:
    if not state.album_key:
        return None
    for index, album in enumerate(albums):
        if archive_album_key(album) == state.album_key:
            return index
    return None
