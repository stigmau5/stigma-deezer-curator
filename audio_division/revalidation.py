from __future__ import annotations

import json
import re
from collections import Counter
from datetime import datetime
from pathlib import Path
from typing import Any, Callable

from audio_division.archive_audit import broken_playlist_references, broken_sfv_references
from audio_division.archive_registry import album_entry, discover_album_folders
from audio_division.artifacts import AUDIO_SUFFIXES, AlbumArtifacts, detect_artifacts, is_disc_folder
from audio_division.physical_archive import archive_identity_for_row, build_identity_lookup
from audio_division.validation_truth import (
    merge_validation_evidence,
    validation_evidence_from_identity_release,
    validation_evidence_from_lifecycle_row,
    validation_evidence_from_validated_index,
)
from curator.atomic import atomic_write_text


HEALTH_OK = "OK"
HEALTH_WARNING = "Warning"
HEALTH_ERROR = "Error"

BREAKDOWN_LABELS = {
    "missing_artwork": "Missing artwork",
    "missing_nfo": "Missing NFO",
    "missing_sfv": "Missing SFV",
    "missing_playlist": "Missing playlist",
    "missing_validation": "Missing validation",
    "missing_audio": "Missing audio",
    "disc_layout_warnings": "Disc layout warnings",
}

CHECKS = (
    ("artwork", "Artwork", "artwork", "missing_artwork", "Artwork is missing."),
    ("nfo", "NFO", "nfo", "missing_nfo", "NFO is missing."),
    ("sfv", "SFV", "sfv", "missing_sfv", "SFV is missing."),
    ("playlist", "Playlist", "playlist", "missing_playlist", "Playlist is missing."),
)

DISC_NUMBER_RE = re.compile(r"^(?:cd|disc)[ _-]?(\d+)$", re.IGNORECASE)
ProgressCallback = Callable[[int, int, dict[str, Any]], None]


def revalidate_archive(
    archive_registry: dict[str, Any],
    archive_root: Path | None = None,
    *,
    identity_registry: dict[str, Any] | None = None,
    lifecycle_registry: dict[str, Any] | None = None,
    validated_index: dict[str, Any] | None = None,
    progress: ProgressCallback | None = None,
) -> dict[str, Any]:
    """Read-only revalidation pass across every album in the archive registry."""
    archive_root = archive_root or Path(str(archive_registry.get("archive_root") or ""))
    identity_registry = identity_registry if identity_registry is not None else load_default_json("identity_registry.json")
    lifecycle_registry = lifecycle_registry if lifecycle_registry is not None else load_default_json("lifecycle_registry.json")
    validated_index = validated_index if validated_index is not None else load_default_json("validated_albums.json")

    identity_lookup = build_identity_lookup(identity_registry or {})
    lifecycle_by_album_id = {
        str(row.get("album_id")): row
        for row in (lifecycle_registry or {}).get("albums", [])
        if isinstance(row, dict) and row.get("album_id")
    }
    rows = list(archive_registry.get("albums", []))
    total = len(rows)
    albums = []
    issues = []

    for index, row in enumerate(rows, start=1):
        if progress:
            progress(index, total, row)
        identity_release = archive_identity_for_row(row, identity_lookup)
        album_id = identity_release.get("discovery_identity", {}).get("deezer_album_id", "")
        validation_evidence = merge_validation_evidence(
            validation_evidence_from_validated_index(album_id, validated_index),
            validation_evidence_from_lifecycle_row(lifecycle_by_album_id.get(str(album_id))),
            validation_evidence_from_identity_release(identity_release),
        )
        result = revalidate_album(row, archive_root, validation_evidence=validation_evidence)
        albums.append(result)
        issues.extend(result["issues"])

    health_counts = Counter(album["health_category"] for album in albums)
    breakdown = Counter(issue["category"] for issue in issues)
    return {
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "archive_root": str(archive_root),
        "summary": {
            "albums_scanned": total,
            "healthy": health_counts.get(HEALTH_OK, 0),
            "warnings": health_counts.get(HEALTH_WARNING, 0),
            "errors": health_counts.get(HEALTH_ERROR, 0),
        },
        "breakdown": {key: breakdown.get(key, 0) for key in BREAKDOWN_LABELS},
        "issues": issues,
        "albums": albums,
    }


