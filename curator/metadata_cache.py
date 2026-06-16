from __future__ import annotations

import argparse
import json
import time
from collections import Counter
from datetime import datetime
from pathlib import Path
from typing import Any, Callable

import requests

from curator.atomic import atomic_write_text
from curator.lifecycle import load_json_file

DEEZER_API = "https://api.deezer.com"
REQUEST_DELAY = 0.1


def empty_cache(generated_at: str | None = None) -> dict[str, Any]:
    return {
        "schema": 1,
        "generated_at": generated_at or datetime.now().isoformat(timespec="seconds"),
        "source": "deezer",
        "albums": {},
        "artists": {},
        "tracks": {},
        "errors": {},
    }


def load_cache(path: Path) -> dict[str, Any]:
    if not path.exists():
        return empty_cache()
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return empty_cache()
    if not isinstance(data, dict):
        return empty_cache()
    for key in ("albums", "artists", "tracks", "errors"):
        if not isinstance(data.get(key), dict):
            data[key] = {}
    data.setdefault("schema", 1)
    data.setdefault("source", "deezer")
    return data


def album_ids_from_registries(
    lifecycle_registry: dict[str, Any],
    identity_registry: dict[str, Any],
) -> list[str]:
    ids = {str(row.get("album_id")) for row in lifecycle_registry.get("albums", []) if row.get("album_id")}
    ids.update(
        str(row.get("discovery_identity", {}).get("deezer_album_id"))
        for row in identity_registry.get("releases", [])
        if row.get("discovery_identity", {}).get("deezer_album_id")
    )
    return sorted(ids, key=lambda value: int(value) if value.isdigit() else value)


def fetch_json(url: str, *, get: Callable[..., Any] = requests.get) -> dict[str, Any] | None:
    try:
        response = get(url, timeout=10)
        response.raise_for_status()
        data = response.json()
    except Exception:
        return None
    return data if isinstance(data, dict) and not data.get("error") else None


def fetch_deezer_album(album_id: str, *, get: Callable[..., Any] = requests.get) -> dict[str, Any] | None:
    return fetch_json(f"{DEEZER_API}/album/{album_id}", get=get)


def fetch_deezer_artist(artist_id: str, *, get: Callable[..., Any] = requests.get) -> dict[str, Any] | None:
    return fetch_json(f"{DEEZER_API}/artist/{artist_id}", get=get)


def fetch_deezer_track(track_id: str, *, get: Callable[..., Any] = requests.get) -> dict[str, Any] | None:
    return fetch_json(f"{DEEZER_API}/track/{track_id}", get=get)


def parse_album_payload(data: dict[str, Any]) -> dict[str, Any]:
    release_date = data.get("release_date")
    contributors = [_parse_contributor(item) for item in data.get("contributors", []) if isinstance(item, dict)]
    genres = [
        {"id": item.get("id"), "name": item.get("name")}
        for item in data.get("genres", {}).get("data", [])
        if isinstance(item, dict)
    ]
    tracks = data.get("tracks", {}).get("data", [])
    track_ids = [str(item.get("id")) for item in tracks if isinstance(item, dict) and item.get("id")]
    artist = data.get("artist") if isinstance(data.get("artist"), dict) else {}
    return {
        "deezer_album_id": str(data.get("id")),
        "title": data.get("title"),
        "release_date": release_date,
        "year": _year(release_date),
        "upc": data.get("upc"),
        "label": data.get("label"),
        "genres": genres,
        "contributors": contributors,
        "artist": _parse_contributor(artist) if artist else None,
        "track_count": data.get("nb_tracks"),
        "duration": data.get("duration"),
        "record_type": data.get("record_type"),
        "explicit": {
            "lyrics": data.get("explicit_lyrics"),
            "content_lyrics": data.get("explicit_content_lyrics"),
            "content_cover": data.get("explicit_content_cover"),
        },
        "covers": {
            "small": data.get("cover_small"),
            "medium": data.get("cover_medium"),
            "big": data.get("cover_big"),
            "xl": data.get("cover_xl"),
        },
        "cover_identity": data.get("md5_image"),
        "track_ids": track_ids,
        "fetched_at": datetime.now().isoformat(timespec="seconds"),
    }


def parse_artist_payload(data: dict[str, Any]) -> dict[str, Any]:
    return {
        "deezer_artist_id": str(data.get("id")),
        "name": data.get("name"),
        "album_count": data.get("nb_album"),
        "fan_count": data.get("nb_fan"),
        "pictures": {
            "small": data.get("picture_small"),
            "medium": data.get("picture_medium"),
            "big": data.get("picture_big"),
            "xl": data.get("picture_xl"),
        },
        "fetched_at": datetime.now().isoformat(timespec="seconds"),
    }


