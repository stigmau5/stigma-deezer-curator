from __future__ import annotations

from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

from audio_division.closed_loop_monitor import folder_identity_key
from audio_division.lifecycle_state import (
    STATE_DOWNLOADED,
    STATE_READY_FOR_PROCESSING,
)


ARCHIVED = "ARCHIVED"
READY_TO_ACQUIRE = "READY_TO_ACQUIRE"
ALREADY_DOWNLOADED = "ALREADY_DOWNLOADED"
READY_FOR_VALIDATION = "READY_FOR_VALIDATION"
READY_FOR_PROCESSING = "READY_FOR_PROCESSING"
ALREADY_PROCESSING = "ALREADY_PROCESSING"
NEEDS_METADATA = "NEEDS_METADATA"
IDENTITY_REVIEW = "IDENTITY_REVIEW"
UNKNOWN = "UNKNOWN"

CONFIDENCE_HIGH = "HIGH"
CONFIDENCE_MEDIUM = "MEDIUM"
CONFIDENCE_LOW = "LOW"


@dataclass(frozen=True)
class AcquisitionRecommendation:
    recommendation: str
    reason: str
    confidence: str
    next_action: str

    def to_dict(self) -> dict[str, str]:
        return asdict(self)


def recommend_acquisition(
    *,
    deezer_album_id: str = "",
    title: str = "",
    url: str = "",
    lifecycle: dict[str, Any] | None = None,
    archive_row: dict[str, Any] | None = None,
    closed_loop_row: dict[str, Any] | None = None,
    identity_release: dict[str, Any] | None = None,
    album_truth: dict[str, Any] | None = None,
    metadata_status: str = "",
    processing_queue_entry: dict[str, Any] | None = None,
) -> AcquisitionRecommendation:
    lifecycle = lifecycle or {}
    archive_row = archive_row or {}
    closed_loop_row = closed_loop_row or {}
    identity_release = identity_release or {}
    album_truth = album_truth or {}
    processing_queue_entry = processing_queue_entry or {}

    if _archive_documented(archive_row, album_truth):
        return AcquisitionRecommendation(
            ARCHIVED,
            "Archive album root exists with documentation.",
            CONFIDENCE_HIGH,
            "Open archive workspace.",
        )
    if archive_row.get("archive_path"):
        return AcquisitionRecommendation(
            ARCHIVED,
            "Archive album root exists; documentation may need review.",
            CONFIDENCE_MEDIUM,
            "Open archive workspace.",
        )

    if str(processing_queue_entry.get("state") or "").upper() == "PROCESSING":
        return AcquisitionRecommendation(
            ALREADY_PROCESSING,
            "Album is already present in the processing queue.",
            CONFIDENCE_HIGH,
            "Review processing queue.",
        )

    closed_loop_state = str(closed_loop_row.get("state") or "").upper()
    if closed_loop_state == STATE_READY_FOR_PROCESSING:
        return AcquisitionRecommendation(
            READY_FOR_PROCESSING,
            "Validation completed for the incoming album folder.",
            CONFIDENCE_HIGH,
            "Queue album for processing.",
        )

    if _validation_present(lifecycle, album_truth):
        return AcquisitionRecommendation(
            READY_FOR_PROCESSING,
            "Validation completed.",
            CONFIDENCE_MEDIUM,
            "Queue album for processing.",
        )

    if closed_loop_state == STATE_DOWNLOADED or closed_loop_row.get("folder"):
        return AcquisitionRecommendation(
            READY_FOR_VALIDATION,
            "Album folder detected in Incoming.",
            CONFIDENCE_HIGH,
            "Validate incoming album.",
        )

    lifecycle_state = str(lifecycle.get("highest_state") or "").upper()
    states = lifecycle.get("states") if isinstance(lifecycle.get("states"), dict) else {}
    if states.get("shipped") or lifecycle_state in {"SHIPPED", "DOWNLOADED"}:
        return AcquisitionRecommendation(
            ALREADY_DOWNLOADED,
            "Lifecycle state indicates the album was already downloaded.",
            CONFIDENCE_MEDIUM,
            "Locate incoming folder or validate manually.",
        )

    if _needs_identity_review(identity_release, album_truth):
        return AcquisitionRecommendation(
            IDENTITY_REVIEW,
            "Identity confidence is too low for automatic acquisition decisions.",
            CONFIDENCE_LOW,
            "Review identity evidence.",
        )

    if metadata_status and metadata_status != "CACHED" and lifecycle:
        return AcquisitionRecommendation(
            NEEDS_METADATA,
            f"Metadata status is {metadata_status}.",
            CONFIDENCE_MEDIUM,
            "Refresh metadata.",
        )

    if deezer_album_id or url:
        return AcquisitionRecommendation(
            READY_TO_ACQUIRE,
            "Album exists on Deezer but is not present in archive.",
            CONFIDENCE_MEDIUM,
            "Select release for acquisition.",
        )

    return AcquisitionRecommendation(
        UNKNOWN,
        "No acquisition evidence is available.",
        CONFIDENCE_LOW,
        "Review source data.",
    )


