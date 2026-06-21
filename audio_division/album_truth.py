from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

from audio_division.artifacts import (
    AlbumArtifacts,
    PREFERRED_ARTWORK_FILENAMES,
    VALIDATION_MARKER_FILENAME,
    detect_artifacts,
)
from audio_division.validation_truth import (
    CONFIDENCE_HIGH,
    CONFIDENCE_LOW,
    CONFIDENCE_MEDIUM,
    CONFIDENCE_NONE,
    SOURCE_ARCHIVE_MARKER,
    SOURCE_IDENTITY_REGISTRY,
    SOURCE_LIFECYCLE_REGISTRY,
    SOURCE_MISSING,
    SOURCE_VALIDATED_INDEX,
    SOURCE_VALIDATOR_LOG,
    source_rank,
)


ARTIFACT_FIELDS = ("validation", "nfo", "sfv", "playlist", "artwork", "metadata")
READINESS_STATES = ("ARCHIVE_READY", "NEEDS_VALIDATION", "NEEDS_DOCUMENTATION", "NEEDS_REVIEW", "UNKNOWN")
PROCESSING_STATES = ("DISCOVERED", "DOWNLOADED", "PROCESSING", "ARCHIVED")
PRESENT = "Present"
MISSING = "Missing"
UNKNOWN = "Unknown"

MAINTENANCE_NEEDS_VALIDATION = "needs_validation"
MAINTENANCE_NEEDS_DOCUMENTATION = "needs_documentation"
MAINTENANCE_NEEDS_METADATA = "needs_metadata"
MAINTENANCE_NEEDS_REVIEW = "needs_review"
MAINTENANCE_WARNINGS = "warnings"
MAINTENANCE_READY = "ready"

MAINTENANCE_LABELS = {
    MAINTENANCE_NEEDS_VALIDATION: "Needs Validation",
    MAINTENANCE_NEEDS_DOCUMENTATION: "Needs Documentation",
    MAINTENANCE_NEEDS_METADATA: "Needs Metadata",
    MAINTENANCE_NEEDS_REVIEW: "Needs Review",
    MAINTENANCE_WARNINGS: "Warnings",
    MAINTENANCE_READY: "Ready",
}

MAINTENANCE_PRIORITIES = {
    MAINTENANCE_NEEDS_VALIDATION: "HIGH",
    MAINTENANCE_NEEDS_DOCUMENTATION: "MEDIUM",
    MAINTENANCE_NEEDS_METADATA: "LOW",
    MAINTENANCE_NEEDS_REVIEW: "HIGH",
    MAINTENANCE_WARNINGS: "HIGH",
    MAINTENANCE_READY: "INFO",
}

MAINTENANCE_OPERATIONS = {
    MAINTENANCE_NEEDS_VALIDATION: "validate_album",
    MAINTENANCE_NEEDS_DOCUMENTATION: "generate_documentation",
    MAINTENANCE_NEEDS_METADATA: "refresh_metadata",
    MAINTENANCE_NEEDS_REVIEW: "open_album_folder",
    MAINTENANCE_WARNINGS: "open_album_folder",
    MAINTENANCE_READY: "open_album_folder",
}


@dataclass(frozen=True)
class TruthValue:
    status: str
    source: str
    path: str = ""
    reason: str = ""
    confidence: str = ""

    @property
    def present(self) -> bool:
        return self.status == PRESENT


@dataclass(frozen=True)
class MaintenanceValue:
    category: str
    label: str
    priority: str
    operation: str
    reason: str

    def to_dict(self) -> dict[str, str]:
        return {
            "category": self.category,
            "label": self.label,
            "priority": self.priority,
            "operation": self.operation,
            "reason": self.reason,
        }


