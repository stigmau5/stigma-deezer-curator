from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any


STATE_DOWNLOADED = "Downloaded"
STATE_VALIDATED = "Validated"
STATE_ARCHIVED = "Archived"
STATE_ARCHIVE_READY = "Archive Ready"
STATE_NEEDS_METADATA = "Needs Metadata"
STATE_NEEDS_DOCUMENTATION = "Needs Documentation"
STATE_NEEDS_REVIEW = "Needs Review"
STATE_UNKNOWN = "Unknown"

ACTION_VALIDATE = "Validate"
ACTION_ARCHIVE = "Archive"
ACTION_REFRESH = "Refresh"
ACTION_HEALTHY = "Healthy"
ACTION_REFRESH_METADATA = "Refresh Metadata"
ACTION_GENERATE_DOCUMENTATION = "Generate Documentation"
ACTION_REVIEW = "Review"

CONFIDENCE_HIGH = "HIGH"
CONFIDENCE_MEDIUM = "MEDIUM"
CONFIDENCE_LOW = "LOW"


@dataclass(frozen=True)
class PipelineRecommendation:
    state: str
    recommended_action: str
    reason: str
    confidence: str

    def to_dict(self) -> dict[str, str]:
        return asdict(self)


def recommend_next_action(release: Any) -> PipelineRecommendation:
    row = _as_mapping(release)
    truth = _dict(row.get("album_truth"))
    status = _status_text(row)
    lifecycle = _upper(row.get("lifecycle_state") or row.get("highest_state"))
    archive_status = _upper(row.get("archive_status"))
    archive_readiness = _dict(row.get("archive_readiness"))
    readiness = _upper(truth.get("readiness") or archive_readiness.get("state"))
    maintenance = _dict(truth.get("maintenance"))
    processing_state = _upper(truth.get("processing_state") or row.get("processing_state"))
    items = _dict(truth.get("items") or row.get("album_status", {}).get("items"))
    has_archive = bool(row.get("archive_path")) or archive_status == "ARCHIVED"

    if readiness == "ARCHIVE READY":
        return PipelineRecommendation(
            STATE_ARCHIVE_READY,
            ACTION_HEALTHY,
            "AlbumTruth marks the release archive-ready.",
            CONFIDENCE_HIGH,
        )

    if has_archive or status in {"ALREADY ARCHIVED", "ARCHIVED"} or lifecycle == "ARCHIVED":
        return PipelineRecommendation(
            STATE_ARCHIVED,
            ACTION_REFRESH,
            "Archive evidence exists for the release.",
            CONFIDENCE_HIGH if has_archive else CONFIDENCE_MEDIUM,
        )

    if maintenance.get("category") == "needs_metadata" or _upper(row.get("metadata_status")) == "AVAILABLE NOT CACHED":
        return PipelineRecommendation(
            STATE_NEEDS_METADATA,
            ACTION_REFRESH_METADATA,
            "Metadata is available but not cached.",
            CONFIDENCE_MEDIUM,
        )

    if maintenance.get("category") == "needs_documentation" or _missing_documentation(items):
        return PipelineRecommendation(
            STATE_NEEDS_DOCUMENTATION,
            ACTION_GENERATE_DOCUMENTATION,
            "Documentation artifacts are missing.",
            CONFIDENCE_MEDIUM,
        )

    if lifecycle in {"VALIDATED", "READY FOR PROCESSING"} or status in {"ALREADY VALIDATED", "READY TO PROCESS"}:
        return PipelineRecommendation(
            STATE_VALIDATED,
            ACTION_ARCHIVE,
            "Validation evidence exists and the release is ready for archive processing.",
            CONFIDENCE_HIGH,
        )

    if processing_state == "DOWNLOADED" or status in {"DOWNLOADED", "READY TO VALIDATE"} or row.get("folder"):
        return PipelineRecommendation(
            STATE_DOWNLOADED,
            ACTION_VALIDATE,
            "Downloaded release evidence exists.",
            CONFIDENCE_HIGH if row.get("folder") else CONFIDENCE_MEDIUM,
        )

    if maintenance.get("category") == "needs_review" or _upper(row.get("identity_confidence")) in {"LOW", "UNKNOWN"}:
        return PipelineRecommendation(
            STATE_NEEDS_REVIEW,
            ACTION_REVIEW,
            "Identity or AlbumTruth evidence needs review before workflow can continue.",
            CONFIDENCE_LOW,
        )

    return PipelineRecommendation(
        STATE_UNKNOWN,
        ACTION_REVIEW,
        "No actionable workflow evidence is available.",
        CONFIDENCE_LOW,
    )


def recommend_for_releases(releases: list[Any] | tuple[Any, ...]) -> list[dict[str, str]]:
    return [recommend_next_action(release).to_dict() for release in releases]


def _as_mapping(value: Any) -> dict[str, Any]:
    if isinstance(value, dict):
        return value
    if hasattr(value, "to_row"):
        row = value.to_row()
        if isinstance(row, dict):
            return row
    return {
        name: getattr(value, name)
        for name in dir(value)
        if not name.startswith("_") and not callable(getattr(value, name))
    }


def _dict(value: Any) -> dict[str, Any]:
    return value if isinstance(value, dict) else {}


def _status_text(row: dict[str, Any]) -> str:
    return _upper(row.get("status") or row.get("state") or row.get("acquisition_status") or "")


def _upper(value: Any) -> str:
    return str(value or "").replace("_", " ").strip().upper()


def _missing_documentation(items: dict[str, Any]) -> bool:
    if not items:
        return False
    return any(str(items.get(field) or "") == "Missing" for field in ("nfo", "sfv", "playlist"))
