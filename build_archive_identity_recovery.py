from pathlib import Path

from curator.archive_identity_recovery import (
    build_archive_identity_recovery,
    write_archive_identity_recovery_reports,
)
from curator.lifecycle import load_json_file


def main() -> None:
    root = Path(__file__).resolve().parent
    identity_registry = load_json_file(root / "data" / "identity_registry.json")
    lifecycle_registry = load_json_file(root / "data" / "lifecycle_registry.json")
    registry = build_archive_identity_recovery(identity_registry, lifecycle_registry)
    write_archive_identity_recovery_reports(registry, root / "reports")

    summary = registry["summary"]
    print(
        "Wrote archive identity recovery reports; "
        f"recoverable: {summary['recoverable_total']}, "
        f"unrecoverable: {summary['unrecoverable_total']}."
    )


if __name__ == "__main__":
    main()
