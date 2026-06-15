# Archive Browsing Vision

Date: 2026-06-15

Scope: Sprint F design-only vision. No GUI work, playback integration, schema change, or implementation is included.

## Product Direction

STiGMA Audio Division can evolve from a curator into a local-first music archive platform:

- Curator.
- Archive Manager.
- Validator Viewer.
- Metadata Browser.
- Music Browser.

The filesystem should remain truth. Derived registries, reports, metadata cache, and future indexes should make the archive understandable without taking ownership away from the archive itself.

## Architecture Implications

Future browsing needs a read model that joins:

- Lifecycle registry.
- Archive folders.
- Validator evidence.
- Deezer metadata cache.
- Generated NFO/artwork status.
- Optional future playback state.

This read model can start as JSON reports and later become a rebuildable SQLite index. The important rule is that browsing should query derived projections, not mutate source workflows.

## Future Views

### Library View

Purpose:

- Give a complete overview of known albums and archived albums.

Shows:

- Album count.
- Validated count.
- Confirmed count.
- Archive confidence.
- Recently validated releases.
- Stuck releases.
- Duplicate candidates.
- Missing metadata/NFO/artwork indicators.

Required data:

- Lifecycle registry.
- Archive identity entries.
- Validator evidence.
- Metadata cache.

Dependencies:

- Identity resolution layer.
- Archive manifest or folder scanner.
- Metadata enrichment.

Architecture implications:

- Needs fast filtering and sorting.
- Should read from a derived index.
- Should expose evidence and confidence instead of hiding ambiguity.

### Artist View

Purpose:

- Show what is known, owned, missing, and validated for one artist.

Shows:

- Artist identity.
- Discovered albums.
- Archived albums.
- Validated/confirmed coverage.
- Missing or unattempted releases.
- Duplicate release candidates.
- Related contributors later.

Required data:

- Deezer artist ID.
- Artist file rows.
- Lifecycle states.
- Metadata cache.
- Archive links.

Dependencies:

- Artist identity normalization.
- Contributor model.
- Metadata cache.

Architecture implications:

- Artist name alone is not enough.
- Compilation and featured-artist relationships should be explicit.

### Album View

Purpose:

- Explain one album/release completely.

Shows:

- Title, artist, release date, UPC, label, type.
- Lifecycle states.
- Archive folder path.
- Validation evidence and age.
- Track list.
- Hash/manifest status.
- NFO/artwork status.
- Candidate duplicate releases.

Required data:

- Lifecycle row.
- Metadata cache.
- Archive identity entry.
- Validator evidence.
- Future NFO status.

Dependencies:

- Identity resolution.
- Ordered track metadata.
- Validator evidence import.

Architecture implications:

- Album view must support uncertainty: one Deezer album can have no archive entry, one archive entry can have no Deezer album, and one release candidate can have multiple Deezer IDs.

### Track View

Purpose:

- Browse recordings and diagnose track-level identity.

Shows:

- Track title.
- Disc and track number.
- Duration.
- Deezer track ID.
- ISRC.
- Local file path.
- SHA256.
- Validation status.
- Other releases containing same ISRC.

Required data:

- Cached track metadata.
- Local file manifest.
- Validator hashes.
- Embedded local tags.

Dependencies:

- Metadata enrichment.
- Archive manifest.
- Track-level identity model.

Architecture implications:

- Track rows need both provider identity and local file identity.
- ISRC is the central recording key but cannot replace local file hash.

### Archive Health View

Purpose:

- Make archive safety and completeness visible.

Shows:

- Validation coverage.
- Hash coverage.
- Metadata coverage.
- NFO coverage.
- Unmatched validation logs.
- Stale validations.
- Missing album IDs.
- Duplicate manifests.
- Files needing repair.

Required data:

- Validator evidence.
- Archive scanner.
- Metadata cache.
- Lifecycle registry.

Dependencies:

- Identity resolution.
- Manifest hash design.
- Reportable quality metrics.

Architecture implications:

- Should separate "not archived", "archived but unvalidated", "validated but unidentified", and "identified but stale".

### Coverage View

Purpose:

- Help decide what to process next.

Shows:

- Artist coverage.
- Discovery backlog.
- Attempted but not shipped.
- Shipped but not validated.
- Validated but not discovered.
- Confirmed but not validated.
- Metadata gaps.

Required data:

- Lifecycle registry.
- Archive intelligence reports.
- Metadata cache.
- Identity resolution candidates.

Dependencies:

- Existing Sprint C/D reports.
- Future metadata coverage metrics.

Architecture implications:

- Coverage should be explainable from source evidence.
- Backlog prioritization can later use popularity, fan count, missing release dates, or manual preferences.

## Browsing Data Model

Recommended derived read objects:

- `LibrarySummary`
- `ArtistSummary`
- `AlbumSummary`
- `TrackSummary`
- `ArchiveEntrySummary`
- `ValidationEvidenceSummary`
- `IdentityCandidate`
- `QualitySignal`

These objects should be projections over source files, not new authority.

## UX Principles

- Always show confidence when an archive folder is linked to a lifecycle album.
- Make evidence inspectable: source file, validation log, hashes, metadata fetch time.
- Keep "known to Deezer", "present on disk", "validated", and "confirmed" visually distinct.
- Let unmatched archive folders exist as first-class objects.
- Prefer review queues for ambiguous identity decisions.
- Avoid hiding destructive actions inside browsing surfaces.

## Roadmap Dependencies

Before a full archive browser:

1. Identity resolution layer.
2. Metadata cache.
3. Archive manifest/hash model.
4. NFO status projection.
5. Rebuildable index, likely SQLite.

An early browser prototype can exist before SQLite, but it will be limited by JSON projection performance and identity uncertainty.

## Recommendation

Do not build the archive browser first. Build identity resolution and metadata enrichment first, then use those outputs to create a small read-only browser prototype. The browser should make uncertainty visible rather than forcing every archive folder into a lifecycle album row.
