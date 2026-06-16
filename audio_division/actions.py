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
) -> list[dict[str, Any]]:
    actions: list[dict[str, Any]] = []
    metadata_albums = metadata.get("albums", {})

    for row in lifecycle.get("albums", []):
        album_id = str(row.get("album_id"))
        states = row.get("states", {})
        artist = row.get("artist")
        title = row.get("title")

        if states.get("shipped") and not states.get("validated"):
            actions.append(
                _action(
                    "missing_validation",
                    album_id,
                    artist,
                    title,
                    "high",
                    "Album was shipped but has no validation evidence.",
                    ["shipped_not_validated"],
                )
            )

        if states.get("validated"):
            actions.append(
                _action(
                    "missing_nfo",
                    album_id,
                    artist,
                    title,
                    "medium",
                    "Album is validated but has no tracked NFO evidence.",
                    ["validated_album", "nfo_tracking_not_integrated"],
                )
            )
            actions.append(
                _action(
                    "missing_sfv",
                    album_id,
                    artist,
                    title,
                    "low",
                    "Album is validated but has no tracked SFV evidence.",
                    ["validated_album", "sfv_tracking_not_integrated"],
                )
            )

        if album_id and album_id not in metadata_albums:
            actions.append(
                _action(
                    "missing_metadata",
                    album_id,
                    artist,
                    title,
                    "medium",
                    "Album is present in lifecycle registry but missing metadata cache entry.",
                    ["metadata_cache_miss"],
                )
            )
        elif album_id:
            album_meta = metadata_albums.get(album_id, {})
            covers = album_meta.get("covers", {}) if isinstance(album_meta, dict) else {}
            if not any(covers.values()):
                actions.append(
                    _action(
                        "missing_artwork",
                        album_id,
                        artist,
                        title,
                        "low",
                        "Album metadata is cached but has no cover URLs.",
                        ["metadata_cached", "missing_cover_urls"],
                    )
                )

    for item in identity.get("unresolved", []):
        best = (item.get("candidates") or [{}])[0]
        actions.append(
            _action(
                "identity_review",
                best.get("deezer_album_id"),
                best.get("artist") or item.get("parsed_folder", {}).get("artist"),
                best.get("title") or item.get("parsed_folder", {}).get("title"),
                "high" if item.get("candidates") else "medium",
                "Validator evidence could not be confidently linked to a lifecycle album.",
                [item.get("reason", "unresolved_identity")],
                extra={
                    "folder": item.get("folder"),
                    "path": item.get("path"),
                    "candidate_count": len(item.get("candidates", [])),
                },
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
