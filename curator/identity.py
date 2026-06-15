from __future__ import annotations

import hashlib
import json
import re
import unicodedata
from collections import Counter
from datetime import datetime
from pathlib import Path
from typing import Any

from curator.atomic import atomic_write_text
from curator.validator_evidence import parse_validation_log

CONFIDENCE_ORDER = ("HIGH", "MEDIUM", "LOW", "UNKNOWN")
FOLDER_RE = re.compile(r"(.+)-(\d{4})-FLAC-STiGMA$")


def normalize_identity_text(value: Any) -> str:
    text = str(value or "").lower().replace("&", "and")
    text = unicodedata.normalize("NFKD", text)
    text = "".join(char for char in text if not unicodedata.combining(char))
    text = re.sub(r"[^a-z0-9]+", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def split_archive_folder(folder: str | None) -> dict[str, str | None]:
    if not folder:
        return {"artist": None, "title": None, "year": None}

    match = FOLDER_RE.match(folder)
    body = match.group(1) if match else folder
    year = match.group(2) if match else None
    if "-" not in body:
        return {"artist": None, "title": body.strip() or None, "year": year}

    artist, title = body.split("-", 1)
    return {
        "artist": artist.strip() or None,
        "title": title.strip() or None,
        "year": year,
    }


def manifest_hash_from_hashes(hashes: dict[str, Any]) -> str | None:
    if not hashes:
        return None
    manifest = "\n".join(f"{name}\0{hashes[name]}" for name in sorted(hashes))
    return hashlib.sha256(manifest.encode("utf-8")).hexdigest()


def _log_manifest_hash(path: str | None) -> str | None:
    if not path:
        return None
    try:
        data = json.loads(Path(path).read_text(encoding="utf-8"))
    except Exception:
        return None
    completeness = data.get("completeness", {}) if isinstance(data, dict) else {}
    hashes = completeness.get("hashes", {}) if isinstance(completeness, dict) else {}
    return manifest_hash_from_hashes(hashes) if isinstance(hashes, dict) else None


def _release_from_lifecycle(row: dict[str, Any]) -> dict[str, Any]:
    album_id = str(row.get("album_id", ""))
    validation = row.get("validation_evidence", {})
    archive_folder = (
        validation.get("folder")
        or row.get("details", {}).get("validated_folder")
        or None
    )
    evidence = ["lifecycle_album_id"]
    confidence = "UNKNOWN"

    if row.get("states", {}).get("validated"):
        confidence = "HIGH"
        evidence.append("validated_index_album_id_match")

    if validation.get("available"):
        confidence = "HIGH"
        evidence.extend(validation.get("available_evidence", []))

    if "validation_log" in validation.get("available_evidence", []):
        evidence.append("validator_album_id_match")

    return {
        "release_id": f"deezer_album:{album_id}",
        "discovery_identity": {
            "provider": "deezer",
            "deezer_album_id": album_id,
            "artist": row.get("artist"),
            "title": row.get("title"),
            "highest_lifecycle_state": row.get("highest_state"),
        },
        "archive_identity": {
            "folder": archive_folder,
            "manifest_hash": _log_manifest_hash(validation.get("validation_log_path")),
        },
        "identity_confidence": confidence,
        "evidence": sorted(set(evidence)),
        "sources": row.get("sources", []),
        "validation": {
            "available": bool(validation.get("available")),
            "validated_at": validation.get("validated_at"),
            "track_count": validation.get("track_count"),
            "integrity_status": validation.get("integrity_status"),
            "deezer_verification_status": validation.get("deezer_verification_status"),
            "validation_log_path": validation.get("validation_log_path"),
        },
    }


def _candidate_index(albums: list[dict[str, Any]]) -> dict[tuple[str, str], list[dict[str, Any]]]:
    index: dict[tuple[str, str], list[dict[str, Any]]] = {}
    for row in albums:
        key = (
            normalize_identity_text(row.get("artist")),
            normalize_identity_text(row.get("title")),
        )
        if key[0] and key[1]:
            index.setdefault(key, []).append(row)
    return index


def _candidate_from_folder(
    parsed_folder: dict[str, str | None],
    candidates_by_artist_title: dict[tuple[str, str], list[dict[str, Any]]],
) -> list[dict[str, Any]]:
    key = (
        normalize_identity_text(parsed_folder.get("artist")),
        normalize_identity_text(parsed_folder.get("title")),
    )
    rows = candidates_by_artist_title.get(key, [])
    return [
        {
            "deezer_album_id": str(row.get("album_id")),
            "artist": row.get("artist"),
            "title": row.get("title"),
            "confidence": "MEDIUM",
            "evidence": ["normalized_artist_title_match"],
        }
        for row in rows[:10]
    ]


def _unresolved_from_log(
    item: dict[str, Any],
    candidates_by_artist_title: dict[tuple[str, str], list[dict[str, Any]]],
) -> dict[str, Any]:
    path = item.get("path")
    parsed_log = parse_validation_log(Path(path)) if path else None
    folder = item.get("folder") or (parsed_log or {}).get("folder")
    parsed_folder = split_archive_folder(folder)
    candidates = _candidate_from_folder(parsed_folder, candidates_by_artist_title)
    reason = item.get("reason") or "unresolved"

    if parsed_log and not parsed_log.get("album_id"):
        missing = parsed_log.get("completeness", {}).get("missing_album_id_tracks")
        tracks = parsed_log.get("track_count")
        if missing == tracks:
            reason = "all_tracks_missing_album_id"

    return {
        "path": path,
        "folder": folder,
        "parsed_folder": parsed_folder,
        "reason": reason,
        "identity_confidence": "MEDIUM" if candidates else "UNKNOWN",
        "candidates": candidates,
        "validation": {
            "validated_at": (parsed_log or {}).get("validated_at"),
            "track_count": (parsed_log or {}).get("track_count"),
            "manifest_hash": _log_manifest_hash(path),
            "missing_album_id_tracks": (parsed_log or {}).get("completeness", {}).get(
                "missing_album_id_tracks"
            ),
            "hashes_count": (parsed_log or {}).get("hashes_count"),
        },
    }


def build_identity_registry(
    lifecycle_registry: dict[str, Any],
    *,
    generated_at: str | None = None,
) -> dict[str, Any]:
    albums = lifecycle_registry.get("albums", [])
    releases = [_release_from_lifecycle(row) for row in albums]
    candidates_by_artist_title = _candidate_index(albums)
    unresolved = [
        _unresolved_from_log(item, candidates_by_artist_title)
        for item in lifecycle_registry.get("unmatched_validation_logs", [])
    ]

    counts = Counter(item["identity_confidence"] for item in releases)
    unresolved_candidate_counts = Counter(item["identity_confidence"] for item in unresolved)
    summary = {
        "total_releases": len(releases),
        "confidence_counts": {level: counts.get(level, 0) for level in CONFIDENCE_ORDER},
        "unresolved_validator_logs": len(unresolved),
        "unresolved_with_candidates": unresolved_candidate_counts.get("MEDIUM", 0),
        "unresolved_without_candidates": unresolved_candidate_counts.get("UNKNOWN", 0),
    }

    return {
        "schema": 1,
        "generated_at": generated_at or datetime.now().isoformat(timespec="seconds"),
        "source_registry_generated_at": lifecycle_registry.get("generated_at"),
        "summary": summary,
        "releases": releases,
        "unresolved": unresolved,
    }


def write_identity_registry(registry: dict[str, Any], path: Path) -> None:
    text = json.dumps(registry, ensure_ascii=False, indent=2, sort_keys=True) + "\n"
    atomic_write_text(path, text)


def render_identity_resolution_report(registry: dict[str, Any]) -> str:
    summary = registry["summary"]
    total = summary["total_releases"]
    lines = [
        "# Identity Resolution Report",
        "",
        f"Generated: {registry['generated_at']}",
        "",
        "This report is derived from lifecycle and validator evidence. The filesystem remains source of truth.",
        "",
        "## Summary",
        "",
        f"- Total releases: `{total}`",
        f"- High confidence matches: `{summary['confidence_counts']['HIGH']}`",
        f"- Medium confidence matches: `{summary['confidence_counts']['MEDIUM']}`",
        f"- Low confidence matches: `{summary['confidence_counts']['LOW']}`",
        f"- Unknown confidence releases: `{summary['confidence_counts']['UNKNOWN']}`",
        f"- Unresolved validator logs: `{summary['unresolved_validator_logs']}`",
        f"- Unresolved logs with review candidates: `{summary['unresolved_with_candidates']}`",
        "",
        "## Confidence Counts",
        "",
        "| Confidence | Releases | Percent |",
        "| --- | ---: | ---: |",
    ]
    for level in CONFIDENCE_ORDER:
        count = summary["confidence_counts"].get(level, 0)
        lines.append(f"| {level} | {count} | {_pct(count, total)} |")

    lines.extend(
        [
            "",
            "## High Confidence Examples",
            "",
            "| Release ID | Album ID | Artist | Title | Archive folder | Evidence |",
            "| --- | --- | --- | --- | --- | --- |",
        ]
    )
    high = [row for row in registry["releases"] if row["identity_confidence"] == "HIGH"]
    for row in high[:50]:
        discovery = row["discovery_identity"]
        archive = row["archive_identity"]
        lines.append(
            f"| `{_escape(row['release_id'])}` | `{_escape(discovery.get('deezer_album_id'))}` | "
            f"{_escape(discovery.get('artist'))} | {_escape(discovery.get('title'))} | "
            f"{_escape(archive.get('folder'))} | {_escape(', '.join(row.get('evidence', [])))} |"
        )

    return "\n".join(lines) + "\n"


def render_unresolved_identity_report(registry: dict[str, Any]) -> str:
    unresolved = registry.get("unresolved", [])
    lines = [
        "# Unresolved Identity Report",
        "",
        f"Generated: {registry['generated_at']}",
        "",
        f"Unresolved validator logs: `{len(unresolved)}`",
        "",
        "## Reasons",
        "",
        "| Reason | Logs |",
        "| --- | ---: |",
    ]
    for reason, count in Counter(item.get("reason", "unknown") for item in unresolved).most_common():
        lines.append(f"| {_escape(reason)} | {count} |")

    lines.extend(
        [
            "",
            "## Logs",
            "",
            "| Folder | Reason | Confidence | Track count | Missing ALBUM_ID tracks | Candidates | Path |",
            "| --- | --- | --- | ---: | ---: | --- | --- |",
        ]
    )
    for item in unresolved[:200]:
        candidates = ", ".join(
            f"{candidate['artist']} - {candidate['title']} ({candidate['deezer_album_id']})"
            for candidate in item.get("candidates", [])[:3]
        )
        validation = item.get("validation", {})
        lines.append(
            f"| {_escape(item.get('folder'))} | {_escape(item.get('reason'))} | "
            f"{_escape(item.get('identity_confidence'))} | {validation.get('track_count') or ''} | "
            f"{validation.get('missing_album_id_tracks') or ''} | {_escape(candidates)} | "
            f"`{_escape(item.get('path'))}` |"
        )
    return "\n".join(lines) + "\n"


def write_identity_reports(registry: dict[str, Any], reports_dir: Path) -> None:
    reports_dir.mkdir(parents=True, exist_ok=True)
    atomic_write_text(reports_dir / "identity_resolution_report.md", render_identity_resolution_report(registry))
    atomic_write_text(reports_dir / "unresolved_identity_report.md", render_unresolved_identity_report(registry))


def _pct(count: int, total: int) -> str:
    if total == 0:
        return "0.0%"
    return f"{(count / total) * 100:.1f}%"


def _escape(value: Any) -> str:
    return str(value or "").replace("|", "\\|").replace("\n", " ").strip()
