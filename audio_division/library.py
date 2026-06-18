from __future__ import annotations

from collections import defaultdict
from pathlib import Path
from typing import Any

from audio_division.album_truth import album_truth, truth_summary as album_truth_summary
from audio_division.artifacts import detect_album_artifacts
from audio_division.archive_readiness import annotate_library_readiness
from audio_division.dashboard import load_json
from audio_division.metadata_status import album_metadata_status
from curator.atomic import atomic_write_text


def load_library_sources(data_dir: Path) -> dict[str, dict[str, Any]]:
    return {
        "lifecycle": load_json(data_dir / "lifecycle_registry.json"),
        "identity": load_json(data_dir / "identity_registry.json"),
        "metadata": load_json(data_dir / "metadata_cache.json"),
    }


def build_library(
    lifecycle: dict[str, Any],
    identity: dict[str, Any],
    metadata: dict[str, Any],
    archive_root: Path | None = None,
) -> dict[str, Any]:
    identity_by_album = {
        row.get("discovery_identity", {}).get("deezer_album_id"): row
        for row in identity.get("releases", [])
        if row.get("discovery_identity", {}).get("deezer_album_id")
    }
    metadata_albums = metadata.get("albums", {})
    lifecycle_rows = lifecycle.get("albums", [])
    albums = [
        _album_record(row, metadata_albums.get(str(row.get("album_id")), {}), metadata, identity_by_album, archive_root)
        for row in lifecycle_rows
    ]
    artists = build_artist_index(albums, metadata)

    return annotate_library_readiness({
        "summary": library_summary(artists, albums, metadata, lifecycle),
        "artists": artists,
        "albums": sorted(albums, key=lambda item: (_sort_text(item["artist"]), _sort_text(item["title"]), item["album_id"])),
        "albums_by_artist": _albums_by_artist(albums),
    })


def library_from_data_dir(data_dir: Path, archive_root: Path | None = None) -> dict[str, Any]:
    sources = load_library_sources(data_dir)
    return build_library(sources["lifecycle"], sources["identity"], sources["metadata"], archive_root)


def build_artist_index(albums: list[dict[str, Any]], metadata: dict[str, Any]) -> list[dict[str, Any]]:
    counts: dict[str, int] = defaultdict(int)
    display: dict[str, str] = {}
    for album in albums:
        key = _artist_key(album.get("artist"))
        counts[key] += 1
        display.setdefault(key, album.get("artist") or "(unknown)")

    for artist in metadata.get("artists", {}).values():
        name = artist.get("name")
        if not name:
            continue
        key = _artist_key(name)
        display.setdefault(key, name)
        counts.setdefault(key, 0)

    return [
        {"artist_key": key, "name": display[key], "album_count": counts[key]}
        for key in sorted(display, key=lambda item: display[item].lower())
    ]


def albums_for_artist(library: dict[str, Any], artist_key: str) -> list[dict[str, Any]]:
    return library.get("albums_by_artist", {}).get(artist_key, [])


def album_details(library: dict[str, Any], album_id: str) -> dict[str, Any]:
    for album in library.get("albums", []):
        if str(album.get("album_id")) == str(album_id):
            return album
    return {}


def album_archive_operation_target(details: dict[str, Any]) -> tuple[str, str]:
    path = str(details.get("archive_path") or "").strip()
    if path:
        return path, "ok"
    confidence = details.get("archive_path_confidence", "UNKNOWN")
    reason = details.get("archive_path_reason", "no_archive_path")
    if confidence == "MEDIUM":
        return "", "Archive folder is known, but Main Archive Root is not configured."
    if reason == "no_archive_folder_evidence":
        return "", "No archive path available for this album."
    return "", f"No archive path available for this album: {reason}"


def album_status(details: dict[str, Any]) -> dict[str, Any]:
    if not details:
        return {"items": {}, "health_percent": 0}
    truth = album_truth(
        archive_path=details.get("archive_path"),
        registry_artifacts=details.get("artifacts", {}),
        validator_evidence={"validation": details.get("validation_status") == "validated"},
        metadata_state=details.get("metadata_status"),
    )
    return truth.to_album_status()


