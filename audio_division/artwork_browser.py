from __future__ import annotations

from pathlib import Path
from typing import Any

from audio_division.album_presentation import thumbnail_info
from audio_division.artifacts import select_artwork_file
from curator.atomic import atomic_write_text


def artwork_items(library: dict[str, Any], archive_registry: dict[str, Any] | None = None) -> list[dict[str, Any]]:
    items = []
    seen_paths = set()
    for album in library.get("albums", []):
        thumbnail = thumbnail_info(album)
        readiness = album.get("archive_readiness", {})
        archive_path = album.get("archive_path", "")
        if archive_path:
            seen_paths.add(str(Path(archive_path)))
        if thumbnail.get("source") == "none" and archive_path:
            artwork_path = first_artwork_path(Path(archive_path))
            if artwork_path:
                thumbnail = {
                    "status": "Present",
                    "source": "local",
                    "path": str(artwork_path),
                    "url": "",
                    "display": artwork_path.name,
                }
        items.append(
            {
                "album_id": album.get("album_id", ""),
                "artist": album.get("artist", ""),
                "album": album.get("title", ""),
                "year": album.get("year") or "",
                "readiness": readiness.get("state", "UNKNOWN"),
                "archive_path": archive_path,
                "artwork_status": thumbnail.get("status", "Missing"),
                "artwork_source": thumbnail.get("source", "none"),
                "thumbnail_path": thumbnail.get("path", ""),
                "thumbnail_url": thumbnail.get("url", ""),
                "thumbnail_display": thumbnail.get("display", ""),
            }
        )
    for album in (archive_registry or {}).get("albums", []):
        archive_path = str(album.get("archive_path") or "")
        if not archive_path or archive_path in seen_paths:
            continue
        path = Path(archive_path)
        artwork_path = first_artwork_path(path)
        if not artwork_path:
            continue
        artist, title = split_archive_folder(album.get("name") or path.name)
        items.append(
            {
                "album_id": "",
                "artist": artist,
                "album": title,
                "year": "",
                "readiness": "UNKNOWN",
                "archive_path": archive_path,
                "artwork_status": "Present",
                "artwork_source": "local",
                "thumbnail_path": str(artwork_path),
                "thumbnail_url": "",
                "thumbnail_display": artwork_path.name,
            }
        )
    return sorted(
        items,
        key=lambda item: (
            _source_rank(item.get("artwork_source")),
            _sort_text(item["artist"]),
            _sort_text(item["album"]),
            str(item["album_id"]),
        ),
    )


def filter_artwork_items(
    items: list[dict[str, Any]],
    *,
    artist: str = "",
    album: str = "",
) -> list[dict[str, Any]]:
    artist_query = artist.strip().lower()
    album_query = album.strip().lower()
    out = []
    for item in items:
        if artist_query and artist_query not in str(item.get("artist", "")).lower():
            continue
        if album_query and album_query not in str(item.get("album", "")).lower():
            continue
        out.append(item)
    return out


def artwork_summary(items: list[dict[str, Any]]) -> dict[str, Any]:
    total = len(items)
    local = sum(1 for item in items if item.get("artwork_source") == "local")
    metadata = sum(1 for item in items if item.get("artwork_source") == "metadata_url")
    missing = sum(1 for item in items if item.get("artwork_source") == "none")
    return {
        "total_albums": total,
        "local_artwork": local,
        "metadata_artwork": metadata,
        "missing_artwork": missing,
        "coverage_percent": _ratio(local + metadata, total),
    }


def grid_rows(items: list[dict[str, Any]], columns: int = 4) -> list[list[dict[str, Any]]]:
    columns = max(1, columns)
    return [items[index : index + columns] for index in range(0, len(items), columns)]


def render_artwork_coverage_report(library: dict[str, Any], archive_registry: dict[str, Any] | None = None) -> str:
    items = artwork_items(library, archive_registry)
    summary = artwork_summary(items)
    lines = [
        "# Artwork Coverage Report",
        "",
        "Artwork coverage is derived from the Library projection and existing archive evidence. No artwork files are modified.",
        "",
        "## Summary",
        "",
        f"- Total albums: `{summary['total_albums']}`",
        f"- Local artwork: `{summary['local_artwork']}`",
        f"- Metadata artwork references: `{summary['metadata_artwork']}`",
        f"- Missing artwork: `{summary['missing_artwork']}`",
        f"- Coverage: `{summary['coverage_percent']:.1%}`",
        "",
        "## Albums",
        "",
        "| Artist | Album | Year | Readiness | Artwork | Source |",
        "| --- | --- | ---: | --- | --- | --- |",
    ]
    for item in items[:500]:
        lines.append(
            f"| {_escape(item.get('artist'))} | {_escape(item.get('album'))} | {_escape(item.get('year'))} | "
            f"{_escape(item.get('readiness'))} | {item.get('artwork_status', 'Missing')} | "
            f"{_escape(item.get('thumbnail_display'))} |"
        )
    return "\n".join(lines) + "\n"


def write_artwork_coverage_report(
    library: dict[str, Any],
    reports_dir: Path,
    archive_registry: dict[str, Any] | None = None,
) -> None:
    reports_dir.mkdir(parents=True, exist_ok=True)
    atomic_write_text(reports_dir / "artwork_coverage_report.md", render_artwork_coverage_report(library, archive_registry))


def first_artwork_path(album_path: Path) -> Path | None:
    return select_artwork_file(album_path)


def split_archive_folder(folder_name: Any) -> tuple[str, str]:
    text = str(folder_name or "").strip()
    for separator in (" - ", "-"):
        if separator in text:
            artist, album = text.split(separator, 1)
            return artist.strip() or "(unknown)", album.strip() or text
    return "(unknown)", text or "(unknown)"


def _ratio(count: int, total: int) -> float:
    if total == 0:
        return 0.0
    return round(count / total, 4)


def _sort_text(value: Any) -> str:
    return str(value or "").lower()


def _source_rank(source: Any) -> int:
    return {"local": 0, "metadata_url": 1, "none": 2}.get(str(source), 3)


def _escape(value: Any) -> str:
    return str(value or "").replace("|", "\\|").replace("\n", " ").strip()
