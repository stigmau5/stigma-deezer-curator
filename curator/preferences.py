import json
from pathlib import Path

from curator.atomic import atomic_write_text

DEFAULTS = {
    "batch_size": 6,
}


def load_preferences(path: Path) -> dict:
    if not path.exists():
        return DEFAULTS.copy()

    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return DEFAULTS.copy()

    prefs = DEFAULTS.copy()
    prefs.update({k: v for k, v in data.items() if k in DEFAULTS})
    return prefs


def save_preferences(path: Path, prefs: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    atomic_write_text(path, json.dumps(prefs, indent=2, ensure_ascii=False) + "\n")
