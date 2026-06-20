# Lifecycle Map

Generated: `2026-06-20`

This is a read-only lifecycle audit of the STIGMA Deezer Curator, Streamrip, STIGMA FLAC Validator, STIGMA Audio Division, and Archive Hub workflow.

No workflow code, archive files, validator files, schemas, or generated state files were modified.

## Executive Finding

The real-world album lifecycle is already visible from filesystem evidence and existing state files, but the evidence is split across several layers:

- Curator state tracks discovery intent, queue attempts, confirmations, and shipped jobs.
- Streamrip creates downloaded release folders outside the archive.
- The validator records historical validation by Deezer album ID and by external validation logs.
- Audio Division is treated as the authoritative external archive-processing tool for NFO, SFV, playlist, and documentation generation.
- Archive Hub detects physical archive presence from the archive filesystem through `data/archive_registry.json` and `AlbumTruth`.

The Hub can determine lifecycle state today, but not perfectly from one source. It needs a layered evidence model that keeps filesystem truth first while also preserving Curator, validator, and processing evidence.

## Current System Diagram

```text
Deezer links
  |
  v
Curator inbox
  |
  +--> Artist expansion -> data/artists/*.txt
  |
  +--> Streamrip queue -> /home/stigma/apps/streamrip/download_que.txt
  |
  +--> Local handoff receipt -> data/shipped/*.txt
  |
  +--> Server job handoff -> /media/storage/streamrip/jobs/pending/*.job
                                  |
                                  v
                              Streamrip
                                  |
                                  v
                          Downloaded release folder
                                  |
                                  v
                         STIGMA FLAC Validator
                                  |
                         validation evidence
                                  |
                                  v
                         STIGMA Audio Division
                                  |
                    NFO / SFV / playlist / cover / archive layout
                                  |
                                  v
                           Physical Archive
                                  |
                                  v
                 Archive Registry -> AlbumTruth -> Hub UI / reports
```

## Current Folder Diagram

```text
Repository state
  data/
    inbox.txt
    curated.log
    artists/*.txt
    attempted_albums.json
    confirmed_albums.json
    shipped/*.txt
    shipped_tmp/*.job
    shipped_jobs.json
    validated_albums.json
    lifecycle_registry.json
    identity_registry.json
    archive_registry.json
    metadata_cache.json
    audio_division_settings.json
    operation_history.json

Streamrip handoff
  /home/stigma/apps/streamrip/
    bin/rip
    download_que.txt

Streamrip / validator working area
  /home/stigma/StreamripDownloads/
    Incoming/
    complete_releases/
    needs_stamp/
    problematic/
    validated/

Physical archive
  /media/stigma/fa8a4ea5-d1da-4c46-b697-900ced38b5ca/archive/
    <letter-or-number>/
      <artist>/
        Albums/<release>/
        EPs/<release>/
        Singles/<release>/
        Live/<release>/
```

## Current Counts

These counts come from the current derived state files and reports:

| Evidence | Count |
| --- | ---: |
| Lifecycle albums | `6653` |
| Artist files | `191` |
| Artist-file album lines | `6483` |
| Attempted albums | `2027` |
| Confirmed albums | `70` |
| Shipped albums | `918` |
| Validated album IDs | `504` |
| Physical archive album folders | `3000` |
| Physical archive tracks | `41456` |
| Archive Albums category folders | `2485` |
| Archive EPs category folders | `252` |
| Archive Singles category folders | `263` |
| Metadata cached albums | `24` |
| Metadata cached artists | `11` |
| Metadata cached tracks | `288` |
| Validation logs found under `/home/stigma/StreamripDownloads` | `77` |
| Unmatched validator logs | `77` |
| Operation history entries | `8` |

Archive audit currently reports:

| Archive audit category | Count |
| --- | ---: |
| Albums scanned | `3000` |
| Missing NFO | `0` |
| Missing SFV | `0` |
| Missing playlist | `0` |
| Missing audio | `0` |
| Broken playlist references | `0` |
| Broken SFV references | `0` |
| Unexpected layouts | `0` |
| Missing artwork | `13` |
| Missing archive-root validation marker | `3000` |

The validation number is a known evidence-integration gap documented in `reports/validation_truth_report.md`.

## Curator Lifecycle

### Discovery

