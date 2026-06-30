from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any, Iterable

from audio_division.pipeline_controller import (
    ACTION_ARCHIVE,
    ACTION_GENERATE_DOCUMENTATION,
    ACTION_HEALTHY,
    ACTION_REFRESH,
    ACTION_REFRESH_METADATA,
    ACTION_REVIEW,
    ACTION_VALIDATE,
    recommend_next_action,
)


STAGE_ACQUIRE = "Acquire"
STAGE_DOWNLOADED = "Downloaded"
STAGE_VALIDATED = "Validated"
STAGE_READY_TO_ARCHIVE = "Ready To Archive"
STAGE_ARCHIVED = "Archived"
STAGE_NEEDS_ATTENTION = "Needs Attention"
STAGE_COMPLETED = "Completed"

PIPELINE_STAGES = (
    STAGE_ACQUIRE,
    STAGE_DOWNLOADED,
    STAGE_VALIDATED,
    STAGE_READY_TO_ARCHIVE,
    STAGE_ARCHIVED,
    STAGE_NEEDS_ATTENTION,
    STAGE_COMPLETED,
)


@dataclass(frozen=True)
class PipelineDashboardItem:
    stage: str
    album: str
    artist: str
    recommended_next_action: str
    count: int
    state: str
    reason: str
    confidence: str
    source: str = ""
    release_id: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def build_pipeline_dashboard(releases: Iterable[Any]) -> dict[str, Any]:
    items = _dedupe_items([release_to_dashboard_item(release) for release in releases])
    grouped = {stage: [] for stage in PIPELINE_STAGES}
    for item in items:
        grouped.setdefault(item.stage, []).append(item.to_dict())

    stages = [
        {
            "stage": stage,
            "count": len(grouped.get(stage, [])),
            "items": sorted(
                grouped.get(stage, []),
                key=lambda row: (_sort_text(row.get("artist")), _sort_text(row.get("album"))),
            ),
        }
        for stage in PIPELINE_STAGES
    ]
    return {
        "total_releases": len(items),
        "stages": stages,
        "stage_counts": {stage["stage"]: stage["count"] for stage in stages},
    }


def release_to_dashboard_item(release: Any) -> PipelineDashboardItem:
    row = _release_row(release)
    recommendation = recommend_next_action(row)
    stage = _stage_for_release(row, recommendation.recommended_action)
    return PipelineDashboardItem(
        stage=stage,
        album=_album(row),
        artist=str(row.get("artist") or row.get("artist_name") or ""),
        recommended_next_action=recommendation.recommended_action,
        count=1,
        state=recommendation.state,
        reason=recommendation.reason,
        confidence=recommendation.confidence,
        source=str(row.get("source") or row.get("source_section") or ""),
        release_id=str(row.get("deezer_album_id") or row.get("album_id") or row.get("archive_path") or ""),
    )


def _stage_for_release(row: dict[str, Any], action: str) -> str:
    if _is_acquisition_candidate(row):
        return STAGE_ACQUIRE
    if action == ACTION_VALIDATE:
        return STAGE_DOWNLOADED
    if action == ACTION_ARCHIVE:
        return STAGE_READY_TO_ARCHIVE
    if _validated_without_archive_action(row):
        return STAGE_VALIDATED
    if action == ACTION_REFRESH:
        return STAGE_ARCHIVED
    if action == ACTION_HEALTHY:
        return STAGE_COMPLETED
    if action in {ACTION_REVIEW, ACTION_REFRESH_METADATA, ACTION_GENERATE_DOCUMENTATION}:
        return STAGE_NEEDS_ATTENTION
    return STAGE_NEEDS_ATTENTION


def _is_acquisition_candidate(row: dict[str, Any]) -> bool:
    acquisition = row.get("acquisition_recommendation")
    if isinstance(acquisition, dict) and _upper(acquisition.get("recommendation")) == "READY TO ACQUIRE":
        return True
    status = _upper(row.get("acquisition_status") or row.get("status"))
    if status in {"NEEDS DOWNLOAD", "READY TO ACQUIRE"}:
        return True
    has_source_identity = bool(row.get("url") or row.get("deezer_album_id"))
    has_workflow_evidence = bool(row.get("folder") or row.get("archive_path"))
    return has_source_identity and not has_workflow_evidence and _upper(row.get("archive_status")) in {"", "NOT ARCHIVED"}


def _validated_without_archive_action(row: dict[str, Any]) -> bool:
    lifecycle = _upper(row.get("lifecycle_state") or row.get("highest_state"))
    status = _upper(row.get("status") or row.get("validation_status"))
    return lifecycle == "VALIDATED" or status in {"VALIDATED", "ALREADY VALIDATED"}


def _release_row(value: Any) -> dict[str, Any]:
    if isinstance(value, dict):
        return dict(value)
    if hasattr(value, "to_row"):
        row = value.to_row()
        if isinstance(row, dict):
            return dict(row)
    return {
        name: getattr(value, name)
        for name in dir(value)
        if not name.startswith("_") and not callable(getattr(value, name))
    }


def _album(row: dict[str, Any]) -> str:
    return str(row.get("album") or row.get("title") or "")


def _upper(value: Any) -> str:
    return str(value or "").replace("_", " ").strip().upper()


def _sort_text(value: Any) -> str:
    return str(value or "").casefold()


def _dedupe_items(items: list[PipelineDashboardItem]) -> list[PipelineDashboardItem]:
    by_key: dict[str, PipelineDashboardItem] = {}
    for item in items:
        key = item.release_id or f"{item.artist.casefold()}::{item.album.casefold()}"
        current = by_key.get(key)
        if current is None or _stage_priority(item.stage) >= _stage_priority(current.stage):
            by_key[key] = item
    return list(by_key.values())


def _stage_priority(stage: str) -> int:
    priority = {
        STAGE_NEEDS_ATTENTION: 0,
        STAGE_ACQUIRE: 1,
        STAGE_DOWNLOADED: 2,
        STAGE_VALIDATED: 3,
        STAGE_READY_TO_ARCHIVE: 4,
        STAGE_ARCHIVED: 5,
        STAGE_COMPLETED: 6,
    }
    return priority.get(stage, 0)