def find_closed_loop_row(
    rows: list[dict[str, Any]] | tuple[dict[str, Any], ...],
    *,
    deezer_album_id: str = "",
    artist: str = "",
    title: str = "",
    identity_release: dict[str, Any] | None = None,
) -> dict[str, Any]:
    keys = _release_identity_keys(artist=artist, title=title, identity_release=identity_release)
    album_id = str(deezer_album_id or "")
    for row in rows:
        if not isinstance(row, dict):
            continue
        if album_id and str(row.get("album_id") or "") == album_id:
            return row
        if _row_identity_keys(row) & keys:
            return row
    return {}


def find_processing_queue_entry(
    queue: dict[str, Any] | None,
    *,
    deezer_album_id: str = "",
    archive_path: str = "",
    artist: str = "",
    title: str = "",
    identity_release: dict[str, Any] | None = None,
) -> dict[str, Any]:
    queue = queue or {}
    entries = queue.get("albums", {})
    if not isinstance(entries, dict):
        return {}
    keys = _release_identity_keys(artist=artist, title=title, identity_release=identity_release)
    path_key = str(archive_path or "")
    album_id = str(deezer_album_id or "")
    for key, entry in entries.items():
        if not isinstance(entry, dict):
            continue
        if album_id and str(entry.get("album_id") or "") == album_id:
            return entry
        if path_key and (str(key) == path_key or str(entry.get("archive_path") or "") == path_key):
            return entry
        entry_key = folder_identity_key(
            entry.get("archive_path")
            or " ".join(part for part in (entry.get("artist"), entry.get("album"), entry.get("title")) if part)
        )
        if entry_key in keys:
            return entry
    return {}


def _archive_documented(archive_row: dict[str, Any], album_truth: dict[str, Any]) -> bool:
    if not archive_row.get("archive_path"):
        return False
    artifacts = archive_row.get("artifacts") if isinstance(archive_row.get("artifacts"), dict) else {}
    if artifacts.get("nfo") and artifacts.get("sfv") and artifacts.get("validation_log"):
        return True
    items = album_truth.get("items") if isinstance(album_truth.get("items"), dict) else {}
    return items.get("nfo") == "Present" and items.get("sfv") == "Present" and items.get("validation") == "Present"


def _validation_present(lifecycle: dict[str, Any], album_truth: dict[str, Any]) -> bool:
    states = lifecycle.get("states") if isinstance(lifecycle.get("states"), dict) else {}
    evidence = lifecycle.get("validation_evidence") if isinstance(lifecycle.get("validation_evidence"), dict) else {}
    if states.get("validated") or evidence.get("available"):
        return True
    lifecycle_state = str(lifecycle.get("highest_state") or "").upper()
    if lifecycle_state in {"VALIDATED", "READY_FOR_PROCESSING"}:
        return True
    return bool(album_truth.get("validation_present") or album_truth.get("items", {}).get("validation") == "Present")


def _needs_identity_review(identity_release: dict[str, Any], album_truth: dict[str, Any]) -> bool:
    confidence = str(
        identity_release.get("identity_confidence")
        or album_truth.get("identity_confidence")
        or "UNKNOWN"
    ).upper()
    maintenance = album_truth.get("maintenance") if isinstance(album_truth.get("maintenance"), dict) else {}
    if maintenance.get("category") == "needs_review":
        return True
    return bool(identity_release) and confidence not in {"HIGH", "MEDIUM"}


def _release_identity_keys(
    *,
    artist: str = "",
    title: str = "",
    identity_release: dict[str, Any] | None = None,
) -> set[str]:
    identity_release = identity_release or {}
    archive_identity = identity_release.get("archive_identity") if isinstance(identity_release.get("archive_identity"), dict) else {}
    discovery = identity_release.get("discovery_identity") if isinstance(identity_release.get("discovery_identity"), dict) else {}
    values = [
        archive_identity.get("folder"),
        " ".join(part for part in (artist, title) if part),
        " ".join(part for part in (discovery.get("artist"), discovery.get("title")) if part),
    ]
    return {folder_identity_key(value) for value in values if folder_identity_key(value)}


def _row_identity_keys(row: dict[str, Any]) -> set[str]:
    values = [
        row.get("identity_key"),
        row.get("folder"),
        Path(str(row.get("archive_path") or "")).name,
        " ".join(part for part in (row.get("artist"), row.get("album"), row.get("title")) if part),
    ]
    return {folder_identity_key(value) for value in values if folder_identity_key(value)}
