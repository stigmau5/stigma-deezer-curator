# Metadata Intelligence

Sprint S makes metadata a first-class archive intelligence asset.

This sprint does not fetch metadata and does not modify the metadata cache schema. All calculations use the existing `data/metadata_cache.json` and lifecycle album ids.

## Metadata States

`CACHED`

Album metadata exists in `metadata_cache.json`.

`AVAILABLE_NOT_CACHED`

The album has a provider album id, so metadata can be imported later, but it is not currently cached.

`MISSING`

Audio Division has evidence that metadata import was attempted and failed. Current evidence comes from `metadata_cache.json` errors.

`UNKNOWN`

No album id is available for metadata lookup.

## Coverage Calculations

Metadata coverage is:

```text
cached albums / total lifecycle albums
```

The dashboard also shows state counts so uncached albums are not mislabeled as missing.

## Collection Intelligence

Collection reports use cached metadata only:

- labels
- release years
- genres
- record types
- artist counts
- track counts
- total cached duration
- ISRC coverage for cached tracks

These reports describe the imported metadata subset, not the entire archive.

## Future Metadata Imports

Future user-initiated actions could include:

- Import Artist Metadata
- Import Album Metadata
- Import Missing Metadata
- Refresh Metadata

Future imports should be explicit, resumable, rate-limit aware, and should preserve the existing cache schema until a migration is intentionally approved.
