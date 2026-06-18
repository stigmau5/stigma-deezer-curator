# Album Truth

Album Truth is the central status model for album-level archive evidence.

It exists so Archive, Library, and Dashboard views do not independently decide whether validation, artwork, NFO, SFV, playlists, or metadata are present.

The album is the primary unit. Curator, Archive, and Settings should all ask the same derived album model what is true before rendering status or deciding which action is appropriate.

## Source Priority

Album Truth is derived in this order:

1. Filesystem artifacts
2. Validator evidence
3. Archive Registry artifacts
4. Metadata Cache
5. Reports and UI

Filesystem evidence wins. If an archive folder can be inspected and `STIGMA_VALIDATED.txt` is missing, validation is missing even if older lifecycle evidence says the album was validated.

## Artifact Rules

- `cover.jpg`, `folder.jpg`, `front.jpg`, `cover.png`, or `folder.png` imply artwork presence.
- Any local `.nfo` file, including `release.nfo`, implies NFO presence.
- Any local `.sfv` file, including `release.sfv`, implies SFV presence.
- Any local `.m3u` or `.m3u8` file, including `playlist.m3u8`, implies playlist presence.
- `STIGMA_VALIDATED.txt` implies validation presence.
- Cached album metadata implies metadata presence.

Audio Division generated files are treated as normal filesystem artifacts. The Hub does not need separate workflow knowledge to recognize them.

## Album Model

`AlbumTruth` exposes:

- `artist`
- `album`
- `archive_path`
- `artwork_present`
- `nfo_present`
- `sfv_present`
- `playlist_present`
- `validation_present`
- `metadata_status`
- `identity_confidence`
- `health`
- `readiness`
- `processing_state`
- `source`

The model is derived and rebuildable. It is not a database and it does not become archive truth.

## Output Shape

The engine emits the existing `album_status` structure:

```json
{
  "items": {
    "validation": "Present",
    "nfo": "Present",
    "sfv": "Missing",
    "playlist": "Present",
    "artwork": "Present",
    "metadata": "Present"
  },
  "health_percent": 83
}
```

Additional source metadata records where each decision came from.

## Processing State

Sprint AB introduces a closed-loop foundation without automation.

Processing states:

- `DISCOVERED`: the album is known, but no archive path is known.
- `DOWNLOADED`: an archive path is known, but no processing artifacts are present.
- `PROCESSING`: an archive path exists and at least one processing artifact is present.
- `ARCHIVED`: validation, NFO, and SFV evidence are present.

These states are informational. Audio Division does not automatically launch validation, NFO generation, SFV generation, metadata import, or playback from this model.

## Album-Centric Pipeline

Future source-agnostic flow:

```text
Filesystem / Validator / Registry / Metadata
-> AlbumTruth
-> Archive Browser / Library / Dashboard / Operations
```

Reports and UI are consumers, not truth sources. If they disagree with `AlbumTruth`, the report or UI is stale.

## Consumers

- Archive album projection
- Library album projection
- Archive readiness
- Dashboard validation summary

The model is derived only. It does not modify archive files, metadata cache files, validator outputs, or lifecycle data.