def parse_track_payload(data: dict[str, Any]) -> dict[str, Any]:
    contributors = [_parse_contributor(item) for item in data.get("contributors", []) if isinstance(item, dict)]
    return {
        "deezer_track_id": str(data.get("id")),
        "title": data.get("title"),
        "isrc": data.get("isrc"),
        "duration": data.get("duration"),
        "track_number": data.get("track_position"),
        "disc_number": data.get("disk_number"),
        "contributors": contributors,
        "artist": _parse_contributor(data.get("artist", {})) if isinstance(data.get("artist"), dict) else None,
        "explicit": {
            "lyrics": data.get("explicit_lyrics"),
            "content_lyrics": data.get("explicit_content_lyrics"),
            "content_cover": data.get("explicit_content_cover"),
        },
        "fetched_at": datetime.now().isoformat(timespec="seconds"),
    }


def build_metadata_cache(
    lifecycle_registry: dict[str, Any],
    identity_registry: dict[str, Any],
    *,
    existing_cache: dict[str, Any] | None = None,
    limit: int | None = None,
    get: Callable[..., Any] = requests.get,
    sleep: Callable[[float], None] = time.sleep,
) -> dict[str, Any]:
    cache = existing_cache or empty_cache()
    cache["generated_at"] = datetime.now().isoformat(timespec="seconds")
    ids = album_ids_from_registries(lifecycle_registry, identity_registry)
    missing = [
        album_id
        for album_id in ids
        if album_id not in cache["albums"] and album_id not in cache["errors"]
    ]
    selected = missing[:limit] if limit is not None else missing

    for album_id in selected:
        payload = fetch_deezer_album(album_id, get=get)
        if not payload:
            cache["errors"][album_id] = {"type": "album_fetch_failed", "fetched_at": cache["generated_at"]}
            continue

        album = parse_album_payload(payload)
        cache["albums"][album_id] = album

        artist_ids = {
            str(item.get("deezer_artist_id"))
            for item in [album.get("artist"), *album.get("contributors", [])]
            if isinstance(item, dict) and item.get("deezer_artist_id")
        }
        for artist_id in sorted(artist_ids):
            if artist_id in cache["artists"]:
                continue
            artist_payload = fetch_deezer_artist(artist_id, get=get)
            if artist_payload:
                cache["artists"][artist_id] = parse_artist_payload(artist_payload)
            sleep(REQUEST_DELAY)

        for track_id in album.get("track_ids", []):
            if track_id in cache["tracks"]:
                continue
            track_payload = fetch_deezer_track(track_id, get=get)
            if track_payload:
                cache["tracks"][track_id] = parse_track_payload(track_payload)
            sleep(REQUEST_DELAY)

        sleep(REQUEST_DELAY)

    cache["summary"] = metadata_coverage(cache, len(ids))
    return cache


def metadata_coverage(cache: dict[str, Any], total_albums: int) -> dict[str, Any]:
    albums_cached = len(cache.get("albums", {}))
    return {
        "total_lifecycle_albums": total_albums,
        "albums_with_metadata": albums_cached,
        "albums_missing_metadata": max(total_albums - albums_cached, 0),
        "artists_cached": len(cache.get("artists", {})),
        "tracks_cached": len(cache.get("tracks", {})),
        "coverage_percent": _pct_float(albums_cached, total_albums),
    }


def metadata_quality(cache: dict[str, Any]) -> dict[str, int]:
    albums = list(cache.get("albums", {}).values())
    tracks = list(cache.get("tracks", {}).values())
    return {
        "albums_missing_upc": sum(1 for item in albums if not item.get("upc")),
        "albums_missing_release_date": sum(1 for item in albums if not item.get("release_date")),
        "albums_missing_genres": sum(1 for item in albums if not item.get("genres")),
        "albums_missing_label": sum(1 for item in albums if not item.get("label")),
        "albums_missing_contributors": sum(1 for item in albums if not item.get("contributors")),
        "tracks_missing_isrc": sum(1 for item in tracks if not item.get("isrc")),
    }


def collection_summary(cache: dict[str, Any]) -> dict[str, Any]:
    albums = list(cache.get("albums", {}).values())
    years = Counter(str(item.get("year")) for item in albums if item.get("year"))
    labels = Counter(item.get("label") for item in albums if item.get("label"))
    genres = Counter(
        genre.get("name")
        for item in albums
        for genre in item.get("genres", [])
        if isinstance(genre, dict) and genre.get("name")
    )
    contributors = Counter(
        contributor.get("name")
        for item in albums
        for contributor in item.get("contributors", [])
        if isinstance(contributor, dict) and contributor.get("name")
    )
    dated = [item for item in albums if item.get("release_date")]
    return {
        "albums_by_year": dict(years.most_common()),
        "albums_by_genre": dict(genres.most_common()),
        "albums_by_label": dict(labels.most_common()),
        "top_contributors": dict(contributors.most_common(25)),
        "oldest_release": min(dated, key=lambda item: item["release_date"]) if dated else None,
        "newest_release": max(dated, key=lambda item: item["release_date"]) if dated else None,
    }


