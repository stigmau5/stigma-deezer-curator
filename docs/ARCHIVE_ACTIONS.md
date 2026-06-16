# Archive Actions

Archive Actions are read-only improvement opportunities for STiGMA Audio Division.

They do not modify archive files.

They do not execute validator jobs.

They do not generate NFO or SFV files.

They do not refresh metadata automatically.

## Purpose

Archive Actions answer:

What should I do next to improve the archive?

The first action framework uses existing derived state:

- lifecycle registry
- identity registry
- metadata cache

## Categories

- `missing_nfo`
- `missing_sfv`
- `missing_validation`
- `missing_metadata`
- `missing_artwork`
- `identity_review`

Future categories can be added by extending `audio_division/actions.py`.

## Priorities

`high`

Likely archive quality blockers, such as shipped albums without validation or identity evidence needing review.

`medium`

Important enrichment work, such as missing metadata or NFO tracking.

`low`

Useful follow-up work, such as SFV/artwork tracking.

## Report

Generated report:

- `reports/archive_actions_report.md`

The report includes grouped counts and action details.

## Dashboard

The Audio Division dashboard displays:

- total action count
- action counts grouped by category
- details for the first recommended action

The interface is read-only. No action execution exists yet.

## Future Integration

Actions can later connect to:

- STiGMA FLAC Validator for validation actions.
- Audio Division NFO generator for NFO actions.
- SFV generator for checksum-file actions.
- Metadata refresh for missing metadata/artwork actions.
- Identity review tools for unresolved validator evidence.

Execution should remain explicit and user-triggered.
