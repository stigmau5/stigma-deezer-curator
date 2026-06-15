from __future__ import annotations

import json
from collections import Counter
from datetime import datetime
from pathlib import Path
from typing import Any

from curator.atomic import atomic_write_text

LOG_FILENAME = "STIGMA_VALIDATED.txt"


def default_evidence_roots() -> list[Path]:
    candidates = [
        Path.home() / "StreamripDownloads",
        Path.home() / "StreamripDownloads" / "complete_releases",
    ]
    return [path for path in candidates if path.exists()]


def load_json_file(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}
    return data if isinstance(data, dict) else {}


def discover_validation_logs(roots: list[Path]) -> list[Path]:
    logs: set[Path] = set()
    for root in roots:
        if not root.exists():
            continue
        if root.is_file() and root.name == LOG_FILENAME:
            logs.add(root)
            continue
        for path in root.rglob(LOG_FILENAME):
            if path.is_file():
                logs.add(path)
    return sorted(logs)


def evidence_from_validated_index(path: Path) -> dict[str, dict[str, Any]]:
    out: dict[str, dict[str, Any]] = {}
    for album_id, payload in load_json_file(path).items():
        if not isinstance(payload, dict):
            continue
        out[str(album_id)] = {
            "album_id": str(album_id),
            "validated_at": payload.get("validated_at"),
            "track_count": payload.get("tracks"),
            "integrity_status": "unknown",
            "deezer_verification_status": "not_recorded",
            "confidence": "validated_index",
            "available_evidence": ["validated_index"],
            "folder": payload.get("folder"),
            "source": payload.get("source", "validated_albums.json"),
        }
    return out


def parse_validation_log(path: Path) -> dict[str, Any] | None:
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None

    if not isinstance(data, dict):
        return None

    completeness = data.get("completeness", {})
    if not isinstance(completeness, dict):
        completeness = {}

    hashes = completeness.get("hashes", {})
    if not isinstance(hashes, dict):
        hashes = {}

    notes = completeness.get("notes", [])
    if not isinstance(notes, list):
        notes = []

    missing_tracks = completeness.get("missing_tracks", [])
    if not isinstance(missing_tracks, list):
        missing_tracks = []

    album_id = completeness.get("album_id")
    return {
        "album_id": str(album_id).strip() if album_id else None,
        "validated_at": data.get("validated_at"),
        "track_count": data.get("tracks"),
        "integrity_status": "passed",
        "deezer_verification_status": "not_recorded",
        "confidence": "validation_log",
        "available_evidence": ["validation_log"],
        "folder": data.get("album") or path.parent.name,
        "validation_log_path": str(path),
        "warnings_count": len(data.get("warnings", []) or []),
        "hashes_count": len(hashes),
        "completeness": {
            "mode": completeness.get("mode"),
            "expected_tracks": completeness.get("expected_tracks"),
            "found_tracks": completeness.get("found_tracks"),
            "missing_tracks_count": len(missing_tracks),
            "missing_album_id_tracks": completeness.get("missing_album_id_tracks"),
            "album_id": album_id,
            "notes_count": len(notes),
        },
    }


def _merge_evidence(base: dict[str, Any], extra: dict[str, Any]) -> dict[str, Any]:
    merged = dict(base)
    for key, value in extra.items():
        if value is None:
            continue
        if key == "available_evidence":
            existing = set(merged.get(key, []))
            existing.update(value)
            merged[key] = sorted(existing)
        elif key == "confidence":
            merged[key] = "detailed_log" if "validation_log" in extra.get("available_evidence", []) else value
        else:
            merged[key] = value

    if "validated_index" in merged.get("available_evidence", []) and "validation_log" in merged.get(
        "available_evidence", []
    ):
        merged["confidence"] = "detailed_log"
    return merged


