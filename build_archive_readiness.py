from pathlib import Path

from audio_division.archive_readiness import write_archive_readiness_report
from audio_division.library import library_from_data_dir
from audio_division.settings import load_audio_division_settings


def main() -> None:
    root = Path(__file__).resolve().parent
    data_dir = root / "data"
    settings = load_audio_division_settings(data_dir / "audio_division_settings.json")
    archive_root = settings.get("archive_paths", {}).get("main_archive_root", "")
    library = library_from_data_dir(data_dir, Path(archive_root) if archive_root else None)
    write_archive_readiness_report(library, root / "reports")
    summary = library.get("archive_readiness_summary", {})
    print(f"Wrote archive readiness report for {summary.get('total_albums', 0)} album(s).")


if __name__ == "__main__":
    main()
