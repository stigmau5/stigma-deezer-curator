from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any


ARTIFACT_FIELDS = ("validation", "nfo", "sfv", "playlist", "artwork", "metadata")
ARTWORK_NAMES = ("cover.jpg", "folder.jpg", "front.jpg", "cover.png", "folder.png")
ARTWORK_SUFFIXES = {".jpg", ".jpeg", ".png", ".webp"}
PLAYLIST_SUFFIXES = {".m3u", ".m3u8"}
PRESENT = "Present"
MISSING = "Missing"
UNKNOWN = "Unknown"


@dataclass(frozen=True)
class TruthValue:
    status: str
    source: str
    path: str = ""
    reason: str = ""

    @property
    def present(self) -> bool:
        return self.status == PRESENT


@dataclass(frozen=True)
class AlbumTruth:
    validation: TruthValue
    nfo: TruthValue
    sfv: TruthValue
    playlist: TruthValue
    artwork: TruthValue
    metadata: TruthValue

    def status_items(self) -> dict[str, str]:
        return {field: getattr(self, field).status for field in ARTIFACT_FIELDS}

    def to_album_status(self) -> dict[str, Any]:
        items = self.status_items()
        known = [value for value in items.values() if value != UNKNOWN]
        present = sum(1 for value in known if value == PRESENT)
        return {
            "items": items,
            "health_percent": round((present / len(known)) * 100) if known else 0,
            "truth_sources": {field: getattr(self, field).source for field in ARTIFACT_FIELDS},
            "truth_paths": {field: getattr(self, field).path for field in ARTIFACT_FIELDS if getattr(self, field).path},
        }


def album_truth(
    *,
    archive_path: str | Path | None = None,
    registry_artifacts: dict[str, Any] | None = None,
    validator_evidence: dict[str, Any] | bool | None = None,
    metadata_state: str | None = None,
    metadata_album: dict[str, Any] | None = None,
) -> AlbumTruth:
    filesystem = filesystem_artifacts(archive_path)
    validator = normalize_validator_evidence(validator_evidence)
    registry = registry_artifacts or {}
    return AlbumTruth(
        validation=resolve_truth("validation", filesystem, validator, registry, metadata_state, metadata_album),
        nfo=resolve_truth("nfo", filesystem, validator, registry, metadata_state, metadata_album),
        sfv=resolve_truth("sfv", filesystem, validator, registry, metadata_state, metadata_album),
        playlist=resolve_truth("playlist", filesystem, validator, registry, metadata_state, metadata_album),
        artwork=resolve_truth("artwork", filesystem, validator, registry, metadata_state, metadata_album),
        metadata=resolve_truth("metadata", filesystem, validator, registry, metadata_state, metadata_album),
    )


def album_status_from_truth(**kwargs: Any) -> dict[str, Any]:
    return album_truth(**kwargs).to_album_status()


def truth_summary(albums: list[dict[str, Any]]) -> dict[str, Any]:
    counts = {field: {PRESENT: 0, MISSING: 0, UNKNOWN: 0} for field in ARTIFACT_FIELDS}
    for album in albums:
        items = album.get("album_status", {}).get("items", {})
        for field in ARTIFACT_FIELDS:
            status = items.get(field, UNKNOWN)
            counts[field][status if status in counts[field] else UNKNOWN] += 1
    total = len(albums)
    return {
        "total_albums": total,
        "counts": counts,
        "validation_coverage": _ratio(counts["validation"][PRESENT], total),
        "metadata_coverage": _ratio(counts["metadata"][PRESENT], total),
        "artwork_coverage": _ratio(counts["artwork"][PRESENT], total),
    }


def filesystem_artifacts(archive_path: str | Path | None) -> dict[str, TruthValue]:
    if not archive_path:
        return {}
    path = Path(archive_path)
    if not path.exists() or not path.is_dir():
        return {}
    files = [item for item in path.iterdir() if item.is_file()]
    by_name = {item.name.lower(): item for item in files}
    return {
        "validation": _file_truth(by_name.get("STIGMA_VALIDATED.txt".lower()), "filesystem"),
        "nfo": _first_truth(by_name, files, "filesystem", preferred=("release.nfo",), suffixes={".nfo"}),
        "sfv": _first_truth(by_name, files, "filesystem", preferred=("release.sfv",), suffixes={".sfv"}),
        "playlist": _first_truth(by_name, files, "filesystem", preferred=("playlist.m3u8",), suffixes=PLAYLIST_SUFFIXES),
        "artwork": _first_truth(by_name, files, "filesystem", preferred=ARTWORK_NAMES, suffixes=ARTWORK_SUFFIXES),
    }


def normalize_validator_evidence(evidence: dict[str, Any] | bool | None) -> dict[str, Any]:
    if isinstance(evidence, bool):
        return {"validation": evidence}
    return evidence or {}


def resolve_truth(
    field: str,
    filesystem: dict[str, TruthValue],
    validator: dict[str, Any],
    registry: dict[str, Any],
    metadata_state: str | None,
    metadata_album: dict[str, Any] | None,
) -> TruthValue:
    if field == "metadata":
        return metadata_truth(metadata_state, metadata_album)

    if field in filesystem:
        return filesystem[field]

    if field == "validation":
        validation = validator.get("validation")
        if validation is not None:
            return _bool_truth(bool(validation), "validator_evidence")
        validation_path = validator.get("validation_log_path") or validator.get("path")
        if validation_path:
            return TruthValue(PRESENT, "validator_evidence", str(validation_path))

    registry_key = "validation_log" if field == "validation" else field
    if registry_key in registry:
        path = registry.get(f"{registry_key}_path") or registry.get(f"{field}_path") or ""
        return _bool_truth(bool(registry.get(registry_key)), "archive_registry", str(path))

    return TruthValue(UNKNOWN, "none", reason="no_evidence")


def metadata_truth(metadata_state: str | None, metadata_album: dict[str, Any] | None) -> TruthValue:
    if metadata_state == "CACHED" or bool(metadata_album):
        return TruthValue(PRESENT, "metadata_cache")
    if metadata_state in {"AVAILABLE_NOT_CACHED", "MISSING"}:
        return TruthValue(MISSING, "metadata_cache", reason=metadata_state)
    return TruthValue(UNKNOWN, "metadata_cache", reason=metadata_state or "unknown")


def _file_truth(path: Path | None, source: str) -> TruthValue:
    return TruthValue(PRESENT, source, str(path)) if path else TruthValue(MISSING, source)


def _first_truth(
    by_name: dict[str, Path],
    files: list[Path],
    source: str,
    *,
    preferred: tuple[str, ...],
    suffixes: set[str],
) -> TruthValue:
    for name in preferred:
        path = by_name.get(name.lower())
        if path:
            return TruthValue(PRESENT, source, str(path))
    matches = sorted(item for item in files if item.suffix.lower() in suffixes)
    return TruthValue(PRESENT, source, str(matches[0])) if matches else TruthValue(MISSING, source)


def _bool_truth(value: bool, source: str, path: str = "") -> TruthValue:
    return TruthValue(PRESENT if value else MISSING, source, path)


def _ratio(count: int, total: int) -> float:
    if total == 0:
        return 0.0
    return round(count / total, 4)
