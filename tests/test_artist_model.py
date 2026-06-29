import unittest
from pathlib import Path

from audio_division.artist_model import (
    parse_artist_text,
    release_line_map,
    releases_for_section,
    render_artist_text,
)


class ArtistModelTests(unittest.TestCase):
    def artist_path(self, filename: str) -> Path:
        return Path(__file__).resolve().parents[1] / "data" / "artists" / filename

    def parse_existing_artist(self, filename: str):
        path = self.artist_path(filename)
        return parse_artist_text(path.read_text(encoding="utf-8"), source_file=path)

    def test_parses_existing_nirvana_artist_file(self):
        artist = self.parse_existing_artist("Nirvana.txt")

        self.assertEqual(artist.artist_name, "Nirvana")
        self.assertEqual(artist.deezer_artist_id, "415")
        self.assertEqual(artist.last_updated, "2026-01-10 17:30")
        self.assertEqual(len(artist.albums), 19)
        self.assertEqual(len(artist.eps), 2)
        self.assertEqual(len(artist.singles), 4)
        self.assertEqual(len(artist.live), 9)
        self.assertEqual(len(artist.compilations), 0)
        self.assertEqual(artist.total_release_count, 25)
        self.assertEqual(artist.albums[0].deezer_album_id, "270615252")
        self.assertEqual(artist.albums[0].title, "Nevermind (30th Anniversary Super Deluxe)")
        self.assertEqual(artist.albums[0].type, "album")

    def test_parses_existing_acdc_artist_file_and_preserves_source_text(self):
        path = self.artist_path("AC_DC.txt")
        text = path.read_text(encoding="utf-8")
        artist = parse_artist_text(text, source_file=path)

        self.assertEqual(artist.artist_name, "AC/DC")
        self.assertEqual(artist.deezer_artist_id, "115")
        self.assertEqual(len(artist.albums), 24)
        self.assertEqual(len(artist.eps), 3)
        self.assertEqual(len(artist.singles), 2)
        self.assertEqual(len(artist.live), 6)
        self.assertEqual(artist.total_release_count, 29)
        self.assertEqual(render_artist_text(artist), text)

    def test_line_map_and_section_lookup_return_release_objects(self):
        artist = self.parse_existing_artist("Nirvana.txt")
        line_map = release_line_map(artist)

        self.assertEqual(line_map[8].url, "https://www.deezer.com/album/270615252")
        self.assertEqual(line_map[29].type, "ep")
        self.assertEqual(releases_for_section(artist, "Singles")[0].deezer_album_id, "499516731")

    def test_release_statuses_are_projected_from_existing_indexes(self):
        text = "\n".join(
            [
                "# Artist: Example",
                "",
                "# === Deezer artist expansion ===",
                "# source: https://www.deezer.com/artist/123",
                "# expanded_at: 2026-01-01 10:00",
                "",
                "# Albums",
                "https://www.deezer.com/album/42  # ALBUM | Answer | 2024 | 10 tracks",
                "",
            ]
        )
        artist = parse_artist_text(
            text,
            source_file=Path("Example.txt"),
            lifecycle_registry={
                "albums": [
                    {
                        "album_id": "42",
                        "highest_state": "VALIDATED",
                        "states": {"validated": True},
                        "validation_evidence": {"available": True},
                    }
                ]
            },
            metadata_cache={"albums": {"42": {"label": "Label", "genres": [{"name": "Rock"}], "contributors": [{"name": "Example"}], "release_date": "2024-01-01", "upc": "123"}}},
            validated_index={"42": {"validated_at": "2026-01-01T00:00:00"}},
        )

        release = artist.albums[0]
        self.assertEqual(release.year, "2024")
        self.assertEqual(release.archive_status, "archived")
        self.assertEqual(release.lifecycle_state, "VALIDATED")
        self.assertEqual(release.validation_status, "validated")
        self.assertEqual(release.metadata_status, "CACHED")


if __name__ == "__main__":
    unittest.main()
