# Validator Evidence Integration

Validator evidence integration enriches the derived lifecycle registry with validation facts.

It does not modify the validator.

It does not modify validation workflow.

It does not create a new source of truth.

## Inputs

Primary inputs:

- `data/validated_albums.json`
- Existing `STIGMA_VALIDATED.txt` files found under local Streamrip download folders

`validated_albums.json` provides broad index evidence by Deezer album ID.

`STIGMA_VALIDATED.txt` provides detailed per-folder evidence when it can be safely matched by album ID or folder name.

## Registry Enrichment

Each lifecycle registry album receives a `validation_evidence` object.

Example:

```json
{
  "available": true,
  "album_id": "302127",
  "validated_at": "2026-06-15T12:00:00",
  "track_count": 14,
  "integrity_status": "passed",
  "deezer_verification_status": "not_recorded",
  "confidence": "detailed_log",
  "available_evidence": ["validated_index", "validation_log"]
}
```

## Evidence Levels

`detailed_log`

Matched `STIGMA_VALIDATED.txt` evidence is available.

`validated_index`

The album appears in `validated_albums.json`, but no matching per-folder validation log was found.

`none`

No validation evidence is available.

## Reports

Generated reports:

- `reports/validation_evidence_report.md`
- `reports/validation_coverage_report.md`
- `reports/validation_age_report.md`
- `reports/validation_confidence_report.md`

## Architecture

Filesystem remains truth.

Validator artifacts remain validation evidence.

The lifecycle registry remains derived state.

Reports are disposable and rebuildable.
