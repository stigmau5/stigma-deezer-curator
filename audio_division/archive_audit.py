from __future__ import annotations

import json
import re
from collections import Counter
from datetime import datetime
from pathlib import Path
from typing import Any

from audio_division.album_truth import album_truth
from audio_division.archive_registry import count_audio_tracks, is_album_root
from audio_division.artifacts import detect_album_artifacts
from audio_division.physical_archive import archive_identity_for_row, build_identity_lookup
from audio_division.validation_truth import (
    merge_validation_evidence,
    validation_evidence_from_identity_release,
    validation_evidence_from_lifecycle_row,
    validation_evidence_from_validated_index,
)
from curator.atomic import atomic_write_text


ISSUE_LABELS = {
    "missing_artwork": "Missing artwork",
    "missing_nfo": "Missing NFO",
    "missing_sfv": "Missing SFV",
    "missing_playlist": "Missing playlist",
    "missing_validation": "Missing validation",
    "missing_audio": "Missing audio",
    "broken_playlist_reference": "Broken playlist references",
    "broken_sfv_reference": "Broken SFV references",
    "unexpected_layout": "Unexpected layouts",
}

WARNING_ISSUES = {
    "missing_artwork",
    "missing_nfo",
    "missing_sfv",
    "missing_playlist",
    "missing_validation",
    "missing_audio",
    "unexpected_layout",
}
ERROR_ISSUES = {"broken_playlist_reference", "broken_sfv_reference"}
AUDIO_SUFFIXES = {".flac", ".mp3", ".m4a", ".ogg", ".opus", ".wav", ".aiff"}
CRC_PATTERN = re.compile(r"^[0-9a-fA-F]{8}$")


def audit_archive(
    archive_registry: dict[str, Any],
    archive_root: Path | None = None,
    *,
    identity_registry: dict[str, Any] | None = None,
    lifecycle_registry: dict[str, Any] | None = None,
    validated_index: dict[str, Any] | None = None,
) -> dict[str, Any]:
    archive_root = archive_root or Path(str(archive_registry.get("archive_root") or ""))
    identity_registry = identity_registry if identity_registry is not None else load_default_json("identity_registry.json")
    lifecycle_registry = lifecycle_registry if lifecycle_registry is not None else load_default_json("lifecycle_registry.json")
    validated_index = validated_index if validated_index is not None else load_default_json("validated_albums.json")
    identity_lookup = build_identity_lookup(identity_registry or {})
    lifecycle_by_album_id = {
        str(row.get("album_id")): row
        for row in (lifecycle_registry or {}).get("albums", [])
        if row.get("album_id")
    }
    albums = []
    issues = []
    for row in archive_registry.get("albums", []):
        identity_release = archive_identity_for_row(row, identity_lookup)
        album_id = identity_release.get("discovery_identity", {}).get("deezer_album_id", "")
        validation_evidence = merge_validation_evidence(
            validation_evidence_from_validated_index(album_id, validated_index),
            validation_evidence_from_lifecycle_row(lifecycle_by_album_id.get(str(album_id))),
            validation_evidence_from_identity_release(identity_release),
        )
        album = audit_album(row, archive_root, validation_evidence=validation_evidence)
        albums.append(album)
        issues.extend(album["issues"])

    issue_counts = Counter(issue["category"] for issue in issues)
    validation_source_counts = Counter(album.get("validation_source") or "missing" for album in albums)
    warning_count = sum(1 for issue in issues if issue["severity"] == "warning")
    error_count = sum(1 for issue in issues if issue["severity"] == "error")
    healthy_count = sum(1 for album in albums if not album["issues"])
    return {
        "generated_at": datetime.now().isoformat(timespec="seconds"),
        "archive_root": str(archive_root),
        "summary": {
            "albums_scanned": len(albums),
            "healthy": healthy_count,
            "warnings": warning_count,
            "errors": error_count,
        },
        "issue_counts": dict(issue_counts),
        "validation_source_counts": dict(validation_source_counts),
        "issues": issues,
        "albums": albums,
    }


