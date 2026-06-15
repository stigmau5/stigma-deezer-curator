from __future__ import annotations

import difflib
from collections import Counter
from datetime import datetime
from pathlib import Path
from typing import Any

from curator.atomic import atomic_write_text
from curator.identity import normalize_identity_text

RECOVERY_LEVELS = ("RECOVERABLE_HIGH", "RECOVERABLE_MEDIUM", "RECOVERABLE_LOW", "UNRECOVERABLE")


def lifecycle_candidates(lifecycle_registry: dict[str, Any]) -> list[dict[str, Any]]:
    candidates = []
    for row in lifecycle_registry.get("albums", []):
        details = row.get("details", {})
        validation = row.get("validation_evidence", {})
        candidates.append(
            {
                "deezer_album_id": str(row.get("album_id")),
                "artist": row.get("artist"),
                "title": row.get("title"),
                "normalized_artist": normalize_identity_text(row.get("artist")),
                "normalized_title": normalize_identity_text(row.get("title")),
                "year": details.get("year") or details.get("release_year"),
                "track_count": details.get("validated_tracks") or validation.get("track_count"),
                "highest_lifecycle_state": row.get("highest_state"),
            }
        )
    return candidates


def recovery_level(
    parsed_folder: dict[str, Any],
    candidate: dict[str, Any],
    validation: dict[str, Any],
) -> tuple[str, list[str]]:
    reasons: list[str] = []
    artist_match = normalize_identity_text(parsed_folder.get("artist")) == candidate.get("normalized_artist")
    title_match = normalize_identity_text(parsed_folder.get("title")) == candidate.get("normalized_title")

    if artist_match:
        reasons.append("exact_artist")
    if title_match:
        reasons.append("exact_title")

    if artist_match and title_match:
        year = parsed_folder.get("year")
        candidate_year = candidate.get("year")
        track_count = validation.get("track_count")
        candidate_track_count = candidate.get("track_count")
        year_match = bool(year and candidate_year and str(year) == str(candidate_year))
        track_count_match = bool(
            track_count is not None
            and candidate_track_count is not None
            and int(track_count) == int(candidate_track_count)
        )
        if year_match:
            reasons.append("matching_year")
        if track_count_match:
            reasons.append("matching_track_count")
        if year_match and track_count_match:
            return "RECOVERABLE_HIGH", reasons
        return "RECOVERABLE_MEDIUM", reasons

    title_similarity = difflib.SequenceMatcher(
        None,
        normalize_identity_text(parsed_folder.get("title")),
        candidate.get("normalized_title", ""),
    ).ratio()
    if artist_match and title_similarity >= 0.72:
        reasons.extend(["exact_artist", f"title_similarity_{title_similarity:.2f}"])
        return "RECOVERABLE_LOW", sorted(set(reasons))

    return "UNRECOVERABLE", reasons


