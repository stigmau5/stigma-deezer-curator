# Metadata Enrichment Strategy

Date: 2026-06-15

Scope: Sprint F research-only strategy. This document recommends future metadata caching; it does not implement a cache, network workflow, schema, or database.

## Why Metadata Enrichment Matters

The current lifecycle registry can answer operational questions because Deezer album ID already connects discovery, attempts, shipments, validation index entries, and confirmations.

It cannot yet answer deeper archive questions:

- Are two Deezer album IDs the same real-world release?
- Is this archive folder the same release as a lifecycle row?
- Which local files correspond to which Deezer tracks?
- Which albums are missing UPC, ISRC, cover art, NFO, or validation confidence?
- Which artists are incomplete by release family rather than only by discovered rows?

Those questions require cached metadata beyond the current minimal `artist/title/year/tracks` contract.

## Must Have Fields

### Album

- Deezer album ID.
- Title.
- UPC.
- Release date.
- Record type.
- Track count.
- Duration.
- Main artist ID and name.
- Contributors with IDs, names, and roles.
- Tracklist URL or embedded track data.
- Explicit flag.
- Availability flag.
- Source URL.
- Fetched timestamp.

Archive value:

- Provides provider identity, release identity, duplicate detection, and future repair context.

NFO value:

- Title, artist, date, record type, label/contributors when available, source URL.

Browsing value:

- Album page, release date sorting, contributor display, explicit indicators.

Reporting value:

- Missing metadata, duplicate UPCs, stale provider metadata, release-type counts.

### Track

- Deezer track ID.
- Title.
- ISRC.
- Duration.
- Track position.
- Disc number.
- Artist ID and name.
- Contributors with IDs, names, and roles.
- Explicit flag.
- Readable/availability status.

Archive value:

- Ordered ISRC list and track order are the key bridge between provider releases and local files.

NFO value:

- Track listing, credits, durations, disc structure.

Browsing value:

- Track view, search, per-track credits.

Reporting value:

- Missing ISRC coverage, duplicate recordings, duration mismatches, incomplete tracklists.

### Artist

- Deezer artist ID.
- Name.
- Link.
- Picture IDs/URLs.
- Album count.
- Fetched timestamp.

Archive value:

- Prevents artist-name ambiguity.

NFO value:

- Optional source references and display names.

Browsing value:

- Artist pages, artist art, related navigation later.

Reporting value:

- Discovery coverage and artist completeness.

## Nice To Have Fields

Album:

- Label.
- Genres.
- Cover art URLs.
- `md5_image`.
- Fan/popularity count.
- Explicit content detail fields.

Track:

- Preview URL.
- Rank.
- BPM.
- Gain.
- Available countries.
- Track share/link URL.

Artist:

- Fan count.
- Related artists.
- Top tracks.
- Radio flag.

Archive value:

- Improves duplicate review, prioritization, and enrichment quality.

NFO value:

- Label, genre, art URL, and credits are useful NFO material.

Browsing value:

- Artwork, genre navigation, related artists, popular tracks.

Reporting value:

- Missing artwork reports, genre coverage, popularity-informed backlog.

## Future Use Fields

- Provider availability history.
- Cover image hashes.
- Country availability.
- Popularity/rank trend.
- Related-artist graph snapshots.
- BPM/gain for audio analysis.
- Multiple provider IDs if other services are added.

These should not block identity resolution, but the cache design should leave space for them.

## Cache Architecture Recommendation

### Phase 1: File-Based Metadata Cache

Use JSON files under a derived cache directory, not as source of truth:

```text
data/metadata_cache/
  deezer/
    albums/
      302127.json
    artists/
      27.json
    tracks/
      3135556.json
```

Rationale:

- Minimal architecture change.
- Easy to inspect and rebuild.
- Compatible with current local-first workflow.
- Avoids premature SQLite design.
- Lets identity resolution consume stable snapshots without making network calls during report generation.

Each cache record should include:

- Provider.
- Provider ID.
- Raw payload or normalized payload.
- Fetched timestamp.
- Fetch status.
- Optional API error.
- Schema version for the cache file only.

### Phase 2: Normalized Derived Views

Create derived reports or JSON projections:

- Album release keys.
- Track ISRC sequences.
- Contributor graph.
- Duplicate UPC report.
- Missing metadata report.

These should be rebuildable from cache files.

### Phase 3: SQLite Index, Later

SQLite should index the file cache and filesystem evidence only after identity resolution and cache shape have matured.

The database should remain rebuildable. It should not become the authority for archive existence.

## Cache Refresh Rules

Recommended future policy:

- Never fetch during validation, lifecycle report generation, or GUI browsing unless explicitly requested.
- Cache by provider ID.
- Preserve previous fetched payloads until replacement succeeds.
- Treat failed fetches as retryable.
- Record fetch timestamp and source URL.
- Allow manual refresh of a provider album ID.
- Do not overwrite local identity decisions based only on refreshed provider metadata.

## Metadata Needed for Identity Resolution

Highest priority:

- Album UPC.
- Album release date.
- Deezer artist ID.
- Ordered track IDs.
- Ordered ISRC list.
- Track titles.
- Track positions and disc numbers.
- Track durations.
- Contributor IDs and roles.
- Explicit flags.

These fields are enough to move many archive matches from low or medium confidence to high confidence.

## Metadata Needed for Archive Browsing

Highest priority:

- Album title, artist, release date, cover art.
- Track list and durations.
- Contributor names.
- Validation status and evidence.
- Archive folder path.
- Lifecycle state.

Nice additions:

- Genre.
- Label.
- Artist pictures.
- Related artists.
- Popularity/fan counts.

## Risks

- Deezer metadata can change over time.
- UPC can be wrong or missing.
- ISRCs can repeat across releases.
- Fetching at scale can hit network/API reliability limits.
- Raw payloads can contain fields not useful to STiGMA and increase cache size.
- Cache files can be mistaken for truth unless documentation is clear.

## Recommendation

Do not jump directly to SQLite. First implement a file-based Deezer metadata cache that captures album, artist, and track identity fields needed by identity resolution. The next implementation sprint should prioritize resolving archive evidence to lifecycle entities; metadata caching should follow immediately if identity resolution needs provider fields that are not already local.
