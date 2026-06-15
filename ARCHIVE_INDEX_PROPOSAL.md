# Archive Index Proposal

Audit date: 2026-06-15

Scope: future archive index design. This document does not implement SQLite or any schema changes.

## Core Principle

Filesystem remains the source of truth.

The database is a rebuildable index. If the database is deleted, STiGMA Audio Division should be able to reconstruct it from:

- Archive folders.
- `STIGMA_VALIDATED.txt` logs.
- `validated_albums.json`.
- Curator artist files.
- Attempted/confirmed/shipped state files.
- Future metadata cache files.
- NFO files.

## Current Source Files

Current curator sources:

- `data/artists/*.txt`: discovered/expanded releases.
- `data/curated.log`: processed inbox lines.
- `data/attempted_albums.json`: queue attempts.
- `data/shipped_jobs.json`: server shipment ledger.
- `data/shipped/*.txt`: local streamrip handoff snapshots.
- `data/confirmed_albums.json`: manual confirmations.
- `data/validated_albums.json`: validator summary index.

Current validator sources:

- `STIGMA_VALIDATED.txt` inside album folders.
- Validator config `validated_index`.
- Archive/incoming/needs_stamp/problematic/complete folders.

## What Should Be Indexed?

### Artists

Fields:

- Local artist key.
- Display name.
- Deezer artist ID.
- Source URLs.
- Picture URL/hash.
- Fan/album counts as observed metadata.
- Related artist IDs in future.

Purpose:

- Browse collection by artist.
- Avoid filename-normalization ambiguity.
- Track discovery completeness.

### Releases / Albums

Fields:

- Local release ID.
- Deezer album IDs.
- UPC.
- Title.
- Main artist IDs.
- Contributor IDs.
- Release date.
- Record type.
- Track count.
- Duration.
- Label.
- Genres.
- Explicit flags.
- Cover URLs and `md5_image`.
- Source URL.

Purpose:

- Answer ownership/dedupe questions.
- Power queue suppression.
- Generate NFOs.
- Compare provider metadata with archive evidence.

### Tracks

Fields:

- Local track ID.
- Deezer track ID.
- Parent release ID.
- ISRC.
- Title.
- Track position.
- Disc number.
- Duration.
- Artist/contributor IDs.
- Explicit flags.

Purpose:

- Track-level verification.
- Ordered manifest building.
- ISRC duplicate detection.
- NFO tracklists.

### Archive Files

Fields:

- Archive entry ID.
- Release ID when known.
- Relative path.
- Filename.
- Extension.
- Size.
- Mtime.
- SHA-256.
- Audio tags snapshot.
- Track position/disc number from tags.
- ISRC from tags.
- ALBUM_ID from tags.

Purpose:

- Filesystem truth projection.
- Bitrot/repair checks.
- Exact duplicate detection.

### Archive Entries / Folders

Fields:

- Archive entry ID.
- Root path.
- Relative folder path.
- Folder name.
- Manifest hash.
- Validation log path.
- Current location class: incoming, needs_stamp, problematic, complete/archive.

Purpose:

- Album-level archive state.
- Folder movement/reconciliation.
- Exact album duplicate detection.

### Validations

Fields:

- Validation ID.
- Archive entry ID.
- Validator version.
- Validated timestamp.
- Integrity result.
- Completeness result.
- Deezer verification result.
- Warning/error lists.
- Manifest hash at validation time.
- Per-file hashes.

Purpose:

- Evidence history.
- Repair and audit.
- Detect stale validation after file changes.

### Shipments

Fields:

- Shipment/job ID.
- Deezer album ID.
- URL.
- Job name.
- Remote job path.
- Shipped timestamp.
- Status if future worker completion exists.

Purpose:

- Reconcile shipped jobs with downloads and validations.
- Detect stale or lost jobs.
- Retry safely.

### Attempts

Fields:

- Album ID.
- Attempt count.
- Last attempt timestamp.
- Last queued URL.

Purpose:

- Human review.
- Retry strategy.
- Avoid accidental repeated queueing while not blocking real retries.

### Confirmations

Fields:

- Album ID.
- Confirmed timestamp.
- Artist file/source.
- Optional future reviewer/reason.

Purpose:

- Manual review state.
- Human override and confidence.

### NFOs

Fields:

- Archive entry ID.
- NFO path.
- Generated timestamp.
- Generator version.
- Metadata source hash/version.
- Validation ID used.

Purpose:

- Identify missing/stale NFOs.
- Regenerate safely.
- Report release documentation coverage.

## Questions The Index Should Answer

Ownership:

