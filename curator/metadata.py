import requests
import time
from dataclasses import dataclass

DEEZER_API = "https://api.deezer.com"
REQUEST_DELAY = 0.1  # seconds


@dataclass(frozen=True)
class AlbumMetadata:
    artist: str
    title: str


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

    time.sleep(REQUEST_DELAY)

    if not artist or not title:
        return None

    return AlbumMetadata(
        artist=artist,
        title=title,
    )
