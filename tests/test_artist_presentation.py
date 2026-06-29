import unittest
from pathlib import Path

from audio_division.artist_model import parse_artist_text
from audio_division.artist_presentation import (
    load_artist_presentation,
    presentation_from_artist,
    sort_artist_presentations,
)


class ArtistPresentationTests(unittest.TestCase):
    def artist_path(self, filename: str) -> Path:
        return Path(__file__).resolve().parents[1] / "data" / "artists" / filename

    def test_existing_artist_file_is_loaded_as_projection(self):
        presentation = load_artist_presentation(self.artist_path("AC_DC.txt"))

        self.assertEqual(presentation.display_name, "AC/DC")
        self.assertEqual(presentation.projection_name, "AC_DC.txt")
        self.assertEqual(presentation.artist.artist_name, "AC/DC")
        self.assertEqual(presentation.projection_path.name, "AC_DC.txt")
        self.assertGreater(presentation.total_release_count, 0)

    def test_display_name_falls_back_to_projection_stem(self):
        artist = parse_artist_text(
            "# Albums\nhttps://www.deezer.com/album/42  # ALBUM | Answer | 2024 | 1 tracks",
            source_file=Path("Example_Artist.txt"),
        )
        presentation = presentation_from_artist(artist)

        self.assertEqual(presentation.display_name, "Example Artist")
        self.assertEqual(presentation.projection_name, "Example_Artist.txt")

    def test_sort_uses_artist_identity_not_filename(self):
        zeta = parse_artist_text("# Artist: Alpha\n", source_file=Path("Zeta.txt"))
        alpha = parse_artist_text("# Artist: Zeta\n", source_file=Path("Alpha.txt"))
        rows = [presentation_from_artist(zeta), presentation_from_artist(alpha)]

        sorted_rows = sort_artist_presentations(rows)

        self.assertEqual([row.display_name for row in sorted_rows], ["Alpha", "Zeta"])

    def test_last_added_sort_uses_projection_metadata(self):
        first = presentation_from_artist(parse_artist_text("# Artist: First\n", source_file=Path("First.txt")))
        second = presentation_from_artist(parse_artist_text("# Artist: Second\n", source_file=Path("Second.txt")))

        sorted_rows = sort_artist_presentations(
            [first, second],
            sort_mode="last_added",
            created_meta={"First.txt": "2026-01-01T00:00:00", "Second.txt": "2026-02-01T00:00:00"},
        )

        self.assertEqual([row.display_name for row in sorted_rows], ["Second", "First"])


if __name__ == "__main__":
    unittest.main()
