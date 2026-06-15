# Archive Identity Recovery Report

Generated: 2026-06-15T17:34:32

Identity recovery is derived analysis only. No archive files, tags, validator outputs, or metadata are modified.

## Summary

- Unresolved validator logs: `77`
- Recoverable today: `16`
- Unrecoverable today: `61`

| Recovery level | Logs |
| --- | ---: |
| RECOVERABLE_HIGH | 0 |
| RECOVERABLE_MEDIUM | 16 |
| RECOVERABLE_LOW | 0 |
| UNRECOVERABLE | 61 |

## Improvement Opportunity

- Add or recover `ALBUM_ID` tags to turn review candidates into high-confidence identity links.
- Cache UPC and ordered ISRC lists to improve compilation and variant matching.
- Preserve manifest hashes for archive folders so moved folders can be recognized later.
