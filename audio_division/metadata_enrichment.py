from __future__ import annotations

import argparse
import json
import re
from copy import deepcopy
from datetime import datetime
from pathlib import Path
from typing import Any

from audio_division.metadata_status import album_metadata_status
from curator.atomic import atomic_write_text

ENRICHMENT_SOURCE = "identity_registry"


def enrich_metadata(
    identity_registry: dict[str, Any],
    lifecycle_registry: dict[str, Any],
    metadata_cache: dict[str, Any],
    *,
    generated_at: str | None = None,
) -> tuple[dict[str, Any], dict[str, Any]]:
    """Rebuild the identity-derived portion of a metadata cache in memory."""
    generated_at = generated_at or datetime.now().isoformat(timespec="seconds")
    cache = _normalise_cache(metadata_cache)
    cache["albums"] = {
        str(album_id): album
        for album_id, album in cache["albums"].items()
        if not _is_enriched_album(album)
    }

    identities = _identity_by_album_id(identity_registry)
    lifecycle = _lifecycle_by_album_id(lifecycle_registry)
    album_ids = sorted(set(identities) | set(lifecycle), key=_album_id_sort_key)
    candidates = [
        album_id
        for album_id in album_ids
        if album_metadata_status(album_id, cache)["state"] == "AVAILABLE_NOT_CACHED"
    ]

    enriched_ids: list[str] = []
    missing_ids: list[str] = []
    for album_id in candidates:
        release = identities.get(album_id)
        if not release:
            missing_ids.append(album_id)
            continue
        cache["albums"][album_id] = metadata_from_identity(
            album_id,
            release,
            lifecycle.get(album_id, {}),
            enriched_at=generated_at,
        )
        enriched_ids.append(album_id)

    evaluated = len(candidates)
    enriched = len(enriched_ids)
    cache["generated_at"] = generated_at
    cache["summary"] = _cache_summary(cache, len(album_ids))
    cache["enrichment"] = {
        "source": ENRICHMENT_SOURCE,
        "generated_at": generated_at,
        "albums_evaluated": evaluated,
        "albums_enriched": enriched,
        "albums_missing_metadata": len(missing_ids),
        "coverage_percentage": _percentage(enriched, evaluated),
    }
    result = {
        **cache["enrichment"],
        "enriched_album_ids": enriched_ids,
        "missing_album_ids": missing_ids,
    }
    return cache, result


def metadata_from_identity(
    album_id: str,
    release: dict[str, Any],
    lifecycle: dict[str, Any] | None = None,
    *,
    enriched_at: str | None = None,
) -> dict[str, Any]:
    discovery = release.get("discovery_identity", {})
    lifecycle = lifecycle or {}
    validation = release.get("validation", {})
    details = lifecycle.get("details", {})
    artist = str(discovery.get("artist") or lifecycle.get("artist") or "").strip()
    title = str(discovery.get("title") or lifecycle.get("title") or "").strip()
    genres = _genres(discovery.get("genres") or release.get("genres"))
    release_date = str(
        discovery.get("release_date")
        or release.get("release_date")
        or _archive_year(release)
        or ""
    )
    track_count = _positive_int(
        validation.get("track_count")
        or details.get("validated_tracks")
        or lifecycle.get("validation_evidence", {}).get("track_count")
    )
    contributors = _contributors(discovery.get("contributors") or release.get("contributors"), artist)
    genre = genres[0]["name"] if genres else ""
    return {
        "deezer_album_id": str(album_id),
        "title": title,
        "genre": genre,
        "genres": genres,
        "label": str(discovery.get("label") or release.get("label") or "").strip(),
        "release_date": release_date,
        "year": _year(release_date),
        "contributors": contributors,
        "artist": {"name": artist, "role": "Main"} if artist else None,
        "track_count": track_count,
        "record_type": str(discovery.get("record_type") or release.get("record_type") or "album"),
        "upc": str(discovery.get("upc") or release.get("upc") or "").strip(),
        "duration": "",
        "covers": {},
        "track_ids": [],
        "metadata_source": ENRICHMENT_SOURCE,
        "enriched_at": enriched_at or datetime.now().isoformat(timespec="seconds"),
    }


def rebuild_metadata_enrichment(
    data_dir: Path,
    reports_dir: Path,
    *,
    cache_path: Path | None = None,
) -> dict[str, Any]:
    """Rebuild local enrichment data without touching archive files or the network."""
    data_dir = Path(data_dir)
    reports_dir = Path(reports_dir)
    cache_path = Path(cache_path) if cache_path else data_dir / "metadata_cache.json"
    cache, result = enrich_metadata(
        _load_json(data_dir / "identity_registry.json"),
        _load_json(data_dir / "lifecycle_registry.json"),
        _load_json(cache_path),
    )
    atomic_write_text(cache_path, json.dumps(cache, ensure_ascii=False, indent=2, sort_keys=True) + "\n")
    reports_dir.mkdir(parents=True, exist_ok=True)
    atomic_write_text(reports_dir / "metadata_enrichment_report.md", render_enrichment_report(result))
    return result


