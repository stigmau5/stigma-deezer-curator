# Archive Identity Audit

Audit date: 2026-06-15

Scope: identity research for future STiGMA Audio Division architecture. This document is design-only. It proposes no schema migration and no implementation.

## Inputs Reviewed

- Current curator state files:
  - `data/artists/*.txt`
  - `data/attempted_albums.json`
  - `data/confirmed_albums.json`
  - `data/shipped_jobs.json`
  - `data/validated_albums.json`
- Curator modules:
  - `curator/links.py`
  - `curator/curate.py`
  - `curator/expand.py`
  - `curator/metadata.py`
  - `curator/ship.py`
  - `curator/state.py`
- Validator modules:
  - `/home/stigma/apps/stigma_flac_validator/validator.py`
  - `/home/stigma/apps/stigma_flac_validator/completeness.py`
  - `/home/stigma/apps/stigma_flac_validator/deezer_verify.py`
  - `/home/stigma/apps/stigma_flac_validator/logger.py`
- Observed Deezer payloads from:
  - `https://api.deezer.com/album/302127`
  - `https://api.deezer.com/artist/27`
  - `https://api.deezer.com/artist/27/albums`
  - `https://api.deezer.com/track/3135556`
  - `https://api.deezer.com/track/isrc:GBDUW0000059`

## Available Identifiers

### Deezer Album ID

Observed as `album.id` and encoded in album URLs.

Current use:

- Primary key in `validated_albums.json`.
- Primary dedupe key in `shipped_jobs.json`.
- Parsed from artist files, queue lines, and confirmed state.
- Written to FLAC tags as `ALBUM_ID` by the wider pipeline.

Assessment:

- Stable enough inside Deezer for discovery and requery.
- Not guaranteed to be globally unique across services.
- Not guaranteed to represent a unique real-world release. Deluxe editions, regional variants, reissues, explicit/clean versions, and catalog replacements can have separate Deezer album IDs.
- Excellent operational identity for "what did we ask Deezer/streamrip for?"
- Good verification identity when the archive was downloaded from Deezer and stamped with `ALBUM_ID`.

### Deezer Artist ID

Observed as `artist.id`, contributor IDs, related artist IDs, and artist URLs.

Current use:

- Artist URLs are parsed from inbox.
- Expansion uses the artist ID to fetch album lists.
- Artist files are named by sanitized artist name, not ID.

Assessment:

- Good discovery identity.
- Useful for grouping, contributor graph, related-artist discovery, and avoiding artist-name ambiguity.
- Not sufficient for archive identity because albums and tracks are the archived objects.
- Should be retained in future metadata as both main artist and contributor identifiers.

### Deezer Track ID

Observed as `track.id` and album tracklist item IDs.

Current use:

- Not stored by curator.
- Validator uses ISRC lookup, not Deezer track ID, for Deezer completeness matching.

Assessment:

- Good Deezer-local track identity.
- Useful for reconstructing exact Deezer tracklists and matching streamrip output.
- Less stable than ISRC as a recording identity.
- Should not be the only archive track identity because track IDs can differ across album versions for the same recording.

### UPC

Observed as `album.upc`.

Current use:

- Not stored by curator or validator.

Assessment:

- Strong release-level identifier when present and correct.
- Better than Deezer album ID for duplicate detection across duplicate Deezer entries and possibly across services.
- Not perfect: some releases lack UPC, have placeholder UPCs, have country-specific UPCs, or reuse UPCs across formats/variants.
- Should be captured as a high-value release identifier, not as the sole primary key.

### ISRC

Observed as `track.isrc` and supported by Deezer lookup endpoint `track/isrc:<ISRC>`.

Current use:

- Validator reads local FLAC `isrc` tags.
- Validator queries Deezer by ISRC and compares candidate album track counts.

Assessment:

- Strong recording identity.
- Excellent for duplicate recording detection across albums.
- Not sufficient for release identity because the same ISRC appears on many compilations, remasters, and reissues.
- Critical for track-level verification and archive repair.

### Label

Observed as `album.label`.

Current use:

- Not stored.

Assessment:

- Useful for NFOs, browsing, reporting, and duplicate review.
- Not an identifier unless paired with catalog number, which was not observed in the sampled Deezer payload.
- Should be stored as descriptive metadata, not primary identity.

### Release Date

Observed as `album.release_date` and `track.release_date`.

Current use:

- Recently repaired into `AlbumMetadata.year`.
- Artist files display year, but current data contains many older `unknown year` lines.

Assessment:

- Useful for sorting, NFOs, duplicate review, and lifecycle reporting.
- Not unique enough for identity.
- Important as part of a fuzzy duplicate key: artist + title + release date/year + track count + UPC when available.

### Contributor Identifiers

Observed in album and track `contributors`, with artist IDs, names, pictures, roles, and tracklists.

Current use:

- Not stored beyond the main artist name derived from album metadata.

Assessment:

