from __future__ import annotations

import shlex
from dataclasses import asdict, dataclass
from typing import Any, Sequence


SETTINGS_TOOLS_ROUTE = "settings.tools"


@dataclass(frozen=True)
class ActionGuidance:
    message: str
    tool: str
    setting_key: str
    settings_route: str
    action_label: str
    suggested_action: str
    command: str = ""

    def to_dict(self) -> dict[str, str]:
        return asdict(self)


TOOL_METADATA = {
    "audio_division": {
        "label": "Audio Division",
        "setting_key": "audio_division_path",
        "settings_label": "Audio Division",
    },
    "validator": {
        "label": "FLAC Validator",
        "setting_key": "flac_validator_path",
        "settings_label": "Validator",
    },
    "file_manager": {
        "label": "File Manager",
        "setting_key": "file_manager_path",
        "settings_label": "File Manager",
    },
    "nfo_generator": {
        "label": "NFO Generator",
        "setting_key": "nfo_generator_path",
        "settings_label": "legacy NFO Generator path",
    },
    "sfv_generator": {
        "label": "SFV Generator",
        "setting_key": "sfv_generator_path",
        "settings_label": "legacy SFV Generator path",
    },
}


OPERATION_TO_TOOL = {
    "generate_nfo": "nfo_generator",
    "generate_sfv": "sfv_generator",
    "validate_album": "validator",
    "revalidate_album": "validator",
    "open_album_folder": "file_manager",
    "process_album": "audio_division",
    "validate_downloaded_release": "validator",
}


def operation_tool_id(operation_id: str) -> str:
    return OPERATION_TO_TOOL.get(operation_id, "")


def missing_tool_guidance(tool_id: str) -> ActionGuidance:
    meta = _tool_meta(tool_id)
    label = meta["label"]
    settings_label = meta["settings_label"]
    return ActionGuidance(
        message=f"{label} is not configured.",
        tool=label,
        setting_key=meta["setting_key"],
        settings_route=SETTINGS_TOOLS_ROUTE,
        action_label="Open Settings",
        suggested_action=f"Open Settings > Tools and set {settings_label}.",
    )


def command_failure_guidance(
    tool_id: str,
    command: Sequence[Any],
    failure: BaseException | str,
) -> ActionGuidance:
    meta = _tool_meta(tool_id)
    label = meta["label"]
    command_text = format_command(command)
    detail = str(failure).strip() or "Command failed."
    prefix = f"{label} failed"
    if _is_permission_denied(failure):
        detail = "Permission denied."
        prefix = f"{label} permission denied"
    message = f"{prefix}: {detail} Command attempted: {command_text}"
    return ActionGuidance(
        message=message,
        tool=label,
        setting_key=meta["setting_key"],
        settings_route=SETTINGS_TOOLS_ROUTE,
        action_label="Open Settings",
        suggested_action=(
            f"Check that the configured {meta['settings_label']} exists and is executable, "
            "or choose a different path in Settings > Tools."
        ),
        command=command_text,
    )


def apply_guidance(result: dict[str, Any], guidance: ActionGuidance | None) -> dict[str, Any]:
    if guidance is None:
        return result
    result["message"] = guidance.message
    result["guidance"] = guidance.to_dict()
    return result


def guidance_summary(result: dict[str, Any]) -> str:
    guidance = result.get("guidance")
    if not isinstance(guidance, dict):
        return str(result.get("message") or result.get("stderr") or "")
    suggested = str(guidance.get("suggested_action") or "").strip()
    message = str(result.get("message") or result.get("stderr") or guidance.get("message") or "").strip()
    if suggested and suggested not in message:
        return f"{message} {suggested}"
    return message


def format_command(command: Sequence[Any]) -> str:
    return " ".join(shlex.quote(str(part)) for part in command)


def _tool_meta(tool_id: str) -> dict[str, str]:
    return TOOL_METADATA.get(
        tool_id,
        {
            "label": tool_id.replace("_", " ").title() or "Configured Tool",
            "setting_key": "",
            "settings_label": "tool path",
        },
    )


def _is_permission_denied(value: BaseException | str) -> bool:
    if isinstance(value, PermissionError):
        return True
    return "permission denied" in str(value).lower()
