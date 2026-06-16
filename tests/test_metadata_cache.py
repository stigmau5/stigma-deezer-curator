import unittest

from curator.metadata_cache import (
    build_metadata_cache,
    collection_summary,
    metadata_coverage,
    metadata_quality,
    parse_album_payload,
    parse_artist_payload,
    parse_track_payload,
    render_collection_report,
    render_coverage_report,
    render_quality_report,
)


class FakeResponse:
    def __init__(self, payload):
        self.payload = payload

    def raise_for_status(self):
        return None

    def json(self):
        return self.payload


def fake_get(url, timeout=10):
    if "/album/302127" in url:
        return FakeResponse(
            {
                "id": 302127,
                "title": "Discovery",
                "release_date": "2001-03-07",
                "upc": "724384960650",
                "label": "Daft Life",
                "genres": {"data": [{"id": 113, "name": "Dance"}]},
                "contributors": [{"id": 27, "name": "Daft Punk", "role": "Main"}],
                "artist": {"id": 27, "name": "Daft Punk"},
                "nb_tracks": 1,
                "duration": 226,
                "record_type": "album",
                "explicit_lyrics": False,
                "explicit_content_lyrics": 0,
                "explicit_content_cover": 0,
                "cover_small": "small.jpg",
                "cover_medium": "medium.jpg",
                "cover_big": "big.jpg",
                "cover_xl": "xl.jpg",
                "md5_image": "coverhash",
                "tracks": {"data": [{"id": 3135556}]},
            }
        )
    if "/artist/27" in url:
        return FakeResponse(
            {
                "id": 27,
                "name": "Daft Punk",
                "nb_album": 38,
                "nb_fan": 5163259,
                "picture_small": "artist-small.jpg",
                "picture_medium": "artist-medium.jpg",
                "picture_big": "artist-big.jpg",
                "picture_xl": "artist-xl.jpg",
            }
        )
    if "/track/3135556" in url:
        return FakeResponse(
            {
                "id": 3135556,
                "title": "Harder Better Faster Stronger",
                "isrc": "GBDUW0000059",
                "duration": 226,
                "track_position": 4,
                "disk_number": 1,
                "contributors": [{"id": 27, "name": "Daft Punk", "role": "Main"}],
                "artist": {"id": 27, "name": "Daft Punk"},
                "explicit_lyrics": False,
                "explicit_content_lyrics": 0,
                "explicit_content_cover": 0,
            }
        )
    return FakeResponse({"error": {"message": "missing"}})


class MetadataCacheTests(unittest.TestCase):
    def test_metadata_parsing(self):
        album = parse_album_payload(fake_get("https://api.deezer.com/album/302127").json())
        self.assertEqual(album["deezer_album_id"], "302127")
        self.assertEqual(album["year"], 2001)
        self.assertEqual(album["genres"][0]["name"], "Dance")
        self.assertEqual(album["track_ids"], ["3135556"])

        artist = parse_artist_payload(fake_get("https://api.deezer.com/artist/27").json())
        self.assertEqual(artist["deezer_artist_id"], "27")
        self.assertEqual(artist["fan_count"], 5163259)

        track = parse_track_payload(fake_get("https://api.deezer.com/track/3135556").json())
        self.assertEqual(track["deezer_track_id"], "3135556")
        self.assertEqual(track["isrc"], "GBDUW0000059")

    def test_cache_generation_with_mocked_network(self):
        cache = build_metadata_cache(
            {"albums": [{"album_id": "302127"}]},
            {"releases": []},
            get=fake_get,
            sleep=lambda _: None,
        )
        self.assertIn("302127", cache["albums"])
        self.assertIn("27", cache["artists"])
        self.assertIn("3135556", cache["tracks"])
        self.assertEqual(cache["summary"]["coverage_percent"], 1.0)

    def test_existing_cache_is_preserved(self):
        existing = {
            "schema": 1,
            "source": "deezer",
            "albums": {"302127": {"deezer_album_id": "302127"}},
            "artists": {},
            "tracks": {},
            "errors": {},
        }
        cache = build_metadata_cache(
            {"albums": [{"album_id": "302127"}]},
            {"releases": []},
            existing_cache=existing,
            get=fake_get,
            sleep=lambda _: None,
        )
        self.assertEqual(cache["albums"]["302127"], {"deezer_album_id": "302127"})

    def test_existing_errors_are_skipped(self):
        existing = {
            "schema": 1,
            "source": "deezer",
            "albums": {},
            "artists": {},
            "tracks": {},
            "errors": {"999": {"type": "album_fetch_failed"}},
        }
        cache = build_metadata_cache(
            {"albums": [{"album_id": "999"}, {"album_id": "302127"}]},
            {"releases": []},
            existing_cache=existing,
            limit=1,
            get=fake_get,
            sleep=lambda _: None,
        )
        self.assertIn("302127", cache["albums"])

    def test_coverage_quality_and_collection_reports(self):
        cache = build_metadata_cache(
            {"albums": [{"album_id": "302127"}, {"album_id": "999999"}]},
            {"releases": []},
            limit=1,
            get=fake_get,
            sleep=lambda _: None,
        )
        coverage = metadata_coverage(cache, 2)
        quality = metadata_quality(cache)
        collection = collection_summary(cache)

        self.assertEqual(coverage["albums_with_metadata"], 1)
        self.assertEqual(coverage["albums_missing_metadata"], 1)
        self.assertEqual(quality["albums_missing_upc"], 0)
        self.assertEqual(quality["tracks_missing_isrc"], 0)
        self.assertEqual(collection["albums_by_year"]["2001"], 1)
        self.assertIn("Metadata Coverage Report", render_coverage_report(cache))
        self.assertIn("Metadata Quality Report", render_quality_report(cache))
        self.assertIn("Metadata Collection Report", render_collection_report(cache))


if __name__ == "__main__":
    unittest.main()
