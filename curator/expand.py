import requests
import time

DEEZER_API = "https://api.deezer.com"
PAGE_SIZE = 50


def expand_artist(artist_id: str) -> list[str]:
    """
    Expand a Deezer artist ID into album URLs.
    Includes albums and EPs only.
    """
    albums: list[str] = []
    index = 0

    while True:
        url = f"{DEEZER_API}/artist/{artist_id}/albums"
        params = {
            "index": index,
            "limit": PAGE_SIZE,
        }

        response = requests.get(url, params=params, timeout=10)
        response.raise_for_status()

        data = response.json()
        items = data.get("data", [])

        if not items:
            break

        for item in items:
            record_type = item.get("record_type")
            if record_type not in {"album", "ep"}:
                continue

            album_id = item.get("id")
            if album_id:
                albums.append(f"https://www.deezer.com/album/{album_id}")

        index += PAGE_SIZE
        time.sleep(0.1)  # polite pacing

    return albums
