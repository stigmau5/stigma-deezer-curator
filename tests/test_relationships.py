import unittest

from audio_division.relationships import album_relationships, render_relationships


class RelationshipTests(unittest.TestCase):
    def test_relationships_group_by_artist_label_year_and_genre(self):
        selected = {
            "album_id": "1",
            "artist": "Daft Punk",
            "title": "Discovery",
            "year": "2001",
            "label": "Virgin",
            "genres": ["Electronic", "House"],
        }
        albums = [
            selected,
            {"album_id": "2", "artist": "Daft Punk", "title": "Homework", "year": "1997", "label": "Virgin", "genres": ["House"]},
            {"album_id": "3", "artist": "Air", "title": "Talkie Walkie", "year": "2004", "label": "Virgin", "genres": ["Electronic"]},
            {"album_id": "4", "artist": "Basement Jaxx", "title": "Rooty", "year": "2001", "label": "XL", "genres": ["House"]},
        ]

        relationships = album_relationships(selected, albums)

        self.assertEqual(len(relationships["groups"]["same_artist"]), 1)
        self.assertEqual(len(relationships["groups"]["same_label"]), 2)
        self.assertEqual(len(relationships["groups"]["same_year"]), 1)
        self.assertEqual(len(relationships["groups"]["same_genre"]), 3)
        self.assertNotIn(selected, relationships["groups"]["same_genre"])

    def test_render_relationships_handles_empty_results(self):
        rendered = render_relationships(album_relationships({"album_id": "1"}, []))

        self.assertEqual(rendered, "No related albums found from cached/archive data.")


if __name__ == "__main__":
    unittest.main()
