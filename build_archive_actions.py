from pathlib import Path

from audio_division.actions import generate_archive_actions, write_archive_actions_report
from audio_division.dashboard import load_json


def main() -> None:
    root = Path(__file__).resolve().parent
    data_dir = root / "data"
    actions = generate_archive_actions(
        load_json(data_dir / "lifecycle_registry.json"),
        load_json(data_dir / "identity_registry.json"),
        load_json(data_dir / "metadata_cache.json"),
    )
    write_archive_actions_report(actions, root / "reports")
    print(f"Wrote archive actions report with {len(actions)} action(s).")


if __name__ == "__main__":
    main()
