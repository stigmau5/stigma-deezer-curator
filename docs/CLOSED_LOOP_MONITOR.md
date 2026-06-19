# Closed Loop Monitor

The Closed Loop Monitor is a visibility layer for downloaded albums that have not yet become archive albums.

It supports the long-term workflow:

```text
Discover
Download
Process
Archive
```

Sprint AM does not automate processing, validation, documentation generation, metadata import, or archive repair.

## Incoming Albums

Incoming albums are local downloaded folders that are not represented by the current archive projection.

The current source is:

- Deezer downloads from the configured Incoming Root

Future sources can use the same monitor shape:

- YouTube
- Bandcamp
- Manual Import
- CD Rip

Each source should produce the same basic album candidate:

- album
- artist when discoverable
- source
- folder
- state

## States

Downloaded:
The folder exists in an incoming source root.

Needs Processing:
The incoming folder contains audio evidence but has not been queued as processing.

Processing:
The user has explicitly queued the album for processing.

Archived:
The album has archive evidence and should no longer appear in Incoming.

## Archive Integration

The monitor compares incoming folder identity with archive album identities already known by the Archive Browser.

When an incoming folder is represented by the archive projection, it is filtered out of the Incoming view.

Filesystem and archive registry evidence remain the source of truth. The monitor is a derived view only.

## Actions

Open Folder:
Uses the existing operation runner to open the incoming folder.

Queue For Processing:
Records user intent in `data/processing_queue.json`.

No external processing tool is launched by the monitor.

## Future Workflow

Future sprints can connect queued incoming albums to controlled processing:

```text
Incoming Source
-> Album Candidate
-> Processing Queue
-> Audio Division
-> Archive Registry Refresh
-> AlbumTruth
-> Closed Loop Monitor
```

The monitor should remain source-agnostic. Downloaders and importers should adapt their output into album candidates rather than embedding source-specific behavior in the UI.