def collect_validation_evidence(
    data_dir: Path,
    evidence_roots: list[Path] | None = None,
) -> dict[str, Any]:
    evidence_by_album = evidence_from_validated_index(data_dir / "validated_albums.json")
    folder_to_album = {
        item.get("folder"): album_id
        for album_id, item in evidence_by_album.items()
        if item.get("folder")
    }

    roots = evidence_roots if evidence_roots is not None else default_evidence_roots()
    logs = discover_validation_logs(roots)
    unmatched_logs: list[dict[str, Any]] = []

    for path in logs:
        parsed = parse_validation_log(path)
        if not parsed:
            unmatched_logs.append({"path": str(path), "reason": "unreadable"})
            continue

        album_id = parsed.get("album_id")
        if not album_id and parsed.get("folder"):
            album_id = folder_to_album.get(parsed["folder"])

        if album_id:
            existing = evidence_by_album.get(album_id, {"album_id": album_id})
            evidence_by_album[album_id] = _merge_evidence(existing, parsed | {"album_id": album_id})
        else:
            unmatched_logs.append(
                {
                    "path": str(path),
                    "folder": parsed.get("folder"),
                    "reason": "no_album_id_or_index_folder_match",
                }
            )

    confidence_counts = Counter(
        item.get("confidence", "unknown") for item in evidence_by_album.values()
    )
    evidence_counts = Counter()
    for item in evidence_by_album.values():
        for evidence in item.get("available_evidence", []):
            evidence_counts[evidence] += 1

    return {
        "evidence_by_album": evidence_by_album,
        "summary": {
            "validated_index_albums": len(evidence_from_validated_index(data_dir / "validated_albums.json")),
            "validation_logs_found": len(logs),
            "albums_with_evidence": len(evidence_by_album),
            "unmatched_validation_logs": len(unmatched_logs),
            "confidence_counts": dict(confidence_counts),
            "evidence_counts": dict(evidence_counts),
            "evidence_roots": [str(path) for path in roots],
        },
        "unmatched_logs": unmatched_logs,
    }


def attach_validation_evidence(
    registry: dict[str, Any],
    evidence_result: dict[str, Any],
) -> dict[str, Any]:
    evidence_by_album = evidence_result.get("evidence_by_album", {})
    for row in registry.get("albums", []):
        evidence = evidence_by_album.get(str(row.get("album_id")))
        if not evidence:
            row["validation_evidence"] = {
                "available": False,
                "available_evidence": [],
                "integrity_status": "none",
                "deezer_verification_status": "none",
                "confidence": "none",
            }
            continue

        row["validation_evidence"] = {
            "available": True,
            **evidence,
        }
        if evidence.get("validated_at"):
            row.setdefault("timestamps", {})["validated_at"] = evidence["validated_at"]
        if evidence.get("track_count") is not None:
            row.setdefault("details", {})["validated_tracks"] = evidence["track_count"]

    registry["validation_evidence_summary"] = evidence_result.get("summary", {})
    registry["unmatched_validation_logs"] = evidence_result.get("unmatched_logs", [])
    return registry


def _parse_dt(value: Any) -> datetime | None:
    if not isinstance(value, str) or not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None


def validation_age_buckets(registry: dict[str, Any], *, now: datetime | None = None) -> dict[str, int]:
    now = now or datetime.now()
    buckets = {
        "missing_timestamp": 0,
        "last_30_days": 0,
        "31_90_days": 0,
        "91_365_days": 0,
        "over_365_days": 0,
    }
    for row in registry.get("albums", []):
        if not row.get("states", {}).get("validated", False):
            continue
        dt = _parse_dt(row.get("validation_evidence", {}).get("validated_at"))
        if not dt:
            buckets["missing_timestamp"] += 1
            continue
        age_days = (now.replace(tzinfo=None) - dt.replace(tzinfo=None)).days
        if age_days <= 30:
            buckets["last_30_days"] += 1
        elif age_days <= 90:
            buckets["31_90_days"] += 1
        elif age_days <= 365:
            buckets["91_365_days"] += 1
        else:
            buckets["over_365_days"] += 1
    return buckets


def render_validation_evidence_report(registry: dict[str, Any]) -> str:
    summary = registry.get("validation_evidence_summary", {})
    rows = [
        row
        for row in registry.get("albums", [])
        if row.get("validation_evidence", {}).get("available")
    ]
    lines = [
        "# Validation Evidence Report",
        "",
        f"Generated from lifecycle registry: {registry.get('generated_at', 'unknown')}",
        "",
        "Validator evidence is derived from `validated_albums.json` and discovered `STIGMA_VALIDATED.txt` files.",
        "",
        "## Summary",
        "",
        f"- Albums with validation evidence: `{summary.get('albums_with_evidence', len(rows))}`",
        f"- Validated-index albums: `{summary.get('validated_index_albums', 0)}`",
        f"- Validation logs found: `{summary.get('validation_logs_found', 0)}`",
        f"- Unmatched validation logs: `{summary.get('unmatched_validation_logs', 0)}`",
        "",
        "## Evidence Roots",
        "",
    ]
    for root in summary.get("evidence_roots", []):
        lines.append(f"- `{root}`")

    lines.extend(
        [
            "",
            "## Evidence By Album",
            "",
            "| Album ID | Artist | Title | Validated At | Tracks | Integrity | Deezer | Confidence | Evidence |",
            "| --- | --- | --- | --- | ---: | --- | --- | --- | --- |",
        ]
    )
    for row in sorted(rows, key=lambda item: (item.get("artist", ""), item.get("title", ""), item["album_id"])):
        ev = row["validation_evidence"]
        lines.append(
            f"| `{row['album_id']}` | {_escape(row.get('artist'))} | {_escape(row.get('title'))} | "
            f"{_escape(ev.get('validated_at', ''))} | {ev.get('track_count', '')} | "
            f"{_escape(ev.get('integrity_status', ''))} | {_escape(ev.get('deezer_verification_status', ''))} | "
            f"{_escape(ev.get('confidence', ''))} | {_escape(', '.join(ev.get('available_evidence', [])))} |"
        )
    return "\n".join(lines) + "\n"


