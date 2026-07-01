import tempfile
import unittest
from pathlib import Path

from audio_division.album_workspace import album_workspace
from audio_division.canonical_album import AlbumRef, CanonicalAlbumResolver


class CanonicalAlbumResolverTests(unittest.TestCase):
    def archive_row(self, path: str, name: str = "Alpha Artist - Cached Album"):
        return {
            "name": name,
            "archive_path": path,
            "relative_path": f"A/alpha/Albums/{name}",
            "track_count": 1,
            "artifacts": {
                "exists": True,
                "nfo": True,
                "sfv": True,
                "playlist": True,
                "artwork": True,
                "validation_log": True,
                "counts": {"nfo": 1, "sfv": 1, "playlist": 1, "artwork": 1, "validation_log": 1},
            },
        }

    def lifecycle(self):
        return {
            "albums": [
                {
                    "album_id": "42",
                    "artist": "Alpha Artist",
                    "title": "Cached Album",
                    "highest_state": "VALIDATED",
                    "states": {"validated": True},
                    "details": {"validated_tracks": 1},
                }
            ]
        }

    def identity(self, folder: str = "Alpha Artist - Cached Album"):
        return {
            "releases": [
                {
                    "discovery_identity": {
                        "deezer_album_id": "42",
                        "artist": "Alpha Artist",
                        "title": "Cached Album",
                    },
                    "archive_identity": {"folder": folder},
                    "identity_confidence": "HIGH",
                    "validation": {"available": True},
                }
            ]
        }

    def metadata(self, album_id: str = "42", title: str = "Cached Album"):
        return {
            "albums": {
                album_id: {
                    "title": title,
                    "year": 2001,
                    "release_date": "2001-03-07",
                    "record_type": "album",
                    "label": "Label",
                    "genres": [{"name": "Dance"}],
                    "track_count": 1,
                    "artist": {"name": "Alpha Artist"},
                    "contributors": [{"name": "Alpha Artist", "role": "Main"}],
                    "covers": {"medium": "https://example.test/cover.jpg"},
                }
            },
            "artists": {},
            "tracks": {},
        }

    def test_archived_album_resolves_to_physical_archive_entry(self):
        with tempfile.TemporaryDirectory() as tmp:
            album_dir = Path(tmp) / "Alpha Artist - Cached Album"
            album_dir.mkdir()
            resolver = CanonicalAlbumResolver(
                archive_registry={"albums": [self.archive_row(str(album_dir))]},
                identity_registry=self.identity(),
                lifecycle_registry=self.lifecycle(),
                metadata_cache=self.metadata(),
            )

            canonical = resolver.resolve(AlbumRef(album_id="42"))

        self.assertEqual(canonical.source, "archive_registry")
        self.assertTrue(canonical.filesystem_bound)
        self.assertEqual(canonical["archive_path"], str(album_dir))
        self.assertEqual(canonical["album_id"], "42")
        self.assertEqual(canonical["metadata_status"], "CACHED")
        self.assertEqual(canonical["catalog_lifecycle_state"], "VALIDATED")
        self.assertTrue(canonical["canonical_sources"]["archive_registry"])

    def test_catalog_only_album_resolves_without_filesystem_evidence(self):
        resolver = CanonicalAlbumResolver(
            archive_registry={"albums": []},
            identity_registry=self.identity(),
            lifecycle_registry=self.lifecycle(),
            metadata_cache=self.metadata(),
        )

        canonical = resolver.resolve(AlbumRef(album_id="42"))
        workspace = album_workspace(canonical.details, self.metadata())

        self.assertEqual(canonical.source, "lifecycle_registry")
        self.assertFalse(canonical.filesystem_bound)
        self.assertEqual(canonical["archive_path"], "")
        self.assertEqual(workspace["files"]["source"], "missing")
        self.assertEqual(workspace["nfo"]["status"], "Missing")
        self.assertEqual(canonical["album_status"]["items"]["metadata"], "Present")

    def test_duplicate_identity_paths_resolve_to_same_physical_binding(self):
        archive_path = "/archive/Alpha Artist - Shared Album"
        identity = {
            "releases": [
                {
                    "discovery_identity": {"deezer_album_id": "1", "artist": "Alpha Artist", "title": "First"},
                    "archive_identity": {"folder": "Alpha Artist - Shared Album"},
                    "identity_confidence": "MEDIUM",
                },
                {
                    "discovery_identity": {"deezer_album_id": "2", "artist": "Alpha Artist", "title": "Second"},
                    "archive_identity": {"folder": "Alpha Artist - Shared Album"},
                    "identity_confidence": "HIGH",
                },
            ]
        }
        metadata = self.metadata("2", "Second")
        resolver = CanonicalAlbumResolver(
            archive_registry={"albums": [self.archive_row(archive_path, "Alpha Artist - Shared Album")]},
            identity_registry=identity,
            lifecycle_registry={"albums": []},
            metadata_cache=metadata,
        )

        first = resolver.resolve(AlbumRef(album_id="1"))
        second = resolver.resolve(AlbumRef(album_id="2"))

        self.assertEqual(first.source, "archive_registry")
        self.assertEqual(second.source, "archive_registry")
        self.assertEqual(first["archive_path"], archive_path)
        self.assertEqual(second["archive_path"], archive_path)
        self.assertEqual(second["album_id"], "2")
        self.assertEqual(second.identity_release["identity_confidence"], "HIGH")

    def test_regression_catalog_reference_rebinds_to_archive_artifacts(self):
        with tempfile.TemporaryDirectory() as tmp:
            album_dir = Path(tmp) / "Alpha Artist - Cached Album"
            album_dir.mkdir()
            (album_dir / "01.flac").write_bytes(b"audio")
            (album_dir / "release.nfo").write_text("nfo", encoding="utf-8")
            (album_dir / "release.sfv").write_text("01.flac 00000000", encoding="utf-8")
            (album_dir / "album.m3u8").write_text("#EXTM3U\n01.flac\n", encoding="utf-8")
            (album_dir / "cover.jpg").write_bytes(b"cover")
            (album_dir / "STIGMA_VALIDATED.txt").write_text("validated", encoding="utf-8")

            resolver = CanonicalAlbumResolver(
                archive_registry={"albums": [self.archive_row(str(album_dir))]},
                identity_registry=self.identity(),
                lifecycle_registry=self.lifecycle(),
                metadata_cache=self.metadata(),
            )

            presentation_ref = {
                "album_id": "42",
                "artist": "Alpha Artist",
                "title": "Cached Album",
            }
            canonical = resolver.resolve(presentation_ref)
            workspace = album_workspace(canonical.details, self.metadata())

        integrity = {check["id"]: check for check in workspace["integrity"]["checks"]}
        self.assertEqual(canonical.source, "archive_registry")
        self.assertEqual(workspace["cover"]["status"], "Present")
        self.assertEqual(workspace["files"]["source"], "filesystem")
        self.assertIn("01.flac", workspace["files"]["items"])
        self.assertEqual(workspace["nfo"]["status"], "Present")
        self.assertEqual(workspace["tracklist"]["source"], "playlist")
        self.assertEqual(integrity["artwork"]["status"], "Present")
        self.assertEqual(integrity["nfo"]["status"], "Present")
        self.assertEqual(integrity["playlist"]["status"], "Present")
        self.assertEqual(integrity["audio_files"]["status"], "Present")


if __name__ == "__main__":
    unittest.main()
