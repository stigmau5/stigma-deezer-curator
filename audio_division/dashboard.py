from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from audio_division.actions import ACTION_CATEGORIES, action_summary, generate_archive_actions
from audio_division.metadata_status import metadata_coverage as compute_metadata_coverage
from audio_division.operations import operation_summary


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
        "operation_history": load_json(data_dir / "operation_history.json"),
    }


def dashboard_summary(data_dir: Path) -> dict[str, Any]:
    sources = load_dashboard_sources(data_dir)
    readiness = {}
    hub_opportunities = {}
    try:
        from audio_division.library import library_from_data_dir
        from audio_division.opportunities import derive_hub_opportunities, hub_opportunity_summary
        from audio_division.settings import load_audio_division_settings

        settings = load_audio_division_settings(data_dir / "audio_division_settings.json")
        archive_root = settings.get("archive_paths", {}).get("main_archive_root", "")
        library = library_from_data_dir(data_dir, Path(archive_root) if archive_root else None)
        readiness = library.get("archive_readiness_summary", {})
        hub_opportunities = hub_opportunity_summary(derive_hub_opportunities(library))
    except Exception:
        readiness = {}
        hub_opportunities = {}
    return compute_dashboard_summary(
        sources["lifecycle"],
        sources["identity"],
        sources["metadata"],
        sources["operation_history"],
        readiness,
        hub_opportunities,
    )


def compute_dashboard_summary(
    lifecycle: dict[str, Any],
    identity: dict[str, Any],
    metadata: dict[str, Any],
    operation_history: dict[str, Any] | None = None,
    readiness_summary: dict[str, Any] | None = None,
    hub_opportunity_summary_data: dict[str, Any] | None = None,
) -> dict[str, Any]:
    lifecycle_summary = lifecycle.get("summary", {})
    state_counts = lifecycle_summary.get("state_evidence_counts", {})
    gaps = lifecycle_summary.get("gaps", {})
    total_albums = lifecycle_summary.get("total_albums", len(lifecycle.get("albums", [])))

    metadata_summary = metadata.get("summary", {})
    metadata_state_summary = compute_metadata_coverage(lifecycle, metadata)
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
    actions = generate_archive_actions(lifecycle, identity, metadata)
    actions_summary = action_summary(actions)
    operations_summary = operation_summary(actions)
    first_action = actions[0] if actions else {}
    history = (operation_history or {}).get("history", [])
    readiness_counts = (readiness_summary or {}).get("counts", {})
    hub_counts = (hub_opportunity_summary_data or {}).get("by_category", {})

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
            "cached": metadata_state_summary["states"].get("CACHED", 0),
            "available_not_cached": metadata_state_summary["states"].get("AVAILABLE_NOT_CACHED", 0),
            "missing": metadata_state_summary["states"].get("MISSING", 0),
            "unknown": metadata_state_summary["states"].get("UNKNOWN", 0),
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
        "archive_readiness": {
            "archive_ready": readiness_counts.get("ARCHIVE_READY", 0),
            "needs_validation": readiness_counts.get("NEEDS_VALIDATION", 0),
            "needs_documentation": readiness_counts.get("NEEDS_DOCUMENTATION", 0),
            "needs_review": readiness_counts.get("NEEDS_REVIEW", 0),
            "unknown": readiness_counts.get("UNKNOWN", 0),
        },
        "top_opportunities": {
            "needs_validation": hub_counts.get("NEEDS_VALIDATION", 0),
            "needs_documentation": hub_counts.get("NEEDS_DOCUMENTATION", 0),
            "needs_metadata": hub_counts.get("NEEDS_METADATA", 0),
            "needs_review": hub_counts.get("NEEDS_REVIEW", 0),
            "archive_ready": hub_counts.get("ARCHIVE_READY", 0),
            "most_urgent_category": (hub_opportunity_summary_data or {}).get("most_urgent_category", ""),
        },
        "archive_actions": {
            "action_count": actions_summary["total_actions"],
            **{category: actions_summary["by_category"].get(category, 0) for category in ACTION_CATEGORIES},
            "selected_action": first_action,
            "actions": actions,
        },
        "archive_operations": {
            "operation_count": operations_summary["total_operations"],
            **operations_summary["candidate_counts"],
        },
        "recent_operations": {
            "operation_count": len(history),
            "items": history[:5],
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
