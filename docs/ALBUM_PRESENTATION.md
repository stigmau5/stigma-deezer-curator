# Album Presentation

Sprint U2 turns the Library album detail panel into an album-centric view while keeping the existing library model intact.

## Purpose

The presentation layer converts existing album detail dictionaries into stable display sections:

- Overview
- Artwork
- Archive Status
- Metadata
- Identity

It does not fetch metadata, download artwork, start playback, or modify archive files.

## Data Sources

Album presentation uses data already projected by `audio_division.library`:

- lifecycle state
- identity confidence
- archive path confidence
- metadata cache fields
- archive readiness
- detected archive artifacts
- local artwork paths or cached artwork URLs

## Thumbnail Behavior

Local artwork is preferred when an existing file path is available.

If local artwork cannot be loaded by Tk, the panel still displays artwork status and the source reference. Metadata artwork URLs are shown as references only; the Hub does not download artwork in this sprint.

Missing artwork is displayed as a normal archive status, not an error.

## Rebuild Philosophy

Album presentation is derived UI state. The filesystem remains truth, and registries remain rebuildable projections.

## Future Expansion

Future sprints can add richer artwork cache handling, NFO viewing, playlist inspection, album actions, and playback without changing the presentation contract introduced here.
