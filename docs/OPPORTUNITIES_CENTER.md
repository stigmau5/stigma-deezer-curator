# Opportunities Center

Sprint T adds a central Opportunities Center for STiGMA Archive Hub.

The center uses existing derived state from Library, Archive Readiness, Metadata Intelligence, Identity, and Lifecycle. It does not modify archive files and does not introduce a database.

## Categories

`NEEDS_VALIDATION`

Album has enough identity/path evidence to act on, but validation evidence is missing.

`NEEDS_DOCUMENTATION`

Album is validated, but archive documentation is incomplete.

`NEEDS_METADATA`

Album does not have cached metadata, but no higher-priority readiness issue is currently blocking it.

`NEEDS_REVIEW`

Identity, archive path, or readiness evidence is uncertain.

`ARCHIVE_READY`

Album is currently archive-ready according to the readiness model.

## Priority Model

`HIGH`

- validation issues
- identity or archive path review

`MEDIUM`

- documentation gaps

`LOW`

- metadata enrichment
- archive-ready browsing

## Actions

The GUI exposes single-album actions only:

- Validate Album
- Generate Documentation
- Refresh Metadata
- Open Folder

Actions use the existing operation runner. Unsupported future actions are surfaced through the runner instead of bypassing it.

## Future Campaign Hooks

Future campaign workflows may include:

- Validate Campaign
- Documentation Campaign
- Metadata Campaign
- Identity Resolution Campaign

Campaigns should remain explicit user-initiated workflows.
