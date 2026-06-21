from __future__ import annotations

from collections import Counter
from datetime import datetime
from pathlib import Path
from typing import Any

from curator.atomic import atomic_write_text

ACTION_CATEGORIES = (
    "missing_nfo",
    "missing_sfv",
    "missing_validation",
    "missing_metadata",
    "missing_artwork",
    "identity_review",
)

PRIORITY_ORDER = {"high": 0, "medium": 1, "low": 2}


def generate_archive_actions(
    lifecycle: dict[str, Any],
    identity: dict[str, Any],
    metadata: dict[str, Any],
    albums: list[dict[str, Any]] | None = None,
) -> list[dict[str, Any]]:
    if albums is None:
        from audio_division.library import build_library

        albums = build_library(lifecycle, identity, metadata).get("albums", [])
    return _actions_from_maintenance(albums)


def _actions_from_maintenance(albums: list[dict[str, Any]]) -> list[dict[str, Any]]:
    from audio_division.maintenance import (
        CATEGORY_NEEDS_DOCUMENTATION,
        CATEGORY_NEEDS_METADATA,
        CATEGORY_NEEDS_REVIEW,
        CATEGORY_NEEDS_VALIDATION,
        CATEGORY_WARNINGS,
        maintenance_records,
    )

    actions = []
    for album in maintenance_records(albums):
        category = album["maintenance_category"]
        truth_items = album.get("album_truth", {}).get("items", {})
        priority = album["maintenance_priority"].lower()
        if priority == "info":
            continue
        categories = []
        if category == CATEGORY_NEEDS_VALIDATION:
            categories = ["missing_validation"]
        elif category == CATEGORY_NEEDS_DOCUMENTATION:
            categories = [name for field, name in (("nfo", "missing_nfo"), ("sfv", "missing_sfv")) if truth_items.get(field) != "Present"]
        elif category == CATEGORY_NEEDS_METADATA:
            categories = ["missing_metadata"]
        elif category in {CATEGORY_NEEDS_REVIEW, CATEGORY_WARNINGS}:
            categories = ["missing_artwork"] if truth_items.get("artwork") != "Present" else ["identity_review"]
        for action_category in categories:
            actions.append(
                _action(
                    action_category,
                    album.get("album_id"),
                    album.get("artist"),
                    album.get("title") or album.get("album"),
                    priority,
                    album["maintenance_reason"],
                    [f"maintenance:{category}"],
                )
            )
    return sorted(actions, key=lambda item: (PRIORITY_ORDER[item["priority"]], item["type"], item.get("title") or ""))


def action_summary(actions: list[dict[str, Any]]) -> dict[str, Any]:
    categories = Counter(action["type"] for action in actions)
    priorities = Counter(action["priority"] for action in actions)
    return {
        "total_actions": len(actions),
        "by_category": {category: categories.get(category, 0) for category in ACTION_CATEGORIES},
        "by_priority": {priority: priorities.get(priority, 0) for priority in ("high", "medium", "low")},
    }


def render_archive_actions_report(actions: list[dict[str, Any]], *, generated_at: str | None = None) -> str:
    generated_at = generated_at or datetime.now().isoformat(timespec="seconds")
    summary = action_summary(actions)
    lines = [
        "# Archive Actions Report",
        "",
        f"Generated: {generated_at}",
        "",
        "Archive actions are read-only improvement opportunities. No actions are executed by this report.",
        "",
        "## Summary",
        "",
        f"- Total actions: `{summary['total_actions']}`",
        "",
        "| Category | Actions |",
        "| --- | ---: |",
    ]
    for category, count in summary["by_category"].items():
        lines.append(f"| {category} | {count} |")

    lines.extend(
        [
            "",
            "## Actions",
            "",
            "| Priority | Category | Album ID | Artist | Title | Description | Evidence |",
            "| --- | --- | --- | --- | --- | --- | --- |",
        ]
    )
    for action in actions[:500]:
        lines.append(
            f"| {action['priority']} | {action['type']} | `{_escape(action.get('album_id'))}` | "
            f"{_escape(action.get('artist'))} | {_escape(action.get('title'))} | "
            f"{_escape(action.get('description'))} | {_escape(', '.join(action.get('evidence', [])))} |"
        )
    return "\n".join(lines) + "\n"


def write_archive_actions_report(actions: list[dict[str, Any]], reports_dir: Path) -> None:
    reports_dir.mkdir(parents=True, exist_ok=True)
    atomic_write_text(reports_dir / "archive_actions_report.md", render_archive_actions_report(actions))


def _action(
    category: str,
    album_id: Any,
    artist: Any,
    title: Any,
    priority: str,
    description: str,
    evidence: list[str],
    *,
    extra: dict[str, Any] | None = None,
) -> dict[str, Any]:
    action = {
        "type": category,
        "album_id": str(album_id) if album_id else "",
        "artist": artist or "",
        "title": title or "",
        "priority": priority,
        "description": description,
        "evidence": evidence,
    }
    if extra:
        action.update(extra)
    return action


def _escape(value: Any) -> str:
    return str(value or "").replace("|", "\\|").replace("\n", " ").strip()
