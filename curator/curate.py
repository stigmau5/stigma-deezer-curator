from pathlib import Path

from curator.links import parse_deezer_link, LinkType
from curator.expand import expand_artist_releases
from curator.log import CuratedLog
from curator.write import write_expansion_block


def run_curation(
    inbox_path: Path,
    log_path: Path,
    artists_dir: Path,
) -> dict:
    """
    Processes inbox links.

    Behavior:
    - Album links are passed through (returned to GUI)
    - Artist links are expanded into structured, annotated blocks
    - Each inbox line is processed once (tracked in curated.log)

    Returns:
        {
            "album_urls": [...],
            "stats": {
                "albums_passed": int,
                "artists_expanded": int,
                "artists_skipped": int,
            }
        }
    """
    log = CuratedLog(log_path)

    if not inbox_path.exists():
        return {
            "album_urls": [],
            "stats": {
                "albums_passed": 0,
                "artists_expanded": 0,
                "artists_skipped": 0,
            },
        }

    with inbox_path.open("r", encoding="utf-8") as f:
        raw_links = [line.strip() for line in f if line.strip()]

    album_urls: list[str] = []

    stats = {
        "albums_passed": 0,
        "artists_expanded": 0,
        "artists_skipped": 0,
    }

    for raw in raw_links:
        if log.has(raw):
            stats["artists_skipped"] += 1
            continue

        link = parse_deezer_link(raw)

        try:
            if link.type == LinkType.ALBUM:
                album_urls.append(link.raw)
                stats["albums_passed"] += 1

            elif link.type == LinkType.ARTIST and link.id:
                releases = expand_artist_releases(link.id)

                wrote = write_expansion_block(
                    artist_url=link.raw,
                    releases=releases,
                    output_dir=artists_dir,
                )

                if wrote:
                    stats["artists_expanded"] += 1
                else:
                    stats["artists_skipped"] += 1

            # UNKNOWN links are intentionally ignored

        except Exception as exc:
            print(f"⚠️  Failed to process {raw}: {exc}")

        finally:
            log.append([raw])

    return {
        "album_urls": album_urls,
        "stats": stats,
    }
