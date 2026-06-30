from __future__ import annotations

import os
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

from audio_division.tool_discovery import (
    TOOL_AUDIO_DIVISION,
    TOOL_FILE_MANAGER,
    TOOL_VALIDATOR,
    ToolDiscovery,
    discover_configured_tools,
)


STATUS_PASS = "PASS"
STATUS_WARNING = "WARNING"
STATUS_FAIL = "FAIL"

SEVERITY_INFO = "INFO"
SEVERITY_LOW = "LOW"
SEVERITY_MEDIUM = "MEDIUM"
SEVERITY_HIGH = "HIGH"


@dataclass(frozen=True)
class EnvironmentCheck:
    name: str
    status: str
    severity: str
    evidence: str
    suggested_action: str
    category: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class EnvironmentHealthReport:
    status: str
    checks: tuple[EnvironmentCheck, ...]
    summary: dict[str, int]

    def to_dict(self) -> dict[str, Any]:
        return {
            "status": self.status,
            "summary": dict(self.summary),
            "checks": [check.to_dict() for check in self.checks],
        }


def environment_health_report(
    settings: dict[str, Any],
    *,
    base_dir: Path | None = None,
    data_dir: Path | None = None,
    home_dir: Path | None = None,
    path_values: str | None = None,
) -> EnvironmentHealthReport:
    base = Path(base_dir).expanduser() if base_dir is not None else Path.cwd()
    data = Path(data_dir).expanduser() if data_dir is not None else base / "data"
    checks: list[EnvironmentCheck] = []
    checks.extend(_configuration_checks(settings))
    checks.extend(_filesystem_checks(settings, base, data))
    checks.extend(_tool_checks(settings, base, home_dir=home_dir, path_values=path_values))
    checks.extend(_provider_checks(settings, data))
    summary = _summary(checks)
    status = STATUS_FAIL if summary[STATUS_FAIL] else STATUS_WARNING if summary[STATUS_WARNING] else STATUS_PASS
    return EnvironmentHealthReport(status=status, checks=tuple(checks), summary=summary)


def _configuration_checks(settings: dict[str, Any]) -> list[EnvironmentCheck]:
    checks = []
    required = (
        ("archive_paths", "main_archive_root", "Main Archive Root"),
        ("archive_paths", "incoming_root", "Incoming Root"),
        ("reports", "reports_directory", "Reports Directory"),
        ("metadata", "metadata_cache_path", "Metadata Cache"),
        ("validator", "validated_index_path", "Validation Index"),
        ("tools", "audio_division_path", "Audio Division"),
        ("tools", "flac_validator_path", "FLAC Validator"),
        ("tools", "file_manager_path", "File Manager"),
    )
    for section, key, label in required:
        value = str(settings.get(section, {}).get(key) or "").strip()
        checks.append(
            _check(
                f"Required setting: {label}",
                STATUS_PASS if value else STATUS_FAIL,
                SEVERITY_HIGH if not value else SEVERITY_INFO,
                f"{section}.{key} = {value or '<empty>'}",
                "Configure this setting before running acquisition or archive operations." if not value else "No action required.",
                "Configuration",
            )
        )
    return checks


def _filesystem_checks(settings: dict[str, Any], base_dir: Path, data_dir: Path) -> list[EnvironmentCheck]:
    archive_root = _settings_path(settings, base_dir, "archive_paths", "main_archive_root")
    incoming_root = _settings_path(settings, base_dir, "archive_paths", "incoming_root")
    reports_dir = _settings_path(settings, base_dir, "reports", "reports_directory")
    metadata_cache = _settings_path(settings, base_dir, "metadata", "metadata_cache_path")
    validation_index = _settings_path(settings, base_dir, "validator", "validated_index_path")
    return [
        _path_exists_check("Archive Root exists", archive_root, "Filesystem", required=True),
        _path_exists_check("Incoming Root exists", incoming_root, "Filesystem", required=True),
        _directory_writable_check("Reports directory writable", reports_dir, "Filesystem"),
        _file_readable_check("Metadata cache readable", metadata_cache or data_dir / "metadata_cache.json", "Filesystem"),
        _file_readable_check("Validation index readable", validation_index or data_dir / "validated_albums.json", "Filesystem"),
        _resolved_path_check("Archive Root resolves", archive_root, "Configuration", required=True),
        _resolved_path_check("Incoming Root resolves", incoming_root, "Configuration", required=True),
    ]


def _tool_checks(
    settings: dict[str, Any],
    base_dir: Path,
    *,
    home_dir: Path | None,
    path_values: str | None,
) -> list[EnvironmentCheck]:
    discoveries = discover_configured_tools(settings, base_dir=base_dir, home_dir=home_dir, path_values=path_values)
    labels = {
        TOOL_AUDIO_DIVISION: "Audio Division available",
        TOOL_VALIDATOR: "FLAC Validator available",
        TOOL_FILE_MANAGER: "File manager available",
    }
    return [_tool_check(labels[tool_id], discovery) for tool_id, discovery in discoveries.items()]


