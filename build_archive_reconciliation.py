import json
from pathlib import Path

from audio_division.archive_reconciliation import reconcile_archive, write_archive_reconciliation_report
from audio_division.settings import load_audio_division_settings


def main() -> None:
    root = Path(__file__).resolve().parent
    data_dir = root / "data"
    settings = load_audio_division_settings(data_dir / "audio_division_settings.json")
    archive_root = Path(settings.get("archive_paths", {}).get("main_archive_root", ""))
    registry_path = data_dir / "archive_registry.json"
    registry = json.loads(registry_path.read_text(encoding="utf-8")) if registry_path.exists() else {}
    report = reconcile_archive(archive_root, registry)
    reports_dir = Path(settings.get("reports", {}).get("reports_directory") or root / "reports")
    if not reports_dir.is_absolute():
        reports_dir = root / reports_dir
    write_archive_reconciliation_report(report, reports_dir)
    summary = report["summary"]
    print(
        "Wrote archive reconciliation report "
        f"({summary['albums_missing']} missing, {summary['albums_added']} added, "
        f"{summary['disc_folder_album_rows']} disc rows)."
    )


if __name__ == "__main__":
    main()
