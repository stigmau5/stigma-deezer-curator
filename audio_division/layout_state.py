from __future__ import annotations

import json
from typing import Any


DEFAULT_WINDOW_GEOMETRY = "1400x850"
MIN_WINDOW_WIDTH = 1100
MIN_WINDOW_HEIGHT = 650


def default_window_geometry(screen_width: int | None = None, screen_height: int | None = None) -> str:
    width = 1400
    height = 850
    if screen_width:
        width = min(width, max(MIN_WINDOW_WIDTH, screen_width - 80))
    if screen_height:
        height = min(height, max(MIN_WINDOW_HEIGHT, screen_height - 100))
    return f"{width}x{height}"


def valid_window_geometry(value: Any) -> str:
    text = str(value or "").strip()
    if not text:
        return ""
    size = text.split("+", 1)[0]
    if "x" not in size:
        return ""
    width_text, height_text = size.split("x", 1)
    try:
        width = int(width_text)
        height = int(height_text)
    except ValueError:
        return ""
    if width < MIN_WINDOW_WIDTH or height < MIN_WINDOW_HEIGHT:
        return ""
    return text


def serialize_pane_positions(positions: list[int]) -> str:
    return json.dumps([int(position) for position in positions])


def deserialize_pane_positions(value: Any) -> list[int]:
    if not value:
        return []
    try:
        data = json.loads(str(value))
    except (TypeError, ValueError):
        return []
    if not isinstance(data, list):
        return []
    positions: list[int] = []
    for item in data:
        try:
            position = int(item)
        except (TypeError, ValueError):
            continue
        if position >= 0:
            positions.append(position)
    return positions


def capture_pane_positions(pane: Any) -> list[int]:
    panes = pane.panes()
    positions = []
    for index in range(max(0, len(panes) - 1)):
        try:
            positions.append(int(pane.sashpos(index)))
        except Exception:
            continue
    return positions


def restore_pane_positions(pane: Any, positions: list[int]) -> None:
    panes = pane.panes()
    for index, position in enumerate(positions[: max(0, len(panes) - 1)]):
        try:
            pane.sashpos(index, position)
        except Exception:
            continue