def _provider_checks(settings: dict[str, Any], data_dir: Path) -> list[EnvironmentCheck]:
    providers = settings.get("providers", {}) if isinstance(settings.get("providers"), dict) else {}
    deezer = providers.get("deezer", {}) if isinstance(providers.get("deezer"), dict) else {}
    if deezer:
        return [
            _check(
                "Deezer configuration present",
                STATUS_PASS,
                SEVERITY_INFO,
                "providers.deezer is configured.",
                "No action required.",
                "Providers",
            )
        ]
    artist_files = tuple((data_dir / "artists").glob("*.txt")) if (data_dir / "artists").exists() else tuple()
    if artist_files:
        return [
            _check(
                "Deezer configuration present",
                STATUS_PASS,
                SEVERITY_LOW,
                f"Found {len(artist_files)} Deezer-backed artist projection files.",
                "Add explicit providers.deezer settings when provider management is introduced.",
                "Providers",
            )
        ]
    return [
        _check(
            "Deezer configuration present",
            STATUS_WARNING,
            SEVERITY_MEDIUM,
            "No providers.deezer configuration or Deezer artist projections were found.",
            "Configure Deezer provider settings when provider management is available.",
            "Providers",
        )
    ]


def _tool_check(name: str, discovery: ToolDiscovery) -> EnvironmentCheck:
    if discovery.status == "Installed":
        return _check(
            name,
            STATUS_PASS,
            SEVERITY_INFO,
            f"Resolved path: {discovery.resolved_path}",
            "No action required.",
            "External Tools",
        )
    if discovery.status == "Multiple Found":
        return _check(
            name,
            STATUS_WARNING,
            SEVERITY_MEDIUM,
            f"Multiple candidates: {', '.join(discovery.candidates)}",
            "Select the intended tool path in Settings.",
            "External Tools",
        )
    return _check(
        name,
        STATUS_FAIL,
        SEVERITY_HIGH,
        "Tool was not found.",
        "Install the tool or configure its path in Settings.",
        "External Tools",
    )


def _path_exists_check(name: str, path: Path | None, category: str, *, required: bool) -> EnvironmentCheck:
    if path and path.exists() and path.is_dir():
        return _check(name, STATUS_PASS, SEVERITY_INFO, str(path), "No action required.", category)
    return _check(
        name,
        STATUS_FAIL if required else STATUS_WARNING,
        SEVERITY_HIGH if required else SEVERITY_MEDIUM,
        str(path) if path else "Path is not configured.",
        "Create the directory or update Settings to the correct path.",
        category,
    )


def _directory_writable_check(name: str, path: Path | None, category: str) -> EnvironmentCheck:
    if path and path.exists() and path.is_dir() and os.access(path, os.W_OK):
        return _check(name, STATUS_PASS, SEVERITY_INFO, str(path), "No action required.", category)
    if path and not path.exists() and os.access(path.parent, os.W_OK):
        return _check(
            name,
            STATUS_WARNING,
            SEVERITY_MEDIUM,
            f"{path} does not exist, but parent is writable.",
            "Create the reports directory before generating reports.",
            category,
        )
    return _check(
        name,
        STATUS_FAIL,
        SEVERITY_HIGH,
        str(path) if path else "Reports directory is not configured.",
        "Configure a writable reports directory.",
        category,
    )


def _file_readable_check(name: str, path: Path | None, category: str) -> EnvironmentCheck:
    if path and path.exists() and path.is_file() and os.access(path, os.R_OK):
        return _check(name, STATUS_PASS, SEVERITY_INFO, str(path), "No action required.", category)
    return _check(
        name,
        STATUS_WARNING,
        SEVERITY_MEDIUM,
        str(path) if path else "File is not configured.",
        "Create or refresh this local data file before relying on derived workflow state.",
        category,
    )


def _resolved_path_check(name: str, path: Path | None, category: str, *, required: bool) -> EnvironmentCheck:
    if path and path.exists():
        return _check(name, STATUS_PASS, SEVERITY_INFO, str(path.resolve()), "No action required.", category)
    return _check(
        name,
        STATUS_FAIL if required else STATUS_WARNING,
        SEVERITY_HIGH if required else SEVERITY_MEDIUM,
        str(path) if path else "Path is not configured.",
        "Update Settings so this path resolves on disk.",
        category,
    )


def _settings_path(settings: dict[str, Any], base_dir: Path, section: str, key: str) -> Path | None:
    value = str(settings.get(section, {}).get(key) or "").strip()
    if not value:
        return None
    path = Path(value).expanduser()
    return path if path.is_absolute() else base_dir / path


def _check(
    name: str,
    status: str,
    severity: str,
    evidence: str,
    suggested_action: str,
    category: str,
) -> EnvironmentCheck:
    return EnvironmentCheck(
        name=name,
        status=status,
        severity=severity,
        evidence=evidence,
        suggested_action=suggested_action,
        category=category,
    )


def _summary(checks: list[EnvironmentCheck]) -> dict[str, int]:
    return {
        STATUS_PASS: sum(1 for check in checks if check.status == STATUS_PASS),
        STATUS_WARNING: sum(1 for check in checks if check.status == STATUS_WARNING),
        STATUS_FAIL: sum(1 for check in checks if check.status == STATUS_FAIL),
        "total": len(checks),
    }
