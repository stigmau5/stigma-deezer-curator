import tkinter as tk
from tkinter import ttk, messagebox
from pathlib import Path
from datetime import datetime
import subprocess
import json
import re
import threading

from curator.curate import run_curation
from audio_division.dashboard import dashboard_summary
from audio_division.settings import (
    load_audio_division_settings,
    save_audio_division_settings,
)
from audio_division.operation_runner import run_operation
from audio_division.batch_operations import (
    available_batch_operations,
    collect_album_targets,
    run_batch_operation,
    write_batch_operation_report,
)
from audio_division.library import (
    album_archive_operation_target,
    album_details,
    albums_for_artist,
    library_from_data_dir,
)
from audio_division.opportunities import (
    HUB_OPPORTUNITY_CATEGORIES,
    OPPORTUNITY_CATEGORIES,
    derive_hub_opportunities,
    filter_opportunities,
    generate_opportunities,
    group_hub_opportunities,
    hub_opportunity_summary,
    opportunity_summary,
)

# ---------------- Base paths ----------------

BASE_DIR = Path(__file__).resolve().parent

DATA_DIR = BASE_DIR / "data"
INBOX = DATA_DIR / "inbox.txt"
LOG = DATA_DIR / "curated.log"
ARTISTS_DIR = DATA_DIR / "artists"
SHIPPED_DIR = DATA_DIR / "shipped"
AUDIO_DIVISION_SETTINGS_FILE = DATA_DIR / "audio_division_settings.json"
OPERATION_HISTORY_FILE = DATA_DIR / "operation_history.json"
META_FILE = DATA_DIR / "artist_meta.json"

STREAMRIP_BIN = Path(
    "/home/stigma/Dokument/projekt/streamrip/.venv/bin/rip"
)
STREAMRIP_QUEUE = Path(
    "/home/stigma/Dokument/projekt/streamrip/download_que.txt"
)

# ---------------- Metadata helpers ----------------


def load_meta():
    if META_FILE.exists():
        try:
            return json.loads(META_FILE.read_text())
        except Exception:
            pass
    return {"created": {}}


def save_meta(meta):
    META_FILE.write_text(json.dumps(meta, indent=2))


def record_created(filename: str):
    meta = load_meta()
    if filename not in meta["created"]:
        meta["created"][filename] = datetime.now().isoformat()
        save_meta(meta)


# ---------------- GUI ----------------


