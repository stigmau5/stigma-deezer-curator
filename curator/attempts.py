from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Dict

from curator.atomic import atomic_write_text


@dataclass
class AttemptInfo:
    album_url: str
    attempts: int
    last_attempt: str


def load_attempts(path: Path) -> Dict[str, AttemptInfo]:
    if not path.exists():
        return {}

    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}

    out: Dict[str, AttemptInfo] = {}
    for album_id, data in raw.items():
        if not isinstance(data, dict):
            continue
        out[album_id] = AttemptInfo(
            album_url=data.get("album_url", ""),
            attempts=int(data.get("attempts", 0)),
            last_attempt=data.get("last_attempt", ""),
        )
    return out


def save_attempts(path: Path, attempts: Dict[str, AttemptInfo]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)

    raw = {}
    for album_id, info in attempts.items():
        raw[album_id] = {
            "album_url": info.album_url,
            "attempts": info.attempts,
            "last_attempt": info.last_attempt,
        }

    atomic_write_text(path, json.dumps(raw, indent=2, ensure_ascii=False) + "\n")


def record_attempt(
    attempts: Dict[str, AttemptInfo],
    album_id: str,
    album_url: str,
) -> None:
    now = datetime.now().isoformat(timespec="seconds")

    if album_id in attempts:
        info = attempts[album_id]
        info.attempts += 1
        info.last_attempt = now
    else:
        attempts[album_id] = AttemptInfo(
            album_url=album_url,
            attempts=1,
            last_attempt=now,
        )
