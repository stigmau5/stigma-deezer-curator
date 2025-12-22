from pathlib import Path
import re

from curator.metadata import get_album_metadata
from curator.utils import safe_filename


def album_id_from_url(url: str) -> str | None:
    match = re.search(r"/album/(\d+)", url)
    return match.group(1) if match else None


def write_by_artist(album_urls: list[str], output_dir: Path) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)

    for url in album_urls:
        album_id = album_id_from_url(url)
        if not album_id:
            continue

        metadata = get_album_metadata(album_id)
        if not metadata:
            continue

        filename = safe_filename(metadata.artist) + ".txt"
        path = output_dir / filename

        existing_lines: set[str] = set()
        if path.exists():
            with path.open("r", encoding="utf-8") as f:
                existing_lines = {line.rstrip() for line in f}

        entry_lines = [
            f"- {metadata.title}",
            f"  {url}",
        ]

        # Avoid duplicate album URLs
        if url in existing_lines:
            continue

        with path.open("a", encoding="utf-8") as f:
            if not existing_lines:
                f.write(f"# Artist: {metadata.artist}\n\n")

            for line in entry_lines:
                f.write(line + "\n")
