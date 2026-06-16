# Audio Division Dashboard

The Audio Division dashboard is a read-only overview of derived archive intelligence.

It does not modify curator queues.

It does not modify shipping.

It does not modify validator behavior.

It does not perform network actions.

## Dashboard Purpose

The dashboard makes the new Audio Division backend visible in the existing application.

It shows:

- archive size
- lifecycle state coverage
- identity confidence
- metadata cache coverage
- validation coverage
- archive health gaps
- archive action counts and first recommended action details

## Data Sources

The dashboard reads:

- `data/lifecycle_registry.json`
- `data/identity_registry.json`
- `data/metadata_cache.json`

These are derived files. If they are missing, the dashboard displays zero values instead of failing startup.

## Settings

The Settings tab reads and writes:

- `data/audio_division_settings.json`

Settings currently support:

- main archive root
- incoming root
- problematic root
- needs validation root
- validated index path
- validation log root
- metadata cache path
- reports directory

The settings file is written atomically.

No subsystem uses these settings yet. They are a foundation for future archive, validator, metadata, and reporting integration.

## Rebuild Philosophy

Filesystem remains source of truth.

The dashboard reads derived projections. It does not make the lifecycle registry, identity registry, metadata cache, or settings file authoritative for archive contents.

If derived registries are deleted, they can be rebuilt from existing state files, validator evidence, and metadata APIs.