@dataclass(frozen=True)
class AlbumTruth:
    validation: TruthValue
    nfo: TruthValue
    sfv: TruthValue
    playlist: TruthValue
    artwork: TruthValue
    metadata: TruthValue
    artist: str = ""
    album: str = ""
    archive_path: str = ""
    metadata_status: str = UNKNOWN
    identity_confidence: str = UNKNOWN
    health: int = 0
    readiness: str = UNKNOWN
    processing_state: str = "DISCOVERED"
    source: str = "none"

    @property
    def validation_present(self) -> bool:
        return self.validation.present

    @property
    def validation_status(self) -> str:
        return self.validation.status

    @property
    def validation_source(self) -> str:
        return self.validation.source

    @property
    def validation_confidence(self) -> str:
        return self.validation.confidence or CONFIDENCE_NONE

    @property
    def validation_reason(self) -> str:
        return self.validation.reason

    @property
    def maintenance(self) -> MaintenanceValue:
        return maintenance_value(
            self.status_items(),
            readiness=self.readiness,
            metadata_status=self.metadata_status,
            identity_confidence=self.identity_confidence,
            validation_reason=self.validation_reason,
        )

    @property
    def nfo_present(self) -> bool:
        return self.nfo.present

    @property
    def sfv_present(self) -> bool:
        return self.sfv.present

    @property
    def playlist_present(self) -> bool:
        return self.playlist.present

    @property
    def artwork_present(self) -> bool:
        return self.artwork.present

    def status_items(self) -> dict[str, str]:
        return {field: getattr(self, field).status for field in ARTIFACT_FIELDS}

    def to_album_status(self) -> dict[str, Any]:
        items = self.status_items()
        return {
            "items": items,
            "health_percent": self.health,
            "truth_sources": {field: getattr(self, field).source for field in ARTIFACT_FIELDS},
            "truth_confidences": {field: getattr(self, field).confidence for field in ARTIFACT_FIELDS if getattr(self, field).confidence},
            "truth_reasons": {field: getattr(self, field).reason for field in ARTIFACT_FIELDS if getattr(self, field).reason},
            "truth_paths": {field: getattr(self, field).path for field in ARTIFACT_FIELDS if getattr(self, field).path},
            "validation_status": self.validation_status,
            "validation_source": self.validation_source,
            "validation_confidence": self.validation_confidence,
            "validation_reason": self.validation_reason,
            "maintenance": self.maintenance.to_dict(),
        }

    def to_dict(self) -> dict[str, Any]:
        return {
            "artist": self.artist,
            "album": self.album,
            "archive_path": self.archive_path,
            "artwork_present": self.artwork_present,
            "nfo_present": self.nfo_present,
            "sfv_present": self.sfv_present,
            "playlist_present": self.playlist_present,
            "validation_present": self.validation_present,
            "validation_status": self.validation_status,
            "validation_source": self.validation_source,
            "validation_confidence": self.validation_confidence,
            "validation_reason": self.validation_reason,
            "metadata_status": self.metadata_status,
            "identity_confidence": self.identity_confidence,
            "health": self.health,
            "readiness": self.readiness,
            "processing_state": self.processing_state,
            "source": self.source,
            "maintenance": self.maintenance.to_dict(),
            "items": self.status_items(),
            "sources": {field: getattr(self, field).source for field in ARTIFACT_FIELDS},
            "confidences": {field: getattr(self, field).confidence for field in ARTIFACT_FIELDS if getattr(self, field).confidence},
            "reasons": {field: getattr(self, field).reason for field in ARTIFACT_FIELDS if getattr(self, field).reason},
            "paths": {field: getattr(self, field).path for field in ARTIFACT_FIELDS if getattr(self, field).path},
        }


