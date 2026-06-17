# Album Operations

Sprint O adds album-level archive maintenance to the Library tab.

The feature is read from existing registry and archive evidence. It does not create a new source of truth, rewrite metadata, or call tools outside the existing operation runner.

## Status Model

Album status is derived for:

- Validation
- NFO
- SFV
- Playlist
- Artwork
- Metadata

Each item is shown as:

- `Present`
- `Missing`
- `Unknown`

`Unknown` is used when Audio Division does not have enough archive evidence to make a safe claim, such as when no archive folder can be resolved.

## Artifact Detection

The artifact detector scans the resolved album folder for:

- `*.nfo`
- `*.sfv`
- `*.m3u`
- `*.m3u8`
- artwork files with `.jpg`, `.jpeg`, `.png`, or `.webp`
- `STIGMA_VALIDATED.txt`

Counts are retained for display and future reporting.

## Album Health

Album Health is a simple informational score:

```text
present known items / known items
```

Unknown items are excluded from the denominator. The score is not persisted and is not used as archive truth.

## Operation Integration

Album operations use the existing `audio_division.operation_runner` layer:

- Validate Album
- Generate NFO
- Generate SFV
- Open Folder

The GUI passes the selected album folder to the operation runner. Results are written to `data/operation_history.json` by the existing history layer.

No direct GUI subprocess calls are introduced for album operations.

## Future Expansion

Potential future album actions:

- Play Album
- Open NFO
- Open Playlist
- Regenerate Documentation
- Repair Album
- Identity Review

These are not implemented in Sprint O.
