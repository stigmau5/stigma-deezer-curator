import tkinter as tk
from tkinter import ttk, messagebox
from pathlib import Path
from datetime import datetime
import subprocess
import json
import threading
import webbrowser

from curator.curate import run_curation
from audio_division.dashboard import dashboard_summary, load_json
from audio_division.settings import (
    load_audio_division_settings,
    save_audio_division_settings,
)
from audio_division.layout_state import (
    capture_pane_positions,
    default_window_geometry,
    deserialize_pane_positions,
    restore_pane_positions,
    serialize_pane_positions,
    valid_window_geometry,
)
from audio_division.operation_runner import run_operation
from audio_division.playback import run_playback_action
from audio_division.archive_reconciliation import reconcile_archive, write_archive_reconciliation_report
from audio_division.archive_audit import audit_archive, write_archive_audit
from audio_division.revalidation import revalidate_archive, write_archive_revalidation_report
from audio_division.batch_operations import (
    available_batch_operations,
    collect_album_targets,
    run_batch_operation,
    write_batch_operation_report,
)
from audio_division.album_workspace import album_workspace
from audio_division.artwork_browser import artwork_items, filter_artwork_items
from audio_division.cover_widget import CoverWidget
from audio_division.physical_archive import (
    albums_for_archive_artist,
    archive_letter_iid,
    archive_tree,
    archive_tree_expansion,
    build_archive_albums,
    filter_archive_albums,
)
from audio_division.library import (
    album_archive_operation_target,
    album_details,
    albums_for_artist,
    library_from_data_dir,
)
from audio_division.selection_state import (
    archive_album_key,
    capture_archive_selection,
    selected_album_index,
)
from audio_division.processing_queue import (
    load_processing_queue,
    queue_for_processing,
    save_processing_queue,
)
from audio_division.closed_loop_monitor import queue_album_payload
from audio_division.incoming_projection import incoming_releases
from audio_division.audio_division_wrapper import process_validated_release
from audio_division.validator_runner import run_validator_for_release
from audio_division.pipeline_controller import recommend_next_action
from audio_division.pipeline_dashboard import PIPELINE_STAGES, build_pipeline_dashboard
from audio_division.tool_discovery import discover_configured_tools
from audio_division.maintenance import (
    maintenance_action_target,
    maintenance_albums,
    maintenance_counts,
    maintenance_operation_for_album,
    maintenance_summaries,
)
from audio_division.metadata_enrichment import rebuild_metadata_enrichment
from audio_division.acquisition_queue import (
    load_acquisition_queue,
    queue_release,
    queue_rows,
    remove_queue_item,
    save_acquisition_queue,
)
from audio_division.artist_model import (
    release_line_map,
)
from audio_division.artist_presentation import (
    load_artist_presentation,
    load_artist_presentations,
    sort_artist_presentations,
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
AUDIO_DIVISION_SETTINGS_FILE = DATA_DIR / "audio_division_settings.json"
OPERATION_HISTORY_FILE = DATA_DIR / "operation_history.json"
PROCESSING_QUEUE_FILE = DATA_DIR / "processing_queue.json"
ACQUISITION_QUEUE_FILE = DATA_DIR / "acquisition_queue.json"
META_FILE = DATA_DIR / "artist_meta.json"

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


def human_status(value: str) -> str:
    text = str(value or "").strip()
    if not text:
        return ""
    display = {
        "READY_FOR_PROCESSING": "Ready to Process",
        "READY_FOR_VALIDATION": "Ready to Validate",
        "READY_TO_ACQUIRE": "Ready to Acquire",
        "ALREADY_DOWNLOADED": "Already Downloaded",
        "ALREADY_PROCESSING": "Already Processing",
        "NEEDS_METADATA": "Needs Metadata",
        "IDENTITY_REVIEW": "Identity Review",
        "AVAILABLE_NOT_CACHED": "Available, Not Cached",
        "WAITING VALIDATION": "Waiting Validation",
        "READY FOR PROCESSING": "Ready to Process",
    }
    mapped = display.get(text.upper())
    if mapped:
        return mapped
    normalized = text.replace("_", " ").replace("-", " ").lower()
    words = []
    for word in normalized.split():
        if word in {"to", "for", "in", "on"}:
            words.append(word)
        else:
            words.append(word.capitalize())
    return " ".join(words)


class Tooltip:
    def __init__(self, widget, text: str = ""):
        self.widget = widget
        self.text = text
        self.window = None
        widget.bind("<Enter>", self.show)
        widget.bind("<Leave>", self.hide)

    def set_text(self, text: str):
        self.text = text

    def show(self, event=None):
        if not self.text or self.window is not None:
            return
        x = self.widget.winfo_rootx() + 20
        y = self.widget.winfo_rooty() + self.widget.winfo_height() + 4
        self.window = tk.Toplevel(self.widget)
        self.window.wm_overrideredirect(True)
        self.window.wm_geometry(f"+{x}+{y}")
        label = ttk.Label(self.window, text=self.text, relief="solid", padding=4, wraplength=900)
        label.pack()

    def hide(self, event=None):
        if self.window is not None:
            self.window.destroy()
            self.window = None


# ---------------- GUI ----------------


class DeezerCuratorGUI(tk.Tk):
    def __init__(self):
        super().__init__()

        self.main_mode = "artist"  # artist | inbox
        self.sort_mode = "alphabetical"
        self.current_artist_filename = None
        self.current_artist_model = None
        self.current_artist_presentation = None
        self.artist_presentations = []
        self.artist_release_lines = {}
        self.acquisition_rows = []
        self.selected_acquisition_release = None
        self.selected_acquisition_release_id = ""
        self.acquisition_sort_column = ""
        self.acquisition_sort_reverse = False
        self.acquisition_queue = load_acquisition_queue(ACQUISITION_QUEUE_FILE)
        self.acquisition_queue_rows: list[dict] = []

        self.audio_settings = load_audio_division_settings(AUDIO_DIVISION_SETTINGS_FILE)
        self.audio_setting_vars: dict[tuple[str, str], tk.StringVar] = {}
        self.tool_status_labels: dict[str, ttk.Label] = {}
        self.tool_resolved_labels: dict[str, ttk.Label] = {}
        self.tool_version_labels: dict[str, ttk.Label] = {}
        self.layout_panes: dict[str, ttk.Panedwindow] = {}
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
        self.library_presentation_labels: dict[tuple[str, str], ttk.Label] = {}
        self.library_thumbnail_image = None
        self.artwork_rows: list[dict] = []
        self.filtered_artwork_rows: list[dict] = []
        self.artwork_artist_var = tk.StringVar()
        self.artwork_album_var = tk.StringVar()
        self.artwork_status_var = tk.StringVar(value="Select an album cover.")
        self.archive_albums: list[dict] = []
        self.filtered_archive_albums: list[dict] = []
        self.archive_artist_rows: list[dict] = []
        self.archive_album_rows: list[dict] = []
        self.archive_selected_album: dict = {}
        self.archive_artist_var = tk.StringVar()
        self.archive_album_var = tk.StringVar()
        self.archive_operation_result_var = tk.StringVar()
        self.archive_audit_status_var = tk.StringVar(value="")
        self.archive_revalidation_status_var = tk.StringVar(value="")
        self._archive_audit_running = False
        self._archive_revalidation_running = False
        self.archive_current_nfo: dict = {}
        self.library_current_nfo: dict = {}
        self.processing_queue = load_processing_queue(PROCESSING_QUEUE_FILE)
        self.processing_queue_rows: list[dict] = []
        self.closed_loop_rows: list[dict] = []
        self.pipeline_stage_labels: dict[str, ttk.Label] = {}
        self.pipeline_stage_trees: dict[str, ttk.Treeview] = {}
        self.maintenance_rows: list[dict] = []
        self.maintenance_album_rows: list[dict] = []
        self.selected_maintenance_id = ""
        self.maintenance_summary_labels: dict[str, ttk.Label] = {}
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

        self.title("STiGMA Archive Hub — v0.3.1")
        self.minsize(1100, 650)
        self.geometry(self._initial_window_geometry())
        self.protocol("WM_DELETE_WINDOW", self.on_close)

        self._build_layout()
        self.after(150, self.restore_layout_state)
        self.refresh_artists()
        self.load_inbox()
        self.load_custom_queue()

    # ---------------- UI ----------------

    def _build_layout(self):
        self.tabs = ttk.Notebook(self)
        self.tabs.pack(fill="both", expand=True)

        pipeline_tab = ttk.Frame(self.tabs, padding=10)
        self.tabs.add(pipeline_tab, text="Pipeline")

        curator_tab = ttk.Frame(self.tabs)
        self.tabs.add(curator_tab, text="Curator")

        archive_tab = ttk.Frame(self.tabs, padding=10)
        self.tabs.add(archive_tab, text="Archive")
        self.archive_tab = archive_tab

        maintenance_tab = ttk.Frame(self.tabs, padding=10)
        self.tabs.add(maintenance_tab, text="Maintenance")

        settings_tab = ttk.Frame(self.tabs, padding=10)
        self.tabs.add(settings_tab, text="Settings")

        self.archive_sections = ttk.Notebook(archive_tab)
        self.archive_sections.pack(fill="both", expand=True)

        physical_archive_tab = ttk.Frame(self.archive_sections, padding=6)
        self.archive_sections.add(physical_archive_tab, text="Physical Archive")

        library_tab = ttk.Frame(self.archive_sections, padding=6)
        self.archive_sections.add(library_tab, text="Library")
        self.library_tab = library_tab

        artwork_tab = ttk.Frame(self.archive_sections, padding=6)
        self.archive_sections.add(artwork_tab, text="Artwork")

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
        self.artist_list.bind("<Button-3>", self.show_artist_menu)

        # ===== CENTER =====
        center = ttk.Frame(main, padding=6)
        main.add(center, weight=2)

        self.main_label = ttk.Label(center, text="Acquisition")
        self.main_label.pack(anchor="w")

        columns = (
            "status",
            "album",
            "year",
            "type",
            "archive",
            "lifecycle",
            "validation",
            "metadata",
            "identity",
        )
        self.acquisition_tree = ttk.Treeview(
            center,
            columns=columns,
            show="headings",
            selectmode="extended",
        )
        for column, title, width in (
            ("status", "Status", 130),
            ("album", "Album", 300),
            ("year", "Year", 70),
            ("type", "Type", 80),
            ("archive", "Archive", 100),
            ("lifecycle", "Lifecycle", 110),
            ("validation", "Validation", 110),
            ("metadata", "Metadata", 150),
            ("identity", "Identity Confidence", 135),
        ):
            self.acquisition_tree.heading(
                column,
                text=title,
                command=lambda column=column: self.sort_acquisition_grid(column),
            )
            self.acquisition_tree.column(column, width=width, anchor="w")
        self.acquisition_tree.pack(fill="both", expand=True)
        self.acquisition_tree.bind("<<TreeviewSelect>>", self.on_acquisition_selected)
        self.acquisition_tree.bind("<Double-1>", self.on_acquisition_double_click)
        self.acquisition_tree.bind("<Button-3>", self.show_acquisition_menu)
        self.acquisition_tree.bind("<Control-Right>", self.acquire_selected_release)
        self.acquisition_tree.bind("<Return>", self.on_acquisition_double_click)
        self.acquisition_tree.bind("<Control-c>", lambda event: self.copy_selected_release_link())
        self.acquisition_tree.bind("<Control-C>", lambda event: self.copy_selected_release_link())

        self.main_editor = tk.Text(center, wrap="none")

        # ===== RIGHT =====
        right = ttk.Frame(main, padding=6)
        main.add(right, weight=2)

        ttk.Label(right, text="Acquisition Worklist").pack(anchor="w")
        queue_columns = ("state", "artist", "album", "type", "source", "album_id")
        self.queue_tree = ttk.Treeview(
            right,
            columns=queue_columns,
            show="headings",
            selectmode="extended",
        )
        for column, title, width in (
            ("state", "State", 135),
            ("artist", "Artist", 170),
            ("album", "Album", 260),
            ("type", "Type", 80),
            ("source", "Source", 90),
            ("album_id", "Album ID", 110),
        ):
            self.queue_tree.heading(column, text=title)
            self.queue_tree.column(column, width=width, anchor="w")
        self.queue_tree.pack(fill="both", expand=True)
        self.queue_tree.bind("<Double-1>", self.show_queue_release)
        self.queue_tree.bind("<Button-3>", self.show_queue_menu)

        # ===== BOTTOM =====
        bottom = ttk.Frame(curator_tab, padding=8)
        bottom.pack(fill="x")

        inbox_group = ttk.LabelFrame(bottom, text="Inbox", padding=(6, 3))
        inbox_group.pack(side="left", padx=(0, 8))
        ttk.Button(inbox_group, text="Show Inbox", command=self.show_inbox_mode).pack(side="left", padx=2)
        ttk.Button(inbox_group, text="Show Artist", command=self.show_artist_mode).pack(side="left", padx=2)
        ttk.Button(inbox_group, text="Save Inbox", command=self.save_inbox).pack(side="left", padx=2)
        self.run_button = ttk.Button(inbox_group, text="Run Curator", command=self.run_from_inbox)
        self.run_button.pack(side="left", padx=2)

        acquire_group = ttk.LabelFrame(bottom, text="Acquire", padding=(6, 3))
        acquire_group.pack(side="left", padx=(0, 8))
        ttk.Button(acquire_group, text="Acquire Selected", command=self.acquire_selected_release).pack(side="left", padx=2)

        tools_group = ttk.LabelFrame(bottom, text="Tools", padding=(6, 3))
        tools_group.pack(side="left", padx=(0, 8))
        ttk.Button(tools_group, text="Show Identity", command=self.show_selected_release_identity).pack(side="left", padx=2)
        ttk.Button(tools_group, text="Copy Deezer Link", command=self.copy_selected_release_link).pack(side="left", padx=2)

        self.status = ttk.Label(bottom, text="Idle")
        self.status.pack(side="right")

        self._build_archive_tab(physical_archive_tab)
        self._build_library_tab(library_tab)
        self._build_artwork_tab(artwork_tab)
        self._build_pipeline_tab(pipeline_tab)
        self._build_audio_dashboard(maintenance_tab)
        self._build_settings_tab(settings_tab)

    def _initial_window_geometry(self) -> str:
        saved = valid_window_geometry(self.audio_settings.get("ui", {}).get("window_geometry", ""))
        if saved:
            return saved
        return default_window_geometry(self.winfo_screenwidth(), self.winfo_screenheight())

    def restore_layout_state(self):
        ui = self.audio_settings.get("ui", {})
        for name, pane in self.layout_panes.items():
            positions = deserialize_pane_positions(ui.get(f"{name}_panes", ""))
            if positions:
                restore_pane_positions(pane, positions)

    def save_layout_state(self):
        ui = self.audio_settings.setdefault("ui", {})
        ui["window_geometry"] = self.geometry()
        for name, pane in self.layout_panes.items():
            positions = capture_pane_positions(pane)
            if positions:
                ui[f"{name}_panes"] = serialize_pane_positions(positions)
        save_audio_division_settings(AUDIO_DIVISION_SETTINGS_FILE, self.audio_settings)

    def on_close(self):
        self.save_layout_state()
        self.destroy()

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
        self.layout_panes["library_main"] = browser

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
        browser.add(details_frame, weight=4)
        self.library_detail_container = ttk.Frame(details_frame)
        self.library_detail_container.pack(fill="both", expand=True)
        self._build_library_detail_sections(self.library_detail_container)

        operations = ttk.LabelFrame(details_frame, text="Album Operations", padding=6)
        operations.pack(fill="x", pady=(8, 0))
        buttons = ttk.Frame(operations)
        buttons.pack(fill="x")
        ttk.Button(buttons, text="Revalidate", command=lambda: self.run_library_album_operation("revalidate_album")).pack(side="left")
        ttk.Button(buttons, text="Generate NFO", command=lambda: self.run_library_album_operation("generate_nfo")).pack(side="left", padx=(6, 0))
        ttk.Button(buttons, text="Generate SFV", command=lambda: self.run_library_album_operation("generate_sfv")).pack(side="left", padx=(6, 0))
        ttk.Button(buttons, text="Open Folder", command=lambda: self.run_library_album_operation("open_album_folder")).pack(side="left", padx=(6, 0))
        ttk.Button(buttons, text="Play Album", command=lambda: self.run_library_album_playback("play_album")).pack(side="left", padx=(6, 0))
        ttk.Button(buttons, text="Play Playlist", command=lambda: self.run_library_album_playback("play_playlist")).pack(side="left", padx=(6, 0))
        ttk.Label(operations, textvariable=self.library_operation_result_var).pack(anchor="w", pady=(6, 0))

        self.refresh_library()

    def _build_archive_tab(self, parent):
        toolbar = ttk.Frame(parent)
        toolbar.pack(fill="x", pady=(0, 8))
        ttk.Button(toolbar, text="Refresh", command=self.refresh_archive_browser).pack(side="left")
        ttk.Button(toolbar, text="Refresh Metadata", command=self.refresh_archive_metadata).pack(side="left", padx=(6, 0))
        self.archive_audit_button = ttk.Button(toolbar, text="Run Audit", command=self.run_archive_audit)
        self.archive_audit_button.pack(side="left", padx=(6, 0))
        self.archive_revalidation_button = ttk.Button(toolbar, text="Revalidate Archive", command=self.run_archive_revalidation)
        self.archive_revalidation_button.pack(side="left", padx=(6, 0))
        ttk.Label(toolbar, textvariable=self.archive_audit_status_var).pack(side="left", padx=(8, 0))
        ttk.Label(toolbar, textvariable=self.archive_revalidation_status_var).pack(side="left", padx=(8, 0))
        ttk.Label(toolbar, text="Artist").pack(side="left", padx=(12, 4))
        artist_filter = ttk.Entry(toolbar, textvariable=self.archive_artist_var, width=24)
        artist_filter.pack(side="left")
        ttk.Label(toolbar, text="Album").pack(side="left", padx=(12, 4))
        album_filter = ttk.Entry(toolbar, textvariable=self.archive_album_var, width=24)
        album_filter.pack(side="left")
        artist_filter.bind("<KeyRelease>", lambda event: self.apply_archive_filters())
        album_filter.bind("<KeyRelease>", lambda event: self.apply_archive_filters())

        panes = ttk.Panedwindow(parent, orient="horizontal")
        panes.pack(fill="both", expand=True)
        self.layout_panes["archive_main"] = panes

        tree_frame = ttk.LabelFrame(panes, text="Archive Tree", padding=4)
        panes.add(tree_frame, weight=1)
        tree_toolbar = ttk.Frame(tree_frame)
        tree_toolbar.pack(fill="x", pady=(0, 4))
        ttk.Button(tree_toolbar, text="Expand All", command=lambda: self.set_archive_tree_expansion("expand_all")).pack(side="left")
        ttk.Button(tree_toolbar, text="Collapse All", command=lambda: self.set_archive_tree_expansion("collapse_all")).pack(side="left", padx=(4, 0))
        ttk.Button(tree_toolbar, text="Expand Artist", command=lambda: self.set_archive_tree_expansion("expand_artist")).pack(side="left", padx=(4, 0))
        self.archive_tree = ttk.Treeview(tree_frame, show="tree", selectmode="browse")
        self.archive_tree.pack(fill="both", expand=True)
        self.archive_tree.bind("<<TreeviewSelect>>", self.on_archive_artist_selected)

        album_frame = ttk.LabelFrame(panes, text="Albums", padding=4)
        panes.add(album_frame, weight=2)
        self.archive_album_tree = ttk.Treeview(
            album_frame,
            columns=("album", "year", "validation", "readiness"),
            show="headings",
            selectmode="browse",
        )
        for column, title, width in (
            ("album", "Album", 280),
            ("year", "Year", 70),
            ("validation", "Validation", 100),
            ("readiness", "Readiness", 140),
        ):
            self.archive_album_tree.heading(column, text=title)
            self.archive_album_tree.column(column, width=width, anchor="w")
        self.archive_album_tree.pack(fill="both", expand=True)
        self.archive_album_tree.bind("<<TreeviewSelect>>", self.on_archive_album_selected)

        processing = ttk.LabelFrame(album_frame, text="Closed Loop Monitor", padding=4)
        processing.pack(fill="x", pady=(6, 0))
        self.processing_queue_tree = ttk.Treeview(
            processing,
            columns=("artist", "album", "source", "folder", "state", "next_action"),
            show="headings",
            height=5,
            selectmode="browse",
        )
        for column, title, width in (
            ("artist", "Artist", 140),
            ("album", "Album", 210),
            ("source", "Source", 80),
            ("folder", "Folder", 220),
            ("state", "Current State", 120),
            ("next_action", "Next Action", 120),
        ):
            self.processing_queue_tree.heading(column, text=title)
            self.processing_queue_tree.column(column, width=width, anchor="w")
        self.processing_queue_tree.pack(fill="x", expand=False)
        monitor_actions = ttk.Frame(processing)
        monitor_actions.pack(fill="x", pady=(4, 0))
        ttk.Button(monitor_actions, text="Open Folder", command=self.open_selected_incoming_folder).pack(side="left")
        ttk.Button(monitor_actions, text="Validate Download", command=self.validate_selected_incoming_release).pack(side="left", padx=(4, 0))
        ttk.Button(monitor_actions, text="Queue For Processing", command=self.queue_selected_incoming_album).pack(side="left", padx=(4, 0))

        maintenance = ttk.LabelFrame(album_frame, text="Maintenance Action Center", padding=4)
        maintenance.pack(fill="both", expand=True, pady=(6, 0))
        summary = ttk.Frame(maintenance)
        summary.pack(fill="x", pady=(0, 4))
        for key, title in (
            ("albums", "Albums"),
            ("artists", "Artists"),
            ("warnings", "Warnings"),
            ("downloaded", "Downloaded"),
            ("validated", "Validated"),
            ("ready_for_processing", "Ready For Processing"),
            ("archived", "Archived"),
            ("validation_coverage", "Validation Coverage"),
            ("documentation_coverage", "Documentation Coverage"),
        ):
            ttk.Label(summary, text=f"{title}:").pack(side="left", padx=(0, 3))
            label = ttk.Label(summary, text="0")
            label.pack(side="left", padx=(0, 10))
            self.maintenance_summary_labels[key] = label

        maintenance_panes = ttk.Panedwindow(maintenance, orient="vertical")
        maintenance_panes.pack(fill="both", expand=True)
        self.maintenance_tree = ttk.Treeview(
            maintenance_panes,
            columns=("category", "count"),
            show="headings",
            height=5,
            selectmode="browse",
        )
        for column, title, width in (("category", "Maintenance Area", 220), ("count", "Album Count", 90)):
            self.maintenance_tree.heading(column, text=title)
            self.maintenance_tree.column(column, width=width, anchor="w")
        maintenance_panes.add(self.maintenance_tree, weight=1)
        self.maintenance_tree.bind("<<TreeviewSelect>>", self.on_maintenance_selected)

        self.maintenance_album_tree = ttk.Treeview(
            maintenance_panes,
            columns=("artist", "album", "priority", "operation", "reason"),
            show="headings",
            height=6,
            selectmode="browse",
        )
        for column, title, width in (
            ("artist", "Artist", 140),
            ("album", "Album", 220),
            ("priority", "Priority", 80),
            ("operation", "Next Action", 140),
            ("reason", "Reason", 260),
        ):
            self.maintenance_album_tree.heading(column, text=title)
            self.maintenance_album_tree.column(column, width=width, anchor="w")
        maintenance_panes.add(self.maintenance_album_tree, weight=2)
        self.maintenance_album_tree.bind("<Double-1>", lambda event: self.open_selected_maintenance_album())

        maintenance_actions = ttk.Frame(maintenance)
        maintenance_actions.pack(fill="x", pady=(4, 0))
        ttk.Button(maintenance_actions, text="Open Album", command=self.open_selected_maintenance_album).pack(side="left")
        ttk.Button(maintenance_actions, text="Run Recommended Action", command=self.run_recommended_maintenance_operation).pack(side="left", padx=(4, 0))
        ttk.Button(maintenance_actions, text="Validate Album", command=lambda: self.run_maintenance_operation("validate_album")).pack(side="left", padx=(4, 0))
        ttk.Button(maintenance_actions, text="Generate Documentation", command=lambda: self.run_maintenance_operation("generate_documentation")).pack(side="left", padx=(4, 0))
        ttk.Button(maintenance_actions, text="Open Folder", command=lambda: self.run_maintenance_operation("open_album_folder")).pack(side="left", padx=(4, 0))

        detail = ttk.LabelFrame(panes, text="Album Workspace", padding=6)
        panes.add(detail, weight=4)
        self._build_archive_workspace(detail)
        self.refresh_archive_browser()

    def _build_archive_workspace(self, parent):
        workspace = ttk.Panedwindow(parent, orient="vertical")
        workspace.pack(fill="both", expand=True)
        self.layout_panes["archive_workspace"] = workspace

        summary = ttk.Panedwindow(workspace, orient="horizontal")
        workspace.add(summary, weight=2)

        visual = ttk.Frame(summary)
        summary.add(visual, weight=1)
        cover_box = ttk.Frame(visual, width=280, height=240)
        cover_box.pack(fill="x", pady=(0, 8))
        cover_box.pack_propagate(False)
        self.archive_thumbnail = tk.Label(cover_box, text="No artwork", anchor="center", relief="sunken", bg="white")
        self.archive_thumbnail.pack(fill="both", expand=True)
        self.archive_cover_title = ttk.Label(visual, text="", anchor="center", justify="center", wraplength=280)
        self.archive_cover_title.pack(fill="x", pady=(0, 8))
        self.archive_artwork_status = ttk.Label(visual, text="Artwork: Unknown", wraplength=280)
        self.archive_artwork_status.pack(anchor="w", fill="x", pady=(0, 8))

        status = ttk.LabelFrame(visual, text="Status", padding=6)
        status.pack(fill="x", pady=(0, 8))
        self.archive_status_glance_labels: dict[str, ttk.Label] = {}
        for idx, field in enumerate(("Validation", "NFO", "SFV", "Playlist", "Artwork", "Readiness", "Health")):
            ttk.Label(status, text=f"{field}:").grid(row=idx // 2, column=(idx % 2) * 2, sticky="w", padx=(0, 6), pady=1)
            value = ttk.Label(status, text="Unknown")
            value.grid(row=idx // 2, column=(idx % 2) * 2 + 1, sticky="w", padx=(0, 10), pady=1)
            self.archive_status_glance_labels[field] = value

        integrity = ttk.LabelFrame(visual, text="Album Integrity", padding=6)
        integrity.pack(fill="x", pady=(0, 8))
        self.archive_integrity_text = tk.Text(integrity, height=9, wrap="word", font="TkFixedFont")
        self.archive_integrity_text.pack(fill="x")
        self.archive_integrity_text.config(state="disabled")

        operations = ttk.LabelFrame(visual, text="Operations", padding=6)
        operations.pack(fill="x")
        ttk.Button(operations, text="Revalidate", command=lambda: self.run_archive_album_operation("revalidate_album")).grid(row=0, column=0, sticky="ew", padx=(0, 3), pady=(0, 3))
        ttk.Button(operations, text="NFO", command=lambda: self.run_archive_album_operation("generate_nfo")).grid(row=0, column=1, sticky="ew", pady=(0, 3))
        ttk.Button(operations, text="SFV", command=lambda: self.run_archive_album_operation("generate_sfv")).grid(row=1, column=0, sticky="ew", padx=(0, 3))
        ttk.Button(operations, text="Folder", command=lambda: self.run_archive_album_operation("open_album_folder")).grid(row=1, column=1, sticky="ew")
        ttk.Button(operations, text="Play Album", command=lambda: self.run_archive_album_playback("play_album")).grid(row=2, column=0, sticky="ew", padx=(0, 3), pady=(3, 0))
        ttk.Button(operations, text="Playlist", command=lambda: self.run_archive_album_playback("play_playlist")).grid(row=2, column=1, sticky="ew", pady=(3, 0))
        ttk.Button(operations, text="Queue", command=self.queue_selected_archive_album_for_processing).grid(row=3, column=0, columnspan=2, sticky="ew", pady=(3, 0))
        ttk.Button(operations, text="Process Album", command=self.process_selected_archive_album).grid(row=4, column=0, columnspan=2, sticky="ew", pady=(3, 0))
        operations.columnconfigure(0, weight=1)
        operations.columnconfigure(1, weight=1)
        ttk.Label(operations, textvariable=self.archive_operation_result_var, wraplength=280).grid(row=5, column=0, columnspan=2, sticky="ew", pady=(6, 0))

        self.archive_presentation_labels: dict[tuple[str, str], ttk.Label] = {}
        details = ttk.Frame(summary)
        summary.add(details, weight=3)
        details.columnconfigure(0, weight=1)
        details.columnconfigure(1, weight=1)
        details.rowconfigure(1, weight=1)
        for index, (section_id, title, fields) in enumerate((
            ("overview", "Overview", ("Album title", "Artist", "Year", "Record type", "Lifecycle state", "Lifecycle evidence", "Lifecycle reason")),
            ("metadata", "Metadata", ("Label", "Genre", "Release date", "Track count", "Contributors", "Metadata status")),
            ("identity", "Identity", ("Album ID", "Identity confidence", "Archive path confidence", "Archive folder", "Archive path")),
        )):
            row = 0 if index < 2 else 1
            column = index if index < 2 else 0
            columnspan = 1 if index < 2 else 2
            frame = ttk.LabelFrame(details, text=title, padding=6)
            frame.grid(row=row, column=column, columnspan=columnspan, sticky="nsew", padx=(0 if column == 0 else 6, 0), pady=(0, 6))
            details.rowconfigure(row, weight=1)
            for field_row, field in enumerate(fields):
                ttk.Label(frame, text=f"{field}:").grid(row=field_row, column=0, sticky="nw", padx=(0, 6), pady=1)
                value = ttk.Label(frame, text="", wraplength=360)
                value.grid(row=field_row, column=1, sticky="ew", pady=1)
                frame.columnconfigure(1, weight=1)
                self.archive_presentation_labels[(section_id, field)] = value
                if section_id == "identity" and field == "Archive path":
                    self.archive_path_label = value
                    self.archive_path_tooltip = Tooltip(value)
        for hidden_field in ("Cached fields", "Missing fields"):
            self.archive_presentation_labels[("metadata", hidden_field)] = ttk.Label(details)
        related = ttk.LabelFrame(details, text="Related Albums", padding=6)
        related.grid(row=2, column=0, columnspan=2, sticky="nsew", pady=(0, 6))
        details.rowconfigure(2, weight=1)
        self.archive_relationships_text = tk.Text(related, height=7, wrap="word", font="TkFixedFont")
        self.archive_relationships_text.pack(fill="both", expand=True)
        self.archive_relationships_text.config(state="disabled")

        evidence = ttk.Panedwindow(workspace, orient="horizontal")
        workspace.add(evidence, weight=5)
        self.layout_panes["archive_evidence"] = evidence
        files_frame = ttk.LabelFrame(evidence, text="Files", padding=6)
        evidence.add(files_frame, weight=1)
        self.archive_files_text = self._build_scrolled_text(files_frame)
        self.archive_files_text.config(state="disabled")
        nfo_frame = ttk.LabelFrame(evidence, text="NFO", padding=6)
        evidence.add(nfo_frame, weight=2)
        self.archive_view_nfo_button = ttk.Button(
            nfo_frame,
            text="View NFO",
            command=lambda: self.show_nfo_viewer(self.archive_current_nfo, self.archive_selected_album),
        )
        self.archive_view_nfo_button.pack(anchor="w", pady=(0, 6))
        self.archive_nfo_text = self._build_scrolled_text(nfo_frame)
        self.archive_nfo_text.config(state="disabled")

    def _build_library_detail_sections(self, parent):
        workspace = ttk.Panedwindow(parent, orient="vertical")
        workspace.pack(fill="both", expand=True)
        self.layout_panes["library_workspace"] = workspace

        top = ttk.Frame(workspace)
        workspace.add(top, weight=1)
        cover_box = ttk.Frame(top, width=320, height=260)
        cover_box.pack(side="left", fill="y", padx=(0, 10))
        cover_box.pack_propagate(False)
        self.library_thumbnail = tk.Label(cover_box, text="No artwork", anchor="center", relief="sunken", bg="white")
        self.library_thumbnail.pack(fill="both", expand=True)
        album_header = ttk.Frame(top)
        album_header.pack(side="left", fill="both", expand=True)
        self.library_artwork_status = ttk.Label(album_header, text="Artwork: Unknown", wraplength=480)
        self.library_artwork_status.pack(anchor="w", pady=(0, 8))

        status = ttk.LabelFrame(album_header, text="Archive Status", padding=6)
        status.pack(fill="x")
        self.library_status_glance_labels: dict[str, ttk.Label] = {}
        for idx, field in enumerate(("Validation", "NFO", "SFV", "Playlist", "Artwork", "Readiness", "Health")):
            ttk.Label(status, text=f"{field}:").grid(row=idx // 2, column=(idx % 2) * 2, sticky="w", padx=(0, 6), pady=1)
            value = ttk.Label(status, text="Unknown")
            value.grid(row=idx // 2, column=(idx % 2) * 2 + 1, sticky="w", padx=(0, 18), pady=1)
            self.library_status_glance_labels[field] = value

        integrity = ttk.LabelFrame(album_header, text="Album Integrity", padding=6)
        integrity.pack(fill="x", pady=(8, 0))
        self.library_integrity_text = tk.Text(integrity, height=9, wrap="word", font="TkFixedFont")
        self.library_integrity_text.pack(fill="x")
        self.library_integrity_text.config(state="disabled")

        middle = ttk.Panedwindow(workspace, orient="horizontal")
        workspace.add(middle, weight=1)
        for section_id, title, fields in (
            ("overview", "Overview", ("Album title", "Artist", "Year", "Record type", "Lifecycle state", "Lifecycle evidence", "Lifecycle reason")),
            ("metadata", "Metadata", ("Label", "Genre", "Release date", "Track count", "Contributors", "Metadata status", "Cached fields", "Missing fields")),
            ("identity", "Identity", ("Album ID", "Identity confidence", "Archive path confidence", "Archive folder", "Archive path")),
        ):
            frame = ttk.LabelFrame(middle, text=title, padding=6)
            middle.add(frame, weight=1)
            for row, field in enumerate(fields):
                ttk.Label(frame, text=f"{field}:").grid(row=row, column=0, sticky="nw", padx=(0, 6), pady=1)
                value = ttk.Label(frame, text="", wraplength=420)
                value.grid(row=row, column=1, sticky="ew", pady=1)
                frame.columnconfigure(1, weight=1)
                self.library_presentation_labels[(section_id, field)] = value
        related_frame = ttk.LabelFrame(middle, text="Related Albums", padding=6)
        middle.add(related_frame, weight=1)
        self.library_relationships_text = tk.Text(related_frame, height=10, wrap="word", font="TkFixedFont")
        self.library_relationships_text.pack(fill="both", expand=True)
        self.library_relationships_text.config(state="disabled")

        evidence = ttk.Panedwindow(workspace, orient="horizontal")
        workspace.add(evidence, weight=4)
        self.layout_panes["library_evidence"] = evidence
        files_frame = ttk.LabelFrame(evidence, text="Files", padding=6)
        evidence.add(files_frame, weight=1)
        self.library_files_text = self._build_scrolled_text(files_frame)
        self.library_files_text.config(state="disabled")

        nfo_frame = ttk.LabelFrame(evidence, text="NFO", padding=6)
        evidence.add(nfo_frame, weight=1)
        self.library_view_nfo_button = ttk.Button(
            nfo_frame,
            text="View NFO",
            command=lambda: self.show_nfo_viewer(self.library_current_nfo, self.library_selected_album),
        )
        self.library_view_nfo_button.pack(anchor="w", pady=(0, 6))
        self.library_nfo_text = self._build_scrolled_text(nfo_frame)
        self.library_nfo_text.config(state="disabled")

    def _build_artwork_tab(self, parent):
        toolbar = ttk.Frame(parent)
        toolbar.pack(fill="x", pady=(0, 10))
        ttk.Button(toolbar, text="Refresh", command=self.refresh_artwork_browser).pack(side="left")
        ttk.Label(toolbar, text="Artist").pack(side="left", padx=(12, 4))
        artist_filter = ttk.Entry(toolbar, textvariable=self.artwork_artist_var, width=24)
        artist_filter.pack(side="left")
        ttk.Label(toolbar, text="Album").pack(side="left", padx=(12, 4))
        album_filter = ttk.Entry(toolbar, textvariable=self.artwork_album_var, width=24)
        album_filter.pack(side="left")
        ttk.Button(toolbar, text="Open Album", command=self.open_selected_artwork_album).pack(side="left", padx=(12, 0))
        ttk.Button(toolbar, text="Open Folder", command=self.open_selected_artwork_folder).pack(side="left", padx=(6, 0))
        artist_filter.bind("<KeyRelease>", lambda event: self.apply_artwork_filters())
        album_filter.bind("<KeyRelease>", lambda event: self.apply_artwork_filters())

        self.artwork_tree = ttk.Treeview(
            parent,
            columns=("cover", "artist", "album", "year", "readiness"),
            show="headings",
            selectmode="browse",
        )
        for column, title, width in (
            ("cover", "Cover", 180),
            ("artist", "Artist", 180),
            ("album", "Album", 260),
            ("year", "Year", 70),
            ("readiness", "Readiness", 150),
        ):
            self.artwork_tree.heading(column, text=title)
            self.artwork_tree.column(column, width=width, anchor="w")
        self.artwork_tree.pack(fill="both", expand=True)
        ttk.Label(parent, textvariable=self.artwork_status_var).pack(anchor="w", pady=(8, 0))

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
        ttk.Label(toolbar, text="Maintenance overview: validation, documentation, lifecycle, and audit work").pack(side="left")
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
            ("Secondary: Top Opportunities", [
                ("top_opportunities.needs_validation", "Needs Validation"),
                ("top_opportunities.needs_documentation", "Needs Documentation"),
                ("top_opportunities.needs_metadata", "Needs Metadata"),
                ("top_opportunities.needs_review", "Needs Review"),
                ("top_opportunities.archive_ready", "Archive Ready"),
                ("top_opportunities.most_urgent_category", "Most Urgent"),
            ]),
            ("Maintenance Actions", [
                ("archive_actions.action_count", "Action Count"),
                ("archive_actions.missing_nfo", "Missing NFO"),
                ("archive_actions.missing_sfv", "Missing SFV"),
                ("archive_actions.missing_validation", "Missing Validation"),
                ("archive_actions.missing_metadata", "Missing Metadata"),
                ("archive_actions.missing_artwork", "Missing Artwork"),
                ("archive_actions.identity_review", "Identity Review"),
            ]),
            ("Maintenance Tools", [
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

        details = ttk.LabelFrame(parent, text="Selected Maintenance Action", padding=8)
        details.pack(fill="x", pady=(10, 0))
        self.action_detail = tk.Text(details, height=4, wrap="word")
        self.action_detail.pack(fill="x")
        self.action_detail.config(state="disabled")

        operations = ttk.LabelFrame(parent, text="Maintenance Tool Controls", padding=8)
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
        ttk.Button(buttons, text="Reconcile Archive", command=self.reconcile_archive_report).pack(side="left", padx=(6, 0))

        history = ttk.LabelFrame(parent, text="Recent Operations", padding=8)
        history.pack(fill="x", pady=(10, 0))
        self.operation_history_detail = tk.Text(history, height=5, wrap="word")
        self.operation_history_detail.pack(fill="x")
        self.operation_history_detail.config(state="disabled")

        self.refresh_audio_dashboard()

    def _build_pipeline_tab(self, parent):
        toolbar = ttk.Frame(parent)
        toolbar.pack(fill="x", pady=(0, 10))
        ttk.Label(toolbar, text="Pipeline dashboard: releases grouped by next workflow stage").pack(side="left")
        ttk.Button(toolbar, text="Refresh", command=self.refresh_pipeline_dashboard).pack(side="left", padx=(8, 0))

        stages = ttk.Notebook(parent)
        stages.pack(fill="both", expand=True)
        for stage in PIPELINE_STAGES:
            frame = ttk.Frame(stages, padding=8)
            stages.add(frame, text=stage)
            header = ttk.Frame(frame)
            header.pack(fill="x", pady=(0, 8))
            ttk.Label(header, text=stage).pack(side="left")
            count_label = ttk.Label(header, text="0 releases")
            count_label.pack(side="right")
            self.pipeline_stage_labels[stage] = count_label

            columns = ("artist", "album", "count", "next_action", "state")
            tree = ttk.Treeview(frame, columns=columns, show="headings", height=18)
            tree.heading("artist", text="Artist")
            tree.heading("album", text="Album")
            tree.heading("count", text="Count")
            tree.heading("next_action", text="Recommended Next Action")
            tree.heading("state", text="State")
            tree.column("artist", width=210, anchor="w")
            tree.column("album", width=300, anchor="w")
            tree.column("count", width=70, anchor="center")
            tree.column("next_action", width=190, anchor="w")
            tree.column("state", width=160, anchor="w")
            tree.pack(fill="both", expand=True)
            self.pipeline_stage_trees[stage] = tree

        self.refresh_pipeline_dashboard()

    def _build_settings_tab(self, parent):
        sections = ttk.Notebook(parent)
        sections.pack(fill="both", expand=True)

        roots = ttk.Frame(sections, padding=10)
        sections.add(roots, text="Roots")
        root_fields = [
            ("archive_paths", "main_archive_root", "Main Archive Root", "Canonical archive location."),
            ("archive_paths", "incoming_root", "Incoming Root", "Downloaded releases waiting for validation."),
            ("archive_paths", "problematic_root", "Problematic Root", "Holding area for releases needing manual review."),
            (
                "archive_paths",
                "needs_validation_root",
                "Needs Validation Root",
                "Optional validation work area. Today this may overlap Incoming Root when downloads are validated in place.",
            ),
            ("validator", "validated_index_path", "Validated Index", "Local index of releases already validated."),
            ("validator", "validation_log_root", "Validation Logs", "Root scanned for validator evidence."),
            ("metadata", "metadata_cache_path", "Metadata Cache", "Local metadata cache file."),
            ("reports", "reports_directory", "Reports", "Generated report output folder."),
        ]
        self._build_settings_fields(roots, root_fields)

        tools = ttk.Frame(sections, padding=10)
        sections.add(tools, text="Tools")
        ttk.Label(
            tools,
            text="External tools are discovered without execution. Legacy NFO and SFV tool paths remain supported in saved settings.",
            wraplength=900,
        ).grid(row=0, column=0, columnspan=5, sticky="w", pady=(0, 10))
        tool_fields = [
            ("audio_division", "tools", "audio_division_path", "Audio Division"),
            ("validator", "tools", "flac_validator_path", "Validator"),
            ("file_manager", "tools", "file_manager_path", "File Manager"),
        ]
        for row, (tool_id, section, key, label) in enumerate(tool_fields, start=1):
            ttk.Label(tools, text=label).grid(row=row, column=0, sticky="w", padx=(0, 10), pady=4)
            status = ttk.Label(tools, text="Not Found", width=14)
            status.grid(row=row, column=1, sticky="w", padx=(0, 10), pady=4)
            self.tool_status_labels[tool_id] = status
            var = tk.StringVar(value=self.audio_settings.get(section, {}).get(key, ""))
            entry = ttk.Entry(tools, textvariable=var)
            entry.grid(row=row, column=2, sticky="ew", pady=4)
            self.audio_setting_vars[(section, key)] = var
            resolved = ttk.Label(tools, text="", width=34)
            resolved.grid(row=row, column=3, sticky="w", padx=(10, 10), pady=4)
            self.tool_resolved_labels[tool_id] = resolved
            version = ttk.Label(tools, text="Unavailable", width=16)
            version.grid(row=row, column=4, sticky="w", pady=4)
            self.tool_version_labels[tool_id] = version
        tools.columnconfigure(2, weight=1)

        providers = ttk.Frame(sections, padding=10)
        sections.add(providers, text="Providers")
        ttk.Label(
            providers,
            text="Provider settings are grouped here so Deezer, YouTube, and Internet Archive can be added without changing the Settings layout.",
            wraplength=900,
        ).grid(row=0, column=0, columnspan=2, sticky="w", pady=(0, 10))
        provider_fields = [
            ("playback", "provider", "Playback Provider", "Current local playback backend."),
            ("playback", "player_path", "Player Path", "Executable used for local playback."),
            ("playback", "player_args", "Player Arguments", "Optional playback arguments."),
        ]
        self._build_settings_fields(providers, provider_fields, start_row=1)

        buttons = ttk.Frame(parent)
        buttons.pack(fill="x", pady=(10, 0))
        ttk.Button(buttons, text="Save Settings", command=self.save_audio_settings).pack(side="left")
        ttk.Button(buttons, text="Reload Settings", command=self.reload_audio_settings).pack(side="left", padx=(6, 0))
        ttk.Button(buttons, text="Refresh Tool Discovery", command=self.refresh_tool_settings_status).pack(side="left", padx=(6, 0))
        self.refresh_tool_settings_status()

    def _build_settings_fields(self, parent, fields, start_row: int = 0):
        for offset, (section, key, label, description) in enumerate(fields):
            row = start_row + offset
            ttk.Label(parent, text=label).grid(row=row, column=0, sticky="w", padx=(0, 10), pady=4)
            var = tk.StringVar(value=self.audio_settings.get(section, {}).get(key, ""))
            ttk.Entry(parent, textvariable=var).grid(row=row, column=1, sticky="ew", pady=4)
            self.audio_setting_vars[(section, key)] = var
            note = ttk.Label(parent, text=description, foreground="#555", wraplength=380)
            note.grid(row=row, column=2, sticky="w", padx=(10, 0), pady=4)
        parent.columnconfigure(1, weight=1)

    def refresh_tool_settings_status(self):
        if not hasattr(self, "tool_status_labels"):
            return
        preview = dict(self.audio_settings)
        preview["tools"] = dict(self.audio_settings.get("tools", {}))
        for (section, key), var in self.audio_setting_vars.items():
            if section == "tools":
                preview["tools"][key] = var.get()
        discoveries = discover_configured_tools(preview, base_dir=BASE_DIR)
        for tool_id, discovery in discoveries.items():
            status = self.tool_status_labels.get(tool_id)
            if status is not None:
                status.config(text=discovery.status)
            resolved = self.tool_resolved_labels.get(tool_id)
            if resolved is not None:
                resolved.config(text=self._shorten_path(discovery.resolved_path or "Not Found", max_chars=42))
            version = self.tool_version_labels.get(tool_id)
            if version is not None:
                version.config(text=discovery.version)

    def refresh_pipeline_dashboard(self):
        if not hasattr(self, "pipeline_stage_trees"):
            return
        identity = load_json(DATA_DIR / "identity_registry.json")
        lifecycle = load_json(DATA_DIR / "lifecycle_registry.json")
        archive_registry = load_json(DATA_DIR / "archive_registry.json")
        metadata = load_json(DATA_DIR / "metadata_cache.json")

        artist_releases = []
        for presentation in load_artist_presentations(ARTISTS_DIR, DATA_DIR):
            artist_name = presentation.artist.artist_name
            for release in presentation.artist.releases:
                row = {
                    name: getattr(release, name)
                    for name in dir(release)
                    if not name.startswith("_") and not callable(getattr(release, name))
                }
                row["artist"] = artist_name
                artist_releases.append(row)

        incoming_rows = [
            release.to_row()
            for release in incoming_releases(
                self.audio_settings,
                identity_registry=identity,
                lifecycle_registry=lifecycle,
                archive_registry=archive_registry,
                metadata_cache=metadata,
                processing_queue=self.processing_queue,
            )
        ]
        archive_albums = build_archive_albums(archive_registry, identity, metadata)
        dashboard = build_pipeline_dashboard([*artist_releases, *incoming_rows, *archive_albums])

        for stage in dashboard.get("stages", []):
            name = stage.get("stage", "")
            label = self.pipeline_stage_labels.get(name)
            if label is not None:
                label.config(text=f"{stage.get('count', 0)} releases")
            tree = self.pipeline_stage_trees.get(name)
            if tree is None:
                continue
            for item in tree.get_children():
                tree.delete(item)
            for index, row in enumerate(stage.get("items", [])):
                tree.insert(
                    "",
                    tk.END,
                    iid=str(index),
                    values=(
                        row.get("artist", ""),
                        row.get("album", ""),
                        row.get("count", 1),
                        row.get("recommended_next_action", ""),
                        row.get("state", ""),
                    ),
                )

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

    def reconcile_archive_report(self):
        archive_root = self.audio_settings.get("archive_paths", {}).get("main_archive_root", "")
        if not archive_root:
            self.status.config(text="Archive reconciliation failed: Main Archive Root is not configured")
            return
        registry = load_json(DATA_DIR / "archive_registry.json")
        report = reconcile_archive(Path(archive_root), registry)
        reports_dir = Path(self.audio_settings.get("reports", {}).get("reports_directory") or BASE_DIR / "reports")
        if not reports_dir.is_absolute():
            reports_dir = BASE_DIR / reports_dir
        write_archive_reconciliation_report(report, reports_dir)
        summary = report.get("summary", {})
        self.status.config(
            text=(
                "Archive reconciliation report written: "
                f"{summary.get('albums_missing', 0)} missing, "
                f"{summary.get('albums_added', 0)} added, "
                f"{summary.get('disc_folder_album_rows', 0)} disc rows"
            )
        )

    def run_archive_audit(self):
        registry = load_json(DATA_DIR / "archive_registry.json")
        archive_root_text = registry.get("archive_root") or self.audio_settings.get("archive_paths", {}).get("main_archive_root", "")
        if not archive_root_text:
            self.status.config(text="Archive audit failed: Main Archive Root is not configured")
            return
        archive_root = Path(archive_root_text)
        reports_dir = Path(self.audio_settings.get("reports", {}).get("reports_directory") or BASE_DIR / "reports")
        if not reports_dir.is_absolute():
            reports_dir = BASE_DIR / reports_dir
        if self._archive_audit_running:
            return
        self._set_archive_audit_running(True, "Archive audit running...")
        thread = threading.Thread(
            target=self._run_archive_audit_thread,
            args=(registry, archive_root, reports_dir),
            daemon=True,
        )
        thread.start()

    def _set_archive_audit_running(self, running: bool, message: str):
        self._archive_audit_running = running
        state = "disabled" if running else "normal"
        if hasattr(self, "archive_audit_button"):
            self.archive_audit_button.config(state=state)
        if hasattr(self, "archive_audit_status_var"):
            self.archive_audit_status_var.set(message)
        self.status.config(text=message)

    def _run_archive_audit_thread(self, registry: dict, archive_root: Path, reports_dir: Path):
        try:
            report = audit_archive(registry, archive_root)
            self.after(0, lambda: self.archive_audit_status_var.set("Writing archive audit report..."))
            write_archive_audit(report, reports_dir)
            summary = report.get("summary", {})
            message = (
                "Archive audit written: "
                f"{summary.get('albums_scanned', 0)} scanned, "
                f"{summary.get('warnings', 0)} warnings, "
                f"{summary.get('errors', 0)} errors"
            )
        except Exception as exc:
            message = f"Archive audit failed: {exc}"
        self.after(0, lambda message=message: self._set_archive_audit_running(False, message))

    def run_archive_revalidation(self):
        registry = load_json(DATA_DIR / "archive_registry.json")
        archive_root_text = registry.get("archive_root") or self.audio_settings.get("archive_paths", {}).get("main_archive_root", "")
        if not archive_root_text:
            self.status.config(text="Archive revalidation failed: Main Archive Root is not configured")
            return
        archive_root = Path(archive_root_text)
        reports_dir = Path(self.audio_settings.get("reports", {}).get("reports_directory") or BASE_DIR / "reports")
        if not reports_dir.is_absolute():
            reports_dir = BASE_DIR / reports_dir
        if self._archive_revalidation_running:
            return
        self._set_archive_revalidation_running(True, "Archive revalidation running...")
        thread = threading.Thread(
            target=self._run_archive_revalidation_thread,
            args=(registry, archive_root, reports_dir),
            daemon=True,
        )
        thread.start()

    def _set_archive_revalidation_running(self, running: bool, message: str):
        self._archive_revalidation_running = running
        state = "disabled" if running else "normal"
        if hasattr(self, "archive_revalidation_button"):
            self.archive_revalidation_button.config(state=state)
        if hasattr(self, "archive_revalidation_status_var"):
            self.archive_revalidation_status_var.set(message)
        self.status.config(text=message)

    def _run_archive_revalidation_thread(self, registry: dict, archive_root: Path, reports_dir: Path):
        try:
            def progress(current: int, total: int, row: dict):
                if current == 1 or current == total or current % 25 == 0:
                    message = f"Revalidating {current} / {total} albums..."
                    self.after(0, lambda message=message: self.archive_revalidation_status_var.set(message))
                    self.after(0, lambda message=message: self.status.config(text=message))

            report = revalidate_archive(
                registry,
                archive_root,
                identity_registry=load_json(DATA_DIR / "identity_registry.json"),
                lifecycle_registry=load_json(DATA_DIR / "lifecycle_registry.json"),
                validated_index=load_json(DATA_DIR / "validated_albums.json"),
                progress=progress,
            )
            self.after(0, lambda: self.archive_revalidation_status_var.set("Writing archive revalidation report..."))
            write_archive_revalidation_report(report, reports_dir)
            summary = report.get("summary", {})
            message = (
                "Archive revalidation written: "
                f"{summary.get('albums_scanned', 0)} scanned, "
                f"{summary.get('healthy', 0)} healthy, "
                f"{summary.get('warnings', 0)} warnings, "
                f"{summary.get('errors', 0)} errors"
            )
        except Exception as exc:
            message = f"Archive revalidation failed: {exc}"
        self.after(0, lambda message=message: self._set_archive_revalidation_running(False, message))

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
        if hasattr(self, "artwork_tree"):
            self.refresh_artwork_browser()

    def refresh_archive_browser(
        self,
        restore_album_key: str = "",
        restore_artist_key: str = "",
        restore_album_yview: float | None = None,
    ):
        if not hasattr(self, "archive_tree"):
            return
        if not restore_album_key and getattr(self, "archive_selected_album", {}):
            selection = capture_archive_selection(
                self.archive_selected_album,
                album_yview=self.archive_album_tree.yview(),
            )
            restore_album_key = selection.album_key
            restore_artist_key = selection.artist_key
            restore_album_yview = selection.album_yview
        registry = load_json(DATA_DIR / "archive_registry.json")
        identity = load_json(DATA_DIR / "identity_registry.json")
        metadata = load_json(DATA_DIR / "metadata_cache.json")
        self.archive_albums = build_archive_albums(registry, identity, metadata)
        self.processing_queue = load_processing_queue(PROCESSING_QUEUE_FILE)
        self.apply_archive_filters(
            restore_album_key=restore_album_key,
            restore_artist_key=restore_artist_key,
            restore_album_yview=restore_album_yview,
        )

    def refresh_archive_metadata(self):
        selection = capture_archive_selection(
            getattr(self, "archive_selected_album", {}),
            active_tab=self.tabs.select(),
            album_yview=self.archive_album_tree.yview(),
        )
        reports_dir = Path(self.audio_settings.get("reports", {}).get("reports_directory") or BASE_DIR / "reports")
        if not reports_dir.is_absolute():
            reports_dir = BASE_DIR / reports_dir
        try:
            result = rebuild_metadata_enrichment(DATA_DIR, reports_dir)
        except OSError as exc:
            self.archive_operation_result_var.set(f"Metadata refresh failed: {exc}")
            return
        self.refresh_archive_browser(
            restore_album_key=selection.album_key,
            restore_artist_key=selection.artist_key,
            restore_album_yview=selection.album_yview,
        )
        if selection.active_tab:
            self.tabs.select(selection.active_tab)
        self.archive_operation_result_var.set(
            f"Metadata refreshed: {result['albums_enriched']}/{result['albums_evaluated']} albums enriched."
        )

    def apply_archive_filters(
        self,
        restore_album_key: str = "",
        restore_artist_key: str = "",
        restore_album_yview: float | None = None,
    ):
        self.filtered_archive_albums = filter_archive_albums(
            self.archive_albums,
            artist=self.archive_artist_var.get(),
            album=self.archive_album_var.get(),
        )
        self.archive_artist_rows = archive_tree(self.filtered_archive_albums)
        for item in self.archive_tree.get_children():
            self.archive_tree.delete(item)
        letters: dict[str, str] = {}
        for row in self.archive_artist_rows:
            letter = row.get("letter", "#")
            if letter not in letters:
                letter_iid = archive_letter_iid(letter)
                letters[letter] = self.archive_tree.insert("", tk.END, iid=letter_iid, text=letter, open=True)
            self.archive_tree.insert(
                letters[letter],
                tk.END,
                iid=f"artist:{row['artist_key']}",
                text=f"{row['artist']} ({row['album_count']})",
            )
        self.refresh_processing_queue_view()
        self.refresh_maintenance_view()
        self.refresh_pipeline_dashboard()
        if restore_artist_key:
            artist_iid = f"artist:{restore_artist_key}"
            if self.archive_tree.exists(artist_iid):
                self.archive_tree.selection_set(artist_iid)
                self.archive_tree.see(artist_iid)
                self._load_archive_artist_albums(restore_artist_key, restore_album_key, restore_album_yview)
                return
        self.clear_archive_albums()

    def set_archive_tree_expansion(self, mode: str):
        selected_artist_key = ""
        selection = self.archive_tree.selection()
        if selection and str(selection[0]).startswith("artist:"):
            selected_artist_key = str(selection[0]).split(":", 1)[1]
        if not selected_artist_key:
            selected_artist_key = str(getattr(self, "archive_selected_album", {}).get("artist_key") or "")
        open_items = archive_tree_expansion(self.archive_artist_rows, mode, selected_artist_key)
        for item in self.archive_tree.get_children(""):
            self.archive_tree.item(item, open=item in open_items)
        if mode != "collapse_all" and selected_artist_key:
            artist_iid = f"artist:{selected_artist_key}"
            if self.archive_tree.exists(artist_iid):
                self.archive_tree.see(artist_iid)

    def clear_archive_albums(self):
        self.archive_album_rows = []
        self.archive_selected_album = {}
        for item in self.archive_album_tree.get_children():
            self.archive_album_tree.delete(item)
        self.set_archive_detail({})

    def on_archive_artist_selected(self, event=None):
        selection = self.archive_tree.selection()
        if not selection:
            return
        item = selection[0]
        if not str(item).startswith("artist:"):
            return
        artist_key = str(item).split(":", 1)[1]
        self._load_archive_artist_albums(artist_key)

    def _load_archive_artist_albums(
        self,
        artist_key: str,
        restore_album_key: str = "",
        restore_album_yview: float | None = None,
    ):
        self.archive_album_rows = albums_for_archive_artist(self.filtered_archive_albums, artist_key)
        for existing in self.archive_album_tree.get_children():
            self.archive_album_tree.delete(existing)
        restored_index = None
        if restore_album_key:
            state = capture_archive_selection({"artist_key": artist_key, "archive_path": restore_album_key})
            restored_index = selected_album_index(self.archive_album_rows, state)
        restored_iid = str(restored_index) if restored_index is not None else ""
        for index, row in enumerate(self.archive_album_rows):
            readiness = row.get("archive_readiness", {})
            status = row.get("album_status", {}).get("items", {})
            iid = str(index)
            self.archive_album_tree.insert(
                "",
                tk.END,
                iid=iid,
                values=(
                    row.get("title", ""),
                    row.get("year", ""),
                    status.get("validation", "Unknown"),
                    readiness.get("state", "UNKNOWN"),
                ),
            )
        if restored_iid:
            self.archive_album_tree.selection_set(restored_iid)
            self.archive_album_tree.see(restored_iid)
            if restore_album_yview is not None:
                self.archive_album_tree.yview_moveto(restore_album_yview)
            self.archive_selected_album = self.archive_album_rows[int(restored_iid)]
            self.set_archive_detail(self.archive_selected_album)
            return
        self.archive_selected_album = {}
        self.set_archive_detail({})

    def on_archive_album_selected(self, event=None):
        selection = self.archive_album_tree.selection()
        if not selection:
            return
        index = self.archive_album_tree.index(selection[0])
        if index >= len(self.archive_album_rows):
            return
        self.archive_selected_album = self.archive_album_rows[index]
        self.set_archive_detail(self.archive_selected_album)

    def set_archive_detail(self, details: dict):
        workspace = album_workspace(details, load_json(DATA_DIR / "metadata_cache.json"), getattr(self, "archive_albums", []))
        presentation = workspace.get("presentation", {})
        sections = presentation.get("sections", {})
        for (section_id, field), label in self.archive_presentation_labels.items():
            value = ""
            for item_field, item_value in sections.get(section_id, []):
                if item_field == field:
                    value = item_value
                    break
            label.config(text=str(value or ""))
        title = str(details.get("title") or "")
        self.archive_cover_title.config(text=title)
        full_path = str(details.get("archive_path") or "")
        if hasattr(self, "archive_path_label"):
            self.archive_path_label.config(text=self._shorten_path(full_path))
            self.archive_path_tooltip.set_text(full_path)
        for field, value in workspace.get("status_glance", []):
            if field in self.archive_status_glance_labels:
                self.archive_status_glance_labels[field].config(text=str(value or "Unknown"))
        self._set_archive_thumbnail(workspace.get("cover", {}))
        self._set_text_widget(self.archive_integrity_text, self._format_integrity(workspace.get("integrity", {})))
        self._set_text_widget(self.archive_relationships_text, workspace.get("relationships_text", ""))
        files = workspace.get("files", {})
        self._set_text_widget(
            self.archive_files_text,
            f"Source: {files.get('source', 'missing')}\nPath: {files.get('path', '')}\n\n"
            + "\n".join(files.get("items", [])),
        )
        nfo = workspace.get("nfo", {})
        self.archive_current_nfo = nfo
        self.archive_view_nfo_button.config(state="normal" if nfo.get("path") else "disabled")
        self._set_text_widget(
            self.archive_nfo_text,
            f"Status: {nfo.get('status', 'Missing')}\nPath: {nfo.get('path', '')}",
        )

    def _set_archive_thumbnail(self, thumbnail: dict):
        self.archive_thumbnail_image = self._set_album_cover(
            self.archive_thumbnail,
            self.archive_artwork_status,
            thumbnail,
        )

    def run_archive_album_operation(self, operation_id: str):
        target, reason = album_archive_operation_target(self.archive_selected_album)
        if not target:
            self.archive_operation_result_var.set(f"Failure: {reason}")
            return
        active_tab = self.tabs.select()
        selection = capture_archive_selection(
            self.archive_selected_album,
            active_tab=active_tab,
            album_yview=self.archive_album_tree.yview(),
        )
        result = run_operation(operation_id, target, self.audio_settings, OPERATION_HISTORY_FILE)
        self.archive_operation_result_var.set(f"{result['result'].title()}: {result['message']}")
        self.refresh_archive_browser(
            restore_album_key=selection.album_key,
            restore_artist_key=selection.artist_key,
            restore_album_yview=selection.album_yview,
        )
        if selection.active_tab:
            self.tabs.select(selection.active_tab)
        self.refresh_audio_dashboard()

    def run_archive_album_playback(self, operation_id: str):
        target, reason = album_archive_operation_target(self.archive_selected_album)
        if not target:
            self.archive_operation_result_var.set(f"Failure: {reason}")
            return
        result = run_playback_action(operation_id, target, self.audio_settings, OPERATION_HISTORY_FILE)
        self.archive_operation_result_var.set(f"{result['result'].title()}: {result['message']}")
        self.refresh_audio_dashboard()

    def queue_selected_archive_album_for_processing(self):
        if not self.archive_selected_album:
            self.archive_operation_result_var.set("Failure: select an album first")
            return
        self.processing_queue = queue_for_processing(self.processing_queue, self.archive_selected_album, source="archive")
        save_processing_queue(PROCESSING_QUEUE_FILE, self.processing_queue)
        self.refresh_processing_queue_view()
        self.archive_operation_result_var.set("Queued for processing.")

    def process_selected_archive_album(self):
        target, reason = album_archive_operation_target(self.archive_selected_album)
        if not target:
            self.archive_operation_result_var.set(f"Failure: {reason}")
            return
        selection = capture_archive_selection(
            self.archive_selected_album,
            active_tab=self.tabs.select(),
            album_yview=self.archive_album_tree.yview(),
        )
        self.processing_queue = queue_for_processing(self.processing_queue, self.archive_selected_album, source="archive")
        save_processing_queue(PROCESSING_QUEUE_FILE, self.processing_queue)
        reports_dir = Path(self.audio_settings.get("reports", {}).get("reports_directory") or BASE_DIR / "reports")
        if not reports_dir.is_absolute():
            reports_dir = BASE_DIR / reports_dir
        result = process_validated_release(
            target,
            self.audio_settings,
            DATA_DIR,
            reports_dir,
            OPERATION_HISTORY_FILE,
        )
        self.archive_operation_result_var.set(f"{result['result'].title()}: {result['message']}")
        self.refresh_archive_browser(
            restore_album_key=selection.album_key,
            restore_artist_key=selection.artist_key,
            restore_album_yview=selection.album_yview,
        )
        if selection.active_tab:
            self.tabs.select(selection.active_tab)
        self.refresh_audio_dashboard()

    def refresh_processing_queue_view(self):
        if not hasattr(self, "processing_queue_tree"):
            return
        self.processing_queue_rows = [
            self.release_pipeline_row(release.to_row())
            for release in incoming_releases(
                self.audio_settings,
                identity_registry=load_json(DATA_DIR / "identity_registry.json"),
                lifecycle_registry=load_json(DATA_DIR / "lifecycle_registry.json"),
                archive_registry=load_json(DATA_DIR / "archive_registry.json"),
                metadata_cache=load_json(DATA_DIR / "metadata_cache.json"),
                processing_queue=self.processing_queue,
            )
        ]
        self.closed_loop_rows = self.processing_queue_rows
        for item in self.processing_queue_tree.get_children():
            self.processing_queue_tree.delete(item)
        for index, row in enumerate(self.processing_queue_rows[:100]):
            self.processing_queue_tree.insert(
                "",
                tk.END,
                iid=str(index),
                values=(
                    row.get("artist", ""),
                    row.get("album", ""),
                    row.get("source", ""),
                    self._shorten_path(row.get("folder", ""), max_chars=38),
                    row.get("state", ""),
                    row.get("next_action", ""),
                ),
            )
        self.refresh_pipeline_dashboard()

    def release_pipeline_row(self, row: dict) -> dict:
        recommendation = recommend_next_action(row).to_dict()
        updated = dict(row)
        updated["pipeline_recommendation"] = recommendation
        updated["next_action"] = recommendation["recommended_action"]
        return updated

    def selected_incoming_album(self) -> dict:
        selection = self.processing_queue_tree.selection() if hasattr(self, "processing_queue_tree") else []
        if not selection:
            return {}
        index = int(selection[0])
        if index >= len(self.closed_loop_rows):
            return {}
        return self.closed_loop_rows[index]

    def open_selected_incoming_folder(self):
        row = self.selected_incoming_album()
        if not row:
            self.archive_operation_result_var.set("Failure: no incoming album selected.")
            return
        result = run_operation("open_album_folder", row.get("folder", ""), self.audio_settings, OPERATION_HISTORY_FILE)
        self.archive_operation_result_var.set(f"Open Folder: {result['result'].title()} - {result['message']}")

    def queue_selected_incoming_album(self):
        row = self.selected_incoming_album()
        if not row:
            self.archive_operation_result_var.set("Failure: no incoming album selected.")
            return
        self.processing_queue = queue_for_processing(
            self.processing_queue,
            queue_album_payload(row),
            source=row.get("source", "incoming"),
        )
        save_processing_queue(PROCESSING_QUEUE_FILE, self.processing_queue)
        self.refresh_processing_queue_view()
        self.archive_operation_result_var.set("Incoming album queued for processing.")

    def validate_selected_incoming_release(self):
        row = self.selected_incoming_album()
        if not row:
            self.archive_operation_result_var.set("Failure: no incoming album selected.")
            return
        reports_dir = Path(self.audio_settings.get("reports", {}).get("reports_directory") or BASE_DIR / "reports")
        if not reports_dir.is_absolute():
            reports_dir = BASE_DIR / reports_dir
        result = run_validator_for_release(
            row,
            self.audio_settings,
            DATA_DIR,
            reports_dir,
            OPERATION_HISTORY_FILE,
        )
        self.refresh_archive_browser()
        self.refresh_processing_queue_view()
        self.refresh_audio_dashboard()
        self.archive_operation_result_var.set(
            f"Validate Download: {result['result'].title()} - exit {result['exit_code']}"
        )

    def refresh_maintenance_view(self):
        if not hasattr(self, "maintenance_tree"):
            return
        previous = self.selected_maintenance_id
        counts = maintenance_counts(self.filtered_archive_albums)
        for key, label in self.maintenance_summary_labels.items():
            value = counts.get(key, 0)
            if key.endswith("_coverage"):
                value = f"{value}%"
            label.config(text=str(value))
        self.maintenance_rows = maintenance_summaries(self.filtered_archive_albums)
        for item in self.maintenance_tree.get_children():
            self.maintenance_tree.delete(item)
        selected_iid = ""
        for index, row in enumerate(self.maintenance_rows):
            iid = str(index)
            self.maintenance_tree.insert(
                "",
                tk.END,
                iid=iid,
                values=(row.get("name", ""), row.get("album_count", 0)),
            )
            if row.get("id") == previous:
                selected_iid = iid
        if selected_iid:
            self.maintenance_tree.selection_set(selected_iid)
            self.maintenance_tree.see(selected_iid)
            self.render_maintenance_albums(previous)
        else:
            self.selected_maintenance_id = ""
            self.render_maintenance_albums("")

    def on_maintenance_selected(self, event=None):
        selection = self.maintenance_tree.selection()
        if not selection:
            return
        index = int(selection[0])
        if index >= len(self.maintenance_rows):
            return
        self.selected_maintenance_id = self.maintenance_rows[index].get("id", "")
        self.render_maintenance_albums(self.selected_maintenance_id)

    def render_maintenance_albums(self, category_id: str):
        if not hasattr(self, "maintenance_album_tree"):
            return
        self.maintenance_album_rows = maintenance_albums(self.filtered_archive_albums, category_id) if category_id else []
        for item in self.maintenance_album_tree.get_children():
            self.maintenance_album_tree.delete(item)
        for index, row in enumerate(self.maintenance_album_rows):
            self.maintenance_album_tree.insert(
                "",
                tk.END,
                iid=str(index),
                values=(
                    row.get("artist", ""),
                    row.get("title", ""),
                    row.get("maintenance_priority", ""),
                    row.get("maintenance_operation", ""),
                    row.get("maintenance_reason", ""),
                ),
            )

    def selected_maintenance_album(self) -> dict:
        selection = self.maintenance_album_tree.selection() if hasattr(self, "maintenance_album_tree") else []
        if not selection:
            return {}
        index = int(selection[0])
        if index >= len(self.maintenance_album_rows):
            return {}
        return self.maintenance_album_rows[index]

    def open_selected_maintenance_album(self):
        album = self.selected_maintenance_album()
        if not album:
            self.archive_operation_result_var.set("Failure: no maintenance album selected.")
            return
        artist_iid = f"artist:{album.get('artist_key', '')}"
        if self.archive_tree.exists(artist_iid):
            self.archive_tree.selection_set(artist_iid)
            self.archive_tree.see(artist_iid)
            self._load_archive_artist_albums(album.get("artist_key", ""), self._archive_album_key(album), None)
        self.archive_selected_album = album
        self.set_archive_detail(album)
        self.archive_operation_result_var.set("Album opened in workspace.")

    def run_recommended_maintenance_operation(self):
        album = self.selected_maintenance_album()
        if not album:
            self.archive_operation_result_var.set("Failure: no maintenance album selected.")
            return
        self.run_maintenance_operation(maintenance_operation_for_album(album))

    def run_maintenance_operation(self, operation_id: str):
        album = self.selected_maintenance_album()
        if not album:
            self.archive_operation_result_var.set("Failure: no maintenance album selected.")
            return
        resolved_operation, target, reason = maintenance_action_target(operation_id, album)
        if not target:
            self.archive_operation_result_var.set(f"Failure: {reason}")
            return
        selection = capture_archive_selection(
            album,
            active_tab=self.tabs.select(),
            album_yview=self.archive_album_tree.yview(),
        )
        result = run_operation(resolved_operation, target, self.audio_settings, OPERATION_HISTORY_FILE)
        self.archive_operation_result_var.set(
            f"{resolved_operation}: {result['result'].title()} - {result['message']}"
        )
        self.refresh_archive_browser(
            restore_album_key=selection.album_key,
            restore_artist_key=selection.artist_key,
            restore_album_yview=selection.album_yview,
        )
        if selection.active_tab:
            self.tabs.select(selection.active_tab)
        self.refresh_audio_dashboard()

    def _archive_album_key(self, album: dict) -> str:
        return archive_album_key(album)

    def _shorten_path(self, value: str, max_chars: int = 72) -> str:
        text = str(value or "")
        if len(text) <= max_chars:
            return text
        parts = Path(text).parts
        if len(parts) >= 4:
            shortened = ".../" + "/".join(parts[-3:])
            if len(shortened) <= max_chars:
                return shortened
        return "..." + text[-(max_chars - 3):]

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
        workspace = album_workspace(details, load_json(DATA_DIR / "metadata_cache.json"), getattr(self, "library_data", {}).get("albums", []))
        presentation = workspace.get("presentation", {})
        sections = presentation.get("sections", {})
        for (section_id, field), label in self.library_presentation_labels.items():
            value = ""
            for item_field, item_value in sections.get(section_id, []):
                if item_field == field:
                    value = item_value
                    break
            label.config(text=str(value or ""))
        for field, value in workspace.get("status_glance", []):
            if field in self.library_status_glance_labels:
                self.library_status_glance_labels[field].config(text=str(value or "Unknown"))
        self._set_library_thumbnail(workspace.get("cover", {}))
        self._set_text_widget(self.library_integrity_text, self._format_integrity(workspace.get("integrity", {})))
        self._set_text_widget(self.library_relationships_text, workspace.get("relationships_text", ""))
        files = workspace.get("files", {})
        self._set_text_widget(
            self.library_files_text,
            f"Source: {files.get('source', 'missing')}\nPath: {files.get('path', '')}\n\n"
            + "\n".join(files.get("items", [])),
        )
        nfo = workspace.get("nfo", {})
        self.library_current_nfo = nfo
        self.library_view_nfo_button.config(state="normal" if nfo.get("path") else "disabled")
        self._set_text_widget(
            self.library_nfo_text,
            f"Status: {nfo.get('status', 'Missing')}\nPath: {nfo.get('path', '')}",
        )

    def _set_library_thumbnail(self, thumbnail: dict):
        self.library_thumbnail_image = self._set_album_cover(
            self.library_thumbnail,
            self.library_artwork_status,
            thumbnail,
        )

    def _set_album_cover(self, label: tk.Label, status_label: ttk.Label, thumbnail: dict):
        return CoverWidget(label, status_label).render(thumbnail)

    def _build_scrolled_text(self, parent) -> tk.Text:
        frame = ttk.Frame(parent)
        frame.pack(fill="both", expand=True)
        frame.rowconfigure(0, weight=1)
        frame.columnconfigure(0, weight=1)
        text = tk.Text(frame, wrap="none")
        yscroll = ttk.Scrollbar(frame, orient="vertical", command=text.yview)
        xscroll = ttk.Scrollbar(frame, orient="horizontal", command=text.xview)
        text.configure(yscrollcommand=yscroll.set, xscrollcommand=xscroll.set)
        text.grid(row=0, column=0, sticky="nsew")
        yscroll.grid(row=0, column=1, sticky="ns")
        xscroll.grid(row=1, column=0, sticky="ew")
        return text

    def _set_text_widget(self, widget: tk.Text, text: str):
        widget.config(state="normal")
        widget.delete("1.0", tk.END)
        widget.insert(tk.END, text)
        widget.config(state="disabled")

    def _format_integrity(self, integrity: dict) -> str:
        if not integrity:
            return "No album selected."
        lines = []
        for check in integrity.get("checks", []):
            status = check.get("status", "Unknown")
            marker = "OK" if status == "Present" else "--"
            source = check.get("source", "none")
            detail = check.get("path", "")
            suffix = f" ({source})" if source and source != "none" else ""
            if detail:
                suffix += f" - {detail}"
            lines.append(f"{marker} {check.get('label', '')}: {status}{suffix}")
        lines.append("")
        lines.append(f"Health Score: {integrity.get('health_score', 0)}%")
        warnings = integrity.get("warnings", [])
        if warnings:
            lines.append("")
            lines.append("Warnings:")
            lines.extend(f"- {warning}" for warning in warnings)
        return "\n".join(lines)

    def show_nfo_viewer(self, nfo: dict, album: dict):
        if not nfo.get("path"):
            return
        title = album.get("title") or album.get("album") or "Album NFO"
        window = tk.Toplevel(self)
        window.title(f"NFO - {title}")
        window.geometry("900x620")
        window.transient(self)
        window.grab_set()

        body = ttk.Frame(window, padding=8)
        body.pack(fill="both", expand=True)
        ttk.Label(body, text=str(nfo.get("path", "")), wraplength=860).pack(anchor="w", pady=(0, 6))

        text_frame = ttk.Frame(body)
        text_frame.pack(fill="both", expand=True)
        text_frame.rowconfigure(0, weight=1)
        text_frame.columnconfigure(0, weight=1)
        viewer = tk.Text(text_frame, wrap="none", font="TkFixedFont")
        yscroll = ttk.Scrollbar(text_frame, orient="vertical", command=viewer.yview)
        xscroll = ttk.Scrollbar(text_frame, orient="horizontal", command=viewer.xview)
        viewer.configure(yscrollcommand=yscroll.set, xscrollcommand=xscroll.set)
        viewer.grid(row=0, column=0, sticky="nsew")
        yscroll.grid(row=0, column=1, sticky="ns")
        xscroll.grid(row=1, column=0, sticky="ew")
        viewer.insert(tk.END, str(nfo.get("content", "")))
        viewer.config(state="disabled")

        ttk.Button(body, text="Close", command=window.destroy).pack(anchor="e", pady=(8, 0))

    def refresh_artwork_browser(self):
        if not hasattr(self, "artwork_tree"):
            return
        if not self.library_data:
            self.refresh_library()
            return
        self.artwork_rows = artwork_items(self.library_data, load_json(DATA_DIR / "archive_registry.json"))
        self.apply_artwork_filters()

    def apply_artwork_filters(self):
        self.filtered_artwork_rows = filter_artwork_items(
            self.artwork_rows,
            artist=self.artwork_artist_var.get(),
            album=self.artwork_album_var.get(),
        )
        for item in self.artwork_tree.get_children():
            self.artwork_tree.delete(item)
        for idx, row in enumerate(self.filtered_artwork_rows):
            self.artwork_tree.insert(
                "",
                tk.END,
                iid=str(idx),
                values=(
                    row.get("thumbnail_display", ""),
                    row.get("artist", ""),
                    row.get("album", ""),
                    row.get("year", ""),
                    row.get("readiness", ""),
                ),
            )
        self.artwork_status_var.set(f"{len(self.filtered_artwork_rows)} artwork item(s)")

    def selected_artwork_row(self) -> dict:
        selection = self.artwork_tree.selection()
        if not selection:
            return {}
        index = int(selection[0])
        if index >= len(self.filtered_artwork_rows):
            return {}
        return self.filtered_artwork_rows[index]

    def open_selected_artwork_album(self):
        row = self.selected_artwork_row()
        if not row:
            self.artwork_status_var.set("Select an artwork item first.")
            return
        details = album_details(self.library_data, row.get("album_id", ""))
        if not details:
            self.artwork_status_var.set("Selected album is not available in Library data.")
            return
        self.tabs.select(self.archive_tab)
        self.archive_sections.select(self.library_tab)
        self.library_selected_album = details
        self.set_library_detail(details)
        self.artwork_status_var.set("Opened album details.")

    def open_selected_artwork_folder(self):
        row = self.selected_artwork_row()
        if not row:
            self.artwork_status_var.set("Select an artwork item first.")
            return
        details = album_details(self.library_data, row.get("album_id", ""))
        target, reason = album_archive_operation_target(details)
        if not target:
            self.artwork_status_var.set(reason)
            return
        result = run_operation("open_album_folder", target, self.audio_settings, OPERATION_HISTORY_FILE)
        self.artwork_status_var.set(f"{result['result'].title()}: {result['message']}")

    def run_library_album_operation(self, operation_id: str):
        target, reason = album_archive_operation_target(self.library_selected_album)
        if not target:
            self.library_operation_result_var.set(f"Failure: {reason}")
            return
        album_id = self.library_selected_album.get("album_id", "")
        result = run_operation(operation_id, target, self.audio_settings, OPERATION_HISTORY_FILE)
        self.library_operation_result_var.set(f"{result['result'].title()}: {result['message']}")
        self.refresh_library()
        if hasattr(self, "archive_tree"):
            self.refresh_archive_browser()
        if album_id:
            self.library_selected_album = album_details(self.library_data, album_id)
            self.set_library_detail(self.library_selected_album)
        self.refresh_audio_dashboard()

    def run_library_album_playback(self, operation_id: str):
        target, reason = album_archive_operation_target(self.library_selected_album)
        if not target:
            self.library_operation_result_var.set(f"Failure: {reason}")
            return
        result = run_playback_action(operation_id, target, self.audio_settings, OPERATION_HISTORY_FILE)
        self.library_operation_result_var.set(f"{result['result'].title()}: {result['message']}")
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
        self.tabs.select(self.archive_tab)
        self.archive_sections.select(self.library_tab)
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
        self.refresh_tool_settings_status()
        self.status.config(text="Hub settings saved")

    def reload_audio_settings(self):
        self.audio_settings = load_audio_division_settings(AUDIO_DIVISION_SETTINGS_FILE)
        for (section, key), var in self.audio_setting_vars.items():
            var.set(self.audio_settings.get(section, {}).get(key, ""))
        self.refresh_tool_settings_status()
        self.status.config(text="Hub settings reloaded")

    # ---------------- Sorting ----------------

    def on_sort_change(self, event):
        self.sort_mode = (
            "last_added"
            if self.sort_box.get() == "Last added"
            else "alphabetical"
        )
        self.refresh_artists()

    def get_sorted_artists(self):
        presentations = load_artist_presentations(ARTISTS_DIR, DATA_DIR)
        return sort_artist_presentations(
            presentations,
            sort_mode=self.sort_mode,
            created_meta=load_meta()["created"],
        )

    # ---------------- Modes ----------------

    def show_artist_mode(self):
        self.main_mode = "artist"
        label = "Acquisition"
        if self.current_artist_presentation:
            label = f"Acquisition - {self.current_artist_presentation.display_name}"
        self.main_label.config(text=label)
        self.main_editor.pack_forget()
        self.acquisition_tree.pack(fill="both", expand=True)

    def show_inbox_mode(self):
        self.main_mode = "inbox"
        self.main_label.config(text="Inbox")
        self.main_editor.config(state="normal")
        self.current_artist_model = None
        self.current_artist_presentation = None
        self.artist_release_lines = {}
        self.selected_acquisition_release = None
        self.acquisition_tree.pack_forget()
        self.main_editor.pack(fill="both", expand=True)
        self.load_inbox()

    # ---------------- Artist ----------------

    def refresh_artists(self):
        ARTISTS_DIR.mkdir(parents=True, exist_ok=True)
        self.artist_list.delete(0, tk.END)
        self.artist_presentations = list(self.get_sorted_artists())
        for presentation in self.artist_presentations:
            self.artist_list.insert(tk.END, presentation.display_name)

    def open_selected_artist(self, event=None):
        selection = self.artist_list.curselection()
        if not selection:
            return

        index = selection[0]
        if index >= len(self.artist_presentations):
            return
        presentation = self.artist_presentations[index]
        self.current_artist_presentation = presentation
        self.current_artist_filename = presentation.projection_name

        self.show_artist_mode()
        self.main_label.config(text=f"Acquisition - {presentation.display_name}")

        self.current_artist_model = presentation.artist
        self.artist_release_lines = release_line_map(self.current_artist_model)
        self.render_acquisition_grid(preserve_selection=False)
        record_created(presentation.projection_name)

    def artist_presentation_from_event(self, event):
        if event and getattr(event, "y", None) is not None:
            index = self.artist_list.nearest(event.y)
            bounds = self.artist_list.bbox(index)
            if bounds and bounds[1] <= event.y <= bounds[1] + bounds[3] and 0 <= index < len(self.artist_presentations):
                self.artist_list.selection_clear(0, tk.END)
                self.artist_list.selection_set(index)
                self.artist_list.activate(index)
                return self.artist_presentations[index]
        selection = self.artist_list.curselection()
        if selection and selection[0] < len(self.artist_presentations):
            return self.artist_presentations[selection[0]]
        return None

    def show_artist_menu(self, event):
        presentation = self.artist_presentation_from_event(event)
        if not presentation:
            return
        menu = tk.Menu(self, tearoff=False)
        menu.add_command(label="Update Artist", command=lambda: self.artist_menu_placeholder("Update Artist", presentation))
        menu.add_command(label="Fetch New Releases", command=lambda: self.artist_menu_placeholder("Fetch New Releases", presentation))
        menu.add_separator()
        menu.add_command(label="Show Acquisition", command=lambda: self.show_artist_acquisition(presentation))
        menu.add_command(label="Show Archive", command=lambda: self.show_artist_archive(presentation))
        menu.add_command(label="Open Artist Folder", command=lambda: self.open_artist_folder(presentation))
        menu.add_separator()
        menu.add_command(label="Rebuild Projection", command=lambda: self.rebuild_artist_projection(presentation))
        menu.add_command(label="Remove Artist", command=lambda: self.remove_artist_projection(presentation))
        menu.tk_popup(event.x_root, event.y_root)

    def artist_menu_placeholder(self, action: str, presentation):
        self.status.config(text=f"{action} is managed by the curator workflow: {presentation.display_name}")

    def show_artist_acquisition(self, presentation):
        try:
            index = self.artist_presentations.index(presentation)
        except ValueError:
            index = -1
        if index >= 0:
            self.artist_list.selection_clear(0, tk.END)
            self.artist_list.selection_set(index)
            self.artist_list.see(index)
            self.open_selected_artist()

    def show_artist_archive(self, presentation):
        if not getattr(self, "archive_albums", []):
            self.refresh_archive_browser()
        artist_name = presentation.artist.artist_name.casefold()
        album = next(
            (
                row
                for row in self.archive_albums
                if str(row.get("artist") or "").casefold() == artist_name
            ),
            {},
        )
        if not album:
            self.status.config(text=f"No archive entry found for {presentation.display_name}")
            return
        self.open_archive_album(album)

    def open_artist_folder(self, presentation):
        folder = Path(presentation.projection_path).parent
        if not folder.exists():
            self.status.config(text="Artist folder not found")
            return
        subprocess.Popen(["xdg-open", str(folder)])

    def rebuild_artist_projection(self, presentation):
        self.current_artist_presentation = load_artist_presentation(presentation.projection_path, DATA_DIR)
        self.current_artist_model = self.current_artist_presentation.artist
        self.current_artist_filename = self.current_artist_presentation.projection_name
        self.artist_release_lines = release_line_map(self.current_artist_model)
        self.render_acquisition_grid(preserve_selection=True)
        self.status.config(text=f"Rebuilt projection: {self.current_artist_presentation.display_name}")

    def remove_artist_projection(self, presentation):
        if not messagebox.askyesno(
            "Remove Artist",
            f"Remove acquisition projection for {presentation.display_name}?\n\n"
            "Archive, metadata, downloads, identity, and history will not be touched.",
        ):
            return
        path = Path(presentation.projection_path)
        try:
            path.unlink()
        except FileNotFoundError:
            pass
        self.current_artist_presentation = None
        self.current_artist_model = None
        self.current_artist_filename = None
        self.artist_release_lines = {}
        self.refresh_artists()
        self.render_acquisition_grid(preserve_selection=False)
        self.status.config(text=f"Removed acquisition projection: {presentation.display_name}")

    def render_acquisition_grid(self, *, preserve_selection: bool = True):
        selected_ids, scroll_top = self.capture_acquisition_grid_state() if preserve_selection else (set(), 0.0)
        for item in self.acquisition_tree.get_children():
            self.acquisition_tree.delete(item)
        self.acquisition_rows = list(self.current_artist_model.releases) if self.current_artist_model else []
        self.apply_acquisition_sort()
        self.selected_acquisition_release = None
        restored_selection = []
        for index, release in enumerate(self.acquisition_rows):
            recommendation = release.acquisition_recommendation.get(
                "recommendation",
                release.acquisition_status,
            )
            iid = str(index)
            release_id = self.acquisition_release_id(release)
            self.acquisition_tree.insert(
                "",
                tk.END,
                iid=iid,
                values=(
                    human_status(recommendation),
                    release.title,
                    release.year,
                    human_status(release.type),
                    human_status(release.archive_status),
                    human_status(release.lifecycle_state),
                    human_status(release.validation_status),
                    human_status(release.metadata_status),
                    human_status(release.identity_confidence),
                ),
            )
            if release_id in selected_ids:
                restored_selection.append(iid)
        if restored_selection:
            self.acquisition_tree.selection_set(restored_selection)
            self.acquisition_tree.focus(restored_selection[0])
            self.acquisition_tree.see(restored_selection[0])
            self.on_acquisition_selected()
        elif preserve_selection:
            self.selected_acquisition_release_id = ""
        elif not preserve_selection:
            self.selected_acquisition_release_id = ""
            self.selected_acquisition_release = None
        if preserve_selection:
            self.restore_acquisition_scroll(scroll_top)

    def capture_acquisition_grid_state(self) -> tuple[set[str], float]:
        selected_ids = {
            self.acquisition_release_id(release)
            for release in self.selected_artist_releases()
            if self.acquisition_release_id(release)
        }
        if self.selected_acquisition_release_id:
            selected_ids.add(self.selected_acquisition_release_id)
        try:
            scroll_top = self.acquisition_tree.yview()[0]
        except tk.TclError:
            scroll_top = 0.0
        return selected_ids, scroll_top

    def restore_acquisition_scroll(self, scroll_top: float):
        try:
            self.acquisition_tree.yview_moveto(scroll_top)
        except tk.TclError:
            pass

    def sort_acquisition_grid(self, column: str):
        if self.acquisition_sort_column == column:
            self.acquisition_sort_reverse = not self.acquisition_sort_reverse
        else:
            self.acquisition_sort_column = column
            self.acquisition_sort_reverse = False
        self.render_acquisition_grid(preserve_selection=True)

    def apply_acquisition_sort(self):
        if not self.acquisition_sort_column:
            return
        self.acquisition_rows.sort(
            key=lambda release: self.acquisition_sort_value(release, self.acquisition_sort_column),
            reverse=self.acquisition_sort_reverse,
        )

    def acquisition_sort_value(self, release, column: str):
        values = {
            "status": release.acquisition_recommendation.get("recommendation", release.acquisition_status),
            "album": release.title,
            "year": release.year,
            "type": release.type,
            "archive": release.archive_status,
            "lifecycle": release.lifecycle_state,
            "validation": release.validation_status,
            "metadata": release.metadata_status,
            "identity": release.identity_confidence,
        }
        value = values.get(column, "")
        if column == "year":
            try:
                return int(value)
            except (TypeError, ValueError):
                return 0
        return str(value or "").casefold()

    def acquisition_release_id(self, release) -> str:
        return str(getattr(release, "deezer_album_id", "") or getattr(release, "url", "") or "")

    def selected_artist_releases(self):
        if not self.current_artist_model:
            return []
        releases = []
        for iid in self.acquisition_tree.selection():
            index = int(iid)
            if index >= len(self.acquisition_rows):
                continue
            releases.append(self.acquisition_rows[index])
        if not releases and self.selected_acquisition_release:
            releases.append(self.selected_acquisition_release)
        return releases

    def on_acquisition_selected(self, event=None):
        selection = self.acquisition_tree.selection()
        if not selection:
            self.selected_acquisition_release = None
            self.selected_acquisition_release_id = ""
            return
        index = int(selection[0])
        if index >= len(self.acquisition_rows):
            self.selected_acquisition_release = None
            self.selected_acquisition_release_id = ""
            return
        self.selected_acquisition_release = self.acquisition_rows[index]
        self.selected_acquisition_release_id = self.acquisition_release_id(self.selected_acquisition_release)

    def on_acquisition_double_click(self, event=None):
        release = self.release_from_acquisition_event(event) or self.selected_acquisition_release
        if not release:
            return
        if release.archive_path:
            self.open_release_archive_workspace(release)
        else:
            self.select_release_for_acquisition(release)
        return "break"

    def release_from_acquisition_event(self, event):
        iid = ""
        if event and getattr(event, "y", None) is not None:
            iid = self.acquisition_tree.identify_row(event.y)
        if not iid:
            selection = self.acquisition_tree.selection()
            iid = selection[0] if selection else self.acquisition_tree.focus()
        if not iid:
            return None
        self.acquisition_tree.selection_set(iid)
        try:
            index = int(iid)
        except ValueError:
            return None
        if index >= len(self.acquisition_rows):
            return None
        release = self.acquisition_rows[index]
        self.selected_acquisition_release = release
        self.selected_acquisition_release_id = self.acquisition_release_id(release)
        return release

    def show_acquisition_menu(self, event):
        release = self.release_from_acquisition_event(event)
        if not release:
            return
        self.selected_acquisition_release = release
        menu = tk.Menu(self, tearoff=False)
        has_url = bool(release.url)
        has_archive = bool(release.archive_path)
        download_folder = self.release_download_folder(release)
        queue_key = self.acquisition_release_id(release)
        in_worklist = bool(queue_key and queue_key in self.acquisition_queue.get("items", {}))
        menu.add_command(
            label="Acquire",
            command=lambda: self.select_release_for_acquisition(release),
            state=tk.NORMAL if has_url else tk.DISABLED,
        )
        menu.add_separator()
        menu.add_command(
            label="Open on Deezer",
            command=lambda: webbrowser.open(release.url),
            state=tk.NORMAL if has_url else tk.DISABLED,
        )
        menu.add_command(
            label="Copy Deezer Link",
            command=lambda: self.copy_release_link(release),
            state=tk.NORMAL if has_url else tk.DISABLED,
        )
        menu.add_separator()
        menu.add_command(
            label="Open Download Folder",
            command=lambda: self.open_release_download_folder(release),
            state=tk.NORMAL if download_folder else tk.DISABLED,
        )
        menu.add_command(
            label="Show in Archive",
            command=lambda: self.open_release_archive_workspace(release),
            state=tk.NORMAL if has_archive else tk.DISABLED,
        )
        menu.add_separator()
        menu.add_command(label="View Identity", command=lambda: self.show_release_identity(release))
        menu.add_separator()
        menu.add_command(
            label="Remove From Worklist",
            command=lambda: self.remove_release_from_worklist(release),
            state=tk.NORMAL if in_worklist else tk.DISABLED,
        )
        menu.tk_popup(event.x_root, event.y_root)

    def select_release_for_acquisition(self, release):
        self.selected_acquisition_release = release
        self.selected_acquisition_release_id = self.acquisition_release_id(release)
        self.status.config(text=f"Selected for acquisition: {release.title}")

    def queue_release_for_acquisition(self, release):
        self.add_release_to_acquisition_queue(release)
        self.status.config(text=f"Queued for acquisition: {release.title}")

    def copy_release_link(self, release):
        self.clipboard_clear()
        self.clipboard_append(release.url)
        self.status.config(text="Copied Deezer link")

    def copy_selected_release_link(self):
        releases = self.selected_artist_releases()
        if not releases:
            self.status.config(text="Select a release first")
            return
        self.copy_release_link(releases[0])
        return "break"

    def release_download_folder(self, release) -> str:
        album_id = str(getattr(release, "deezer_album_id", "") or "")
        title = str(getattr(release, "title", "") or "").casefold()
        artist = self.current_artist_model.artist_name.casefold() if self.current_artist_model else ""
        rows = getattr(self, "closed_loop_rows", []) or []
        if not rows and hasattr(self, "refresh_processing_queue_view"):
            self.refresh_processing_queue_view()
            rows = getattr(self, "closed_loop_rows", []) or []
        for row in rows:
            if album_id and str(row.get("album_id") or "") == album_id:
                folder = str(row.get("folder") or "")
                if folder and Path(folder).exists():
                    return folder
            row_artist = str(row.get("artist") or "").casefold()
            row_album = str(row.get("album") or "").casefold()
            if artist and title and row_artist == artist and row_album == title:
                folder = str(row.get("folder") or "")
                if folder and Path(folder).exists():
                    return folder
        return ""

    def open_release_download_folder(self, release):
        folder = self.release_download_folder(release)
        if not folder:
            self.status.config(text="No download folder found for release")
            return
        subprocess.Popen(["xdg-open", folder])

    def remove_release_from_worklist(self, release):
        key = self.acquisition_release_id(release)
        if not key:
            self.status.config(text="Release has no worklist identity")
            return
        self.acquisition_queue = remove_queue_item(self.acquisition_queue, key)
        self.persist_acquisition_queue()
        self.status.config(text=f"Removed from worklist: {release.title}")

    def show_selected_release_identity(self):
        releases = self.selected_artist_releases()
        if not releases:
            self.status.config(text="Select a release first")
            return
        self.show_release_identity(releases[0])

    def show_release_identity(self, release):
        recommendation = release.acquisition_recommendation
        messagebox.showinfo(
            "Release Identity",
            "\n".join(
                [
                    f"Album: {release.title}",
                    f"Deezer album ID: {release.deezer_album_id}",
                    f"Artist: {self.current_artist_model.artist_name if self.current_artist_model else ''}",
                    f"Identity confidence: {human_status(release.identity_confidence)}",
                    f"Archive path: {release.archive_path or 'not archived'}",
                    f"Lifecycle: {human_status(release.lifecycle_state)}",
                    f"Validation: {human_status(release.validation_status)}",
                    f"Metadata: {human_status(release.metadata_status)}",
                    f"Recommendation: {human_status(recommendation.get('recommendation', 'UNKNOWN'))}",
                    f"Reason: {recommendation.get('reason', '')}",
                    f"Next action: {recommendation.get('next_action', '')}",
                ]
            ),
        )

    def refresh_acquisition_metadata(self):
        self.refresh_archive_metadata()
        if self.current_artist_presentation:
            self.current_artist_presentation = load_artist_presentation(
                self.current_artist_presentation.projection_path,
                DATA_DIR,
            )
            self.current_artist_model = self.current_artist_presentation.artist
            self.current_artist_filename = self.current_artist_presentation.projection_name
            self.artist_release_lines = release_line_map(self.current_artist_model)
            self.render_acquisition_grid()

    def open_release_archive_workspace(self, release):
        if not release.archive_path:
            self.status.config(text="No archive path for release")
            return
        if not getattr(self, "archive_albums", []):
            self.refresh_archive_browser()
        album = next(
            (
                row
                for row in self.archive_albums
                if str(row.get("archive_path") or "") == release.archive_path
                or str(row.get("album_id") or "") == release.deezer_album_id
            ),
            {},
        )
        if not album:
            self.status.config(text="Archive row not found for release")
            return
        self.open_archive_album(album)
        self.status.config(text=f"Opened archive workspace: {release.title}")

    def open_archive_album(self, album: dict):
        if hasattr(self, "archive_tab"):
            self.tabs.select(self.archive_tab)
        if hasattr(self, "archive_sections"):
            self.archive_sections.select(0)
        artist_iid = f"artist:{album.get('artist_key', '')}"
        if hasattr(self, "archive_tree") and self.archive_tree.exists(artist_iid):
            parent = self.archive_tree.parent(artist_iid)
            if parent:
                self.archive_tree.item(parent, open=True)
            self.archive_tree.item(artist_iid, open=True)
            self.archive_tree.selection_set(artist_iid)
            self.archive_tree.focus(artist_iid)
            self.archive_tree.see(artist_iid)
            self._load_archive_artist_albums(album.get("artist_key", ""), self._archive_album_key(album), None)
            selection = self.archive_album_tree.selection()
            if selection:
                self.archive_album_tree.focus(selection[0])
                self.archive_album_tree.see(selection[0])
                self.archive_album_tree.focus_set()
        self.archive_selected_album = album
        self.set_archive_detail(album)

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

    # ---------------- Queue helpers ----------------

    def acquire_selected_release(self, event=None):
        if self.main_mode != "artist":
            return "break"

        count = 0
        for release in self.selected_artist_releases():
            self.add_release_to_acquisition_queue(release, persist=False)
            count += 1
        self.persist_acquisition_queue()
        self.status.config(text=f"Queued {count} album(s)")
        return "break"

    def send_selected_link_to_queue(self, event=None):
        # Deprecated: retained for older key bindings and external callbacks.
        return self.acquire_selected_release(event)

    def load_custom_queue(self):
        self.acquisition_queue = load_acquisition_queue(ACQUISITION_QUEUE_FILE)
        self.render_acquisition_queue()

    def add_release_to_acquisition_queue(self, release, *, persist: bool = True):
        artist = self.current_artist_presentation.display_name if self.current_artist_presentation else ""
        self.acquisition_queue = queue_release(self.acquisition_queue, release, artist=artist)
        if persist:
            self.persist_acquisition_queue()

    def persist_acquisition_queue(self):
        save_acquisition_queue(ACQUISITION_QUEUE_FILE, self.acquisition_queue)
        self.render_acquisition_queue()

    def render_acquisition_queue(self):
        for item in self.queue_tree.get_children():
            self.queue_tree.delete(item)
        self.acquisition_queue_rows = queue_rows(self.acquisition_queue)
        for index, row in enumerate(self.acquisition_queue_rows):
            self.queue_tree.insert(
                "",
                tk.END,
                iid=str(index),
                values=(
                    human_status(row.get("current_state", "")),
                    row.get("artist", ""),
                    row.get("album", ""),
                    human_status(row.get("release_type", "")),
                    "Deezer" if row.get("url") else "",
                    row.get("deezer_album_id", ""),
                ),
            )

    def selected_queue_rows(self) -> list[dict]:
        rows = []
        for iid in self.queue_tree.selection():
            index = int(iid)
            if index < len(self.acquisition_queue_rows):
                rows.append(self.acquisition_queue_rows[index])
        return rows

    def queue_row_from_event(self, event):
        if not event:
            return None
        iid = self.queue_tree.identify_row(event.y)
        if not iid:
            return None
        self.queue_tree.selection_set(iid)
        index = int(iid)
        if index >= len(self.acquisition_queue_rows):
            return None
        return self.acquisition_queue_rows[index]

    def show_queue_release(self, event=None):
        row = self.queue_row_from_event(event) if event else (self.selected_queue_rows()[0] if self.selected_queue_rows() else None)
        if not row:
            return
        messagebox.showinfo(
            "Acquisition Item",
            "\n".join(
                [
                    f"Artist: {row.get('artist', '')}",
                    f"Album: {row.get('album', '')}",
                    f"Release Type: {row.get('release_type', '')}",
                    "Source: Deezer" if row.get("url") else "Source: ",
                    f"Deezer Album ID: {row.get('deezer_album_id', '')}",
                    f"URL: {row.get('url', '')}",
                    f"Added Time: {row.get('queued_time', '')}",
                    f"Current State: {human_status(row.get('current_state', ''))}",
                ]
            ),
        )

    def show_queue_menu(self, event):
        row = self.queue_row_from_event(event)
        if not row:
            return
        menu = tk.Menu(self, tearoff=False)
        has_url = bool(row.get("url"))
        has_folder = bool(row.get("incoming_folder")) and Path(str(row.get("incoming_folder"))).exists()
        menu.add_command(label="Acquire", command=lambda: self.acquire_queue_album(row))
        menu.add_command(label="Remove From Worklist", command=lambda: self.remove_from_acquisition_queue(row))
        menu.add_separator()
        menu.add_command(
            label="Open on Deezer",
            command=lambda: webbrowser.open(row.get("url", "")),
            state=tk.NORMAL if has_url else tk.DISABLED,
        )
        menu.add_command(
            label="Copy Deezer Link",
            command=lambda: self.copy_queue_link(row),
            state=tk.NORMAL if has_url else tk.DISABLED,
        )
        menu.add_separator()
        menu.add_command(
            label="Open Download Folder",
            command=lambda: self.open_queue_incoming_folder(row),
            state=tk.NORMAL if has_folder else tk.DISABLED,
        )
        menu.tk_popup(event.x_root, event.y_root)

    def acquire_queue_album(self, row: dict):
        self.status.config(text=f"Managed only: {row.get('artist', '')} - {row.get('album', '')}")

    def remove_from_acquisition_queue(self, row: dict):
        self.acquisition_queue = remove_queue_item(self.acquisition_queue, row.get("key", ""))
        self.persist_acquisition_queue()
        self.status.config(text="Removed album from acquisition queue")

    def copy_queue_link(self, row: dict):
        self.clipboard_clear()
        self.clipboard_append(row.get("url", ""))
        self.status.config(text="Copied queued Deezer link")

    def open_queue_incoming_folder(self, row: dict):
        folder = row.get("incoming_folder", "")
        if not folder:
            self.status.config(text="No incoming folder recorded for queue item")
            return
        path = Path(folder)
        if not path.exists():
            self.status.config(text="Incoming folder does not exist")
            return
        subprocess.Popen(["xdg-open", str(path)])

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
