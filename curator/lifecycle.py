from __future__ import annotations

import json
import re
from collections import Counter
from datetime import datetime
from pathlib import Path
from typing import Any

from curator.atomic import atomic_write_text

STATE_ORDER = ("DISCOVERED", "ATTEMPTED", "SHIPPED", "VALIDATED", "CONFIRMED")
STATE_KEYS = {
    "DISCOVERED": "discovered",
    "ATTEMPTED": "attempted",
    "SHIPPED": "shipped",
    "VALIDATED": "validated",
    "CONFIRMED": "confirmed",
}
STATE_RANK = {state: idx for idx, state in enumerate(STATE_ORDER, start=1)}

ALBUM_RE = re.compile(r"deezer\.com/(?:[a-z]{2}/)?album/(\d+)", re.IGNORECASE)


def load_json_file(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}

    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}

    return data if isinstance(data, dict) else {}


def highest_state(states: dict[str, bool]) -> str | None:
    highest: str | None = None
    for state in STATE_ORDER:
        if states.get(STATE_KEYS[state], False):
            highest = state
    return highest


def _empty_album(album_id: str) -> dict[str, Any]:
    return {
        "album_id": album_id,
        "artist": None,
        "title": None,
        "states": {key: False for key in STATE_KEYS.values()},
        "highest_state": None,
        "sources": [],
        "timestamps": {},
        "details": {},
    }


def _album(rows: dict[str, dict[str, Any]], album_id: str) -> dict[str, Any]:
    return rows.setdefault(album_id, _empty_album(album_id))


def _set_state(row: dict[str, Any], state: str) -> None:
    row["states"][STATE_KEYS[state]] = True
    row["highest_state"] = highest_state(row["states"])


def _add_source(row: dict[str, Any], source: str) -> None:
    if source not in row["sources"]:
        row["sources"].append(source)


def _title_from_annotated_line(line: str) -> str | None:
    if "#" not in line:
        return None

    comment = line.split("#", 1)[1].strip()
    parts = [part.strip() for part in comment.split("|")]
    if len(parts) < 2:
        return None

    return parts[1] or None


def _artist_from_file(path: Path, lines: list[str]) -> str:
    for line in lines[:25]:
        if line.startswith("# Artist:"):
            artist = line.split(":", 1)[1].strip()
            if artist:
                return artist
    return path.stem.replace("_", " ")


def _artist_from_filename(filename: str | None) -> str | None:
    if not filename:
        return None
    return Path(filename).stem.replace("_", " ")


def read_artist_releases(artists_dir: Path) -> tuple[dict[str, dict[str, Any]], dict[str, int]]:
    rows: dict[str, dict[str, Any]] = {}
    files = sorted(artists_dir.glob("*.txt")) if artists_dir.exists() else []
    line_count = 0

    for path in files:
        lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
        artist = _artist_from_file(path, lines)

        for line in lines:
            match = ALBUM_RE.search(line)
            if not match:
                continue

            line_count += 1
            row = _album(rows, match.group(1))
            row["artist"] = row["artist"] or artist
            row["title"] = row["title"] or _title_from_annotated_line(line)
            _set_state(row, "DISCOVERED")
            _add_source(row, f"artists/{path.name}")

    return rows, {"artist_files": len(files), "artist_album_lines": line_count}


def _merge_rows(
    target: dict[str, dict[str, Any]],
    incoming: dict[str, dict[str, Any]],
) -> None:
    for album_id, incoming_row in incoming.items():
        row = _album(target, album_id)
        row["artist"] = row["artist"] or incoming_row.get("artist")
        row["title"] = row["title"] or incoming_row.get("title")

        for key, value in incoming_row["states"].items():
            if value:
                row["states"][key] = True

        row["highest_state"] = highest_state(row["states"])

        for source in incoming_row.get("sources", []):
            _add_source(row, source)


