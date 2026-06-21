from __future__ import annotations

from collections import Counter
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Iterable

from audio_division.artifacts import detect_artifacts
from curator.atomic import atomic_write_text

STATE_DISCOVERED = "DISCOVERED"
STATE_DOWNLOADED = "DOWNLOADED"
STATE_VALIDATED = "VALIDATED"
STATE_READY_FOR_PROCESSING = "READY_FOR_PROCESSING"
STATE_ARCHIVED = "ARCHIVED"
STATE_UNKNOWN = "UNKNOWN"

CANONICAL_STATES = (
    STATE_DISCOVERED,
    STATE_DOWNLOADED,
    STATE_VALIDATED,
    STATE_READY_FOR_PROCESSING,
    STATE_ARCHIVED,
    STATE_UNKNOWN,
)


@dataclass(frozen=True)
class AlbumLifecycleState:
    state: str
    evidence: tuple[str, ...]
    reason: str
    confidence: str
    conflicts: tuple[str, ...] = ()

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        data["evidence"] = list(self.evidence)
        data["conflicts"] = list(self.conflicts)
        return data


def detect_lifecycle_state(album: dict[str, Any], queue_entry: dict[str, Any] | None = None) -> AlbumLifecycleState:
    evidence = lifecycle_evidence(album, queue_entry)
    conflicts = lifecycle_conflicts(evidence)

    if evidence["archived"]:
        return _state(STATE_ARCHIVED, evidence, "Archive album root exists.", "HIGH", conflicts)
    if evidence["validated"] and evidence["downloaded"]:
        return _state(
            STATE_READY_FOR_PROCESSING,
            evidence,
            "Validated album exists outside the archive.",
            "HIGH",
            conflicts,
        )
    if evidence["validated"]:
        return _state(STATE_VALIDATED, evidence, "Validator evidence exists.", "MEDIUM", conflicts)
    if evidence["downloaded"]:
        return _state(STATE_DOWNLOADED, evidence, "Downloaded folder exists.", "HIGH", conflicts)
    if evidence["discovered"]:
        return _state(STATE_DISCOVERED, evidence, "Curator discovery evidence exists.", "MEDIUM", conflicts)
    return _state(STATE_UNKNOWN, evidence, "No lifecycle evidence found.", "LOW", conflicts)


def lifecycle_evidence(album: dict[str, Any], queue_entry: dict[str, Any] | None = None) -> dict[str, Any]:
    queue_entry = queue_entry or {}
    sources: list[str] = []
    archive_path = str(album.get("archive_path") or "").strip()
    folder = str(album.get("folder") or "").strip()
    album_id = str(album.get("album_id") or "").strip()
    legacy_state = str(album.get("lifecycle_state") or album.get("highest_state") or "").strip().upper()

    archived = _archive_present(album, archive_path)
    downloaded = _download_present(folder, archive_path, archived)
    validation_marker = _validation_marker_path(folder, archive_path)
    validated = _validation_present(album) or bool(validation_marker)
    discovered = bool(album_id or legacy_state in {"DISCOVERED", "ATTEMPTED", "SHIPPED", "VALIDATED", "CONFIRMED"})

    if discovered:
        sources.append("curator_state")
    if queue_entry.get("state"):
        sources.append("processing_queue")
    if downloaded:
        sources.append("download_folder")
    if validation_marker:
        sources.append("validation_marker")
    if validated and not validation_marker:
        sources.extend(_validation_sources(album))
    if archived:
        sources.append("archive_filesystem")

    return {
        "discovered": discovered,
        "downloaded": downloaded,
        "validated": validated,
        "archived": archived,
        "album_id": album_id,
        "archive_path": archive_path,
        "download_folder": folder if downloaded else "",
        "validation_marker": str(validation_marker) if validation_marker else "",
        "legacy_state": legacy_state,
        "sources": tuple(sorted(set(source for source in sources if source))),
    }


def lifecycle_conflicts(evidence: dict[str, Any]) -> tuple[str, ...]:
    conflicts: list[str] = []
    if evidence.get("archived") and evidence.get("downloaded"):
        conflicts.append("ready_for_processing_and_archived")
    if evidence.get("validated") and not evidence.get("archived") and not evidence.get("downloaded"):
        conflicts.append("validated_without_album_folder")
    if evidence.get("archived") and not evidence.get("archive_path"):
        conflicts.append("archived_without_archive_path")
    return tuple(conflicts)


def attach_lifecycle_state(album: dict[str, Any], queue_entry: dict[str, Any] | None = None) -> dict[str, Any]:
    row = dict(album)
    row["pipeline_state"] = detect_lifecycle_state(row, queue_entry).to_dict()
    return row


