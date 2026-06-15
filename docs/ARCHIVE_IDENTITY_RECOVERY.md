# Archive Identity Recovery

Archive identity recovery is a derived analysis layer.

It does not modify archive files.

It does not modify tags.

It does not modify validator outputs.

It does not rewrite metadata.

## Purpose

The recovery layer answers:

- What unresolved validator evidence can be linked today?
- What confidence does each candidate have?
- What evidence supports the candidate?
- What remains unrecoverable with current data?
- Which preservation work would improve archive identity quality most?

## Inputs

- `data/lifecycle_registry.json`
- `data/identity_registry.json`
- Validator evidence already captured by the identity registry
- Archive folder names
- Artist names
- Album titles
- Track counts when available

## Recovery Levels

`RECOVERABLE_HIGH`

Exact artist, exact title, matching year, and matching track count.

`RECOVERABLE_MEDIUM`

Exact artist and exact title.

This is a review candidate, not an automatic repair.

`RECOVERABLE_LOW`

Exact artist and partial title similarity.

This is weak evidence and should only be used to guide manual review.

`UNRECOVERABLE`

Insufficient evidence exists today.

## Reports

Generated reports:

- `reports/archive_identity_recovery_report.md`
- `reports/recoverable_identity_report.md`
- `reports/unrecoverable_identity_report.md`
- `reports/archive_strength_report.md`

## Archive Strength Score

The archive strength score is informational only.

Current categories:

- Lifecycle Coverage
- Identity Coverage
- Validation Coverage
- Documentation Coverage
- Metadata Coverage

Documentation and metadata coverage are future categories and currently score zero by design.

## Rebuild Philosophy

Recovery reports are disposable.

They can be rebuilt from lifecycle and identity registries, which are themselves derived from filesystem state and validator evidence.

Filesystem remains source of truth.
