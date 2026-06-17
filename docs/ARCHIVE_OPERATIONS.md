# Archive Operations

Archive Operations make STiGMA Audio Division an orchestration layer.

Audio Division does not replace archive tools.

Audio Division does not rewrite validators, NFO generators, or SFV generators.

## Operation Lifecycle

1. User selects an operation and target.
2. Audio Division validates the request.
3. Audio Division prepares the external command from settings.
4. Audio Division launches the configured tool through `audio_division/operation_runner.py`.
5. Audio Division records the result in `data/operation_history.json`.
6. Future registry/report refreshes can reflect changed archive state.

## Supported Operations

- `generate_nfo`
- `generate_sfv`
- `validate_album`
- `open_album_folder`

`refresh_metadata` remains defined as an operation, but this sprint does not execute it.

## Settings

Tool paths are stored in `data/audio_division_settings.json`:

- `tools.nfo_generator_path`
- `tools.sfv_generator_path`
- `tools.flac_validator_path`
- `tools.file_manager_path`

The default file manager command is `xdg-open`.

## History Logging

History file:

- `data/operation_history.json`

Schema:

```json
{
  "schema": 1,
  "history": [
    {
      "timestamp": "...",
      "operation": "generate_nfo",
      "target": "/archive/Artist-Album-2026-FLAC-STiGMA",
      "result": "success",
      "message": "completed"
    }
  ]
}
```

History is written atomically and capped to recent entries.

## Tool Execution Philosophy

All execution flows through the operation runner.

The GUI should not call archive tools directly.

Future execution should remain:

- explicit
- user-triggered
- logged
- auditable
- followed by registry/report refresh

## Future Expansion

Future operations can add:

- metadata refresh
- batch validation
- batch NFO generation
- batch SFV generation
- post-operation registry rebuilds
- operation dry-run previews
