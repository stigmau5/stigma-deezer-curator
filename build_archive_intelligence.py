from pathlib import Path

from curator.archive_intelligence import (
    load_lifecycle_registry,
    write_archive_intelligence_reports,
)


def main() -> None:
    root = Path(__file__).resolve().parent
    registry = load_lifecycle_registry(root / "data" / "lifecycle_registry.json")
    write_archive_intelligence_reports(registry, root / "reports")

    total = len(registry.get("albums", []))
    print(f"Wrote archive intelligence reports for {total} album(s).")


if __name__ == "__main__":
    main()