Curator discovery starts with `data/inbox.txt`.

The inbox may contain Deezer album links and Deezer artist links. `curator.curate.run_curation()` processes each inbox line:

- Album links are passed through unless their album ID is already present in `data/validated_albums.json`.
- Artist links are expanded through Deezer metadata into artist release files.
- Processed inbox lines are recorded in `data/curated.log`.
- Failed artist expansions are intentionally not logged, so transient API failures remain retryable.

Discovery evidence:

- `data/inbox.txt`
- `data/curated.log`
- `data/artists/*.txt`
- `data/lifecycle_registry.json`

### Artist Files

Artist files are the main discovery inventory.

`curator.lifecycle.read_artist_releases()` parses `data/artists/*.txt` and extracts Deezer album IDs from album URLs. Each matching line creates `DISCOVERED` evidence in `data/lifecycle_registry.json`.

Discovery identity is currently Deezer album ID.

### Attempted

An album becomes attempted when the user queues or fires an album URL from the GUI.

Attempt evidence is written by `curator.attempts.record_attempt()` to:

```text
data/attempted_albums.json
```

The file records:

- album URL
- attempt count
- last attempt timestamp

This state means the user tried to act on the discovered release. It does not prove Streamrip downloaded anything.

### Confirmed

The GUI can mark selected artist-file or queue albums as confirmed.

Confirmation evidence is stored in:

```text
data/confirmed_albums.json
```

The file records:

- album ID
- album URL
- confirmation timestamp
- source artist file, when available

Current lifecycle ordering treats `CONFIRMED` as the highest legacy Curator state. That reflects Curator's historical meaning, but it is not the same as physical archive readiness.

### Queued

There are two queue styles:

1. Local Streamrip queue:

```text
/home/stigma/apps/streamrip/download_que.txt
```

The GUI writes URL-only queue contents, then launches:

```text
/home/stigma/apps/streamrip/bin/rip file /home/stigma/apps/streamrip/download_que.txt
```

2. Server job queue:

```text
/media/storage/streamrip/jobs/pending/*.job
```

`curator.ship.ship_one_album_url()` creates a local temporary job file under `data/shipped_tmp/`, uploads it as `.tmp`, then atomically renames it into the server pending directory.

Queued evidence:

- current contents of `/home/stigma/apps/streamrip/download_que.txt`
- local receipts in `data/shipped/*.txt`
- job ledger in `data/shipped_jobs.json`
- temporary job files in `data/shipped_tmp/`
- remote server pending jobs, if reachable

### Downloaded

Downloaded state is less formal than discovery or shipping.

The Hub's source-agnostic Closed Loop Monitor can discover downloaded folders through:

```text
audio_division_settings.archive_paths.incoming_root
```

Current setting:

```text
incoming_root: ""
```

Observed Streamrip working folders:

```text
/home/stigma/StreamripDownloads/Incoming/
/home/stigma/StreamripDownloads/complete_releases/
/home/stigma/StreamripDownloads/needs_stamp/
/home/stigma/StreamripDownloads/problematic/
/home/stigma/StreamripDownloads/validated/
```

Current observed folder counts:

| Folder | Direct release folders |
| --- | ---: |
| `/home/stigma/StreamripDownloads/Incoming` | `0` |
| `/home/stigma/StreamripDownloads/complete_releases` | `77` |
| `/home/stigma/StreamripDownloads/problematic` | `0` |
| `/home/stigma/StreamripDownloads/validated` | `0` |

The current Hub does not have a configured incoming root, so downloaded albums are not fully represented in the UI as a continuous lifecycle state.

## Streamrip Lifecycle

Streamrip is not owned by this repository. The Curator treats Streamrip as an external downloader.

Known local installation:

```text
/home/stigma/apps/streamrip/bin/rip
```

Known queue file:

```text
/home/stigma/apps/streamrip/download_que.txt
```

Known observed output area:

```text
/home/stigma/StreamripDownloads/
```

The repository does not currently encode Streamrip's internal temporary-folder rules. The Hub can infer downloaded state from folders that appear under configured incoming roots, but it does not currently inspect Streamrip's runtime internals.

Recommended interpretation:

- Queue file means selected download intent.
- Shipped job ledger means remote download intent.
- Incoming or complete release folder means downloaded physical evidence.
- Archive registry entry means the release has crossed into archive territory.

