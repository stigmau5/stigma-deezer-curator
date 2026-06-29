import unittest

from audio_division.acquisition_intelligence import (
    ALREADY_PROCESSING,
    ARCHIVED,
    READY_FOR_PROCESSING,
    READY_FOR_VALIDATION,
    READY_TO_ACQUIRE,
    find_closed_loop_row,
    find_processing_queue_entry,
    recommend_acquisition,
)


class AcquisitionIntelligenceTests(unittest.TestCase):
    def test_archived_release_explains_documented_archive(self):
        recommendation = recommend_acquisition(
            deezer_album_id="42",
            archive_row={
                "archive_path": "/archive/Example-Answer-2024-FLAC-STiGMA",
                "artifacts": {"nfo": True, "sfv": True, "validation_log": True},
            },
            album_truth={"items": {"nfo": "Present", "sfv": "Present", "validation": "Present"}},
            metadata_status="CACHED",
        )

        self.assertEqual(recommendation.recommendation, ARCHIVED)
        self.assertEqual(recommendation.confidence, "HIGH")
        self.assertIn("documentation", recommendation.reason)

    def test_incoming_downloaded_folder_is_ready_for_validation(self):
        recommendation = recommend_acquisition(
            deezer_album_id="42",
            closed_loop_row={"folder": "/incoming/Example-Answer", "state": "DOWNLOADED"},
        )

        self.assertEqual(recommendation.recommendation, READY_FOR_VALIDATION)
        self.assertEqual(recommendation.next_action, "Validate incoming album.")

    def test_incoming_validated_folder_is_ready_for_processing(self):
        recommendation = recommend_acquisition(
            deezer_album_id="42",
            closed_loop_row={"folder": "/incoming/Example-Answer", "state": "READY_FOR_PROCESSING"},
        )

        self.assertEqual(recommendation.recommendation, READY_FOR_PROCESSING)
        self.assertIn("Validation completed", recommendation.reason)

    def test_processing_queue_entry_blocks_duplicate_action(self):
        recommendation = recommend_acquisition(
            deezer_album_id="42",
            processing_queue_entry={"album_id": "42", "state": "PROCESSING"},
        )

        self.assertEqual(recommendation.recommendation, ALREADY_PROCESSING)
        self.assertEqual(recommendation.confidence, "HIGH")

    def test_deezer_only_release_is_ready_to_acquire(self):
        recommendation = recommend_acquisition(
            deezer_album_id="42",
            url="https://www.deezer.com/album/42",
            metadata_status="AVAILABLE_NOT_CACHED",
        )

        self.assertEqual(recommendation.recommendation, READY_TO_ACQUIRE)
        self.assertIn("not present in archive", recommendation.reason)

    def test_lookup_helpers_match_release_to_operational_rows(self):
        identity = {
            "archive_identity": {"folder": "Example-Answer-2024-FLAC-STiGMA"},
            "discovery_identity": {"artist": "Example", "title": "Answer"},
        }
        closed_loop = [
            {
                "folder": "/incoming/Example-Answer-2024-FLAC-STiGMA",
                "artist": "Example",
                "album": "Answer",
                "state": "DOWNLOADED",
            }
        ]
        queue = {
            "albums": {
                "/incoming/Example-Answer-2024-FLAC-STiGMA": {
                    "album_id": "42",
                    "album": "Answer",
                    "state": "PROCESSING",
                }
            }
        }

        self.assertEqual(
            find_closed_loop_row(closed_loop, deezer_album_id="42", artist="Example", title="Answer", identity_release=identity),
            closed_loop[0],
        )
        self.assertEqual(
            find_processing_queue_entry(queue, deezer_album_id="42", artist="Example", title="Answer", identity_release=identity),
            queue["albums"]["/incoming/Example-Answer-2024-FLAC-STiGMA"],
        )


if __name__ == "__main__":
    unittest.main()