def lifecycle_state_summary(albums: Iterable[dict[str, Any]]) -> dict[str, Any]:
    rows = list(albums)
    state_counts = Counter()
    evidence_counts = Counter()
    conflict_counts = Counter()
    unknown = []
    conflicts = []
    for row in rows:
        state = _row_state(row)
        state_counts[state] += 1
        for source in row.get("pipeline_state", {}).get("evidence", []):
            evidence_counts[source] += 1
        row_conflicts = row.get("pipeline_state", {}).get("conflicts", [])
        for conflict in row_conflicts:
            conflict_counts[conflict] += 1
        if state == STATE_UNKNOWN:
            unknown.append(row)
        if row_conflicts:
            conflicts.append(row)
    return {
        "total_albums": len(rows),
        "state_counts": {state: state_counts.get(state, 0) for state in CANONICAL_STATES},
        "evidence_counts": dict(sorted(evidence_counts.items())),
        "conflict_counts": dict(sorted(conflict_counts.items())),
        "unknown_albums": len(unknown),
        "conflicting_albums": len(conflicts),
    }


def merge_lifecycle_rows(*collections: Iterable[dict[str, Any]]) -> list[dict[str, Any]]:
    rows: dict[str, dict[str, Any]] = {}
    archived_album_ids: set[str] = set()
    pending: list[dict[str, Any]] = []
    for collection in collections:
        for raw in collection:
            row = raw if raw.get("pipeline_state") else attach_lifecycle_state(raw)
            if _row_state(row) == STATE_ARCHIVED and row.get("archive_path"):
                rows[f"archive:{row['archive_path']}"] = row
                if row.get("album_id"):
                    archived_album_ids.add(str(row["album_id"]))
                continue
            pending.append(row)

    for row in pending:
        if row.get("album_id") and str(row["album_id"]) in archived_album_ids:
            continue
        key = _identity_key(row)
        existing = rows.get(key)
        if not existing or _state_rank(_row_state(row)) > _state_rank(_row_state(existing)):
            rows[key] = row
    return sorted(rows.values(), key=lambda item: (_sort_text(item.get("artist")), _sort_text(item.get("title") or item.get("album")), _identity_key(item)))


def render_lifecycle_state_report(albums: list[dict[str, Any]]) -> str:
    summary = lifecycle_state_summary(albums)
    lines = [
        "# Lifecycle State Report",
        "",
        "Lifecycle state is derived from existing state files and filesystem evidence. No workflow actions are executed.",
        "",
        "## State Counts",
        "",
        f"- Albums evaluated: `{summary['total_albums']}`",
        f"- Unknown albums: `{summary['unknown_albums']}`",
        f"- Albums with conflicting evidence: `{summary['conflicting_albums']}`",
        "",
        "| State | Albums |",
        "| --- | ---: |",
    ]
    for state in CANONICAL_STATES:
        lines.append(f"| {state} | {summary['state_counts'].get(state, 0)} |")

    lines.extend(["", "## Evidence Counts", "", "| Evidence | Albums |", "| --- | ---: |"])
    if summary["evidence_counts"]:
        for source, count in summary["evidence_counts"].items():
            lines.append(f"| {source} | {count} |")
    else:
        lines.append("| none | 0 |")

    lines.extend(["", "## Impossible Or Conflicting States", "", "| Conflict | Albums |", "| --- | ---: |"])
    if summary["conflict_counts"]:
        for conflict, count in summary["conflict_counts"].items():
            lines.append(f"| {conflict} | {count} |")
    else:
        lines.append("| none | 0 |")

    conflict_rows = [row for row in albums if row.get("pipeline_state", {}).get("conflicts")]
    lines.extend(["", "## Conflict Examples", "", "| State | Artist | Album | Album ID | Path | Conflicts | Reason |", "| --- | --- | --- | --- | --- | --- | --- |"])
    if not conflict_rows:
        lines.append("| none |  |  |  |  |  |  |")
    for row in conflict_rows[:200]:
        state = row.get("pipeline_state", {})
        lines.append(
            f"| {_escape(state.get('state'))} | {_escape(row.get('artist'))} | {_escape(row.get('title') or row.get('album'))} | "
            f"`{_escape(row.get('album_id'))}` | `{_escape(row.get('archive_path') or row.get('folder'))}` | "
            f"{_escape(', '.join(state.get('conflicts', [])))} | {_escape(state.get('reason'))} |"
        )

    unknown_rows = [row for row in albums if _row_state(row) == STATE_UNKNOWN]
    lines.extend(["", "## Unknown Albums", "", "| Artist | Album | Path | Reason |", "| --- | --- | --- | --- |"])
    if not unknown_rows:
        lines.append("| none |  |  |  |")
    for row in unknown_rows[:200]:
        state = row.get("pipeline_state", {})
        lines.append(
            f"| {_escape(row.get('artist'))} | {_escape(row.get('title') or row.get('album'))} | "
            f"`{_escape(row.get('archive_path') or row.get('folder'))}` | {_escape(state.get('reason'))} |"
        )

    return "\n".join(lines) + "\n"