def revalidate_album(
    row: dict[str, Any],
    archive_root: Path | None = None,
    *,
    validation_evidence: dict[str, Any] | None = None,
    detected_artifacts: AlbumArtifacts | None = None,
) -> dict[str, Any]:
    path_text = str(row.get("archive_path") or "")
    path = Path(path_text) if path_text else Path("")
    detected = detected_artifacts or detect_artifacts(path if path_text else None)
    filesystem_available = bool(path_text and path.exists() and path.is_dir())
    checks = _artifact_checks(row, detected, filesystem_available, validation_evidence or {})
    issues = []
    if not filesystem_available:
        issues.append(_issue(row, "folder_unavailable", "Archive folder is unavailable.", "error"))
    issues.extend(_issues_from_checks(row, checks))

    if checks_by_id(checks)["audio_files"]["status"] == "Present":
        issues.extend(_disc_layout_issues(row, path))

    for broken in broken_playlist_references(path, detected):
        issues.append(_issue(row, "broken_playlist_reference", f"Broken playlist reference: {broken}", "error"))
    for broken in broken_sfv_references(path, detected):
        issues.append(_issue(row, "broken_sfv_reference", f"Broken SFV reference: {broken}", "error"))

    health_category = _health_category(issues)
    return {
        "artist": _artist_from_row(row),
        "album": _album_from_row(row),
        "path": str(path),
        "checks": checks,
        "health_category": health_category,
        "health_score": _health_score(checks, issues),
        "warnings": [_display_issue(issue) for issue in issues],
        "issues": issues,
    }


def revalidate_album_details(
    details: dict[str, Any],
    detected_artifacts: AlbumArtifacts | None = None,
) -> dict[str, Any]:
    """Single-album entrypoint used by Album Workspace integrity summaries."""
    archive_path = Path(str(details.get("archive_path") or "")) if details.get("archive_path") else None
    row = {
        "name": details.get("archive_folder") or details.get("title") or details.get("album") or (archive_path.name if archive_path else ""),
        "artist": details.get("artist") or "",
        "album": details.get("title") or details.get("album") or "",
        "archive_path": str(archive_path) if archive_path else "",
        "relative_path": details.get("relative_path") or "",
    }
    validation_evidence = _validation_evidence_from_details(details)
    return revalidate_album(row, validation_evidence=validation_evidence, detected_artifacts=detected_artifacts)


def render_archive_revalidation_report(report: dict[str, Any]) -> str:
    summary = report.get("summary", {})
    lines = [
        "# Archive Revalidation Report",
        "",
        f"Generated: `{report.get('generated_at', 'unknown')}`",
        f"Archive root: `{_escape(report.get('archive_root'))}`",
        "",
        "## Summary",
        "",
        f"- Albums scanned: `{summary.get('albums_scanned', 0)}`",
        f"- Healthy: `{summary.get('healthy', 0)}`",
        f"- Warnings: `{summary.get('warnings', 0)}`",
        f"- Errors: `{summary.get('errors', 0)}`",
        "",
        "## Breakdown",
        "",
        "| Check | Count |",
        "| --- | ---: |",
    ]
    breakdown = report.get("breakdown", {})
    for key, label in BREAKDOWN_LABELS.items():
        lines.append(f"| {label} | {breakdown.get(key, 0)} |")

    lines.extend(
        [
            "",
            "## Issues",
            "",
            "| Health | Check | Artist | Album | Path | Detail |",
            "| --- | --- | --- | --- | --- | --- |",
        ]
    )
    issues = report.get("issues", [])
    if not issues:
        lines.append("| OK |  |  |  |  |  |")
    for issue in issues:
        lines.append(
            f"| {_escape(issue.get('severity'))} | {_escape(issue.get('label'))} | "
            f"{_escape(issue.get('artist'))} | {_escape(issue.get('album'))} | "
            f"`{_escape(issue.get('path'))}` | {_escape(issue.get('reason'))} |"
        )
    return "\n".join(lines) + "\n"


def write_archive_revalidation_report(report: dict[str, Any], reports_dir: Path) -> None:
    reports_dir.mkdir(parents=True, exist_ok=True)
    atomic_write_text(reports_dir / "archive_revalidation_report.md", render_archive_revalidation_report(report))


