from __future__ import annotations

import os
import shutil
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any, Iterable


TOOL_AUDIO_DIVISION = "audio_division"
TOOL_VALIDATOR = "validator"
TOOL_FILE_MANAGER = "file_manager"

TOOL_SETTING_KEYS = {
    TOOL_AUDIO_DIVISION: "audio_division_path",
    TOOL_VALIDATOR: "flac_validator_path",
    TOOL_FILE_MANAGER: "file_manager_path",
}

TOOL_LABELS = {
    TOOL_AUDIO_DIVISION: "Audio Division",
    TOOL_VALIDATOR: "Validator",
    TOOL_FILE_MANAGER: "File Manager",
}

TOOL_COMMAND_NAMES = {
    TOOL_AUDIO_DIVISION: (
        "stigma-audio-division",
        "stigma_audio_division",
        "audio-division",
        "audio_division",
    ),
    TOOL_VALIDATOR: (
        "stigma-flac-validator",
        "stigma_flac_validator",
        "flac-validator",
        "flac_validator",
    ),
    TOOL_FILE_MANAGER: ("xdg-open", "open"),
}

TOOL_REPOSITORY_NAMES = {
    TOOL_AUDIO_DIVISION: (
        "audio-division",
        "stigma-audio-division",
        "stigma_audio_division",
        "audio_division",
    ),
    TOOL_VALIDATOR: (
        "stigma-flac-validator",
        "stigma_flac_validator",
        "flac-validator",
        "flac_validator",
    ),
    TOOL_FILE_MANAGER: (),
}


@dataclass(frozen=True)
class ToolDiscovery:
    tool_id: str
    label: str
    status: str
    resolved_path: str
    version: str
    candidates: tuple[str, ...]
    source: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def apply_tool_discovery(
    settings: dict[str, Any],
    *,
    base_dir: Path | None = None,
    home_dir: Path | None = None,
    path_values: str | None = None,
) -> dict[str, Any]:
    tools = settings.setdefault("tools", {})
    for tool_id in (TOOL_AUDIO_DIVISION, TOOL_VALIDATOR):
        key = TOOL_SETTING_KEYS[tool_id]
        if str(tools.get(key) or "").strip():
            continue
        discovery = discover_tool(tool_id, settings, base_dir=base_dir, home_dir=home_dir, path_values=path_values)
        if discovery.status == "Installed" and len(discovery.candidates) == 1:
            tools[key] = discovery.resolved_path
    return settings


def discover_configured_tools(
    settings: dict[str, Any],
    *,
    base_dir: Path | None = None,
    home_dir: Path | None = None,
    path_values: str | None = None,
) -> dict[str, ToolDiscovery]:
    return {
        tool_id: discover_tool(tool_id, settings, base_dir=base_dir, home_dir=home_dir, path_values=path_values)
        for tool_id in (TOOL_AUDIO_DIVISION, TOOL_VALIDATOR, TOOL_FILE_MANAGER)
    }


def discover_tool(
    tool_id: str,
    settings: dict[str, Any] | None = None,
    *,
    base_dir: Path | None = None,
    home_dir: Path | None = None,
    path_values: str | None = None,
) -> ToolDiscovery:
    settings = settings or {}
    configured = str(settings.get("tools", {}).get(TOOL_SETTING_KEYS.get(tool_id, ""), "") or "").strip()
    candidates = _candidate_paths(tool_id, configured, base_dir=base_dir, home_dir=home_dir, path_values=path_values)
    if configured:
        resolved = _resolve_configured_path(configured, path_values)
        if resolved:
            return _discovery(tool_id, "Installed", resolved, candidates, "configured")
        return _discovery(tool_id, "Not Found", "", candidates, "configured")
    if len(candidates) == 1:
        return _discovery(tool_id, "Installed", candidates[0], candidates, "discovered")
    if len(candidates) > 1:
        return _discovery(tool_id, "Multiple Found", "", candidates, "discovered")
    return _discovery(tool_id, "Not Found", "", candidates, "discovered")


def _candidate_paths(
    tool_id: str,
    configured: str,
    *,
    base_dir: Path | None,
    home_dir: Path | None,
    path_values: str | None,
) -> tuple[str, ...]:
    candidates: list[str] = []
    configured_path = _resolve_configured_path(configured, path_values) if configured else ""
    if configured_path:
        candidates.append(configured_path)

    for root in _search_roots(base_dir, home_dir):
        for repo_name in TOOL_REPOSITORY_NAMES.get(tool_id, ()):
            repo = root / repo_name
            candidates.extend(_existing_tool_paths(repo, TOOL_COMMAND_NAMES.get(tool_id, ())))

    for command in TOOL_COMMAND_NAMES.get(tool_id, ()):
        resolved = _which(command, path_values)
        if resolved:
            candidates.append(resolved)
    return _unique_paths(candidates)


def _search_roots(base_dir: Path | None, home_dir: Path | None) -> tuple[Path, ...]:
    roots: list[Path] = []
    if base_dir is not None:
        base = Path(base_dir).expanduser()
        roots.extend([base.parent, base.parent.parent])
    home = Path(home_dir).expanduser() if home_dir is not None else Path.home()
    roots.extend([home / "apps", home / "projects"])
    return tuple(root for root in roots if root)


def _existing_tool_paths(repo: Path, commands: Iterable[str]) -> list[str]:
    if not repo.exists():
        return []
    candidates: list[Path] = []
    for command in commands:
        candidates.extend(
            (
                repo / command,
                repo / "bin" / command,
                repo / "src" / command,
            )
        )
    candidates.extend((repo / "main.py", repo / "app.py"))
    return [str(path) for path in candidates if path.exists()]


def _resolve_configured_path(value: str, path_values: str | None) -> str:
    if not value:
        return ""
    path = Path(value).expanduser()
    if path.exists():
        return str(path)
    return _which(value, path_values)


def _which(command: str, path_values: str | None) -> str:
    if not command:
        return ""
    resolved = shutil.which(command, path=path_values if path_values is not None else os.environ.get("PATH"))
    return str(resolved or "")


def _unique_paths(paths: Iterable[str]) -> tuple[str, ...]:
    unique: list[str] = []
    seen = set()
    for path in paths:
        normalized = str(Path(path).expanduser())
        key = os.path.normcase(normalized)
        if key in seen:
            continue
        seen.add(key)
        unique.append(normalized)
    return tuple(unique)


def _discovery(
    tool_id: str,
    status: str,
    resolved_path: str,
    candidates: tuple[str, ...],
    source: str,
) -> ToolDiscovery:
    return ToolDiscovery(
        tool_id=tool_id,
        label=TOOL_LABELS.get(tool_id, tool_id.replace("_", " ").title()),
        status=status,
        resolved_path=resolved_path,
        version=_version_from_files(resolved_path),
        candidates=candidates,
        source=source,
    )


def _version_from_files(resolved_path: str) -> str:
    if not resolved_path:
        return "Unavailable"
    path = Path(resolved_path).expanduser()
    roots = [path if path.is_dir() else path.parent, path.parent.parent]
    for root in roots:
        version_path = root / "VERSION"
        if version_path.exists() and version_path.is_file():
            try:
                value = version_path.read_text(encoding="utf-8").strip().splitlines()[0]
            except Exception:
                value = ""
            if value:
                return value
    return "Unavailable"
