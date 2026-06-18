from __future__ import annotations

from typing import Any

from audio_division.library import album_archive_operation_target


CAMPAIGNS = (
    ("missing_nfo", "Missing NFO"),
    ("missing_sfv", "Missing SFV"),
    ("missing_validation", "Missing Validation"),
    ("missing_artwork", "Missing Artwork"),
    ("metadata_available_not_cached", "Metadata Available Not Cached"),
)

CAMPAIGN_OPERATIONS = {
    "missing_nfo": "generate_nfo",
    "missing_sfv": "generate_sfv",
    "missing_validation": "validate_album",
}


def campaign_summaries(albums: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [
        {"id": campaign_id, "name": name, "album_count": len(campaign_albums(albums, campaign_id))}
        for campaign_id, name in CAMPAIGNS
    ]


def campaign_albums(albums: list[dict[str, Any]], campaign_id: str) -> list[dict[str, Any]]:
    return [album for album in albums if album_matches_campaign(album, campaign_id)]


def album_matches_campaign(album: dict[str, Any], campaign_id: str) -> bool:
    truth = album.get("album_truth", {})
    items = truth.get("items") or album.get("album_status", {}).get("items", {})
    if campaign_id == "missing_nfo":
        return items.get("nfo") == "Missing"
    if campaign_id == "missing_sfv":
        return items.get("sfv") == "Missing"
    if campaign_id == "missing_validation":
        return items.get("validation") == "Missing"
    if campaign_id == "missing_artwork":
        return items.get("artwork") == "Missing"
    if campaign_id == "metadata_available_not_cached":
        return album.get("metadata_status") == "AVAILABLE_NOT_CACHED" or truth.get("metadata_status") == "AVAILABLE_NOT_CACHED"
    return False


def selected_campaign_targets(
    operation_id: str,
    albums: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    targets = []
    seen: set[str] = set()
    for album in albums:
        key = str(album.get("album_id") or album.get("archive_path") or "")
        if key in seen:
            continue
        target, reason = album_archive_operation_target(album)
        targets.append(
            {
                "album_id": str(album.get("album_id") or ""),
                "artist": album.get("artist", ""),
                "album": album.get("title") or album.get("album") or "",
                "target": target,
                "eligible": bool(target),
                "reason": reason,
                "operation": operation_id,
            }
        )
        seen.add(key)
    return targets
