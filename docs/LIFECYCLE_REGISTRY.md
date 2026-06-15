# Lifecycle Registry

The STiGMA Audio Division lifecycle registry is a derived projection of current archive workflow state.

It is not a source of truth.

## Purpose

The registry answers operational questions without introducing SQLite or changing existing workflows:

- What albums do we know about?
- Which albums are validated?
- Which albums are stuck?
- Which albums were shipped but never validated?
- Which albums are discovered but never attempted?

## Source Files

The registry is rebuilt from existing files:

- `data/artists/*.txt`
- `data/attempted_albums.json`
- `data/confirmed_albums.json`
- `data/shipped_jobs.json`
- `data/validated_albums.json`

The registry builder does not modify those files.

## Outputs

Generated outputs:

- `data/lifecycle_registry.json`
- `reports/lifecycle_summary.md`
- `reports/discovery_gap_report.md`
- `reports/shipment_gap_report.md`
- `reports/validation_gap_report.md`

These files are disposable. They can be deleted and rebuilt from the source files.

## Lifecycle Definitions

`DISCOVERED`

An album ID exists in an artist file under `data/artists/`.

`ATTEMPTED`

An album ID exists in `data/attempted_albums.json`.

`SHIPPED`

An album ID exists in `data/shipped_jobs.json`.

`VALIDATED`

An album ID exists in `data/validated_albums.json`.

`CONFIRMED`

An album ID exists in `data/confirmed_albums.json`.

## Highest State

Highest state is calculated from this order:

```text
DISCOVERED < ATTEMPTED < SHIPPED < VALIDATED < CONFIRMED
```

This is intentionally limited to evidence available in the existing curator state files.

The registry does not infer future states such as downloaded, archived, NFO generated, rejected, or problematic.

## Registry Shape

The generated JSON uses an explicit top-level object:

```json
{
  "schema": 1,
  "generated_at": "2026-06-15T12:00:00",
  "source_counts": {},
  "summary": {},
  "albums": [
    {
      "album_id": "302127",
      "artist": "Daft Punk",
      "title": "Discovery",
      "states": {
        "discovered": true,
        "attempted": true,
        "shipped": false,
        "validated": true,
        "confirmed": false
      },
      "highest_state": "VALIDATED",
      "sources": [],
      "timestamps": {},
      "details": {}
    }
  ]
}
```

## Rebuild Philosophy

Filesystem and existing state files remain truth.

The lifecycle registry is a projection. It should always be rebuilt from source files rather than hand-edited.

This keeps the project aligned with the Audio Division architecture direction:

- Filesystem is truth.
- Validator output is validation evidence.
- Curator state files are workflow evidence.
- Derived indexes are rebuildable.

## Why This Is Not Source Of Truth

The registry intentionally duplicates information from source files so it can answer questions quickly.

That duplication is safe only because:

- It is generated.
- It can be deleted.
- It can be rebuilt.
- Existing workflows do not depend on editing it.
- It does not replace artist files, validator output, shipment ledgers, or confirmation state.
