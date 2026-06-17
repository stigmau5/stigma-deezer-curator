from pathlib import Path

from audio_division.artifacts import (
    album_paths_from_identity_registry,
    scan_archive_artifacts,
    write_archive_artifact_report,
)
from audio_division.dashboard import load_json


def main() -> None:
    root = Path(__file__).resolve().parent
    identity = load_json(root / "data" / "identity_registry.json")
    report = scan_archive_artifacts(album_paths_from_identity_registry(identity))
    write_archive_artifact_report(report, root / "reports")
    print(f"Wrote archive artifact report for {report['total_albums_scanned']} album folder(s).")


if __name__ == "__main__":
    main()