def revalidate_archive_root(
    archive_root: Path,
    reports_dir: Path,
    *,
    progress: ProgressCallback | None = None,
) -> dict[str, Any]:
    albums = [album_entry(path, archive_root) for path in discover_album_folders(archive_root)]
    registry = {"archive_root": str(archive_root), "albums": albums}
    report = revalidate_archive(registry, archive_root, progress=progress)
    write_archive_revalidation_report(report, reports_dir)
    return report


def checks_by_id(checks: list[dict[str, str]]) -> dict[str, dict[str, str]]:
    return {check["id"]: check for check in checks}


def load_default_json(filename: str) -> dict[str, Any]:
    path = Path(__file__).resolve().parents[1] / "data" / filename
    if not path.exists():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}
    return data if isinstance(data, dict) else {}


def _artifact_checks(
    row: dict[str, Any],
    detected: AlbumArtifacts,
    filesystem_available: bool,
    validation_evidence: dict[str, Any],
) -> list[dict[str, str]]:
    checks = []
    for check_id, label, artifact, _, _ in CHECKS:
        present = filesystem_available and detected.present(artifact)
        checks.append(
            {
                "id": check_id,
                "label": label,
                "status": "Present" if present else "Missing",
                "source": "Filesystem" if present else "Filesystem",
                "path": _artifact_path(artifact, detected),
            }
        )

    validation = _validation_check(row, detected, filesystem_available, validation_evidence)
    audio_count = detected.count("audio") if filesystem_available else 0
    checks.extend(
        [
            validation,
            {
                "id": "audio_files",
                "label": "Audio Files",
                "status": "Present" if audio_count > 0 else "Missing",
                "source": "Filesystem" if filesystem_available else "none",
                "path": f"{audio_count} audio file(s)" if filesystem_available else "",
            },
        ]
    )
    return checks


def _validation_check(
    row: dict[str, Any],
    detected: AlbumArtifacts,
    filesystem_available: bool,
    validation_evidence: dict[str, Any],
) -> dict[str, str]:
    if filesystem_available and detected.present("validation"):
        return {
            "id": "validation",
            "label": "Validation",
            "status": "Present",
            "source": "Filesystem",
            "path": _artifact_path("validation", detected),
        }
    source = str(validation_evidence.get("validation_source") or "")
    if source:
        return {
            "id": "validation",
            "label": "Validation",
            "status": "Present",
            "source": _source_label(source),
            "path": str(validation_evidence.get("validation_log_path") or validation_evidence.get("folder") or ""),
        }
    return {
        "id": "validation",
        "label": "Validation",
        "status": "Missing",
        "source": "none",
        "path": "",
    }


def _validation_evidence_from_details(details: dict[str, Any]) -> dict[str, Any]:
    truth = details.get("album_truth") if isinstance(details.get("album_truth"), dict) else {}
    status = details.get("album_status") if isinstance(details.get("album_status"), dict) else {}
    sources = truth.get("sources") if isinstance(truth.get("sources"), dict) else {}
    status_sources = status.get("truth_sources") if isinstance(status.get("truth_sources"), dict) else {}
    paths = truth.get("paths") if isinstance(truth.get("paths"), dict) else {}
    status_paths = status.get("truth_paths") if isinstance(status.get("truth_paths"), dict) else {}
    items = truth.get("items") if isinstance(truth.get("items"), dict) else {}
    status_items = status.get("items") if isinstance(status.get("items"), dict) else {}
    if (items.get("validation") or status_items.get("validation")) != "Present":
        return {}
    source = str(sources.get("validation") or status_sources.get("validation") or "album_truth")
    return {
        "validation_source": source,
        "validation_log_path": str(paths.get("validation") or status_paths.get("validation") or ""),
    }


def _issues_from_checks(row: dict[str, Any], checks: list[dict[str, str]]) -> list[dict[str, Any]]:
    category_by_check = {
        "artwork": ("missing_artwork", "Artwork is missing."),
        "nfo": ("missing_nfo", "NFO is missing."),
        "sfv": ("missing_sfv", "SFV is missing."),
        "playlist": ("missing_playlist", "Playlist is missing."),
        "validation": ("missing_validation", "Validation evidence is missing."),
        "audio_files": ("missing_audio", "Audio Files is missing."),
    }
    issues = []
    for check in checks:
        if check["status"] != "Missing":
            continue
        category, reason = category_by_check.get(check["id"], (check["id"], f"{check['label']} is missing."))
        issues.append(_issue(row, category, reason, "warning"))
    return issues


