import unittest

from audio_division.physical_archive import archive_tree_expansion
from audio_division.selection_state import capture_archive_selection, selected_album_index


class ArchiveTreeNavigationTests(unittest.TestCase):
    def rows(self):
        return [
            {"letter": "A", "artist": "Alpha", "artist_key": "alpha"},
            {"letter": "A", "artist": "Another", "artist_key": "another"},
            {"letter": "B", "artist": "Beta", "artist_key": "beta"},
        ]

    def test_tree_expansion_modes(self):
        rows = self.rows()

        self.assertEqual(archive_tree_expansion(rows, "expand_all"), {"letter:A", "letter:B"})
        self.assertEqual(archive_tree_expansion(rows, "collapse_all"), set())
        self.assertEqual(archive_tree_expansion(rows, "expand_artist", "another"), {"letter:A"})

    def test_expand_artist_without_artist_selection_collapses_tree(self):
        self.assertEqual(archive_tree_expansion(self.rows(), "expand_artist", "missing"), set())

    def test_album_selection_survives_refresh_and_reordering(self):
        selected = {
            "artist_key": "alpha",
            "archive_path": "/archive/alpha/second",
            "title": "Second",
        }
        state = capture_archive_selection(selected, album_yview=(0.35, 0.75))
        refreshed = [
            {"artist_key": "alpha", "archive_path": "/archive/alpha/second", "title": "Second"},
            {"artist_key": "alpha", "archive_path": "/archive/alpha/first", "title": "First"},
        ]

        self.assertEqual(selected_album_index(refreshed, state), 0)
        self.assertEqual(state.artist_key, "alpha")
        self.assertEqual(state.album_yview, 0.35)

    def test_missing_album_is_not_restored(self):
        state = capture_archive_selection({"artist_key": "alpha", "archive_path": "/archive/missing"})
        self.assertIsNone(selected_album_index([], state))


if __name__ == "__main__":
    unittest.main()
