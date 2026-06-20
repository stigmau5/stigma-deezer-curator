# Album Relationship Explorer

The Album Relationship Explorer is a read-only workspace feature.

It answers simple collection questions for the selected album:

- What else do I have by this artist?
- What else shares this label?
- What else is from this year?
- What else shares cached genres?

## Data Sources

Relationships are derived from existing in-memory album projections:

- Archive Registry projections
- Library projections
- Metadata Cache fields already attached to albums

No network calls are made. No metadata is fetched. No archive files are modified.

## Relationship Rules

The selected album is excluded from all relationship groups.

Groups:

- `same_artist`: normalized artist names match
- `same_label`: normalized label values match
- `same_year`: normalized year values match
- `same_genre`: at least one normalized cached genre overlaps

Results are capped per group for readability.

## Architecture

`audio_division.relationships` owns relationship derivation and rendering.

`audio_division.album_workspace` includes the relationship payload so Archive and Library can display the same album-centric knowledge.

The relationship explorer is not a registry and not a source of truth. It is a derived view over the current archive and metadata projections.