def build_lifecycle_registry(
    data_dir: Path,
    *,
    generated_at: str | None = None,
    validation_evidence: dict[str, Any] | None = None,
) -> dict[str, Any]:
    rows: dict[str, dict[str, Any]] = {}

    discovered, artist_counts = read_artist_releases(data_dir / "artists")
    _merge_rows(rows, discovered)

    attempted = load_json_file(data_dir / "attempted_albums.json")
    for album_id, payload in attempted.items():
        row = _album(rows, str(album_id))
        _set_state(row, "ATTEMPTED")
        _add_source(row, "attempted_albums.json")
        if isinstance(payload, dict):
            row["title"] = row["title"] or _title_from_annotated_line(
                str(payload.get("album_url", ""))
            )
            if payload.get("last_attempt"):
                row["timestamps"]["last_attempt"] = payload["last_attempt"]
            if payload.get("attempts") is not None:
                row["details"]["attempts"] = payload["attempts"]

    shipped_raw = load_json_file(data_dir / "shipped_jobs.json")
    shipped = shipped_raw.get("shipped", {}) if isinstance(shipped_raw, dict) else {}
    if not isinstance(shipped, dict):
        shipped = {}

    for album_id, payload in shipped.items():
        row = _album(rows, str(album_id))
        _set_state(row, "SHIPPED")
        _add_source(row, "shipped_jobs.json")
        if isinstance(payload, dict):
            if payload.get("shipped_at_utc"):
                row["timestamps"]["shipped_at_utc"] = payload["shipped_at_utc"]
            if payload.get("jobname"):
                row["details"]["jobname"] = payload["jobname"]
            if payload.get("remote_job"):
                row["details"]["remote_job"] = payload["remote_job"]

    validated = load_json_file(data_dir / "validated_albums.json")
    for album_id, payload in validated.items():
        row = _album(rows, str(album_id))
        _set_state(row, "VALIDATED")
        _add_source(row, "validated_albums.json")
        if isinstance(payload, dict):
            row["title"] = row["title"] or payload.get("folder")
            if payload.get("validated_at"):
                row["timestamps"]["validated_at"] = payload["validated_at"]
            if payload.get("folder"):
                row["details"]["validated_folder"] = payload["folder"]
            if payload.get("tracks") is not None:
                row["details"]["validated_tracks"] = payload["tracks"]

    confirmed = load_json_file(data_dir / "confirmed_albums.json")
    for album_id, payload in confirmed.items():
        row = _album(rows, str(album_id))
        _set_state(row, "CONFIRMED")
        _add_source(row, "confirmed_albums.json")
        if isinstance(payload, dict):
            row["artist"] = row["artist"] or _artist_from_filename(payload.get("artist_file"))
            if payload.get("confirmed_at"):
                row["timestamps"]["confirmed_at"] = payload["confirmed_at"]
            if payload.get("artist_file"):
                row["details"]["confirmed_artist_file"] = payload["artist_file"]

    albums = []
    for row in rows.values():
        row["artist"] = row["artist"] or "(unknown)"
        row["title"] = row["title"] or "(unknown)"
        row["sources"].sort()
        albums.append(row)

    albums.sort(
        key=lambda row: (
            -STATE_RANK.get(row["highest_state"] or "", 0),
            row["artist"].lower(),
            row["title"].lower(),
            row["album_id"],
        )
    )

    summary = summarize_registry(albums)

    registry = {
        "schema": 1,
        "generated_at": generated_at or datetime.now().isoformat(timespec="seconds"),
        "source_counts": {
            **artist_counts,
            "attempted_albums": len(attempted),
            "shipped_albums": len(shipped),
            "validated_albums": len(validated),
            "confirmed_albums": len(confirmed),
        },
        "summary": summary,
        "albums": albums,
    }

    if validation_evidence is not None:
        from curator.validator_evidence import attach_validation_evidence

        attach_validation_evidence(registry, validation_evidence)

    return registry


