import requests
import time

from curator.metadata import get_album_metadata

DEEZER_API = "https://api.deezer.com"
PAGE_SIZE = 50


def expand_artist_releases(artist_id: str) -> dict[str, list[str]]:
    """
    Expand a Deezer artist into structured, annotated release lines.

    Classification uses Deezer's own record_type:
        album | ep | single
    """
    releases = []
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
            album_id = item.get("id")
            record_type = item.get("record_type")

            if not album_id or record_type not in {"album", "ep", "single"}:
                continue

            metadata = get_album_metadata(str(album_id))
            if not metadata:
                continue

            title = getattr(metadata, "title", "Unknown title")
            year = getattr(metadata, "year", None)
            tracks = getattr(metadata, "tracks", 0) or 0

            # ---- Flags ----
            flags = []
            title_lower = title.lower()

            if "live" in title_lower:
                flags.append("LIVE?")

            if "deluxe" in title_lower or "expanded" in title_lower:
                flags.append("DELUXE?")

            if getattr(metadata, "is_compilation", False):
                flags.append("COMPILATION")

            if getattr(metadata, "is_clean", False):
                flags.append("CLEAN")

            releases.append(
                {
                    "url": f"https://www.deezer.com/album/{album_id}",
                    "type": record_type,  # authoritative
                    "title": title,
                    "year": year,
                    "tracks": tracks,
                    "flags": flags,
                }
            )

        index += PAGE_SIZE
        time.sleep(0.1)

    # ---- Bucket & sort ----
    buckets = {
        "albums": [],
        "eps": [],
        "singles": [],
    }

    for r in releases:
        line = _format_release_line(r)

        if r["type"] == "album":
            buckets["albums"].append((r["year"], line))
        elif r["type"] == "ep":
            buckets["eps"].append((r["year"], line))
        elif r["type"] == "single":
            buckets["singles"].append((r["year"], line))

    for key in buckets:
        buckets[key].sort(key=lambda t: (t[0] is None, t[0]))
        buckets[key] = [line for _, line in buckets[key]]

    return buckets


def _format_release_line(r: dict) -> str:
    """
    URL-first, grep-safe, streamrip-safe line.
    """
    parts = [
        r["type"].upper(),
        r["title"],
    ]

    if r["year"]:
        parts.append(str(r["year"]))
    else:
        parts.append("unknown year")

    parts.append(f'{r["tracks"]} tracks')
    parts.extend(r["flags"])

    meta = " | ".join(parts)
    return f'{r["url"]}  # {meta}'