def write_metadata_cache(cache: dict[str, Any], path: Path) -> None:
    atomic_write_text(path, json.dumps(cache, ensure_ascii=False, indent=2, sort_keys=True) + "\n")


def write_metadata_reports(cache: dict[str, Any], reports_dir: Path) -> None:
    reports_dir.mkdir(parents=True, exist_ok=True)
    atomic_write_text(reports_dir / "metadata_coverage_report.md", render_coverage_report(cache))
    atomic_write_text(reports_dir / "metadata_quality_report.md", render_quality_report(cache))
    atomic_write_text(reports_dir / "metadata_collection_report.md", render_collection_report(cache))


def render_coverage_report(cache: dict[str, Any]) -> str:
    summary = cache.get("summary", metadata_coverage(cache, len(cache.get("albums", {}))))
    lines = [
        "# Metadata Coverage Report",
        "",
        f"Generated: {cache.get('generated_at', 'unknown')}",
        "",
        "| Metric | Count |",
        "| --- | ---: |",
        f"| Total lifecycle albums | {summary['total_lifecycle_albums']} |",
        f"| Albums with metadata | {summary['albums_with_metadata']} |",
        f"| Albums missing metadata | {summary['albums_missing_metadata']} |",
        f"| Artists cached | {summary['artists_cached']} |",
        f"| Tracks cached | {summary['tracks_cached']} |",
        f"| Coverage percentage | {summary['coverage_percent']:.1%} |",
        "",
    ]
    return "\n".join(lines)


def render_quality_report(cache: dict[str, Any]) -> str:
    quality = metadata_quality(cache)
    lines = [
        "# Metadata Quality Report",
        "",
        f"Generated: {cache.get('generated_at', 'unknown')}",
        "",
        "| Quality gap | Count |",
        "| --- | ---: |",
    ]
    for key, count in quality.items():
        lines.append(f"| {key.replace('_', ' ').title()} | {count} |")
    lines.append("")
    return "\n".join(lines)


def render_collection_report(cache: dict[str, Any]) -> str:
    summary = collection_summary(cache)
    lines = [
        "# Metadata Collection Report",
        "",
        f"Generated: {cache.get('generated_at', 'unknown')}",
        "",
        "## Release Range",
        "",
        f"- Oldest release: `{_album_label(summary.get('oldest_release'))}`",
        f"- Newest release: `{_album_label(summary.get('newest_release'))}`",
        "",
    ]
    for title, key in (
        ("Albums By Year", "albums_by_year"),
        ("Albums By Genre", "albums_by_genre"),
        ("Albums By Label", "albums_by_label"),
        ("Top Contributors", "top_contributors"),
    ):
        lines.extend([f"## {title}", "", "| Value | Albums |", "| --- | ---: |"])
        for value, count in list(summary[key].items())[:50]:
            lines.append(f"| {_escape(value)} | {count} |")
        lines.append("")
    return "\n".join(lines)


def _parse_contributor(data: dict[str, Any]) -> dict[str, Any]:
    return {
        "deezer_artist_id": str(data.get("id")) if data.get("id") is not None else None,
        "name": data.get("name"),
        "role": data.get("role"),
    }


def _year(value: Any) -> int | None:
    if not isinstance(value, str) or len(value) < 4 or not value[:4].isdigit():
        return None
    return int(value[:4])


def _pct_float(count: int, total: int) -> float:
    if total == 0:
        return 0.0
    return round(count / total, 4)


def _album_label(item: dict[str, Any] | None) -> str:
    if not item:
        return "none"
    return f"{item.get('release_date')} - {item.get('artist', {}).get('name') if isinstance(item.get('artist'), dict) else ''} - {item.get('title')}"


def _escape(value: Any) -> str:
    return str(value or "").replace("|", "\\|").replace("\n", " ").strip()


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="Build derived Deezer metadata cache.")
    parser.add_argument("--limit", type=int, default=None, help="maximum missing albums to fetch")
    args = parser.parse_args(argv)

    root = Path(__file__).resolve().parents[1]
    data_dir = root / "data"
    cache_path = data_dir / "metadata_cache.json"
    cache = build_metadata_cache(
        load_json_file(data_dir / "lifecycle_registry.json"),
        load_json_file(data_dir / "identity_registry.json"),
        existing_cache=load_cache(cache_path),
        limit=args.limit,
    )
    write_metadata_cache(cache, cache_path)
    write_metadata_reports(cache, root / "reports")

    summary = cache["summary"]
    print(
        "Wrote metadata cache; "
        f"albums: {summary['albums_with_metadata']}/{summary['total_lifecycle_albums']}, "
        f"artists: {summary['artists_cached']}, tracks: {summary['tracks_cached']}."
    )


if __name__ == "__main__":
    main()
