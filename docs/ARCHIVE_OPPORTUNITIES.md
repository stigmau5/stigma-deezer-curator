# Archive Opportunities

Sprint P adds a read-only Archive Opportunities Center.

Opportunities are derived from existing registry, metadata, identity, and artifact evidence. They are recommendations only. Audio Division does not execute operations automatically and does not modify archive files while generating opportunities.

## Opportunity Categories

- `missing_nfo`
- `missing_sfv`
- `missing_playlist`
- `missing_validation`
- `missing_artwork`
- `low_album_health`
- `identity_review`
- `missing_metadata`

## Priority Model

Priorities are intentionally simple:

- `HIGH`: work that protects validated archive documentation or validates known albums.
- `MEDIUM`: work that improves identity, metadata, SFV coverage, or low album health.
- `LOW`: convenience or completeness work such as playlists and artwork.

Current examples:

- Validated album missing NFO: `HIGH`
- Album missing validation evidence: `HIGH`
- Validated album missing SFV: `MEDIUM`
- Identity uncertainty: `MEDIUM`
- Missing metadata: `MEDIUM`
- Low album health below 70%: `MEDIUM`
- Missing playlist: `LOW`
- Missing artwork: `LOW`

## Data Sources

The opportunities engine consumes the Library projection, which is derived from:

- `data/lifecycle_registry.json`
- `data/identity_registry.json`
- `data/metadata_cache.json`
- configured archive root when available

## Report

`reports/archive_opportunities_report.md` summarizes:

- total opportunities
- priorities
- category counts
- top opportunity examples

## Future Batch Workflows

Future phases may add explicit batch workflows:

- Generate Selected NFOs
- Validate Selected Albums
- Generate Missing SFVs
- Metadata Refresh Queue
- Batch Operations

Those workflows should remain explicit user actions and continue to use the operation runner.
