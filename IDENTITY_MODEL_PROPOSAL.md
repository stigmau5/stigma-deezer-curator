# Identity Model Proposal

Date: 2026-06-15

Scope: Sprint F architecture proposal. This document designs a future identity model only. It does not introduce a schema, database, migration, source of truth, or implementation.

## Design Principles

- Filesystem remains truth.
- Existing state files remain operational truth for current workflows.
- Derived registries and future indexes must be rebuildable.
- Provider identity and archive identity are related but not the same thing.
- Identity resolution must preserve uncertainty instead of hiding it.
- Folder-name-only matches must be treated as candidates, not facts.

## Proposed Identity Layers

### 1. Discovery Identity

Purpose: identify what STiGMA found or was asked to process.

Primary keys:

- Deezer album ID.
- Deezer artist ID.

Secondary keys:

- Deezer album URL.
- Deezer artist URL.
- Deezer track IDs from album tracklists.
- Discovery source file and line.
- Expansion timestamp.

Use cases:

- Avoid processing the same Deezer album repeatedly.
- Track discovered, attempted, shipped, confirmed, and validated states.
- Requery provider metadata.
- Explain why an album exists in the system.

Limitations:

- Deezer album ID is provider-local.
- Multiple Deezer album IDs can represent the same real-world release.
- Deezer metadata can change after discovery.

### 2. Release Identity

Purpose: identify the real-world release or release candidate.

Primary keys when available:

- UPC.
- Ordered ISRC list.
- Main artist provider IDs.
- Release title.
- Release date.
- Track count.

Secondary keys:

- Label.
- Record type.
- Duration.
- Contributor IDs and roles.
- Explicit/clean flags.
- Cover image hash or Deezer `md5_image`.

Use cases:

- Detect duplicate Deezer album IDs for the same release.
- Distinguish deluxe, remaster, compilation, clean, explicit, and anniversary variants.
- Support NFO generation.
- Support archive browsing and collection intelligence.

Limitations:

- UPC can be missing, malformed, reused, or shared across variants.
- ISRC lists can overlap across compilations and reissues.
- Release dates and titles are descriptive signals, not unique identifiers.

### 3. Archive Identity

Purpose: identify what exists on disk.

Primary keys:

- Archive root.
- Archive-relative folder path.
- Album manifest hash.

Secondary keys:

- Folder name.
- File list.
- Per-file SHA256 hashes.
- Embedded album tags.
- Embedded album artist tags.
- Embedded title, track number, disc number, date, ISRC, and `ALBUM_ID` tags.

Use cases:

- Determine what is actually archived.
- Detect exact duplicate folders.
- Detect moved or renamed folders.
- Support archive repair.
- Verify that an archived folder still contains the same files previously validated.

Limitations:

- Folder paths can change.
- Tags can be missing, inconsistent, or edited.
- Hashing is expensive compared with reading state files.

### 4. Verification Identity

Purpose: identify the validation evidence proving archive quality.

Primary keys:

- Validation log path.
- Validation timestamp.
- Album manifest hash when available.
- Per-file SHA256 hashes.

Secondary keys:

- Validator version or validator profile.
- Integrity status.
- Completeness status.
- Deezer verification result.
- `ALBUM_ID` coverage status.
- ISRC coverage status.

Use cases:

- Explain why an archive entry is considered validated.
- Detect stale validation after files change.
- Support repair and revalidation.
- Rank confidence in lifecycle and archive reports.

Limitations:

- Current validator logs do not include a validator run ID.
- Current detailed logs can lack album ID and ordered ISRC evidence.
- Current lifecycle integration only imports a subset of evidence.

## Proposed Local Identity Objects

### StigmaDiscoveryRef

```text
stigma_discovery_ref
  provider = deezer
  provider_album_id
  provider_artist_id
  album_url
  artist_url
  source_file
  source_line
  discovered_at
```

Primary key recommendation: `(provider, provider_album_id)`.

### StigmaReleaseCandidate

```text
stigma_release_candidate
  release_uid
  provider_album_ids
  upc
  title
  normalized_title
  main_artist_ids
  main_artist_names
  release_date
  record_type
  label
  track_count
  ordered_isrcs
  ordered_track_titles
  duration
```

Primary key recommendation: local `release_uid`.

