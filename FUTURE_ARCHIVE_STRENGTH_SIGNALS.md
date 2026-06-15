# Future Archive Strength Signals

Date: 2026-06-15

Scope: Sprint F research-only quality metric proposal. No metrics are implemented here.

## Purpose

Archive strength signals should answer one question:

How trustworthy, complete, browsable, and repairable is the local music archive?

Signals should be derived from filesystem evidence, lifecycle state, validator output, metadata cache, and future NFO/artwork projections. They should not become source of truth.

## Already Measurable

### Validation Coverage

Definition:

- Albums with validation evidence divided by known lifecycle albums.

Current sources:

- `data/lifecycle_registry.json`
- `data/validated_albums.json`
- `STIGMA_VALIDATED.txt`

Value: High.

Reason: directly answers how much of the known collection has validation evidence.

### Lifecycle State Distribution

Definition:

- Count and percentage of albums by highest lifecycle state.

Current sources:

- Lifecycle registry.

Value: High.

Reason: exposes stuck albums and backlog.

### Backlog Size

Definition:

- Discovered but never attempted.

Current sources:

- Artist files.
- Attempted state.

Value: High.

Reason: immediately actionable for curation.

### Shipment Gap

Definition:

- Shipped but not validated.

Current sources:

- `shipped_jobs.json`
- `validated_albums.json`

Value: High.

Reason: identifies likely workflow failures or unprocessed downloads.

### Validation Evidence Confidence

Definition:

- Detailed log vs validated index vs no evidence.

Current sources:

- Sprint E validator evidence integration.

Value: High.

Reason: distinguishes broad validation state from rich evidence.

### Missing ALBUM_ID Coverage in Validator Logs

Definition:

- Tracks missing `ALBUM_ID` tags in validation logs.

Current sources:

- `STIGMA_VALIDATED.txt`

Value: High.

Reason: this is the current blocker for confident validator-to-lifecycle linking.

## Measurable After Identity Resolution

### Archive Confidence

Definition:

- Confidence that an archive folder corresponds to a lifecycle/release entity.

Signals:

- `ALBUM_ID` match.
- UPC match.
- Ordered ISRC match.
- Manifest match.
- Artist/title/year/track count match.
- Conflicts or ambiguity.

Value: High.

### Orphan Archive Entries

Definition:

- Archive folders with validation evidence but no lifecycle or release identity.

Value: High.

### Duplicate Archive Entries

Definition:

- Multiple archive folders representing the same release candidate.

Value: High.

### Exact File Duplicate Coverage

Definition:

- Duplicate SHA256 files across archive entries.

Value: Medium.

### Manifest Duplicate Coverage

Definition:

- Duplicate album manifest hashes across archive folders.

Value: High.

### Stale Validation

Definition:

- Archive manifest differs from the manifest captured at validation time.

Value: High.

### Repairability Score

Definition:

- Whether an archive entry has enough metadata and hashes to repair or verify it later.

Signals:

- Manifest hash.
- Per-track hashes.
- Ordered track list.
- ISRC coverage.
- Album ID/UPC.

Value: Medium to High.

## Measurable After Metadata Enrichment

### Metadata Coverage

Definition:

- Percentage of albums with cached album, artist, and track metadata.

Value: High.

### UPC Coverage

Definition:

- Percentage of release candidates with UPC.

Value: High.

### ISRC Coverage

Definition:

- Percentage of tracks with ISRC.

Value: High.

### Artwork Coverage

Definition:

- Percentage of albums with cover art URL or local artwork.

Value: Medium.

### NFO Readiness

Definition:

- Albums with enough metadata and validation evidence to generate NFO safely.

Value: High.

### Artist Completeness

Definition:

- Owned/validated release candidates compared with discovered or provider-known releases.

Value: High.

### Duplicate Release Risk

Definition:

- Multiple provider album IDs sharing UPC, ordered ISRC list, or near-identical metadata.

Value: High.

### Variant Clarity

Definition:

- Ability to distinguish explicit/clean, remaster, deluxe, anniversary, live, soundtrack, and compilation variants.

Value: Medium.

## High Value Signals

- Validation Coverage.
- Validation Evidence Confidence.
- Missing `ALBUM_ID` Coverage.
- Archive Confidence.
- Orphan Archive Entries.
- Manifest Duplicate Coverage.
- Stale Validation.
- Metadata Coverage.
- UPC Coverage.
- ISRC Coverage.
- NFO Readiness.
- Artist Completeness.
- Duplicate Release Risk.

## Medium Value Signals

- Exact File Duplicate Coverage.
- Repairability Score.
- Artwork Coverage.
- Variant Clarity.
- Label Coverage.
- Genre Coverage.
- Validation Age.
- Shipment Latency.

## Low Value Signals

- Popularity coverage.
- Fan-count prioritization.
- Preview URL coverage.
- BPM/gain coverage.
- Related artist graph strength.
- Country availability coverage.

These can become useful later, but they should not shape near-term architecture.

## Recommended Strength Score Families

Avoid one global score at first. Use separate families:

- Integrity Confidence: FLAC test, hashes, manifest, stale validation.
- Identity Confidence: album ID, UPC, ISRC, metadata match.
- Metadata Confidence: album/artist/track cache completeness.
- Lifecycle Health: state progression and gaps.
- Archive Completeness: validation, NFO, artwork, metadata, confirmations.
- Repair Readiness: hashes, manifests, tracklists, ISRCs, tags.

## Recommendation

Start with identity and validation strength signals. They are closest to the current risk: archive evidence exists but cannot always be linked. Metadata, NFO, artwork, and browsing strength should build on that foundation.
