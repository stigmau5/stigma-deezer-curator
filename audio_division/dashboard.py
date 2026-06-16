from __future__ import annotations

import json
from pathlib import Path
from typing import Any


def load_json(path: Path) -> dict[str, Any]:
    if not path.exists():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}
    return data if isinstance(data, dict) else {}


def load_dashboard_sources(data_dir: Path) -> dict[str, dict[str, Any]]:
    return {
        "lifecycle": load_json(data_dir / "lifecycle_registry.json"),
        "identity": load_json(data_dir / "identity_registry.json"),
        "metadata": load_json(data_dir / "metadata_cache.json"),
    }


def dashboard_summary(data_dir: Path) -> dict[str, Any]:
    sources = load_dashboard_sources(data_dir)
    return compute_dashboard_summary(
        sources["lifecycle"],
        sources["identity"],
        sources["metadata"],
    )


def compute_dashboard_summary(
    lifecycle: dict[str, Any],
    identity: dict[str, Any],
    metadata: dict[str, Any],
) -> dict[str, Any]:
    lifecycle_summary = lifecycle.get("summary", {})
    state_counts = lifecycle_summary.get("state_evidence_counts", {})
    gaps = lifecycle_summary.get("gaps", {})
    total_albums = lifecycle_summary.get("total_albums", len(lifecycle.get("albums", [])))

    metadata_summary = metadata.get("summary", {})
    albums_cached = metadata_summary.get("albums_with_metadata", len(metadata.get("albums", {})))
    artists_cached = metadata_summary.get("artists_cached", len(metadata.get("artists", {})))
    tracks_cached = metadata_summary.get("tracks_cached", len(metadata.get("tracks", {})))
    metadata_coverage = metadata_summary.get("coverage_percent", _ratio(albums_cached, total_albums))

    identity_summary = identity.get("summary", {})
    identity_counts = identity_summary.get("confidence_counts", {})
    validation_evidence = lifecycle.get("validation_evidence_summary", {})
    validated = state_counts.get("VALIDATED", 0)
    validation_coverage = _ratio(validated, total_albums)

    archive_strength = _archive_strength_score(total_albums, identity_counts.get("HIGH", 0), validated, metadata_coverage)

    return {
        "archive_overview": {
            "albums": total_albums,
            "artists": artists_cached,
            "cached_tracks": tracks_cached,
            "archive_strength": archive_strength,
        },
        "lifecycle": {
            "discovered": state_counts.get("DISCOVERED", 0),
            "attempted": state_counts.get("ATTEMPTED", 0),
            "shipped": state_counts.get("SHIPPED", 0),
            "validated": validated,
            "confirmed": state_counts.get("CONFIRMED", 0),
        },
        "identity": {
            "high_confidence": identity_counts.get("HIGH", 0),
            "medium_confidence": identity_counts.get("MEDIUM", 0),
            "unknown": identity_counts.get("UNKNOWN", 0),
            "unresolved_logs": identity_summary.get("unresolved_validator_logs", 0),
        },
        "metadata": {
            "albums_cached": albums_cached,
            "artists_cached": artists_cached,
            "tracks_cached": tracks_cached,
            "coverage_percent": metadata_coverage,
        },
        "validation": {
            "coverage_percent": validation_coverage,
            "evidence_count": validation_evidence.get("albums_with_evidence", validated),
        },
        "archive_health": {
            "shipped_not_validated": gaps.get("shipped_not_validated", 0),
            "attempted_not_shipped": max(state_counts.get("ATTEMPTED", 0) - state_counts.get("SHIPPED", 0), 0),
            "confirmed_not_validated": gaps.get("confirmed_not_validated", 0),
        },
    }


def _archive_strength_score(total: int, high_identity: int, validated: int, metadata_coverage: float) -> float:
    categories = [
        1.0 if total else 0.0,
        _ratio(high_identity, total),
        _ratio(validated, total),
        0.0,
        metadata_coverage,
    ]
    return round(sum(categories) / len(categories), 4)


def _ratio(count: int, total: int) -> float:
    if total == 0:
        return 0.0
    return round(count / total, 4)
