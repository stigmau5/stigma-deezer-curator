# Album Truth

Album Truth is the central status model for album-level archive evidence.

It exists so Archive, Library, and Dashboard views do not independently decide whether validation, artwork, NFO, SFV, playlists, or metadata are present.

## Source Priority

Album Truth is derived in this order:

1. Filesystem artifacts
2. Validator evidence
3. Archive Registry artifacts
4. Metadata Cache

Filesystem evidence wins. If an archive folder can be inspected and `STIGMA_VALIDATED.txt` is missing, validation is missing even if older lifecycle evidence says the album was validated.

## Artifact Rules

- `cover.jpg`, `folder.jpg`, `front.jpg`, `cover.png`, or `folder.png` imply artwork presence.
- Any local `.nfo` file, including `release.nfo`, implies NFO presence.
- Any local `.sfv` file, including `release.sfv`, implies SFV presence.
- Any local `.m3u` or `.m3u8` file, including `playlist.m3u8`, implies playlist presence.
- `STIGMA_VALIDATED.txt` implies validation presence.
- Cached album metadata implies metadata presence.

Audio Division generated files are treated as normal filesystem artifacts. The Hub does not need separate workflow knowledge to recognize them.

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

## Consumers

- Archive album projection
- Library album projection
- Archive readiness
- Dashboard validation summary

The model is derived only. It does not modify archive files, metadata cache files, validator outputs, or lifecycle data.