def resolve_archive_path(identity: dict[str, Any], archive_root: Path | None = None) -> dict[str, Any]:
    folder = identity.get("archive_identity", {}).get("folder") or ""
    log_path = identity.get("validation", {}).get("validation_log_path") or ""
    if log_path:
        path = Path(log_path).parent
        return _path_resolution(path, folder or path.name, "HIGH", "validation_log_path")
    if not folder:
        return {
            "archive_folder": "",
            "archive_path": "",
            "archive_path_confidence": "UNKNOWN",
            "archive_path_reason": "no_archive_folder_evidence",
        }

    path = Path(folder)
    if path.is_absolute():
        return _path_resolution(path, folder, "HIGH", "absolute_archive_folder")
    if archive_root:
        return _path_resolution(archive_root / path, folder, "HIGH", "archive_root_plus_folder")
    return {
        "archive_folder": folder,
        "archive_path": "",
        "archive_path_confidence": "MEDIUM",
        "archive_path_reason": "relative_archive_folder_without_archive_root",
    }


def archive_path_summary(albums: list[dict[str, Any]]) -> dict[str, Any]:
    total = len(albums)
    known = sum(1 for album in albums if album.get("archive_path"))
    medium = sum(1 for album in albums if album.get("archive_path_confidence") == "MEDIUM")
    unknown = sum(1 for album in albums if album.get("archive_path_confidence") == "UNKNOWN")
    return {
        "total_albums": total,
        "known_archive_paths": known,
        "medium_confidence_paths": medium,
        "unresolved_archive_paths": unknown,
        "coverage_percent": _ratio(known, total),
    }


def render_archive_path_resolution_report(library: dict[str, Any]) -> str:
    albums = library.get("albums", [])
    summary = archive_path_summary(albums)
    lines = [
        "# Archive Path Resolution Report",
        "",
        "Archive paths are derived from existing identity and validator evidence. No archive files are modified.",
        "",
        "## Summary",
        "",
        f"- Total albums: `{summary['total_albums']}`",
        f"- Albums with known archive paths: `{summary['known_archive_paths']}`",
        f"- Albums with relative folder evidence only: `{summary['medium_confidence_paths']}`",
        f"- Albums with unresolved paths: `{summary['unresolved_archive_paths']}`",
        f"- Coverage: `{summary['coverage_percent']:.1%}`",
        "",
        "## Examples",
        "",
        "| Confidence | Album ID | Artist | Album | Archive Folder | Archive Path | Reason |",
        "| --- | --- | --- | --- | --- | --- | --- |",
    ]
    for album in albums[:500]:
        lines.append(
            f"| {album.get('archive_path_confidence', 'UNKNOWN')} | `{_escape(album.get('album_id'))}` | "
            f"{_escape(album.get('artist'))} | {_escape(album.get('title'))} | "
            f"`{_escape(album.get('archive_folder'))}` | `{_escape(album.get('archive_path'))}` | "
            f"{_escape(album.get('archive_path_reason'))} |"
        )
    return "\n".join(lines) + "\n"


def write_archive_path_resolution_report(library: dict[str, Any], reports_dir: Path) -> None:
    reports_dir.mkdir(parents=True, exist_ok=True)
    atomic_write_text(reports_dir / "archive_path_resolution_report.md", render_archive_path_resolution_report(library))


def library_summary(
    artists: list[dict[str, Any]],
    albums: list[dict[str, Any]],
    metadata: dict[str, Any],
    lifecycle: dict[str, Any],
) -> dict[str, Any]:
    total = len(albums)
    truth = album_truth_summary(albums)
    validated = truth["counts"]["validation"]["Present"]
    metadata_summary = metadata.get("summary", {})
    return {
        "artists": len(artists),
        "albums": total,
        "tracks": len(metadata.get("tracks", {})),
        "metadata_coverage": metadata_summary.get("coverage_percent", _ratio(metadata_summary.get("albums_with_metadata", 0), total)),
        "validation_coverage": _ratio(validated, total),
        "album_truth": truth,
        "source_lifecycle_generated_at": lifecycle.get("generated_at"),
    }