- Useful for featured artists, compilations, collaborations, and artist graph intelligence.
- Important to distinguish album artist, track artist, featured artist, and contributor role.
- Not a release identity by itself.

## Stability and Suitability

| Identifier | Stability | Discovery | Archive identity | Duplicate detection | Verification |
| --- | --- | --- | --- | --- | --- |
| Deezer album ID | High within Deezer | Excellent | Good for Deezer-sourced archive entries | Medium | Excellent if stamped |
| Deezer artist ID | High within Deezer | Excellent | Weak | Medium for artist-name collisions | Weak |
| Deezer track ID | High within Deezer | Good | Medium | Medium | Good if captured |
| UPC | High when present | Medium | Excellent release key | Excellent | Good |
| ISRC | High when present | Good by lookup | Track-level, not album-level | Excellent for recordings | Excellent |
| Label | Descriptive | Weak | Weak | Weak-medium | Weak |
| Release date | Descriptive | Medium | Weak alone | Medium with title/artist/UPC | Medium |
| Contributor ID | High within Deezer | Good | Weak alone | Medium | Medium |
| File hash | Local/deterministic | None | Excellent archive file identity | Excellent exact-file duplicate detection | Excellent |
| Album manifest hash | Local/deterministic | None | Excellent archive manifest identity | Excellent exact-album duplicate detection | Excellent |

## Can Multiple Deezer Album IDs Represent the Same Release?

Yes. This should be assumed.

Likely cases:

- Regional duplicates.
- Explicit and clean versions.
- Reissued albums with identical or near-identical tracklists.
- Deluxe/anniversary/drumless/remaster editions that share UPC or title family.
- Catalog migrations where Deezer assigns a new album ID.
- Same real-world release appearing as both artist album and compilation-like entry.

Implication: Deezer album ID should remain the operational source identity, but future release identity must allow more than one Deezer album ID to map to one logical release cluster.

## Can UPC Be Used As a Release Identifier?

Yes, but not alone.

Recommended role:

- Use UPC as the strongest external release identifier when present.
- Pair with track count, title, main artist/contributors, release date, and track ISRC sequence for confidence.
- Allow multiple Deezer album IDs per UPC.
- Allow missing or suspect UPC.

Do not use UPC as the sole database primary key because it can be absent, malformed, duplicated, or reused across variants.

## Future STiGMA Album Identity Model

Recommended model:

```text
StigmaAlbumIdentity
  stigma_album_uid       local stable UUID or deterministic ID
  source_album_ids       Deezer album IDs and future provider IDs
  release_keys           UPC, label, release_date, record_type
  main_artist_ids        Deezer artist IDs
  contributor_ids        Deezer artist IDs with roles
  track_recording_keys   ordered ISRC list when available
  archive_keys           archive folder path, file hashes, manifest hash
  verification_keys      ALBUM_ID tag, validator run ID, validated_at
```

This separates provider identity, real-world release identity, and local archive identity.

## Recommended Identity Layers

### Discovery Identity

Purpose: identify what Deezer content to expand, queue, or fetch.

Recommended fields:

- Deezer artist ID.
- Deezer album ID.
- Deezer track ID for track-level lookups.
- Deezer URL.
- Search/discovery source and timestamp.

Primary rule: discovery identity is provider-local and can change shape over time.

### Release Identity

Purpose: identify the real-world album/release concept.

Recommended fields:

- UPC when present.
- Deezer album IDs as aliases.
- Title.
- Main artist/contributors.
- Release date.
- Record type.
- Track count.
- Ordered ISRC list.

Primary rule: release identity is a confidence model, not a single fragile ID.

### Archive Identity

Purpose: identify what exists on disk.

Recommended fields:

- Archive root and relative folder path.
- Folder name.
- Audio file paths.
- Per-file SHA-256.
- Album manifest hash from sorted relative paths + file hashes + sizes.
- Embedded ALBUM_ID tags.
- Embedded ISRC tags.

Primary rule: filesystem remains source of truth; database stores a rebuildable index.

### Verification Identity

Purpose: identify what has been validated and by which evidence.

Recommended fields:

- Validator run ID.
- Validated timestamp.
- Validator version.
- ALBUM_ID consistency result.
- FLAC integrity result.
- Completeness result.
- Deezer completeness result.
- Per-track hashes.
- Manifest hash.

Primary rule: validation is evidence about archive files at a point in time, not just a boolean.

## Recommendation

Keep Deezer album ID as the operational cursor for the current curator pipeline. Add UPC, ISRC, Deezer track IDs, and contributor IDs as soon as an archive index exists. Future duplicate detection should use layered confidence:

1. Exact archive duplicate: identical album manifest hash.
2. Same release: same UPC plus compatible track count/date/title.
3. Same recordings: high overlap of ordered ISRC list.
4. Provider duplicate: multiple Deezer album IDs with same UPC or same ordered ISRC sequence.
5. Fuzzy candidate: normalized artist/title/year/track count match.