## STIGMA FLAC Validator Lifecycle

The validator is external and remains authoritative for validation.

Known validation evidence sources:

```text
data/validated_albums.json
/home/stigma/StreamripDownloads/**/STIGMA_VALIDATED.txt
```

`curator.validator_evidence.collect_validation_evidence()` reads:

- `data/validated_albums.json`
- validation logs discovered under `/home/stigma/StreamripDownloads`
- validation logs discovered under `/home/stigma/StreamripDownloads/complete_releases`

The validated index is keyed by Deezer album ID. Detailed validation logs may include:

- validated timestamp
- track count
- completeness payload
- hash counts
- optional album ID
- validator log path

Current validator evidence:

- `504` validated album IDs from `data/validated_albums.json`
- `77` `STIGMA_VALIDATED.txt` logs
- `77` logs currently unresolved to lifecycle album IDs
- `504` identity releases marked high-confidence by validated album ID

Success markers:

- Album ID present in `data/validated_albums.json`
- Matched `STIGMA_VALIDATED.txt` log
- Archive-root `STIGMA_VALIDATED.txt`, if present

Failure or warning markers:

- Missing validator evidence
- Unmatched validator logs
- Missing `ALBUM_ID` inside validation logs
- Validation logs with incomplete identity payloads

Current gap:

Physical archive audit only recognizes archive-root `STIGMA_VALIDATED.txt`; it does not yet consume matched identity validation evidence. This makes physical archive validation appear worse than lifecycle validation.

## STIGMA Audio Division Lifecycle

Audio Division is treated as an external archive-processing tool, not rewritten inside the Hub.

The Hub integration contract is:

```text
<audio_division_path> process-album <album_folder>
```

Current setting:

```text
tools.audio_division_path: ""
```

Audio Division is expected to own:

- archive processing
- NFO generation
- SFV generation
- playlist generation
- archive documentation

The Hub also still has compatibility settings for:

```text
tools.nfo_generator_path
tools.sfv_generator_path
tools.flac_validator_path
```

All are currently blank.

Generated artifact evidence recognized by the Hub:

- any `.nfo` file means NFO present
- any `.sfv` file means SFV present
- any `.m3u` or `.m3u8` file means playlist present
- preferred artwork files include `cover.jpg`, `folder.jpg`, `front.jpg`, `cover.png`, `folder.png`
- `STIGMA_VALIDATED.txt` means filesystem-local validation present

Audio Division output that remains after successful processing should therefore be visible through Archive Registry and AlbumTruth without the Hub needing to understand Audio Division internals.

Evidence intentionally removed:

- This repository does not contain code that documents Audio Division cleanup behavior.
- No repository-owned cleanup contract proves which temporary files are deleted after processing.
- The lifecycle map should treat cleanup as external tool behavior until Audio Division exposes a stable processing report or manifest.

## Archive Lifecycle

The archive filesystem is the source of truth.

Configured archive root:

```text
/media/stigma/fa8a4ea5-d1da-4c46-b697-900ced38b5ca/archive
```

Formal album roots are:

```text
<archive>/<letter>/<artist>/Albums/<release>
<archive>/<letter>/<artist>/EPs/<release>
<archive>/<letter>/<artist>/Singles/<release>
<archive>/<letter>/<artist>/Live/<release>
```

Disc folders are components, not album entities:

```text
CD1
CD2
CD3
Disc 1
Disc 2
```

Archive presence is detected by `audio_division.archive_registry.discover_album_folders()` and `is_album_root()`.

An archive album root must:

- be under a recognized category folder
- not be a disc folder
- contain album evidence, such as direct audio, album artifacts, or disc folders with audio

The Archive Registry records:

- folder name
- absolute archive path
- relative archive path
- audio track count, including disc folders
- NFO presence
- SFV presence
- playlist presence
- artwork presence
- archive-root validation marker presence

`AlbumTruth` then derives album status from:

1. filesystem artifacts
2. validator evidence
3. archive registry artifacts
4. metadata cache
5. reports/UI

Filesystem evidence wins.

## Canonical Lifecycle States

The current legacy lifecycle registry uses:

```text
DISCOVERED
ATTEMPTED
SHIPPED
VALIDATED
CONFIRMED
```

