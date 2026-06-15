# Archive Identity Resolution Audit

Audit date: 2026-06-15

Scope: Sprint F research-only audit. No implementation, schema migration, workflow change, SQLite work, GUI change, or lifecycle change is proposed as completed here.

## Files Reviewed

Curator state and reports:

- `data/artists/*.txt`
- `data/lifecycle_registry.json`
- `data/validated_albums.json`
- `data/attempted_albums.json`
- `data/confirmed_albums.json`
- `data/shipped_jobs.json`
- `reports/validation_evidence_report.md`
- `reports/validation_confidence_report.md`
- `ARCHIVE_IDENTITY_AUDIT.md`
- `DEEZER_METADATA_SURVEY.md`
- `VALIDATOR_INTEGRATION_AUDIT.md`
- `EVOLUTION_SUMMARY.md`
- `docs/VALIDATOR_EVIDENCE.md`

Curator code:

- `curator/lifecycle.py`
- `curator/validator_evidence.py`
- `curator/metadata.py`
- `curator/ship.py`
- `curator/links.py`

Validator code and artifacts:

- `/home/stigma/apps/stigma_flac_validator/validator.py`
- `/home/stigma/apps/stigma_flac_validator/completeness.py`
- `/home/stigma/apps/stigma_flac_validator/deezer_verify.py`
- `/home/stigma/apps/stigma_flac_validator/logger.py`
- `/home/stigma/apps/stigma_flac_validator/config.py`
- `/home/stigma/apps/stigma_flac_validator/README.md`
- `/home/stigma/StreamripDownloads/**/STIGMA_VALIDATED.txt`

## Current Identity Situation

The lifecycle registry uses Deezer album ID as the operational key. This works well for discovery, attempts, shipment, validation index entries, and confirmations because those state files either contain Deezer album URLs or are keyed by album ID.

Validator evidence has two forms:

- `data/validated_albums.json`, keyed by Deezer album ID.
- Per-folder `STIGMA_VALIDATED.txt`, keyed implicitly by archive folder and any tags found in audio files.

Sprint E found:

- Albums with validation evidence: 504
- Validated-index albums: 504
- Validation logs found: 77
- Matched detailed validation logs: 0
- Unmatched validation logs: 77

This is not a validator correctness bug. It is an identity join problem between provider-centric lifecycle state and local archive-centric validation artifacts.

## Why 77 Validation Logs Were Not Matched

The 77 discovered `STIGMA_VALIDATED.txt` files were not matched because they lack a durable join key that the lifecycle registry can trust.

Observed causes:

- `completeness.album_id` is `null` in sampled validation logs.
- `missing_album_id_tracks` equals the track count in sampled logs, meaning every track was missing an `ALBUM_ID` tag.
- The global `validated_albums.json` only includes albums whose completeness result had an album ID.
- Folder names in the validation logs are human archive names such as `Ronny & Ragge-Let's Pok-1993-FLAC-STiGMA`, not canonical lifecycle keys.
- The lifecycle registry currently knows Deezer album IDs and display artist/title, but not UPC, ordered ISRC lists, track hashes, or manifest hashes.
- Many unmatched validation folders belong to artists not present in the current discovery set.
- Some archive folder names include hyphens, punctuation, doubled spaces, accents, alternate spellings, or compilation artist names that make folder parsing ambiguous.
- One observed validation path was nested under a shipment-like folder, for example `20260306_184928_deezer_album_178200592/...`, but the validation log itself still had `album_id: null`.

The current Sprint E linker correctly refused to guess.

## Naming Differences

Current naming formats are close but not equivalent.

Lifecycle discovery rows come from artist files:

```text
https://www.deezer.com/album/606885032  # ALBUM | ...Men fran Peking hors det inget (Remastered 2024) | unknown year | 0 tracks
```

Validated index folders are Streamrip/archive folder names:

```text
Boogie Belgique-Blueberry Hill-2015-FLAC-STiGMA
```

Unmatched validation logs are also folder-name based:

```text
Various Artists-Punk-O-Rama, Vol. 3-2008-FLAC-STiGMA
Ronny & Ragge-Let's Pok-1993-FLAC-STiGMA
Yusuf  Cat Stevens-Tea For The Tillerman (Super Deluxe)-2020-FLAC-STiGMA
```

Risks in folder-name identity:

- Artist and title are separated by hyphens, but both artist and title can contain hyphens.
- Archive folders are sanitized differently from Deezer display strings.
- Accents and punctuation may be preserved, stripped, or altered at different points.
- `Various Artists` folders do not map to a single discovered artist file.
- Release year in the folder may not equal original release date, Deezer release date, remaster date, or compilation date.
- Folder name says what is archived, not necessarily which Deezer album ID produced it.

## Metadata Differences

The validator log knows:

- Archive folder name.
- Validation timestamp.
- Track count.
- Completeness mode.
- Album tag.
- Album artist tag.
- Expected and found track counts.
- Missing track numbers.
- Missing `ALBUM_ID` tag count.
- Optional album ID if all tracks share one.
- Per-file SHA256 hashes.

The lifecycle registry knows:

- Deezer album ID.
- Artist display name.
- Title display name.
- Discovered/attempted/shipped/validated/confirmed booleans.
- Shipped job name when available.
- Validated index folder when available.
- Validation timestamp and track count from `validated_albums.json`.

