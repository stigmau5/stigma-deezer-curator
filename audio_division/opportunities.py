from __future__ import annotations

from collections import Counter
from datetime import datetime
from pathlib import Path
from typing import Any

from audio_division.maintenance import (
    CATEGORY_NEEDS_DOCUMENTATION,
    CATEGORY_NEEDS_METADATA,
    CATEGORY_NEEDS_REVIEW,
    CATEGORY_NEEDS_VALIDATION,
    CATEGORY_READY,
    CATEGORY_WARNINGS,
    maintenance_records,
)
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

HUB_OPPORTUNITY_CATEGORIES = (
    "NEEDS_VALIDATION",
    "NEEDS_DOCUMENTATION",
    "NEEDS_METADATA",
    "NEEDS_REVIEW",
    "ARCHIVE_READY",
)

PRIORITY_ORDER = {"HIGH": 0, "MEDIUM": 1, "LOW": 2}


def generate_opportunities(library: dict[str, Any]) -> list[dict[str, Any]]:
    opportunities: list[dict[str, Any]] = []
    for album in maintenance_records(library.get("albums", [])):
        items = album.get("album_truth", {}).get("items", {})
        category = album["maintenance_category"]
        priority = album["maintenance_priority"]
        reason = album["maintenance_reason"]

        if category == CATEGORY_NEEDS_VALIDATION:
            _append_if(opportunities, True, "missing_validation", album, priority, reason, "Validate Album")
        elif category == CATEGORY_NEEDS_DOCUMENTATION:
            _append_if(opportunities, items.get("nfo") != "Present", "missing_nfo", album, priority, reason, "Generate NFO")
            _append_if(opportunities, items.get("sfv") != "Present", "missing_sfv", album, priority, reason, "Generate SFV")
        elif category == CATEGORY_NEEDS_METADATA:
            _append_if(opportunities, True, "missing_metadata", album, priority, reason, "Refresh Metadata")
        elif category in {CATEGORY_NEEDS_REVIEW, CATEGORY_WARNINGS}:
            if items.get("artwork") != "Present":
                _append_if(opportunities, True, "missing_artwork", album, priority, reason, "Review Artwork")
            elif items.get("playlist") != "Present":
                _append_if(opportunities, True, "missing_playlist", album, priority, reason, "Review Playlist")
            else:
                _append_if(opportunities, True, "identity_review", album, priority, reason, "Review Album")

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
        "Archive opportunities are a secondary rendering of the canonical Maintenance model. No operations are executed by this report.",
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


def derive_hub_opportunities(library: dict[str, Any]) -> list[dict[str, Any]]:
    opportunities = [_hub_opportunity(album) for album in maintenance_records(library.get("albums", []))]
    return sorted(opportunities, key=lambda item: (PRIORITY_ORDER[item["priority"]], item["category"], item["artist"], item["album"]))


def hub_opportunity_summary(opportunities: list[dict[str, Any]]) -> dict[str, Any]:
    categories = Counter(item["category"] for item in opportunities)
    priorities = Counter(item["priority"] for item in opportunities)
    most_urgent = next((item["category"] for item in opportunities if item["priority"] == "HIGH"), "")
    return {
        "total": len(opportunities),
        "by_category": {category: categories.get(category, 0) for category in HUB_OPPORTUNITY_CATEGORIES},
        "by_priority": {priority: priorities.get(priority, 0) for priority in ("HIGH", "MEDIUM", "LOW")},
        "most_urgent_category": most_urgent,
        "top_categories": categories.most_common(5),
    }


def group_hub_opportunities(opportunities: list[dict[str, Any]]) -> dict[str, list[dict[str, Any]]]:
    groups = {category: [] for category in HUB_OPPORTUNITY_CATEGORIES}
    for opportunity in opportunities:
        groups.setdefault(opportunity["category"], []).append(opportunity)
    return groups


