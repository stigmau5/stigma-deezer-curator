# Maintenance Model

Maintenance is the single answer to: "What should I work on next?"

The Archive tab's Maintenance Action Center is the primary action surface. Campaigns, Opportunities, Dashboard Actions, and Archive Actions remain compatibility or reporting views; they must delegate classification to Maintenance.

## Ownership

AlbumTruth owns album state. Maintenance reads AlbumTruth and assigns one primary category per album. It does not inspect lifecycle, identity, metadata, or artifact sources independently.

Category precedence:

1. `needs_validation`
2. `needs_documentation`
3. `needs_metadata`
4. `needs_review`
5. `warnings`
6. `ready`

An album appears in exactly one primary Maintenance category. This keeps category counts additive and prevents the same deficiency from being counted differently by several UI systems.

## Categories

- **Needs Validation**: AlbumTruth validation is not present.
- **Needs Documentation**: validation is present, but NFO or SFV evidence is not present.
- **Needs Metadata**: validation and documentation are present, but metadata status is not `CACHED`.
- **Needs Review**: AlbumTruth readiness or identity confidence requires review.
- **Warnings**: AlbumTruth reports unresolved identity or archive-path confidence.
- **Ready**: AlbumTruth validation, documentation, metadata, identity, and readiness evidence is complete.

Structural and duplicate warnings remain advisory annotations in the Warnings view. They do not override an album's primary AlbumTruth-owned category or become a second truth source.

## Routing

Default operation routing:

| Category | Operation |
| --- | --- |
| Needs Validation | Validate Album |
| Needs Documentation | Generate Documentation |
| Needs Metadata | Refresh Metadata |
| Needs Review | Open Folder |
| Warnings | Open Folder |
| Ready | Open Folder |

The operation runner remains responsible for validating and executing the selected operation.

## Compatibility Views

- Campaigns filter canonical Maintenance categories into legacy artifact-specific selections.
- Opportunities render Maintenance records using their existing report schema.
- Dashboard Actions are generated from Maintenance records when library data is available.
- Registry-only callers are projected through the Library and AlbumTruth before actions are rendered.

Compatibility views must not introduce new category precedence or override AlbumTruth.
