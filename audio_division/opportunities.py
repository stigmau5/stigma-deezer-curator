from __future__ import annotations

from collections import Counter
from datetime import datetime
from pathlib import Path
from typing import Any

from curator.atomic import atomic_write_text

OPPORTUNITY_CATEGORIES = (
    "missing_nfo",
    "missing_sfv",
    "missing_playlist",
    "missing_validation",
    "missing_artwork",
    "low_album_health",
    "identity_review",
    "missing_metadata",
)

PRIORITY_ORDER = {"HIGH": 0, "MEDIUM": 1, "LOW": 2}


def generate_opportunities(library: dict[str, Any]) -> list[dict[str, Any]]:
    opportunities: list[dict[str, Any]] = []
    for album in library.get("albums", []):
        album_id = str(album.get("album_id", ""))
        status = album.get("album_status", {})
        items = status.get("items", {})

        _append_if(
            opportunities,
            items.get("validation") == "Missing",
            "missing_validation",
            album,
            "HIGH",
            "Album is known but has no validation evidence.",
            "Validate Album",
        )
        _append_if(
            opportunities,
            album.get("validation_status") == "validated" and items.get("nfo") == "Missing",
            "missing_nfo",
            album,
            "HIGH",
            "Validated album is missing NFO documentation.",
            "Generate NFO",
        )
        _append_if(
            opportunities,
            album.get("validation_status") == "validated" and items.get("sfv") == "Missing",
            "missing_sfv",
            album,
            "MEDIUM",
            "Validated album is missing SFV verification data.",
            "Generate SFV",
        )
        _append_if(
            opportunities,
            items.get("playlist") == "Missing",
            "missing_playlist",
            album,
            "LOW",
            "Album folder has no playlist artifact.",
            "Generate Playlist",
        )
        _append_if(
            opportunities,
            items.get("artwork") == "Missing",
            "missing_artwork",
            album,
            "LOW",
            "Album has no local or cached artwork evidence.",
            "Review Artwork",
        )
        _append_if(
            opportunities,
            items.get("metadata") == "Missing",
            "missing_metadata",
            album,
            "MEDIUM",
            "Album is missing metadata cache coverage.",
            "Refresh Metadata",
        )
        _append_if(
            opportunities,
            album.get("identity_confidence") not in ("HIGH", "MEDIUM"),
            "identity_review",
            album,
            "MEDIUM",
            "Album identity is not confidently resolved.",
            "Review Identity",
        )
        _append_if(
            opportunities,
            status.get("health_percent", 100) < 70,
            "low_album_health",
            album,
            "MEDIUM",
            "Album health is below the maintenance threshold.",
            "Review Album",
        )

    return sorted(opportunities, key=lambda item: (PRIORITY_ORDER[item["priority"]], item["category"], item["artist"], item["album"]))


def filter_opportunities(
    opportunities: list[dict[str, Any]],
    *,
    category: str = "",
    priority: str = "",
    artist: str = "",
) -> list[dict[str, Any]]:
    category = category.strip()
    priority = priority.strip().upper()
    artist = artist.strip().lower()
    out = []
    for opportunity in opportunities:
        if category and opportunity.get("category") != category:
            continue
        if priority and opportunity.get("priority") != priority:
            continue
        if artist and artist not in opportunity.get("artist", "").lower():
            continue
        out.append(opportunity)
    return out


def opportunity_summary(opportunities: list[dict[str, Any]]) -> dict[str, Any]:
    priorities = Counter(item["priority"] for item in opportunities)
    categories = Counter(item["category"] for item in opportunities)
    readiness = Counter(item.get("readiness", "") for item in opportunities if item.get("readiness"))
    return {
        "total": len(opportunities),
        "high": priorities.get("HIGH", 0),
        "medium": priorities.get("MEDIUM", 0),
        "low": priorities.get("LOW", 0),
        "top_categories": categories.most_common(5),
        "by_category": {category: categories.get(category, 0) for category in OPPORTUNITY_CATEGORIES},
        "by_readiness": dict(readiness),
    }


def render_opportunities_report(opportunities: list[dict[str, Any]], *, generated_at: str | None = None) -> str:
    generated_at = generated_at or datetime.now().isoformat(timespec="seconds")
    summary = opportunity_summary(opportunities)
    lines = [
        "# Archive Opportunities Report",
        "",
        f"Generated: {generated_at}",
        "",
        "Archive opportunities are read-only maintenance recommendations. No operations are executed by this report.",
        "",
        "## Summary",
        "",
        f"- Total opportunities: `{summary['total']}`",
        f"- High priority: `{summary['high']}`",
        f"- Medium priority: `{summary['medium']}`",
        f"- Low priority: `{summary['low']}`",
        "",
        "| Category | Opportunities |",
        "| --- | ---: |",
    ]
    for category, count in summary["by_category"].items():
        lines.append(f"| {category} | {count} |")

    lines.extend(["", "## Readiness Categories", "", "| Readiness | Opportunities |", "| --- | ---: |"])
    for readiness, count in sorted(summary["by_readiness"].items()):
        lines.append(f"| {readiness} | {count} |")

    lines.extend(
        [
            "",
            "## Opportunities",
            "",
            "| Priority | Category | Album ID | Artist | Album | Recommended Action | Description |",
            "| --- | --- | --- | --- | --- | --- | --- |",
        ]
    )
    for item in opportunities[:500]:
        lines.append(
            f"| {item['priority']} | {item['category']} | `{_escape(item.get('album_id'))}` | "
            f"{_escape(item.get('artist'))} | {_escape(item.get('album'))} | "
            f"{_escape(item.get('recommended_action'))} | {_escape(item.get('description'))} |"
        )
    return "\n".join(lines) + "\n"


def write_opportunities_report(opportunities: list[dict[str, Any]], reports_dir: Path) -> None:
    reports_dir.mkdir(parents=True, exist_ok=True)
    atomic_write_text(reports_dir / "archive_opportunities_report.md", render_opportunities_report(opportunities))


def _append_if(
    opportunities: list[dict[str, Any]],
    condition: bool,
    category: str,
    album: dict[str, Any],
    priority: str,
    description: str,
    recommended_action: str,
) -> None:
    if not condition:
        return
    album_id = str(album.get("album_id", ""))
    opportunities.append(
        {
            "id": f"{category}:{album_id}",
            "category": category,
            "album_id": album_id,
            "artist": album.get("artist", ""),
            "album": album.get("title", ""),
            "priority": priority,
            "description": description,
            "recommended_action": recommended_action,
            "readiness": album.get("archive_readiness", {}).get("state", ""),
        }
    )


def _escape(value: Any) -> str:
    return str(value or "").replace("|", "\\|").replace("\n", " ").strip()