def render_validation_coverage_report(registry: dict[str, Any]) -> str:
    albums = registry.get("albums", [])
    total = len(albums)
    validated = [row for row in albums if row.get("states", {}).get("validated", False)]
    with_evidence = [row for row in albums if row.get("validation_evidence", {}).get("available")]
    with_logs = [
        row
        for row in albums
        if "validation_log" in row.get("validation_evidence", {}).get("available_evidence", [])
    ]
    lines = [
        "# Validation Coverage Report",
        "",
        f"Generated from lifecycle registry: {registry.get('generated_at', 'unknown')}",
        "",
        "| Metric | Albums | Percent of total |",
        "| --- | ---: | ---: |",
        f"| Total albums | {total} | 100.0% |",
        f"| Validated state | {len(validated)} | {_pct(len(validated), total)} |",
        f"| Any validation evidence | {len(with_evidence)} | {_pct(len(with_evidence), total)} |",
        f"| Detailed validation logs matched | {len(with_logs)} | {_pct(len(with_logs), total)} |",
        "",
    ]
    return "\n".join(lines)


def render_validation_age_report(registry: dict[str, Any], *, now: datetime | None = None) -> str:
    buckets = validation_age_buckets(registry, now=now)
    lines = [
        "# Validation Age Report",
        "",
        f"Generated from lifecycle registry: {registry.get('generated_at', 'unknown')}",
        "",
        "| Age bucket | Albums |",
        "| --- | ---: |",
        f"| Missing timestamp | {buckets['missing_timestamp']} |",
        f"| Last 30 days | {buckets['last_30_days']} |",
        f"| 31-90 days | {buckets['31_90_days']} |",
        f"| 91-365 days | {buckets['91_365_days']} |",
        f"| Over 365 days | {buckets['over_365_days']} |",
        "",
    ]
    return "\n".join(lines)


def render_validation_confidence_report(registry: dict[str, Any]) -> str:
    counts = Counter(
        row.get("validation_evidence", {}).get("confidence", "none")
        for row in registry.get("albums", [])
    )
    lines = [
        "# Validation Confidence Report",
        "",
        f"Generated from lifecycle registry: {registry.get('generated_at', 'unknown')}",
        "",
        "| Confidence | Albums | Meaning |",
        "| --- | ---: | --- |",
        f"| detailed_log | {counts.get('detailed_log', 0)} | Matched `STIGMA_VALIDATED.txt` evidence. |",
        f"| validated_index | {counts.get('validated_index', 0)} | Present in `validated_albums.json` only. |",
        f"| none | {counts.get('none', 0)} | No validation evidence. |",
        "",
    ]
    unmatched = registry.get("unmatched_validation_logs", [])
    lines.extend(
        [
            "## Unmatched Validation Logs",
            "",
            f"Unmatched logs: `{len(unmatched)}`",
            "",
            "| Path | Reason |",
            "| --- | --- |",
        ]
    )
    for item in unmatched[:100]:
        lines.append(f"| `{_escape(item.get('path', ''))}` | {_escape(item.get('reason', ''))} |")
    return "\n".join(lines) + "\n"


def write_validation_reports(registry: dict[str, Any], reports_dir: Path) -> None:
    reports_dir.mkdir(parents=True, exist_ok=True)
    atomic_write_text(reports_dir / "validation_evidence_report.md", render_validation_evidence_report(registry))
    atomic_write_text(reports_dir / "validation_coverage_report.md", render_validation_coverage_report(registry))
    atomic_write_text(reports_dir / "validation_age_report.md", render_validation_age_report(registry))
    atomic_write_text(reports_dir / "validation_confidence_report.md", render_validation_confidence_report(registry))


def _pct(count: int, total: int) -> str:
    if total == 0:
        return "0.0%"
    return f"{(count / total) * 100:.1f}%"


def _escape(value: Any) -> str:
    return str(value or "").replace("|", "\\|").replace("\n", " ")
