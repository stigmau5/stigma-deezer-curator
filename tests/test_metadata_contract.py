from __future__ import annotations

import unittest
from unittest.mock import patch

from curator.expand import expand_artist_releases
from curator.metadata import AlbumMetadata, get_album_metadata


class FakeResponse:
    def __init__(self, payload: dict):
        self.payload = payload

    def raise_for_status(self) -> None:
        return None

    def json(self) -> dict:
        return self.payload


class MetadataContractTests(unittest.TestCase):
    def test_album_metadata_includes_expansion_fields(self) -> None:
        payload = {
            "artist": {"name": "Daft Punk"},
            "title": "Discovery",
            "release_date": "2001-03-07",
            "nb_tracks": 14,
            "record_type": "album",
            "explicit_lyrics": False,
        }

        with (
            patch("curator.metadata.requests.get", return_value=FakeResponse(payload)),
            patch("curator.metadata.time.sleep"),
        ):
            metadata = get_album_metadata("302127")

        self.assertEqual(
            metadata,
            AlbumMetadata(
                artist="Daft Punk",
                title="Discovery",
                year=2001,
                tracks=14,
                is_compilation=False,
                is_clean=False,
            ),
        )

    def test_album_metadata_marks_compilation_and_clean_edition_conservatively(self) -> None:
        payload = {
            "artist": {"name": "Various Artists"},
            "title": "Radio Hits (Clean)",
            "release_date": "2020",
            "nb_tracks": "18",
            "record_type": "compilation",
            "explicit_lyrics": False,
        }

        with (
            patch("curator.metadata.requests.get", return_value=FakeResponse(payload)),
            patch("curator.metadata.time.sleep"),
        ):
            metadata = get_album_metadata("123")

        self.assertIsNotNone(metadata)
        self.assertEqual(metadata.year, 2020)
        self.assertEqual(metadata.tracks, 18)
        self.assertTrue(metadata.is_compilation)
        self.assertTrue(metadata.is_clean)

    def test_expand_uses_metadata_contract_fields(self) -> None:
        pages = [
            FakeResponse(
                {
                    "data": [
                        {
                            "id": 123,
                            "record_type": "album",
                        }
                    ]
                }
            ),
            FakeResponse({"data": []}),
        ]

        with (
            patch("curator.expand.requests.get", side_effect=pages),
            patch("curator.expand.time.sleep"),
            patch(
                "curator.expand.get_album_metadata",
                return_value=AlbumMetadata(
                    artist="Various Artists",
                    title="Radio Hits (Clean)",
                    year=2020,
                    tracks=18,
                    is_compilation=True,
                    is_clean=True,
                ),
            ),
        ):
            releases = expand_artist_releases("456")

        self.assertEqual(
            releases["albums"],
            [
                "https://www.deezer.com/album/123  # "
                "ALBUM | Radio Hits (Clean) | 2020 | 18 tracks | COMPILATION | CLEAN"
            ],
        )


if __name__ == "__main__":
    unittest.main()