def render_hub_opportunities_report(opportunities: list[dict[str, Any]], *, generated_at: str | None = None) -> str:
    generated_at = generated_at or datetime.now().isoformat(timespec="seconds")
    summary = hub_opportunity_summary(opportunities)
    lines = [
        "# Opportunities Report",
        "",
        f"Generated: {generated_at}",
        "",
        "Opportunities are a secondary rendering of AlbumTruth-owned Maintenance categories.",
        "",
        "## Summary",
        "",
        f"- Total albums: `{summary['total']}`",
        f"- Most urgent category: `{summary['most_urgent_category'] or 'none'}`",
        "",
        "| Category | Albums |",
        "| --- | ---: |",
    ]
    for category, count in summary["by_category"].items():
        lines.append(f"| {category} | {count} |")
    lines.extend(["", "## Albums", "", "| Priority | Category | Artist | Album | Lifecycle | Readiness | Reason |", "| --- | --- | --- | --- | --- | --- | --- |"])
    for item in opportunities[:500]:
        lines.append(
            f"| {item['priority']} | {item['category']} | {_escape(item.get('artist'))} | {_escape(item.get('album'))} | "
            f"{_escape(item.get('lifecycle_state'))} | {_escape(item.get('archive_readiness'))} | {_escape(item.get('reason'))} |"
        )
    return "\n".join(lines) + "\n"


def render_archive_ready_report(opportunities: list[dict[str, Any]]) -> str:
    ready = [item for item in opportunities if item["category"] == "ARCHIVE_READY"]
    return _render_category_report("Archive Ready Report", ready)


def render_review_candidates_report(opportunities: list[dict[str, Any]]) -> str:
    review = [item for item in opportunities if item["category"] == "NEEDS_REVIEW"]
    return _render_category_report("Review Candidates Report", review)


def write_hub_opportunity_reports(opportunities: list[dict[str, Any]], reports_dir: Path) -> None:
    reports_dir.mkdir(parents=True, exist_ok=True)
    atomic_write_text(reports_dir / "opportunities_report.md", render_hub_opportunities_report(opportunities))
    atomic_write_text(reports_dir / "archive_ready_report.md", render_archive_ready_report(opportunities))
    atomic_write_text(reports_dir / "review_candidates_report.md", render_review_candidates_report(opportunities))


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


def _hub_opportunity(album: dict[str, Any]) -> dict[str, Any]:
    maintenance_category = album["maintenance_category"]
    category = {
        CATEGORY_NEEDS_VALIDATION: "NEEDS_VALIDATION",
        CATEGORY_NEEDS_DOCUMENTATION: "NEEDS_DOCUMENTATION",
        CATEGORY_NEEDS_METADATA: "NEEDS_METADATA",
        CATEGORY_NEEDS_REVIEW: "NEEDS_REVIEW",
        CATEGORY_WARNINGS: "NEEDS_REVIEW",
        CATEGORY_READY: "ARCHIVE_READY",
    }[maintenance_category]
    action = {
        CATEGORY_NEEDS_VALIDATION: "Validate Album",
        CATEGORY_NEEDS_DOCUMENTATION: "Generate Documentation",
        CATEGORY_NEEDS_METADATA: "Refresh Metadata",
        CATEGORY_NEEDS_REVIEW: "Open Folder",
        CATEGORY_WARNINGS: "Open Folder",
        CATEGORY_READY: "Open Folder",
    }[maintenance_category]
    readiness_state = album.get("album_truth", {}).get("readiness", "UNKNOWN")

    return {
        "id": f"{category}:{album.get('album_id', '')}",
        "category": category,
        "album_id": str(album.get("album_id", "")),
        "artist": album.get("artist", ""),
        "album": album.get("title", ""),
        "lifecycle_state": album.get("lifecycle_state", ""),
        "archive_readiness": readiness_state,
        "priority": "LOW" if album["maintenance_priority"] == "INFO" else album["maintenance_priority"],
        "reason": album["maintenance_reason"],
        "recommended_action": action,
    }


def _render_category_report(title: str, opportunities: list[dict[str, Any]]) -> str:
    lines = [
        f"# {title}",
        "",
        f"Albums: `{len(opportunities)}`",
        "",
        "| Priority | Artist | Album | Lifecycle | Reason |",
        "| --- | --- | --- | --- | --- |",
    ]
    for item in opportunities[:500]:
        lines.append(
            f"| {item['priority']} | {_escape(item.get('artist'))} | {_escape(item.get('album'))} | "
            f"{_escape(item.get('lifecycle_state'))} | {_escape(item.get('reason'))} |"
        )
    return "\n".join(lines) + "\n"


def _escape(value: Any) -> str:
    return str(value or "").replace("|", "\\|").replace("\n", " ").strip()
