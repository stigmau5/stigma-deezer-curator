from __future__ import annotations

from collections import Counter
from datetime import datetime
from pathlib import Path
from typing import Any

from curator.atomic import atomic_write_text

READINESS_STATES = (
    "ARCHIVE_READY",
    "NEEDS_VALIDATION",
    "NEEDS_DOCUMENTATION",
    "NEEDS_REVIEW",
    "UNKNOWN",
)


def evaluate_album_readiness(album: dict[str, Any]) -> dict[str, Any]:
    reasons: list[str] = []
    status = album.get("album_status", {})
    items = status.get("items", {})
    identity_confidence = album.get("identity_confidence", "UNKNOWN")
    path_confidence = album.get("archive_path_confidence", "UNKNOWN")

    if not album.get("archive_path"):
        reasons.append("archive_path_missing")
    if path_confidence == "UNKNOWN":
        reasons.append("archive_path_unknown")
    if identity_confidence == "UNKNOWN":
        reasons.append("identity_unknown")

    if reasons:
        return _readiness("UNKNOWN", "Insufficient archive path or identity evidence.", "LOW", reasons)

    if identity_confidence not in ("HIGH", "MEDIUM") or path_confidence not in ("HIGH", "MEDIUM"):
        return _readiness("NEEDS_REVIEW", "Identity or archive path evidence needs review.", "MEDIUM", ["uncertain_identity_or_path"])

    if items.get("validation") != "Present":
        return _readiness("NEEDS_VALIDATION", "Validation evidence is missing.", "HIGH", ["validation_missing"])

    documentation_missing = [name for name in ("nfo", "sfv") if items.get(name) != "Present"]
    if documentation_missing:
        return _readiness(
            "NEEDS_DOCUMENTATION",
            "Validation is present but archive documentation is incomplete.",
            "HIGH",
            [f"{name}_missing" for name in documentation_missing],
        )

    if items.get("artwork") != "Present":
        return _readiness("NEEDS_REVIEW", "Artwork evidence is incomplete.", "MEDIUM", ["artwork_missing"])

    return _readiness("ARCHIVE_READY", "Validation, documentation, archive path, identity, and artwork are present.", "HIGH", ["ready"])


def annotate_library_readiness(library: dict[str, Any]) -> dict[str, Any]:
    for album in library.get("albums", []):
        album["archive_readiness"] = evaluate_album_readiness(album)
    library["archive_readiness_summary"] = readiness_summary(library.get("albums", []))
    return library


def readiness_summary(albums: list[dict[str, Any]]) -> dict[str, Any]:
    counts = Counter((album.get("archive_readiness") or evaluate_album_readiness(album))["state"] for album in albums)
    total = len(albums)
    return {
        "total_albums": total,
        "counts": {state: counts.get(state, 0) for state in READINESS_STATES},
        "percentages": {state: _ratio(counts.get(state, 0), total) for state in READINESS_STATES},
        "coverage_percent": _ratio(counts.get("ARCHIVE_READY", 0), total),
    }


def render_archive_readiness_report(library: dict[str, Any], *, generated_at: str | None = None) -> str:
    generated_at = generated_at or datetime.now().isoformat(timespec="seconds")
    albums = library.get("albums", [])
    summary = library.get("archive_readiness_summary") or readiness_summary(albums)
    lines = [
        "# Archive Readiness Report",
        "",
        f"Generated: {generated_at}",
        "",
        "Archive readiness is derived from existing Audio Division evidence. No archive files are modified.",
        "",
        "## Summary",
        "",
        f"- Total albums: `{summary['total_albums']}`",
        f"- Archive-ready coverage: `{summary['coverage_percent']:.1%}`",
        "",
        "| State | Count | Percent |",
        "| --- | ---: | ---: |",
    ]
    for state in READINESS_STATES:
        lines.append(f"| {state} | {summary['counts'].get(state, 0)} | {summary['percentages'].get(state, 0):.1%} |")

    lines.extend(
        [
            "",
            "## Examples",
            "",
            "| State | Album ID | Artist | Album | Confidence | Reason |",
            "| --- | --- | --- | --- | --- | --- |",
        ]
    )
    for album in albums[:500]:
        readiness = album.get("archive_readiness") or evaluate_album_readiness(album)
        lines.append(
            f"| {readiness['state']} | `{_escape(album.get('album_id'))}` | {_escape(album.get('artist'))} | "
            f"{_escape(album.get('title'))} | {readiness['confidence']} | {_escape(readiness['reason'])} |"
        )
    return "\n".join(lines) + "\n"


def write_archive_readiness_report(library: dict[str, Any], reports_dir: Path) -> None:
    reports_dir.mkdir(parents=True, exist_ok=True)
    atomic_write_text(reports_dir / "archive_readiness_report.md", render_archive_readiness_report(library))


def _readiness(state: str, reason: str, confidence: str, explanation: list[str]) -> dict[str, Any]:
    return {
        "state": state,
        "reason": reason,
        "confidence": confidence,
        "explanation": explanation,
    }


def _ratio(count: int, total: int) -> float:
    if total == 0:
        return 0.0
    return round(count / total, 4)


def _escape(value: Any) -> str:
    return str(value or "").replace("|", "\\|").replace("\n", " ").strip()
