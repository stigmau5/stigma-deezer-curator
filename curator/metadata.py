import requests
import time
from dataclasses import dataclass
from typing import Any

DEEZER_API = "https://api.deezer.com"
REQUEST_DELAY = 0.1  # seconds


@dataclass(frozen=True)
class AlbumMetadata:
    artist: str
    title: str
    year: int | None = None
    tracks: int = 0
    is_compilation: bool = False
    is_clean: bool = False


def _year_from_release_date(value: Any) -> int | None:
    if not isinstance(value, str) or len(value) < 4:
        return None

    year = value[:4]
    if not year.isdigit():
        return None

    return int(year)


def _track_count(value: Any) -> int:
    try:
        tracks = int(value)
    except (TypeError, ValueError):
        return 0

    return max(0, tracks)


def _is_clean_edition(title: str, explicit_lyrics: Any) -> bool:
    if explicit_lyrics is True:
        return False

    title_lower = title.lower()
    return any(
        marker in title_lower
        for marker in (
            "clean version",
            "clean edit",
            "clean edition",
            "(clean)",
            "[clean]",
        )
    )


def get_album_metadata(album_id: str) -> AlbumMetadata | None:
    url = f"{DEEZER_API}/album/{album_id}"

    try:
        response = requests.get(url, timeout=10)
        response.raise_for_status()
    except requests.RequestException:
        return None

    data = response.json()

    artist = data.get("artist", {}).get("name")
    title = data.get("title")
    year = _year_from_release_date(data.get("release_date"))
    tracks = _track_count(data.get("nb_tracks"))
    is_compilation = data.get("record_type") == "compilation"

    time.sleep(REQUEST_DELAY)

    if not artist or not title:
        return None

    return AlbumMetadata(
        artist=artist,
        title=title,
        year=year,
        tracks=tracks,
        is_compilation=is_compilation,
        is_clean=_is_clean_edition(title, data.get("explicit_lyrics")),
    )
