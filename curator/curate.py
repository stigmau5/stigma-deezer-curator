from pathlib import Path
from curator.links import parse_deezer_link, LinkType
from curator.expand import expand_artist
from curator.log import CuratedLog


def run_curation(
    inbox_path: Path,
    log_path: Path,
) -> list[str]:
    """
    Processes inbox links and returns album URLs to be written to output.
    """
    log = CuratedLog(log_path)

    with inbox_path.open("r", encoding="utf-8") as f:
        raw_links = [line.strip() for line in f if line.strip()]

    new_album_links: list[str] = []

    for raw in raw_links:
        if log.has(raw):
            continue

        link = parse_deezer_link(raw)

        try:
            if link.type == LinkType.ALBUM:
                new_album_links.append(link.raw)

            elif link.type == LinkType.ARTIST and link.id:
                albums = expand_artist(link.id)
                new_album_links.extend(albums)

            # UNKNOWN links are intentionally ignored

        except Exception as exc:
            print(f"⚠️  Failed to process {raw}: {exc}")

        finally:
            # Always record that we've seen this link
            log.append([raw])

    return new_album_links
