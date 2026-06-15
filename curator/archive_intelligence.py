from __future__ import annotations

import json
from collections import Counter, defaultdict
from pathlib import Path
from typing import Any

from curator.atomic import atomic_write_text
from curator.lifecycle import STATE_ORDER


def load_lifecycle_registry(path: Path) -> dict[str, Any]:
    return json.loads(path.read_text(encoding="utf-8"))


def _pct(count: int, total: int) -> float:
    if total == 0:
        return 0.0
    return (count / total) * 100


def _pct_text(count: int, total: int) -> str:
    return f"{_pct(count, total):.1f}%"


def _escape_cell(value: Any) -> str:
    return str(value).replace("|", "\\|").replace("\n", " ").strip()


def _album_sort_key(row: dict[str, Any]) -> tuple[str, str, str]:
    return (str(row.get("artist", "")).lower(), str(row.get("title", "")).lower(), row["album_id"])


def state_counts(registry: dict[str, Any]) -> dict[str, int]:
    counts = Counter(row.get("highest_state") or "UNKNOWN" for row in registry.get("albums", []))
    return {state: counts.get(state, 0) for state in STATE_ORDER}


def calculate_artist_coverage(registry: dict[str, Any]) -> list[dict[str, Any]]:
    artists: dict[str, dict[str, Any]] = defaultdict(
        lambda: {
            "artist": "",
            "discovered": 0,
            "validated": 0,
            "confirmed": 0,
            "backlog": 0,
        }
    )

    for row in registry.get("albums", []):
        if not row.get("states", {}).get("discovered", False):
            continue

        artist = row.get("artist") or "(unknown)"
        item = artists[artist]
        item["artist"] = artist
        item["discovered"] += 1
        if row.get("states", {}).get("validated", False):
            item["validated"] += 1
        if row.get("states", {}).get("confirmed", False):
            item["confirmed"] += 1
        if not row.get("states", {}).get("attempted", False):
            item["backlog"] += 1

    out = []
    for item in artists.values():
        discovered = item["discovered"]
        item["coverage_percent"] = _pct(item["validated"], discovered)
        out.append(item)

    return sorted(
        out,
        key=lambda row: (
            -row["coverage_percent"],
            -row["validated"],
            -row["confirmed"],
            row["artist"].lower(),
        ),
    )


def calculate_backlog(registry: dict[str, Any]) -> dict[str, Any]:
    rows = [
        row
        for row in registry.get("albums", [])
        if row.get("states", {}).get("discovered", False)
        and not row.get("states", {}).get("attempted", False)
    ]
    by_artist = Counter(row.get("artist") or "(unknown)" for row in rows)
    return {
        "total": len(rows),
        "by_artist": by_artist,
        "albums": sorted(rows, key=_album_sort_key),
    }


def calculate_gaps(registry: dict[str, Any]) -> dict[str, list[dict[str, Any]]]:
    albums = registry.get("albums", [])
    return {
        "shipped_not_validated": [
            row
            for row in albums
            if row.get("states", {}).get("shipped", False)
            and not row.get("states", {}).get("validated", False)
        ],
        "attempted_not_shipped": [
            row
            for row in albums
            if row.get("states", {}).get("attempted", False)
            and not row.get("states", {}).get("shipped", False)
        ],
        "confirmed_not_validated": [
            row
            for row in albums
            if row.get("states", {}).get("confirmed", False)
            and not row.get("states", {}).get("validated", False)
        ],
        "validated_not_discovered": [
            row
            for row in albums
            if row.get("states", {}).get("validated", False)
            and not row.get("states", {}).get("discovered", False)
        ],
    }


