from enum import Enum
from dataclasses import dataclass
import re


class LinkType(Enum):
    ALBUM = "album"
    ARTIST = "artist"
    UNKNOWN = "unknown"


@dataclass(frozen=True)
class DeezerLink:
    raw: str
    type: LinkType
    id: str | None


# Optional locale prefix like /en/, /se/, /fr/
_LOCALE = r"(?:/[a-z]{2})?"

ALBUM_RE = re.compile(rf"{_LOCALE}/album/(\d+)")
ARTIST_RE = re.compile(rf"{_LOCALE}/artist/(\d+)")


def parse_deezer_link(url: str) -> DeezerLink:
    url = url.strip()

    album_match = ALBUM_RE.search(url)
    if album_match:
        return DeezerLink(
            raw=url,
            type=LinkType.ALBUM,
            id=album_match.group(1),
        )

    artist_match = ARTIST_RE.search(url)
    if artist_match:
        return DeezerLink(
            raw=url,
            type=LinkType.ARTIST,
            id=artist_match.group(1),
        )

    return DeezerLink(
        raw=url,
        type=LinkType.UNKNOWN,
        id=None,
    )
