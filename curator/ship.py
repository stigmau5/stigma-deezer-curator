from __future__ import annotations

import json
import re
import subprocess
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable

from curator.atomic import atomic_write_text

# Accept both:
#   https://www.deezer.com/album/7500349
#   https://www.deezer.com/us/album/7500349
#   https://www.deezer.com/fr/album/7500349
DEEZEER_ALBUM_RE = re.compile(
    r"(?:https?://)?(?:www\.)?deezer\.com/(?:[a-z]{2}/)?album/(\d+)",
    re.IGNORECASE,
)


@dataclass(frozen=True)
class ShipConfig:
    # SSH target: passwordless auth
    ssh_host: str = "stigma@stigma-mediaserver"

    # Server pending dir
    server_pending_dir: str = "/media/storage/streamrip/jobs/pending"

    # Default job retry settings
    retry_max: int = 3

    # Local curator data dir
    data_dir: Path = Path(__file__).resolve().parents[1] / "data"

    # Local shipped ledger (album_id -> record)
    shipped_db: Path = Path(__file__).resolve().parents[1] / "data" / "shipped_jobs.json"


def _utc_now_stamp() -> str:
    return datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S")


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def parse_deezer_album_id(url: str) -> str:
    url = url.strip()
    m = DEEZEER_ALBUM_RE.search(url)
    if not m:
        raise ValueError(f"Not a Deezer album URL: {url}")
    return m.group(1)


def build_jobname(album_id: str) -> str:
    # Sortable, deterministic enough, matches worker conventions
    return f"{_utc_now_stamp()}_deezer_album_{album_id}"


def render_job_file(url: str, retry_max: int) -> str:
    # Compatible with your server worker expectations
    return f"URL={url}\nRETRY_MAX={retry_max}\nRETRY_COUNT=0\n"


def _run(cmd: list[str], timeout: int = 30) -> None:
    subprocess.run(cmd, check=True, timeout=timeout)


def _load_shipped_db(path: Path) -> dict:
    if not path.exists():
        return {"schema": 1, "shipped": {}}  # album_id -> record
    return json.loads(path.read_text(encoding="utf-8"))


def _save_shipped_db(path: Path, db: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    atomic_write_text(path, json.dumps(db, ensure_ascii=False, indent=2, sort_keys=True) + "\n")


def _already_shipped(db: dict, album_id: str) -> bool:
    shipped = db.get("shipped", {})
    return album_id in shipped


def _mark_shipped(db: dict, album_id: str, url: str, jobname: str, remote_final: str) -> None:
    db.setdefault("shipped", {})
    db["shipped"][album_id] = {
        "album_id": album_id,
        "url": url,
        "jobname": jobname,
        "remote_job": remote_final,
        "shipped_at_utc": _utc_now_iso(),
    }


def ship_one_album_url(url: str, cfg: ShipConfig, *, force: bool = False) -> str:
    """
    Ships one Deezer album URL as a server .job file (atomic upload).
    Returns the remote final path.
    """
    # Strip comments/extra tokens (your queue often has annotations after the URL)
    url = url.strip().split()[0]

    album_id = parse_deezer_album_id(url)

    db = _load_shipped_db(cfg.shipped_db)
    if _already_shipped(db, album_id) and not force:
        rec = db["shipped"][album_id]
        return rec["remote_job"]

    jobname = build_jobname(album_id)

    # Local temp job file in data/shipped_tmp (local-first audit)
    tmp_dir = cfg.data_dir / "shipped_tmp"
    tmp_dir.mkdir(parents=True, exist_ok=True)
    local_tmp = tmp_dir / f"{jobname}.job"

    local_tmp.write_text(render_job_file(url, cfg.retry_max), encoding="utf-8")

    remote_final = f"{cfg.server_pending_dir}/{jobname}.job"
    remote_tmp = remote_final + ".tmp"

    # Non-interactive SSH/SCP so GUI never hangs waiting for prompts
    ssh_base = ["ssh", "-o", "BatchMode=yes", "-o", "ConnectTimeout=10", cfg.ssh_host]
    scp_base = ["scp", "-o", "BatchMode=yes", "-o", "ConnectTimeout=10"]

    # Ensure server dir exists, upload to .tmp, then atomic mv into pending/
    _run(ssh_base + ["mkdir", "-p", cfg.server_pending_dir], timeout=15)
    _run(scp_base + [str(local_tmp), f"{cfg.ssh_host}:{remote_tmp}"], timeout=30)
    _run(ssh_base + ["mv", remote_tmp, remote_final], timeout=15)

    _mark_shipped(db, album_id, url, jobname, remote_final)
    _save_shipped_db(cfg.shipped_db, db)

    return remote_final


def read_urls_from_file(path: Path) -> list[str]:
    urls: list[str] = []
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        s = line.strip()
        if not s or s.startswith("#"):
            continue

        # Accept either "URL=..." or plain url
        if s.startswith("URL="):
            s = s[4:].strip()

        # Your files may have comments/annotations after URL; keep first token only
        s = s.split()[0]

        # Only keep Deezer album URLs
        if "deezer.com" in s and "/album/" in s:
            urls.append(s)

    return urls


def ship_urls(urls: Iterable[str], cfg: ShipConfig, *, force: bool = False) -> list[str]:
    out: list[str] = []
    for u in urls:
        remote = ship_one_album_url(u, cfg, force=force)
        out.append(remote)
    return out
