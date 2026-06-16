# Metadata Cache

The metadata cache is a derived Deezer metadata layer for STiGMA Audio Division.

It does not modify curator workflows.

It does not modify validator workflows.

It does not modify archive files or tags.

It does not introduce SQLite.

## Purpose

The cache answers:

- What release metadata do we know?
- What metadata is missing?
- What artists, genres, labels, years, contributors, and ISRCs exist?
- What metadata foundations are available for future NFOs, archive browsing, and duplicate detection?

## Inputs

- `data/lifecycle_registry.json`
- `data/identity_registry.json`
- Deezer API responses
- Existing `data/metadata_cache.json` when present

## Outputs

- `data/metadata_cache.json`
- `reports/metadata_coverage_report.md`
- `reports/metadata_quality_report.md`
- `reports/metadata_collection_report.md`

`data/metadata_cache.json` is derived and rebuildable.

## Schema

```json
{
  "schema": 1,
  "generated_at": "...",
  "source": "deezer",
  "albums": {},
  "artists": {},
  "tracks": {},
  "errors": {},
  "summary": {}
}
```

Album records include:

- Deezer album ID
- title
- release date
- year
- UPC
- label
- genres
- contributors
- track count
- duration
- record type
- explicit flags
- cover URLs
- cover identity
- track IDs

Artist records include:

- Deezer artist ID
- name
- album count
- fan count
- picture URLs

Track records include:

- Deezer track ID
- title
- ISRC
- duration
- track number
- disc number
- contributors
- explicit flags

## Rebuild Philosophy

The filesystem remains truth.

The lifecycle and identity registries determine what provider IDs should be cached. The metadata cache stores provider descriptions for those IDs. If the cache is deleted, it can be rebuilt from the registries and Deezer APIs.

The builder is incremental: existing cached albums, artists, and tracks are preserved, and missing albums are fetched on later runs.

## Usage

Fetch all missing albums:

```bash
python build_metadata_cache.py
```

Fetch a limited batch:

```bash
python build_metadata_cache.py --limit 25
```

Limited batches are useful because full archive metadata includes thousands of albums and many more tracks.

## Reports

Coverage report:

- albums with metadata
- albums missing metadata
- artists cached
- tracks cached
- coverage percentage

Quality report:

- missing UPC
- missing release date
- missing genres
- missing label
- missing contributors
- missing ISRCs

Collection report:

- albums by year
- albums by genre
- albums by label
- top contributors
- oldest release
- newest release
