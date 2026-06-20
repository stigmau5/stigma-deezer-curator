import tkinter as tk
from tkinter import ttk, messagebox
from pathlib import Path
from datetime import datetime
import subprocess
import json
import re
import threading

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
    archive_tree,
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
from audio_division.closed_loop_monitor import (
    discover_incoming_albums,
    queue_album_payload,
)
from audio_division.integration import run_audio_division_process_album
from audio_division.maintenance import (
    maintenance_action_target,
    maintenance_albums,
    maintenance_counts,
    maintenance_summaries,
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
PROCESSING_QUEUE_FILE = DATA_DIR / "processing_queue.json"
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

        # Grep toggles
        self.include_live = tk.BooleanVar(value=True)
        self.include_compilations = tk.BooleanVar(value=True)

        self.audio_settings = load_audio_division_settings(AUDIO_DIVISION_SETTINGS_FILE)
        self.audio_setting_vars: dict[tuple[str, str], tk.StringVar] = {}
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
        self._archive_audit_running = False
        self.archive_current_nfo: dict = {}
        self.library_current_nfo: dict = {}
        self.processing_queue = load_processing_queue(PROCESSING_QUEUE_FILE)
        self.processing_queue_rows: list[dict] = []
        self.closed_loop_rows: list[dict] = []
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

        self.title("STiGMA Deezer Curator — v0.3.1")
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

        curator_tab = ttk.Frame(self.tabs)
        self.tabs.add(curator_tab, text="Curator")

        audio_tab = ttk.Frame(self.tabs, padding=10)
        self.tabs.add(audio_tab, text="Audio Division")

        archive_tab = ttk.Frame(self.tabs, padding=10)
        self.tabs.add(archive_tab, text="Archive")

        library_tab = ttk.Frame(self.tabs, padding=10)
        self.tabs.add(library_tab, text="Library")
        self.library_tab = library_tab

        artwork_tab = ttk.Frame(self.tabs, padding=10)
        self.tabs.add(artwork_tab, text="Artwork")

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
        self._build_archive_tab(archive_tab)
        self._build_library_tab(library_tab)
        self._build_artwork_tab(artwork_tab)
        self._build_opportunities_tab(opportunities_tab)
        self._build_hub_opportunities_tab(hub_tab)
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
        ttk.Button(buttons, text="Validate Album", command=lambda: self.run_library_album_operation("validate_album")).pack(side="left")
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
        self.archive_audit_button = ttk.Button(toolbar, text="Run Audit", command=self.run_archive_audit)
        self.archive_audit_button.pack(side="left", padx=(6, 0))
        ttk.Label(toolbar, textvariable=self.archive_audit_status_var).pack(side="left", padx=(8, 0))
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
            columns=("album", "source", "folder", "state"),
            show="headings",
            height=5,
            selectmode="browse",
        )
        for column, title, width in (
            ("album", "Album", 210),
            ("source", "Source", 80),
            ("folder", "Folder", 220),
            ("state", "Current State", 120),
        ):
            self.processing_queue_tree.heading(column, text=title)
            self.processing_queue_tree.column(column, width=width, anchor="w")
        self.processing_queue_tree.pack(fill="x", expand=False)
        monitor_actions = ttk.Frame(processing)
        monitor_actions.pack(fill="x", pady=(4, 0))
        ttk.Button(monitor_actions, text="Open Folder", command=self.open_selected_incoming_folder).pack(side="left")
        ttk.Button(monitor_actions, text="Queue For Processing", command=self.queue_selected_incoming_album).pack(side="left", padx=(4, 0))

        maintenance = ttk.LabelFrame(album_frame, text="Maintenance Center", padding=4)
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
            columns=("artist", "album", "priority", "reason"),
            show="headings",
            height=6,
            selectmode="browse",
        )
        for column, title, width in (
            ("artist", "Artist", 140),
            ("album", "Album", 220),
            ("priority", "Priority", 80),
            ("reason", "Reason", 260),
        ):
            self.maintenance_album_tree.heading(column, text=title)
            self.maintenance_album_tree.column(column, width=width, anchor="w")
        maintenance_panes.add(self.maintenance_album_tree, weight=2)
        self.maintenance_album_tree.bind("<Double-1>", lambda event: self.open_selected_maintenance_album())

        maintenance_actions = ttk.Frame(maintenance)
        maintenance_actions.pack(fill="x", pady=(4, 0))
        ttk.Button(maintenance_actions, text="Open Album", command=self.open_selected_maintenance_album).pack(side="left")
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
        ttk.Button(operations, text="Validate", command=lambda: self.run_archive_album_operation("validate_album")).grid(row=0, column=0, sticky="ew", padx=(0, 3), pady=(0, 3))
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
        ttk.Button(buttons, text="Reconcile Archive", command=self.reconcile_archive_report).pack(side="left", padx=(6, 0))

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
            ("tools", "audio_division_path", "Audio Division Path"),
            ("tools", "nfo_generator_path", "NFO Generator Path"),
            ("tools", "sfv_generator_path", "SFV Generator Path"),
            ("tools", "flac_validator_path", "FLAC Validator Path"),
            ("tools", "file_manager_path", "File Manager Path"),
            ("playback", "provider", "Player Provider"),
            ("playback", "player_path", "Player Path"),
            ("playback", "player_args", "Player Arguments"),
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
                letters[letter] = self.archive_tree.insert("", tk.END, text=letter, open=True)
            self.archive_tree.insert(
                letters[letter],
                tk.END,
                iid=f"artist:{row['artist_key']}",
                text=f"{row['artist']} ({row['album_count']})",
            )
        self.refresh_processing_queue_view()
        self.refresh_maintenance_view()
        if restore_artist_key:
            artist_iid = f"artist:{restore_artist_key}"
            if self.archive_tree.exists(artist_iid):
                self.archive_tree.selection_set(artist_iid)
                self.archive_tree.see(artist_iid)
                self._load_archive_artist_albums(restore_artist_key, restore_album_key, restore_album_yview)
                return
        self.clear_archive_albums()

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
        workspace = album_workspace(details, load_json(DATA_DIR / "metadata_cache.json"))
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
        result = run_audio_division_process_album(target, self.audio_settings, OPERATION_HISTORY_FILE)
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
        self.processing_queue_rows = discover_incoming_albums(
            self.audio_settings,
            self.archive_albums,
            self.processing_queue,
        )
        self.closed_loop_rows = self.processing_queue_rows
        for item in self.processing_queue_tree.get_children():
            self.processing_queue_tree.delete(item)
        for index, row in enumerate(self.processing_queue_rows[:100]):
            self.processing_queue_tree.insert(
                "",
                tk.END,
                iid=str(index),
                values=(
                    row.get("album", ""),
                    row.get("source", ""),
                    self._shorten_path(row.get("folder", ""), max_chars=38),
                    row.get("state", ""),
                ),
            )

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
        workspace = album_workspace(details, load_json(DATA_DIR / "metadata_cache.json"))
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
        self.tabs.select(self.library_tab)
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