- Do I already own this Deezer album ID?
- Do I own this UPC under another Deezer album ID?
- Do I own a release with the same ordered ISRC list?
- Do I own a release with the same normalized artist/title/year?

Completeness:

- Which artists have discovered albums not validated?
- Which queued/shipped albums never validated?
- Which archive folders lack ALBUM_ID?
- Which releases are missing tracks?

Operations:

- What validated this week?
- What shipped but did not download?
- What downloaded but is not validated?
- What is in problematic/needs_stamp?
- What needs retry?

NFO and archive documentation:

- What lacks NFO generation?
- Which NFOs are stale relative to validation or metadata?
- Which releases lack cover art?

Duplicates:

- What folders have identical manifest hashes?
- What releases share UPCs?
- What releases share high ISRC overlap?
- What files share SHA-256?
- What artist/title/year candidates need human review?

Collection intelligence:

- Which artists are incomplete?
- Which genres/labels dominate the archive?
- Which releases are singles/EPs/albums?
- Which years are underrepresented?
- Which artists are related to existing collection but missing?

## Minimal Future Schema

This is intentionally minimal and conceptual. Do not implement yet.

```text
artists
  id
  deezer_artist_id
  name
  metadata_json

releases
  id
  primary_deezer_album_id
  upc
  title
  release_date
  record_type
  track_count
  duration
  label
  metadata_json

release_artists
  release_id
  artist_id
  role
  position

tracks
  id
  release_id
  deezer_track_id
  isrc
  title
  disc_number
  track_position
  duration
  metadata_json

archive_entries
  id
  release_id nullable
  root
  relative_path
  folder_name
  manifest_hash
  location_class

archive_files
  id
  archive_entry_id
  track_id nullable
  relative_path
  size
  mtime
  sha256
  tags_json

validations
  id
  archive_entry_id
  validated_at
  validator_version
  ok
  manifest_hash
  details_json

shipments
  id
  deezer_album_id
  url
  jobname
  remote_job
  shipped_at
  status

lifecycle_events
  id
  subject_type
  subject_id
  state
  source
  occurred_at
  details_json

nfos
  id
  archive_entry_id
  path
  generated_at
  generator_version
  source_hash
```

## Rebuild Strategy

Phase 1: file scan

- Scan archive roots.
- Identify album folders.
- Read audio files and tags.
- Read `STIGMA_VALIDATED.txt`.
- Compute or import hashes/manifest hashes.

Phase 2: curator state import

- Import artist files as discovery candidates.
- Import attempts, confirmations, shipments, and curated log.
- Import validated index.

Phase 3: metadata enrichment

- Use Deezer album IDs to fetch/cache album details.
- Fetch tracks/ISRCs where needed.
- Store raw provider payloads as cache JSON.

Phase 4: lifecycle projection

- Compute highest known lifecycle state from evidence.
- Emit conflicts for human review.

Phase 5: reports

- Generate ownership, missing, duplicate, NFO, and validation reports.

## Synchronization Strategy

Recommended approach:

- Treat index updates as rebuildable imports.
- Prefer periodic full rebuild while schema is young.
- Later add incremental scans based on mtimes and manifest hashes.
- Never let the database be the only location of a decision.
- Keep manual decisions in explicit files/events that can be imported.

Conflict handling:

- Filesystem wins for archive existence.
- Validator logs win for validation evidence.
- Curator state wins for attempts/shipments/confirmations.
- Deezer metadata cache is advisory and refreshable.
- Human review wins for reject/supersede/preferred edition.

## Source-of-Truth Files

| Truth area | Source |
| --- | --- |
| Archive existence | Filesystem |
| File integrity | Validator logs / hashes |
| Validation status | `STIGMA_VALIDATED.txt`, `validated_albums.json` |
| Discovery | `data/inbox.txt`, `data/artists/*.txt` |
| Attempts | `data/attempted_albums.json` |
| Shipments | `data/shipped_jobs.json`, shipped snapshots |
| Confirmations | `data/confirmed_albums.json` |
| Provider metadata | Deezer cache / API, rebuildable |
| NFO existence | Filesystem |

## First Implementation Recommendation

Do not start with full SQLite.

Sprint B should build a read-only index prototype that emits a JSON or Markdown report:

- Load existing state files.
- Scan validation index.
- Parse artist files.
- Join by Deezer album ID.
- Show lifecycle state per album.

After that report exposes gaps, introduce SQLite with the minimal schema.

## Risks

- Existing artist files are text and may contain stale metadata.
- Existing validated index is thin.
- Some archive folders may lack validation logs.
- Album IDs alone will miss duplicate releases with different Deezer IDs.
- Full metadata enrichment can become network-heavy without caching.
- If SQLite is introduced too early, it may become accidental source of truth.
