import unittest

from audio_division.maintenance import (
    documentation_operation_for_album,
    grouped_warnings,
    maintenance_action_target,
    maintenance_albums,
    maintenance_counts,
    maintenance_summaries,
)


def album(
    album_id: str,
    *,
    artist: str = "Artist",
    title: str = "Album",
    path: str = "/archive/A/Artist/Albums/Artist-album-2024-WEB-FLAC-STiGMA",
    validation: str = "Present",
    nfo: str = "Present",
    sfv: str = "Present",
    metadata: str = "CACHED",
    readiness: str = "ARCHIVE_READY",
    pipeline_state: str = "ARCHIVED",
):
    items = {
        "validation": validation,
        "nfo": nfo,
        "sfv": sfv,
        "playlist": "Present",
        "artwork": "Present",
        "metadata": "Present" if metadata == "CACHED" else "Missing",
    }
    return {
        "album_id": album_id,
        "artist": artist,
        "artist_key": artist.lower(),
        "title": title,
        "archive_path": path,
        "metadata_status": metadata,
        "album_truth": {"items": items, "readiness": readiness, "metadata_status": metadata},
        "album_status": {"items": items},
        "pipeline_state": {"state": pipeline_state, "evidence": ["test"], "reason": "test", "confidence": "HIGH"},
    }


class MaintenanceTests(unittest.TestCase):
    def test_maintenance_counts(self):
        albums = [
            album("1"),
            album("2", validation="Missing", readiness="NEEDS_VALIDATION", pipeline_state="DOWNLOADED"),
            album("3", nfo="Missing", readiness="NEEDS_DOCUMENTATION", pipeline_state="VALIDATED"),
        ]

        counts = maintenance_counts(albums)

        self.assertEqual(counts["albums"], 3)
        self.assertEqual(counts["artists"], 1)
        self.assertEqual(counts["validation_coverage"], 66.7)
        self.assertEqual(counts["documentation_coverage"], 66.7)
        self.assertEqual(counts["downloaded"], 1)
        self.assertEqual(counts["validated"], 1)
        self.assertEqual(counts["archived"], 1)

    def test_maintenance_categories(self):
        albums = [
            album("1"),
            album("2", validation="Missing", readiness="NEEDS_VALIDATION"),
            album("3", nfo="Missing", readiness="NEEDS_DOCUMENTATION"),
            album("4", metadata="AVAILABLE_NOT_CACHED", readiness="NEEDS_REVIEW"),
        ]

        summaries = {row["id"]: row["album_count"] for row in maintenance_summaries(albums)}

        self.assertEqual(summaries["archive_ready"], 1)
        self.assertEqual(summaries["needs_validation"], 1)
        self.assertEqual(summaries["needs_documentation"], 1)
        self.assertEqual(summaries["needs_metadata"], 1)

    def test_warning_grouping_detects_disc_rows_and_duplicates(self):
        albums = [
            album("1", title="Same"),
            album("2", title="Same"),
            album(
                "3",
                path="/archive/A/Artist/Albums/Artist-box-2024-WEB-FLAC-STiGMA/CD1",
                metadata="UNKNOWN",
                readiness="UNKNOWN",
            ),
        ]

        grouped = {row["type"]: row["count"] for row in grouped_warnings(albums)}

        self.assertEqual(grouped["duplicate_album"], 2)
        self.assertEqual(grouped["unexpected_structure"], 1)
        self.assertEqual(grouped["missing_metadata"], 1)
        self.assertEqual(len(maintenance_albums(albums, "warnings")), 3)

    def test_documentation_operation_routes_to_missing_artifact(self):
        self.assertEqual(documentation_operation_for_album(album("1", nfo="Missing")), "generate_nfo")
        self.assertEqual(documentation_operation_for_album(album("2", sfv="Missing")), "generate_sfv")

    def test_action_target_uses_existing_album_target(self):
        operation, target, reason = maintenance_action_target("generate_documentation", album("1", nfo="Missing"))

        self.assertEqual(operation, "generate_nfo")
        self.assertTrue(target.endswith("Artist-album-2024-WEB-FLAC-STiGMA"))
        self.assertEqual(reason, "ok")


if __name__ == "__main__":
    unittest.main()
