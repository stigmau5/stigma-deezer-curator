# Lifecycle State Report

Lifecycle state is derived from existing state files and filesystem evidence. No workflow actions are executed.

## State Counts

- Albums evaluated: `8459`
- Unknown albums: `0`
- Albums with conflicting evidence: `31`

| State | Albums |
| --- | ---: |
| DISCOVERED | 5428 |
| DOWNLOADED | 0 |
| VALIDATED | 31 |
| READY_FOR_PROCESSING | 0 |
| ARCHIVED | 3000 |
| UNKNOWN | 0 |

## Evidence Counts

| Evidence | Albums |
| --- | ---: |
| album_truth | 31 |
| archive_filesystem | 3000 |
| curator_state | 6976 |
| validator_evidence | 31 |

## Impossible Or Conflicting States

| Conflict | Albums |
| --- | ---: |
| validated_without_album_folder | 31 |

## Conflict Examples

| State | Artist | Album | Album ID | Path | Conflicts | Reason |
| --- | --- | --- | --- | --- | --- | --- |
| VALIDATED | Backyard Babies | Diesel & Power | `265518642` | `/media/stigma/fa8a4ea5-d1da-4c46-b697-900ced38b5ca/archive/Backyard Babies-Diesel & Power-2012-FLAC-STiGMA` | validated_without_album_folder | Validator evidence exists. |
| VALIDATED | Coca carola | Tigger & Ber | `154960182` | `/media/stigma/fa8a4ea5-d1da-4c46-b697-900ced38b5ca/archive/Coca carola-Tigger & Ber-1992-FLAC-STiGMA` | validated_without_album_folder | Validator evidence exists. |
| VALIDATED | Galenskaparna & After Shave | Grisen i säcken | `134760902` | `/media/stigma/fa8a4ea5-d1da-4c46-b697-900ced38b5ca/archive/Galenskaparna & After Shave-Grisen i säcken-1992-FLAC-STiGMA` | validated_without_album_folder | Validator evidence exists. |
| VALIDATED | Galenskaparna & After Shave | Hajen som visste för mycket | `134809492` | `/media/stigma/fa8a4ea5-d1da-4c46-b697-900ced38b5ca/archive/Galenskaparna & After Shave-Hajen som visste för mycket-2012-FLAC-STiGMA` | validated_without_album_folder | Validator evidence exists. |
| VALIDATED | Galenskaparna & After Shave | Kasinofeber | `134757192` | `/media/stigma/fa8a4ea5-d1da-4c46-b697-900ced38b5ca/archive/Galenskaparna & After Shave-Kasinofeber-2002-FLAC-STiGMA` | validated_without_album_folder | Validator evidence exists. |
| VALIDATED | Galenskaparna & After Shave | Macken (Låtarna ur TV-serien) | `134809612` | `/media/stigma/fa8a4ea5-d1da-4c46-b697-900ced38b5ca/archive/Galenskaparna & After Shave-Macken (Låtarna ur TV-serien)-2012-FLAC-STiGMA` | validated_without_album_folder | Validator evidence exists. |
| VALIDATED | Galenskaparna & After Shave | MACKEN – TV-serien på scen | `129528442` | `/media/stigma/fa8a4ea5-d1da-4c46-b697-900ced38b5ca/archive/Galenskaparna & After Shave-MACKEN – TV-serien på scen-2017-FLAC-STiGMA` | validated_without_album_folder | Validator evidence exists. |
| VALIDATED | Galenskaparna & After Shave | Monopol | `134764102` | `/media/stigma/fa8a4ea5-d1da-4c46-b697-900ced38b5ca/archive/Galenskaparna & After Shave-Monopol-1996-FLAC-STiGMA` | validated_without_album_folder | Validator evidence exists. |
| VALIDATED | Galenskaparna & After Shave | Spargrisarna kan rädda världen | `129508582` | `/media/stigma/fa8a4ea5-d1da-4c46-b697-900ced38b5ca/archive/Galenskaparna & After Shave-Spargrisarna kan rädda världen-2018-FLAC-STiGMA` | validated_without_album_folder | Validator evidence exists. |
| VALIDATED | Galenskaparna & After Shave | Stinsen Brinner | `134809522` | `/media/stigma/fa8a4ea5-d1da-4c46-b697-900ced38b5ca/archive/Galenskaparna & After Shave-Stinsen Brinner-2012-FLAC-STiGMA` | validated_without_album_folder | Validator evidence exists. |
| VALIDATED | Galenskaparna & After Shave | Träsmak | `134773562` | `/media/stigma/fa8a4ea5-d1da-4c46-b697-900ced38b5ca/archive/Galenskaparna & After Shave-Träsmak-2012-FLAC-STiGMA` | validated_without_album_folder | Validator evidence exists. |
| VALIDATED | Galenskaparna & After Shave | Åke från Åstol | `134812992` | `/media/stigma/fa8a4ea5-d1da-4c46-b697-900ced38b5ca/archive/Galenskaparna & After Shave-Åke från Åstol-1998-FLAC-STiGMA` | validated_without_album_folder | Validator evidence exists. |
| VALIDATED | Guts | Beach Diggin', Vol. 3 | `704387011` | `/media/stigma/fa8a4ea5-d1da-4c46-b697-900ced38b5ca/archive/Guts-Beach Diggin', Vol. 3-2015-FLAC-STiGMA` | validated_without_album_folder | Validator evidence exists. |
| VALIDATED | Guts | Beach Diggin', Vol. 4 | `317793567` | `/media/stigma/fa8a4ea5-d1da-4c46-b697-900ced38b5ca/archive/Guts-Beach Diggin', Vol. 4-2016-FLAC-STiGMA` | validated_without_album_folder | Validator evidence exists. |
| VALIDATED | Guts | Fines bouches, Vol. 1 | `9537198` | `/media/stigma/fa8a4ea5-d1da-4c46-b697-900ced38b5ca/archive/Guts-Fines bouches, Vol. 1-2015-FLAC-STiGMA` | validated_without_album_folder | Validator evidence exists. |
| VALIDATED | Guts | Straight from the Decks, Vol. 3 (Guts Finest Selection from His Famous DJ Sets) | `459560955` | `/media/stigma/fa8a4ea5-d1da-4c46-b697-900ced38b5ca/archive/Guts-Straight from the Decks, Vol. 3 (Guts Finest Selection from His Famous DJ Sets)-2023-FLAC-STiGMA` | validated_without_album_folder | Validator evidence exists. |
| VALIDATED | Guts | Straight from the Decks, Vol. 4 (Guts Finest Selection from His Famous DJ Sets) | `657757471` | `/media/stigma/fa8a4ea5-d1da-4c46-b697-900ced38b5ca/archive/Guts-Straight from the Decks, Vol. 4 (Guts Finest Selection from His Famous DJ Sets)-2024-FLAC-STiGMA` | validated_without_album_folder | Validator evidence exists. |
| VALIDATED | Khruangbin | Live at Radio City Music Hall | `444973115` | `/media/stigma/fa8a4ea5-d1da-4c46-b697-900ced38b5ca/archive/Khruangbin-Live at Radio City Music Hall-2023-FLAC-STiGMA` | validated_without_album_folder | Validator evidence exists. |
| VALIDATED | Khruangbin | Live at RBC Echo Beach | `452997095` | `/media/stigma/fa8a4ea5-d1da-4c46-b697-900ced38b5ca/archive/Khruangbin-Live at RBC Echo Beach-2023-FLAC-STiGMA` | validated_without_album_folder | Validator evidence exists. |
| VALIDATED | Khruangbin | Live at Stubb's | `423497267` | `/media/stigma/fa8a4ea5-d1da-4c46-b697-900ced38b5ca/archive/Khruangbin-Live at Stubb's-2023-FLAC-STiGMA` | validated_without_album_folder | Validator evidence exists. |
| VALIDATED | Khruangbin | Live at The Fillmore Miami | `461612575` | `/media/stigma/fa8a4ea5-d1da-4c46-b697-900ced38b5ca/archive/Khruangbin-Live at The Fillmore Miami-2023-FLAC-STiGMA` | validated_without_album_folder | Validator evidence exists. |
| VALIDATED | Kill Emil | Lights & Shadows | `42283171` | `/media/stigma/fa8a4ea5-d1da-4c46-b697-900ced38b5ca/archive/Kill Emil-Lights & Shadows-2017-FLAC-STiGMA` | validated_without_album_folder | Validator evidence exists. |
| VALIDATED | Lehto | Moo Juice (Benji Boko & BOY COM Remixes) | `477119535` | `/media/stigma/fa8a4ea5-d1da-4c46-b697-900ced38b5ca/archive/Renegades Of Jazz-Moo Juice (Benji Boko & BOY COM Remixes)-2011-FLAC-STiGMA` | validated_without_album_folder | Validator evidence exists. |
| VALIDATED | Mattafix | Rhythm & Hymns | `678442161` | `/media/stigma/fa8a4ea5-d1da-4c46-b697-900ced38b5ca/archive/Mattafix-Rhythm & Hymns-2008-FLAC-STiGMA` | validated_without_album_folder | Validator evidence exists. |
| VALIDATED | ommood | Me & Mon Ami | `342106957` | `/media/stigma/fa8a4ea5-d1da-4c46-b697-900ced38b5ca/archive/ommood-Me & Mon Ami-2022-FLAC-STiGMA` | validated_without_album_folder | Validator evidence exists. |
| VALIDATED | PaceWon & Mr. Green | The Only Color That Matters is Green | `496599671` | `/media/stigma/fa8a4ea5-d1da-4c46-b697-900ced38b5ca/archive/PaceWon & Mr. Green-The Only Color That Matters is Green-2008-FLAC-STiGMA` | validated_without_album_folder | Validator evidence exists. |
| VALIDATED | PaceWon & Mr. Green | The Only Number That Matters Is Won | `503695371` | `/media/stigma/fa8a4ea5-d1da-4c46-b697-900ced38b5ca/archive/PaceWon & Mr. Green-The Only Number That Matters Is Won-2012-FLAC-STiGMA` | validated_without_album_folder | Validator evidence exists. |
| VALIDATED | PaceWon & Mr. Green | The Only Number That Matters Is Won 1.5 | `484354065` | `/media/stigma/fa8a4ea5-d1da-4c46-b697-900ced38b5ca/archive/PaceWon & Mr. Green-The Only Number That Matters Is Won 1.5-2012-FLAC-STiGMA` | validated_without_album_folder | Validator evidence exists. |
| VALIDATED | Papa Roach | Time For Annihilation: On the Record & On the Road | `459629975` | `/media/stigma/fa8a4ea5-d1da-4c46-b697-900ced38b5ca/archive/Papa Roach-Time For Annihilation On the Record & On the Road-2010-FLAC-STiGMA` | validated_without_album_folder | Validator evidence exists. |
| VALIDATED | Protassov | Steam & Oil EP | `9665570` | `/media/stigma/fa8a4ea5-d1da-4c46-b697-900ced38b5ca/archive/Protassov-Steam & Oil EP-2015-FLAC-STiGMA` | validated_without_album_folder | Validator evidence exists. |
| VALIDATED | Sub Focus | Flashing Lights | `1341248` | `/media/stigma/fa8a4ea5-d1da-4c46-b697-900ced38b5ca/archive/Chase & Status-Flashing Lights-2011-FLAC-STiGMA` | validated_without_album_folder | Validator evidence exists. |

## Unknown Albums

| Artist | Album | Path | Reason |
| --- | --- | --- | --- |
| none |  |  |  |
