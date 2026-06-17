# Library Browser

The Library Browser is a read-only archive browsing prototype for STiGMA Audio Division.

It does not modify archive files.

It does not fetch metadata.

It does not play audio.

It does not execute archive operations.

## Data Sources

The browser reads:

- `data/lifecycle_registry.json`
- `data/identity_registry.json`
- `data/metadata_cache.json`

Metadata cache is preferred for enriched album, artist, track, label, genre, date, duration, and artwork references.

Lifecycle registry is used as fallback when metadata is missing.

Identity registry provides identity confidence.

## Browsing Model

The `audio_division/library.py` module builds a derived read model:

- artist index
- album index
- albums grouped by artist
- album detail records
- library summary

The GUI tab stays thin and renders this read model.

## Current Views

Library summary:

- Artists
- Albums
- Tracks
- Metadata Coverage
- Validation Coverage

Artist browser:

- Artist name
- Album count

Album browser:

- Title
- Year
- Record type
- Validation status

Album details:

- Album title
- Artist
- Year
- Release date
- Label
- Genres
- Track count
- Duration
- Lifecycle state
- Identity confidence
- Validation status
- Metadata status
- Archive strength signals
- Artwork URL/reference when cached

## Limitations

- Artwork URLs are displayed as references only.
- Artwork is not downloaded.
- Local artwork discovery is not implemented yet.
- Sorting is basic and local to the current view.
- Track-level browsing is not implemented yet.
- No album actions are exposed from the Library tab in this sprint.

## Future Ideas

- Playback.
- Artwork cache.
- NFO viewing.
- Album actions.
- Artist completeness.
- Missing releases.
- Track browsing.
- Local artwork detection.
- Rich filtering by lifecycle, identity confidence, validation, genre, year, and label.