def audit_album(row: dict[str, Any], archive_root: Path, validation_evidence: dict[str, Any] | None = None) -> dict[str, Any]:
    path = Path(str(row.get("archive_path") or ""))
    artifacts = detect_album_artifacts(path)
    truth = album_truth(
        artist=artist_from_row(row),
        album=album_from_row(row),
        archive_path=path,
        registry_artifacts=artifacts,
        validator_evidence=validation_evidence or {},
    )
    track_count = count_audio_tracks(path)
    issues: list[dict[str, Any]] = []

    missing_checks = {
        "artwork": ("missing_artwork", "Artwork is missing."),
        "nfo": ("missing_nfo", "NFO is missing."),
        "sfv": ("missing_sfv", "SFV is missing."),
        "playlist": ("missing_playlist", "Playlist is missing."),
        "validation": ("missing_validation", "Validation evidence is missing."),
    }
    for artifact, (category, reason) in missing_checks.items():
        if artifact == "validation":
            present = truth.validation.present
        else:
            present = bool(artifacts.get(artifact))
        if not present:
            if artifact == "validation" and truth.validation.reason:
                reason = truth.validation.reason
            issues.append(issue(row, category, reason, "warning"))
    if track_count == 0:
        issues.append(issue(row, "missing_audio", "No audio files were found in the album root or disc folders.", "warning"))

    issues.extend(unexpected_layout_issues(row, path, archive_root))
    for broken in broken_playlist_references(path):
        issues.append(issue(row, "broken_playlist_reference", f"Playlist reference does not exist: {broken}", "error"))
    for broken in broken_sfv_references(path):
        issues.append(issue(row, "broken_sfv_reference", f"SFV reference does not exist: {broken}", "error"))

    return {
        "artist": artist_from_row(row),
        "album": album_from_row(row),
        "path": str(path),
        "track_count": track_count,
        "health": truth.health,
        "validation_status": truth.validation_status,
        "validation_source": truth.validation_source,
        "validation_confidence": truth.validation_confidence,
        "validation_reason": truth.validation_reason,
        "issues": issues,
    }


def unexpected_layout_issues(row: dict[str, Any], album_path: Path, archive_root: Path) -> list[dict[str, Any]]:
    issues = []
    if album_path.exists() and album_path.is_dir() and not is_album_root(album_path, archive_root):
        issues.append(issue(row, "unexpected_layout", "Path is not a formal archive album root.", "warning"))
    try:
        child_dirs = [path for path in album_path.iterdir() if path.is_dir()]
    except OSError:
        child_dirs = []
    for folder in child_dirs:
        if count_direct_audio(folder) and not is_expected_disc_folder(folder):
            issues.append(issue(row, "unexpected_layout", f"Audio directory is not a recognized disc folder: {folder.name}", "warning"))
    return issues


def broken_playlist_references(album_path: Path) -> list[str]:
    broken = []
    for playlist in artifact_files(album_path, {".m3u", ".m3u8"}):
        for reference in playlist_references(playlist):
            if not resolve_reference(playlist.parent, reference).exists():
                broken.append(f"{playlist.name}: {reference}")
    return broken


def broken_sfv_references(album_path: Path) -> list[str]:
    broken = []
    for sfv in artifact_files(album_path, {".sfv"}):
        for reference in sfv_references(sfv):
            if not resolve_reference(sfv.parent, reference).exists():
                broken.append(f"{sfv.name}: {reference}")
    return broken


def artifact_files(album_path: Path, suffixes: set[str]) -> list[Path]:
    try:
        return sorted(
            (path for path in album_path.iterdir() if path.is_file() and path.suffix.lower() in suffixes),
            key=lambda path: path.name.lower(),
        )
    except OSError:
        return []


def playlist_references(playlist: Path) -> list[str]:
    references = []
    for line in safe_read_lines(playlist):
        text = line.strip()
        if not text or text.startswith("#"):
            continue
        references.append(text)
    return references


def sfv_references(sfv: Path) -> list[str]:
    references = []
    for line in safe_read_lines(sfv):
        text = line.strip()
        if not text or text.startswith(";"):
            continue
        parts = text.rsplit(maxsplit=1)
        if len(parts) == 2 and CRC_PATTERN.match(parts[1]):
            references.append(parts[0])
    return references


