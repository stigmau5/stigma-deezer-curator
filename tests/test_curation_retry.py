from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from curator.curate import run_curation


class CurationRetryTests(unittest.TestCase):
    def test_successful_artist_expansion_is_logged(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            inbox = base / "inbox.txt"
            log = base / "curated.log"
            artists = base / "artists"
            inbox.write_text("https://www.deezer.com/artist/123\n", encoding="utf-8")

            with (
                patch("curator.curate.expand_artist_releases", return_value={"albums": []}),
                patch("curator.curate.write_expansion_block", return_value=True),
            ):
                result = run_curation(inbox, log, artists)

            self.assertEqual(result["stats"]["artists_expanded"], 1)
            self.assertEqual(
                log.read_text(encoding="utf-8"),
                "https://www.deezer.com/artist/123\n",
            )

    def test_failed_artist_expansion_is_not_logged(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            inbox = base / "inbox.txt"
            log = base / "curated.log"
            artists = base / "artists"
            inbox.write_text("https://www.deezer.com/artist/123\n", encoding="utf-8")

            with patch(
                "curator.curate.expand_artist_releases",
                side_effect=RuntimeError("temporary deezer failure"),
            ):
                result = run_curation(inbox, log, artists)

            self.assertEqual(result["stats"]["artists_expanded"], 0)
            self.assertFalse(log.exists())

    def test_failed_artist_expansion_can_be_retried(self) -> None:
        with tempfile.TemporaryDirectory() as tmp:
            base = Path(tmp)
            inbox = base / "inbox.txt"
            log = base / "curated.log"
            artists = base / "artists"
            inbox.write_text("https://www.deezer.com/artist/123\n", encoding="utf-8")

            with patch(
                "curator.curate.expand_artist_releases",
                side_effect=RuntimeError("temporary deezer failure"),
            ):
                first = run_curation(inbox, log, artists)

            self.assertEqual(first["stats"]["artists_expanded"], 0)
            self.assertFalse(log.exists())

            with (
                patch("curator.curate.expand_artist_releases", return_value={"albums": []}) as expand,
                patch("curator.curate.write_expansion_block", return_value=True),
            ):
                second = run_curation(inbox, log, artists)

            expand.assert_called_once_with("123")
            self.assertEqual(second["stats"]["artists_expanded"], 1)
            self.assertEqual(
                log.read_text(encoding="utf-8"),
                "https://www.deezer.com/artist/123\n",
            )


if __name__ == "__main__":
    unittest.main()
