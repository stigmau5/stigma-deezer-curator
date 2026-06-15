from __future__ import annotations

import json
import tempfile
import unittest
from pathlib import Path

from curator.atomic import atomic_write_text
from curator.attempts import AttemptInfo, load_attempts, save_attempts
from curator.preferences import load_preferences, save_preferences
from curator.ship import _load_shipped_db, _save_shipped_db
from curator.state import ConfirmedAlbum, load_confirmed, save_confirmed


class AtomicWriteTextTests(unittest.TestCase):
    def test_writes_utf8_text_and_cleans_temp_file(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "state.json"

            atomic_write_text(path, '{"name": "Beyoncé"}\n')

            self.assertEqual(path.read_text(encoding="utf-8"), '{"name": "Beyoncé"}\n')
            self.assertEqual([p.name for p in path.parent.iterdir()], ["state.json"])

    def test_overwrites_existing_file_atomically(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "state.json"
            path.write_text("old\n", encoding="utf-8")

            atomic_write_text(path, "new\n")

            self.assertEqual(path.read_text(encoding="utf-8"), "new\n")


class StateWriterTests(unittest.TestCase):
    def test_confirmed_albums_roundtrip_and_overwrite(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "confirmed_albums.json"

            save_confirmed(
                path,
                {
                    "123": ConfirmedAlbum(
                        album_id="123",
                        album_url="https://www.deezer.com/album/123",
                        confirmed_at="2026-06-15T12:00:00",
                        artist_file="Artist.txt",
                    )
                },
            )
            first = json.loads(path.read_text(encoding="utf-8"))
            self.assertEqual(first["123"]["artist_file"], "Artist.txt")
            self.assertIn("\n", path.read_text(encoding="utf-8")[-1:])

            save_confirmed(
                path,
                {
                    "456": ConfirmedAlbum(
                        album_id="456",
                        album_url="https://www.deezer.com/album/456",
                        confirmed_at="2026-06-15T13:00:00",
                        artist_file=None,
                    )
                },
            )

            loaded = load_confirmed(path)
            self.assertNotIn("123", loaded)
            self.assertEqual(loaded["456"].album_url, "https://www.deezer.com/album/456")

    def test_attempted_albums_roundtrip_and_overwrite(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "attempted_albums.json"

            save_attempts(
                path,
                {
                    "123": AttemptInfo(
                        album_url="https://www.deezer.com/album/123",
                        attempts=1,
                        last_attempt="2026-06-15T12:00:00",
                    )
                },
            )
            self.assertEqual(load_attempts(path)["123"].attempts, 1)

            save_attempts(
                path,
                {
                    "123": AttemptInfo(
                        album_url="https://www.deezer.com/album/123",
                        attempts=2,
                        last_attempt="2026-06-15T13:00:00",
                    )
                },
            )

            self.assertEqual(load_attempts(path)["123"].attempts, 2)

    def test_preferences_roundtrip_and_overwrite(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "preferences.json"

            save_preferences(path, {"batch_size": 6})
            self.assertEqual(load_preferences(path)["batch_size"], 6)

            save_preferences(path, {"batch_size": 20})

            self.assertEqual(load_preferences(path)["batch_size"], 20)

    def test_shipped_jobs_roundtrip_and_overwrite(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "shipped_jobs.json"

            _save_shipped_db(
                path,
                {
                    "schema": 1,
                    "shipped": {
                        "123": {
                            "album_id": "123",
                            "url": "https://www.deezer.com/album/123",
                            "jobname": "job-123",
                            "remote_job": "/pending/job-123.job",
                            "shipped_at_utc": "2026-06-15T12:00:00Z",
                        }
                    },
                },
            )
            self.assertEqual(_load_shipped_db(path)["shipped"]["123"]["jobname"], "job-123")

            _save_shipped_db(path, {"schema": 1, "shipped": {}})

            self.assertEqual(_load_shipped_db(path), {"schema": 1, "shipped": {}})


if __name__ == "__main__":
    unittest.main()
