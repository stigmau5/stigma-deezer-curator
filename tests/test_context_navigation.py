import unittest

from audio_division.context_navigation import (
    context_actions,
    context_album_id,
    context_deezer_link,
    context_folder,
    context_parent_folder,
)


class ContextNavigationTests(unittest.TestCase):
    def test_archive_release_actions(self):
        row = {
            "album_id": "42",
            "archive_path": "/archive/Artist/Album",
            "identity_confidence": "HIGH",
            "validation_status": "validated",
        }

        actions = context_actions(row)

        self.assertTrue(actions["jump_to_archive"])
        self.assertTrue(actions["jump_to_curator"])
        self.assertTrue(actions["open_folder"])
        self.assertTrue(actions["open_parent_folder"])
        self.assertTrue(actions["copy_album_id"])
        self.assertTrue(actions["copy_deezer_link"])
        self.assertTrue(actions["revalidate"])
        self.assertTrue(actions["process_album"])
        self.assertFalse(actions["reveal_incoming_folder"])
        self.assertEqual(context_deezer_link(row), "https://www.deezer.com/album/42")
        self.assertEqual(context_parent_folder(row), "/archive/Artist")

    def test_incoming_release_actions(self):
        row = {"deezer_album_id": "99", "folder": "/incoming/Artist - Album", "url": "https://deezer.test/album/99"}

        actions = context_actions(row)

        self.assertFalse(actions["jump_to_archive"])
        self.assertTrue(actions["jump_to_curator"])
        self.assertTrue(actions["open_folder"])
        self.assertTrue(actions["reveal_incoming_folder"])
        self.assertFalse(actions["revalidate"])
        self.assertTrue(actions["copy_album_id"])
        self.assertEqual(context_album_id(row), "99")
        self.assertEqual(context_folder(row), "/incoming/Artist - Album")

    def test_empty_row_disables_actions(self):
        actions = context_actions({})

        self.assertFalse(any(actions.values()))

    def test_process_requires_a_folder_or_archive_path(self):
        actions = context_actions({"album_id": "42", "validation_status": "validated"})

        self.assertFalse(actions["process_album"])


if __name__ == "__main__":
    unittest.main()
