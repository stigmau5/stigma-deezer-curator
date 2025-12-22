import argparse
from pathlib import Path

from curator.curate import run_curation
from curator.write import write_by_artist


def main() -> None:
    parser = argparse.ArgumentParser(
        prog="stigma-deezer-curator",
        description="STiGMA Deezer Curator — curate Deezer links into artist files",
    )

    parser.add_argument(
        "--inbox",
        type=Path,
        default=Path("data/inbox.txt"),
        help="Path to inbox.txt (default: data/inbox.txt)",
    )

    parser.add_argument(
        "--log",
        type=Path,
        default=Path("data/curated.log"),
        help="Path to curated log (default: data/curated.log)",
    )

    parser.add_argument(
        "--artists",
        type=Path,
        default=Path("data/artists"),
        help="Directory for artist output (default: data/artists)",
    )

    args = parser.parse_args()

    if not args.inbox.exists():
        print(f"❌ Inbox not found: {args.inbox}")
        return

    print("▶ Running STiGMA Deezer Curator")
    print(f"  Inbox:   {args.inbox}")
    print(f"  Log:     {args.log}")
    print(f"  Artists: {args.artists}")
    print()

    album_links = run_curation(
        inbox_path=args.inbox,
        log_path=args.log,
    )

    write_by_artist(album_links, args.artists)

    print("✔ Done")
    print(f"  New album links written: {len(album_links)}")