`release_uid` should be local because no single external field is safe enough. It can initially be deterministic from strongest available fields, then later become a stable generated ID if SQLite or explicit merge/split workflows are introduced.

### StigmaArchiveEntry

```text
stigma_archive_entry
  archive_uid
  archive_root
  relative_path
  folder_name
  observed_at
  album_manifest_hash
  file_count
  track_count
  tag_album
  tag_album_artist
  tag_album_id
  tag_isrcs
```

Primary key recommendation: local `archive_uid`, derived from archive root + relative path until manifest identity exists.

### StigmaVerificationEvidence

```text
stigma_verification_evidence
  evidence_uid
  archive_uid
  validation_log_path
  validated_at
  integrity_status
  completeness_status
  deezer_verification_status
  album_id_status
  track_hashes
  manifest_hash
  confidence
```

Primary key recommendation: validation log path + validated timestamp + manifest hash when available.

## Confidence Scoring

Recommended scoring should be explainable, not opaque.

### High Confidence

Any of:

- Consistent embedded `ALBUM_ID` on all tracks equals lifecycle Deezer album ID.
- UPC matches cached Deezer metadata and ordered ISRC list matches.
- Shipment job ID containing Deezer album ID leads to the exact archive folder and track metadata is compatible.
- Manifest hash matches prior verified manifest for the same archive entry.

Recommended action: auto-link is acceptable after implementation has tests and a review report.

### Medium Confidence

All of:

- Normalized artist matches.
- Normalized title matches.
- Track count matches.
- Year or release date is compatible.
- No competing candidate has equal or better evidence.

Recommended action: candidate link requiring review or explicit confirmation.

### Low Confidence

Any of:

- Title-only match.
- Artist-only plus similar title.
- Folder-year and track-count match but artist is ambiguous.
- Compilation with `Various Artists`.
- Multiple variants with similar titles.

Recommended action: report only, no lifecycle enrichment.

### No Confidence

Any of:

- Missing provider ID.
- Missing tag identifiers.
- Missing cached metadata.
- Multiple plausible candidates.
- Conflicting `ALBUM_ID`, UPC, or ISRC evidence.

Recommended action: leave unmatched and preserve evidence.

## Primary Key Recommendations

Current operational key:

- Keep Deezer album ID for lifecycle state files.

Future derived identity layer:

- Discovery: `(provider, provider_album_id)`.
- Release: local `release_uid`, with UPC and ordered ISRC list as high-value external keys.
- Archive entry: local `archive_uid`, initially archive root + relative path, later backed by manifest hash.
- Verification: validation evidence UID based on log path + timestamp + manifest/hash evidence.

Future SQLite index if approved:

- Use local integer or UUID primary keys internally.
- Store external IDs as unique or indexed attributes, not universal primary keys.
- Allow many Deezer album IDs to map to one release candidate.
- Allow one release candidate to map to multiple archive entries.
- Allow one archive entry to have multiple validation runs.

## Collision and Duplicate Handling

Expected relationships:

- One Deezer album ID to one discovery row.
- Many Deezer album IDs to one release candidate.
- One release candidate to zero, one, or many archive entries.
- One archive entry to zero, one, or many verification records.
- One ISRC to many releases.
- One UPC to one or more release candidates.

Duplicate detection should separate:

- Provider duplicates: multiple Deezer album IDs with same UPC/tracklist.
- Release duplicates: same UPC but different source rows.
- Recording duplicates: shared ISRCs across releases.
- Archive duplicates: identical manifest hash.
- File duplicates: identical SHA256.

## Migration Path

1. Keep lifecycle registry unchanged as a Deezer album ID projection.
2. Build an identity resolution report that reads lifecycle, validator logs, and archive folders.
3. Add candidate matches with confidence and explanation.
4. Add metadata cache for UPC, artist IDs, track IDs, ordered ISRCs, and tracklists.
5. Add archive manifest generation.
6. Only then consider SQLite as a rebuildable index over identity facts.

## Non-Goals

- Replacing filesystem truth.
- Making folder names authoritative identifiers.
- Making UPC the only release key.
- Making SQLite the next immediate step.
- Auto-merging ambiguous archive entries.

## Recommendation

Implement identity resolution before metadata browser, NFO generation, playback integration, or SQLite. The immediate deliverable should be a read-only identity resolver that emits candidate links and confidence reasons without mutating lifecycle state.
