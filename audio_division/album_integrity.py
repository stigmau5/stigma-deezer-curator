from __future__ import annotations

from pathlib import Path
from typing import Any

from audio_division.archive_audit import broken_playlist_references, broken_sfv_references
from audio_division.archive_registry import AUDIO_SUFFIXES, count_audio_tracks
from audio_division.artifacts import detect_album_artifacts


INTEGRITY_CHECKS = (
    ("artwork", "Artwork"),
    ("nfo", "NFO"),
    ("sfv", "SFV"),
    ("playlist", "Playlist"),
    ("validation", "Validation"),
    ("audio_files", "Audio Files"),
)


def album_integrity(details: dict[str, Any]) -> dict[str, Any]:
    archive_path = Path(str(details.get("archive_path") or "")) if details.get("archive_path") else None
    filesystem_available = bool(archive_path and archive_path.exists() and archive_path.is_dir())
    filesystem = detect_album_artifacts(archive_path) if filesystem_available and archive_path else {}
    truth = details.get("album_truth", {})
    status = details.get("album_status", {})
    checks = [
        artifact_check("artwork", filesystem, truth, status, filesystem_available),
        artifact_check("nfo", filesystem, truth, status, filesystem_available),
        artifact_check("sfv", filesystem, truth, status, filesystem_available),
        artifact_check("playlist", filesystem, truth, status, filesystem_available),
        artifact_check("validation", filesystem, truth, status, filesystem_available, artifact_key="validation_log"),
        audio_check(archive_path, filesystem_available),
    ]
    warnings = integrity_warnings(checks, archive_path, filesystem_available)
    return {
        "checks": checks,
        "health_score": health_score(checks, warnings),
        "warnings": warnings,
    }


def artifact_check(
    field: str,
    filesystem: dict[str, Any],
    truth: dict[str, Any],
    status: dict[str, Any],
    filesystem_available: bool,
    *,
    artifact_key: str | None = None,
) -> dict[str, str]:
    artifact_key = artifact_key or field
    if filesystem_available:
        if field == "validation" and not filesystem.get(artifact_key):
            item_status = truth_item_status(field, truth, status)
            if item_status == "Present":
                source = truth_item_source(field, truth, status)
                return {
                    "id": field,
                    "label": label_for(field),
                    "status": item_status,
                    "source": source_label(source),
                    "path": truth_item_path(field, truth, status),
                }
        present = bool(filesystem.get(artifact_key))
        return {
            "id": field,
            "label": label_for(field),
            "status": "Present" if present else "Missing",
            "source": "Filesystem",
            "path": filesystem_path(field, filesystem),
        }
    item_status = truth_item_status(field, truth, status)
    source = truth_item_source(field, truth, status)
    return {
        "id": field,
        "label": label_for(field),
        "status": item_status,
        "source": source_label(source),
        "path": truth_item_path(field, truth, status),
    }


def audio_check(archive_path: Path | None, filesystem_available: bool) -> dict[str, str]:
    if not filesystem_available or not archive_path:
        return {"id": "audio_files", "label": "Audio Files", "status": "Unknown", "source": "none", "path": ""}
    count = count_audio_tracks(archive_path)
    return {
        "id": "audio_files",
        "label": "Audio Files",
        "status": "Present" if count > 0 else "Missing",
        "source": "Filesystem",
        "path": f"{count} audio file(s)",
    }


def integrity_warnings(checks: list[dict[str, str]], archive_path: Path | None, filesystem_available: bool) -> list[str]:
    warnings = []
    if not filesystem_available:
        warnings.append("Archive folder is unavailable; integrity is derived from AlbumTruth where possible.")
    for check in checks:
        if check["status"] == "Missing":
            warnings.append(f"{check['label']} is missing.")
        elif check["status"] == "Unknown":
            warnings.append(f"{check['label']} is unknown.")
    if filesystem_available and archive_path:
        for broken in broken_playlist_references(archive_path):
            warnings.append(f"Broken playlist reference: {broken}")
        for broken in broken_sfv_references(archive_path):
            warnings.append(f"Broken SFV reference: {broken}")
    return warnings


def health_score(checks: list[dict[str, str]], warnings: list[str]) -> int:
    known = [check for check in checks if check["status"] != "Unknown"]
    if not known:
        return 0
    present = sum(1 for check in known if check["status"] == "Present")
    score = round((present / len(known)) * 100)
    broken_penalty = sum(3 for warning in warnings if warning.startswith("Broken "))
    return max(0, score - broken_penalty)


def filesystem_path(field: str, filesystem: dict[str, Any]) -> str:
    if field == "artwork":
        return str(filesystem.get("artwork_path") or "")
    return ""


def truth_item_status(field: str, truth: dict[str, Any], status: dict[str, Any]) -> str:
    items = truth.get("items") if isinstance(truth.get("items"), dict) else {}
    status_items = status.get("items") if isinstance(status.get("items"), dict) else {}
    value = items.get(field) or status_items.get(field) or "Unknown"
    return value if value in {"Present", "Missing", "Unknown"} else "Unknown"


def truth_item_source(field: str, truth: dict[str, Any], status: dict[str, Any]) -> str:
    sources = truth.get("sources") if isinstance(truth.get("sources"), dict) else {}
    status_sources = status.get("truth_sources") if isinstance(status.get("truth_sources"), dict) else {}
    return str(sources.get(field) or status_sources.get(field) or "none")


def truth_item_path(field: str, truth: dict[str, Any], status: dict[str, Any]) -> str:
    paths = truth.get("paths") if isinstance(truth.get("paths"), dict) else {}
    status_paths = status.get("truth_paths") if isinstance(status.get("truth_paths"), dict) else {}
    return str(paths.get(field) or status_paths.get(field) or "")


def source_label(source: str) -> str:
    labels = {
        "filesystem": "Filesystem",
        "archive_marker": "Archive Marker",
        "validated_index": "Validated Index",
        "identity_registry": "Identity Registry",
        "lifecycle_registry": "Lifecycle Registry",
        "validator_log": "Validator Log",
        "missing": "Missing",
        "validator_evidence": "Validator Evidence",
        "archive_registry": "Archive Registry",
        "metadata_cache": "Metadata Cache",
        "none": "none",
    }
    return labels.get(source, source or "none")


def label_for(field: str) -> str:
    for key, label in INTEGRITY_CHECKS:
        if key == field:
            return label
    return field.replace("_", " ").title()
