from pathlib import Path
import re
from datetime import datetime

from curator.metadata import get_album_metadata
from curator.utils import safe_filename


# ---------------- Helpers ----------------


def album_id_from_url(url: str) -> str | None:
    match = re.search(r"/album/(\d+)", url)
    return match.group(1) if match else None


def has_expansion_block(text: str, artist_url: str) -> bool:
    """
    Detect whether an artist file already contains
    an expansion block for this Deezer artist URL.
    """
    return f"# source: {artist_url}" in text


# ---------------- Existing behavior (unchanged) ----------------


def write_by_artist(album_urls: list[str], output_dir: Path) -> None:
    """
    Legacy writer: appends simple title + URL entries.
    This is kept intact for the existing inbox-based flow.
    """
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

        if url in existing_lines:
            continue

        with path.open("a", encoding="utf-8") as f:
            if not existing_lines:
                f.write(f"# Artist: {metadata.artist}\n\n")

            for line in entry_lines:
                f.write(line + "\n")


# ---------------- New behavior: expansion block writer ----------------


def write_expansion_block(
    *,
    artist_url: str,
    releases: dict[str, list[str]],
    output_dir: Path,
) -> bool:
    """
    Write a structured, append-only Deezer expansion block.

    Returns:
        True  -> block was written
        False -> block already existed, nothing written
    """
    output_dir.mkdir(parents=True, exist_ok=True)

    # Resolve artist name from first available release
    first_line = next(
        (line for lines in releases.values() for line in lines),
        None,
    )
    if not first_line:
        return False

    album_url = first_line.split()[0]
    album_id = album_id_from_url(album_url)
    if not album_id:
        return False

    metadata = get_album_metadata(album_id)
    if not metadata:
        return False

    artist_name = metadata.artist
    filename = safe_filename(artist_name) + ".txt"
    path = output_dir / filename

    existing_text = ""
    if path.exists():
        existing_text = path.read_text(encoding="utf-8")
        if has_expansion_block(existing_text, artist_url):
            return False

    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M")

    with path.open("a", encoding="utf-8") as f:
        if not existing_text:
            f.write(f"# Artist: {artist_name}\n\n")

        f.write("# === Deezer artist expansion ===\n")
        f.write(f"# source: {artist_url}\n")
        f.write(f"# expanded_at: {timestamp}\n\n")

        f.write("# Albums\n")
        for line in releases.get("albums", []):
            f.write(line + "\n")
        f.write("\n")

        f.write("# EPs\n")
        for line in releases.get("eps", []):
            f.write(line + "\n")
        f.write("\n")

        f.write("# Singles\n")
        for line in releases.get("singles", []):
            f.write(line + "\n")
        f.write("\n")

    return True
