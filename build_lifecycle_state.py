from pathlib import Path

from audio_division.closed_loop_monitor import discover_incoming_albums
from audio_division.dashboard import load_json
from audio_division.lifecycle_state import merge_lifecycle_rows, write_lifecycle_state_report
from audio_division.library import library_from_data_dir
from audio_division.physical_archive import build_archive_albums
from audio_division.settings import load_audio_division_settings


def main() -> None:
    root = Path(__file__).resolve().parent
    data_dir = root / "data"
    settings = load_audio_division_settings(data_dir / "audio_division_settings.json")
    archive_root = settings.get("archive_paths", {}).get("main_archive_root", "")
    archive_root_path = Path(archive_root) if archive_root else None

    lifecycle_library = library_from_data_dir(data_dir, archive_root_path)
    archive_albums = build_archive_albums(
        load_json(data_dir / "archive_registry.json"),
        load_json(data_dir / "identity_registry.json"),
        load_json(data_dir / "metadata_cache.json"),
    )
    incoming = discover_incoming_albums(settings, archive_albums, load_json(data_dir / "processing_queue.json"))
    rows = merge_lifecycle_rows(lifecycle_library.get("albums", []), archive_albums, incoming)
    write_lifecycle_state_report(rows, root / "reports")
    print(f"Wrote lifecycle state report for {len(rows)} album(s).")


if __name__ == "__main__":
    main()
