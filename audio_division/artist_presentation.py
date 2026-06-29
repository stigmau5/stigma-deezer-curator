from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any, Iterable

from audio_division.artist_model import Artist, load_artist_file


@dataclass(frozen=True)
class ArtistPresentation:
    artist: Artist
    projection_path: Path
    projection_name: str
    display_name: str
    sort_name: str
    deezer_artist_id: str | None
    total_release_count: int
    last_updated: str


def load_artist_presentation(path: Path, data_dir: Path | None = None) -> ArtistPresentation:
    artist = load_artist_file(path, data_dir)
    return presentation_from_artist(artist)


def load_artist_presentations(artists_dir: Path, data_dir: Path | None = None) -> tuple[ArtistPresentation, ...]:
    artists_dir.mkdir(parents=True, exist_ok=True)
    return tuple(
        load_artist_presentation(path, data_dir)
        for path in sorted(artists_dir.glob("*.txt"), key=lambda item: item.name.casefold())
    )


def presentation_from_artist(artist: Artist) -> ArtistPresentation:
    projection_path = Path(artist.source_file)
    display_name = artist.artist_name.strip() or projection_path.stem.replace("_", " ")
    return ArtistPresentation(
        artist=artist,
        projection_path=projection_path,
        projection_name=projection_path.name,
        display_name=display_name,
        sort_name=display_name.casefold(),
        deezer_artist_id=artist.deezer_artist_id,
        total_release_count=artist.total_release_count,
        last_updated=artist.last_updated,
    )


def sort_artist_presentations(
    presentations: Iterable[ArtistPresentation],
    *,
    sort_mode: str = "alphabetical",
    created_meta: dict[str, Any] | None = None,
) -> tuple[ArtistPresentation, ...]:
    rows = tuple(presentations)
    created_meta = created_meta or {}
    if sort_mode == "last_added":
        return tuple(
            sorted(
                rows,
                key=lambda row: str(created_meta.get(row.projection_name, "")),
                reverse=True,
            )
        )
    return tuple(sorted(rows, key=lambda row: (row.sort_name, row.projection_name.casefold())))
