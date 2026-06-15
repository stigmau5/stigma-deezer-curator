from pathlib import Path

from curator.lifecycle import build_lifecycle_registry, write_registry, write_reports


def main() -> None:
    root = Path(__file__).resolve().parent
    registry = build_lifecycle_registry(root / "data")
    write_registry(registry, root / "data" / "lifecycle_registry.json")
    write_reports(registry, root / "reports")

    total = registry["summary"]["total_albums"]
    print(f"Wrote lifecycle registry for {total} album(s).")


if __name__ == "__main__":
    main()
