from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Any

from audio_division.actions import action_summary


@dataclass(frozen=True)
class OperationDefinition:
    id: str
    title: str
    description: str
    required_inputs: tuple[str, ...]
    capability: str
    risk_level: str
    action_type: str

    def to_dict(self) -> dict:
        data = asdict(self)
        data["required_inputs"] = list(self.required_inputs)
        return data


def default_operations() -> dict[str, OperationDefinition]:
    operations = [
        OperationDefinition(
            id="validate_album",
            title="Validate Album",
            description="Prepare a validation request for an archive album folder.",
            required_inputs=("album_folder",),
            capability="validate_album",
            risk_level="read_only_external_tool",
            action_type="missing_validation",
        ),
        OperationDefinition(
            id="revalidate_album",
            title="Revalidate Album",
            description="Prepare a repeat validation request for an archive album folder.",
            required_inputs=("album_folder",),
            capability="validate_album",
            risk_level="read_only_external_tool",
            action_type="missing_validation",
        ),
        OperationDefinition(
            id="generate_nfo",
            title="Generate NFO",
            description="Prepare an NFO generation request for a validated album.",
            required_inputs=("album_folder", "metadata"),
            capability="generate_nfo",
            risk_level="writes_album_documentation",
            action_type="missing_nfo",
        ),
        OperationDefinition(
            id="generate_sfv",
            title="Generate SFV",
            description="Prepare an SFV generation request for an archive album.",
            required_inputs=("album_folder",),
            capability="generate_sfv",
            risk_level="writes_album_documentation",
            action_type="missing_sfv",
        ),
        OperationDefinition(
            id="open_album_folder",
            title="Open Album Folder",
            description="Prepare a request to open an album folder in the file manager.",
            required_inputs=("album_folder",),
            capability="open_album_folder",
            risk_level="read_only",
            action_type="identity_review",
        ),
        OperationDefinition(
            id="refresh_metadata",
            title="Refresh Metadata",
            description="Prepare a metadata refresh request for an album.",
            required_inputs=("deezer_album_id",),
            capability="refresh_metadata",
            risk_level="network_read",
            action_type="missing_metadata",
        ),
    ]
    return {operation.id: operation for operation in operations}


def operation_candidate_counts(
    actions: list[dict[str, Any]],
    operations: dict[str, OperationDefinition] | None = None,
) -> dict[str, int]:
    operations = operations or default_operations()
    by_category = action_summary(actions)["by_category"]
    return {operation.id: by_category.get(operation.action_type, 0) for operation in operations.values()}


def operation_summary(actions: list[dict[str, Any]]) -> dict[str, Any]:
    operations = default_operations()
    counts = operation_candidate_counts(actions, operations)
    return {
        "total_operations": len(operations),
        "candidate_counts": counts,
        "operations": {operation_id: operation.to_dict() for operation_id, operation in operations.items()},
    }