def maintenance_value(
    items: dict[str, Any],
    *,
    readiness: str = UNKNOWN,
    metadata_status: str = UNKNOWN,
    identity_confidence: str = UNKNOWN,
    validation_reason: str = "",
    warning_reason: str = "",
) -> MaintenanceValue:
    missing_docs = [
        label
        for field, label in (("nfo", "NFO"), ("sfv", "SFV"))
        if field in items and items.get(field) != PRESENT
    ]
    if items.get("validation") != PRESENT:
        category = MAINTENANCE_NEEDS_VALIDATION
        reason = validation_reason or "Validation evidence is missing."
    elif missing_docs:
        category = MAINTENANCE_NEEDS_DOCUMENTATION
        reason = f"Missing documentation: {', '.join(missing_docs)}."
    elif ("metadata" in items and items.get("metadata") != PRESENT) or metadata_status != "CACHED":
        category = MAINTENANCE_NEEDS_METADATA
        reason = f"Metadata status is {metadata_status or UNKNOWN}."
    elif readiness in {"NEEDS_REVIEW", UNKNOWN} or identity_confidence not in {"HIGH", "MEDIUM"}:
        category = MAINTENANCE_NEEDS_REVIEW
        missing_review = [
            label
            for field, label in (("playlist", "playlist"), ("artwork", "artwork"))
            if field in items and items.get(field) != PRESENT
        ]
        reason = (
            f"Review incomplete {', '.join(missing_review)} evidence."
            if missing_review
            else "AlbumTruth requires review."
        )
    elif warning_reason:
        category = MAINTENANCE_WARNINGS
        reason = warning_reason
    else:
        category = MAINTENANCE_READY
        reason = "AlbumTruth reports the album ready."
    return MaintenanceValue(
        category=category,
        label=MAINTENANCE_LABELS[category],
        priority=MAINTENANCE_PRIORITIES[category],
        operation=MAINTENANCE_OPERATIONS[category],
        reason=reason,
    )


def maintenance_value_from_album(album: dict[str, Any], warning_reason: str = "") -> MaintenanceValue:
    truth = album.get("album_truth") if isinstance(album.get("album_truth"), dict) else {}
    projected = truth.get("maintenance") if isinstance(truth.get("maintenance"), dict) else {}
    category = str(projected.get("category") or "")
    if category in MAINTENANCE_LABELS and not warning_reason:
        return MaintenanceValue(
            category=category,
            label=str(projected.get("label") or MAINTENANCE_LABELS[category]),
            priority=str(projected.get("priority") or MAINTENANCE_PRIORITIES[category]),
            operation=str(projected.get("operation") or MAINTENANCE_OPERATIONS[category]),
            reason=str(projected.get("reason") or ""),
        )

    legacy_status = album.get("album_status") if isinstance(album.get("album_status"), dict) else {}
    items = truth.get("items") if isinstance(truth.get("items"), dict) else legacy_status.get("items", {})
    readiness = truth.get("readiness") or album.get("archive_readiness", {}).get("state") or UNKNOWN
    metadata_status = truth.get("metadata_status") or album.get("metadata_status") or UNKNOWN
    identity_confidence = truth.get("identity_confidence") or album.get("identity_confidence") or UNKNOWN
    validation_reason = truth.get("validation_reason") or legacy_status.get("validation_reason") or ""
    return maintenance_value(
        items if isinstance(items, dict) else {},
        readiness=str(readiness),
        metadata_status=str(metadata_status),
        identity_confidence=str(identity_confidence),
        validation_reason=str(validation_reason),
        warning_reason=warning_reason,
    )


