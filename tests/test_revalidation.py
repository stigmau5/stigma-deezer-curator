import tempfile
import unittest
from pathlib import Path

from audio_division.album_integrity import album_integrity
from audio_division.archive_registry import album_entry
from audio_division.revalidation import (
    HEALTH_ERROR,
    HEALTH_OK,
    HEALTH_WARNING,
    render_archive_revalidation_report,
    revalidate_album,
    revalidate_archive,
)


class ArchiveRevalidationTests(unittest.TestCase):
    def make_album(self, root: Path, name: str = "artist-album-2026-WEB-FLAC-STiGMA") -> Path:
        album = root / "A" / "artist" / "Albums" / name
        album.mkdir(parents=True)
        return album

    def make_healthy_album(self, root: Path) -> Path:
        album = self.make_album(root)
        (album / "01.flac").write_text("audio", encoding="utf-8")
        (album / "cover.jpg").write_text("art", encoding="utf-8")
        (album / "release.nfo").write_text("nfo", encoding="utf-8")
        (album / "release.sfv").write_text("01.flac 1234ABCD\n", encoding="utf-8")
        (album / "playlist.m3u8").write_text("01.flac\n", encoding="utf-8")
        (album / "STIGMA_VALIDATED.txt").write_text("ok", encoding="utf-8")
        return album

    def test_healthy_archive_album_is_ok(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            album = self.make_healthy_album(root)
            registry = {"archive_root": str(root), "albums": [album_entry(album, root)]}

            report = revalidate_archive(registry, root, identity_registry={}, lifecycle_registry={}, validated_index={})

        self.assertEqual(report["summary"]["albums_scanned"], 1)
        self.assertEqual(report["summary"]["healthy"], 1)
        self.assertEqual(report["summary"]["warnings"], 0)
        self.assertEqual(report["summary"]["errors"], 0)
        self.assertEqual(report["albums"][0]["health_category"], HEALTH_OK)

    def test_missing_artifacts_are_warning_breakdown_rows(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            album = self.make_album(root)
            (album / "01.flac").write_text("audio", encoding="utf-8")
            registry = {"archive_root": str(root), "albums": [album_entry(album, root)]}

            report = revalidate_archive(registry, root, identity_registry={}, lifecycle_registry={}, validated_index={})
            text = render_archive_revalidation_report(report)

        self.assertEqual(report["summary"]["warnings"], 1)
        self.assertEqual(report["breakdown"]["missing_artwork"], 1)
        self.assertEqual(report["breakdown"]["missing_nfo"], 1)
        self.assertEqual(report["breakdown"]["missing_sfv"], 1)
        self.assertEqual(report["breakdown"]["missing_playlist"], 1)
        self.assertEqual(report["breakdown"]["missing_validation"], 1)
        self.assertIn("# Archive Revalidation Report", text)
        self.assertIn("Missing artwork", text)

    def test_broken_references_are_errors(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            album = self.make_healthy_album(root)
            (album / "playlist.m3u8").write_text("missing.flac\n", encoding="utf-8")
            registry = {"archive_root": str(root), "albums": [album_entry(album, root)]}

            report = revalidate_archive(registry, root, identity_registry={}, lifecycle_registry={}, validated_index={})

        self.assertEqual(report["summary"]["errors"], 1)
        self.assertEqual(report["albums"][0]["health_category"], HEALTH_ERROR)

    def test_multidisc_layout_warnings_are_warnings_only(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            album = self.make_album(root)
            cd1 = album / "CD1"
            cd3 = album / "CD3"
            cd1.mkdir()
            cd3.mkdir()
            (cd1 / "01.flac").write_text("audio", encoding="utf-8")
            (album / "cover.jpg").write_text("art", encoding="utf-8")
            (album / "release.nfo").write_text("nfo", encoding="utf-8")
            (album / "release.sfv").write_text("CD1/01.flac 1234ABCD\n", encoding="utf-8")
            (album / "playlist.m3u8").write_text("CD1/01.flac\n", encoding="utf-8")
            (album / "STIGMA_VALIDATED.txt").write_text("ok", encoding="utf-8")

            result = revalidate_album(album_entry(album, root), root)

        self.assertEqual(result["health_category"], HEALTH_WARNING)
        self.assertIn("Missing disc folder(s): 2", result["warnings"])
        self.assertIn("Disc folder has no audio files: CD3", result["warnings"])

    def test_album_integrity_uses_revalidation_engine(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            album = self.make_healthy_album(root)

            result = album_integrity({"archive_path": str(album)})

        self.assertEqual(result["health_category"], HEALTH_OK)
        self.assertEqual(result["health_score"], 100)
        self.assertEqual(result["warnings"], [])


if __name__ == "__main__":
    unittest.main()
