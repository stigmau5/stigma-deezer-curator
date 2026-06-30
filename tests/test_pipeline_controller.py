import unittest

from audio_division.pipeline_controller import (
    ACTION_ARCHIVE,
    ACTION_HEALTHY,
    ACTION_REFRESH,
    ACTION_REFRESH_METADATA,
    ACTION_VALIDATE,
    STATE_ARCHIVE_READY,
    STATE_ARCHIVED,
    STATE_DOWNLOADED,
    STATE_NEEDS_METADATA,
    STATE_VALIDATED,
    recommend_for_releases,
    recommend_next_action,
)


class PipelineControllerTests(unittest.TestCase):
    def test_downloaded_release_recommends_validation(self):
        recommendation = recommend_next_action(
            {
                "artist": "Example",
                "album": "Answer",
                "folder": "/incoming/Example-Answer",
                "status": "Downloaded",
            }
        )

        self.assertEqual(recommendation.state, STATE_DOWNLOADED)
        self.assertEqual(recommendation.recommended_action, ACTION_VALIDATE)

    def test_validated_release_recommends_archive(self):
        recommendation = recommend_next_action(
            {
                "lifecycle_state": "VALIDATED",
                "album_truth": {"items": {"validation": "Present"}},
            }
        )

        self.assertEqual(recommendation.state, STATE_VALIDATED)
        self.assertEqual(recommendation.recommended_action, ACTION_ARCHIVE)

    def test_archived_release_recommends_refresh(self):
        recommendation = recommend_next_action(
            {
                "archive_path": "/archive/E/Example/Example-Answer",
                "archive_status": "archived",
            }
        )

        self.assertEqual(recommendation.state, STATE_ARCHIVED)
        self.assertEqual(recommendation.recommended_action, ACTION_REFRESH)

    def test_archive_ready_release_is_healthy(self):
        recommendation = recommend_next_action(
            {
                "archive_path": "/archive/E/Example/Example-Answer",
                "album_truth": {"readiness": "ARCHIVE_READY"},
            }
        )

        self.assertEqual(recommendation.state, STATE_ARCHIVE_READY)
        self.assertEqual(recommendation.recommended_action, ACTION_HEALTHY)

    def test_metadata_blocker_recommends_refresh_metadata(self):
        recommendation = recommend_next_action(
            {
                "metadata_status": "AVAILABLE_NOT_CACHED",
                "lifecycle_state": "DISCOVERED",
            }
        )

        self.assertEqual(recommendation.state, STATE_NEEDS_METADATA)
        self.assertEqual(recommendation.recommended_action, ACTION_REFRESH_METADATA)

    def test_batch_projection_returns_dicts(self):
        recommendations = recommend_for_releases(
            [
                {"folder": "/incoming/one", "status": "Downloaded"},
                {"lifecycle_state": "READY_FOR_PROCESSING"},
            ]
        )

        self.assertEqual(recommendations[0]["recommended_action"], ACTION_VALIDATE)
        self.assertEqual(recommendations[1]["recommended_action"], ACTION_ARCHIVE)


if __name__ == "__main__":
    unittest.main()
