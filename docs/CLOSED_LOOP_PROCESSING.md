# Closed Loop Processing

Sprint AC introduces a visibility-only Processing Queue.

The queue helps STiGMA Archive Hub show which downloaded albums need archive work after curation and download. It does not run Audio Division, the validator, NFO generation, SFV generation, metadata import, or any external tool.

## Processing States

- `DISCOVERED`: the album is known, but no archive path is known.
- `DOWNLOADED`: an archive path is known, but processing artifacts are not present.
- `PROCESSING`: the user has queued the album for processing.
- `ARCHIVED`: validation, NFO, and SFV evidence are present.

`AlbumTruth` remains the canonical source for physical evidence. The processing queue records user intent only.

## Truth Relationship

Processing display is derived from:

1. `AlbumTruth.processing_state`
2. `data/processing_queue.json`

If `AlbumTruth` says an album is archived, the UI should display it as archived even if an old queue entry still says `PROCESSING`.

## Queue File

Queue state is stored in:

```text
data/processing_queue.json
```

Schema:

```json
{
  "schema": 1,
  "albums": {
    "/archive/Artist-Album": {
      "artist": "Artist",
      "album": "Album",
      "archive_path": "/archive/Artist-Album",
      "source": "archive",
      "state": "PROCESSING",
      "queued_at": "2026-06-19T12:00:00",
      "updated_at": "2026-06-19T12:00:00"
    }
  }
}
```

## UI Behavior

The Archive tab displays a Processing section with:

- Album
- Source
- Current State

The `Queue For Processing` action updates queue state only. It does not mutate archive files and does not execute tools.

## Future Loop

Future sprints can connect this queue to controlled campaigns:

```text
Curator
-> Download
-> Processing Queue
-> Validate / Generate NFO / Generate SFV
-> AlbumTruth refresh
-> Archived
```

For now the queue is a foundation for visibility and workflow planning.
