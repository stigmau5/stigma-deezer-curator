from __future__ import annotations

from dataclasses import asdict, dataclass


@dataclass(frozen=True)
class ToolDefinition:
    id: str
    title: str
    description: str
    capabilities: tuple[str, ...]
    executable: bool = False

    def to_dict(self) -> dict:
        data = asdict(self)
        data["capabilities"] = list(self.capabilities)
        return data


def default_tool_registry() -> dict[str, ToolDefinition]:
    tools = [
        ToolDefinition(
            id="stigma_flac_validator",
            title="STiGMA FLAC Validator",
            description="Validates album integrity and emits validation evidence.",
            capabilities=("validate_album", "validate_directory"),
        ),
        ToolDefinition(
            id="stigma_nfo_generator",
            title="STiGMA Audio Division NFO Generator",
            description="Generates or regenerates archive NFO documentation.",
            capabilities=("generate_nfo", "regenerate_nfo"),
        ),
        ToolDefinition(
            id="stigma_sfv_generator",
            title="STiGMA Audio Division SFV Generator",
            description="Generates or regenerates archive SFV checksum files.",
            capabilities=("generate_sfv", "regenerate_sfv"),
        ),
    ]
    return {tool.id: tool for tool in tools}


def tools_with_capability(registry: dict[str, ToolDefinition], capability: str) -> list[ToolDefinition]:
    return [tool for tool in registry.values() if capability in tool.capabilities]
