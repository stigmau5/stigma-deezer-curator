from pathlib import Path

from audio_division.artwork_browser import write_artwork_coverage_report
from audio_division.dashboard import load_json
from audio_division.library import library_from_data_dir
from audio_division.settings import load_audio_division_settings


def main() -> None:
    root = Path(__file__).resolve().parent
    data_dir = root / "data"
    settings = load_audio_division_settings(data_dir / "audio_division_settings.json")
    archive_root = settings.get("archive_paths", {}).get("main_archive_root", "")
    library = library_from_data_dir(data_dir, Path(archive_root) if archive_root else None)
    archive_registry = load_json(data_dir / "archive_registry.json")
    write_artwork_coverage_report(library, root / "reports", archive_registry)
    print(f"Wrote artwork coverage report for {len(library.get('albums', []))} album(s).")


if __name__ == "__main__":
    main()
