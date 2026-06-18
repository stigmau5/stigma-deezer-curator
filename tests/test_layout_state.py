from __future__ import annotations

from audio_division.layout_state import (
    default_window_geometry,
    deserialize_pane_positions,
    serialize_pane_positions,
    valid_window_geometry,
)
from audio_division.settings import load_audio_division_settings, save_audio_division_settings


def test_default_window_geometry_respects_small_displays():
    assert default_window_geometry(1366, 768) == "1286x668"
    assert default_window_geometry(1920, 1080) == "1400x850"


def test_window_geometry_validation():
    assert valid_window_geometry("1400x850+10+20") == "1400x850+10+20"
    assert valid_window_geometry("900x500") == ""
    assert valid_window_geometry("not-a-size") == ""


def test_pane_position_roundtrip():
    encoded = serialize_pane_positions([240, 760])
    assert deserialize_pane_positions(encoded) == [240, 760]


def test_invalid_pane_positions_fall_back_to_empty():
    assert deserialize_pane_positions("") == []
    assert deserialize_pane_positions("broken") == []
    assert deserialize_pane_positions('{"not": "a list"}') == []
    assert deserialize_pane_positions('["120", -1, "bad", 360]') == [120, 360]


def test_ui_layout_settings_persist(tmp_path):
    path = tmp_path / "audio_division_settings.json"
    settings = load_audio_division_settings(path)
    settings["ui"]["window_geometry"] = "1400x850+5+6"
    settings["ui"]["archive_main_panes"] = serialize_pane_positions([220, 640])

    save_audio_division_settings(path, settings)

    loaded = load_audio_division_settings(path)
    assert loaded["ui"]["window_geometry"] == "1400x850+5+6"
    assert deserialize_pane_positions(loaded["ui"]["archive_main_panes"]) == [220, 640]
