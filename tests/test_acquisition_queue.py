import json
import tempfile
import unittest
from pathlib import Path

from audio_division.acquisition_queue import (
    STATE_DOWNLOADED,
    STATE_QUEUED,
    add_queue_item,
    empty_acquisition_queue,
    load_acquisition_queue,
    queue_release,
    queue_rows,
    remove_queue_item,
    save_acquisition_queue,
    update_queue_item_state,
)


class ReleaseStub:
    title = "Answer"
    type = "album"
    deezer_album_id = "42"
    url = "https://www.deezer.com/album/42"


class AcquisitionQueueTests(unittest.TestCase):
    def test_queue_release_stores_album_shape(self):
        queue = queue_release(empty_acquisition_queue(), ReleaseStub(), artist="Example", queued_time="2026-01-01T10:00:00")
        row = queue_rows(queue)[0]

        self.assertEqual(row["artist"], "Example")
        self.assertEqual(row["album"], "Answer")
        self.assertEqual(row["release_type"], "album")
        self.assertEqual(row["deezer_album_id"], "42")
        self.assertEqual(row["url"], "https://www.deezer.com/album/42")
        self.assertEqual(row["queued_time"], "2026-01-01T10:00:00")
        self.assertEqual(row["current_state"], STATE_QUEUED)
        self.assertEqual(row["action"], "Acquire Album")

    def test_queue_release_updates_existing_item_without_resetting_time(self):
        queue = queue_release(empty_acquisition_queue(), ReleaseStub(), artist="Example", queued_time="first")
        queue = queue_release(queue, ReleaseStub(), artist="Example Updated", queued_time="second")
        row = queue_rows(queue)[0]

        self.assertEqual(len(queue["items"]), 1)
        self.assertEqual(row["artist"], "Example Updated")
        self.assertEqual(row["queued_time"], "first")

    def test_remove_and_update_state(self):
        queue = add_queue_item(
            empty_acquisition_queue(),
            {"deezer_album_id": "42", "album": "Answer", "current_state": STATE_QUEUED},
            queued_time="now",
        )
        queue = update_queue_item_state(queue, "42", STATE_DOWNLOADED)
        self.assertEqual(queue_rows(queue)[0]["current_state"], STATE_DOWNLOADED)
        self.assertEqual(queue_rows(queue)[0]["action"], "Validate")

        queue = remove_queue_item(queue, "42")
        self.assertEqual(queue_rows(queue), [])

    def test_unknown_state_is_rejected_for_updates(self):
        queue = add_queue_item(empty_acquisition_queue(), {"deezer_album_id": "42", "album": "Answer"})

        with self.assertRaises(ValueError):
            update_queue_item_state(queue, "42", "Imaginary")

    def test_load_and_save_queue(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "acquisition_queue.json"
            queue = queue_release(empty_acquisition_queue(), ReleaseStub(), artist="Example", queued_time="now")
            save_acquisition_queue(path, queue)

            loaded = load_acquisition_queue(path)

        self.assertEqual(queue_rows(loaded)[0]["deezer_album_id"], "42")

    def test_legacy_list_shape_loads(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "acquisition_queue.json"
            path.write_text(
                json.dumps({"items": [{"album_id": "42", "title": "Answer", "state": STATE_DOWNLOADED}]}),
                encoding="utf-8",
            )

            loaded = load_acquisition_queue(path)

        self.assertEqual(queue_rows(loaded)[0]["album"], "Answer")
        self.assertEqual(queue_rows(loaded)[0]["current_state"], STATE_DOWNLOADED)


if __name__ == "__main__":
    unittest.main()
