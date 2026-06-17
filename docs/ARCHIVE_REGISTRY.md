# Archive Registry

Sprint U1 adds a rebuildable Archive Registry.

The registry is derived from read-only filesystem inspection. It is not a source of truth and should be safe to delete and rebuild.

## Source

The scanner reads the configured `archive_paths.main_archive_root` from `data/audio_division_settings.json`.

## Album Folder Detection

A folder is considered an album folder when it directly contains at least one audio file.

Current audio extensions:

- `.flac`
- `.mp3`
- `.m4a`
- `.ogg`
- `.opus`
- `.wav`
- `.aiff`

## Captured Data

Each archive entry records:

- folder name
- absolute archive path
- relative archive path
- audio track count
- NFO presence
- SFV presence
- playlist presence
- artwork presence
- validation evidence presence

## Outputs

- `data/archive_registry.json`
- `reports/archive_registry_report.md`
- `reports/archive_artifact_coverage_report.md`

## Rebuild Philosophy

The archive filesystem remains truth. The registry is a queryable projection over that filesystem and can be regenerated at any time.

Future work may link archive registry entries to lifecycle and identity records, but this sprint only records physical archive contents.
