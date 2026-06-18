# Metadata Bridge

The Archive tab is filesystem-first. It starts from `data/archive_registry.json`, then enriches the selected album with existing identity and metadata evidence.

No network calls are made. Deezer is not queried by this layer.

## Data Flow

Archive selection:

1. Archive Registry album folder
2. Identity Registry release match
3. Deezer album ID
4. Metadata Cache album lookup
5. Album Workspace presentation

The archive folder remains the physical source of truth. Metadata only fills descriptive fields such as label, genres, release date, record type, cached artwork URLs, and contributors.

## Matching Rules

The bridge first compares normalized release folder names. Source and group tags such as `WEB`, `FLAC`, and `STiGMA` are ignored for this comparison, allowing existing identity folder evidence to match physical archive folder names.

If folder normalization does not match, the bridge uses a guarded fallback:

- artist must match
- title must be present in the archive folder name
- year must match when both sides provide a year
- very short titles are ignored to avoid weak matches

If neither rule matches, the archive album remains identity-unknown.

## Metadata Status

When an album ID is available:

- `CACHED`: album metadata exists in `metadata_cache.json`
- `AVAILABLE_NOT_CACHED`: an album ID exists but metadata has not been imported
- `MISSING`: metadata import was attempted and failed

When no album ID is available:

- `UNKNOWN`: the archive album cannot be connected to a provider identity

These states are shown in the Album Workspace instead of leaving metadata fields blank without explanation.

## Evidence Priority

Physical archive evidence remains preferred:

1. filesystem artwork, NFO, playlists, and track files
2. validation evidence
3. identity registry
4. metadata cache
5. lifecycle data

Metadata is enrichment. It does not override physical archive artifacts.

## Future Work

Future improvements could add a manual identity review workflow for unmatched archive folders. That should remain explicit and user-driven; this bridge does not rewrite archive files or mutate metadata.
