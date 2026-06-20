# Identity Join Audit

Generated: 2026-06-20

Sprint AZ is a read-only audit. No lifecycle, identity, archive, validation, or AlbumTruth logic was changed.

## Executive Summary

Lifecycle state detection reports 31 conflicts. Every conflict is the same class:

`validated_without_album_folder`

The albums are validated by Deezer Album ID through `data/validated_albums.json`, and the Identity Registry marks them `HIGH` confidence because the lifecycle album ID exists in the validated index. That high confidence only proves the discovery-to-validation join.

It does not prove an archive-folder join.

For all 31 conflicts, the identity record contains a release-folder name such as:

`Guts-Beach Diggin', Vol. 4-2016-FLAC-STiGMA`

The current archive-path projection treats that folder as if it lived directly below the main archive root:

`<archive_root>/Guts-Beach Diggin', Vol. 4-2016-FLAC-STiGMA`

That path does not exist. The physical archive registry uses formal archive roots such as artist/category/release folders, not direct release folders at archive root. No exact normalized `archive_registry.json` album-root match was found for any of the 31 conflict folders.

The root issue is identity layering:

- Deezer Album ID joins discovery and validation.
- Archive Registry joins physical archive folders.
- The current validator evidence does not carry a durable final archive path.
- Folder-name evidence is being treated as stronger than it really is.

## Sources Reviewed

- `data/artists/*.txt`
- `data/lifecycle_registry.json`
- `data/identity_registry.json`
- `data/archive_registry.json`
- `data/validated_albums.json`
- `reports/lifecycle_state_report.md`
- `audio_division/lifecycle_state.py`
- `audio_division/library.py`
- `audio_division/album_truth.py`

## Evidence Summary

| Source | Key Currently Used | What It Proves | Join Risk |
| --- | --- | --- | --- |
| Curator artist files | Deezer Album ID | Album was discovered from Deezer | Low for discovery |
| Lifecycle Registry | Deezer Album ID | Album state across discovered, attempted, shipped, validated, confirmed | Low for curator state |
| Validated Albums | Deezer Album ID | Validator accepted a release associated with that Deezer ID | Low for validation state |
| Identity Registry | Deezer Album ID plus folder string | Discovery-to-validation join and weak archive hint | Medium if folder is treated as archive path |
| Archive Registry | Physical archive path | Album folder exists in archive | Low for filesystem truth |
| AlbumTruth | Archive path plus artifacts plus metadata | Current album status when archive path is known | Depends on upstream join |

## Conflict Explanation

The lifecycle engine sees validated evidence for each conflicted Deezer Album ID. It then tries to resolve archive truth through identity/archive evidence. The available identity evidence is only a release-folder name from validation records, not a formal archive path. Because that projected folder does not exist under the archive root and no matching archive-registry entity exists, the lifecycle state remains `VALIDATED` rather than `ARCHIVED`, and the conflict is reported.

Two conflicts also show artist mismatch between lifecycle identity and validated folder identity:

- Album ID `477119535`: lifecycle artist `Lehto`; validated folder artist `Renegades Of Jazz`
- Album ID `1341248`: lifecycle artist `Sub Focus`; validated folder artist `Chase & Status`

Those may be featured-artist, remix, compilation, or Deezer attribution differences. They should not be auto-joined without stronger evidence.

## Conflict Detail

