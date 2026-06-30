from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import datetime, timedelta
from typing import Any, Iterable

from audio_division.incoming_projection import STATUS_DUPLICATE_DOWNLOAD
from audio_division.lifecycle_state import (
    STATE_ARCHIVED,
    STATE_DISCOVERED,
    STATE_DOWNLOADED,
    STATE_READY_FOR_PROCESSING,
    STATE_UNKNOWN,
    STATE_VALIDATED,
    attach_lifecycle_state,
)


PIPELINE_HEALTH_STATES = (
    STATE_DISCOVERED,
    STATE_DOWNLOADED,
    STATE_VALIDATED,
    STATE_READY_FOR_PROCESSING,
    STATE_ARCHIVED,
    "NEEDS_REVIEW",
    STATE_UNKNOWN,
)


@dataclass(frozen=True)
class PipelineHealthReport:
    discovered: int
    downloaded: int
    validated: int
    ready_to_process: int
    archived: int
    needs_review: int
    unknown: int
    stalled_downloads: int
    duplicate_downloads: int
    validation_failures: int
    ready_to_archive: int
    recently_archived: int
    total_releases: int

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def pipeline_health_report(
    releases: Iterable[dict[str, Any]],
    *,
    reference_time: datetime | None = None,
    recent_days: int = 30,
) -> PipelineHealthReport:
    rows = [_with_lifecycle_state(row) for row in releases]
    counts = {state: 0 for state in PIPELINE_HEALTH_STATES}
    for row in rows:
        state = _pipeline_state(row)
        if _needs_review(row, state):
            counts["NEEDS_REVIEW"] += 1
        else:
            counts[state] = counts.get(state, 0) + 1

    return PipelineHealthReport(
        discovered=counts[STATE_DISCOVERED],
        downloaded=counts[STATE_DOWNLOADED],
        validated=counts[STATE_VALIDATED],
        ready_to_process=counts[STATE_READY_FOR_PROCESSING],
        archived=counts[STATE_ARCHIVED],
        needs_review=counts["NEEDS_REVIEW"],
        unknown=counts[STATE_UNKNOWN],
        stalled_downloads=sum(1 for row in rows if _is_stalled_download(row)),
        duplicate_downloads=sum(1 for row in rows if _is_duplicate_download(row)),
        validation_failures=sum(1 for row in rows if _is_validation_failure(row)),
        ready_to_archive=sum(1 for row in rows if _is_ready_to_archive(row)),
        recently_archived=sum(1 for row in rows if _is_recently_archived(row, reference_time, recent_days)),
        total_releases=len(rows),
    )


def pipeline_health_summary(
    releases: Iterable[dict[str, Any]],
    *,
    reference_time: datetime | None = None,
    recent_days: int = 30,
) -> dict[str, Any]:
    return pipeline_health_report(releases, reference_time=reference_time, recent_days=recent_days).to_dict()


def _with_lifecycle_state(row: dict[str, Any]) -> dict[str, Any]:
    if isinstance(row.get("pipeline_state"), dict) and row["pipeline_state"].get("state"):
        return dict(row)
    legacy = _legacy_state(row)
    if legacy in {STATE_DISCOVERED, STATE_DOWNLOADED, STATE_VALIDATED, STATE_READY_FOR_PROCESSING, STATE_ARCHIVED}:
        updated = dict(row)
        updated["pipeline_state"] = {
            "state": legacy,
            "evidence": ["lifecycle_registry"],
            "reason": "Lifecycle registry state.",
            "confidence": "MEDIUM",
            "conflicts": [],
        }
        return updated
    return attach_lifecycle_state(dict(row))


def _pipeline_state(row: dict[str, Any]) -> str:
    state = str(row.get("pipeline_state", {}).get("state") or STATE_UNKNOWN).upper()
    return state if state in PIPELINE_HEALTH_STATES else STATE_UNKNOWN


def _legacy_state(row: dict[str, Any]) -> str:
    state = str(row.get("lifecycle_state") or row.get("highest_state") or "").strip().upper()
    if state in {"ATTEMPTED", "SHIPPED"}:
        return STATE_DOWNLOADED
    if state == "CONFIRMED":
        return STATE_VALIDATED
    if state == "READY TO PROCESS":
        return STATE_READY_FOR_PROCESSING
    return state


def _needs_review(row: dict[str, Any], state: str) -> bool:
    if state == STATE_UNKNOWN:
        return False
    if row.get("pipeline_state", {}).get("conflicts"):
        return True
    confidence = str(row.get("identity_confidence") or row.get("album_truth", {}).get("identity_confidence") or "")
    maintenance = row.get("album_truth", {}).get("maintenance", {})
    return confidence in {"LOW", "UNKNOWN"} or maintenance.get("category") == "needs_review"


def _is_stalled_download(row: dict[str, Any]) -> bool:
    state = _pipeline_state(row)
    if state != STATE_DOWNLOADED:
        return False
    status = _upper(row.get("status") or row.get("state"))
    if status in {"READY TO VALIDATE", "DUPLICATE DOWNLOAD"}:
        return False
    return not _validation_present(row) and not row.get("archive_path")


def _is_duplicate_download(row: dict[str, Any]) -> bool:
    status = _upper(row.get("status") or row.get("state"))
    evidence = {_upper(item) for item in row.get("evidence", []) if item}
    return status == _upper(STATUS_DUPLICATE_DOWNLOAD) or "DUPLICATE DOWNLOAD" in evidence


def _is_validation_failure(row: dict[str, Any]) -> bool:
    status = _upper(row.get("validation_status") or row.get("status") or "")
    result = _upper(row.get("result") or row.get("validation_result") or "")
    exit_code = row.get("exit_code")
    evidence = row.get("validation_evidence", {}) if isinstance(row.get("validation_evidence"), dict) else {}
    return (
        status in {"FAILED", "FAILURE", "VALIDATION FAILED"}
        or result in {"FAILED", "FAILURE"}
        or evidence.get("result") == "failure"
        or (exit_code not in {None, "", 0, "0"} and str(exit_code).isdigit())
    )


def _is_ready_to_archive(row: dict[str, Any]) -> bool:
    state = _pipeline_state(row)
    if state == STATE_ARCHIVED:
        return False
    return state in {STATE_VALIDATED, STATE_READY_FOR_PROCESSING} or _validation_present(row)


def _is_recently_archived(row: dict[str, Any], reference_time: datetime | None, recent_days: int) -> bool:
    if _pipeline_state(row) != STATE_ARCHIVED:
        return False
    timestamp = _first_timestamp(row, ("archived_at", "archive_updated_at", "updated_at", "created_at"))
    if timestamp is None:
        return False
    reference = reference_time or datetime.now()
    return reference - timedelta(days=recent_days) <= timestamp <= reference


def _validation_present(row: dict[str, Any]) -> bool:
    if str(row.get("validation_status") or "").lower() == "validated":
        return True
    items = row.get("album_truth", {}).get("items", {}) or row.get("album_status", {}).get("items", {})
    return items.get("validation") == "Present"


def _first_timestamp(row: dict[str, Any], fields: tuple[str, ...]) -> datetime | None:
    for field in fields:
        parsed = _parse_timestamp(row.get(field))
        if parsed is not None:
            return parsed
    return None


def _parse_timestamp(value: Any) -> datetime | None:
    text = str(value or "").strip()
    if not text:
        return None
    try:
        return datetime.fromisoformat(text.replace("Z", "+00:00")).replace(tzinfo=None)
    except ValueError:
        return None


def _upper(value: Any) -> str:
    return str(value or "").replace("_", " ").strip().upper()