def recovery_candidates_for_unresolved(
    unresolved: dict[str, Any],
    candidates: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    parsed_folder = unresolved.get("parsed_folder", {})
    validation = unresolved.get("validation", {})
    scored: list[dict[str, Any]] = []

    for candidate in candidates:
        level, reasons = recovery_level(parsed_folder, candidate, validation)
        if level == "UNRECOVERABLE":
            continue
        scored.append(
            {
                "deezer_album_id": candidate["deezer_album_id"],
                "artist": candidate.get("artist"),
                "title": candidate.get("title"),
                "highest_lifecycle_state": candidate.get("highest_lifecycle_state"),
                "recovery_level": level,
                "reasons": reasons,
            }
        )

    rank = {level: idx for idx, level in enumerate(RECOVERY_LEVELS)}
    return sorted(scored, key=lambda item: (rank[item["recovery_level"]], item["artist"] or "", item["title"] or ""))[
        :10
    ]


def build_archive_identity_recovery(
    identity_registry: dict[str, Any],
    lifecycle_registry: dict[str, Any],
    *,
    generated_at: str | None = None,
) -> dict[str, Any]:
    candidates = lifecycle_candidates(lifecycle_registry)
    recoverable: list[dict[str, Any]] = []
    unrecoverable: list[dict[str, Any]] = []

    for unresolved in identity_registry.get("unresolved", []):
        matches = recovery_candidates_for_unresolved(unresolved, candidates)
        if matches:
            best_level = matches[0]["recovery_level"]
            recoverable.append({**unresolved, "recovery_level": best_level, "recovery_candidates": matches})
        else:
            unrecoverable.append({**unresolved, "recovery_level": "UNRECOVERABLE", "recovery_candidates": []})

    recovery_counts = Counter(item["recovery_level"] for item in recoverable)
    recovery_counts["UNRECOVERABLE"] = len(unrecoverable)
    strength = archive_strength(identity_registry, lifecycle_registry)

    return {
        "schema": 1,
        "generated_at": generated_at or datetime.now().isoformat(timespec="seconds"),
        "summary": {
            "unresolved_validator_logs": len(identity_registry.get("unresolved", [])),
            "recoverable_total": len(recoverable),
            "unrecoverable_total": len(unrecoverable),
            "recovery_counts": {level: recovery_counts.get(level, 0) for level in RECOVERY_LEVELS},
        },
        "archive_strength": strength,
        "recoverable": recoverable,
        "unrecoverable": unrecoverable,
    }


def archive_strength(identity_registry: dict[str, Any], lifecycle_registry: dict[str, Any]) -> dict[str, Any]:
    releases = identity_registry.get("releases", [])
    total = len(releases)
    high_identity = sum(1 for row in releases if row.get("identity_confidence") == "HIGH")
    validation = sum(1 for row in releases if row.get("validation", {}).get("available"))
    lifecycle = sum(1 for row in releases if row.get("discovery_identity", {}).get("deezer_album_id"))

    categories = {
        "lifecycle_coverage": _ratio(lifecycle, total),
        "identity_coverage": _ratio(high_identity, total),
        "validation_coverage": _ratio(validation, total),
        "documentation_coverage": 0.0,
        "metadata_coverage": 0.0,
    }
    overall = sum(categories.values()) / len(categories) if categories else 0.0
    return {
        "total_releases": total,
        "categories": categories,
        "overall_archive_strength_score": round(overall, 4),
    }


def render_archive_identity_recovery_report(registry: dict[str, Any]) -> str:
    summary = registry["summary"]
    lines = [
        "# Archive Identity Recovery Report",
        "",
        f"Generated: {registry['generated_at']}",
        "",
        "Identity recovery is derived analysis only. No archive files, tags, validator outputs, or metadata are modified.",
        "",
        "## Summary",
        "",
        f"- Unresolved validator logs: `{summary['unresolved_validator_logs']}`",
        f"- Recoverable today: `{summary['recoverable_total']}`",
        f"- Unrecoverable today: `{summary['unrecoverable_total']}`",
        "",
        "| Recovery level | Logs |",
        "| --- | ---: |",
    ]
    for level in RECOVERY_LEVELS:
        lines.append(f"| {level} | {summary['recovery_counts'].get(level, 0)} |")
    lines.extend(
        [
            "",
            "## Improvement Opportunity",
            "",
            "- Add or recover `ALBUM_ID` tags to turn review candidates into high-confidence identity links.",
            "- Cache UPC and ordered ISRC lists to improve compilation and variant matching.",
            "- Preserve manifest hashes for archive folders so moved folders can be recognized later.",
            "",
        ]
    )
    return "\n".join(lines)


def render_recoverable_identity_report(registry: dict[str, Any]) -> str:
    rows = registry.get("recoverable", [])
    lines = [
        "# Recoverable Identity Report",
        "",
        f"Generated: {registry['generated_at']}",
        "",
        f"Recoverable validator logs: `{len(rows)}`",
        "",
        "| Folder | Level | Best candidate | Reasons | Track count | Path |",
        "| --- | --- | --- | --- | ---: | --- |",
    ]
    for row in rows:
        best = row["recovery_candidates"][0]
        validation = row.get("validation", {})
        candidate = f"{best.get('artist')} - {best.get('title')} ({best.get('deezer_album_id')})"
        lines.append(
            f"| {_escape(row.get('folder'))} | {row.get('recovery_level')} | {_escape(candidate)} | "
            f"{_escape(', '.join(best.get('reasons', [])))} | {validation.get('track_count') or ''} | "
            f"`{_escape(row.get('path'))}` |"
        )
    return "\n".join(lines) + "\n"


def render_unrecoverable_identity_report(registry: dict[str, Any]) -> str:
    rows = registry.get("unrecoverable", [])
    lines = [
        "# Unrecoverable Identity Report",
        "",
        f"Generated: {registry['generated_at']}",
        "",
        f"Unrecoverable validator logs: `{len(rows)}`",
        "",
        "| Folder | Reason | Missing evidence | Track count | Path |",
        "| --- | --- | --- | ---: | --- |",
    ]
    for row in rows:
        validation = row.get("validation", {})
        missing = "album_id, metadata_identity, review_candidate"
        lines.append(
            f"| {_escape(row.get('folder'))} | {_escape(row.get('reason'))} | {missing} | "
            f"{validation.get('track_count') or ''} | `{_escape(row.get('path'))}` |"
        )
    return "\n".join(lines) + "\n"


def render_archive_strength_report(registry: dict[str, Any]) -> str:
    strength = registry["archive_strength"]
    categories = strength["categories"]
    lines = [
        "# Archive Strength Report",
        "",
        f"Generated: {registry['generated_at']}",
        "",
        f"Total releases: `{strength['total_releases']}`",
        f"Overall Archive Strength Score: `{strength['overall_archive_strength_score']:.1%}`",
        "",
        "| Category | Coverage |",
        "| --- | ---: |",
    ]
    for name, value in categories.items():
        lines.append(f"| {name.replace('_', ' ').title()} | {value:.1%} |")
    lines.extend(
        [
            "",
            "The score is informational only. Documentation and metadata coverage are future categories and currently score zero by design.",
            "",
        ]
    )
    return "\n".join(lines)


def write_archive_identity_recovery_reports(registry: dict[str, Any], reports_dir: Path) -> None:
    reports_dir.mkdir(parents=True, exist_ok=True)
    atomic_write_text(
        reports_dir / "archive_identity_recovery_report.md",
        render_archive_identity_recovery_report(registry),
    )
    atomic_write_text(reports_dir / "recoverable_identity_report.md", render_recoverable_identity_report(registry))
    atomic_write_text(
        reports_dir / "unrecoverable_identity_report.md",
        render_unrecoverable_identity_report(registry),
    )
    atomic_write_text(reports_dir / "archive_strength_report.md", render_archive_strength_report(registry))


def _ratio(count: int, total: int) -> float:
    if total == 0:
        return 0.0
    return round(count / total, 4)


def _escape(value: Any) -> str:
    return str(value or "").replace("|", "\\|").replace("\n", " ").strip()
