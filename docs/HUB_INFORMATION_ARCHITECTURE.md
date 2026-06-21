# Archive Hub Information Architecture

## Product Direction

The application is now an Archive Hub rather than a collection of sprint-era tools. Its primary navigation should answer four user questions:

1. **Curator** — What should enter the archive workflow?
2. **Archive** — What physically exists, and what is true about an album?
3. **Maintenance** — What needs work next?
4. **Settings** — Which roots, tools, and providers power the workflow?

AlbumTruth remains the owner of album state. Maintenance remains the owner of work classification. Navigation must not introduce another truth or classification layer.

## Proposed Navigation

### Curator

- Discovery and artist expansion
- Inbox and selection
- Download / Streamrip queue
- Shipping and processing handoff
- Metadata acquisition context

Curator ends when an album has entered the managed workflow. Archive inspection and repair do not belong here.

### Archive

Archive uses secondary navigation rather than separate top-level destinations:

- **Physical Archive** — filesystem-first artist and album browsing
- **Library** — lifecycle and metadata-backed collection browsing
- **Artwork** — cover-focused browsing

All three routes open the same conceptual album workspace:

- overview and identity;
- integrity and readiness;
- files and tracklist;
- artwork;
- NFO and documentation;
- related albums and operations.

Library and Artwork are lenses over Archive, not separate products.

### Maintenance

- Validation work
- Documentation work
- Metadata work
- Review and warnings
- Archive Audit findings
- Lifecycle and identity issues
- Recent operations and tool controls

Campaigns, Opportunities, Dashboard Actions, and Archive Actions are compatibility/reporting projections. They should not return as peer navigation destinations or classify albums independently.

### Settings

- **Roots** — archive, incoming, problematic, validation, metadata, and report paths
- **Tools** — Audio Division, NFO, SFV, validator, and file-manager executables
- **Providers** — playback and future external service providers

## Small Implementation Pass

This sprint applies only low-risk container and labeling changes:

- reduce top-level navigation to Curator, Archive, Maintenance, and Settings;
- nest Physical Archive, Library, and Artwork under Archive;
- rename the former Audio Division dashboard to Maintenance without changing its data or operations;
- clarify maintenance action and tool labels;
- group Settings into Roots, Tools, and Providers;
- retain all underlying views, commands, state, and refresh behavior.

## Follow-up Sequence

1. Move the contextual Maintenance Action Center from the Physical Archive pane into the Maintenance workspace while preserving album selection context.
2. Add read-only Audit Findings and Lifecycle Issues lists sourced from existing reports/models.
3. Merge duplicated Archive and Library album-workspace widgets behind one presenter.
4. Retire unreachable sprint-era Opportunity UI code after a deprecation cycle.
5. Review Curator metadata and download progress placement once the Archive workspace consolidation is complete.

These are navigation and presentation changes only. They do not authorize new truth models, background jobs, or archive mutations.