def render_archive_health_report(registry: dict[str, Any]) -> str:
    total = len(registry.get("albums", []))
    counts = state_counts(registry)
    gaps = calculate_gaps(registry)
    backlog = calculate_backlog(registry)

    lines = [
        "# Archive Health Report",
        "",
        f"Generated from lifecycle registry: {registry.get('generated_at', 'unknown')}",
        "",
        "The lifecycle registry is derived state. Filesystem and source state files remain truth.",
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
        count = counts[state]
        lines.append(f"| {state} | {count} | {_pct_text(count, total)} |")

    lines.extend(
        [
            "",
            "## Overall Observations",
            "",
            f"- Discovered backlog: `{backlog['total']}` albums discovered but never attempted.",
            f"- Shipment gap: `{len(gaps['shipped_not_validated'])}` shipped albums are not validated.",
            f"- Attempt gap: `{len(gaps['attempted_not_shipped'])}` attempted albums are not shipped.",
            f"- Confirmation gap: `{len(gaps['confirmed_not_validated'])}` confirmed albums are not validated.",
            f"- Archive-only validation signal: `{len(gaps['validated_not_discovered'])}` validated albums are not discovered in artist files.",
            "",
        ]
    )
    return "\n".join(lines)


def render_artist_coverage_report(registry: dict[str, Any]) -> str:
    coverage = calculate_artist_coverage(registry)
    complete = [row for row in coverage if row["discovered"] > 0 and row["validated"] == row["discovered"]]
    incomplete = [row for row in coverage if row["discovered"] > row["validated"]]
    incomplete.sort(key=lambda row: (-row["backlog"], row["coverage_percent"], row["artist"].lower()))

    lines = [
        "# Artist Coverage Report",
        "",
        f"Generated from lifecycle registry: {registry.get('generated_at', 'unknown')}",
        "",
        "Coverage is validated / discovered for albums present in artist files.",
        "",
        "## Top Complete Artists",
        "",
        "| Artist | Discovered | Validated | Confirmed | Coverage |",
        "| --- | ---: | ---: | ---: | ---: |",
    ]
    for row in complete[:25]:
        lines.append(
            f"| {_escape_cell(row['artist'])} | {row['discovered']} | {row['validated']} | "
            f"{row['confirmed']} | {_pct_text(row['validated'], row['discovered'])} |"
        )

    lines.extend(
        [
            "",
            "## Top Incomplete Artists",
            "",
            "| Artist | Discovered | Validated | Confirmed | Coverage | Backlog |",
            "| --- | ---: | ---: | ---: | ---: | ---: |",
        ]
    )
    for row in incomplete[:25]:
        lines.append(
            f"| {_escape_cell(row['artist'])} | {row['discovered']} | {row['validated']} | "
            f"{row['confirmed']} | {_pct_text(row['validated'], row['discovered'])} | {row['backlog']} |"
        )

    lines.extend(
        [
            "",
            "## All Artists",
            "",
            "| Artist | Discovered | Validated | Confirmed | Coverage |",
            "| --- | ---: | ---: | ---: | ---: |",
        ]
    )
    for row in coverage:
        lines.append(
            f"| {_escape_cell(row['artist'])} | {row['discovered']} | {row['validated']} | "
            f"{row['confirmed']} | {_pct_text(row['validated'], row['discovered'])} |"
        )

    return "\n".join(lines) + "\n"


def render_backlog_report(registry: dict[str, Any]) -> str:
    backlog = calculate_backlog(registry)
    lines = [
        "# Backlog Report",
        "",
        f"Generated from lifecycle registry: {registry.get('generated_at', 'unknown')}",
        "",
        "Focus: `DISCOVERED` albums that have never reached `ATTEMPTED`.",
        "",
        f"- Total backlog albums: `{backlog['total']}`",
        "",
        "## Artists With Largest Backlog",
        "",
        "| Artist | Backlog Albums |",
        "| --- | ---: |",
    ]
    for artist, count in backlog["by_artist"].most_common(50):
        lines.append(f"| {_escape_cell(artist)} | {count} |")

    lines.extend(
        [
            "",
            "## Top Backlog Albums",
            "",
            "| Artist | Album ID | Title |",
            "| --- | --- | --- |",
        ]
    )
    for row in backlog["albums"][:500]:
        lines.append(
            f"| {_escape_cell(row['artist'])} | `{row['album_id']}` | {_escape_cell(row['title'])} |"
        )

    return "\n".join(lines) + "\n"


def render_gap_analysis_report(registry: dict[str, Any]) -> str:
    gaps = calculate_gaps(registry)
    lines = [
        "# Gap Analysis Report",
        "",
        f"Generated from lifecycle registry: {registry.get('generated_at', 'unknown')}",
        "",
        "## Counts",
        "",
        f"- Shipped but not validated: `{len(gaps['shipped_not_validated'])}`",
        f"- Attempted but not shipped: `{len(gaps['attempted_not_shipped'])}`",
        f"- Confirmed but not validated: `{len(gaps['confirmed_not_validated'])}`",
        f"- Validated but not discovered: `{len(gaps['validated_not_discovered'])}`",
        "",
    ]

    sections = [
        ("Shipped But Not Validated", gaps["shipped_not_validated"]),
        ("Attempted But Not Shipped", gaps["attempted_not_shipped"]),
        ("Confirmed But Not Validated", gaps["confirmed_not_validated"]),
        ("Validated But Not Discovered", gaps["validated_not_discovered"]),
    ]

    for title, rows in sections:
        lines.extend([f"## {title}", "", "| Album ID | Artist | Title | Highest State |", "| --- | --- | --- | --- |"])
        for row in sorted(rows, key=_album_sort_key)[:200]:
            lines.append(
                f"| `{row['album_id']}` | {_escape_cell(row['artist'])} | "
                f"{_escape_cell(row['title'])} | {row.get('highest_state', '')} |"
            )
        lines.append("")

    return "\n".join(lines)


def write_archive_intelligence_reports(registry: dict[str, Any], reports_dir: Path) -> None:
    reports_dir.mkdir(parents=True, exist_ok=True)
    atomic_write_text(reports_dir / "archive_health_report.md", render_archive_health_report(registry))
    atomic_write_text(reports_dir / "artist_coverage_report.md", render_artist_coverage_report(registry))
    atomic_write_text(reports_dir / "backlog_report.md", render_backlog_report(registry))
    atomic_write_text(reports_dir / "gap_analysis_report.md", render_gap_analysis_report(registry))