def resolve_reference(base: Path, reference: str) -> Path:
    path = Path(reference)
    if path.is_absolute():
        return path
    return base / path


def safe_read_lines(path: Path) -> list[str]:
    try:
        return path.read_text(encoding="utf-8", errors="replace").splitlines()
    except OSError:
        return []


def count_direct_audio(path: Path) -> int:
    try:
        return sum(1 for item in path.iterdir() if item.is_file() and item.suffix.lower() in AUDIO_SUFFIXES)
    except OSError:
        return 0


def is_expected_disc_folder(path: Path) -> bool:
    return bool(re.match(r"^(cd|disc)[ _-]?\d+$", path.name.strip(), re.IGNORECASE))


def issue(row: dict[str, Any], category: str, reason: str, severity: str) -> dict[str, Any]:
    return {
        "category": category,
        "label": ISSUE_LABELS.get(category, category),
        "severity": severity,
        "artist": artist_from_row(row),
        "album": album_from_row(row),
        "path": str(row.get("archive_path") or ""),
        "reason": reason,
    }


def artist_from_row(row: dict[str, Any]) -> str:
    parts = Path(str(row.get("relative_path") or "")).parts
    for category in ("Albums", "EPs", "Singles", "Live"):
        if category in parts:
            index = parts.index(category)
            if index > 0:
                return parts[index - 1]
    return str(row.get("artist") or "")


def album_from_row(row: dict[str, Any]) -> str:
    return str(row.get("name") or row.get("album") or "")


def render_archive_audit(report: dict[str, Any]) -> str:
    summary = report.get("summary", {})
    lines = [
        "# Archive Audit",
        "",
        f"Generated: `{report.get('generated_at', 'unknown')}`",
        f"Archive root: `{escape(report.get('archive_root'))}`",
        "",
        "## Summary",
        "",
        f"- Albums scanned: `{summary.get('albums_scanned', 0)}`",
        f"- Healthy: `{summary.get('healthy', 0)}`",
        f"- Warnings: `{summary.get('warnings', 0)}`",
        f"- Errors: `{summary.get('errors', 0)}`",
        "",
        "## Categories",
        "",
        "| Category | Count |",
        "| --- | ---: |",
    ]
    counts = report.get("issue_counts", {})
    for category, label in ISSUE_LABELS.items():
        lines.append(f"| {label} | {counts.get(category, 0)} |")
    lines.extend(["", "## Validation Sources", "", "| Source | Albums |", "| --- | ---: |"])
    validation_sources = report.get("validation_source_counts", {})
    if validation_sources:
        for source, count in sorted(validation_sources.items()):
            lines.append(f"| {escape(source)} | {count} |")
    else:
        lines.append("| none | 0 |")
    lines.extend(["", "## Issues", "", "| Severity | Category | Artist | Album | Path | Reason |", "| --- | --- | --- | --- | --- | --- |"])
    issues = report.get("issues", [])
    if not issues:
        lines.append("| none |  |  |  |  |  |")
    for row in issues:
        lines.append(
            f"| {escape(row.get('severity'))} | {escape(row.get('label'))} | {escape(row.get('artist'))} | "
            f"{escape(row.get('album'))} | `{escape(row.get('path'))}` | {escape(row.get('reason'))} |"
        )
    return "\n".join(lines) + "\n"


def write_archive_audit(report: dict[str, Any], reports_dir: Path) -> None:
    reports_dir.mkdir(parents=True, exist_ok=True)
    atomic_write_text(reports_dir / "archive_audit.md", render_archive_audit(report))


def load_archive_registry(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}
    return data if isinstance(data, dict) else {}


def load_default_json(filename: str) -> dict[str, Any]:
    path = Path(__file__).resolve().parents[1] / "data" / filename
    if not path.exists():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}
    return data if isinstance(data, dict) else {}


def escape(value: Any) -> str:
    return str(value or "").replace("|", "\\|").replace("\n", " ").strip()
