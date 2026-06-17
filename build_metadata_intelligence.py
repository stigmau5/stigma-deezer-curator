from pathlib import Path

from audio_division.dashboard import load_json
from audio_division.metadata_status import write_metadata_reports


def main() -> None:
    root = Path(__file__).resolve().parent
    data_dir = root / "data"
    lifecycle = load_json(data_dir / "lifecycle_registry.json")
    metadata = load_json(data_dir / "metadata_cache.json")
    write_metadata_reports(lifecycle, metadata, root / "reports")
    print("Wrote metadata intelligence reports.")


if __name__ == "__main__":
    main()
