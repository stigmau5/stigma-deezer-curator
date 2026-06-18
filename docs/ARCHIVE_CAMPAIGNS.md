# Archive Campaigns

Archive Campaigns are derived views over album evidence.

They group albums that need the same kind of archive work without creating a new database, schema, or truth source. `AlbumTruth` remains the canonical representation of album state.

## Campaigns

Initial campaigns:

- Missing NFO
- Missing SFV
- Missing Validation
- Missing Artwork
- Metadata Available Not Cached

Each campaign displays:

- Campaign Name
- Album Count

Selecting a campaign shows matching albums.

## Actions

Supported selected-album actions:

- Validate Selected
- Generate NFO Selected
- Generate SFV Selected

Actions run only for selected albums in the visible campaign album list. If no campaign albums are selected, the current implementation treats the visible campaign list as the selection.

Future support may add `Run Entire Campaign`, but Sprint AE intentionally keeps execution selected and user-initiated.

## Source Of Truth

Campaigns are derived from existing album projections:

```text
AlbumTruth / album_status
-> Campaigns
-> Selected album operations
```

Reports and UI are not truth sources. If archive files change, rebuild or refresh the archive registry so `AlbumTruth` can update, then campaigns will update from that evidence.

## Non-Goals

Sprint AE does not:

- Introduce SQLite
- Add a new top-level tab
- Automatically process entire campaigns
- Create a new archive state model
- Replace the validator
- Replace Audio Division
