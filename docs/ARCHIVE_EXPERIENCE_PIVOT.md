# Archive Experience Pivot

Sprint W shifts STiGMA Hub from a dashboard-centric application toward an archive-centric music workstation.

## Architecture Proposal

The existing intelligence systems remain intact:

- Lifecycle Registry
- Identity Registry
- Metadata Cache
- Archive Registry
- Archive Readiness
- Validation Evidence
- Opportunities
- Reports

These systems should support browsing instead of competing with it. The archive remains the product, and reports remain supporting tools.

Filesystem evidence has priority:

1. Archive folder contents
2. Playlists and documentation artifacts
3. Validator evidence
4. Metadata cache
5. Derived reports

The album workspace becomes the primary integration point. A selected album should gather cover art, track order, NFO contents, validation state, documentation state, readiness, and operations into one place.

## GUI Mockup Proposal

The target Library layout moves toward the older STiGMA Music Directory Scanner pattern:

```text
+ Artists + Albums +---------------- Album Workspace ----------------+
|        |                 | Cover          | Status                  |
|        |                 |                | Validation / NFO / SFV  |
|        |                 |                | Playlist / Artwork      |
|        |                 +------------------------------------------+
|        |                 | Tracklist                | NFO           |
|        |                 | filesystem/playlist      | actual text   |
|        |                 +------------------------------------------+
|        |                 | Operations: Validate / Generate NFO / ...|
+--------+-----------------+------------------------------------------+
```

Dashboards stay available, but Library and album workspace become the main daily experience.

## Incremental Implementation Plan

### W1 Album Workspace

- Larger persistent artwork area.
- Status visible at a glance.
- Actual NFO contents displayed when available.
- Tracklist derived from playlist, filesystem, then metadata cache.
- Existing album operations stay on the album page.

### W2 Visual Artwork Grid

- Replace artwork table with real cover cards.
- Keep artist and album filtering.
- Open album/folder from selected card.

### W3 Archive Tree Browser

- Add physical archive tree from Archive Registry.
- Selecting an archive folder opens the same album workspace.
- Expose unresolved archive folders without requiring lifecycle identity.

### W4 Documentation View

- Dedicated NFO/SFV/playlist inspection.
- Diff/regeneration preview hooks.
- No automatic mutation.

### W5 Player Foundation

- Load playlist or folder into a controlled playback layer.
- Keep filesystem order as truth.
- No metadata requirement for playback.

## First Implementation

Sprint W implements the first album workspace data layer and updates Library details to use it. This is read-only except for existing explicit operation buttons.
