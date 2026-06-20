from __future__ import annotations

from typing import Any


RELATIONSHIP_LIMIT = 8


def album_relationships(
    album: dict[str, Any],
    albums: list[dict[str, Any]],
    *,
    limit: int = RELATIONSHIP_LIMIT,
) -> dict[str, Any]:
    """Build read-only album relationship groups from cached/archive data."""
    current_key = album_key(album)
    candidates = [row for row in albums if album_key(row) != current_key]
    groups = {
        "same_artist": _same_artist(album, candidates, limit),
        "same_label": _same_value(album, candidates, "label", limit),
        "same_year": _same_value(album, candidates, "year", limit),
        "same_genre": _same_genre(album, candidates, limit),
    }
    total = sum(len(items) for items in groups.values())
    return {"groups": groups, "total": total, "summary": relationship_summary(groups)}


def relationship_summary(groups: dict[str, list[dict[str, Any]]]) -> list[tuple[str, int]]:
    labels = {
        "same_artist": "Same Artist",
        "same_label": "Same Label",
        "same_year": "Same Year",
        "same_genre": "Same Genre",
    }
    return [(labels[key], len(groups.get(key, []))) for key in labels]


def render_relationships(relationships: dict[str, Any]) -> str:
    groups = relationships.get("groups", {})
    sections = (
        ("same_artist", "Same Artist"),
        ("same_label", "Same Label"),
        ("same_year", "Same Year"),
        ("same_genre", "Same Genre"),
    )
    lines: list[str] = []
    for key, title in sections:
        rows = groups.get(key, [])
        lines.append(f"{title}: {len(rows)}")
        if rows:
            lines.extend(f"  {_display_album(row)}" for row in rows)
        lines.append("")
    if not any(groups.get(key) for key, _ in sections):
        return "No related albums found from cached/archive data."
    return "\n".join(lines).rstrip()


def album_key(album: dict[str, Any]) -> str:
    for key in ("album_id", "archive_path"):
        value = str(album.get(key) or "").strip()
        if value:
            return f"{key}:{value}"
    return f"title:{_norm(album.get('artist'))}:{_norm(album.get('title') or album.get('album'))}"


def _same_artist(album: dict[str, Any], candidates: list[dict[str, Any]], limit: int) -> list[dict[str, Any]]:
    artist = _norm(album.get("artist"))
    if not artist:
        return []
    rows = [row for row in candidates if _norm(row.get("artist")) == artist]
    return _sort_rows(rows)[:limit]


def _same_value(album: dict[str, Any], candidates: list[dict[str, Any]], field: str, limit: int) -> list[dict[str, Any]]:
    value = _norm(album.get(field))
    if not value:
        return []
    rows = [row for row in candidates if _norm(row.get(field)) == value]
    return _sort_rows(rows)[:limit]


def _same_genre(album: dict[str, Any], candidates: list[dict[str, Any]], limit: int) -> list[dict[str, Any]]:
    genres = {_norm(value) for value in _as_list(album.get("genres")) if _norm(value)}
    if not genres:
        return []
    scored: dict[str, tuple[int, dict[str, Any]]] = {}
    for row in candidates:
        overlap = genres.intersection({_norm(value) for value in _as_list(row.get("genres")) if _norm(value)})
        if not overlap:
            continue
        scored[album_key(row)] = (len(overlap), row)
    rows = [row for _, row in sorted(scored.values(), key=lambda item: (-item[0], _sort_key(item[1])))]
    return rows[:limit]


def _sort_rows(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return sorted(rows, key=_sort_key)


def _sort_key(row: dict[str, Any]) -> tuple[str, str, str]:
    return (_norm(row.get("artist")), _norm(row.get("year")), _norm(row.get("title") or row.get("album")))


def _display_album(row: dict[str, Any]) -> str:
    artist = str(row.get("artist") or "(unknown)")
    title = str(row.get("title") or row.get("album") or "(unknown)")
    year = str(row.get("year") or "").strip()
    suffix = f" ({year})" if year else ""
    return f"{artist} - {title}{suffix}"


def _as_list(value: Any) -> list[Any]:
    if isinstance(value, list):
        return value
    if value:
        return [value]
    return []


def _norm(value: Any) -> str:
    return " ".join(str(value or "").strip().lower().split())