def render_enrichment_report(result: dict[str, Any]) -> str:
    return "\n".join(
        [
            "# Metadata Enrichment Report",
            "",
            "Identity-derived metadata is cached locally. No archive files, queues, or network providers are modified.",
            "",
            f"- Albums evaluated: `{result.get('albums_evaluated', 0)}`",
            f"- Albums enriched: `{result.get('albums_enriched', 0)}`",
            f"- Albums missing metadata: `{result.get('albums_missing_metadata', 0)}`",
            f"- Coverage percentage: `{float(result.get('coverage_percentage', 0.0)):.1f}%`",
            "",
        ]
    )


def _normalise_cache(metadata_cache: dict[str, Any]) -> dict[str, Any]:
    cache = deepcopy(metadata_cache) if isinstance(metadata_cache, dict) else {}
    cache.setdefault("schema", 1)
    cache.setdefault("source", "deezer")
    for key in ("albums", "artists", "tracks", "errors"):
        if not isinstance(cache.get(key), dict):
            cache[key] = {}
    return cache


def _identity_by_album_id(registry: dict[str, Any]) -> dict[str, dict[str, Any]]:
    releases = registry.get("releases", [])
    if isinstance(releases, dict):
        releases = releases.values()
    return {
        str(release.get("discovery_identity", {}).get("deezer_album_id")): release
        for release in releases
        if isinstance(release, dict) and release.get("discovery_identity", {}).get("deezer_album_id")
    }


def _lifecycle_by_album_id(registry: dict[str, Any]) -> dict[str, dict[str, Any]]:
    albums = registry.get("albums", [])
    if isinstance(albums, dict):
        albums = albums.values()
    return {
        str(album.get("album_id")): album
        for album in albums
        if isinstance(album, dict) and album.get("album_id")
    }


def _is_enriched_album(album: Any) -> bool:
    return isinstance(album, dict) and album.get("metadata_source") == ENRICHMENT_SOURCE


def _genres(value: Any) -> list[dict[str, Any]]:
    if isinstance(value, str):
        value = [item.strip() for item in value.split(",")]
    if not isinstance(value, list):
        return []
    result = []
    for item in value:
        if isinstance(item, dict):
            name = str(item.get("name") or "").strip()
            genre_id = item.get("id")
        else:
            name = str(item or "").strip()
            genre_id = None
        if name:
            result.append({"id": genre_id, "name": name})
    return result


def _contributors(value: Any, artist: str) -> list[dict[str, Any]]:
    if isinstance(value, dict):
        value = [value]
    result = []
    for item in value if isinstance(value, list) else []:
        if isinstance(item, dict):
            name = str(item.get("name") or "").strip()
            role = item.get("role") or "Contributor"
        else:
            name = str(item or "").strip()
            role = "Contributor"
        if name:
            result.append({"name": name, "role": role})
    if not result and artist:
        result.append({"name": artist, "role": "Main"})
    return result


def _archive_year(release: dict[str, Any]) -> str:
    folder = str(release.get("archive_identity", {}).get("folder") or "")
    years = re.findall(r"(?<!\d)(?:19|20)\d{2}(?!\d)", folder)
    return years[-1] if years else ""


def _year(release_date: str) -> int | None:
    match = re.match(r"((?:19|20)\d{2})", str(release_date or ""))
    return int(match.group(1)) if match else None


def _positive_int(value: Any) -> int:
    try:
        return max(int(value or 0), 0)
    except (TypeError, ValueError):
        return 0


def _percentage(count: int, total: int) -> float:
    return round((count / total) * 100, 1) if total else 0.0


def _cache_summary(cache: dict[str, Any], total: int) -> dict[str, Any]:
    cached = len(cache.get("albums", {}))
    return {
        "total_lifecycle_albums": total,
        "albums_with_metadata": cached,
        "albums_missing_metadata": max(total - cached, 0),
        "artists_cached": len(cache.get("artists", {})),
        "tracks_cached": len(cache.get("tracks", {})),
        "coverage_percent": round(cached / total, 4) if total else 0.0,
    }


def _album_id_sort_key(value: str) -> tuple[int, int | str]:
    return (0, int(value)) if value.isdigit() else (1, value)


def _load_json(path: Path) -> dict[str, Any]:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return {}
    return value if isinstance(value, dict) else {}


def main() -> int:
    parser = argparse.ArgumentParser(description="Rebuild identity-derived metadata cache entries.")
    parser.add_argument("--data-dir", type=Path, default=Path("data"))
    parser.add_argument("--reports-dir", type=Path, default=Path("reports"))
    args = parser.parse_args()
    result = rebuild_metadata_enrichment(args.data_dir, args.reports_dir)
    print(
        f"Metadata enrichment: {result['albums_enriched']}/{result['albums_evaluated']} albums "
        f"({result['coverage_percentage']:.1f}%)."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
