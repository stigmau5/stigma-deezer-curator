import unittest

from audio_division.archive_health_dashboard import HEALTH_ERROR, HEALTH_OK, archive_health_report


def album(
    album_id: str,
    *,
    artist: str = "Artist",
    title: str | None = None,
    path: str = "/archive/A/Artist/Albums/Artist-album-2024-WEB-FLAC-STiGMA",
    artwork: str = "Present",
    nfo: str = "Present",
    playlist: str = "Present",
    sfv: str = "Present",
    validation: str = "Present",
    metadata: str = "Present",
    metadata_status: str = "CACHED",
    identity_confidence: str = "HIGH",
    readiness: str = "ARCHIVE_READY",
):
    items = {
        "artwork": artwork,
        "nfo": nfo,
        "playlist": playlist,
        "sfv": sfv,
        "validation": validation,
        "metadata": metadata,
    }
    return {
        "album_id": album_id,
        "artist": artist,
        "artist_key": artist.lower(),
        "title": title or f"Album {album_id}",
        "archive_path": path,
        "metadata_status": metadata_status,
        "identity_confidence": identity_confidence,
        "album_truth": {
            "items": items,
            "readiness": readiness,
            "metadata_status": metadata_status,
            "identity_confidence": identity_confidence,
        },
        "album_status": {"items": items},
    }


class ArchiveHealthDashboardTests(unittest.TestCase):
    def test_healthy_archive_report(self):
        report = archive_health_report([album("1"), album("2", artist="Other")])

        self.assertEqual(report.status, HEALTH_OK)
        self.assertEqual(report.albums, 2)
        self.assertEqual(report.healthy, 2)
        self.assertEqual(report.metadata_coverage, 100.0)
        self.assertEqual(report.identity_coverage, 100.0)

    def test_missing_artifacts_and_coverage_are_counted_from_albumtruth(self):
        report = archive_health_report(
            [
                album("1"),
                album(
                    "2",
                    artwork="Missing",
                    nfo="Missing",
                    playlist="Missing",
                    sfv="Missing",
                    validation="Missing",
                    metadata="Missing",
                    metadata_status="AVAILABLE_NOT_CACHED",
                    identity_confidence="UNKNOWN",
                    readiness="NEEDS_VALIDATION",
                ),
            ]
        )

        self.assertEqual(report.status, HEALTH_ERROR)
        self.assertEqual(report.healthy, 1)
        self.assertEqual(report.missing_artwork, 1)
        self.assertEqual(report.missing_nfo, 1)
        self.assertEqual(report.missing_playlist, 1)
        self.assertEqual(report.missing_sfv, 1)
        self.assertEqual(report.missing_validation, 1)
        self.assertEqual(report.metadata_coverage, 50.0)
        self.assertEqual(report.identity_coverage, 50.0)

    def test_duplicate_and_unexpected_layout_warnings_are_included(self):
        report = archive_health_report(
            [
                album("1", title="Same"),
                album("2", title="Same"),
                album(
                    "3",
                    path="/archive/A/Artist/Albums/Artist-box-2024-WEB-FLAC-STiGMA/CD1",
                    readiness="ARCHIVE_READY",
                ),
            ]
        )

        self.assertEqual(report.duplicate_releases, 2)
        self.assertEqual(report.unexpected_layouts, 1)
        self.assertEqual(report.errors, 0)
        self.assertGreater(report.warnings, 0)

    def test_broken_layout_counts_unknown_readiness_with_archive_path(self):
        report = archive_health_report([album("1", readiness="UNKNOWN")])

        self.assertEqual(report.status, HEALTH_ERROR)
        self.assertEqual(report.broken_layouts, 1)
        self.assertEqual(report.errors, 1)

    def test_report_serializes_to_dict(self):
        payload = archive_health_report([album("1")]).to_dict()

        self.assertEqual(payload["albums"], 1)
        self.assertIn("metadata_coverage", payload)
        self.assertIn("duplicate_releases", payload)


if __name__ == "__main__":
    unittest.main()
