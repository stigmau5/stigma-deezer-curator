# Archive Path Resolution

Sprint P.5 adds explicit album-to-archive-folder resolution.

The Library projection now distinguishes between folder evidence and an openable archive path. This prevents album operations from pretending a path is known when Audio Division only has partial evidence.

## Sources

Archive path evidence currently comes from:

- `data/identity_registry.json`
- `archive_identity.folder`
- `validation.validation_log_path` when present
- Settings: `archive_paths.main_archive_root`

The lifecycle registry identifies albums by Deezer album ID, but it does not contain archive paths.

## Confidence Model

`HIGH`

- `validation_log_path` points to a file inside the album folder.
- `archive_identity.folder` is absolute.
- `archive_identity.folder` is relative and `Main Archive Root` is configured.

`MEDIUM`

- `archive_identity.folder` is known, but it is relative and no `Main Archive Root` is configured.
- Audio Division knows the archive folder name but not an openable absolute path.

`UNKNOWN`

- No archive folder evidence exists for the album.

## Projection Fields

Each Library album may expose:

- `archive_folder`
- `archive_path`
- `archive_path_confidence`
- `archive_path_reason`

Album operations use `archive_path`. They do not use folder names as executable targets unless those names have been resolved to a path.

## Future Archive Scanning

Future work can improve coverage by adding a read-only archive scanner that indexes existing folders and matches them to lifecycle albums. That scanner should remain derived and should not modify archive files.
