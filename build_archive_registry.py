from pathlib import Path

from audio_division.archive_registry import build_archive_registry, write_archive_registry
from audio_division.settings import load_audio_division_settings


def main() -> None:
    root = Path(__file__).resolve().parent
    data_dir = root / "data"
    settings = load_audio_division_settings(data_dir / "audio_division_settings.json")
    archive_root = Path(settings.get("archive_paths", {}).get("main_archive_root", ""))
    registry = build_archive_registry(archive_root)
    write_archive_registry(registry, data_dir, root / "reports")
    print(f"Wrote archive registry with {registry['summary']['album_folders']} album folder(s).")


if __name__ == "__main__":
    main()