| Album ID | Artist | Title | Validation Evidence | Archive Evidence | Identity Evidence | Reason for Mismatch |
| --- | --- | --- | --- | --- | --- | --- |
| `265518642` | Backyard Babies | Diesel & Power | validated_index; `2026-01-13T15:13:37.114354`; tracks `14`; folder `Backyard Babies-Diesel & Power-2012-FLAC-STiGMA` | projected `/media/stigma/fa8a4ea5-d1da-4c46-b697-900ced38b5ca/archive/Backyard Babies-Diesel & Power-2012-FLAC-STiGMA` exists `no`; archive_registry exact match `no` | HIGH; lifecycle_album_id, validated_index, validated_index_album_id_match; folder `Backyard Babies-Diesel & Power-2012-FLAC-STiGMA` | Validated index gives a release folder name, but no formal archive_registry album root has the same normalized folder; projected path under archive root does not exist. |
| `154960182` | Coca carola | Tigger & Ber | validated_index; `2026-01-13T15:22:32.222523`; tracks `13`; folder `Coca carola-Tigger & Ber-1992-FLAC-STiGMA` | projected `/media/stigma/fa8a4ea5-d1da-4c46-b697-900ced38b5ca/archive/Coca carola-Tigger & Ber-1992-FLAC-STiGMA` exists `no`; archive_registry exact match `no` | HIGH; lifecycle_album_id, validated_index, validated_index_album_id_match; folder `Coca carola-Tigger & Ber-1992-FLAC-STiGMA` | Validated index gives a release folder name, but no formal archive_registry album root has the same normalized folder; projected path under archive root does not exist. |
| `134760902` | Galenskaparna & After Shave | Grisen i säcken | validated_index; `2026-01-13T15:13:08.336464`; tracks `17`; folder `Galenskaparna & After Shave-Grisen i säcken-1992-FLAC-STiGMA` | projected `/media/stigma/fa8a4ea5-d1da-4c46-b697-900ced38b5ca/archive/Galenskaparna & After Shave-Grisen i säcken-1992-FLAC-STiGMA` exists `no`; archive_registry exact match `no` | HIGH; lifecycle_album_id, validated_index, validated_index_album_id_match; folder `Galenskaparna & After Shave-Grisen i säcken-1992-FLAC-STiGMA` | Validated index gives a release folder name, but no formal archive_registry album root has the same normalized folder; projected path under archive root does not exist. |
| `134809492` | Galenskaparna & After Shave | Hajen som visste för mycket | validated_index; `2026-01-13T15:20:10.343822`; tracks `11`; folder `Galenskaparna & After Shave-Hajen som visste för mycket-2012-FLAC-STiGMA` | projected `/media/stigma/fa8a4ea5-d1da-4c46-b697-900ced38b5ca/archive/Galenskaparna & After Shave-Hajen som visste för mycket-2012-FLAC-STiGMA` exists `no`; archive_registry exact match `no` | HIGH; lifecycle_album_id, validated_index, validated_index_album_id_match; folder `Galenskaparna & After Shave-Hajen som visste för mycket-2012-FLAC-STiGMA` | Validated index gives a release folder name, but no formal archive_registry album root has the same normalized folder; projected path under archive root does not exist. |
| `134757192` | Galenskaparna & After Shave | Kasinofeber | validated_index; `2026-01-13T15:23:08.313235`; tracks `12`; folder `Galenskaparna & After Shave-Kasinofeber-2002-FLAC-STiGMA` | projected `/media/stigma/fa8a4ea5-d1da-4c46-b697-900ced38b5ca/archive/Galenskaparna & After Shave-Kasinofeber-2002-FLAC-STiGMA` exists `no`; archive_registry exact match `no` | HIGH; lifecycle_album_id, validated_index, validated_index_album_id_match; folder `Galenskaparna & After Shave-Kasinofeber-2002-FLAC-STiGMA` | Validated index gives a release folder name, but no formal archive_registry album root has the same normalized folder; projected path under archive root does not exist. |
| `134809612` | Galenskaparna & After Shave | Macken (Låtarna ur TV-serien) | validated_index; `2026-01-13T15:13:31.865666`; tracks `24`; folder `Galenskaparna & After Shave-Macken (Låtarna ur TV-serien)-2012-FLAC-STiGMA` | projected `/media/stigma/fa8a4ea5-d1da-4c46-b697-900ced38b5ca/archive/Galenskaparna & After Shave-Macken (Låtarna ur TV-serien)-2012-FLAC-STiGMA` exists `no`; archive_registry exact match `no` | HIGH; lifecycle_album_id, validated_index, validated_index_album_id_match; folder `Galenskaparna & After Shave-Macken (Låtarna ur TV-serien)-2012-FLAC-STiGMA` | Validated index gives a release folder name, but no formal archive_registry album root has the same normalized folder; projected path under archive root does not exist. |
| `129528442` | Galenskaparna & After Shave | MACKEN - TV-serien på scen | validated_index; `2026-01-13T15:23:14.640519`; tracks `14`; folder `Galenskaparna & After Shave-MACKEN - TV-serien på scen-2017-FLAC-STiGMA` | projected `/media/stigma/fa8a4ea5-d1da-4c46-b697-900ced38b5ca/archive/Galenskaparna & After Shave-MACKEN - TV-serien på scen-2017-FLAC-STiGMA` exists `no`; archive_registry exact match `no` | HIGH; lifecycle_album_id, validated_index, validated_index_album_id_match; folder `Galenskaparna & After Shave-MACKEN - TV-serien på scen-2017-FLAC-STiGMA` | Validated index gives a release folder name, but no formal archive_registry album root has the same normalized folder; projected path under archive root does not exist. |
| `134764102` | Galenskaparna & After Shave | Monopol | validated_index; `2026-01-13T15:22:11.144052`; tracks `10`; folder `Galenskaparna & After Shave-Monopol-1996-FLAC-STiGMA` | projected `/media/stigma/fa8a4ea5-d1da-4c46-b697-900ced38b5ca/archive/Galenskaparna & After Shave-Monopol-1996-FLAC-STiGMA` exists `no`; archive_registry exact match `no` | HIGH; lifecycle_album_id, validated_index, validated_index_album_id_match; folder `Galenskaparna & After Shave-Monopol-1996-FLAC-STiGMA` | Validated index gives a release folder name, but no formal archive_registry album root has the same normalized folder; projected path under archive root does not exist. |
| `129508582` | Galenskaparna & After Shave | Spargrisarna kan rädda världen | validated_index; `2026-01-13T15:23:51.091288`; tracks `15`; folder `Galenskaparna & After Shave-Spargrisarna kan rädda världen-2018-FLAC-STiGMA` | projected `/media/stigma/fa8a4ea5-d1da-4c46-b697-900ced38b5ca/archive/Galenskaparna & After Shave-Spargrisarna kan rädda världen-2018-FLAC-STiGMA` exists `no`; archive_registry exact match `no` | HIGH; lifecycle_album_id, validated_index, validated_index_album_id_match; folder `Galenskaparna & After Shave-Spargrisarna kan rädda världen-2018-FLAC-STiGMA` | Validated index gives a release folder name, but no formal archive_registry album root has the same normalized folder; projected path under archive root does not exist. |
| `134809522` | Galenskaparna & After Shave | Stinsen Brinner | validated_index; `2026-01-13T15:25:35.741659`; tracks `12`; folder `Galenskaparna & After Shave-Stinsen Brinner-2012-FLAC-STiGMA` | projected `/media/stigma/fa8a4ea5-d1da-4c46-b697-900ced38b5ca/archive/Galenskaparna & After Shave-Stinsen Brinner-2012-FLAC-STiGMA` exists `no`; archive_registry exact match `no` | HIGH; lifecycle_album_id, validated_index, validated_index_album_id_match; folder `Galenskaparna & After Shave-Stinsen Brinner-2012-FLAC-STiGMA` | Validated index gives a release folder name, but no formal archive_registry album root has the same normalized folder; projected path under archive root does not exist. |
| `134773562` | Galenskaparna & After Shave | Träsmak | validated_index; `2026-01-13T15:13:29.256717`; tracks `19`; folder `Galenskaparna & After Shave-Träsmak-2012-FLAC-STiGMA` | projected `/media/stigma/fa8a4ea5-d1da-4c46-b697-900ced38b5ca/archive/Galenskaparna & After Shave-Träsmak-2012-FLAC-STiGMA` exists `no`; archive_registry exact match `no` | HIGH; lifecycle_album_id, validated_index, validated_index_album_id_match; folder `Galenskaparna & After Shave-Träsmak-2012-FLAC-STiGMA` | Validated index gives a release folder name, but no formal archive_registry album root has the same normalized folder; projected path under archive root does not exist. |
| `134812992` | Galenskaparna & After Shave | Åke från Åstol | validated_index; `2026-01-13T15:29:58.300570`; tracks `8`; folder `Galenskaparna & After Shave-Åke från Åstol-1998-FLAC-STiGMA` | projected `/media/stigma/fa8a4ea5-d1da-4c46-b697-900ced38b5ca/archive/Galenskaparna & After Shave-Åke från Åstol-1998-FLAC-STiGMA` exists `no`; archive_registry exact match `no` | HIGH; lifecycle_album_id, validated_index, validated_index_album_id_match; folder `Galenskaparna & After Shave-Åke från Åstol-1998-FLAC-STiGMA` | Validated index gives a release folder name, but no formal archive_registry album root has the same normalized folder; projected path under archive root does not exist. |
| `704387011` | Guts | Beach Diggin', Vol. 3 | validated_index; `2026-01-08T02:29:23.129810`; tracks `14`; folder `Guts-Beach Diggin', Vol. 3-2015-FLAC-STiGMA` | projected `/media/stigma/fa8a4ea5-d1da-4c46-b697-900ced38b5ca/archive/Guts-Beach Diggin', Vol. 3-2015-FLAC-STiGMA` exists `no`; archive_registry exact match `no` | HIGH; lifecycle_album_id, validated_index, validated_index_album_id_match; folder `Guts-Beach Diggin', Vol. 3-2015-FLAC-STiGMA` | Validated index gives a release folder name, but no formal archive_registry album root has the same normalized folder; projected path under archive root does not exist. |
| `317793567` | Guts | Beach Diggin', Vol. 4 | validated_index; `2026-01-08T02:28:03.856742`; tracks `13`; folder `Guts-Beach Diggin', Vol. 4-2016-FLAC-STiGMA` | projected `/media/stigma/fa8a4ea5-d1da-4c46-b697-900ced38b5ca/archive/Guts-Beach Diggin', Vol. 4-2016-FLAC-STiGMA` exists `no`; archive_registry exact match `no` | HIGH; lifecycle_album_id, validated_index, validated_index_album_id_match; folder `Guts-Beach Diggin', Vol. 4-2016-FLAC-STiGMA` | Validated index gives a release folder name, but no formal archive_registry album root has the same normalized folder; projected path under archive root does not exist. |
| `9537198` | Guts | Fines bouches, Vol. 1 | validated_index; `2026-01-08T02:28:06.418441`; tracks `8`; folder `Guts-Fines bouches, Vol. 1-2015-FLAC-STiGMA` | projected `/media/stigma/fa8a4ea5-d1da-4c46-b697-900ced38b5ca/archive/Guts-Fines bouches, Vol. 1-2015-FLAC-STiGMA` exists `no`; archive_registry exact match `no` | HIGH; lifecycle_album_id, validated_index, validated_index_album_id_match; folder `Guts-Fines bouches, Vol. 1-2015-FLAC-STiGMA` | Validated index gives a release folder name, but no formal archive_registry album root has the same normalized folder; projected path under archive root does not exist. |
| `459560955` | Guts | Straight from the Decks, Vol. 3 (Guts Finest Selection from His Famous DJ Sets) | validated_index; `2026-01-08T02:30:05.640663`; tracks `16`; folder `Guts-Straight from the Decks, Vol. 3 (Guts Finest Selection from His Famous DJ Sets)-2023-FLAC-STiGMA` | projected `/media/stigma/fa8a4ea5-d1da-4c46-b697-900ced38b5ca/archive/Guts-Straight from the Decks, Vol. 3 (Guts Finest Selection from His Famous DJ Sets)-2023-FLAC-STiGMA` exists `no`; archive_registry exact match `no` | HIGH; lifecycle_album_id, validated_index, validated_index_album_id_match; folder `Guts-Straight from the Decks, Vol. 3 (Guts Finest Selection from His Famous DJ Sets)-2023-FLAC-STiGMA` | Validated index gives a release folder name, but no formal archive_registry album root has the same normalized folder; projected path under archive root does not exist. |
| `657757471` | Guts | Straight from the Decks, Vol. 4 (Guts Finest Selection from His Famous DJ Sets) | validated_index; `2026-01-08T02:30:29.011690`; tracks `15`; folder `Guts-Straight from the Decks, Vol. 4 (Guts Finest Selection from His Famous DJ Sets)-2024-FLAC-STiGMA` | projected `/media/stigma/fa8a4ea5-d1da-4c46-b697-900ced38b5ca/archive/Guts-Straight from the Decks, Vol. 4 (Guts Finest Selection from His Famous DJ Sets)-2024-FLAC-STiGMA` exists `no`; archive_registry exact match `no` | HIGH; lifecycle_album_id, validated_index, validated_index_album_id_match; folder `Guts-Straight from the Decks, Vol. 4 (Guts Finest Selection from His Famous DJ Sets)-2024-FLAC-STiGMA` | Validated index gives a release folder name, but no formal archive_registry album root has the same normalized folder; projected path under archive root does not exist. |
| `444973115` | Khruangbin | Live at Radio City Music Hall | validated_index; `2026-01-13T15:16:14.389868`; tracks `7`; folder `Khruangbin-Live at Radio City Music Hall-2023-FLAC-STiGMA` | projected `/media/stigma/fa8a4ea5-d1da-4c46-b697-900ced38b5ca/archive/Khruangbin-Live at Radio City Music Hall-2023-FLAC-STiGMA` exists `no`; archive_registry exact match `no` | HIGH; lifecycle_album_id, validated_index, validated_index_album_id_match; folder `Khruangbin-Live at Radio City Music Hall-2023-FLAC-STiGMA` | Validated index gives a release folder name, but no formal archive_registry album root has the same normalized folder; projected path under archive root does not exist. |
| `452997095` | Khruangbin | Live at RBC Echo Beach | validated_index; `2026-01-13T15:17:44.859586`; tracks `9`; folder `Khruangbin-Live at RBC Echo Beach-2023-FLAC-STiGMA` | projected `/media/stigma/fa8a4ea5-d1da-4c46-b697-900ced38b5ca/archive/Khruangbin-Live at RBC Echo Beach-2023-FLAC-STiGMA` exists `no`; archive_registry exact match `no` | HIGH; lifecycle_album_id, validated_index, validated_index_album_id_match; folder `Khruangbin-Live at RBC Echo Beach-2023-FLAC-STiGMA` | Validated index gives a release folder name, but no formal archive_registry album root has the same normalized folder; projected path under archive root does not exist. |
| `423497267` | Khruangbin | Live at Stubb's | validated_index; `2026-01-13T15:24:29.303395`; tracks `9`; folder `Khruangbin-Live at Stubb's-2023-FLAC-STiGMA` | projected `/media/stigma/fa8a4ea5-d1da-4c46-b697-900ced38b5ca/archive/Khruangbin-Live at Stubb's-2023-FLAC-STiGMA` exists `no`; archive_registry exact match `no` | HIGH; lifecycle_album_id, validated_index, validated_index_album_id_match; folder `Khruangbin-Live at Stubb's-2023-FLAC-STiGMA` | Validated index gives a release folder name, but no formal archive_registry album root has the same normalized folder; projected path under archive root does not exist. |
| `461612575` | Khruangbin | Live at The Fillmore Miami | validated_index; `2026-01-13T15:20:26.490500`; tracks `9`; folder `Khruangbin-Live at The Fillmore Miami-2023-FLAC-STiGMA` | projected `/media/stigma/fa8a4ea5-d1da-4c46-b697-900ced38b5ca/archive/Khruangbin-Live at The Fillmore Miami-2023-FLAC-STiGMA` exists `no`; archive_registry exact match `no` | HIGH; lifecycle_album_id, validated_index, validated_index_album_id_match; folder `Khruangbin-Live at The Fillmore Miami-2023-FLAC-STiGMA` | Validated index gives a release folder name, but no formal archive_registry album root has the same normalized folder; projected path under archive root does not exist. |
| `42283171` | Kill Emil | Lights & Shadows | validated_index; `2026-01-08T02:29:07.392283`; tracks `14`; folder `Kill Emil-Lights & Shadows-2017-FLAC-STiGMA` | projected `/media/stigma/fa8a4ea5-d1da-4c46-b697-900ced38b5ca/archive/Kill Emil-Lights & Shadows-2017-FLAC-STiGMA` exists `no`; archive_registry exact match `no` | HIGH; lifecycle_album_id, validated_index, validated_index_album_id_match; folder `Kill Emil-Lights & Shadows-2017-FLAC-STiGMA` | Validated index gives a release folder name, but no formal archive_registry album root has the same normalized folder; projected path under archive root does not exist. |
| `477119535` | Lehto | Moo Juice (Benji Boko & BOY COM Remixes) | validated_index; `2026-01-08T02:30:45.025298`; tracks `2`; folder `Renegades Of Jazz-Moo Juice (Benji Boko & BOY COM Remixes)-2011-FLAC-STiGMA` | projected `/media/stigma/fa8a4ea5-d1da-4c46-b697-900ced38b5ca/archive/Renegades Of Jazz-Moo Juice (Benji Boko & BOY COM Remixes)-2011-FLAC-STiGMA` exists `no`; archive_registry exact match `no` | HIGH; lifecycle_album_id, validated_index, validated_index_album_id_match; folder `Renegades Of Jazz-Moo Juice (Benji Boko & BOY COM Remixes)-2011-FLAC-STiGMA` | Validated index gives a release folder name, but no formal archive_registry album root has the same normalized folder; projected path under archive root does not exist. Folder artist `Renegades Of Jazz` differs from lifecycle artist `Lehto`. |
| `678442161` | Mattafix | Rhythm & Hymns | validated_index; `2026-01-13T15:32:05.963786`; tracks `11`; folder `Mattafix-Rhythm & Hymns-2008-FLAC-STiGMA` | projected `/media/stigma/fa8a4ea5-d1da-4c46-b697-900ced38b5ca/archive/Mattafix-Rhythm & Hymns-2008-FLAC-STiGMA` exists `no`; archive_registry exact match `no` | HIGH; lifecycle_album_id, validated_index, validated_index_album_id_match; folder `Mattafix-Rhythm & Hymns-2008-FLAC-STiGMA` | Validated index gives a release folder name, but no formal archive_registry album root has the same normalized folder; projected path under archive root does not exist. |
| `342106957` | ommood | Me & Mon Ami | validated_index; `2026-01-08T02:29:38.305080`; tracks `3`; folder `ommood-Me & Mon Ami-2022-FLAC-STiGMA` | projected `/media/stigma/fa8a4ea5-d1da-4c46-b697-900ced38b5ca/archive/ommood-Me & Mon Ami-2022-FLAC-STiGMA` exists `no`; archive_registry exact match `no` | HIGH; lifecycle_album_id, validated_index, validated_index_album_id_match; folder `ommood-Me & Mon Ami-2022-FLAC-STiGMA` | Validated index gives a release folder name, but no formal archive_registry album root has the same normalized folder; projected path under archive root does not exist. |
| `496599671` | PaceWon & Mr. Green | The Only Color That Matters is Green | validated_index; `2026-01-13T15:33:44.851651`; tracks `12`; folder `PaceWon & Mr. Green-The Only Color That Matters is Green-2008-FLAC-STiGMA` | projected `/media/stigma/fa8a4ea5-d1da-4c46-b697-900ced38b5ca/archive/PaceWon & Mr. Green-The Only Color That Matters is Green-2008-FLAC-STiGMA` exists `no`; archive_registry exact match `no` | HIGH; lifecycle_album_id, validated_index, validated_index_album_id_match; folder `PaceWon & Mr. Green-The Only Color That Matters is Green-2008-FLAC-STiGMA` | Validated index gives a release folder name, but no formal archive_registry album root has the same normalized folder; projected path under archive root does not exist. |
| `503695371` | PaceWon & Mr. Green | The Only Number That Matters Is Won | validated_index; `2026-01-13T15:29:55.207887`; tracks `14`; folder `PaceWon & Mr. Green-The Only Number That Matters Is Won-2012-FLAC-STiGMA` | projected `/media/stigma/fa8a4ea5-d1da-4c46-b697-900ced38b5ca/archive/PaceWon & Mr. Green-The Only Number That Matters Is Won-2012-FLAC-STiGMA` exists `no`; archive_registry exact match `no` | HIGH; lifecycle_album_id, validated_index, validated_index_album_id_match; folder `PaceWon & Mr. Green-The Only Number That Matters Is Won-2012-FLAC-STiGMA` | Validated index gives a release folder name, but no formal archive_registry album root has the same normalized folder; projected path under archive root does not exist. |
| `484354065` | PaceWon & Mr. Green | The Only Number That Matters Is Won 1.5 | validated_index; `2026-01-13T15:34:32.700899`; tracks `7`; folder `PaceWon & Mr. Green-The Only Number That Matters Is Won 1.5-2012-FLAC-STiGMA` | projected `/media/stigma/fa8a4ea5-d1da-4c46-b697-900ced38b5ca/archive/PaceWon & Mr. Green-The Only Number That Matters Is Won 1.5-2012-FLAC-STiGMA` exists `no`; archive_registry exact match `no` | HIGH; lifecycle_album_id, validated_index, validated_index_album_id_match; folder `PaceWon & Mr. Green-The Only Number That Matters Is Won 1.5-2012-FLAC-STiGMA` | Validated index gives a release folder name, but no formal archive_registry album root has the same normalized folder; projected path under archive root does not exist. |
| `459629975` | Papa Roach | Time For Annihilation: On the Record & On the Road | validated_index; `2026-01-13T19:12:28.879585`; tracks `14`; folder `Papa Roach-Time For Annihilation On the Record & On the Road-2010-FLAC-STiGMA` | projected `/media/stigma/fa8a4ea5-d1da-4c46-b697-900ced38b5ca/archive/Papa Roach-Time For Annihilation On the Record & On the Road-2010-FLAC-STiGMA` exists `no`; archive_registry exact match `no` | HIGH; lifecycle_album_id, validated_index, validated_index_album_id_match; folder `Papa Roach-Time For Annihilation On the Record & On the Road-2010-FLAC-STiGMA` | Validated index gives a release folder name, but no formal archive_registry album root has the same normalized folder; projected path under archive root does not exist. |
| `9665570` | Protassov | Steam & Oil EP | validated_index; `2026-01-08T02:28:42.633488`; tracks `5`; folder `Protassov-Steam & Oil EP-2015-FLAC-STiGMA` | projected `/media/stigma/fa8a4ea5-d1da-4c46-b697-900ced38b5ca/archive/Protassov-Steam & Oil EP-2015-FLAC-STiGMA` exists `no`; archive_registry exact match `no` | HIGH; lifecycle_album_id, validated_index, validated_index_album_id_match; folder `Protassov-Steam & Oil EP-2015-FLAC-STiGMA` | Validated index gives a release folder name, but no formal archive_registry album root has the same normalized folder; projected path under archive root does not exist. |
| `1341248` | Sub Focus | Flashing Lights | validated_index; `2026-01-13T15:18:44.999904`; tracks `4`; folder `Chase & Status-Flashing Lights-2011-FLAC-STiGMA` | projected `/media/stigma/fa8a4ea5-d1da-4c46-b697-900ced38b5ca/archive/Chase & Status-Flashing Lights-2011-FLAC-STiGMA` exists `no`; archive_registry exact match `no` | HIGH; lifecycle_album_id, validated_index, validated_index_album_id_match; folder `Chase & Status-Flashing Lights-2011-FLAC-STiGMA` | Validated index gives a release folder name, but no formal archive_registry album root has the same normalized folder; projected path under archive root does not exist. Folder artist `Chase & Status` differs from lifecycle artist `Sub Focus`. |

## What Key Should Join Discovery, Validation, Processing, and Archive?

No single current key safely joins every layer.

Recommended join model:

| Layer | Primary Key | Secondary Evidence |
| --- | --- | --- |
| Discovery | Deezer Album ID | Deezer artist ID, title, release date, UPC |
| Validation | Deezer Album ID when present | validated folder, validation timestamp, track count, hash evidence |
| Processing | Processing manifest ID | Deezer Album ID, source folder, output folder, generated artifacts |
| Archive | Archive path | manifest hash, NFO/SFV/playlist/artwork, validation marker |

The practical bridge should be:

1. Use Deezer Album ID as the operational key for discovery, curator state, and validation state.
2. Use physical archive path as the authoritative key for archive presence.
3. Use folder-name matching only as candidate evidence unless the path exists or exactly matches an archive-registry album root.
4. Add a future processing manifest that records both Deezer Album ID and final archive path at processing time.

The durable future join should be a multi-layer identity:

```text
Discovery Identity: Deezer Album ID
Release Identity: UPC plus ordered ISRC list when available
Processing Identity: source folder plus generated manifest
Archive Identity: final archive path plus manifest hash
Verification Identity: validation marker plus hashes
```

## Recommended Smallest Future Fix

No fix was implemented in this audit.

The smallest safe implementation should:

1. Split confidence into separate meanings:
   - `validation_confidence`
   - `archive_confidence`
2. Stop treating validator folder names as physical archive paths unless the path exists.
3. Resolve archive joins through `archive_registry.json` first.
4. Downgrade unmatched folder-only evidence to `UNKNOWN` or `CANDIDATE`.
5. Add a report of candidate archive matches by normalized artist, title, year, and track count for manual review.

The more durable future fix is for Audio Division processing to emit a small manifest with:

- Deezer Album ID
- source folder
- final archive path
- generated artifact paths
- validation marker path
- track count
- optional UPC/ISRC/hash evidence

That manifest would close the identity gap without making SQLite or folder naming the source of truth.