class DeezerCuratorGUI(tk.Tk):
    def __init__(self):
        super().__init__()

        self.title("STiGMA Deezer Curator — v0.3.1")
        self.geometry("1400x700")

        self.main_mode = "artist"  # artist | inbox
        self.sort_mode = "alphabetical"

        # Grep toggles
        self.include_live = tk.BooleanVar(value=True)
        self.include_compilations = tk.BooleanVar(value=True)

        self.audio_settings = load_audio_division_settings(AUDIO_DIVISION_SETTINGS_FILE)
        self.audio_setting_vars: dict[tuple[str, str], tk.StringVar] = {}
        self.dashboard_value_labels: dict[str, ttk.Label] = {}
        self.action_detail = None
        self.operation_history_detail = None
        self.operation_target_var = tk.StringVar()
        self.library_data = {}
        self.library_artist_rows: list[dict] = []
        self.library_album_rows: list[dict] = []
        self.library_summary_labels: dict[str, ttk.Label] = {}
        self.library_selected_album: dict = {}
        self.library_operation_result_var = tk.StringVar()
        self.opportunity_rows: list[dict] = []
        self.filtered_opportunity_rows: list[dict] = []
        self.opportunity_summary_labels: dict[str, ttk.Label] = {}
        self.opportunity_category_var = tk.StringVar(value="")
        self.opportunity_priority_var = tk.StringVar(value="")
        self.opportunity_artist_var = tk.StringVar()
        self.batch_progress_var = tk.StringVar(value="No batch running.")
        self.hub_opportunity_rows: list[dict] = []
        self.hub_opportunity_groups: dict[str, list[dict]] = {}
        self.hub_selected_category = tk.StringVar(value="NEEDS_REVIEW")
        self.hub_summary_labels: dict[str, ttk.Label] = {}
        self.hub_action_result_var = tk.StringVar(value="")

        self._build_layout()
        self.refresh_artists()
        self.load_inbox()
        self.load_custom_queue()

    # ---------------- UI ----------------

    def _build_layout(self):
        self.tabs = ttk.Notebook(self)
        self.tabs.pack(fill="both", expand=True)

        curator_tab = ttk.Frame(self.tabs)
        self.tabs.add(curator_tab, text="Curator")

        audio_tab = ttk.Frame(self.tabs, padding=10)
        self.tabs.add(audio_tab, text="Audio Division")

        library_tab = ttk.Frame(self.tabs, padding=10)
        self.tabs.add(library_tab, text="Library")
        self.library_tab = library_tab

        opportunities_tab = ttk.Frame(self.tabs, padding=10)
        self.tabs.add(opportunities_tab, text="Archive Opportunities")

        hub_tab = ttk.Frame(self.tabs, padding=10)
        self.tabs.add(hub_tab, text="Opportunities")

        settings_tab = ttk.Frame(self.tabs, padding=10)
        self.tabs.add(settings_tab, text="Settings")

        main = ttk.Panedwindow(curator_tab, orient="horizontal")
        main.pack(fill="both", expand=True)

        # ===== LEFT =====
        left = ttk.Frame(main, padding=6)
        main.add(left, weight=1)

        ttk.Label(left, text="Artists").pack(anchor="w")

        self.sort_box = ttk.Combobox(
            left,
            values=["Alphabetical", "Last added"],
            state="readonly",
            width=18,
        )
        self.sort_box.current(0)
        self.sort_box.pack(pady=(0, 6))
        self.sort_box.bind("<<ComboboxSelected>>", self.on_sort_change)

        self.artist_list = tk.Listbox(left)
        self.artist_list.pack(fill="both", expand=True)
        self.artist_list.bind("<<ListboxSelect>>", self.open_selected_artist)

        # ===== CENTER =====
        center = ttk.Frame(main, padding=6)
        main.add(center, weight=2)

        self.main_label = ttk.Label(center, text="Artist file")
        self.main_label.pack(anchor="w")

        self.main_editor = tk.Text(center, wrap="none")
        self.main_editor.pack(fill="both", expand=True)

        # ===== RIGHT =====
        right = ttk.Frame(main, padding=6)
        main.add(right, weight=2)

        ttk.Label(right, text="Streamrip queue").pack(anchor="w")
        self.custom_editor = tk.Text(right, wrap="none")
        self.custom_editor.pack(fill="both", expand=True)

        # ===== BOTTOM =====
        bottom = ttk.Frame(curator_tab, padding=8)
        bottom.pack(fill="x")

        ttk.Button(bottom, text="Show Artist", command=self.show_artist_mode).pack(
            side="left", padx=4
        )
        ttk.Button(bottom, text="Show Inbox", command=self.show_inbox_mode).pack(
            side="left", padx=4
        )
        ttk.Button(bottom, text="Save Inbox", command=self.save_inbox).pack(
            side="left", padx=4
        )

        ttk.Button(
            bottom,
            text="Send selected link(s)",
            command=self.send_selected_link_to_queue,
        ).pack(side="left", padx=8)

        ttk.Separator(bottom, orient="vertical").pack(side="left", fill="y", padx=6)

        ttk.Button(
            bottom, text="Send Albums", command=lambda: self.grep_section("Albums")
        ).pack(side="left", padx=2)
        ttk.Button(
            bottom, text="Send EPs", command=lambda: self.grep_section("EPs")
        ).pack(side="left", padx=2)
        ttk.Button(
            bottom, text="Send Singles", command=lambda: self.grep_section("Singles")
        ).pack(side="left", padx=2)

        ttk.Separator(bottom, orient="vertical").pack(side="left", fill="y", padx=6)

        ttk.Checkbutton(
            bottom, text="Include Live", variable=self.include_live
        ).pack(side="left")
        ttk.Checkbutton(
            bottom, text="Include Compilations", variable=self.include_compilations
        ).pack(side="left")

        ttk.Separator(bottom, orient="vertical").pack(side="left", fill="y", padx=6)

        self.run_button = ttk.Button(
            bottom, text="Run Curator (Inbox)", command=self.run_from_inbox
        )
        self.run_button.pack(side="left", padx=8)

        ttk.Button(
            bottom, text="Send to streamrip", command=self.send_to_streamrip
        ).pack(side="left", padx=8)

        self.status = ttk.Label(bottom, text="Idle")
        self.status.pack(side="right")

        self._build_audio_dashboard(audio_tab)
        self._build_library_tab(library_tab)
        self._build_opportunities_tab(opportunities_tab)
        self._build_hub_opportunities_tab(hub_tab)
        self._build_settings_tab(settings_tab)

    def _build_library_tab(self, parent):
        toolbar = ttk.Frame(parent)
        toolbar.pack(fill="x", pady=(0, 10))
        ttk.Button(toolbar, text="Refresh", command=self.refresh_library).pack(side="left")

        summary = ttk.LabelFrame(parent, text="Library Summary", padding=8)
        summary.pack(fill="x", pady=(0, 10))
        fields = [
            ("artists", "Artists"),
            ("albums", "Albums"),
            ("tracks", "Tracks"),
            ("metadata_coverage", "Metadata Coverage"),
            ("validation_coverage", "Validation Coverage"),
        ]
        for col, (key, label) in enumerate(fields):
            ttk.Label(summary, text=label).grid(row=0, column=col * 2, sticky="w", padx=(0, 6))
            value = ttk.Label(summary, text="0")
            value.grid(row=0, column=col * 2 + 1, sticky="w", padx=(0, 18))
            self.library_summary_labels[key] = value

        browser = ttk.Panedwindow(parent, orient="horizontal")
        browser.pack(fill="both", expand=True)

        artists_frame = ttk.LabelFrame(browser, text="Artists", padding=6)
        browser.add(artists_frame, weight=1)
        self.library_artist_list = tk.Listbox(artists_frame, exportselection=False)
        self.library_artist_list.pack(side="left", fill="both", expand=True)
        artist_scroll = ttk.Scrollbar(artists_frame, orient="vertical", command=self.library_artist_list.yview)
        artist_scroll.pack(side="right", fill="y")
        self.library_artist_list.configure(yscrollcommand=artist_scroll.set)
        self.library_artist_list.bind("<<ListboxSelect>>", self.on_library_artist_selected)

        albums_frame = ttk.LabelFrame(browser, text="Albums", padding=6)
        browser.add(albums_frame, weight=2)
        columns = ("title", "year", "record_type", "validation")
        self.library_album_tree = ttk.Treeview(
            albums_frame,
            columns=columns,
            show="headings",
            selectmode="browse",
        )
        headings = [
            ("title", "Title", 260),
            ("year", "Year", 70),
            ("record_type", "Type", 90),
            ("validation", "Validation", 110),
        ]
        for column, text, width in headings:
            self.library_album_tree.heading(column, text=text)
            self.library_album_tree.column(column, width=width, anchor="w")
        self.library_album_tree.pack(side="left", fill="both", expand=True)
        album_scroll = ttk.Scrollbar(albums_frame, orient="vertical", command=self.library_album_tree.yview)
        album_scroll.pack(side="right", fill="y")
        self.library_album_tree.configure(yscrollcommand=album_scroll.set)
        self.library_album_tree.bind("<<TreeviewSelect>>", self.on_library_album_selected)

        details_frame = ttk.LabelFrame(browser, text="Album Details", padding=6)
        browser.add(details_frame, weight=2)
        self.library_detail_text = tk.Text(details_frame, wrap="word", height=20)
        self.library_detail_text.pack(fill="both", expand=True)
        self.library_detail_text.config(state="disabled")

        operations = ttk.LabelFrame(details_frame, text="Album Operations", padding=6)
        operations.pack(fill="x", pady=(8, 0))
        buttons = ttk.Frame(operations)
        buttons.pack(fill="x")
        ttk.Button(buttons, text="Validate Album", command=lambda: self.run_library_album_operation("validate_album")).pack(side="left")
        ttk.Button(buttons, text="Generate NFO", command=lambda: self.run_library_album_operation("generate_nfo")).pack(side="left", padx=(6, 0))
        ttk.Button(buttons, text="Generate SFV", command=lambda: self.run_library_album_operation("generate_sfv")).pack(side="left", padx=(6, 0))
        ttk.Button(buttons, text="Open Folder", command=lambda: self.run_library_album_operation("open_album_folder")).pack(side="left", padx=(6, 0))
        ttk.Label(operations, textvariable=self.library_operation_result_var).pack(anchor="w", pady=(6, 0))

        self.refresh_library()

    def _build_opportunities_tab(self, parent):
        toolbar = ttk.Frame(parent)
        toolbar.pack(fill="x", pady=(0, 10))
        ttk.Button(toolbar, text="Refresh", command=self.refresh_opportunities).pack(side="left")
        ttk.Button(toolbar, text="Show Album", command=self.open_selected_opportunity_album).pack(side="left", padx=(6, 0))
        ttk.Button(toolbar, text="Generate NFO", command=lambda: self.run_opportunity_batch("generate_nfo")).pack(side="left", padx=(18, 0))
        ttk.Button(toolbar, text="Generate SFV", command=lambda: self.run_opportunity_batch("generate_sfv")).pack(side="left", padx=(6, 0))
        ttk.Button(toolbar, text="Validate Albums", command=lambda: self.run_opportunity_batch("validate_album")).pack(side="left", padx=(6, 0))

        filters = ttk.LabelFrame(parent, text="Filters", padding=8)
        filters.pack(fill="x", pady=(0, 10))
        ttk.Label(filters, text="Category").grid(row=0, column=0, sticky="w", padx=(0, 6))
        category = ttk.Combobox(
            filters,
            textvariable=self.opportunity_category_var,
            values=["", *OPPORTUNITY_CATEGORIES],
            state="readonly",
            width=22,
        )
        category.grid(row=0, column=1, sticky="w", padx=(0, 12))
        ttk.Label(filters, text="Priority").grid(row=0, column=2, sticky="w", padx=(0, 6))
        priority = ttk.Combobox(
            filters,
            textvariable=self.opportunity_priority_var,
            values=["", "HIGH", "MEDIUM", "LOW"],
            state="readonly",
            width=12,
        )
        priority.grid(row=0, column=3, sticky="w", padx=(0, 12))
        ttk.Label(filters, text="Artist").grid(row=0, column=4, sticky="w", padx=(0, 6))
        artist = ttk.Entry(filters, textvariable=self.opportunity_artist_var)
        artist.grid(row=0, column=5, sticky="ew")
        filters.columnconfigure(5, weight=1)
        category.bind("<<ComboboxSelected>>", lambda event: self.apply_opportunity_filters())
        priority.bind("<<ComboboxSelected>>", lambda event: self.apply_opportunity_filters())
        artist.bind("<KeyRelease>", lambda event: self.apply_opportunity_filters())

        summary = ttk.LabelFrame(parent, text="Summary", padding=8)
        summary.pack(fill="x", pady=(0, 10))
        for col, (key, label) in enumerate(
            (
                ("total", "Total Opportunities"),
                ("high", "High Priority"),
                ("medium", "Medium Priority"),
                ("low", "Low Priority"),
                ("top_categories", "Top Categories"),
            )
        ):
            ttk.Label(summary, text=label).grid(row=0, column=col * 2, sticky="w", padx=(0, 6))
            value = ttk.Label(summary, text="0")
            value.grid(row=0, column=col * 2 + 1, sticky="w", padx=(0, 18))
            self.opportunity_summary_labels[key] = value

        batch = ttk.LabelFrame(parent, text="Batch Progress", padding=8)
        batch.pack(fill="x", pady=(0, 10))
        ttk.Label(batch, textvariable=self.batch_progress_var).pack(anchor="w")

        columns = ("category", "priority", "artist", "album", "recommended_action")
        self.opportunity_tree = ttk.Treeview(parent, columns=columns, show="headings", selectmode="extended")
        headings = [
            ("category", "Category", 170),
            ("priority", "Priority", 90),
            ("artist", "Artist", 180),
            ("album", "Album", 260),
            ("recommended_action", "Recommended Action", 180),
        ]
        for column, text, width in headings:
            self.opportunity_tree.heading(column, text=text, command=lambda c=column: self.sort_opportunities(c))
            self.opportunity_tree.column(column, width=width, anchor="w")
        self.opportunity_tree.pack(side="left", fill="both", expand=True)
        scrollbar = ttk.Scrollbar(parent, orient="vertical", command=self.opportunity_tree.yview)
        scrollbar.pack(side="right", fill="y")
        self.opportunity_tree.configure(yscrollcommand=scrollbar.set)
        self.opportunity_tree.bind("<Double-1>", lambda event: self.open_selected_opportunity_album())

        self.refresh_opportunities()

    def _build_hub_opportunities_tab(self, parent):
        summary = ttk.LabelFrame(parent, text="Top Opportunities", padding=8)
        summary.pack(fill="x", pady=(0, 10))
        for col, (key, label) in enumerate(
            (
                ("NEEDS_VALIDATION", "Needs Validation"),
                ("NEEDS_DOCUMENTATION", "Needs Documentation"),
                ("NEEDS_METADATA", "Needs Metadata"),
                ("NEEDS_REVIEW", "Needs Review"),
                ("ARCHIVE_READY", "Archive Ready"),
            )
        ):
            ttk.Label(summary, text=label).grid(row=0, column=col * 2, sticky="w", padx=(0, 6))
            value = ttk.Label(summary, text="0")
            value.grid(row=0, column=col * 2 + 1, sticky="w", padx=(0, 18))
            self.hub_summary_labels[key] = value

        panes = ttk.Panedwindow(parent, orient="horizontal")
        panes.pack(fill="both", expand=True)

        categories = ttk.LabelFrame(panes, text="Categories", padding=6)
        panes.add(categories, weight=1)
        self.hub_category_list = tk.Listbox(categories, exportselection=False)
        self.hub_category_list.pack(fill="both", expand=True)
        self.hub_category_list.bind("<<ListboxSelect>>", self.on_hub_category_selected)

        albums = ttk.LabelFrame(panes, text="Albums", padding=6)
        panes.add(albums, weight=4)
        columns = ("artist", "album", "lifecycle", "readiness", "priority", "reason")
        self.hub_album_tree = ttk.Treeview(albums, columns=columns, show="headings", selectmode="browse")
        headings = [
            ("artist", "Artist", 160),
            ("album", "Album", 230),
            ("lifecycle", "Lifecycle State", 110),
            ("readiness", "Archive Readiness", 130),
            ("priority", "Priority", 80),
            ("reason", "Reason", 280),
        ]
        for column, text, width in headings:
            self.hub_album_tree.heading(column, text=text)
            self.hub_album_tree.column(column, width=width, anchor="w")
        self.hub_album_tree.pack(fill="both", expand=True)

        actions = ttk.LabelFrame(parent, text="Actions", padding=8)
        actions.pack(fill="x", pady=(10, 0))
        ttk.Button(actions, text="Validate Album", command=lambda: self.run_hub_opportunity_action("validate_album")).pack(side="left")
        ttk.Button(actions, text="Generate Documentation", command=lambda: self.run_hub_opportunity_action("generate_nfo")).pack(side="left", padx=(6, 0))
        ttk.Button(actions, text="Refresh Metadata", command=lambda: self.run_hub_opportunity_action("refresh_metadata")).pack(side="left", padx=(6, 0))
        ttk.Button(actions, text="Open Folder", command=lambda: self.run_hub_opportunity_action("open_album_folder")).pack(side="left", padx=(6, 0))
        ttk.Label(actions, textvariable=self.hub_action_result_var).pack(side="left", padx=(12, 0))

        self.refresh_hub_opportunities()

    def _build_audio_dashboard(self, parent):
        toolbar = ttk.Frame(parent)
        toolbar.pack(fill="x", pady=(0, 10))
        ttk.Button(toolbar, text="Refresh", command=self.refresh_audio_dashboard).pack(side="left")

        grid = ttk.Frame(parent)
        grid.pack(fill="both", expand=True)

        sections = [
            ("Archive Overview", [
                ("archive_overview.albums", "Albums"),
                ("archive_overview.artists", "Artists"),
                ("archive_overview.cached_tracks", "Cached Tracks"),
                ("archive_overview.archive_strength", "Archive Strength"),
            ]),
            ("Lifecycle", [
                ("lifecycle.discovered", "Discovered"),
                ("lifecycle.attempted", "Attempted"),
                ("lifecycle.shipped", "Shipped"),
                ("lifecycle.validated", "Validated"),
                ("lifecycle.confirmed", "Confirmed"),
            ]),
            ("Identity", [
                ("identity.high_confidence", "High Confidence"),
                ("identity.medium_confidence", "Medium Confidence"),
                ("identity.unknown", "Unknown"),
                ("identity.unresolved_logs", "Unresolved Logs"),
            ]),
            ("Metadata", [
                ("metadata.albums_cached", "Albums Cached"),
                ("metadata.artists_cached", "Artists Cached"),
                ("metadata.tracks_cached", "Tracks Cached"),
                ("metadata.coverage_percent", "Metadata Coverage"),
            ]),
            ("Metadata Overview", [
                ("metadata.cached", "Cached"),
                ("metadata.available_not_cached", "Available Not Cached"),
                ("metadata.missing", "Missing"),
                ("metadata.unknown", "Unknown"),
            ]),
            ("Validation", [
                ("validation.coverage_percent", "Validation Coverage"),
                ("validation.evidence_count", "Validation Evidence Count"),
            ]),
            ("Archive Health", [
                ("archive_health.shipped_not_validated", "Shipped Not Validated"),
                ("archive_health.attempted_not_shipped", "Attempted Not Shipped"),
                ("archive_health.confirmed_not_validated", "Confirmed Not Validated"),
            ]),
            ("Archive Readiness", [
                ("archive_readiness.archive_ready", "Archive Ready"),
                ("archive_readiness.needs_validation", "Needs Validation"),
                ("archive_readiness.needs_documentation", "Needs Documentation"),
                ("archive_readiness.needs_review", "Needs Review"),
                ("archive_readiness.unknown", "Unknown"),
            ]),
            ("Top Opportunities", [
                ("top_opportunities.needs_validation", "Needs Validation"),
                ("top_opportunities.needs_documentation", "Needs Documentation"),
                ("top_opportunities.needs_metadata", "Needs Metadata"),
                ("top_opportunities.needs_review", "Needs Review"),
                ("top_opportunities.archive_ready", "Archive Ready"),
                ("top_opportunities.most_urgent_category", "Most Urgent"),
            ]),
            ("Archive Actions", [
                ("archive_actions.action_count", "Action Count"),
                ("archive_actions.missing_nfo", "Missing NFO"),
                ("archive_actions.missing_sfv", "Missing SFV"),
                ("archive_actions.missing_validation", "Missing Validation"),
                ("archive_actions.missing_metadata", "Missing Metadata"),
                ("archive_actions.missing_artwork", "Missing Artwork"),
                ("archive_actions.identity_review", "Identity Review"),
            ]),
            ("Archive Operations", [
                ("archive_operations.operation_count", "Operations"),
                ("archive_operations.generate_nfo", "Generate NFO"),
                ("archive_operations.generate_sfv", "Generate SFV"),
                ("archive_operations.validate_album", "Validate Album"),
                ("archive_operations.open_album_folder", "Open Album Folder"),
                ("archive_operations.refresh_metadata", "Refresh Metadata"),
            ]),
            ("Recent Operations", [
                ("recent_operations.operation_count", "History Entries"),
            ]),
        ]

        for idx, (title, fields) in enumerate(sections):
            frame = ttk.LabelFrame(grid, text=title, padding=8)
            frame.grid(row=idx // 3, column=idx % 3, sticky="nsew", padx=5, pady=5)
            grid.columnconfigure(idx % 3, weight=1)
            grid.rowconfigure(idx // 3, weight=1)
            for row, (key, label) in enumerate(fields):
                ttk.Label(frame, text=label).grid(row=row, column=0, sticky="w", padx=(0, 10), pady=2)
                value = ttk.Label(frame, text="0")
                value.grid(row=row, column=1, sticky="e", pady=2)
                frame.columnconfigure(1, weight=1)
                self.dashboard_value_labels[key] = value

        details = ttk.LabelFrame(parent, text="Action Details", padding=8)
        details.pack(fill="x", pady=(10, 0))
        self.action_detail = tk.Text(details, height=4, wrap="word")
        self.action_detail.pack(fill="x")
        self.action_detail.config(state="disabled")

        operations = ttk.LabelFrame(parent, text="Operation Test Controls", padding=8)
        operations.pack(fill="x", pady=(10, 0))
        ttk.Label(operations, text="Target folder").grid(row=0, column=0, sticky="w", padx=(0, 10), pady=2)
        ttk.Entry(operations, textvariable=self.operation_target_var).grid(row=0, column=1, sticky="ew", pady=2)
        operations.columnconfigure(1, weight=1)
        buttons = ttk.Frame(operations)
        buttons.grid(row=1, column=0, columnspan=2, sticky="w", pady=(6, 0))
        ttk.Button(buttons, text="Generate NFO", command=lambda: self.run_archive_operation("generate_nfo")).pack(side="left")
        ttk.Button(buttons, text="Generate SFV", command=lambda: self.run_archive_operation("generate_sfv")).pack(side="left", padx=(6, 0))
        ttk.Button(buttons, text="Validate Album", command=lambda: self.run_archive_operation("validate_album")).pack(side="left", padx=(6, 0))
        ttk.Button(buttons, text="Open Folder", command=lambda: self.run_archive_operation("open_album_folder")).pack(side="left", padx=(6, 0))

        history = ttk.LabelFrame(parent, text="Recent Operations", padding=8)
        history.pack(fill="x", pady=(10, 0))
        self.operation_history_detail = tk.Text(history, height=5, wrap="word")
        self.operation_history_detail.pack(fill="x")
        self.operation_history_detail.config(state="disabled")

        self.refresh_audio_dashboard()

    def _build_settings_tab(self, parent):
        fields = [
            ("archive_paths", "main_archive_root", "Main Archive Root"),
            ("archive_paths", "incoming_root", "Incoming Root"),
            ("archive_paths", "problematic_root", "Problematic Root"),
            ("archive_paths", "needs_validation_root", "Needs Validation Root"),
            ("validator", "validated_index_path", "Validated Index Path"),
            ("validator", "validation_log_root", "Validation Log Root"),
            ("metadata", "metadata_cache_path", "Metadata Cache Path"),
            ("reports", "reports_directory", "Reports Directory"),
            ("tools", "nfo_generator_path", "NFO Generator Path"),
            ("tools", "sfv_generator_path", "SFV Generator Path"),
            ("tools", "flac_validator_path", "FLAC Validator Path"),
            ("tools", "file_manager_path", "File Manager Path"),
        ]
        form = ttk.Frame(parent)
        form.pack(fill="both", expand=True)
        for row, (section, key, label) in enumerate(fields):
            ttk.Label(form, text=label).grid(row=row, column=0, sticky="w", padx=(0, 10), pady=4)
            var = tk.StringVar(value=self.audio_settings.get(section, {}).get(key, ""))
            ttk.Entry(form, textvariable=var).grid(row=row, column=1, sticky="ew", pady=4)
            self.audio_setting_vars[(section, key)] = var
        form.columnconfigure(1, weight=1)

        buttons = ttk.Frame(parent)
        buttons.pack(fill="x", pady=(10, 0))
        ttk.Button(buttons, text="Save Settings", command=self.save_audio_settings).pack(side="left")
        ttk.Button(buttons, text="Reload Settings", command=self.reload_audio_settings).pack(side="left", padx=(6, 0))

    def refresh_audio_dashboard(self):
        summary = dashboard_summary(DATA_DIR)
        for key, label in self.dashboard_value_labels.items():
            section, field = key.split(".", 1)
            value = summary.get(section, {}).get(field, 0)
            label.config(text=f"{value:.1%}" if isinstance(value, float) else str(value))
        action = summary.get("archive_actions", {}).get("selected_action", {})
        if self.action_detail is not None:
            details = (
                f"{action.get('priority', '').upper()} {action.get('type', '')}\n"
                f"{action.get('artist', '')} - {action.get('title', '')}\n"
                f"{action.get('description', '')}\n"
                f"Evidence: {', '.join(action.get('evidence', []))}"
            ).strip()
            self.action_detail.config(state="normal")
            self.action_detail.delete("1.0", tk.END)
            self.action_detail.insert(tk.END, details or "No archive actions found.")
            self.action_detail.config(state="disabled")
        if self.operation_history_detail is not None:
            items = summary.get("recent_operations", {}).get("items", [])
            text = "\n".join(
                f"{item.get('timestamp', '')}  {item.get('operation', '')}  {item.get('result', '')}"
                for item in items
            )
            self.operation_history_detail.config(state="normal")
            self.operation_history_detail.delete("1.0", tk.END)
            self.operation_history_detail.insert(tk.END, text or "No operations recorded.")
            self.operation_history_detail.config(state="disabled")

    def run_archive_operation(self, operation_id: str):
        target = self.operation_target_var.get().strip()
        result = run_operation(operation_id, target, self.audio_settings, OPERATION_HISTORY_FILE)
        self.status.config(text=f"{operation_id}: {result['result']} - {result['message']}")
        self.refresh_audio_dashboard()

    def refresh_library(self):
        try:
            archive_root = self.audio_settings.get("archive_paths", {}).get("main_archive_root", "")
            self.library_data = library_from_data_dir(DATA_DIR, Path(archive_root) if archive_root else None)
        except Exception as exc:
            self.library_data = {"artists": [], "albums": {}, "summary": {}}
            self.status.config(text=f"Library refresh failed: {exc}")

        summary = self.library_data.get("summary", {})
        for key, label in self.library_summary_labels.items():
            value = summary.get(key, 0)
            label.config(text=f"{value:.1%}" if isinstance(value, float) else str(value))

        self.library_artist_rows = list(self.library_data.get("artists", []))
        self.library_artist_list.delete(0, tk.END)
        for row in self.library_artist_rows:
            count = row.get("album_count", 0)
            suffix = f" ({count})" if count else ""
            self.library_artist_list.insert(tk.END, f"{row.get('name', 'Unknown Artist')}{suffix}")

        self.clear_library_albums()
        self.set_library_detail({})
        if hasattr(self, "opportunity_tree"):
            self.refresh_opportunities()
        if hasattr(self, "hub_category_list"):
            self.refresh_hub_opportunities()

    def clear_library_albums(self):
        self.library_album_rows = []
        self.library_selected_album = {}
        for item in self.library_album_tree.get_children():
            self.library_album_tree.delete(item)

    def on_library_artist_selected(self, event=None):
        selection = self.library_artist_list.curselection()
        if not selection:
            return
        artist = self.library_artist_rows[selection[0]]
        self.clear_library_albums()
        self.library_album_rows = albums_for_artist(self.library_data, artist.get("artist_key", ""))
        for row in self.library_album_rows:
            self.library_album_tree.insert(
                "",
                tk.END,
                values=(
                    row.get("title", ""),
                    row.get("year", ""),
                    row.get("record_type", ""),
                    row.get("validation_status", ""),
                ),
            )
        self.set_library_detail({})

    def on_library_album_selected(self, event=None):
        selection = self.library_album_tree.selection()
        if not selection:
            return
        index = self.library_album_tree.index(selection[0])
        if index >= len(self.library_album_rows):
            return
        album_id = self.library_album_rows[index].get("album_id", "")
        self.library_selected_album = album_details(self.library_data, album_id)
        self.set_library_detail(self.library_selected_album)

    def set_library_detail(self, details: dict):
        artwork = details.get("artwork", {}) if details else {}
        signals = details.get("archive_strength_signals", {}) if details else {}
        status = details.get("album_status", {}) if details else {}
        status_items = status.get("items", {})
        counts = details.get("artifacts", {}).get("counts", {}) if details else {}
        lines = []
        if details:
            urls = artwork.get("urls", {}) if isinstance(artwork.get("urls"), dict) else {}
            readiness = details.get("archive_readiness", {})
            metadata_detail = details.get("metadata_detail", {})
            cached_fields = metadata_detail.get("cached_fields", {})
            missing_fields = metadata_detail.get("missing_fields", [])
            lines = [
                details.get("title", ""),
                f"Artist: {details.get('artist', '')}",
                f"Archive Folder: {details.get('archive_folder', '')}",
                f"Archive Path: {details.get('archive_path', '')}",
                f"Archive Path Confidence: {details.get('archive_path_confidence', 'UNKNOWN')}",
                f"Year: {details.get('year', '')}",
                f"Release Date: {details.get('release_date', '')}",
                f"Label: {details.get('label', '')}",
                f"Genres: {', '.join(details.get('genres', []))}",
                f"Track Count: {details.get('track_count', '')}",
                f"Duration: {details.get('duration', '')}",
                f"Lifecycle State: {details.get('lifecycle_state', '')}",
                f"Identity Confidence: {details.get('identity_confidence', '')}",
                f"Validation Status: {details.get('validation_status', '')}",
                f"Metadata Status: {details.get('metadata_status', '')}",
                f"Metadata Coverage: {sum(1 for value in cached_fields.values() if value)}/{len(cached_fields) or 5}",
                f"Cached Metadata Fields: {', '.join(field for field, present in cached_fields.items() if present)}",
                f"Missing Metadata Fields: {', '.join(missing_fields)}",
                f"Archive Strength Signals: {', '.join(k for k, v in signals.items() if v)}",
                f"Artwork URL: {artwork.get('url') or urls.get('medium') or urls.get('big') or urls.get('xl') or ''}",
                f"Artwork Identity: {artwork.get('md5_image') or artwork.get('cover_identity') or ''}",
                "",
                "Album Status:",
                f"Validation: {status_items.get('validation', 'Unknown')}",
                f"NFO: {status_items.get('nfo', 'Unknown')} ({counts.get('nfo', 0)})",
                f"SFV: {status_items.get('sfv', 'Unknown')} ({counts.get('sfv', 0)})",
                f"Playlist: {status_items.get('playlist', 'Unknown')} ({counts.get('playlist', 0)})",
                f"Artwork: {status_items.get('artwork', 'Unknown')} ({counts.get('artwork', 0)})",
                f"Metadata: {status_items.get('metadata', 'Unknown')}",
                f"Album Health: {status.get('health_percent', 0)}%",
                "",
                "Archive Readiness:",
                f"State: {readiness.get('state', 'UNKNOWN')}",
                f"Reason: {readiness.get('reason', '')}",
                f"Confidence: {readiness.get('confidence', '')}",
                f"Explanation: {', '.join(readiness.get('explanation', []))}",
            ]
        self.library_detail_text.config(state="normal")
        self.library_detail_text.delete("1.0", tk.END)
        self.library_detail_text.insert(tk.END, "\n".join(lines) or "Select an album.")
        self.library_detail_text.config(state="disabled")

    def run_library_album_operation(self, operation_id: str):
        target, reason = album_archive_operation_target(self.library_selected_album)
        if not target:
            self.library_operation_result_var.set(f"Failure: {reason}")
            return
        album_id = self.library_selected_album.get("album_id", "")
        result = run_operation(operation_id, target, self.audio_settings, OPERATION_HISTORY_FILE)
        self.library_operation_result_var.set(f"{result['result'].title()}: {result['message']}")
        self.refresh_library()
        if album_id:
            self.library_selected_album = album_details(self.library_data, album_id)
            self.set_library_detail(self.library_selected_album)
        self.refresh_audio_dashboard()

    def refresh_opportunities(self):
        if not hasattr(self, "opportunity_tree"):
            return
        if not self.library_data:
            self.refresh_library()
        self.opportunity_rows = generate_opportunities(self.library_data)
        self.apply_opportunity_filters()

    def apply_opportunity_filters(self):
        self.filtered_opportunity_rows = filter_opportunities(
            self.opportunity_rows,
            category=self.opportunity_category_var.get(),
            priority=self.opportunity_priority_var.get(),
            artist=self.opportunity_artist_var.get(),
        )
        self.render_opportunities()

    def render_opportunities(self):
        summary = opportunity_summary(self.filtered_opportunity_rows)
        top_categories = ", ".join(f"{category}: {count}" for category, count in summary.get("top_categories", [])[:3])
        values = {
            "total": summary.get("total", 0),
            "high": summary.get("high", 0),
            "medium": summary.get("medium", 0),
            "low": summary.get("low", 0),
            "top_categories": top_categories,
        }
        for key, label in self.opportunity_summary_labels.items():
            label.config(text=str(values.get(key, 0)))

        for item in self.opportunity_tree.get_children():
            self.opportunity_tree.delete(item)
        for idx, row in enumerate(self.filtered_opportunity_rows):
            self.opportunity_tree.insert(
                "",
                tk.END,
                iid=str(idx),
                values=(
                    row.get("category", ""),
                    row.get("priority", ""),
                    row.get("artist", ""),
                    row.get("album", ""),
                    row.get("recommended_action", ""),
                ),
            )

    def sort_opportunities(self, column: str):
        self.filtered_opportunity_rows.sort(key=lambda row: str(row.get(column, "")).lower())
        self.render_opportunities()

    def open_selected_opportunity_album(self):
        selection = self.opportunity_tree.selection()
        if not selection:
            return
        index = int(selection[0])
        if index >= len(self.filtered_opportunity_rows):
            return
        album_id = self.filtered_opportunity_rows[index].get("album_id", "")
        details = album_details(self.library_data, album_id)
        if not details:
            self.status.config(text="Opportunity album is not available in Library data")
            return
        self.tabs.select(self.library_tab)
        artist_key = details.get("artist_key", "")
        for idx, row in enumerate(self.library_artist_rows):
            if row.get("artist_key") == artist_key:
                self.library_artist_list.selection_clear(0, tk.END)
                self.library_artist_list.selection_set(idx)
                self.library_artist_list.see(idx)
                self.on_library_artist_selected()
                break
        for item in self.library_album_tree.get_children():
            album_index = self.library_album_tree.index(item)
            if album_index < len(self.library_album_rows) and self.library_album_rows[album_index].get("album_id") == album_id:
                self.library_album_tree.selection_set(item)
                self.library_album_tree.see(item)
                self.on_library_album_selected()
                self.status.config(text="Opened opportunity album in Library")
                return
        self.set_library_detail(details)
        self.status.config(text="Opened opportunity album details")

    def selected_opportunities(self) -> list[dict]:
        selection = self.opportunity_tree.selection()
        if not selection:
            return list(self.filtered_opportunity_rows)
        rows = []
        for item in selection:
            index = int(item)
            if index < len(self.filtered_opportunity_rows):
                rows.append(self.filtered_opportunity_rows[index])
        return rows

    def run_opportunity_batch(self, operation_id: str):
        opportunities = self.selected_opportunities()
        counts = available_batch_operations(opportunities)
        if counts.get(operation_id, 0) == 0:
            self.batch_progress_var.set(f"No eligible opportunities for {operation_id}.")
            return

        targets = collect_album_targets(operation_id, opportunities, self.library_data)
        target_count = sum(1 for target in targets if target.get("eligible"))
        if target_count == 0:
            self.batch_progress_var.set("No archive paths available for this batch.")
            return
        if operation_id != "open_album_folder":
            ok = messagebox.askyesno(
                "Confirm Batch Operation",
                f"Operation: {operation_id}\nAlbum Count: {len(targets)}\nTarget Count: {target_count}",
            )
            if not ok:
                self.batch_progress_var.set("Batch cancelled.")
                return

        def update_progress(progress):
            self.batch_progress_var.set(
                f"Total: {progress['total']}  Completed: {progress['completed']}  Current: {progress['current_item']}"
            )

        summary = run_batch_operation(
            operation_id,
            targets,
            self.audio_settings,
            OPERATION_HISTORY_FILE,
            progress=update_progress,
        )
        write_batch_operation_report(summary, BASE_DIR / "reports")
        self.batch_progress_var.set(
            f"Completed {summary['operation']}: {summary['successes']} succeeded, "
            f"{summary['failures']} failed, {summary.get('skipped', 0)} skipped."
        )
        self.refresh_audio_dashboard()

    def refresh_hub_opportunities(self):
        if not hasattr(self, "hub_category_list"):
            return
        if not self.library_data:
            self.refresh_library()
        opportunities = derive_hub_opportunities(self.library_data)
        self.hub_opportunity_groups = group_hub_opportunities(opportunities)
        summary = hub_opportunity_summary(opportunities)
        for key, label in self.hub_summary_labels.items():
            label.config(text=str(summary["by_category"].get(key, 0)))
        self.hub_category_list.delete(0, tk.END)
        for category in HUB_OPPORTUNITY_CATEGORIES:
            self.hub_category_list.insert(tk.END, f"{category} ({summary['by_category'].get(category, 0)})")
        current = self.hub_selected_category.get()
        index = HUB_OPPORTUNITY_CATEGORIES.index(current) if current in HUB_OPPORTUNITY_CATEGORIES else 0
        self.hub_category_list.selection_set(index)
        self.hub_category_list.see(index)
        self.render_hub_category(current)

    def on_hub_category_selected(self, event=None):
        selection = self.hub_category_list.curselection()
        if not selection:
            return
        category = HUB_OPPORTUNITY_CATEGORIES[selection[0]]
        self.hub_selected_category.set(category)
        self.render_hub_category(category)

    def render_hub_category(self, category: str):
        self.hub_opportunity_rows = self.hub_opportunity_groups.get(category, [])
        for item in self.hub_album_tree.get_children():
            self.hub_album_tree.delete(item)
        for index, row in enumerate(self.hub_opportunity_rows):
            self.hub_album_tree.insert(
                "",
                tk.END,
                iid=str(index),
                values=(
                    row.get("artist", ""),
                    row.get("album", ""),
                    row.get("lifecycle_state", ""),
                    row.get("archive_readiness", ""),
                    row.get("priority", ""),
                    row.get("reason", ""),
                ),
            )

    def selected_hub_opportunity(self) -> dict:
        selection = self.hub_album_tree.selection()
        if not selection:
            return {}
        index = int(selection[0])
        if index >= len(self.hub_opportunity_rows):
            return {}
        return self.hub_opportunity_rows[index]

    def run_hub_opportunity_action(self, operation_id: str):
        opportunity = self.selected_hub_opportunity()
        if not opportunity:
            self.hub_action_result_var.set("Select an album first.")
            return
        details = album_details(self.library_data, opportunity.get("album_id", ""))
        target, reason = album_archive_operation_target(details)
        if operation_id == "refresh_metadata" and not target:
            target = opportunity.get("album_id", "")
        if not target:
            self.hub_action_result_var.set(f"Failure: {reason}")
            return
        result = run_operation(operation_id, target, self.audio_settings, OPERATION_HISTORY_FILE)
        self.hub_action_result_var.set(f"{result['result'].title()}: {result['message']}")
        self.refresh_audio_dashboard()

    def save_audio_settings(self):
        for (section, key), var in self.audio_setting_vars.items():
            self.audio_settings.setdefault(section, {})[key] = var.get()
        save_audio_division_settings(AUDIO_DIVISION_SETTINGS_FILE, self.audio_settings)
        self.status.config(text="Audio Division settings saved")

    def reload_audio_settings(self):
        self.audio_settings = load_audio_division_settings(AUDIO_DIVISION_SETTINGS_FILE)
        for (section, key), var in self.audio_setting_vars.items():
            var.set(self.audio_settings.get(section, {}).get(key, ""))
        self.status.config(text="Audio Division settings reloaded")

    # ---------------- Sorting ----------------

    def on_sort_change(self, event):
        self.sort_mode = (
            "last_added"
            if self.sort_box.get() == "Last added"
            else "alphabetical"
        )
        self.refresh_artists()

    def get_sorted_artists(self):
        files = [p.name for p in ARTISTS_DIR.glob("*.txt")]
        meta = load_meta()["created"]
        if self.sort_mode == "last_added":
            return sorted(files, key=lambda f: meta.get(f, ""), reverse=True)
        return sorted(files)

    # ---------------- Modes ----------------

    def show_artist_mode(self):
        self.main_mode = "artist"
        self.main_label.config(text="Artist file")
        self.main_editor.config(state="disabled")

    def show_inbox_mode(self):
        self.main_mode = "inbox"
        self.main_label.config(text="Inbox")
        self.main_editor.config(state="normal")
        self.load_inbox()

    # ---------------- Artist ----------------

    def refresh_artists(self):
        ARTISTS_DIR.mkdir(parents=True, exist_ok=True)
        self.artist_list.delete(0, tk.END)
        for name in self.get_sorted_artists():
            self.artist_list.insert(tk.END, name)

    def open_selected_artist(self, event=None):
        selection = self.artist_list.curselection()
        if not selection:
            return

        filename = self.artist_list.get(selection[0])
        path = ARTISTS_DIR / filename

        self.show_artist_mode()
        self.main_editor.config(state="normal")
        self.main_editor.delete("1.0", tk.END)

        if path.exists():
            self.main_editor.insert(tk.END, path.read_text(encoding="utf-8"))
            record_created(filename)

        self.main_editor.config(state="disabled")

    # ---------------- Inbox ----------------

    def load_inbox(self):
        self.main_editor.delete("1.0", tk.END)
        if INBOX.exists():
            self.main_editor.insert(tk.END, INBOX.read_text(encoding="utf-8"))

    def save_inbox(self):
        if self.main_mode != "inbox":
            return
        DATA_DIR.mkdir(parents=True, exist_ok=True)
        INBOX.write_text(self.main_editor.get("1.0", tk.END), encoding="utf-8")

    # ---------------- Grep helpers ----------------

    def grep_section(self, section_name: str):
        if self.main_mode != "artist":
            messagebox.showwarning("No artist selected", "Open an artist file first.")
            return

        lines = self.main_editor.get("1.0", tk.END).splitlines()
        collecting = False
        found = []

        header = f"# {section_name}"

        for line in lines:
            line = line.rstrip()

            if line.startswith("# "):
                collecting = line == header
                continue

            if not collecting or not line.startswith("http"):
                continue

            if not self.include_live.get() and "LIVE?" in line:
                continue

            if not self.include_compilations.get() and "COMPILATION" in line:
                continue

            found.append(line)

        if not found:
            messagebox.showinfo(
                "No matches", f"No matching links in section '{section_name}'."
            )
            return

        for entry in found:
            self.custom_editor.insert(tk.END, entry + "\n")

        self.status.config(text=f"Added {len(found)} {section_name} link(s)")

    # ---------------- Queue helpers ----------------

    def send_selected_link_to_queue(self):
        if self.main_mode != "artist":
            return

        try:
            text = self.main_editor.get(tk.SEL_FIRST, tk.SEL_LAST)
        except tk.TclError:
            index = self.main_editor.index(tk.INSERT)
            text = self.main_editor.get(
                f"{index.split('.')[0]}.0", f"{index.split('.')[0]}.end"
            )

        for line in text.splitlines():
            if line.strip().startswith("http"):
                self.custom_editor.insert(tk.END, line.strip() + "\n")

    def load_custom_queue(self):
        self.custom_editor.delete("1.0", tk.END)
        if STREAMRIP_QUEUE.exists():
            self.custom_editor.insert(tk.END, STREAMRIP_QUEUE.read_text())

    def send_to_streamrip(self):
        raw_text = self.custom_editor.get("1.0", tk.END)

        links = []
        for line in raw_text.splitlines():
            line = line.strip()
            if not line.startswith("http"):
                continue
            links.append(line.split()[0])

        if not links:
            messagebox.showwarning(
                "No links", "No valid URLs found to send to streamrip."
            )
            return

        STREAMRIP_QUEUE.write_text("\n".join(links) + "\n", encoding="utf-8")

        SHIPPED_DIR.mkdir(parents=True, exist_ok=True)
        ts = datetime.now().strftime("%Y-%m-%d_%H-%M")
        archive = SHIPPED_DIR / f"{ts}_{len(links)}links_download_que.txt"
        archive.write_text("\n".join(links) + "\n", encoding="utf-8")

        subprocess.Popen(
            [
                "x-terminal-emulator",
                "-e",
                str(STREAMRIP_BIN),
                "file",
                str(STREAMRIP_QUEUE),
            ]
        )

        self.status.config(
            text=f"Sent {len(links)} links • archived as {archive.name}"
        )

    # ---------------- Curator (threaded) ----------------

    def run_from_inbox(self):
        self.run_button.config(state="disabled")
        self.status.config(text="Running curator…")

        thread = threading.Thread(target=self._run_curator_thread, daemon=True)
        thread.start()

    def _run_curator_thread(self):
        try:
            self.show_inbox_mode()
            self.save_inbox()

            result = run_curation(INBOX, LOG, ARTISTS_DIR)
            stats = result["stats"]

            self.after(
                0,
                lambda: messagebox.showinfo(
                    "Done",
                    (
                        "Curator finished.\n\n"
                        f'Albums passed: {stats["albums_passed"]}\n'
                        f'Artists expanded: {stats["artists_expanded"]}\n'
                        f'Artists skipped: {stats["artists_skipped"]}'
                    ),
                ),
            )
            self.after(0, self.refresh_artists)
        finally:
            self.after(0, lambda: self.run_button.config(state="normal"))
            self.after(0, lambda: self.status.config(text="Idle"))


def main():
    app = DeezerCuratorGUI()
    app.mainloop()


if __name__ == "__main__":
    main()
