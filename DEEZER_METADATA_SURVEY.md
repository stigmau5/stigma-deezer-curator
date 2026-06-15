# Deezer Metadata Survey

Audit date: 2026-06-15

Scope: survey of Deezer metadata currently used or ignored by STiGMA Audio Division. This is research-only and does not propose implementation in this sprint.

## Current Curator Usage

Current active usage:

- `curator.expand.expand_artist_releases()` calls `https://api.deezer.com/artist/{artist_id}/albums`.
- `curator.metadata.get_album_metadata()` calls `https://api.deezer.com/album/{album_id}`.
- Current output uses album URL, record type, title, year, track count, and flags.

Ignored today:

- UPC.
- Full release date.
- Duration.
- Label.
- Genres.
- Cover art and `md5_image`.
- Album popularity/fans.
- Contributor IDs/roles.
- Track IDs.
- ISRCs.
- Track positions and disc numbers.
- Explicit content detail fields.
- Availability/readability.

## Observed Payloads

Observed from public Deezer API samples on 2026-06-15:

- Album: `https://api.deezer.com/album/302127`
- Artist: `https://api.deezer.com/artist/27`
- Artist albums: `https://api.deezer.com/artist/27/albums?limit=2`
- Artist top: `https://api.deezer.com/artist/27/top?limit=2`
- Related artists: `https://api.deezer.com/artist/27/related?limit=2`
- Track: `https://api.deezer.com/track/3135556`
- ISRC track lookup: `https://api.deezer.com/track/isrc:GBDUW0000059`

The official Deezer developer docs page redirects to login, so the concrete survey below is based on live public API responses plus current repository behavior.

## Album Metadata Available

Observed album keys:

- `id`
- `title`
- `upc`
- `link`
- `share`
- `cover`, `cover_small`, `cover_medium`, `cover_big`, `cover_xl`
- `md5_image`
- `genre_id`
- `genres.data[]`
- `label`
- `nb_tracks`
- `duration`
- `fans`
- `release_date`
- `record_type`
- `available`
- `tracklist`
- `explicit_lyrics`
- `explicit_content_lyrics`
- `explicit_content_cover`
- `contributors[]`
- `artist`
- `tracks`
- `type`

Representative shape:

```json
{
  "id": 302127,
  "title": "Discovery",
  "upc": "724384960650",
  "label": "Daft Life Ltd./ADA France",
  "nb_tracks": 14,
  "duration": 3662,
  "fans": 334693,
  "release_date": "2001-03-07",
  "record_type": "album",
  "available": true,
  "explicit_lyrics": false,
  "contributors": [
    {
      "id": 27,
      "name": "Daft Punk",
      "role": "Main"
    }
  ]
}
```

### Album Field Classification

| Field | Class | Archive value | NFO value | Reporting value | Intelligence value |
| --- | --- | --- | --- | --- | --- |
| `id` | Must Have | Provider source identity | Optional source ID | Dedupe by source | Lifecycle joins |
| `title` | Must Have | Human identity | Title line | Catalog reports | Fuzzy duplicate matching |
| `upc` | Must Have | Release identity | Optional catalog metadata | Duplicate reporting | Cross-provider matching |
| `release_date` | Must Have | Release chronology | Release date | Year/date reports | Completeness by era |
| `record_type` | Must Have | Album/EP/single buckets | Release type | Collection mix | Classification |
| `nb_tracks` | Must Have | Completeness expectation | Track count | Missing/incomplete reports | Validation comparison |
| `duration` | Nice To Have | Sanity check | Runtime | Duration reports | Duplicate confidence |
| `label` | Nice To Have | Catalog context | Label line | Label reports | Collection trends |
| `genres` | Nice To Have | Browsing context | Genre line | Genre reports | Recommendation/intelligence |
| `contributors` | Must Have | Artist identity graph | Credits | Collaborator reports | Artist graph |
| `artist` | Must Have | Main display artist | Artist line | Artist reports | Grouping |
| `explicit_lyrics` | Nice To Have | Variant signal | Content flag | Explicit/clean reports | Duplicate variant detection |
| `explicit_content_*` | Future Use | Detail flag | Usually omit | Content detail reports | Variant detection |
| `cover_*` | Nice To Have | Artwork retrieval | NFO/artwork links | Missing artwork reports | Visual archive completeness |
| `md5_image` | Future Use | Artwork identity | Omit | Artwork duplicate reports | Cover dedupe |
| `fans` | Future Use | None for correctness | Omit | Popularity reports | Prioritization |
| `available` | Future Use | Availability snapshot | Omit | Dead content reports | Reacquisition planning |
| `tracklist` | Must Have | Track fetch URL | Omit | Debugging | Completeness fetch |
| `link`/`share` | Nice To Have | Source URL | Source URL | Link reports | Traceability |

## Artist Metadata Available

Observed artist keys:

- `id`
- `name`
- `link`
- `share`
- `picture`, `picture_small`, `picture_medium`, `picture_big`, `picture_xl`
- `nb_album`
- `nb_fan`
- `radio`
- `tracklist`
- `type`

Related artist endpoint returned artist objects with the same general shape.

Top tracks endpoint returned track objects with contributor and album context.

Representative shape:

