from pathlib import Path

from audio_division.library import library_from_data_dir, write_archive_path_resolution_report
from audio_division.settings import load_audio_division_settings


def main() -> None:
    root = Path(__file__).resolve().parent
    data_dir = root / "data"
    settings = load_audio_division_settings(data_dir / "audio_division_settings.json")
    archive_root = settings.get("archive_paths", {}).get("main_archive_root", "")
    library = library_from_data_dir(data_dir, Path(archive_root) if archive_root else None)
    write_archive_path_resolution_report(library, root / "reports")
    summary = library.get("summary", {})
    print(f"Wrote archive path resolution report for {summary.get('albums', 0)} album(s).")


if __name__ == "__main__":
    main()
