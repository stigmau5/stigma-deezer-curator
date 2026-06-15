from pathlib import Path

from curator.identity import build_identity_registry, write_identity_registry, write_identity_reports
from curator.lifecycle import load_json_file


def main() -> None:
    root = Path(__file__).resolve().parent
    lifecycle_registry = load_json_file(root / "data" / "lifecycle_registry.json")
    registry = build_identity_registry(lifecycle_registry)
    write_identity_registry(registry, root / "data" / "identity_registry.json")
    write_identity_reports(registry, root / "reports")

    total = registry["summary"]["total_releases"]
    unresolved = registry["summary"]["unresolved_validator_logs"]
    print(f"Wrote identity registry for {total} release(s); unresolved logs: {unresolved}.")


if __name__ == "__main__":
    main()
