# Audio Division Integration Audit

Sprint BC is a read-only audit of the smallest safe integration point between STIGMA Archive Hub and the external `stigma_audio_division` tool.

The Hub should orchestrate Audio Division. It should not copy, rewrite, or partially reimplement Audio Division behavior.

## Systems Reviewed

- Hub integration layer: `audio_division/integration.py`
- Hub operation history: `audio_division/operation_runner.py`
- Hub lifecycle model: `audio_division/lifecycle_state.py`
- Existing integration design: `docs/AUDIO_DIVISION_INTEGRATION.md`
- Audio Division process flow: `/home/stigma/apps/stigma_audio_division/main.py`
- Audio Division archive behavior: `/home/stigma/apps/stigma_audio_division/archive.py`
- Audio Division rename behavior: `/home/stigma/apps/stigma_audio_division/rename.py`
- Audio Division scan, metadata, verification, and cleanup helpers
- Audio Division GUI execution path
- Audio Division config defaults and local `config.toml`

## Current Hub Integration Contract

The Hub currently models Audio Division processing as:

```text
<audio_division_path> process-album <album_folder>
```

The Hub wrapper:

1. Validates that an album folder was supplied.
2. Validates that `tools.audio_division_path` is configured.
3. Runs the configured command with `subprocess.run`.
4. Treats exit code `0` as success.
5. Records the result in `data/operation_history.json`.

The wrapper does not currently inspect the archive after execution. It records process result, not archive truth.

## Audio Division Process Flow

The external `process_album(folder, cfg)` flow is:

```text
input folder
-> scan FLAC files
-> validate that tracks exist
-> classify release as ALBUM, EP, or SINGLE
-> detect release metadata from FLAC tags
-> build rename plan
-> optionally prompt for confirmation
-> move and rename FLAC files into scene release folder
-> move cover into release root
-> generate NFO
-> generate SFV
-> generate M3U8
-> verify SFV
-> move release into archive or quarantine
-> cleanup source tree
```

Audio Division is therefore the correct owner of:

- release naming
- FLAC renaming
- multidisc layout
- NFO generation
- SFV generation
- playlist generation
- archive placement
- duplicate quarantine behavior
- post-processing source cleanup

## Inputs

Audio Division expects a local folder containing FLAC files.

Supported layout:

```text
incoming_album/
  01-track.flac
  02-track.flac
```

or:

```text
incoming_album/
  CD1/
    01-track.flac
  CD2/
    01-track.flac
```

Scan behavior:

- Recursively walks the supplied folder.
- Skips hidden directories.
- Skips subtrees containing `.FETCHING`.
- Groups `CD1`, `CD2`, etc. as discs.
- Raises an error if no FLAC files are found.

Required FLAC metadata:

- `ARTIST`
- `ALBUM`
- `DATE`, `YEAR`, or `ORIGINALDATE`

Folder names are not trusted for release metadata.

Required config:

- `paths.archive_root`
- optional duplicate quarantine root
- optional duplicate log path
- optional NFO greets

## Output Folders

Audio Division first creates a release folder beside the input folder:

```text
<incoming_parent>/<artist>-<album>-<year>-WEB-FLAC-STiGMA/
```

Then it archives the release to:

```text
<archive_root>/<artist_letter>/<artist>/<Albums|EPs|Singles>/<release>/
```

Duplicates are moved to quarantine when configured:

```text
<archive_root>/<quarantine_root>/<release>/
```

If quarantine is not configured and the target already exists, Audio Division raises an error.

## Generated Artifacts

For a successfully processed release, Audio Division generates:

```text
00-<release>.nfo
00-<release>.sfv
00-<release>.m3u8
cover.jpg
```

The release also contains renamed FLAC files. Multidisc releases contain `CD1`, `CD2`, etc. under the album root.

## Cleanup Behavior

After archiving, Audio Division calls source cleanup.

Cleanup removes directories that no longer contain FLAC files. Exceptions during cleanup are swallowed.

This means the source folder may disappear or become empty after a successful process. That is expected. The archive target becomes the durable evidence.

## Failure Behavior

Possible failure points:

- no FLAC files found
- missing required FLAC tags
- invalid year/date metadata
- rename move failure
- artifact write failure
- archive target duplicate without quarantine
- archive move failure
- unexpected filesystem error

Important current behavior:

- SFV verification returns `False` on failure, but `process_album()` does not currently stop when verification fails.
- Duplicate quarantine returns a target path and may look like a successful process from the subprocess perspective.
- Cleanup errors are swallowed.
- The current main entrypoint prompts for `Album folder:` and does not implement a `process-album` subcommand.

## Command Contract Mismatch

The Hub documents and generates:

```text
<audio_division_path> process-album <album_folder>
```

The currently reviewed Audio Division `main.py` does not parse that command. It prompts interactively for an album folder and calls `process_album(folder, cfg)`.

The Audio Division GUI achieves noninteractive behavior by importing `process_album()` directly and injecting:

```text
cfg["options"]["auto_apply"] = True
```

The config defaults contain `behavior.non_interactive` and `behavior.assume_yes`, but `process_album()` currently checks `options.auto_apply`.

### Finding

The Hub should not assume the current `process-album` command is safe until Audio Division exposes a stable noninteractive CLI or a dedicated wrapper script.

## Success Evidence

Return code alone is not enough to prove successful archive processing.