Important missing bridge fields:

- UPC.
- Deezer artist ID.
- Deezer track IDs.
- Ordered Deezer tracklist.
- Ordered ISRC list.
- Embedded ISRCs from local files.
- Local track title/duration list.
- Album manifest hash.
- Archive root and stable archive-relative path.
- Explicit validation run ID.
- Shipment job to final archive folder mapping after movement.

## ALBUM_ID Differences

The validator supports two album ID paths:

- `completeness.py` reads `album_id` tags through Mutagen easy tags.
- `validator.py` reads `ALBUM_ID` or `album_id` tags for informational status.

`logger.py` writes the global validated index only when `completeness.get("album_id")` is present.

The unmatched logs show `album_id: null`, so they cannot enter `validated_albums.json` and cannot be joined by lifecycle album ID. They can still prove file integrity and local completeness, but they cannot prove Deezer lifecycle identity.

## SHA256 and ISRC Handling

SHA256:

- Validator computes SHA256 per FLAC file.
- `STIGMA_VALIDATED.txt` persists hashes inside `completeness.hashes`.
- The lifecycle registry does not currently import hashes.
- There is no album manifest hash yet.

ISRC:

- Validator has an ISRC-based Deezer verification module.
- The per-folder validation logs sampled in this audit do not include ordered ISRC evidence.
- The curator does not cache Deezer track ISRC lists.

Implication: the pieces exist, but the current outputs do not provide an identity bridge that is both stable and safe.

## Match Classification

### High Confidence Matches

Criteria recommended for future use:

- `ALBUM_ID` tag is present and consistent on every track, and it equals a lifecycle Deezer album ID.
- Or the validation log is under a shipment job path containing `deezer_album_<id>`, every track count/title signal is compatible, and there is no conflicting embedded album ID.
- Or UPC and ordered ISRC list match cached Deezer metadata exactly.

Current count from existing detailed logs: 0 confirmed high-confidence matches.

Reason: no sampled unmatched log has a usable `album_id`, UPC, ordered ISRC list, or imported manifest identity.

### Medium Confidence Matches

Criteria recommended for future use:

- Normalized artist + normalized title + track count match exactly.
- Year/release date is compatible.
- No competing lifecycle candidates exist.
- Local file track titles align with cached Deezer track titles.

Observed exploratory count: 16 of 77 unmatched logs have exact normalized artist/title matches against current registry rows, all for `Ronny & Ragge`.

These should remain review candidates, not automatic links, until tracklist, ISRC, UPC, or shipment evidence is added.

### Low Confidence Matches

Criteria:

- Folder title resembles a lifecycle title but artist is missing, ambiguous, or compilation-like.
- Year and track count are plausible but not unique.
- Artist exists but multiple album variants have similar titles.

Examples likely to fall here:

- Compilations by `Various Artists`.
- Common titles such as `Svenska Favoriter`, `Svenska klassiker`, or `Svenska Sangfavoriter`.
- Remastered, deluxe, anniversary, soundtrack, clean, and explicit variants.

### Impossible Matches With Current Evidence

Criteria:

- Artist is not present in discovery state.
- No album ID, UPC, ISRC list, shipment path, or track metadata bridge exists.
- Folder parser cannot safely split artist/title due ambiguous hyphen placement.
- Multiple plausible Deezer records exist and there is no disambiguator.

Observed exploratory count: 61 of 77 unmatched logs had no exact normalized artist/title pair in the current lifecycle registry.

These may still be valid archive releases, but they are not linkable to lifecycle entities with present data.

## Current Failure Modes

- A validated archive folder can remain invisible to lifecycle intelligence if it lacks `ALBUM_ID`.
- A lifecycle row can show only `validated_index` evidence even when a detailed `STIGMA_VALIDATED.txt` exists elsewhere for the same real-world release.
- Folder-name matching can create false positives for compilations, remasters, and common Swedish compilation titles.
- Deezer album ID alone cannot collapse duplicate real-world releases across provider duplicates.
- SHA256 hashes prove exact files, but without a manifest identity and metadata bridge they cannot identify the intended release.

## Recommendations

1. Keep refusing automatic folder-name-only joins.
2. Treat all unmatched logs as archive evidence awaiting identity resolution, not as failed validations.
3. Introduce a future identity resolution layer before metadata cache, browser, or SQLite work.
4. Preserve all existing evidence exactly: folder, archive-relative path, validation timestamp, track count, file hashes, album tags, and missing tag counts.
5. Add a reviewable candidate-match report before any automatic writes.
6. Use confidence tiers rather than a single yes/no match.
7. Make `ALBUM_ID` consistency the strongest bridge for Deezer-sourced archive entries.
8. Add UPC and ordered ISRC list to future metadata cache before trying to resolve duplicate releases at scale.

## Bottom Line

The 77 validation logs are unmatched because they are archive-local validation artifacts without a stable provider identity. The safest next step is not to make matching cleverer inside lifecycle generation. The safest next step is to design and implement a separate identity resolution layer that can produce explicit, reviewable, confidence-scored links between archive folders, validator evidence, and Deezer lifecycle entities.
