from pathlib import Path

from audio_division.library import library_from_data_dir
from audio_division.opportunities import derive_hub_opportunities, write_hub_opportunity_reports
from audio_division.settings import load_audio_division_settings


def main() -> None:
    root = Path(__file__).resolve().parent
    data_dir = root / "data"
    settings = load_audio_division_settings(data_dir / "audio_division_settings.json")
    archive_root = settings.get("archive_paths", {}).get("main_archive_root", "")
    library = library_from_data_dir(data_dir, Path(archive_root) if archive_root else None)
    opportunities = derive_hub_opportunities(library)
    write_hub_opportunity_reports(opportunities, root / "reports")
    print(f"Wrote opportunities center reports for {len(opportunities)} album(s).")


if __name__ == "__main__":
    main()
