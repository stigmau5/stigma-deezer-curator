# Physical Archive Browser

Sprint X adds a filesystem-native Archive tab to STiGMA Archive Hub.

## Philosophy

The Library tab answers: what does the lifecycle system know?

The Archive tab answers: what is physically present in the archive?

Filesystem evidence is the first-class source for this view. The browser is derived from `data/archive_registry.json` and does not scan the filesystem directly from the GUI.

## Data Priority

Archive browsing prefers evidence in this order:

1. Archive Registry
2. Physical artifacts
3. Validation evidence
4. Metadata Cache
5. Lifecycle Registry

No SQLite database is introduced.

## Projection

The lightweight archive projection creates album records with:

- artist
- album title
- archive path
- artwork evidence
- NFO evidence
- playlist evidence
- SFV evidence
- validation evidence
- readiness
- health

The records are compatible with `audio_division.album_workspace`, so Archive and Library selections share one album viewer model.

## Browser Model

The Archive tab uses three panes:

- Archive tree: artist list derived from archive folders.
- Album list: physical albums under the selected artist.
- Album workspace: cover, status, tracklist, NFO, metadata/identity placeholders, and operations.

Simple filters are available for artist and album text.

## Relationship To Library

Library remains lifecycle-driven and is not replaced.

Archive is filesystem-driven and exposes unresolved physical folders that lifecycle identity may not yet know how to join.

Together they provide:

- Lifecycle View: what STiGMA knows.
- Archive View: what STiGMA has.

## Operations

Archive selections reuse the existing operation runner:

- Open Folder
- Validate Album
- Generate NFO
- Generate SFV

No operation is automatic.

## Future Role

The Archive tab is the natural foundation for:

- playback
- playlist loading
- archive repair workflows
- NFO inspection
- physical-folder identity review
- visual artwork browsing
