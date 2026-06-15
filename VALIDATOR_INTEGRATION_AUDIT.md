# Validator Integration Audit

Audit date: 2026-06-15

Scope: research audit of `/home/stigma/apps/stigma_flac_validator` and its future integration with STiGMA Audio Division. This document proposes integration architecture only; it does not implement changes.

## Validator Role

The STiGMA FLAC Validator is already the strongest truth component in the wider audio pipeline. Its README says it is the truth and routing authority for local-first music archiving. Code confirms that it validates folders, checks FLAC integrity, checks completeness, optionally compares against Deezer, writes per-album validation logs, and updates `validated_albums.json`.

## Inputs

### CLI Input

Entrypoint:

```text
stigma-flac-validator [OPTIONS] SOURCE
python3 cli.py SOURCE
```

`SOURCE` can be:

- A single album folder.
- A directory containing album folders.
- A folder with Disc/CD subfolders.

### Filesystem Input

Validator discovers album folders using:

- Audio files directly in folder.
- Audio files in Disc/CD subfolders.
- Immediate subfolders under a source directory.

Supported audio extensions:

- `.flac`
- `.mp3`
- `.ogg`
- `.m4a`
- `.wav`
- `.aac`

Validation is FLAC-centered. Non-FLAC files are governed by `NON_FLAC_POLICY`.

### Metadata Input

Validator reads local audio tags through Mutagen:

- `album`
- `albumartist` or `artist`
- `tracknumber`
- `discnumber`
- `album_id`
- `ALBUM_ID`
- `isrc`

It also uses:

- `flac -t` subprocess for FLAC integrity.
- Deezer API by ISRC lookup for optional completeness verification.

### Config Input

Config path:

```text
~/.config/stigma-flac-validator/config.json
```

Observed config keys used by CLI:

- `needs_stamp_dir`
- `complete_dir`
- `problematic_dir`
- `validated_index`

### Flags

- `--stamp`: enable moving/routing.
- `--dry-run`: decide states but do not move.
- `--require-album-id`: fail or route when ALBUM_ID is missing.
- `--revalidate`: ignore existing validation logs.
- `--no-deezer`: skip Deezer completeness verification.

## Outputs

### Per-Album Validation Log

Filename:

```text
STIGMA_VALIDATED.txt
```

Writer:

- `/home/stigma/apps/stigma_flac_validator/logger.py`

Current shape:

```json
{
  "album": "folder name",
  "validated_at": "ISO timestamp",
  "tracks": 14,
  "warnings": [],
  "completeness": {
    "mode": "album-wide",
    "album": "Discovery",
    "album_artist": "Daft Punk",
    "expected_tracks": 14,
    "found_tracks": 14,
    "missing_tracks": [],
    "missing_album_id_tracks": 0,
    "album_id": "302127",
    "hashes": {
      "01 Track.flac": "sha256..."
    }
  }
}
```

### Global Validated Index

Configured by `validated_index`.

Current curator copy:

```json
{
  "1583391": {
    "folder": "Souleance-La Belle Vie-2012-FLAC-STiGMA",
    "source": "stigma-flac-validator",
    "tracks": 18,
    "validated_at": "2026-01-08T02:28:02.056617"
  }
}
```

Current repository count observed: 504 validated album IDs.

### Console Output

Validator prints:

- Number of albums found.
- Per-album state.
- FLAC validation failures.
- Completeness failures.
- Missing ALBUM_ID warnings/failures.
- Deezer mismatch notes.
- Move/routing actions.

### Routing Output

When `--stamp` is enabled:

- FLAC validation failure can move to `problematic_dir`.
- Missing ALBUM_ID can move to `needs_stamp_dir`.
- Fully validated albums can move to `complete_dir`.

## What Validator Already Knows

Validator already knows:

- Album folder path and folder name.
- Whether folder contains audio files.
- FLAC file list.
- Whether each FLAC passes `flac -t`.
- SHA-256 hash per FLAC file.
- Whether non-FLAC files are present.
- Album tag consistency.
- Album artist tag consistency.
- Track numbering completeness.
- Disc numbering mode.
- Expected vs found track count.
- Missing track numbers.
- Missing ALBUM_ID count.
- Consistent ALBUM_ID value when all tracks agree.
- ISRC values present in local tags.
- Deezer candidate album ID discovered through ISRC lookup.
- Deezer track count match result.
- Validation timestamp.
- Destination routing decision in stamp mode.

## What Audio Division Currently Consumes

Current curator consumes only:

- `data/validated_albums.json` keys as album IDs.
- The presence of an album ID in that file to skip already validated albums.
- Identity Viewer displays album ID status as validated.

Current curator ignores:

- Folder path.
- Validation timestamp beyond display potential.
- Track count.
- Per-album validation log.
- Hashes.
- Completeness detail.
- Warnings.
- Deezer verification detail.
- ISRCs.

