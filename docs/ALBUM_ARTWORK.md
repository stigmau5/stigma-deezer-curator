# Album Artwork

Artwork is an album property. The Archive and Library workspaces render album covers directly from archive evidence when a local cover exists.

No network fetches are performed. Metadata artwork URLs may still be displayed as references, but they are not downloaded by the Hub.

## Local Artwork Priority

When an album folder is available, local files are preferred in this order:

1. `cover.jpg`
2. `folder.jpg`
3. `front.jpg`
4. `cover.png`
5. `folder.png`

If none of those files exist, the first supported image file is used as a fallback. Supported image suffixes are `.jpg`, `.jpeg`, `.png`, and `.webp`.

## Data Flow

1. Archive scanning records whether artwork exists and which file was selected.
2. Library and Archive album projections carry the selected local artwork path.
3. Album Workspace resolves the cover.
4. The GUI renders the cover through `CoverWidget`, a shared album-cover renderer.

The placeholder remains visible when no local artwork is available.

## CoverWidget

`audio_division.cover_widget.CoverWidget` is the reusable GUI boundary for album covers. Archive and Library workspaces both use it so missing artwork, image loading failures, and image scaling behave consistently.

`CoverWidget` only renders local filesystem artwork. It does not fetch, download, edit, or cache artwork.

## Relationship To Artwork Tab

The Artwork tab is no longer required for viewing album covers. Artwork browsing can remain as a secondary collection/reporting surface, but the primary album experience is the Archive or Library workspace.

## Future Work

Possible future work:

- artwork cache inspection
- cover quality reporting
- manual artwork review actions

Those should remain explicit workflows and should not rewrite archive artwork automatically.
