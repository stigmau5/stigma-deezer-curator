# Archive Readiness

Sprint R introduces a derived Archive Readiness model.

Readiness answers:

```text
Is this album archive-ready?
```

The model uses existing Audio Division evidence only. It does not modify archive files, rewrite metadata, run validators, or create a new source of truth.

## States

`ARCHIVE_READY`

Validation is present, documentation is present, archive path is known, identity is resolved, and artwork evidence is present.

`NEEDS_VALIDATION`

Archive path and identity evidence exist, but validation evidence is missing.

`NEEDS_DOCUMENTATION`

Validation is present, but documentation evidence is incomplete. Current documentation checks include NFO and SFV.

`NEEDS_REVIEW`

The album has enough evidence to inspect, but one or more quality signals are incomplete or uncertain.

`UNKNOWN`

There is not enough evidence to make a readiness decision. Missing archive path or unknown identity currently places an album here.

## Rule Precedence

Rules are evaluated in this order:

1. `UNKNOWN`: missing archive path or unknown identity.
2. `NEEDS_REVIEW`: uncertain path or identity confidence.
3. `NEEDS_VALIDATION`: validation is missing.
4. `NEEDS_DOCUMENTATION`: NFO or SFV is missing after validation exists.
5. `NEEDS_REVIEW`: artwork evidence is missing.
6. `ARCHIVE_READY`: all readiness signals are present.

## Future Workflow Usage

Archive Opportunities also carry readiness categories so future campaigns can group work by readiness state.

Readiness can guide future archive campaigns:

- Validate Ready Candidates
- Generate Missing Documentation
- Archive Completion Campaign
- Identity Resolution Campaign

Those campaigns should remain explicit user-initiated workflows.