def _album_record(
    lifecycle_row: dict[str, Any],
    metadata_album: dict[str, Any],
    metadata: dict[str, Any],
    identity_by_album: dict[str, dict[str, Any]],
    archive_root: Path | None,
) -> dict[str, Any]:
    album_id = str(lifecycle_row.get("album_id"))
    identity = identity_by_album.get(album_id, {})
    metadata_detail = album_metadata_status(album_id, metadata)
    path_resolution = resolve_archive_path(identity, archive_root)
    archive_path_text = path_resolution.get("archive_path", "")
    archive_path = Path(archive_path_text) if archive_path_text else None
    artifacts = detect_album_artifacts(archive_path) if archive_path else {}
    artist = _metadata_artist(metadata_album) or lifecycle_row.get("artist") or "(unknown)"
    title = metadata_album.get("title") or lifecycle_row.get("title") or "(unknown)"
    states = lifecycle_row.get("states", {})
    covers = metadata_album.get("covers", {}) if isinstance(metadata_album.get("covers"), dict) else {}
    truth = album_truth(
        archive_path=archive_path,
        registry_artifacts=artifacts,
        validator_evidence={
            "validation": bool(states.get("validated")),
            "validation_log_path": identity.get("validation", {}).get("validation_log_path", ""),
        },
        metadata_state=metadata_detail["state"],
        metadata_album=metadata_album,
    )
    status = truth.to_album_status()
    validation_status = "validated" if truth.validation.present else "not_validated"

    return {
        "album_id": album_id,
        "artist_key": _artist_key(artist),
        "artist": artist,
        "title": title,
        "year": metadata_album.get("year"),
        "release_date": metadata_album.get("release_date"),
        "record_type": metadata_album.get("record_type"),
        "label": metadata_album.get("label"),
        "genres": [item.get("name") for item in metadata_album.get("genres", []) if isinstance(item, dict) and item.get("name")],
        "track_count": metadata_album.get("track_count") or lifecycle_row.get("details", {}).get("validated_tracks"),
        "duration": metadata_album.get("duration"),
        "lifecycle_state": lifecycle_row.get("highest_state"),
        "identity_confidence": identity.get("identity_confidence", "UNKNOWN"),
        "validation_status": validation_status,
        "metadata_status": metadata_detail["state"],
        "metadata_detail": metadata_detail,
        "archive_folder": path_resolution["archive_folder"],
        "archive_path": path_resolution["archive_path"],
        "archive_path_confidence": path_resolution["archive_path_confidence"],
        "archive_path_reason": path_resolution["archive_path_reason"],
        "artifacts": artifacts,
        "album_status": status,
        "archive_strength_signals": {
            "has_identity": identity.get("identity_confidence") == "HIGH",
            "has_validation": truth.validation.present,
            "has_metadata": bool(metadata_album),
            "has_nfo": truth.nfo.present,
            "has_sfv": truth.sfv.present,
            "has_playlist": truth.playlist.present,
            "has_artwork": truth.artwork.present,
        },
        "artwork": {
            "cover_identity": metadata_album.get("cover_identity"),
            "urls": covers,
            "local": artifacts.get("artwork_path") if artifacts else None,
        },
    }


def _path_resolution(path: Path, folder: str, confidence: str, reason: str) -> dict[str, Any]:
    return {
        "archive_folder": folder,
        "archive_path": str(path),
        "archive_path_confidence": confidence,
        "archive_path_reason": reason,
    }


def _albums_by_artist(albums: list[dict[str, Any]]) -> dict[str, list[dict[str, Any]]]:
    out: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for album in albums:
        out[album["artist_key"]].append(album)
    for key in out:
        out[key].sort(key=lambda item: (_sort_year(item.get("year")), _sort_text(item.get("title"))))
    return dict(out)


def _metadata_artist(metadata_album: dict[str, Any]) -> str | None:
    artist = metadata_album.get("artist")
    if isinstance(artist, dict):
        return artist.get("name")
    return None


def _artist_key(name: Any) -> str:
    text = str(name or "(unknown)").strip().lower()
    return " ".join(text.split())


def _sort_text(value: Any) -> str:
    return str(value or "").lower()


def _sort_year(value: Any) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        return 9999


def _ratio(count: int, total: int) -> float:
    if total == 0:
        return 0.0
    return round(count / total, 4)


def _escape(value: Any) -> str:
    return str(value or "").replace("|", "\\|").replace("\n", " ").strip()