Strong success evidence should be:

- release folder exists under the configured archive root
- release folder is indexed by the Archive Registry
- FLAC files are present
- `00-*.nfo` is present
- `00-*.sfv` is present
- `00-*.m3u8` is present
- playlist references resolve
- SFV references resolve
- AlbumTruth reports archive evidence

Supporting evidence:

- operation history result is success
- Audio Division stdout contains archived target path
- source folder has been cleaned or no longer contains FLAC files

Validation evidence from `STIGMA_VALIDATED.txt` remains owned by STIGMA FLAC Validator. Audio Division processing does not currently write that marker.

## Failure Evidence

Failure evidence should include:

- subprocess exit code is nonzero
- stderr or stdout contains an error
- source folder still contains FLAC files
- release folder exists beside source but was not archived
- archive target is missing
- generated artifacts are missing
- playlist references are broken
- SFV references are broken
- release was quarantined as a duplicate

Quarantine should be modeled separately from normal archive success. It means Audio Division handled the duplicate, but the album did not become a normal archived release.

## Can Hub Safely Hand an Album to Audio Division?

Not safely through the current command contract unless `tools.audio_division_path` points to a purpose-built wrapper that implements noninteractive processing.

The reason is not that Audio Division is unsuitable. The reason is that the Hub's subprocess contract and the current Audio Division entrypoint do not match.

There is also a workflow safety concern: Hub must only hand incoming or downloaded folders to Audio Division. It should not hand existing archive album roots to `process_album()`, because Audio Division is designed to rename, move, archive, and clean up a source folder.

For existing archive albums, the safe operations remain:

- validate album
- revalidate album
- generate or regenerate documentation through explicit documentation tools
- open folder
- inspect AlbumTruth

## Lifecycle Representation

Audio Division processing can be represented as a lifecycle transition.

Recommended derived transition:

```text
DOWNLOADED
-> PROCESSING
-> ARCHIVED
```

If validator evidence exists before processing:

```text
VALIDATED
-> READY_FOR_PROCESSING
-> PROCESSING
-> ARCHIVED
```

The `PROCESSING` state should be workflow intent from queue or operation history. The `ARCHIVED` state should be derived from filesystem evidence and AlbumTruth.

Failure should be recorded in operation history and processing queue state. It should not be treated as archive truth unless filesystem evidence confirms a partial release, quarantine release, or broken archive target.

## Smallest Safe Integration Point

The smallest safe integration point is a stable Audio Division process command that the Hub can call as a subprocess.

Recommended command shape:

```text
stigma process-album <incoming_folder> --config <config.toml> --yes
```

Recommended future structured result:

```json
{
  "status": "archived",
  "source_folder": "/path/to/incoming",
  "release_folder": "/path/to/intermediate/release",
  "archive_path": "/path/to/archive/release",
  "quarantine_path": null,
  "generated_artifacts": {
    "nfo": "...",
    "sfv": "...",
    "playlist": "...",
    "artwork": "..."
  },
  "track_count": 12,
  "release_type": "ALBUM",
  "verification_passed": true,
  "warnings": []
}
```

The Hub should continue to use subprocess isolation. Importing Audio Division internals directly would couple the Hub to Audio Division's Python module layout, config loading, stdout behavior, and mutation sequence.

## Recommended Future Process Album Design

1. Audio Division exposes a noninteractive CLI or wrapper.
2. Hub validates that the target is an incoming/downloaded folder, not an archive root.
3. Hub records operation start in operation history.
4. Hub invokes Audio Division through the integration layer.
5. Hub captures stdout, stderr, exit code, and optional structured result.
6. Hub rebuilds or refreshes Archive Registry inputs.
7. Hub refreshes AlbumTruth.
8. Hub determines final outcome from filesystem evidence:
   - archived
   - quarantined
   - failed
   - partial
9. Hub updates processing queue visibility.

## Recommended Guardrails

- Do not call `process_album()` on existing archive album roots.
- Do not treat return code `0` as final archive truth.
- Do not mark an album archived until the archive registry or AlbumTruth sees the release.
- Do not conflate Audio Division processing with FLAC Validator validation.
- Treat quarantine as handled duplicate, not normal archive success.
- Preserve operation history as audit evidence, not source of truth.
- Prefer a dry-run or preview mode before future automatic campaign processing.

## Answer Summary

Can Hub safely hand an album to Audio Division?

Only after the command contract is made real through a noninteractive CLI or wrapper, and only for incoming/downloaded source folders.

What proves successful processing?

Filesystem evidence in the archive, generated artifacts, valid references, Archive Registry projection, and AlbumTruth. Operation history is supporting evidence only.

What proves failed processing?

Nonzero subprocess result, error output, source folder still containing FLACs, missing archive target, partial release folder, broken artifacts, or quarantine evidence.

Can processing be represented as a lifecycle transition?

Yes. `DOWNLOADED` or `READY_FOR_PROCESSING` can transition through `PROCESSING` intent to `ARCHIVED` filesystem truth.

## Next Recommended Sprint

Implement the Audio Division process contract alignment.

Scope:

- either add a stable wrapper path expectation in Hub settings
- or update Audio Division to expose `process-album <folder>` noninteractively
- add post-run evidence verification in Hub
- refuse to process existing archive roots
- represent quarantine and partial results distinctly

This should happen before campaign-scale processing or any automatic closed-loop handoff.
