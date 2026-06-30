# Audio Division Integration

Sprint AD adds the first integration layer between STiGMA Archive Hub and the external `stigma_audio_division` tool.

The Hub does not rewrite Audio Division. It treats Audio Division as the authoritative archive-processing tool for:

- NFO generation
- SFV generation
- Playlist generation
- Archive documentation
- Album processing

The FLAC validator remains separate. Validation is still handled by `stigma_flac_validator`.

## Settings

The preferred setting is:

```text
tools.audio_division_path
```

The Settings UI presents workflow-level tools:

```text
Audio Division
Validator
File Manager
```

Audio Division and Validator paths are auto-discovered without executing the tools. If exactly one installation is found, the setting can be populated automatically. If none or multiple are found, the path remains manually configurable.

Existing settings remain available for compatibility:

```text
tools.nfo_generator_path
tools.sfv_generator_path
tools.flac_validator_path
```

`nfo_generator_path` and `sfv_generator_path` are treated as legacy implementation details. They are kept in the settings file and operation runner for older maintenance actions, but they are no longer primary Settings UI fields.

Incoming Root and Needs Validation Root are both retained. Incoming Root represents newly downloaded releases; Needs Validation Root remains an optional validation work area and may point at the same location when validation happens in place.

## Command Contract

Initial process-album command:

```text
<audio_division_path> process-album <album_folder>
```

This is a wrapper contract only. The Hub does not copy Audio Division internals and does not infer how NFO, SFV, playlist, or archive documentation are generated.

## Processing Flow

```text
Downloaded
-> Queue
-> Process
-> AlbumTruth Refresh
-> Archived
```

Sprint AD adds the `Process Album` UI action from the Archive workspace. The action:

1. Queues the selected album for processing.
2. Calls the integration layer.
3. Records the result in operation history.
4. Refreshes Archive state through existing derived data.

Archive state remains derived from `AlbumTruth`; queue state is workflow intent.

## Source-Agnostic Future

Future sources should all produce an Album Candidate:

- Deezer
- YouTube
- Bandcamp
- Manual Import
- CD Rip

An Album Candidate should contain enough information to identify and stage an album, but Audio Division should remain source-agnostic. The processing tool should operate on archive folders and local evidence, not on source-specific downloader behavior.

Future architecture:

```text
Source
-> Album Candidate
-> Download / Import
-> Processing Queue
-> Audio Division
-> Validator
-> AlbumTruth
-> Archive
```

## Non-Goals

This sprint does not:

- Rewrite Audio Division
- Rewrite the validator
- Introduce SQLite
- Introduce playback
- Copy NFO or SFV generation logic into the Hub
- Automatically process queued albums
