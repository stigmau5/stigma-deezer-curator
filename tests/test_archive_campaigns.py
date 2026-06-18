import unittest

from audio_division.campaigns import (
    campaign_albums,
    campaign_summaries,
    selected_campaign_targets,
)


class ArchiveCampaignTests(unittest.TestCase):
    def album(self, album_id: str, **items):
        defaults = {
            "validation": "Present",
            "nfo": "Present",
            "sfv": "Present",
            "artwork": "Present",
            "metadata": "Present",
        }
        defaults.update(items)
        return {
            "album_id": album_id,
            "artist": "Artist",
            "title": f"Album {album_id}",
            "archive_path": f"/archive/Album-{album_id}",
            "album_status": {"items": defaults},
            "album_truth": {"items": defaults},
            "metadata_status": "CACHED",
        }

    def test_campaign_summaries(self):
        albums = [
            self.album("1", nfo="Missing"),
            self.album("2", sfv="Missing"),
            self.album("3", validation="Missing"),
        ]
        summaries = {row["id"]: row["album_count"] for row in campaign_summaries(albums)}

        self.assertEqual(summaries["missing_nfo"], 1)
        self.assertEqual(summaries["missing_sfv"], 1)
        self.assertEqual(summaries["missing_validation"], 1)

    def test_campaign_album_matching(self):
        albums = [
            self.album("1", artwork="Missing"),
            {**self.album("2"), "metadata_status": "AVAILABLE_NOT_CACHED"},
        ]

        self.assertEqual(campaign_albums(albums, "missing_artwork")[0]["album_id"], "1")
        self.assertEqual(campaign_albums(albums, "metadata_available_not_cached")[0]["album_id"], "2")

    def test_selected_campaign_targets(self):
        targets = selected_campaign_targets("generate_nfo", [self.album("1", nfo="Missing")])

        self.assertEqual(targets[0]["operation"], "generate_nfo")
        self.assertEqual(targets[0]["target"], "/archive/Album-1")
        self.assertTrue(targets[0]["eligible"])


if __name__ == "__main__":
    unittest.main()
