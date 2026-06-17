# Archive Tool Integration

Audio Division is the orchestration layer for existing archive tools.

It does not replace mature tools.

It does not execute tools automatically.

It does not modify archive files during startup.

## Orchestration Philosophy

Archive tools remain responsible for generating archive truth:

- STiGMA FLAC Validator validates integrity and emits validation evidence.
- STiGMA Audio Division NFO tooling generates NFO documentation.
- SFV tooling generates checksum documentation.

Audio Division identifies what needs work, prepares operation requests, and refreshes derived registries after future explicit execution.

## Tool Registry

`audio_division/tool_registry.py` represents external tools as capabilities.

Current tools:

- `stigma_flac_validator`
- `stigma_nfo_generator`
- `stigma_sfv_generator`

Current capabilities:

- `validate_album`
- `validate_directory`
- `generate_nfo`
- `regenerate_nfo`
- `generate_sfv`
- `regenerate_sfv`

Tools are marked non-executable in this sprint. The registry is descriptive.

## Operation Registry

`audio_division/operations.py` defines operations that Audio Division can prepare.

Current operations:

- Validate Album
- Generate NFO
- Generate SFV
- Open Album Folder
- Refresh Metadata

Each operation defines:

- id
- title
- description
- required inputs
- capability
- risk level
- action type

No operation executes in this sprint.

## Artifact Awareness

`audio_division/artifacts.py` detects archive artifacts:

- `.nfo`
- `.sfv`
- `.m3u` / `.m3u8`
- `STIGMA_VALIDATED.txt`

Generated report:

- `reports/archive_artifact_report.md`

## Future Execution Flow

Generate NFO:

```text
Audio Division
-> Operation
-> Tool Registry
-> STiGMA Audio Division NFO generator
-> Refresh Registry
```

Validate Album:

```text
Audio Division
-> Operation
-> STiGMA FLAC Validator
-> Refresh Registry
```

Generate SFV:

```text
Audio Division
-> Operation
-> SFV generator
-> Refresh Registry
```

All future execution should be explicit, user-triggered, auditable, and followed by a registry/report rebuild.