## What Audio Division Could Consume Next

High-value fields to consume:

- Album ID.
- Archive folder path.
- Validated timestamp.
- Track count.
- Album title and album artist from tags.
- Per-file SHA-256 hashes.
- Album manifest hash.
- ISRC list.
- Completeness details.
- Warning list.
- Deezer verification result.
- Validator version.

These should feed a rebuildable archive index, not replace the filesystem as source of truth.

## Additional Metadata Validator Could Emit

Recommended additions for future validator output:

- `schema_version`
- `validator_version`
- `source_root`
- `album_path`
- `archive_relative_path`
- `album_id_status`
- `audio_files[]` with:
  - relative path
  - size
  - mtime
  - extension
  - sha256
  - duration if available
  - tags: title, tracknumber, discnumber, album, albumartist, artist, isrc, album_id
- `track_isrcs_ordered`
- `track_count_expected`
- `track_count_found`
- `manifest_hash`
- `deezer_verification`:
  - checked boolean
  - matched boolean
  - candidate album ID
  - notes
  - source ISRC
- `routing_decision`
- `errors`
- `warnings`

## Should Track Hashes Be Recorded?

Yes.

Reasons:

- Supports exact file identity.
- Supports bitrot checks.
- Supports archive repair.
- Allows duplicate file detection even when tags differ.
- Allows detecting changed files after validation.

Current validator already computes SHA-256 per FLAC and writes it into `STIGMA_VALIDATED.txt` under completeness hashes.

Recommendation:

- Keep per-track hashes.
- Add relative paths and sizes so hashes remain useful after moves.
- In the archive index, store per-track file hash as evidence, not as the only track identity.

## Should Album Manifest Hashes Be Recorded?

Yes.

Definition:

- Deterministic hash over sorted relative file paths, file sizes, file hashes, and possibly normalized tag identity.

Benefits:

- One stable archive-entry fingerprint.
- Easy exact duplicate detection.
- Easy "has this folder changed since validation?" check.
- Useful for backup verification and repair.

Recommendation:

- Add `manifest_hash` to future validator output.
- Build it from data the validator already has.

## Archive Repair Support

Validator data can support repair if it records:

- Which files existed.
- Expected track/disc positions.
- File hashes.
- ISRCs.
- ALBUM_ID.
- Tag snapshots.
- Missing track numbers.
- Deezer expected count.
- Validation timestamp.

Repair questions enabled:

- Which track file changed?
- Which track is missing?
- Which album folder lost tags?
- Which album has a mismatched ALBUM_ID?
- Which albums need redownload?

## Duplicate Detection Support

Validator can support duplicate detection with:

- ALBUM_ID.
- UPC if passed from Deezer metadata in future.
- Ordered ISRC list.
- Track count.
- Folder title/artist tags.
- Manifest hash.
- Per-file hashes.

Duplicate classes:

- Exact duplicate: same manifest hash.
- Same files, different folder: same per-file hashes.
- Same release, different files: same UPC or ALBUM_ID plus compatible tracklist.
- Same recordings, different release: high ISRC overlap.
- Suspect duplicate: normalized artist/title/year/track count match.

## Future Integration Model

Recommended architecture:

```text
Validator remains writer of validation evidence.
Audio Division reads validator evidence into a rebuildable index.
Curator uses index summaries for skip/dedupe decisions.
Filesystem remains source of truth.
```

Integration layers:

1. Validator output contract
   - Versioned JSON per album.
   - Versioned global index.
   - No database dependency.

2. Archive index importer
   - Reads `validated_albums.json`.
   - Reads `STIGMA_VALIDATED.txt` from archive folders.
   - Normalizes into searchable tables.
   - Can be rerun from scratch.

3. Curator integration
   - Checks album ID, UPC, and ISRC-level ownership before queueing.
   - Displays validated/archived status.
   - Avoids treating shipped/attempted as validated.

4. Repair/reconciliation jobs
   - Compare shipped jobs to validated results.
   - Compare archive folders to validator manifest hashes.
   - Report missing, changed, duplicate, and unindexed folders.

## Risks

- Current `validated_albums.json` is too thin for future archive intelligence.
- Per-album logs are inside folders; if folders move, the global index needs path reconciliation.
- Validator global index writes are not atomic in current validator code.
- Deezer completeness currently matches by ISRC and track count only; this is useful but not full release verification.
- The validator and curator currently share no formal schema contract.

## Recommendations

Do next:

- Define a versioned validator output schema.
- Keep current `validated_albums.json` compatibility but add richer optional fields later.
- Add manifest hash generation in validator in a future implementation sprint.
- Import validator logs into a rebuildable archive index.

Do not do yet:

- Make SQLite the source of truth.
- Let curator mutate validator state.
- Treat Deezer mismatch as archive corruption without human review.