def summarize_registry(albums: list[dict[str, Any]]) -> dict[str, Any]:
    highest_counts = Counter(row["highest_state"] or "UNKNOWN" for row in albums)
    coverage_counts = Counter()
    for row in albums:
        for state, key in STATE_KEYS.items():
            if row["states"].get(key, False):
                coverage_counts[state] += 1

    gaps = {
        "discovered_not_attempted": sum(
            1
            for row in albums
            if row["states"]["discovered"] and not row["states"]["attempted"]
        ),
        "shipped_not_validated": sum(
            1
            for row in albums
            if row["states"]["shipped"] and not row["states"]["validated"]
        ),
        "confirmed_not_validated": sum(
            1
            for row in albums
            if row["states"]["confirmed"] and not row["states"]["validated"]
        ),
        "validated_not_discovered": sum(
            1
            for row in albums
            if row["states"]["validated"] and not row["states"]["discovered"]
        ),
    }

    return {
        "total_albums": len(albums),
        "highest_state_counts": {state: highest_counts.get(state, 0) for state in STATE_ORDER},
        "state_evidence_counts": {state: coverage_counts.get(state, 0) for state in STATE_ORDER},
        "gaps": gaps,
    }


def write_registry(registry: dict[str, Any], path: Path) -> None:
    text = json.dumps(registry, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    atomic_write_text(path, text)


def write_reports(registry: dict[str, Any], reports_dir: Path) -> None:
    reports_dir.mkdir(parents=True, exist_ok=True)
    atomic_write_text(reports_dir / "lifecycle_summary.md", render_lifecycle_summary(registry))
    atomic_write_text(reports_dir / "discovery_gap_report.md", render_discovery_gap_report(registry))
    atomic_write_text(reports_dir / "shipment_gap_report.md", render_shipment_gap_report(registry))
    atomic_write_text(reports_dir / "validation_gap_report.md", render_validation_gap_report(registry))


def _pct(count: int, total: int) -> str:
    if total == 0:
        return "0.0%"
    return f"{(count / total) * 100:.1f}%"


def _escape_cell(value: Any) -> str:
    return str(value).replace("|", "\\|").replace("\n", " ").strip()


def render_lifecycle_summary(registry: dict[str, Any]) -> str:
    summary = registry["summary"]
    total = summary["total_albums"]
    lines = [
        "# Lifecycle Summary",
        "",
        f"Generated: {registry['generated_at']}",
        "",
        "This report is derived from current state files. The filesystem remains source of truth.",
        "",
        "## Totals",
        "",
        f"- Total albums: `{total}`",
        "",
        "## Highest Lifecycle State",
        "",
        "| State | Albums | Percent |",
        "| --- | ---: | ---: |",
    ]

    for state in STATE_ORDER:
        count = summary["highest_state_counts"].get(state, 0)
        lines.append(f"| {state} | {count} | {_pct(count, total)} |")

    lines.extend(
        [
            "",
            "## State Evidence Coverage",
            "",
            "| State evidence | Albums | Percent |",
            "| --- | ---: | ---: |",
        ]
    )

    for state in STATE_ORDER:
        count = summary["state_evidence_counts"].get(state, 0)
        lines.append(f"| {state} | {count} | {_pct(count, total)} |")

    gaps = summary["gaps"]
    lines.extend(
        [
            "",
            "## Summary Observations",
            "",
            f"- Discovered but never attempted: `{gaps['discovered_not_attempted']}`",
            f"- Shipped but not validated: `{gaps['shipped_not_validated']}`",
            f"- Confirmed but not validated: `{gaps['confirmed_not_validated']}`",
            f"- Validated but not discovered: `{gaps['validated_not_discovered']}`",
            "",
        ]
    )

    return "\n".join(lines)


def render_discovery_gap_report(registry: dict[str, Any]) -> str:
    rows = [
        row
        for row in registry["albums"]
        if row["states"]["discovered"] and not row["states"]["attempted"]
    ]
    by_artist = Counter(row["artist"] for row in rows)

    lines = [
        "# Discovery Gap Report",
        "",
        f"Generated: {registry['generated_at']}",
        "",
        f"Discovered but never attempted: `{len(rows)}`",
        "",
        "## Top Artists By Backlog",
        "",
        "| Artist | Albums |",
        "| --- | ---: |",
    ]
    for artist, count in by_artist.most_common(25):
        lines.append(f"| {_escape_cell(artist)} | {count} |")

    lines.extend(["", "## Albums", "", "| Artist | Album ID | Title |", "| --- | --- | --- |"])
    for row in sorted(rows, key=lambda r: (r["artist"].lower(), r["title"].lower(), r["album_id"])):
        lines.append(
            f"| {_escape_cell(row['artist'])} | `{row['album_id']}` | {_escape_cell(row['title'])} |"
        )

    return "\n".join(lines) + "\n"


def render_shipment_gap_report(registry: dict[str, Any]) -> str:
    rows = [
        row
        for row in registry["albums"]
        if row["states"]["shipped"] and not row["states"]["validated"]
    ]
    shipped_times = [
        row["timestamps"].get("shipped_at_utc")
        for row in rows
        if row["timestamps"].get("shipped_at_utc")
    ]

    lines = [
        "# Shipment Gap Report",
        "",
        f"Generated: {registry['generated_at']}",
        "",
        f"Shipped but not validated: `{len(rows)}`",
        f"Oldest shipped evidence: `{min(shipped_times) if shipped_times else 'unknown'}`",
        f"Newest shipped evidence: `{max(shipped_times) if shipped_times else 'unknown'}`",
        "",
        "## Albums",
        "",
        "| Album ID | Artist | Title | Shipped At | Job |",
        "| --- | --- | --- | --- | --- |",
    ]

    def key(row: dict[str, Any]) -> tuple[str, str]:
        return (row["timestamps"].get("shipped_at_utc", ""), row["album_id"])

    for row in sorted(rows, key=key):
        lines.append(
            "| "
            f"`{row['album_id']}` | "
            f"{_escape_cell(row['artist'])} | "
            f"{_escape_cell(row['title'])} | "
            f"{_escape_cell(row['timestamps'].get('shipped_at_utc', ''))} | "
            f"{_escape_cell(row['details'].get('jobname', ''))} |"
        )

    return "\n".join(lines) + "\n"


def render_validation_gap_report(registry: dict[str, Any]) -> str:
    albums = registry["albums"]
    confirmed_not_validated = [
        row for row in albums if row["states"]["confirmed"] and not row["states"]["validated"]
    ]
    validated_not_discovered = [
        row for row in albums if row["states"]["validated"] and not row["states"]["discovered"]
    ]
    shipped_without_attempt = [
        row for row in albums if row["states"]["shipped"] and not row["states"]["attempted"]
    ]
    validated_without_shipped = [
        row for row in albums if row["states"]["validated"] and not row["states"]["shipped"]
    ]

    lines = [
        "# Validation Gap Report",
        "",
        f"Generated: {registry['generated_at']}",
        "",
        "## Counts",
        "",
        f"- Confirmed but not validated: `{len(confirmed_not_validated)}`",
        f"- Validated but not discovered: `{len(validated_not_discovered)}`",
        f"- Shipped without attempted evidence: `{len(shipped_without_attempt)}`",
        f"- Validated without shipped evidence: `{len(validated_without_shipped)}`",
        "",
    ]

    sections = [
        ("Confirmed But Not Validated", confirmed_not_validated),
        ("Validated But Not Discovered", validated_not_discovered),
        ("Shipped Without Attempted Evidence", shipped_without_attempt),
        ("Validated Without Shipped Evidence", validated_without_shipped),
    ]

    for title, rows in sections:
        lines.extend([f"## {title}", "", "| Album ID | Artist | Title | Evidence |", "| --- | --- | --- | --- |"])
        for row in sorted(rows, key=lambda r: (r["artist"].lower(), r["title"].lower(), r["album_id"])):
            evidence = ", ".join(state for state in STATE_ORDER if row["states"][STATE_KEYS[state]])
            lines.append(
                f"| `{row['album_id']}` | {_escape_cell(row['artist'])} | "
                f"{_escape_cell(row['title'])} | {evidence} |"
            )
        lines.append("")

    return "\n".join(lines)
