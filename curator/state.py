from __future__ import annotations

import json
import re
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Any

from curator.atomic import atomic_write_text

# Extract album id from common Deezer album URLs:
# https://www.deezer.com/album/123
# https://www.deezer.com/us/album/123
# https://www.deezer.com/se/album/123
_ALBUM_ID_RE = re.compile(r"(?:/[a-z]{2})?/album/(\d+)")


@dataclass(frozen=True)
class ConfirmedAlbum:
    album_id: str
    album_url: str
    confirmed_at: str  # ISO string
    artist_file: str | None = None


import re

def album_id_from_url(text: str) -> str | None:
    if not text:
        return None

    # Only keep the actual URL (drop any inline comments / markers)
    url = text.strip().split()[0]

    # Accept URL even if it has extra path/query, but require /album/<digits>
    m = re.search(r"/album/(\d+)", url)
    return m.group(1) if m else None


def load_confirmed(path: Path) -> dict[str, ConfirmedAlbum]:
    """
    Returns a dict album_id -> ConfirmedAlbum
    """
    if not path.exists():
        return {}

    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}

    if not isinstance(raw, dict):
        return {}

    out: dict[str, ConfirmedAlbum] = {}
    for album_id, payload in raw.items():
        if not isinstance(payload, dict):
            continue
        album_url = str(payload.get("album_url", "")).strip()
        confirmed_at = str(payload.get("confirmed_at", "")).strip()
        artist_file = payload.get("artist_file", None)
        if not album_url or not confirmed_at:
            continue
        out[str(album_id)] = ConfirmedAlbum(
            album_id=str(album_id),
            album_url=album_url,
            confirmed_at=confirmed_at,
            artist_file=str(artist_file) if artist_file else None,
        )
    return out


def save_confirmed(path: Path, confirmed: dict[str, ConfirmedAlbum]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)

    data: dict[str, Any] = {}
    for album_id, item in confirmed.items():
        data[album_id] = {
            "album_url": item.album_url,
            "confirmed_at": item.confirmed_at,
            "artist_file": item.artist_file,
        }

    atomic_write_text(path, json.dumps(data, indent=2, ensure_ascii=False) + "\n")


def is_confirmed(confirmed: dict[str, ConfirmedAlbum], album_url: str) -> bool:
    album_id = album_id_from_url(album_url)
    if not album_id:
        return False
    return album_id in confirmed


def confirm_album(
    confirmed: dict[str, ConfirmedAlbum],
    album_url: str,
    *,
    artist_file: str | None = None,
) -> bool:
    """
    Returns True if it added a new confirmation, False if it was already confirmed
    """
    album_url = album_url.strip()
    album_id = album_id_from_url(album_url)
    if not album_id:
        return False

    if album_id in confirmed:
        return False

    confirmed[album_id] = ConfirmedAlbum(
        album_id=album_id,
        album_url=album_url,
        confirmed_at=datetime.now().isoformat(timespec="seconds"),
        artist_file=artist_file,
    )
    return True
