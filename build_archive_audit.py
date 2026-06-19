import json
from pathlib import Path

from audio_division.archive_audit import audit_archive, write_archive_audit
from audio_division.settings import load_audio_division_settings


def main() -> None:
    root = Path(__file__).resolve().parent
    data_dir = root / "data"
    settings = load_audio_division_settings(data_dir / "audio_division_settings.json")
    registry_path = data_dir / "archive_registry.json"
    registry = json.loads(registry_path.read_text(encoding="utf-8")) if registry_path.exists() else {}
    archive_root = Path(registry.get("archive_root") or settings.get("archive_paths", {}).get("main_archive_root", ""))
    report = audit_archive(registry, archive_root)
    reports_dir = Path(settings.get("reports", {}).get("reports_directory") or root / "reports")
    if not reports_dir.is_absolute():
        reports_dir = root / reports_dir
    write_archive_audit(report, reports_dir)
    summary = report["summary"]
    print(
        "Wrote archive audit "
        f"({summary['albums_scanned']} scanned, {summary['warnings']} warnings, {summary['errors']} errors)."
    )


if __name__ == "__main__":
    main()
