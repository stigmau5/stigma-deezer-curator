from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any, Iterable

from audio_division.album_truth import PRESENT
from audio_division.maintenance import maintenance_warnings


HEALTH_OK = "OK"
HEALTH_WARNING = "WARNING"
HEALTH_ERROR = "ERROR"

ARTIFACT_FIELDS = {
    "missing_artwork": "artwork",
    "missing_nfo": "nfo",
    "missing_playlist": "playlist",
    "missing_sfv": "sfv",
    "missing_validation": "validation",
}


@dataclass(frozen=True)
class ArchiveHealthReport:
    albums: int
    healthy: int
    warnings: int
    errors: int
    missing_artwork: int
    missing_nfo: int
    missing_playlist: int
    missing_sfv: int
    missing_validation: int
    metadata_coverage: float
    identity_coverage: float
    duplicate_releases: int
    broken_layouts: int
    unexpected_layouts: int
    status: str

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def archive_health_report(albums: Iterable[dict[str, Any]]) -> ArchiveHealthReport:
    rows = list(albums)
    total = len(rows)
    warning_rows = maintenance_warnings(rows)
    duplicate_releases = sum(1 for warning in warning_rows if warning.get("type") == "duplicate_album")
    unexpected_layouts = sum(1 for warning in warning_rows if warning.get("type") == "unexpected_structure")
    missing = {
        name: sum(1 for album in rows if _artifact_status(album, field) != PRESENT)
        for name, field in ARTIFACT_FIELDS.items()
    }
    broken_layouts = sum(1 for album in rows if _is_broken_layout(album))
    errors = missing["missing_validation"] + broken_layouts
    warnings = (
        missing["missing_artwork"]
        + missing["missing_nfo"]
        + missing["missing_playlist"]
        + missing["missing_sfv"]
        + _missing_metadata_count(rows)
        + _missing_identity_count(rows)
        + duplicate_releases
        + unexpected_layouts
    )
    healthy = sum(1 for album in rows if _is_healthy(album))
    status = HEALTH_ERROR if errors else HEALTH_WARNING if warnings else HEALTH_OK
    return ArchiveHealthReport(
        albums=total,
        healthy=healthy,
        warnings=warnings,
        errors=errors,
        missing_artwork=missing["missing_artwork"],
        missing_nfo=missing["missing_nfo"],
        missing_playlist=missing["missing_playlist"],
        missing_sfv=missing["missing_sfv"],
        missing_validation=missing["missing_validation"],
        metadata_coverage=_coverage(total - _missing_metadata_count(rows), total),
        identity_coverage=_coverage(total - _missing_identity_count(rows), total),
        duplicate_releases=duplicate_releases,
        broken_layouts=broken_layouts,
        unexpected_layouts=unexpected_layouts,
        status=status,
    )


def archive_health_summary(albums: Iterable[dict[str, Any]]) -> dict[str, Any]:
    return archive_health_report(albums).to_dict()


def _artifact_status(album: dict[str, Any], field: str) -> str:
    truth_items = album.get("album_truth", {}).get("items")
    if isinstance(truth_items, dict) and field in truth_items:
        return str(truth_items.get(field) or "")
    status_items = album.get("album_status", {}).get("items")
    if isinstance(status_items, dict) and field in status_items:
        return str(status_items.get(field) or "")
    return ""


def _metadata_present(album: dict[str, Any]) -> bool:
    return _artifact_status(album, "metadata") == PRESENT or str(album.get("metadata_status") or "") == "CACHED"


def _identity_present(album: dict[str, Any]) -> bool:
    confidence = str(album.get("identity_confidence") or album.get("album_truth", {}).get("identity_confidence") or "")
    return confidence in {"HIGH", "MEDIUM"}


def _missing_metadata_count(albums: list[dict[str, Any]]) -> int:
    return sum(1 for album in albums if not _metadata_present(album))


def _missing_identity_count(albums: list[dict[str, Any]]) -> int:
    return sum(1 for album in albums if not _identity_present(album))


def _is_healthy(album: dict[str, Any]) -> bool:
    required = ("artwork", "nfo", "playlist", "sfv", "validation", "metadata")
    if any(_artifact_status(album, field) != PRESENT for field in required):
        return False
    if not _identity_present(album):
        return False
    readiness = str(album.get("album_truth", {}).get("readiness") or album.get("archive_readiness", {}).get("state") or "")
    return readiness in {"ARCHIVE_READY", "OK", ""}


def _is_broken_layout(album: dict[str, Any]) -> bool:
    readiness = str(album.get("album_truth", {}).get("readiness") or album.get("archive_readiness", {}).get("state") or "")
    archive_path = str(album.get("archive_path") or "")
    return bool(archive_path) and readiness == "UNKNOWN"


def _coverage(present: int, total: int) -> float:
    return round((present / total) * 100, 1) if total else 0.0
