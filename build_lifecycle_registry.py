from pathlib import Path

from curator.lifecycle import build_lifecycle_registry, write_registry, write_reports
from curator.validator_evidence import collect_validation_evidence, write_validation_reports


def main() -> None:
    root = Path(__file__).resolve().parent
    data_dir = root / "data"
    evidence = collect_validation_evidence(data_dir)
    registry = build_lifecycle_registry(data_dir, validation_evidence=evidence)
    write_registry(registry, root / "data" / "lifecycle_registry.json")
    write_reports(registry, root / "reports")
    write_validation_reports(registry, root / "reports")

    total = registry["summary"]["total_albums"]
    print(f"Wrote lifecycle registry for {total} album(s).")


if __name__ == "__main__":
    main()
