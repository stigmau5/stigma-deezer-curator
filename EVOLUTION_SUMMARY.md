# Evolution Sprint A Summary

Audit date: 2026-06-15

Scope: research and architecture design for STiGMA Audio Division after M1 safety stabilization. No implementation was performed.

## Documents Produced

- `ARCHIVE_IDENTITY_AUDIT.md`
- `DEEZER_METADATA_SURVEY.md`
- `VALIDATOR_INTEGRATION_AUDIT.md`
- `RELEASE_LIFECYCLE_PROPOSAL.md`
- `ARCHIVE_INDEX_PROPOSAL.md`
- `EVOLUTION_SUMMARY.md`

## Key Findings

### Identity

Deezer album ID is a good operational identity but not a complete release identity. Future architecture should separate:

- Discovery Identity: Deezer URLs, artist IDs, album IDs, track IDs.
- Release Identity: UPC, title, release date, contributors, ordered ISRCs.
- Archive Identity: folder path, file hashes, manifest hash, embedded tags.
- Verification Identity: validator run evidence, ALBUM_ID status, hashes, validation timestamp.

UPC and ISRC are currently ignored by the curator but are high-value future identifiers. UPC is useful for release-level duplicate detection. ISRC is useful for track-level recording identity and archive repair.

### Deezer Metadata

Deezer already provides more useful metadata than STiGMA currently stores:

- Album UPC, label, full release date, duration, genres, popularity/fans, cover art, contributors, explicit flags.
- Artist IDs, fan counts, pictures, related artists, top tracks.
- Track IDs, ISRCs, duration, disc/track positions, contributors, explicit flags, preview URLs, rank, availability.

The highest-value missing fields are UPC, ISRC, contributor IDs/roles, track positions, disc numbers, duration, label, and cover art identity.

### Validator

The FLAC validator is already the strongest truth component:

- Runs `flac -t`.
- Computes SHA-256 per FLAC file.
- Checks track/disc completeness.
- Reads album/artist/track tags.
- Reads `ALBUM_ID`.
- Reads ISRCs.
- Optionally verifies Deezer completeness by ISRC lookup and track count.
- Writes `STIGMA_VALIDATED.txt`.
- Updates `validated_albums.json`.

Current curator consumes only the album IDs from `validated_albums.json`, leaving most validation evidence unused.

### Lifecycle

Current lifecycle is implicit and spread across files. Attempted, shipped, validated, and confirmed are different concepts and should remain separate.

Recommended lifecycle:

- `DISCOVERED`
- `EXPANDED`
- `CANDIDATE`
- `QUEUED`
- `ATTEMPTED`
- `SHIPPED`
- `DOWNLOADED`
- `VALIDATION_PENDING`
- `VALIDATED`
- `ARCHIVED`
- `NFO_PENDING`
- `NFO_GENERATED`
- `CONFIRMED`
- `REJECTED`
- `PROBLEMATIC`
- `SUPERSEDED`

### Archive Index

SQLite is a good future fit, but the filesystem must remain source of truth. The database should be rebuildable from:

- Archive folders.
- Validator logs.
- Curator state files.
- Deezer metadata cache.
- NFO files.

Do not implement SQLite before building a read-only lifecycle/index projection from current files.

## Recommended Architecture Direction

Direction:

```text
Curator discovers and ships intent.
Validator proves archive truth.
Filesystem remains canonical.
Archive index projects truth into searchable form.
NFO generator consumes index + validation evidence.
```

Separation of responsibilities:

- Curator: discovery, selection, queueing, handoff, human confirmation.
- Validator: integrity, completeness, ALBUM_ID/ISRC evidence, archive validation.
- Archive index: rebuildable query layer and lifecycle projection.
- NFO generator: deterministic documentation output.
- Human review: reject, confirm, supersede, preferred edition decisions.

## Biggest Opportunities

| Opportunity | Impact | Effort | Notes |
| --- | --- | --- | --- |
| Read-only lifecycle projection | High | Low-medium | Reveals state gaps without schema risk |
| Import validator evidence | High | Medium | Unlocks archive truth and repair reports |
| Capture UPC/ISRC metadata | High | Medium | Major duplicate-detection upgrade |
| Album manifest hashes | High | Medium | Exact archive identity and repair foundation |
| Minimal SQLite index | High | Medium-high | Search/reporting once inputs are understood |
| NFO generation | Medium-high | Medium | Valuable after metadata/validation contracts exist |
| Artist identity by Deezer ID | Medium | Low-medium | Reduces filename/name ambiguity |
| Related artist intelligence | Medium | Medium | Useful later for discovery |
| Popularity/fans-based prioritization | Low-medium | Low | Helpful but not core archive safety |

## Biggest Risks

- Treating Deezer album ID as universal release identity.
- Introducing SQLite before rebuild rules and source ownership are clear.
- Letting database state become more trusted than filesystem/validator evidence.
- Ignoring validator hashes and relying only on `validated_albums.json`.
- Network-heavy metadata enrichment without cache and retry design.
- Duplicate detection based only on normalized titles.
- NFO generation before release identity and validation evidence are stable.

## Recommended Next Implementation Sprint

Sprint B should not implement the full platform. It should build a read-only lifecycle projection/report.

Recommended Sprint B:

- Read current state files.
- Parse artist release files.
- Import `validated_albums.json`.
- Optionally read `STIGMA_VALIDATED.txt` logs from configured archive roots if paths are known.
- Produce a local report:
  - album ID
  - title/artist when known
  - discovered/attempted/shipped/validated/confirmed flags
  - gaps such as shipped-not-validated, attempted-not-shipped, validated-not-known-to-curator

Why:

- Provides immediate value.
- Keeps filesystem/source files authoritative.
- Reveals data quality gaps before schema design.
- Prepares cleanly for SQLite.

## Roadmap

### Sprint B: Read-Only Lifecycle Projection

Goal: one command/report that projects current lifecycle from existing files.

Deliverables:

- State-file readers.
- Artist file parser reuse or extraction.
- Lifecycle projection report.
- Gap reports:
  - shipped not validated
  - attempted not shipped
  - validated but not discovered
  - confirmed but not validated
- No SQLite yet.

### Sprint C: Validator Evidence Contract

Goal: formalize validator output for archive indexing.

Deliverables:

- Versioned validator output schema proposal.
- Manifest hash design.
- Per-track file evidence shape.
- Migration compatibility with current `validated_albums.json`.
- Optional implementation in validator only after schema review.

### Sprint D: Rebuildable Archive Index Prototype

Goal: introduce SQLite as a rebuildable query cache.

Deliverables:

- Minimal SQLite schema.
- Full rebuild command.
- Import of curator state and validator evidence.
- Ownership and duplicate reports.
- No write-back from SQLite to source-of-truth files.

## Final Recommendation

Proceed in this order:

1. Read-only lifecycle projection.
2. Validator evidence schema and manifest hashes.
3. Metadata capture for UPC/ISRC/contributors.
4. Rebuildable SQLite index.
5. NFO generation.

This keeps the project local-first, protects archive truth, and avoids building intelligence on top of unstable identity assumptions.
