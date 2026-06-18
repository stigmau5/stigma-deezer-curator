# Artwork Browser

Sprint V makes artwork a first-class archive asset in STiGMA Archive Hub.

## Purpose

The Artwork tab provides a visual way to browse album covers already known to the Hub. It uses existing derived state and does not download, rewrite, or modify artwork files.

## Data Sources

Artwork Browser uses the Library projection, which already combines:

- Lifecycle Registry
- Identity Registry
- Metadata Cache
- Archive path resolution
- Archive artifact detection
- Archive Readiness

Local artwork is preferred when an archive path contains artwork. Cached metadata artwork URLs are displayed as references only.

## Browser Model

The tab displays:

- Cover reference
- Artist
- Album
- Year
- Readiness

Filters are available for artist and album text.

## Actions

The browser can:

- Open the selected album in the Library tab
- Open the selected album folder through the existing operation runner

No direct subprocess calls are made from the browser action logic.

## Reports

`reports/artwork_coverage_report.md` summarizes:

- total albums
- local artwork coverage
- metadata artwork references
- missing artwork
- coverage percentage

## Limitations

The browser is read-only. It does not fetch missing artwork, create artwork caches, or alter archive folders.

Future sprints can add richer thumbnail caching, larger cover previews, artwork quality checks, and artwork repair workflows.
