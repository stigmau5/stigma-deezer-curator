# Release Lifecycle Proposal

Audit date: 2026-06-15

Scope: design-only lifecycle proposal for future STiGMA Audio Division. No implementation or schema change is included.

## Current State Signals

Current states are implicit and distributed across files:

- `DISCOVERED`: raw Deezer URLs in `data/inbox.txt`.
- `EXPANDED`: artist release blocks in `data/artists/*.txt`.
- `QUEUED`: URLs copied into GUI queue.
- `ATTEMPTED`: album IDs in `data/attempted_albums.json`.
- `SHIPPED`: album IDs in `data/shipped_jobs.json` or local queue snapshots under `data/shipped/`.
- `VALIDATED`: album IDs in `data/validated_albums.json`.
- `CONFIRMED`: album IDs in `data/confirmed_albums.json`.

Current issues:

- States are not a single lifecycle model.
- Attempted means "queued by GUI", not "download completed".
- Shipped means "job placed in remote pending", not "downloaded".
- Validated means "validator accepted archive folder", but details are not imported.
- Confirmed is manual review intent and can happen before or after validation.

## Proposed Future Lifecycle

Recommended lifecycle states:

1. `DISCOVERED`
2. `EXPANDED`
3. `CANDIDATE`
4. `QUEUED`
5. `ATTEMPTED`
6. `SHIPPED`
7. `DOWNLOADED`
8. `VALIDATION_PENDING`
9. `VALIDATED`
10. `ARCHIVED`
11. `NFO_PENDING`
12. `NFO_GENERATED`
13. `CONFIRMED`
14. `REJECTED`
15. `PROBLEMATIC`
16. `SUPERSEDED`

Not every release must pass through every state. The model should support partial knowledge and re-entry.

## State Definitions

### DISCOVERED

Purpose: a Deezer URL or ID is known.

Source of truth:

- `data/inbox.txt`
- future discovery event log

Transition trigger:

- User pastes album/artist link.
- Future importer adds link.

Recovery behavior:

- Safe to reprocess if not logged as successful.
- Failed discovery should remain retryable.

Ownership:

- Curator.

### EXPANDED

Purpose: artist-level discovery has produced release candidates.

Source of truth:

- `data/artists/*.txt`
- future release metadata cache

Transition trigger:

- Artist expansion succeeds.

Recovery behavior:

- Expansion can be rerun if source block is missing or marked failed.
- Existing blocks should remain append-only until a structured cache exists.

Ownership:

- Curator.

### CANDIDATE

Purpose: a release is eligible for queueing after dedupe/ownership checks.

Source of truth:

- Future index view combining artist files, validated index, shipped ledger, and metadata.

Transition trigger:

- Release appears in artist file and is not already archived or rejected.

Recovery behavior:

- Recomputed from source files and index.

Ownership:

- Curator/archive index.

### QUEUED

Purpose: user or rule selected release for download.

Source of truth:

- GUI queue in memory today.
- Future durable queue file or queue table.

Transition trigger:

- User sends selected release lines to queue.
- Batch rule selects section entries.

Recovery behavior:

- Queue should be recoverable from a durable queue snapshot in the future.

Ownership:

- Curator.

### ATTEMPTED

Purpose: release was intentionally sent toward download at least once.

Source of truth:

- `data/attempted_albums.json`

Transition trigger:

- GUI fires release into queue today.
- Future downloader job creation.

Recovery behavior:

- Attempts should not block future processing alone.
- Attempt count and timestamps help retry review.

Ownership:

- Curator.

### SHIPPED

Purpose: a download job was handed to the local streamrip queue or remote worker pending directory.

Source of truth:

- `data/shipped_jobs.json`
- `data/shipped/*.txt`
- remote pending/job logs in future

Transition trigger:

- Local streamrip handoff.
- Server `.job` promoted into pending.

Recovery behavior:

- Reconcile with remote worker output and validator results.
- If shipped but never downloaded/validated, mark stale for retry.

Ownership:

- Curator/job shipper.

### DOWNLOADED

Purpose: files exist in incoming/download folder.

Source of truth:

- Filesystem.
- Future downloader/worker completion event.

Transition trigger:

- Streamrip completes.
- Remote worker moves job output to incoming.

Recovery behavior:

- Rebuild by scanning incoming folders.
- If unknown identity, route to stamping/problematic.

Ownership:

- Downloader/worker plus validator scanner.

### VALIDATION_PENDING