For the full ecosystem, the recommended canonical lifecycle should be album-centric and evidence-based:

| State | Meaning | Required Evidence | Source Of Truth |
| --- | --- | --- | --- |
| `DISCOVERED` | Album is known as a candidate. | Deezer album ID in `data/artists/*.txt`, inbox candidate, or future source candidate. | Curator state files |
| `QUEUED` | User selected album for download or server job handoff. | URL in Streamrip queue, local shipped receipt, or pending job ledger. | Queue/ship files |
| `ATTEMPTED` | User attempted to act on the album from Curator. | Album ID in `data/attempted_albums.json`. | Curator state |
| `SHIPPED` | Remote Streamrip job was handed off. | Album ID in `data/shipped_jobs.json`. | Curator ship ledger |
| `DOWNLOADED` | Release folder exists outside archive. | Folder under configured incoming/download root. | Filesystem |
| `READY_FOR_VALIDATION` | Downloaded release has audio evidence and is not yet validated. | Download folder with audio, no validation evidence. | Filesystem plus validator evidence |
| `VALIDATED` | Validator accepted the album. | Archive-root `STIGMA_VALIDATED.txt`, matched validator log, or `validated_albums.json` album ID. | Validator evidence, with filesystem marker strongest |
| `READY_FOR_PROCESSING` | Validated or downloaded album is ready for Audio Division processing. | Downloaded folder plus validation or explicit processing queue intent. | Filesystem plus processing queue |
| `PROCESSING` | User queued or launched processing. | `data/processing_queue.json` entry or operation history entry. | Hub workflow state |
| `ARCHIVED` | Album exists as a formal archive root. | Archive Registry album root under `Albums`, `EPs`, `Singles`, or `Live`. | Archive filesystem |
| `DOCUMENTED` | Archive documentation artifacts exist. | NFO, SFV, and playlist found at album root. | Archive filesystem |
| `ARCHIVE_READY` | Album has enough evidence for archive workstation readiness. | AlbumTruth readiness rules: archive path, identity confidence, validation, NFO/SFV, playlist/artwork. | AlbumTruth derived from filesystem and evidence |
| `NEEDS_REVIEW` | State is contradictory or insufficient. | Missing identity, unresolved validation log, missing expected artifact, or ambiguous folder match. | Hub derived reports |

## State Diagram

```text
DISCOVERED
  |
  v
QUEUED / ATTEMPTED
  |
  v
SHIPPED
  |
  v
DOWNLOADED
  |
  v
READY_FOR_VALIDATION
  |
  v
VALIDATED
  |
  v
READY_FOR_PROCESSING
  |
  v
PROCESSING
  |
  v
ARCHIVED
  |
  v
DOCUMENTED
  |
  v
ARCHIVE_READY

Any state
  |
  v
NEEDS_REVIEW
```

Some real-world paths skip states. For example, a manually imported archived album may first appear at `ARCHIVED`, and a legacy validated album may have `VALIDATED` evidence without a current download folder.

## Evidence Sources By State

| Evidence file or folder | Lifecycle meaning |
| --- | --- |
| `data/inbox.txt` | Pending discovery input |
| `data/curated.log` | Inbox lines processed by Curator |
| `data/artists/*.txt` | Discovered Deezer album candidates |
| `data/attempted_albums.json` | User queued or attempted album action |
| `data/confirmed_albums.json` | User-confirmed album candidates |
| `/home/stigma/apps/streamrip/download_que.txt` | Current local Streamrip queue |
| `data/shipped/*.txt` | Local queue handoff receipts |
| `data/shipped_tmp/*.job` | Local temporary server job artifacts |
| `data/shipped_jobs.json` | Server job handoff ledger |
| `/media/storage/streamrip/jobs/pending/*.job` | Remote Streamrip pending jobs |
| `/home/stigma/StreamripDownloads/Incoming` | Incoming downloaded folders, when configured |
| `/home/stigma/StreamripDownloads/complete_releases` | Completed or validator-related release folders |
| `data/validated_albums.json` | Validator index by Deezer album ID |
| `STIGMA_VALIDATED.txt` | Filesystem-local or external validator log evidence |
| `data/lifecycle_registry.json` | Rebuildable Curator lifecycle projection |
| `data/identity_registry.json` | Rebuildable identity and validator evidence projection |
| `data/archive_registry.json` | Rebuildable physical archive projection |
| `data/metadata_cache.json` | Rebuildable metadata enrichment cache |
| `data/processing_queue.json` | Hub processing intent |
| `data/operation_history.json` | Hub operation outcomes |