def _disc_layout_issues(row: dict[str, Any], album_path: Path) -> list[dict[str, Any]]:
    try:
        disc_dirs = [path for path in album_path.iterdir() if path.is_dir() and is_disc_folder(path)]
    except OSError:
        disc_dirs = []
    if not disc_dirs:
        return []
    issues = []
    by_number: dict[int, list[Path]] = {}
    for folder in disc_dirs:
        match = DISC_NUMBER_RE.match(folder.name.strip())
        if not match:
            continue
        number = int(match.group(1))
        by_number.setdefault(number, []).append(folder)
        if not _direct_audio_count(folder):
            issues.append(_issue(row, "disc_layout_warnings", f"Disc folder has no audio files: {folder.name}", "warning"))

    for number, folders in sorted(by_number.items()):
        if len(folders) > 1:
            names = ", ".join(folder.name for folder in folders)
            issues.append(_issue(row, "disc_layout_warnings", f"Duplicate disc number {number}: {names}", "warning"))

    if by_number:
        expected = set(range(1, max(by_number) + 1))
        missing = sorted(expected - set(by_number))
        if missing:
            missing_text = ", ".join(str(number) for number in missing)
            issues.append(_issue(row, "disc_layout_warnings", f"Missing disc folder(s): {missing_text}", "warning"))
    return issues


def _direct_audio_count(path: Path) -> int:
    try:
        return sum(1 for item in path.iterdir() if item.is_file() and item.suffix.lower() in AUDIO_SUFFIXES)
    except OSError:
        return 0


def _artifact_path(artifact: str, detected: AlbumArtifacts) -> str:
    first = detected.first_file(artifact)
    return str(first) if first else ""


def _issue(row: dict[str, Any], category: str, reason: str, severity: str) -> dict[str, Any]:
    return {
        "category": category,
        "label": BREAKDOWN_LABELS.get(category, category.replace("_", " ").title()),
        "severity": HEALTH_ERROR if severity == "error" else HEALTH_WARNING,
        "artist": _artist_from_row(row),
        "album": _album_from_row(row),
        "path": str(row.get("archive_path") or ""),
        "reason": reason,
    }


def _display_issue(issue: dict[str, Any]) -> str:
    return str(issue.get("reason") or "")


def _health_category(issues: list[dict[str, Any]]) -> str:
    if any(issue.get("severity") == HEALTH_ERROR for issue in issues):
        return HEALTH_ERROR
    if issues:
        return HEALTH_WARNING
    return HEALTH_OK


def _health_score(checks: list[dict[str, str]], issues: list[dict[str, Any]]) -> int:
    present = sum(1 for check in checks if check.get("status") == "Present")
    score = round((present / len(checks)) * 100) if checks else 0
    error_penalty = sum(5 for issue in issues if issue.get("severity") == HEALTH_ERROR)
    warning_penalty = sum(2 for issue in issues if issue.get("category") == "disc_layout_warnings")
    return max(0, score - error_penalty - warning_penalty)


def _artist_from_row(row: dict[str, Any]) -> str:
    if row.get("artist"):
        return str(row.get("artist"))
    parts = Path(str(row.get("relative_path") or "")).parts
    for category in ("Albums", "EPs", "Singles", "Live"):
        if category in parts:
            index = parts.index(category)
            if index > 0:
                return parts[index - 1]
    return ""


def _album_from_row(row: dict[str, Any]) -> str:
    return str(row.get("album") or row.get("title") or row.get("name") or "")


def _source_label(source: str) -> str:
    labels = {
        "archive_marker": "Archive Marker",
        "validated_index": "Validated Index",
        "identity_registry": "Identity Registry",
        "lifecycle_registry": "Lifecycle Registry",
        "validator_log": "Validator Log",
        "album_truth": "AlbumTruth",
    }
    return labels.get(source, source or "none")


def _escape(value: Any) -> str:
    return str(value or "").replace("|", "\\|").replace("\n", " ").strip()
