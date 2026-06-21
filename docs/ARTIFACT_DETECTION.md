# Canonical Artifact Detection

`audio_division.artifacts.detect_artifacts()` is the sole filesystem detector for album artifacts.

The canonical `AlbumArtifacts` model records:

- audio files at the album root and in recognized `CD` / `Disc` folders;
- artwork files and the preferred local artwork;
- NFO files;
- SFV files;
- playlists;
- `STIGMA_VALIDATED.txt` markers.

It exposes file lists, presence, counts, deterministic first/preferred selection, a canonical dictionary projection, and the legacy Archive Registry dictionary projection.

Archive Audit, Archive Registry, AlbumTruth, Integrity Inspector, Album Workspace, reconciliation, playback, cover selection, lifecycle marker checks, and Library projection all consume this detector. Their existing selection and reporting behavior is preserved; the refactor only removes duplicate filesystem classification.
