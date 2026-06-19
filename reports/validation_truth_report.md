# Validation Truth Report

Generated: `2026-06-19`

Read-only audit of validation evidence flow. No archive files, validation files, schemas, or truth logic were modified.

## Executive Finding

`reports/archive_audit.md` reports `Missing validation: 3000` because the current archive audit pipeline only treats `STIGMA_VALIDATED.txt` inside each physical archive album folder as validation evidence.

The physical archive root currently contains `0` `STIGMA_VALIDATED.txt` files.

Historical validation evidence does exist, but it lives elsewhere:

- `data/validated_albums.json`: `504` validated album IDs.
- `/home/stigma/StreamripDownloads`: `77` discovered `STIGMA_VALIDATED.txt` logs.
- `data/lifecycle_registry.json`: `504` albums with validation evidence, all from the validated index.
- `data/identity_registry.json`: `504` high-confidence lifecycle validation links, plus `77` unresolved validator logs.

The mismatch is therefore a validation-truth integration gap, not proof that every archive album has never been validated.

## Validation Sources

| Source | Count | Meaning | Current Join Key |
| --- | ---: | --- | --- |
| Archive album-root `STIGMA_VALIDATED.txt` | `0` | Filesystem-local validation marker inside archive folders. | Physical folder path |
| `data/validated_albums.json` | `504` | Validator global index keyed by Deezer album ID. | Deezer album ID |
| Configured validation log root `/home/stigma/StreamripDownloads` | `77` logs | Detailed validator logs outside the archive root. | Folder name and optional embedded album ID |
| Lifecycle validation evidence | `504` | Imported from `validated_albums.json`; no detailed logs matched. | Deezer album ID |
| Identity registry high-confidence validation links | `504` lifecycle releases | High confidence because album IDs appear in validated index. | Deezer album ID |
| Identity unresolved validator logs | `77` | Detailed logs with no durable lifecycle join key. | Folder name, review candidates |

## Validation Consumers

| Component | Validation Source Used | Result |
| --- | --- | --- |
| Archive Audit | Archive Registry artifacts from physical album roots only. | Reports `3000` missing validation. |
| Archive Registry | `detect_album_artifacts()` on album root only. | Records `validation_log: false` for all `3000` album roots. |
| AlbumTruth for Archive Browser | Filesystem artifacts plus archive-registry artifacts; physical archive path wins. | Reports validation `Missing` for all physical archive albums. |
| Archive Browser | Uses `physical_archive.project_archive_album()` and AlbumTruth. | Shows `not_validated` for all archive albums. |
| Maintenance Center | Uses AlbumTruth status fields. | `Needs Validation: 3000`, validation coverage `0.0%`. |
| Dashboard | Uses AlbumTruth summary when available, otherwise lifecycle validation counts. | Can diverge depending on which derived data path is loaded. |
| Lifecycle Registry | Reads `data/validated_albums.json` and validator evidence collection. | Knows `504` validated album IDs. |
| Identity Registry | Reads lifecycle validation evidence. | Knows `504` high-confidence validated lifecycle releases. |

## Validation Coverage

| View | Albums | Validation Present | Validation Missing |
| --- | ---: | ---: | ---: |
| Physical archive audit | `3000` | `0` | `3000` |
| Archive Browser / AlbumTruth physical projection | `3000` | `0` | `3000` |
| Maintenance Center physical projection | `3000` | `0` | `3000` |
| Lifecycle registry | `6653` | `504` | `6149` |
| Identity registry | `6653` | `504` high-confidence lifecycle links | `6149` unknown |

Additional physical archive facts:

- Archive albums scanned: `3000`
- Missing NFO: `0`
- Missing SFV: `0`
- Missing playlist: `0`
- Missing audio: `0`
- Broken playlist references: `0`
- Broken SFV references: `0`
- Unexpected layouts: `0`
- Missing artwork: `13`

## Reason For Mismatch

The pipeline has two separate validation meanings:

1. Filesystem validation marker:
   `STIGMA_VALIDATED.txt` inside the archive album root.

2. External validator/lifecycle validation:
   `validated_albums.json` and detailed logs under `/home/stigma/StreamripDownloads`.

The Archive Audit, Archive Registry, AlbumTruth physical projection, Archive Browser, and Maintenance Center currently use only the first meaning for physical archive albums.

The Lifecycle and Identity systems know about the second meaning, but that evidence is not passed into AlbumTruth when physical archive albums are projected.

In code terms:

- `audio_division.archive_audit.audit_album()` checks album-root artifacts only.
- `audio_division.artifacts.detect_album_artifacts()` only detects `STIGMA_VALIDATED.txt` in the album root.
- `audio_division.physical_archive.project_archive_album()` calls `album_truth(...)` without passing `validator_evidence` from the matched identity release.
- `audio_division.album_truth.album_truth()` can already accept `validator_evidence`, but the physical archive projection does not use it.

## Special Check: Validated Index Samples

These albums have validation evidence in `data/validated_albums.json` / `data/identity_registry.json`, but the physical archive pipeline still reports missing validation.

