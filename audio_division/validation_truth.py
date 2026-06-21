from __future__ import annotations

from pathlib import Path
from typing import Any


SOURCE_ARCHIVE_MARKER = "archive_marker"
SOURCE_VALIDATED_INDEX = "validated_index"
SOURCE_IDENTITY_REGISTRY = "identity_registry"
SOURCE_LIFECYCLE_REGISTRY = "lifecycle_registry"
SOURCE_VALIDATOR_LOG = "validator_log"
SOURCE_MISSING = "missing"

CONFIDENCE_HIGH = "HIGH"
CONFIDENCE_MEDIUM = "MEDIUM"
CONFIDENCE_LOW = "LOW"
CONFIDENCE_NONE = "NONE"

SOURCE_RANK = {
    SOURCE_ARCHIVE_MARKER: 50,
    SOURCE_VALIDATED_INDEX: 40,
    SOURCE_IDENTITY_REGISTRY: 30,
    SOURCE_LIFECYCLE_REGISTRY: 20,
    SOURCE_VALIDATOR_LOG: 10,
    SOURCE_MISSING: 0,
}


def validation_evidence_from_identity_release(release: dict[str, Any] | None) -> dict[str, Any]:
    release = release or {}
    validation = release.get("validation") if isinstance(release.get("validation"), dict) else {}
    if not validation.get("available"):
        return {}
    return {
        "identity_registry": True,
        "validation_source": SOURCE_IDENTITY_REGISTRY,
        "validation_confidence": CONFIDENCE_HIGH if release.get("identity_confidence") == "HIGH" else CONFIDENCE_MEDIUM,
        "validation_reason": "Identity Registry contains validation evidence for this release.",
        "validation_log_path": validation.get("validation_log_path") or "",
        "validated_at": validation.get("validated_at"),
        "track_count": validation.get("track_count"),
    }


def validation_evidence_from_lifecycle_row(row: dict[str, Any] | None) -> dict[str, Any]:
    row = row or {}
    states = row.get("states") if isinstance(row.get("states"), dict) else {}
    evidence = row.get("validation_evidence") if isinstance(row.get("validation_evidence"), dict) else {}
    out: dict[str, Any] = {}
    available_evidence = set(evidence.get("available_evidence") or [])
    if evidence.get("available") and "validated_index" in available_evidence:
        out.update(
            {
                "validated_index": True,
                "validation_source": SOURCE_VALIDATED_INDEX,
                "validation_confidence": CONFIDENCE_HIGH,
                "validation_reason": "Album ID is present in validated_albums.json.",
                "validated_at": evidence.get("validated_at"),
                "track_count": evidence.get("track_count"),
            }
        )
    elif evidence.get("available") or states.get("validated"):
        out.update(
            {
                "lifecycle_registry": True,
                "validation_source": SOURCE_LIFECYCLE_REGISTRY,
                "validation_confidence": CONFIDENCE_MEDIUM,
                "validation_reason": "Lifecycle Registry marks this album as validated.",
                "validated_at": evidence.get("validated_at") or row.get("timestamps", {}).get("validated_at"),
                "track_count": evidence.get("track_count") or row.get("details", {}).get("validated_tracks"),
            }
        )
    if evidence.get("validation_log_path"):
        out["validator_log"] = True
        out["validation_log_path"] = evidence.get("validation_log_path")
    return out


def validation_evidence_from_validated_index(album_id: Any, validated_index: dict[str, Any] | None) -> dict[str, Any]:
    album_id = str(album_id or "").strip()
    if not album_id or not isinstance(validated_index, dict) or album_id not in validated_index:
        return {}
    row = validated_index.get(album_id) if isinstance(validated_index.get(album_id), dict) else {}
    return {
        "validated_index": True,
        "validation_source": SOURCE_VALIDATED_INDEX,
        "validation_confidence": CONFIDENCE_HIGH,
        "validation_reason": "Album ID is present in validated_albums.json.",
        "validated_at": row.get("validated_at"),
        "track_count": row.get("tracks") or row.get("track_count"),
        "folder": row.get("folder"),
    }


def validation_evidence_from_validator_log(path: str | Path | None) -> dict[str, Any]:
    if not path:
        return {}
    return {
        "validator_log": True,
        "validation_source": SOURCE_VALIDATOR_LOG,
        "validation_confidence": CONFIDENCE_LOW,
        "validation_reason": "Validator log exists but no stronger album identity evidence was supplied.",
        "validation_log_path": str(path),
    }


def merge_validation_evidence(*items: dict[str, Any] | None) -> dict[str, Any]:
    merged: dict[str, Any] = {}
    for item in items:
        if not item:
            continue
        for key, value in item.items():
            if key in {"validation_source", "validation_confidence", "validation_reason"} and key in merged:
                continue
            merged[key] = value
    return merged


def source_rank(source: str) -> int:
    return SOURCE_RANK.get(source, 0)
