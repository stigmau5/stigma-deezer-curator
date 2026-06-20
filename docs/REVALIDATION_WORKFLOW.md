# Revalidation Workflow

Validation is repeatable.

The Hub exposes `revalidate_album` as an explicit operation so an already validated album can be checked again without special-casing previous validation state.

## Behavior

`revalidate_album` uses the same configured validator executable as `validate_album`:

```text
tools.flac_validator_path
```

The operation runner records it separately in operation history:

```text
operation: revalidate_album
```

This keeps the user's intent visible while preserving the existing validator workflow.

## Truth Refresh

After revalidation is launched from the Archive workspace, the Hub refreshes:

- Archive Browser
- Album Workspace
- AlbumTruth-derived status
- Audio Division dashboard summaries

Library revalidation refreshes the Library projection and selected album details.

## Non-Goals

This workflow does not:

- modify validator behavior
- prevent validation of already validated albums
- infer success from old validation state
- introduce a new validation source of truth

Filesystem evidence and validator output remain authoritative.
