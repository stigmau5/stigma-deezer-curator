from __future__ import annotations

from pathlib import Path
from typing import Any


PRESENTATION_SECTIONS = ("overview", "artwork", "archive_status", "metadata", "identity")


def album_presentation(details: dict[str, Any]) -> dict[str, Any]:
    if not details:
        return {"sections": {}, "thumbnail": thumbnail_info({})}

    status = details.get("album_status", {})
    status_items = status.get("items", {})
    readiness = details.get("archive_readiness", {})
    metadata_detail = details.get("metadata_detail", {})
    cached_fields = metadata_detail.get("cached_fields", {})
    missing_fields = metadata_detail.get("missing_fields", [])

    sections = {
        "overview": [
            ("Album title", details.get("title") or ""),
            ("Artist", details.get("artist") or ""),
            ("Year", details.get("year") or ""),
            ("Record type", details.get("record_type") or ""),
        ],
        "artwork": [
            ("Artwork status", status_items.get("artwork", "Unknown")),
            ("Artwork source", _artwork_source(details)),
        ],
        "archive_status": [
            ("Validation", status_items.get("validation", "Unknown")),
            ("Documentation", _documentation_status(status_items)),
            ("Readiness", readiness.get("state", "UNKNOWN")),
            ("Health", f"{status.get('health_percent', 0)}%"),
            ("Reason", readiness.get("reason", "")),
        ],
        "metadata": [
            ("Label", details.get("label") or ""),
            ("Genre", ", ".join(details.get("genres", []))),
            ("Release date", details.get("release_date") or ""),
            ("Track count", details.get("track_count") or ""),
            ("Metadata status", details.get("metadata_status") or "UNKNOWN"),
            ("Cached fields", _field_list(cached_fields, True)),
            ("Missing fields", ", ".join(missing_fields)),
        ],
        "identity": [
            ("Album ID", details.get("album_id") or ""),
            ("Identity confidence", details.get("identity_confidence") or "UNKNOWN"),
            ("Archive path confidence", details.get("archive_path_confidence") or "UNKNOWN"),
            ("Archive folder", details.get("archive_folder") or ""),
            ("Archive path", details.get("archive_path") or ""),
        ],
    }
    return {"sections": sections, "thumbnail": thumbnail_info(details)}


def thumbnail_info(details: dict[str, Any]) -> dict[str, Any]:
    artwork = details.get("artwork", {}) if isinstance(details.get("artwork"), dict) else {}
    local = artwork.get("local")
    urls = artwork.get("urls", {}) if isinstance(artwork.get("urls"), dict) else {}
    local_path = Path(local) if isinstance(local, (str, Path)) and local else None
    if local_path and local_path.exists() and local_path.is_file():
        return {
            "status": "Present",
            "source": "local",
            "path": str(local_path),
            "url": "",
            "display": local_path.name,
        }

    url = urls.get("medium") or urls.get("big") or urls.get("xl") or urls.get("small") or ""
    if url:
        return {
            "status": "Present",
            "source": "metadata_url",
            "path": "",
            "url": url,
            "display": url,
        }

    return {"status": "Missing", "source": "none", "path": "", "url": "", "display": "No artwork available"}


def _documentation_status(status_items: dict[str, Any]) -> str:
    docs = [status_items.get("nfo", "Unknown"), status_items.get("sfv", "Unknown")]
    if all(item == "Present" for item in docs):
        return "Present"
    if any(item == "Missing" for item in docs):
        return "Missing"
    return "Unknown"


def _field_list(fields: dict[str, bool], expected: bool) -> str:
    return ", ".join(field for field, present in fields.items() if present is expected)


def _artwork_source(details: dict[str, Any]) -> str:
    info = thumbnail_info(details)
    if info["source"] == "local":
        return f"Local: {info['display']}"
    if info["source"] == "metadata_url":
        return "Metadata URL"
    return "None"