Purpose: downloaded folder awaits validator pass.

Source of truth:

- Filesystem location.
- Future index scan.

Transition trigger:

- Downloaded folder discovered.
- Folder moved to incoming validation area.

Recovery behavior:

- Re-run validator.
- No state should be lost if process crashes.

Ownership:

- Validator.

### VALIDATED

Purpose: validator has accepted integrity and completeness.

Source of truth:

- `STIGMA_VALIDATED.txt`
- `validated_albums.json`
- future archive index imported from validator evidence

Transition trigger:

- Validator writes per-album validation log and global index.

Recovery behavior:

- Rebuild index from validation logs and archive folders.
- Revalidate if file hashes or manifest hash change.

Ownership:

- Validator.

### ARCHIVED

Purpose: validated release is in the long-term archive location.

Source of truth:

- Filesystem archive path.
- Validator routing output.
- Future index scan.

Transition trigger:

- Validator moves to complete/archive directory.
- Manual archive organization confirmed by scan.

Recovery behavior:

- Rebuild from filesystem.
- If validation log missing, mark validation unknown.

Ownership:

- Filesystem/validator/archive index.

### NFO_PENDING

Purpose: release is archived but lacks generated NFO.

Source of truth:

- Filesystem scan and future NFO records.

Transition trigger:

- Archived release has no NFO or stale NFO.

Recovery behavior:

- Regenerate from metadata cache and validation evidence.

Ownership:

- Future NFO generator.

### NFO_GENERATED

Purpose: NFO exists and matches current release metadata/validation evidence.

Source of truth:

- NFO file in archive folder.
- Future NFO manifest or generated_at record.

Transition trigger:

- NFO generator succeeds.

Recovery behavior:

- Regenerate if metadata changes or file missing.

Ownership:

- Future NFO generator.

### CONFIRMED

Purpose: human has reviewed and accepted a release/identity.

Source of truth:

- `data/confirmed_albums.json`
- future manual review events

Transition trigger:

- User confirms selected item in GUI.

Recovery behavior:

- Should remain separate from validation.
- Can be rebuilt only from confirmation state/events.

Ownership:

- Human-in-the-loop curator.

### REJECTED

Purpose: release should not be downloaded/archived.

Source of truth:

- Future rejection ledger.

Transition trigger:

- User marks unwanted duplicate, wrong edition, bad metadata, or out-of-scope release.

Recovery behavior:

- Rejection should be reversible with reason tracking.

Ownership:

- Human-in-the-loop curator.

### PROBLEMATIC

Purpose: release/folder requires human review due to corruption, mismatch, identity ambiguity, or routing failure.

Source of truth:

- Validator problematic folder.
- Future problem ledger.

Transition trigger:

- Validator failure.
- Deezer mismatch.
- Conflicting ALBUM_ID.
- Ship/download failure.

Recovery behavior:

- Human review, repair, restamp, redownload, or reject.

Ownership:

- Validator plus human review.

### SUPERSEDED

Purpose: a release is still known but replaced by a preferred version.

Source of truth:

- Future release relationship table/ledger.

Transition trigger:

- User chooses deluxe/remaster/original preference.
- Duplicate analysis clusters releases.

Recovery behavior:

- Never delete automatically.
- Use for reporting and queue suppression.

Ownership:

- Archive index plus human review.

## Recommended Lifecycle Ownership

| Lifecycle area | Owner |
| --- | --- |
| Discovery and expansion | Curator |
| Queue/attempt/ship | Curator/job shipper |
| Downloaded folder presence | Filesystem/worker |
| Integrity/completeness validation | Validator |
| Archive path truth | Filesystem |
| Searchable lifecycle view | Rebuildable archive index |
| Manual decisions | Human review ledgers |
| NFO status | Future NFO generator |

## Recovery Principles

- Filesystem remains source of truth.
- Database/index must be rebuildable.
- Event logs should explain transitions.
- Failed transitions must remain retryable.
- Attempted/shipped must not be treated as downloaded or validated.
- Validation evidence should be immutable or append-only.
- Manual confirmation should not be overwritten by automated scans.

## Recommended Next Lifecycle Implementation Sprint

Do not build the full lifecycle engine at once.

Start with a read-only lifecycle projection:

- Load curated artist files.
- Load attempted, shipped, confirmed, and validated JSON files.
- Scan validator logs when available.
- Produce a report per album ID showing highest known state and evidence.

This will reveal data gaps before any schema or SQLite work.
