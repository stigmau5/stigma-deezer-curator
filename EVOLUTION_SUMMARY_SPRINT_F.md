# Evolution Summary: Sprint F

Date: 2026-06-15

Sprint: Archive Identity Resolution Audit

Scope: research and architecture only. No implementation, schema change, SQLite work, GUI work, lifecycle change, or validator workflow change was performed.

## Files Reviewed

Curator:

- `data/artists/*.txt`
- `data/lifecycle_registry.json`
- `data/validated_albums.json`
- `data/attempted_albums.json`
- `data/confirmed_albums.json`
- `data/shipped_jobs.json`
- `curator/lifecycle.py`
- `curator/validator_evidence.py`
- `curator/metadata.py`
- `curator/ship.py`
- `curator/links.py`
- `reports/validation_evidence_report.md`
- `reports/validation_confidence_report.md`
- `docs/VALIDATOR_EVIDENCE.md`
- `ARCHIVE_IDENTITY_AUDIT.md`
- `DEEZER_METADATA_SURVEY.md`
- `VALIDATOR_INTEGRATION_AUDIT.md`
- `ARCHIVE_INDEX_PROPOSAL.md`

Validator:

- `/home/stigma/apps/stigma_flac_validator/validator.py`
- `/home/stigma/apps/stigma_flac_validator/completeness.py`
- `/home/stigma/apps/stigma_flac_validator/deezer_verify.py`
- `/home/stigma/apps/stigma_flac_validator/logger.py`
- `/home/stigma/apps/stigma_flac_validator/config.py`
- `/home/stigma/apps/stigma_flac_validator/README.md`
- `/home/stigma/StreamripDownloads/**/STIGMA_VALIDATED.txt`

## Documents Created

- `ARCHIVE_IDENTITY_RESOLUTION_AUDIT.md`
- `IDENTITY_MODEL_PROPOSAL.md`
- `METADATA_ENRICHMENT_STRATEGY.md`
- `ARCHIVE_BROWSING_VISION.md`
- `FUTURE_ARCHIVE_STRENGTH_SIGNALS.md`
- `EVOLUTION_SUMMARY_SPRINT_F.md`

## Key Findings

Sprint E's 77 unmatched validation logs are an identity resolution problem, not a validation failure.

The lifecycle registry is provider-centric:

- Deezer album ID is the operational key.
- Discovery, attempts, shipment, validated index entries, and confirmations all align well around album ID.

The detailed validation logs are archive-centric:

- They live inside archive folders.
- They record local validation timestamp, track count, completeness details, and per-file SHA256 hashes.
- The sampled logs have `completeness.album_id: null`.
- The sampled logs report every track missing `ALBUM_ID`.

That means the detailed validator evidence can prove local integrity, but cannot currently prove which Deezer lifecycle row it belongs to.

Exploratory matching found:

- 0 high-confidence detailed-log matches using present durable identifiers.
- 16 medium-confidence normalized artist/title candidates, all for `Ronny & Ragge`.
- 61 logs with no exact normalized artist/title match in the current lifecycle registry.

Those 16 candidates should not be auto-linked yet. Without `ALBUM_ID`, UPC, ordered ISRC list, manifest identity, or shipment-to-folder evidence, folder-name matching remains too risky.

## Risks

Highest risks:

- False positive archive links from folder names.
- Treating Deezer album ID as a real-world release identity.
- Losing rich validator evidence because it cannot be linked yet.
- Building browser or SQLite surfaces before identity ambiguity is modeled.
- Letting metadata cache become accidental truth.

Medium risks:

- UPC reuse or missing UPC values.
- ISRC overlap across compilations, reissues, and remasters.
- Artist/title normalization issues with accents, punctuation, doubled spaces, and hyphens.
- Compilations and `Various Artists` releases needing special handling.

## Identity Recommendations

Adopt layered identity:

- Discovery Identity: Deezer album ID and Deezer artist ID.
- Release Identity: UPC, ordered ISRC list, title, artist IDs, release date, track count, contributors.
- Archive Identity: archive root, archive-relative path, manifest hash, file hashes, embedded tags.
- Verification Identity: validator log, validation timestamp, integrity status, completeness status, hashes.

Use confidence tiers:

- High: album ID, UPC plus ISRC list, manifest, or shipment path with compatible evidence.
- Medium: exact normalized artist/title/year/track count with no competing candidates.
- Low: fuzzy or partial metadata match.
- None: missing or conflicting evidence.

Keep Deezer album ID as the current lifecycle key. Do not replace it in existing workflows.

## Metadata Recommendations

Cache the fields that make identity resolution possible:

- Album UPC.
- Album release date.
- Deezer artist IDs.
- Contributor IDs and roles.
- Ordered track IDs.
- Ordered track titles.
- Ordered ISRC list.
- Disc and track positions.
- Durations.
- Explicit flags.

Use a file-based cache first. SQLite should wait until identity and metadata shapes are proven.

## Archive Browsing Recommendations

A future browser should support:

- Library View.
- Artist View.
- Album View.
- Track View.
- Archive Health View.
- Coverage View.

It must show uncertainty instead of forcing every archive folder into a lifecycle row. Unmatched archive folders should be first-class objects with evidence and candidate links.

## Preservation Recommendations

Preserve:

- Validation logs.
- File hashes.
- Archive-relative paths.
- Folder names.
- Embedded tags.
- Missing tag counts.
- Validation timestamps.
- Shipment job names.
- Original provider IDs.

Avoid:

- Overwriting identity decisions without review.
- Deriving permanent identity only from folder names.
- Discarding unmatched validation evidence.

## Recommended Next Implementation Sprint

Recommendation: A) Identity Resolution Layer.

Justification:

- The current blocker is not lack of SQLite or browsing UI. It is inability to confidently link archive-local evidence to provider lifecycle rows.
- Metadata cache is important, but the first implementation should define the read-only resolver shape and candidate report. That will reveal exactly which metadata fields are required to upgrade candidates from medium/low confidence to high confidence.
- Archive Browser Prototype would sit on ambiguous identity and risk presenting uncertain links as facts.
- SQLite Archive Index would harden unresolved modeling questions too early.

## Proposed Sprint G: Identity Resolution Layer

Goal:

- Build a read-only identity resolver that consumes lifecycle registry, validation logs, validated index, and archive folder evidence.

Outputs:

- `reports/identity_resolution_report.md`
- Optional derived JSON candidate report under `reports/` or `data/derived/`, if approved.

Rules:

- No workflow changes.
- No validator changes.
- No SQLite.
- No automatic lifecycle mutation.
- No auto-confirming folder-name-only matches.

Core behavior:

- Classify detailed validation logs as high, medium, low, or no-confidence candidates.
- Explain every match reason.
- Preserve unmatched logs as evidence.
- Report missing identifiers needed to improve confidence.

Success criteria:

- STiGMA can see which archive folders are definitely linked, likely linked, ambiguous, or impossible to link with current evidence.
- The next metadata cache sprint has a precise field list grounded in real candidate failures.