## Known Gaps

1. Downloaded state is not yet fully configured.
   `archive_paths.incoming_root` is blank, so the Closed Loop Monitor cannot present Streamrip downloads as a continuous incoming lifecycle.

2. Streamrip output semantics are external.
   The repo knows the queue path and observed output roots, but not Streamrip's internal temp/final naming contract.

3. Validation truth is split.
   Lifecycle and identity know about `504` validated album IDs, but the physical archive audit only sees archive-root `STIGMA_VALIDATED.txt`.

4. Audio Division cleanup behavior is not documented in this repo.
   The Hub recognizes final artifacts, but not which temporary inputs are intentionally removed after processing.

5. `CONFIRMED` is a legacy Curator state, not an archive-readiness state.
   It should remain available as curation evidence but should not outrank filesystem archive evidence in future lifecycle summaries.

6. Server job completion is not visible from the local state files.
   `data/shipped_jobs.json` proves handoff, not download success.

7. Identity remains partial.
   There are `504` high-confidence identity links and `6149` unknown identity releases in `data/identity_registry.json`.

## Recommended Integration Points

1. Configure incoming roots.
   Point `archive_paths.incoming_root` at the real Streamrip post-download staging folder once the desired folder is confirmed.

2. Add a Download Evidence layer.
   Derive downloaded candidates from Streamrip output folders without making those folders a new source of truth.

3. Add a Processing Manifest contract for Audio Division.
   Have Audio Division emit a small report after processing that states input folder, output archive path, artifacts generated, cleanup actions, and result.

4. Connect validation evidence into AlbumTruth.
   Preserve filesystem marker priority, but allow matched validator index/log evidence to explain validation status.

5. Separate Curator lifecycle from Archive lifecycle in reports.
   Curator states answer "what did I intend or hand off?" Archive states answer "what do I physically have?"

6. Make `ARCHIVED` a filesystem-derived state.
   Formal archive root presence should be the decisive evidence that an album is physically archived.

7. Treat operation history as an audit trail, not truth.
   Operation history can explain why a state changed, but the archive filesystem and validator evidence should prove the current state.

## Can The Hub Determine Lifecycle State From Existing Files?

Yes, mostly.

The Hub can determine a useful lifecycle state from filesystem and existing state files if it combines:

- Curator discovery and handoff files
- Streamrip queue and observed download folders
- Validator index and logs
- Audio Division-generated filesystem artifacts
- Archive Registry
- AlbumTruth
- Processing queue and operation history

The strongest current model is:

```text
Curator evidence answers: what was discovered, attempted, confirmed, or shipped?
Download folder evidence answers: what has arrived locally?
Validator evidence answers: what was validated?
Archive filesystem evidence answers: what is actually archived?
AlbumTruth answers: what is true about this album now?
```

What is missing for a perfect closed loop:

- a configured incoming/download root
- a stable Streamrip completion marker or downloaded-album manifest
- a stable Audio Division processing report
- a unified validation source model that distinguishes filesystem marker, validated index, detailed log, and unresolved log

Without those, the Hub can still provide a reliable derived lifecycle, but some transitions remain inferred rather than proven.

## Recommended Next Sprint

Recommended next implementation sprint:

```text
Sprint AY - Download Evidence and Closed Loop Wiring
```

Scope:

- Configure or model the Streamrip incoming/complete output roots.
- Create a derived Download Evidence projection from existing folders.
- Link downloaded candidates to Curator album IDs when possible.
- Display downloaded-not-archived albums in the existing Closed Loop Monitor.
- Do not automate processing.
- Do not modify Streamrip, Audio Division, validator, or archive files.

Rationale:

The biggest lifecycle gap is between `SHIPPED` and `ARCHIVED`. The system already knows discovery, handoff, validation, and archive filesystem state. It does not yet have a strong local proof layer for "downloaded but not processed or archived." Closing that visibility gap makes the later Audio Division processing integration safer.
