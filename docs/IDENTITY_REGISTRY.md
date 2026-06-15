# Identity Registry

The identity registry is a derived projection that links lifecycle releases to archive and validator evidence.

It does not modify curator workflows.

It does not modify validator behavior.

It does not create a new source of truth.

## Inputs

Primary input:

- `data/lifecycle_registry.json`

The lifecycle registry already includes:

- Deezer album IDs.
- Lifecycle state evidence.
- `validated_albums.json` evidence.
- Unmatched `STIGMA_VALIDATED.txt` logs discovered during validator evidence integration.

## Outputs

Generated outputs:

- `data/identity_registry.json`
- `reports/identity_resolution_report.md`
- `reports/unresolved_identity_report.md`

These files are rebuildable from existing state and validator evidence.

## Confidence Model

`HIGH`

The release has durable lifecycle identity evidence. Current high-confidence evidence includes:

- A lifecycle Deezer album ID with validated-index evidence.
- Validator evidence matched by album ID.
- Matched detailed validation log evidence when available.

`MEDIUM`

The release or unresolved validation log has a review candidate based on normalized artist and title matching.

Medium confidence is not an automatic link. It is a manual review queue.

`LOW`

Reserved for future weak metadata similarity, such as partial or fuzzy title matches.

`UNKNOWN`

No reliable evidence exists yet.

## Registry Shape

Each release entry contains:

- `release_id`
- `discovery_identity`
- `archive_identity`
- `identity_confidence`
- `evidence`
- `sources`
- `validation`

Unresolved entries contain:

- validation log path
- folder
- parsed folder fields
- reason resolution failed
- confidence
- candidate matches when available
- validation evidence summary

## Rebuild Philosophy

The registry is disposable.

If it is deleted, it can be rebuilt from:

- lifecycle registry
- validator evidence
- validation logs
- existing state files used by lifecycle generation

The filesystem remains truth. The registry is only a read model for identity review and archive intelligence.

## Why This Is Not Source Of Truth

Identity resolution can be uncertain.

Folder names, title normalization, and metadata similarity are not strong enough to mutate archive state automatically. The registry preserves evidence and confidence instead of rewriting files or declaring ambiguous matches final.

Future metadata cache and archive manifest work can improve confidence without changing this principle.