def write_lifecycle_state_report(albums: list[dict[str, Any]], reports_dir: Path) -> None:
    reports_dir.mkdir(parents=True, exist_ok=True)
    atomic_write_text(reports_dir / "lifecycle_state_report.md", render_lifecycle_state_report(albums))


def _archive_present(album: dict[str, Any], archive_path: str) -> bool:
    if album.get("lifecycle_state") == STATE_ARCHIVED:
        return True
    if album.get("archive_path_reason") == "archive_registry":
        return True
    if archive_path and Path(archive_path).is_dir() and _archive_evidence(album):
        return True
    return False


def _download_present(folder: str, archive_path: str, archived: bool) -> bool:
    path_text = folder or ("" if archived else archive_path)
    return bool(path_text and Path(path_text).is_dir())


def _archive_evidence(album: dict[str, Any]) -> bool:
    artifacts = album.get("artifacts", {})
    status_items = album.get("album_truth", {}).get("items", {}) or album.get("album_status", {}).get("items", {})
    if any(artifacts.get(name) for name in ("nfo", "sfv", "playlist", "artwork", "validation_log")):
        return True
    return any(status_items.get(name) == "Present" for name in ("nfo", "sfv", "playlist", "artwork", "validation"))


def _validation_present(album: dict[str, Any]) -> bool:
    if album.get("validation_status") == "validated":
        return True
    validation = album.get("validation", {})
    if isinstance(validation, dict) and validation.get("available"):
        return True
    if album.get("validation_evidence", {}).get("available"):
        return True
    status_items = album.get("album_truth", {}).get("items", {}) or album.get("album_status", {}).get("items", {})
    if status_items.get("validation") == "Present":
        return True
    legacy_state = str(album.get("lifecycle_state") or album.get("highest_state") or "").upper()
    return legacy_state == STATE_VALIDATED


def _validation_sources(album: dict[str, Any]) -> list[str]:
    validation = album.get("validation", {}) if isinstance(album.get("validation"), dict) else {}
    evidence = album.get("validation_evidence", {}) if isinstance(album.get("validation_evidence"), dict) else {}
    sources = []
    if validation.get("validation_log_path") or evidence.get("validation_log_path"):
        sources.append("validation_log")
    if validation.get("available") or evidence.get("available") or album.get("validation_status") == "validated":
        sources.append("validator_evidence")
    status_items = album.get("album_truth", {}).get("items", {}) or album.get("album_status", {}).get("items", {})
    status_sources = album.get("album_truth", {}).get("sources", {})
    validation_source = status_sources.get("validation")
    if status_items.get("validation") == "Present" and validation_source:
        sources.append(validation_source)
    return sources or ["validator_evidence"]


def _validation_marker_path(folder: str, archive_path: str) -> Path | None:
    for path_text in (folder, archive_path):
        if not path_text:
            continue
        marker = detect_artifacts(path_text).first_file("validation")
        if marker:
            return marker
    return None


def _state(state: str, evidence: dict[str, Any], reason: str, confidence: str, conflicts: tuple[str, ...]) -> AlbumLifecycleState:
    return AlbumLifecycleState(
        state=state,
        evidence=tuple(evidence.get("sources", ())),
        reason=reason,
        confidence=confidence,
        conflicts=conflicts,
    )


def _row_state(row: dict[str, Any]) -> str:
    state = row.get("pipeline_state", {}).get("state", STATE_UNKNOWN)
    return state if state in CANONICAL_STATES else STATE_UNKNOWN


def _state_rank(state: str) -> int:
    order = {
        STATE_UNKNOWN: 0,
        STATE_DISCOVERED: 1,
        STATE_DOWNLOADED: 2,
        STATE_VALIDATED: 3,
        STATE_READY_FOR_PROCESSING: 4,
        STATE_ARCHIVED: 5,
    }
    return order.get(state, 0)


def _identity_key(row: dict[str, Any]) -> str:
    if row.get("album_id"):
        return f"album:{row['album_id']}"
    if row.get("archive_path"):
        return f"archive:{row['archive_path']}"
    if row.get("folder"):
        return f"folder:{row['folder']}"
    return f"name:{row.get('artist', '')}:{row.get('title') or row.get('album', '')}"


def _sort_text(value: Any) -> str:
    return str(value or "").lower()


def _escape(value: Any) -> str:
    return str(value or "").replace("|", "\\|").replace("\n", " ").strip()
