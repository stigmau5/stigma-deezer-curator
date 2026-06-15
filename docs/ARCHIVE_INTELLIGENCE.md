# Archive Intelligence

Archive Intelligence v1 is a reporting layer built on top of the derived lifecycle registry.

It does not introduce SQLite, network calls, or a new source of truth.

## Source

Primary input:

- `data/lifecycle_registry.json`

The lifecycle registry is itself rebuilt from existing state files:

- `data/artists/*.txt`
- `data/attempted_albums.json`
- `data/confirmed_albums.json`
- `data/shipped_jobs.json`
- `data/validated_albums.json`

## Reports

### `reports/archive_health_report.md`

Purpose:

- Summarize total known albums.
- Show count and percentage by highest lifecycle state.
- Surface broad health observations and major gaps.

### `reports/artist_coverage_report.md`

Purpose:

- Show discovered, validated, and confirmed counts per artist.
- Calculate coverage as `validated / discovered`.
- Identify top complete and incomplete artists.

Important limitation:

Coverage is only over albums currently discovered in artist files. It does not claim to know an artist's complete global discography.

### `reports/backlog_report.md`

Purpose:

- Focus on albums that are `DISCOVERED` but not `ATTEMPTED`.
- Show artists with the largest backlog.
- Provide a practical list of backlog albums for future queue/review work.

### `reports/gap_analysis_report.md`

Purpose:

- Highlight lifecycle inconsistencies and stuck work:
  - shipped but not validated
  - attempted but not shipped
  - confirmed but not validated
  - validated but not discovered

## Calculations

Highest lifecycle state comes from the lifecycle registry.

State order:

```text
DISCOVERED < ATTEMPTED < SHIPPED < VALIDATED < CONFIRMED
```

Artist coverage:

```text
validated discovered albums / discovered albums
```

Backlog:

```text
discovered == true and attempted == false
```

Shipment gap:

```text
shipped == true and validated == false
```

Attempt gap:

```text
attempted == true and shipped == false
```

Confirmation gap:

```text
confirmed == true and validated == false
```

Validation discovery gap:

```text
validated == true and discovered == false
```

## Rebuild Philosophy

Archive intelligence reports are disposable derived artifacts.

They can be deleted and regenerated from `data/lifecycle_registry.json`.

`data/lifecycle_registry.json` can be deleted and regenerated from the existing source files.

The filesystem and existing state files remain truth. Reports should guide investigation; they should not be edited as operational state.
