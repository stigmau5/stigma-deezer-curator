import tempfile
import unittest
from pathlib import Path

from audio_division.archive_audit import (
    audit_archive,
    broken_playlist_references,
    broken_sfv_references,
    render_archive_audit,
)
from audio_division.archive_registry import album_entry


class ArchiveAuditTests(unittest.TestCase):
    def make_album(self, root: Path, name: str = "artist-album-2026-WEB-FLAC-STiGMA") -> Path:
        album = root / "A" / "artist" / "Albums" / name
        album.mkdir(parents=True)
        return album

    def test_healthy_album_has_no_issues(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            album = self.make_album(root)
            (album / "01.flac").write_text("audio", encoding="utf-8")
            (album / "cover.jpg").write_text("art", encoding="utf-8")
            (album / "release.nfo").write_text("nfo", encoding="utf-8")
            (album / "release.sfv").write_text("01.flac 1234ABCD\n", encoding="utf-8")
            (album / "playlist.m3u8").write_text("01.flac\n", encoding="utf-8")
            (album / "STIGMA_VALIDATED.txt").write_text("ok", encoding="utf-8")
            registry = {"archive_root": str(root), "albums": [album_entry(album, root)]}

            report = audit_archive(registry, root)

        self.assertEqual(report["summary"]["albums_scanned"], 1)
        self.assertEqual(report["summary"]["healthy"], 1)
        self.assertEqual(report["summary"]["warnings"], 0)
        self.assertEqual(report["summary"]["errors"], 0)

    def test_missing_artifacts_are_warnings(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            album = self.make_album(root)
            (album / "01.flac").write_text("audio", encoding="utf-8")
            registry = {"archive_root": str(root), "albums": [album_entry(album, root)]}

            report = audit_archive(registry, root)
            categories = {issue["category"] for issue in report["issues"]}

        self.assertIn("missing_artwork", categories)
        self.assertIn("missing_nfo", categories)
        self.assertIn("missing_sfv", categories)
        self.assertIn("missing_playlist", categories)
        self.assertIn("missing_validation", categories)
        self.assertEqual(report["summary"]["errors"], 0)

    def test_playlist_and_sfv_reference_validation(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            album = self.make_album(root)
            (album / "01.flac").write_text("audio", encoding="utf-8")
            (album / "playlist.m3u8").write_text("#EXTM3U\n01.flac\n02.flac\n", encoding="utf-8")
            (album / "release.sfv").write_text("; comment\n01.flac 1234ABCD\nmissing.flac DEADBEEF\n", encoding="utf-8")

            playlist_broken = broken_playlist_references(album)
            sfv_broken = broken_sfv_references(album)

        self.assertEqual(playlist_broken, ["playlist.m3u8: 02.flac"])
        self.assertEqual(sfv_broken, ["release.sfv: missing.flac"])

    def test_multidisc_references_and_unexpected_layout(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            album = self.make_album(root)
            cd1 = album / "CD1"
            bonus = album / "Bonus"
            cd1.mkdir()
            bonus.mkdir()
            (cd1 / "01.flac").write_text("audio", encoding="utf-8")
            (bonus / "02.flac").write_text("audio", encoding="utf-8")
            (album / "playlist.m3u8").write_text("CD1/01.flac\nBonus/02.flac\n", encoding="utf-8")
            registry = {"archive_root": str(root), "albums": [album_entry(album, root)]}

            report = audit_archive(registry, root)
            categories = [issue["category"] for issue in report["issues"]]

        self.assertIn("unexpected_layout", categories)
        self.assertNotIn("broken_playlist_reference", categories)

    def test_report_rendering_lists_counts_and_issues(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            album = self.make_album(root)
            registry = {"archive_root": str(root), "albums": [album_entry(album, root)]}

            text = render_archive_audit(audit_archive(registry, root))

        self.assertIn("# Archive Audit", text)
        self.assertIn("Albums scanned", text)
        self.assertIn("Missing audio", text)
        self.assertIn("artist-album-2026-WEB-FLAC-STiGMA", text)


if __name__ == "__main__":
    unittest.main()