```json
{
  "id": 27,
  "name": "Daft Punk",
  "nb_album": 38,
  "nb_fan": 5163259,
  "radio": true,
  "tracklist": "https://api.deezer.com/artist/27/top?limit=50",
  "type": "artist"
}
```

### Artist Field Classification

| Field | Class | Archive value | NFO value | Reporting value | Intelligence value |
| --- | --- | --- | --- | --- | --- |
| `id` | Must Have | Stable artist identity | Optional source ID | Artist dedupe | Artist graph |
| `name` | Must Have | Display/grouping | Artist name | Artist reports | Search/fuzzy matching |
| `nb_album` | Nice To Have | None directly | Omit | Discovery progress | Missing-catalog hints |
| `nb_fan` | Future Use | None | Omit | Popularity reports | Prioritization |
| `picture_*` | Nice To Have | Artist artwork | Optional | Missing image reports | UI enrichment |
| `related` endpoint | Future Use | None | Omit | Discovery reports | Recommendation graph |
| `top` endpoint | Future Use | None | Omit | Popular tracks | Prioritized sampling |
| `tracklist` | Future Use | Fetch pointer | Omit | Debugging | Discovery |
| `link`/`share` | Nice To Have | Source trace | Source URL | Link reports | Traceability |

## Track Metadata Available

Observed track keys:

- `id`
- `readable`
- `title`
- `title_short`
- `title_version`
- `isrc`
- `link`
- `share`
- `duration`
- `track_position`
- `disk_number`
- `rank`
- `release_date`
- `explicit_lyrics`
- `explicit_content_lyrics`
- `explicit_content_cover`
- `preview`
- `bpm`
- `gain`
- `available_countries`
- `contributors`
- `artist`
- `album`
- `md5_image`
- `track_token`
- `type`

Representative shape:

```json
{
  "id": 3135556,
  "title": "Harder, Better, Faster, Stronger",
  "isrc": "GBDUW0000059",
  "duration": 226,
  "track_position": 4,
  "disk_number": 1,
  "rank": 814839,
  "release_date": "2001-03-12",
  "explicit_lyrics": false,
  "contributors": [
    {
      "id": 27,
      "name": "Daft Punk",
      "role": "Main"
    }
  ]
}
```

### Track Field Classification

| Field | Class | Archive value | NFO value | Reporting value | Intelligence value |
| --- | --- | --- | --- | --- | --- |
| `id` | Must Have | Deezer track identity | Optional | Track source reports | Provider matching |
| `isrc` | Must Have | Recording identity | Optional | Duplicate recording reports | Cross-release matching |
| `title` | Must Have | Track display | Tracklist | Track reports | Fuzzy matching |
| `track_position` | Must Have | Ordering | Track number | Completeness reports | Manifest building |
| `disk_number` | Must Have | Multi-disc ordering | Disc number | Completeness reports | Manifest building |
| `duration` | Must Have | Sanity check | Runtime | Duration mismatch | Duplicate confidence |
| `contributors` | Nice To Have | Track artist graph | Credits | Featured artist reports | Contributor intelligence |
| `artist` | Must Have | Primary track artist | Track artist | Artist reports | Grouping |
| `album` | Must Have | Parent album context | Optional | Join reports | Identity linkage |
| `explicit_lyrics` | Nice To Have | Variant signal | Content flag | Explicit reports | Variant detection |
| `preview` | Future Use | None for archive | Omit | Debugging | Manual review |
| `rank` | Future Use | None | Omit | Popularity reports | Prioritization |
| `available_countries` | Future Use | Availability snapshot | Omit | Availability reports | Reacquisition planning |
| `bpm`/`gain` | Future Use | Audio metadata hint | Optional | Audio reports | Playlist intelligence |
| `readable` | Future Use | Availability signal | Omit | Dead track reports | Repair planning |

## Fields STiGMA Should Capture First

Minimum future capture:

- Album: `id`, `title`, `upc`, `release_date`, `record_type`, `nb_tracks`, `duration`, `label`, `genres`, `contributors`, `artist`, `explicit_lyrics`, `cover_xl`, `md5_image`.
- Track: `id`, `title`, `isrc`, `duration`, `track_position`, `disk_number`, `contributors`, `artist`, `explicit_lyrics`.
- Artist: `id`, `name`, `picture_xl`.

Reasoning:

- These fields support identity, duplicate detection, validation, NFO generation, and archive reporting.
- Popularity and availability fields are useful later but not needed to stabilize archive truth.

## Current Gaps

- Artist files are URL-first text, not structured metadata.
- Existing `validated_albums.json` stores only album ID, folder, source, tracks, and timestamp.
- Existing confirmed/attempted/shipped state does not store UPC, ISRC, contributor IDs, or tracklist.
- Validator already reads ISRCs locally but does not emit them to `validated_albums.json`.

## Recommendation

Future metadata ingestion should be explicit and cached:

1. Discovery uses artist album lists for candidate release IDs.
2. Album detail fetch captures release-level metadata and tracklist pointer.
3. Track detail/album tracks capture track-level IDs, ISRCs, order, durations, and contributors.
4. Archive index stores the latest observed provider metadata as rebuildable cache, not source of truth.
5. Validator output links local files to provider metadata through ALBUM_ID, ISRC, hashes, and manifest hash.