| Album ID | Artist | Album | Filesystem Evidence | Audit Result | AlbumTruth Result | Maintenance Result | External Validation Evidence |
| --- | --- | --- | --- | --- | --- | --- | --- |
| `606885032` | 23till | men_fran_peking_hors_det_inget_remastered_2024-2024-WEB-FLAC-STiGMA | No archive-root `STIGMA_VALIDATED.txt` | Missing validation | Missing / filesystem | Needs Validation | validated index, 9 tracks, 2026-01-13T15:30:48.011700 |
| `154960222` | 23till | nojd-1993-WEB-FLAC-STiGMA | No archive-root `STIGMA_VALIDATED.txt` | Missing validation | Missing / filesystem | Needs Validation | validated index, 13 tracks, 2026-01-13T15:15:53.609554 |
| `9410100` | ac_dc | back_in_black-2014-WEB-FLAC-STiGMA | No archive-root `STIGMA_VALIDATED.txt` | Missing validation | Missing / filesystem | Needs Validation | validated index, 10 tracks, 2026-01-13T15:33:25.076974 |
| `9410116` | ac_dc | backtracks-2014-WEB-FLAC-STiGMA | No archive-root `STIGMA_VALIDATED.txt` | Missing validation | Missing / filesystem | Needs Validation | validated index, 47 tracks, 2026-01-13T15:16:48.990544 |
| `9410110` | ac_dc | black_ice-2008-WEB-FLAC-STiGMA | No archive-root `STIGMA_VALIDATED.txt` | Missing validation | Missing / filesystem | Needs Validation | validated index, 15 tracks, 2026-01-13T15:30:30.228176 |
| `9410088` | ac_dc | blow_up_your_video-2014-WEB-FLAC-STiGMA | No archive-root `STIGMA_VALIDATED.txt` | Missing validation | Missing / filesystem | Needs Validation | validated index, 10 tracks, 2026-01-13T15:28:16.371014 |
| `9410164` | ac_dc | dirty_deeds_done_dirt_cheap-1976-WEB-FLAC-STiGMA | No archive-root `STIGMA_VALIDATED.txt` | Missing validation | Missing / filesystem | Needs Validation | validated index, 9 tracks, 2026-01-13T15:26:15.689020 |
| `9410094` | ac_dc | flick_of_the_switch-2014-WEB-FLAC-STiGMA | No archive-root `STIGMA_VALIDATED.txt` | Missing validation | Missing / filesystem | Needs Validation | validated index, 10 tracks, 2026-01-13T15:35:48.786601 |
| `9410090` | ac_dc | fly_on_the_wall-2014-WEB-FLAC-STiGMA | No archive-root `STIGMA_VALIDATED.txt` | Missing validation | Missing / filesystem | Needs Validation | validated index, 10 tracks, 2026-01-13T15:27:17.928744 |
| `9410098` | ac_dc | for_those_about_to_rock_we_salute_you-2014-WEB-FLAC-STiGMA | No archive-root `STIGMA_VALIDATED.txt` | Missing validation | Missing / filesystem | Needs Validation | validated index, 10 tracks, 2026-01-13T15:24:24.157682 |

## Divergence Point

Truth diverges at the boundary between identity/lifecycle evidence and physical archive projection.

The identity registry can say:

```text
Album ID 9410100
identity_confidence: HIGH
validation.available: true
validation.validated_at: 2026-01-13T15:33:25.076974
```

But the physical archive projection then builds AlbumTruth from:

```text
archive_path
registry_artifacts
metadata_state
metadata_album
identity_confidence
```

It does not include:

```text
identity_release.validation
```

So AlbumTruth only sees the missing archive-root `STIGMA_VALIDATED.txt` and reports `Missing`.

## Recommended Fix

Do not change archive data.

Recommended next implementation sprint:

1. Keep Archive Registry filesystem-only.
   It should continue to report only physical artifacts found under album roots.

2. Introduce validation-source detail in the projection/audit layer:
   - `filesystem_validation`: archive-root `STIGMA_VALIDATED.txt`
   - `validated_index`: `data/validated_albums.json`
   - `validation_log`: matched detailed validator log
   - `unresolved_validation_log`: detailed log exists but cannot be safely joined

3. Pass matched identity validation evidence into AlbumTruth for physical archive albums.
   `physical_archive.project_archive_album()` should pass `validator_evidence` from `identity_release["validation"]`.

4. Update Archive Audit to report validation by source:
   - Missing all validation evidence
   - Validated by index only
   - Validated by detailed log
   - Filesystem marker present
   - Validation evidence unresolved

5. Preserve source/confidence labels in UI.
   The user should see the difference between:
   - `Validation: Present (filesystem)`
   - `Validation: Present (validated index)`
   - `Validation: Present (detailed validator log)`
   - `Validation: Unresolved log`

6. Keep filesystem evidence authoritative.
   If an archive-root `STIGMA_VALIDATED.txt` exists, it should win over external evidence for that folder. External validated-index evidence should enrich truth, not overwrite filesystem facts.

## Conclusion

`Missing Validation: 3000` is technically accurate for archive-root `STIGMA_VALIDATED.txt` evidence, but misleading as an archive-health statement.

The archive has `504` known validated lifecycle albums and `77` external detailed validation logs, but the physical archive audit does not currently consume those sources.

The fix should connect matched validator evidence into AlbumTruth and Archive Audit while preserving the distinction between filesystem validation markers, validated-index evidence, detailed logs, and unresolved logs.
