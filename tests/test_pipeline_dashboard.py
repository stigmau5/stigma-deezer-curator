import unittest

from audio_division.pipeline_dashboard import (
    STAGE_ACQUIRE,
    STAGE_ARCHIVED,
    STAGE_COMPLETED,
    STAGE_DOWNLOADED,
    STAGE_NEEDS_ATTENTION,
    STAGE_READY_TO_ARCHIVE,
    build_pipeline_dashboard,
    release_to_dashboard_item,
)


class PipelineDashboardTests(unittest.TestCase):
    def test_acquisition_release_groups_under_acquire(self):
        item = release_to_dashboard_item(
            {
                "artist": "Example",
                "title": "Needs It",
                "deezer_album_id": "123",
                "url": "https://www.deezer.com/album/123",
                "archive_status": "not_archived",
                "acquisition_recommendation": {"recommendation": "READY_TO_ACQUIRE"},
            }
        )

        self.assertEqual(item.stage, STAGE_ACQUIRE)
        self.assertEqual(item.album, "Needs It")
        self.assertEqual(item.artist, "Example")

    def test_downloaded_release_groups_under_downloaded(self):
        item = release_to_dashboard_item(
            {
                "artist": "Example",
                "album": "Downloaded",
                "folder": "/incoming/downloaded",
                "status": "Downloaded",
            }
        )

        self.assertEqual(item.stage, STAGE_DOWNLOADED)
        self.assertEqual(item.recommended_next_action, "Validate")

    def test_validated_release_groups_under_ready_to_archive(self):
        item = release_to_dashboard_item(
            {
                "artist": "Example",
                "album": "Validated",
                "lifecycle_state": "VALIDATED",
                "album_truth": {"items": {"validation": "Present"}},
            }
        )

        self.assertEqual(item.stage, STAGE_READY_TO_ARCHIVE)
        self.assertEqual(item.recommended_next_action, "Archive")

    def test_archived_release_groups_under_archived(self):
        item = release_to_dashboard_item(
            {
                "artist": "Example",
                "title": "Archived",
                "archive_path": "/archive/Example/Archived",
                "archive_status": "archived",
            }
        )

        self.assertEqual(item.stage, STAGE_ARCHIVED)
        self.assertEqual(item.recommended_next_action, "Refresh")

    def test_archive_ready_release_groups_under_completed(self):
        item = release_to_dashboard_item(
            {
                "artist": "Example",
                "title": "Healthy",
                "album_truth": {"readiness": "ARCHIVE_READY"},
            }
        )

        self.assertEqual(item.stage, STAGE_COMPLETED)
        self.assertEqual(item.recommended_next_action, "Healthy")

    def test_metadata_blocker_groups_under_needs_attention(self):
        item = release_to_dashboard_item(
            {
                "artist": "Example",
                "title": "Needs Metadata",
                "metadata_status": "AVAILABLE_NOT_CACHED",
            }
        )

        self.assertEqual(item.stage, STAGE_NEEDS_ATTENTION)
        self.assertEqual(item.recommended_next_action, "Refresh Metadata")

    def test_dashboard_includes_counts_for_empty_stages(self):
        dashboard = build_pipeline_dashboard(
            [
                {"artist": "A", "title": "Acquire", "url": "https://www.deezer.com/album/1", "deezer_album_id": "1"},
                {"artist": "B", "album": "Downloaded", "folder": "/incoming/b", "status": "Downloaded"},
            ]
        )

        self.assertEqual(dashboard["total_releases"], 2)
        self.assertEqual(dashboard["stage_counts"][STAGE_ACQUIRE], 1)
        self.assertEqual(dashboard["stage_counts"][STAGE_DOWNLOADED], 1)
        self.assertIn(STAGE_READY_TO_ARCHIVE, dashboard["stage_counts"])

    def test_dashboard_deduplicates_release_by_latest_workflow_stage(self):
        dashboard = build_pipeline_dashboard(
            [
                {
                    "artist": "Example",
                    "title": "Same Album",
                    "deezer_album_id": "777",
                    "url": "https://www.deezer.com/album/777",
                    "archive_status": "not_archived",
                },
                {
                    "artist": "Example",
                    "title": "Same Album",
                    "album_id": "777",
                    "archive_path": "/archive/Example/Same Album",
                    "archive_status": "archived",
                },
            ]
        )

        self.assertEqual(dashboard["total_releases"], 1)
        self.assertEqual(dashboard["stage_counts"][STAGE_ACQUIRE], 0)
        self.assertEqual(dashboard["stage_counts"][STAGE_ARCHIVED], 1)


if __name__ == "__main__":
    unittest.main()