def album_truth(
    *,
    artist: str = "",
    album: str = "",
    archive_path: str | Path | None = None,
    registry_artifacts: dict[str, Any] | None = None,
    validator_evidence: dict[str, Any] | bool | None = None,
    metadata_state: str | None = None,
    metadata_album: dict[str, Any] | None = None,
    identity_confidence: str = UNKNOWN,
    detected_artifacts: AlbumArtifacts | None = None,
) -> AlbumTruth:
    filesystem = filesystem_artifacts(archive_path, detected_artifacts)
    validator = normalize_validator_evidence(validator_evidence)
    registry = registry_artifacts or {}
    values = {
        "validation": resolve_truth("validation", filesystem, validator, registry, metadata_state, metadata_album),
        "nfo": resolve_truth("nfo", filesystem, validator, registry, metadata_state, metadata_album),
        "sfv": resolve_truth("sfv", filesystem, validator, registry, metadata_state, metadata_album),
        "playlist": resolve_truth("playlist", filesystem, validator, registry, metadata_state, metadata_album),
        "artwork": resolve_truth("artwork", filesystem, validator, registry, metadata_state, metadata_album),
        "metadata": resolve_truth("metadata", filesystem, validator, registry, metadata_state, metadata_album),
    }
    archive_path_text = str(archive_path or "")
    health = health_percent(values)
    readiness = readiness_state(values, archive_path_text, identity_confidence)
    processing_state = processing_state_for(values, archive_path_text)
    return AlbumTruth(
        validation=values["validation"],
        nfo=values["nfo"],
        sfv=values["sfv"],
        playlist=values["playlist"],
        artwork=values["artwork"],
        metadata=values["metadata"],
        artist=artist,
        album=album,
        archive_path=archive_path_text,
        metadata_status=metadata_state or UNKNOWN,
        identity_confidence=identity_confidence or UNKNOWN,
        health=health,
        readiness=readiness,
        processing_state=processing_state,
        source=primary_source(values),
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


def health_percent(values: dict[str, TruthValue]) -> int:
    statuses = [value.status for value in values.values() if value.status != UNKNOWN]
    present = sum(1 for status in statuses if status == PRESENT)
    return round((present / len(statuses)) * 100) if statuses else 0


def readiness_state(values: dict[str, TruthValue], archive_path: str = "", identity_confidence: str = UNKNOWN) -> str:
    if not archive_path:
        return UNKNOWN
    if identity_confidence == UNKNOWN:
        return UNKNOWN
    if values["validation"].status != PRESENT:
        return "NEEDS_VALIDATION"
    if values["nfo"].status != PRESENT or values["sfv"].status != PRESENT:
        return "NEEDS_DOCUMENTATION"
    if values["artwork"].status != PRESENT or values["playlist"].status != PRESENT:
        return "NEEDS_REVIEW"
    return "ARCHIVE_READY"


def processing_state_for(values: dict[str, TruthValue], archive_path: str = "") -> str:
    if not archive_path:
        return "DISCOVERED"
    if values["validation"].present and values["nfo"].present and values["sfv"].present:
        return "ARCHIVED"
    if any(values[field].present for field in ("validation", "nfo", "sfv", "playlist", "artwork")):
        return "PROCESSING"
    return "DOWNLOADED"


def primary_source(values: dict[str, TruthValue]) -> str:
    sources = {value.source for value in values.values()}
    for source in (
        "filesystem",
        SOURCE_ARCHIVE_MARKER,
        SOURCE_VALIDATED_INDEX,
        SOURCE_IDENTITY_REGISTRY,
        SOURCE_LIFECYCLE_REGISTRY,
        SOURCE_VALIDATOR_LOG,
        "validator_evidence",
        "archive_registry",
        "metadata_cache",
    ):
        if source in sources:
            return source
    return "none"


def filesystem_artifacts(
    archive_path: str | Path | None,
    detected: AlbumArtifacts | None = None,
) -> dict[str, TruthValue]:
    if not archive_path:
        return {}
    detected = detected or detect_artifacts(archive_path)
    if not detected.available:
        return {}
    return {
        "validation": _file_truth(
            detected.named_file(VALIDATION_MARKER_FILENAME, case_sensitive=False),
            SOURCE_ARCHIVE_MARKER,
            present_reason="Archive validation marker exists.",
            missing_reason="Archive validation marker is missing.",
            confidence=CONFIDENCE_HIGH,
        ),
        "nfo": _artifact_truth(detected.preferred_file("nfo", ("release.nfo",))),
        "sfv": _artifact_truth(detected.preferred_file("sfv", ("release.sfv",))),
        "playlist": _artifact_truth(detected.preferred_file("playlist", ("playlist.m3u8",))),
        "artwork": _artifact_truth(detected.preferred_file("artwork", PREFERRED_ARTWORK_FILENAMES)),
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

    if field in filesystem and field != "validation":
        return filesystem[field]

    if field == "validation":
        return validation_truth(filesystem, validator, registry)

    registry_key = "validation_log" if field == "validation" else field
    if registry_key in registry:
        path = registry.get(f"{registry_key}_path") or registry.get(f"{field}_path") or ""
        return _bool_truth(bool(registry.get(registry_key)), "archive_registry", str(path))

    return TruthValue(UNKNOWN, "none", reason="no_evidence")


def validation_truth(
    filesystem: dict[str, TruthValue],
    validator: dict[str, Any],
    registry: dict[str, Any],
) -> TruthValue:
    archive_marker = filesystem.get("validation")
    if archive_marker and archive_marker.present:
        return archive_marker

    candidates: list[TruthValue] = []
    if validator.get("validated_index"):
        candidates.append(
            TruthValue(
                PRESENT,
                SOURCE_VALIDATED_INDEX,
                reason=validator.get("validation_reason") or "Album ID is present in validated_albums.json.",
                confidence=validator.get("validation_confidence") or CONFIDENCE_HIGH,
            )
        )
    if validator.get("identity_registry"):
        candidates.append(
            TruthValue(
                PRESENT,
                SOURCE_IDENTITY_REGISTRY,
                str(validator.get("validation_log_path") or ""),
                validator.get("validation_reason") or "Identity Registry contains validation evidence for this release.",
                validator.get("validation_confidence") or CONFIDENCE_HIGH,
            )
        )
    if validator.get("lifecycle_registry"):
        candidates.append(
            TruthValue(
                PRESENT,
                SOURCE_LIFECYCLE_REGISTRY,
                str(validator.get("validation_log_path") or ""),
                validator.get("validation_reason") or "Lifecycle Registry marks this album as validated.",
                validator.get("validation_confidence") or CONFIDENCE_MEDIUM,
            )
        )
    validation = validator.get("validation")
    if validation is not None:
        source = validator.get("validation_source") or SOURCE_VALIDATED_INDEX
        confidence = validator.get("validation_confidence") or (CONFIDENCE_HIGH if bool(validation) else CONFIDENCE_NONE)
        reason = validator.get("validation_reason") or (
            "Validation evidence was supplied by caller." if bool(validation) else "Caller supplied missing validation evidence."
        )
        candidates.append(TruthValue(PRESENT if bool(validation) else MISSING, source, reason=reason, confidence=confidence))
    validation_path = validator.get("validation_log_path") or validator.get("path")
    if validator.get("validator_log") or validation_path:
        candidates.append(
            TruthValue(
                PRESENT,
                SOURCE_VALIDATOR_LOG,
                str(validation_path or ""),
                validator.get("validation_reason") or "Validator log evidence exists.",
                validator.get("validation_confidence") or CONFIDENCE_LOW,
            )
        )

    if registry.get("validation_log"):
        path = registry.get("validation_log_path") or ""
        candidates.append(TruthValue(PRESENT, SOURCE_ARCHIVE_MARKER, str(path), "Archive Registry detected validation marker.", CONFIDENCE_HIGH))

    present_candidates = [candidate for candidate in candidates if candidate.present]
    if present_candidates:
        return sorted(present_candidates, key=lambda item: source_rank(item.source), reverse=True)[0]

    if archive_marker:
        return TruthValue(MISSING, SOURCE_MISSING, reason="No validation evidence found.", confidence=CONFIDENCE_NONE)
    return TruthValue(MISSING, SOURCE_MISSING, reason="No validation evidence found.", confidence=CONFIDENCE_NONE)


def metadata_truth(metadata_state: str | None, metadata_album: dict[str, Any] | None) -> TruthValue:
    if metadata_state == "CACHED" or bool(metadata_album):
        return TruthValue(PRESENT, "metadata_cache")
    if metadata_state in {"AVAILABLE_NOT_CACHED", "MISSING"}:
        return TruthValue(MISSING, "metadata_cache", reason=metadata_state)
    return TruthValue(UNKNOWN, "metadata_cache", reason=metadata_state or "unknown")


def _file_truth(
    path: Path | None,
    source: str,
    *,
    present_reason: str = "",
    missing_reason: str = "",
    confidence: str = "",
) -> TruthValue:
    if path:
        return TruthValue(PRESENT, source, str(path), present_reason, confidence)
    return TruthValue(MISSING, source, reason=missing_reason, confidence=CONFIDENCE_NONE if source == SOURCE_ARCHIVE_MARKER else confidence)


def _artifact_truth(path: Path | None) -> TruthValue:
    return TruthValue(PRESENT, "filesystem", str(path)) if path else TruthValue(MISSING, "filesystem")


def _bool_truth(value: bool, source: str, path: str = "") -> TruthValue:
    return TruthValue(PRESENT if value else MISSING, source, path)


def _ratio(count: int, total: int) -> float:
    if total == 0:
        return 0.0
    return round(count / total, 4)
