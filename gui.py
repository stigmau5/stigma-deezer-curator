import tkinter as tk
from tkinter import ttk, messagebox
from pathlib import Path
from datetime import datetime
from types import SimpleNamespace
import json
import subprocess
import threading
import webbrowser

from identity_viewer import IdentityViewer

from curator.curate import run_curation
from curator.state import (
    load_confirmed,
    save_confirmed,
    confirm_album,
    album_id_from_url,
)
from curator.attempts import (
    load_attempts,
    save_attempts,
    record_attempt,
)
from curator.preferences import (
    load_preferences,
    save_preferences,
)
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
from audio_division.album_workspace import album_workspace
from audio_division.active_album import ActiveAlbum, active_album_from_row, active_album_index, restore_active_album
from audio_division.canonical_album import AlbumRef, CanonicalAlbumResolver
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
from audio_division.closed_loop_monitor import (
    discover_incoming_albums,
    queue_album_payload,
)
from audio_division.integration import run_audio_division_process_album
from audio_division.maintenance import (
    maintenance_action_target,
    maintenance_albums,
    maintenance_counts,
    maintenance_operation_for_album,
    maintenance_summaries,
)
from audio_division.metadata_enrichment import rebuild_metadata_enrichment
from audio_division.context_navigation import (
    context_actions,
    context_album_id,
    context_deezer_link,
    context_folder,
    context_parent_folder,
)
from audio_division.artist_model import (
    load_artist_file,
    release_line_map,
    releases_for_section,
    render_artist_text,
)

# NEW: server shipping
from curator.ship import ShipConfig, ship_urls

# ---------------- Paths ----------------

BASE_DIR = Path(__file__).resolve().parent
DATA_DIR = BASE_DIR / "data"

INBOX_FILE = DATA_DIR / "inbox.txt"
LOG_FILE = DATA_DIR / "curated.log"
ARTISTS_DIR = DATA_DIR / "artists"
SHIPPED_DIR = DATA_DIR / "shipped"

CONFIRMED_FILE = DATA_DIR / "confirmed_albums.json"
ATTEMPTS_FILE = DATA_DIR / "attempted_albums.json"
PREFS_FILE = DATA_DIR / "preferences.json"
VALIDATED_INDEX = DATA_DIR / "validated_albums.json"
AUDIO_DIVISION_SETTINGS_FILE = DATA_DIR / "audio_division_settings.json"
OPERATION_HISTORY_FILE = DATA_DIR / "operation_history.json"
PROCESSING_QUEUE_FILE = DATA_DIR / "processing_queue.json"

STREAMRIP_BIN = Path("/home/stigma/apps/streamrip/bin/rip")
STREAMRIP_QUEUE = Path("/home/stigma/apps/streamrip/download_que.txt")

BATCH_OPTIONS = [2, 4, 6, 8, 10, 12, 14, 16, 18, 20]

# ---------------- Helpers ----------------


def load_validated_ids(path: Path) -> set[str]:
    if not path.exists():
        return set()
    try:
        data = json.loads(path.read_text())
        return set(data.keys())
    except Exception:
        return set()


def extract_http_links(text: str) -> list[str]:
    links: list[str] = []
    for line in text.splitlines():
        s = line.strip()
        if not s.startswith("http"):
            continue
        # keep first token (allows comments after url)
        links.append(s.split()[0])
    return links


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

        self.main_mode = "artist"
        self.current_artist_filename = None
        self.current_artist_model = None
        self.artist_release_lines = {}
        self.acquisition_rows = []
        self.selected_acquisition_release = None
        self.inbox_editable = False

        self.prefs = load_preferences(PREFS_FILE)
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
        self.active_archive_album = ActiveAlbum()
        self.archive_tree_open_items: set[str] = set()
        self.archive_artist_var = tk.StringVar()
        self.archive_album_var = tk.StringVar()
        self.archive_operation_result_var = tk.StringVar()
        self.archive_operation_last_run_var = tk.StringVar(value="Last run: never")
        self.archive_audit_status_var = tk.StringVar(value="")
        self.archive_revalidation_status_var = tk.StringVar(value="")
        self._archive_audit_running = False
        self._archive_revalidation_running = False
        self.archive_current_nfo: dict = {}
        self.archive_current_tracklist: dict = {}
        self.library_current_nfo: dict = {}
        self.processing_queue = load_processing_queue(PROCESSING_QUEUE_FILE)
        self.processing_queue_rows: list[dict] = []
        self.closed_loop_rows: list[dict] = []
        self.maintenance_rows: list[dict] = []
        self.maintenance_album_rows: list[dict] = []
        self.selected_maintenance_id = ""
        self.maintenance_summary_labels: dict[str, ttk.Label] = {}
        self.batch_size = int(self.prefs.get("batch_size", 6))

        # NEW: server shipping config (defaults; can be moved into prefs later)
        self.ship_ssh_host = self.prefs.get("ship_ssh_host", "stigma@stigma-mediaserver")
        self.ship_pending_dir = self.prefs.get(
            "ship_pending_dir", "/media/storage/streamrip/jobs/pending"
        )

        # NEW: ship state guard (prevents overlapping ship runs)
        self._ship_running = False

        self.confirmed = load_confirmed(CONFIRMED_FILE)
        self.attempts = load_attempts(ATTEMPTS_FILE)
        self.validated_ids = load_validated_ids(VALIDATED_INDEX)

        self.fire_history: list[list[str]] = []
        self.MAX_FIRE_HISTORY = 10

        self.title(f"STiGMA Archive Hub — batch {self.batch_size}")
        self.minsize(1100, 650)
        self.geometry(self._initial_window_geometry())
        self.protocol("WM_DELETE_WINDOW", self.on_close)

        self._build_layout()
        self.after(150, self.restore_layout_state)
        self.full_refresh()

        # ---------------- Global hotkeys ----------------
        self.bind_all("<Control-i>", lambda e: self.open_identity_viewer())
        self.bind_all("<Control-e>", self.toggle_inbox_edit)
        self.bind_all("<Control-Shift-Return>", lambda e: self.send_to_streamrip())
        self.bind_all("<F5>", lambda e: self.full_refresh())

        # Artist navigation
        self.main_editor.bind("<Up>", lambda e: self.move_cursor(-1))
        self.main_editor.bind("<Down>", lambda e: self.move_cursor(1))
        self.main_editor.bind("<Control-Up>", lambda e: self.extend_selection(-1))
        self.main_editor.bind("<Control-Down>", lambda e: self.extend_selection(1))
        self.main_editor.bind("<Escape>", lambda e: self.clear_selection())

        # Block edits
        self.main_editor.bind("<Key>", self._block_edit)
        self.main_editor.bind("<BackSpace>", self._block_edit)
        self.main_editor.bind("<Delete>", self._block_edit)
        self.main_editor.bind("<Return>", self._block_edit)

        # Fire / pull
        self.main_editor.bind("<Control-Right>", self.fire_selected_lines)
        self.main_editor.bind("<Control-Left>", self.pull_back)

    # ---------------- Edit control ----------------

    def toggle_inbox_edit(self, event=None):
        if self.main_mode != "inbox":
            self.status.config(text="Inbox edit only available in Inbox mode")
            return "break"

        self.inbox_editable = not self.inbox_editable
        state = "ON" if self.inbox_editable else "OFF"
        self.status.config(text=f"Inbox edit {state}")
        return "break"

    def _block_edit(self, event):
        if self.main_mode == "inbox" and self.inbox_editable:
            return
        if event.state & 0x4:  # allow Ctrl shortcuts
            return
        return "break"

    # ---------------- Identity Viewer ----------------

    def open_identity_viewer(self):
        IdentityViewer(
            self,
            curated_dir=ARTISTS_DIR,
            validated_json=VALIDATED_INDEX,
            confirmed_json=CONFIRMED_FILE,
        )

    # ---------------- Refresh ----------------

    def full_refresh(self):
        self.validated_ids = load_validated_ids(VALIDATED_INDEX)
        self.refresh_artists()
        if self.current_artist_filename:
            self.open_selected_artist()
        self.refresh_audio_dashboard()
        self.refresh_library()
        self.status.config(text="Refreshed from disk")

    # ---------------- Layout ----------------

    def _build_layout(self):
        self.tabs = ttk.Notebook(self)
        self.tabs.pack(fill="both", expand=True)

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

        left = ttk.Frame(main, padding=6)
        main.add(left, weight=1)

        ttk.Label(left, text="Artists").pack(anchor="w")
        self.artist_list = tk.Listbox(left)
        self.artist_list.pack(fill="both", expand=True)
        self.artist_list.bind("<<ListboxSelect>>", self.open_selected_artist)

        center = ttk.Frame(main, padding=6)
        main.add(center, weight=2)

        self.main_label = ttk.Label(center, text="Acquisition")
        self.main_label.pack(anchor="w")

        acquisition_columns = (
            "status",
            "album",
            "year",
            "type",
            "archive",
            "lifecycle",
            "validation",
            "metadata",
        )
        self.acquisition_tree = ttk.Treeview(
            center,
            columns=acquisition_columns,
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
        ):
            self.acquisition_tree.heading(column, text=title)
            self.acquisition_tree.column(column, width=width, anchor="w")
        self.acquisition_tree.pack(fill="both", expand=True)
        self.acquisition_tree.bind("<<TreeviewSelect>>", self.on_acquisition_selected)
        self.acquisition_tree.bind("<Double-1>", self.on_acquisition_double_click)
        self.acquisition_tree.bind("<Button-3>", self.show_acquisition_menu)
        self.acquisition_tree.bind("<Control-Right>", self.acquire_selected_release)

        self.main_editor = tk.Text(center, wrap="none")

        right = ttk.Frame(main, padding=6)
        main.add(right, weight=2)

        ttk.Label(right, text="Acquisition Worklist").pack(anchor="w")
        self.custom_editor = tk.Text(right, wrap="none")
        self.custom_editor.pack(fill="both", expand=True)

        bottom = ttk.Frame(curator_tab, padding=8)
        bottom.pack(fill="x")

        inbox_group = ttk.LabelFrame(bottom, text="Inbox", padding=(6, 3))
        inbox_group.pack(side="left", padx=(0, 8))
        ttk.Button(inbox_group, text="Show Inbox", command=self.show_inbox_mode).pack(side="left", padx=2)
        ttk.Button(inbox_group, text="Show Artist", command=self.show_artist_mode).pack(side="left", padx=2)
        ttk.Button(inbox_group, text="Save Inbox", command=self.save_inbox).pack(side="left", padx=2)
        ttk.Button(inbox_group, text="Run Curator", command=self.run_curator).pack(side="left", padx=2)

        acquire_group = ttk.LabelFrame(bottom, text="Acquire", padding=(6, 3))
        acquire_group.pack(side="left", padx=(0, 8))
        ttk.Button(acquire_group, text="Acquire Selected", command=self.acquire_selected_release).pack(side="left", padx=2)

        ttk.Label(bottom, text="Batch:").pack(side="left")
        self.batch_var = tk.IntVar(value=self.batch_size)
        self.batch_box = ttk.Combobox(
            bottom,
            values=BATCH_OPTIONS,
            width=4,
            state="readonly",
            textvariable=self.batch_var,
        )
        self.batch_box.pack(side="left")
        self.batch_box.bind("<<ComboboxSelected>>", self.on_batch_change)

        ship_group = ttk.LabelFrame(bottom, text="Ship", padding=(6, 3))
        ship_group.pack(side="left", padx=(8, 8))
        self.btn_ship_selected = ttk.Button(ship_group, text="Ship Selected", command=self.ship_selected_to_server)
        self.btn_ship_selected.pack(side="left", padx=2)
        self.btn_ship_queue = ttk.Button(ship_group, text="Ship Queue", command=self.ship_queue_to_server)
        self.btn_ship_queue.pack(side="left", padx=2)

        tools_group = ttk.LabelFrame(bottom, text="Tools", padding=(6, 3))
        tools_group.pack(side="left", padx=(0, 8))
        ttk.Button(tools_group, text="Identity Viewer", command=self.open_identity_viewer).pack(side="left", padx=2)
        ttk.Button(tools_group, text="Copy Deezer Link", command=self.copy_selected_release_link).pack(side="left", padx=2)

        self.status = ttk.Label(bottom, text="Idle")
        self.status.pack(side="right")

        self._build_archive_tab(physical_archive_tab)
        self._build_library_tab(library_tab)
        self._build_artwork_tab(artwork_tab)
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
        summary = ttk.Frame(parent)
        summary.pack(fill="x", pady=(0, 8))
        for key, label in (
            ("artists", "Artists"),
            ("albums", "Albums"),
            ("tracks", "Tracks"),
            ("metadata_coverage", "Metadata Coverage"),
            ("validation_coverage", "Validation Coverage"),
        ):
            ttk.Label(summary, text=label).pack(side="left", padx=(0, 4))
            value = ttk.Label(summary, text="0")
            value.pack(side="left", padx=(0, 16))
            self.library_summary_labels[key] = value

        panes = ttk.Panedwindow(parent, orient="horizontal")
        panes.pack(fill="both", expand=True)
        self.layout_panes["library_main"] = panes

        artist_frame = ttk.Frame(panes, padding=4)
        panes.add(artist_frame, weight=1)
        ttk.Label(artist_frame, text="Artists").pack(anchor="w")
        self.library_artist_list = tk.Listbox(artist_frame)
        self.library_artist_list.pack(fill="both", expand=True)
        self.library_artist_list.bind("<<ListboxSelect>>", self.on_library_artist_selected)

        album_frame = ttk.Frame(panes, padding=4)
        panes.add(album_frame, weight=2)
        ttk.Label(album_frame, text="Albums").pack(anchor="w")
        self.library_album_tree = ttk.Treeview(
            album_frame,
            columns=("title", "year", "type", "validation"),
            show="headings",
        )
        for column, title in (("title", "Title"), ("year", "Year"), ("type", "Type"), ("validation", "Validation")):
            self.library_album_tree.heading(column, text=title)
            self.library_album_tree.column(column, width=120 if column != "title" else 260)
        self.library_album_tree.pack(fill="both", expand=True)
        self.library_album_tree.bind("<<TreeviewSelect>>", self.on_library_album_selected)
        self.library_album_tree.bind("<Button-3>", self.show_library_album_menu)

        detail_frame = ttk.Frame(panes, padding=4)
        panes.add(detail_frame, weight=4)
        ttk.Label(detail_frame, text="Album Details").pack(anchor="w")
        self.library_detail_container = ttk.Frame(detail_frame)
        self.library_detail_container.pack(fill="both", expand=True)
        self._build_library_detail_sections(self.library_detail_container)

        status_frame = ttk.LabelFrame(detail_frame, text="Album Operations", padding=6)
        status_frame.pack(fill="x", pady=(8, 0))
        buttons = ttk.Frame(status_frame)
        buttons.pack(fill="x")
        ttk.Button(buttons, text="Revalidate", command=lambda: self.run_library_album_operation("revalidate_album")).pack(side="left")
        ttk.Button(buttons, text="Generate NFO", command=lambda: self.run_library_album_operation("generate_nfo")).pack(side="left", padx=(6, 0))
        ttk.Button(buttons, text="Generate SFV", command=lambda: self.run_library_album_operation("generate_sfv")).pack(side="left", padx=(6, 0))
        ttk.Button(buttons, text="Open Folder", command=lambda: self.run_library_album_operation("open_album_folder")).pack(side="left", padx=(6, 0))
        ttk.Button(buttons, text="Play Album", command=lambda: self.run_library_album_playback("play_album")).pack(side="left", padx=(6, 0))
        ttk.Button(buttons, text="Play Playlist", command=lambda: self.run_library_album_playback("play_playlist")).pack(side="left", padx=(6, 0))
        ttk.Label(status_frame, textvariable=self.library_operation_result_var).pack(anchor="w", pady=(6, 0))

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
        self.archive_album_tree.bind("<Button-3>", self.show_archive_album_menu)

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
        self.processing_queue_tree.bind("<Button-3>", self.show_incoming_album_menu)
        monitor_actions = ttk.Frame(processing)
        monitor_actions.pack(fill="x", pady=(4, 0))
        ttk.Button(monitor_actions, text="Open Folder", command=self.open_selected_incoming_folder).pack(side="left")
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
        self.maintenance_album_tree.bind("<Button-3>", self.show_maintenance_album_menu)

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

        header = ttk.Frame(workspace, padding=(0, 0, 0, 6))
        workspace.add(header, weight=0)
        header.columnconfigure(0, weight=1)
        self.archive_header_artist_var = tk.StringVar(value="Select an album")
        self.archive_header_album_var = tk.StringVar(value="Select a release to view evidence.")
        self.archive_header_year_var = tk.StringVar(value="")
        ttk.Label(header, textvariable=self.archive_header_artist_var, font=("TkDefaultFont", 11, "bold")).grid(row=0, column=0, sticky="w")
        ttk.Label(header, textvariable=self.archive_header_album_var, font=("TkDefaultFont", 14, "bold")).grid(row=1, column=0, sticky="w")
        ttk.Label(header, textvariable=self.archive_header_year_var).grid(row=2, column=0, sticky="w")
        badges = ttk.Frame(header)
        badges.grid(row=0, column=1, rowspan=3, sticky="e", padx=(12, 0))
        self.archive_header_badges: dict[str, ttk.Label] = {}
        for index, badge in enumerate(("Lifecycle", "Readiness", "Binding")):
            label = ttk.Label(badges, text=badge, relief="ridge", padding=(8, 3))
            label.grid(row=0, column=index, padx=(0, 6))
            self.archive_header_badges[badge] = label

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
        self.archive_operation_buttons: dict[str, ttk.Button] = {}
        self.archive_operation_tooltips: dict[str, Tooltip] = {}
        operation_specs = (
            ("revalidate_album", "Revalidate", lambda: self.run_archive_album_operation("revalidate_album"), 0, 0, 1),
            ("generate_nfo", "NFO", lambda: self.run_archive_album_operation("generate_nfo"), 0, 1, 1),
            ("generate_sfv", "SFV", lambda: self.run_archive_album_operation("generate_sfv"), 1, 0, 1),
            ("open_album_folder", "Folder", lambda: self.run_archive_album_operation("open_album_folder"), 1, 1, 1),
            ("play_album", "Play Album", lambda: self.run_archive_album_playback("play_album"), 2, 0, 1),
            ("play_playlist", "Playlist", lambda: self.run_archive_album_playback("play_playlist"), 2, 1, 1),
            ("queue", "Queue", self.queue_selected_archive_album_for_processing, 3, 0, 2),
            ("process_album", "Process Album", self.process_selected_archive_album, 4, 0, 2),
        )
        for operation_id, text, command, row, column, columnspan in operation_specs:
            button = ttk.Button(operations, text=text, command=command)
            padx = (0, 3) if column == 0 and columnspan == 1 else 0
            pady = (0, 3) if row == 0 else ((3, 0) if row >= 2 else 0)
            button.grid(row=row, column=column, columnspan=columnspan, sticky="ew", padx=padx, pady=pady)
            self.archive_operation_buttons[operation_id] = button
            self.archive_operation_tooltips[operation_id] = Tooltip(button)
        operations.columnconfigure(0, weight=1)
        operations.columnconfigure(1, weight=1)
        ttk.Label(operations, textvariable=self.archive_operation_result_var, wraplength=280).grid(row=5, column=0, columnspan=2, sticky="ew", pady=(6, 0))
        ttk.Label(operations, textvariable=self.archive_operation_last_run_var, wraplength=280).grid(row=6, column=0, columnspan=2, sticky="ew")

        self.archive_presentation_labels: dict[tuple[str, str], ttk.Label] = {}
        details = ttk.Frame(summary)
        summary.add(details, weight=3)
        details.columnconfigure(0, weight=1)
        details.rowconfigure(0, weight=1)
        details_notebook = ttk.Notebook(details)
        details_notebook.grid(row=0, column=0, sticky="nsew")
        for section_id, title, fields in (
            ("overview", "Overview", ("Album title", "Artist", "Year", "Record type", "Lifecycle state", "Lifecycle evidence", "Lifecycle reason")),
            ("metadata", "Metadata", ("Label", "Genre", "Release date", "Track count", "Contributors", "Metadata status")),
            ("identity", "Identity", ("Album ID", "Identity confidence", "Archive path confidence", "Archive folder", "Archive path")),
        ):
            frame = ttk.Frame(details_notebook, padding=6)
            details_notebook.add(frame, text=title)
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

        integrity_tab = ttk.Frame(details_notebook, padding=6)
        details_notebook.add(integrity_tab, text="Integrity")
        self.archive_integrity_tab_text = self._build_scrolled_text(integrity_tab)
        self.archive_integrity_tab_text.config(state="disabled")

        files_tab = ttk.Frame(details_notebook, padding=6)
        details_notebook.add(files_tab, text="Files")
        self.archive_files_text = self._build_scrolled_text(files_tab)
        self.archive_files_text.config(state="disabled")

        nfo_tab = ttk.Frame(details_notebook, padding=6)
        details_notebook.add(nfo_tab, text="NFO")
        self.archive_view_nfo_button = ttk.Button(
            nfo_tab,
            text="View NFO",
            command=lambda: self.show_nfo_viewer(self.archive_current_nfo, self.archive_selected_album),
        )
        self.archive_view_nfo_button.pack(anchor="w", pady=(0, 6))
        self.archive_view_nfo_tooltip = Tooltip(self.archive_view_nfo_button)
        self.archive_nfo_text = self._build_scrolled_text(nfo_tab)
        self.archive_nfo_text.config(state="disabled")

        related_tab = ttk.Frame(details_notebook, padding=6)
        details_notebook.add(related_tab, text="Related")
        self.archive_relationships_text = self._build_scrolled_text(related_tab)
        self.archive_relationships_text.config(state="disabled")

        self._set_archive_empty_state()

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
                if section_id == "identity" and field == "Archive path":
                    self.library_path_label = value
                    self.library_path_tooltip = Tooltip(value)
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

    def refresh_library(self):
        if not hasattr(self, "library_artist_list"):
            return
        archive_root = self.audio_settings.get("archive_paths", {}).get("main_archive_root", "")
        self.library_data = library_from_data_dir(DATA_DIR, Path(archive_root) if archive_root else None)
        summary = self.library_data.get("summary", {})
        for key, label in self.library_summary_labels.items():
            value = summary.get(key, 0)
            label.config(text=f"{value:.1%}" if isinstance(value, float) else str(value))

        self.library_artist_rows = self.library_data.get("artists", [])
        self.library_artist_list.delete(0, tk.END)
        for artist in self.library_artist_rows:
            self.library_artist_list.insert(tk.END, f"{artist['name']} ({artist['album_count']})")
        self.clear_library_albums()
        if hasattr(self, "artwork_tree"):
            self.refresh_artwork_browser()

    def remember_active_archive_album(self) -> ActiveAlbum:
        if getattr(self, "archive_selected_album", {}):
            self.active_archive_album = active_album_from_row(self.archive_selected_album)
        return self.active_archive_album

    def capture_archive_tree_expansion(self) -> set[str]:
        if not hasattr(self, "archive_tree"):
            return set()
        return {
            str(item)
            for item in self.archive_tree.get_children("")
            if self.archive_tree.item(item, "open")
        }

    def capture_active_archive_context(self, active_tab: str = ""):
        self.remember_active_archive_album()
        self.archive_tree_open_items = self.capture_archive_tree_expansion()
        return capture_archive_selection(
            getattr(self, "archive_selected_album", {}),
            active_tab=active_tab,
            album_yview=self.archive_album_tree.yview() if hasattr(self, "archive_album_tree") else None,
        )

    def restore_active_archive_context(self, selection):
        self.refresh_archive_browser(
            restore_album_key=selection.album_key,
            restore_artist_key=selection.artist_key,
            restore_album_yview=selection.album_yview,
        )

    def find_active_archive_album(self, active: ActiveAlbum | None = None) -> dict:
        active = active or self.active_archive_album
        if not active.present:
            return {}
        return (
            restore_active_album(self.filtered_archive_albums, active)
            or restore_active_album(self.archive_albums, active)
            or {}
        )

    def resolve_archive_workspace_album(self, details: dict) -> dict:
        if not details:
            return {}
        active = active_album_from_row(details)
        physical = self.find_active_archive_album(active)
        if physical and physical is not details:
            self.archive_selected_album = physical
            self.active_archive_album = active_album_from_row(physical)
            return physical
        return details

    def preserve_archive_workspace(self):
        if self.archive_selected_album:
            self.set_archive_detail(self.archive_selected_album)

    def refresh_archive_browser(
        self,
        restore_album_key: str = "",
        restore_artist_key: str = "",
        restore_album_yview: float | None = None,
    ):
        if not hasattr(self, "archive_tree"):
            return
        active = self.remember_active_archive_album()
        open_items = self.capture_archive_tree_expansion()
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
            active_album=active,
            open_items=open_items,
        )

    def refresh_archive_metadata(self):
        selection = self.capture_active_archive_context(active_tab=self.tabs.select())
        self.set_archive_operation_result("Refresh Metadata: Running...")
        reports_dir = Path(self.audio_settings.get("reports", {}).get("reports_directory") or BASE_DIR / "reports")
        if not reports_dir.is_absolute():
            reports_dir = BASE_DIR / reports_dir
        try:
            result = rebuild_metadata_enrichment(DATA_DIR, reports_dir)
        except OSError as exc:
            self._finish_archive_operation("Refresh Metadata", False, str(exc))
            return
        self.restore_active_archive_context(selection)
        if selection.active_tab:
            self.tabs.select(selection.active_tab)
        self._finish_archive_operation(
            "Refresh Metadata",
            True,
            f"{result['albums_enriched']}/{result['albums_evaluated']} albums enriched.",
        )

    def apply_archive_filters(
        self,
        restore_album_key: str = "",
        restore_artist_key: str = "",
        restore_album_yview: float | None = None,
        active_album: ActiveAlbum | None = None,
        open_items: set[str] | None = None,
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
        if open_items:
            for item in self.archive_tree.get_children(""):
                self.archive_tree.item(item, open=item in open_items)
        self.refresh_processing_queue_view()
        self.refresh_maintenance_view()
        active_album = active_album or self.active_archive_album
        active_match = self.find_active_archive_album(active_album)
        if active_match:
            restore_artist_key = str(active_match.get("artist_key") or restore_artist_key)
            restore_album_key = str(active_match.get("archive_path") or restore_album_key)
        if restore_artist_key:
            artist_iid = f"artist:{restore_artist_key}"
            if self.archive_tree.exists(artist_iid):
                self.archive_tree.selection_set(artist_iid)
                self.archive_tree.see(artist_iid)
                self._load_archive_artist_albums(restore_artist_key, restore_album_key, restore_album_yview, active_album)
                return
        self.preserve_archive_workspace()

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
        for item in self.archive_album_tree.get_children():
            self.archive_album_tree.delete(item)
        self.preserve_archive_workspace()

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
        active_album: ActiveAlbum | None = None,
    ):
        self.archive_album_rows = albums_for_archive_artist(self.filtered_archive_albums, artist_key)
        for existing in self.archive_album_tree.get_children():
            self.archive_album_tree.delete(existing)
        restored_index = None
        active_album = active_album or self.active_archive_album
        if active_album and active_album.present:
            restored_index = active_album_index(self.archive_album_rows, active_album)
        if restore_album_key:
            state = capture_archive_selection({"artist_key": artist_key, "archive_path": restore_album_key})
            restored_index = restored_index if restored_index is not None else selected_album_index(self.archive_album_rows, state)
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
            self.archive_album_tree.focus(restored_iid)
            self.archive_album_tree.see(restored_iid)
            if restore_album_yview is not None:
                self.archive_album_tree.yview_moveto(restore_album_yview)
            self.archive_selected_album = self.archive_album_rows[int(restored_iid)]
            self.active_archive_album = active_album_from_row(self.archive_selected_album)
            self.set_archive_detail(self.archive_selected_album)
            return
        self.preserve_archive_workspace()

    def on_archive_album_selected(self, event=None):
        selection = self.archive_album_tree.selection()
        if not selection:
            return
        index = self.archive_album_tree.index(selection[0])
        if index >= len(self.archive_album_rows):
            return
        self.archive_selected_album = self.archive_album_rows[index]
        self.active_archive_album = active_album_from_row(self.archive_selected_album)
        self.set_archive_detail(self.archive_selected_album)

    def set_archive_detail(self, details: dict):
        details = self.resolve_archive_workspace_album(details)
        canonical, workspace = self.update_album_workspace("archive", details)
        if not canonical:
            return
        self.archive_selected_album = canonical
        self.active_archive_album = active_album_from_row(canonical)
        self._update_archive_header(canonical, workspace)
        self._update_archive_operation_enablement(canonical, workspace)

    def update_album_workspace(self, target: str, details: dict) -> tuple[dict, dict]:
        if not details:
            self._set_album_workspace_empty_state(target)
            return {}, {}
        canonical_album = self.resolve_canonical_album(details)
        canonical = canonical_album.details
        if not canonical:
            self._set_album_workspace_empty_state(target)
            return {}, {}
        metadata = load_json(DATA_DIR / "metadata_cache.json")
        workspace = album_workspace(canonical, metadata, self._workspace_collection_albums())
        presentation = workspace.get("presentation", {})
        sections = presentation.get("sections", {})
        presentation_labels = getattr(self, f"{target}_presentation_labels", {})
        for (section_id, field), label in presentation_labels.items():
            value = ""
            for item_field, item_value in sections.get(section_id, []):
                if item_field == field:
                    value = item_value
                    break
            label.config(text=str(value or ""))
        title = str(canonical.get("title") or "")
        cover_title = getattr(self, f"{target}_cover_title", None)
        if cover_title is not None:
            cover_title.config(text=title)
        full_path = str(canonical.get("archive_path") or "")
        path_label = getattr(self, f"{target}_path_label", None)
        path_tooltip = getattr(self, f"{target}_path_tooltip", None)
        if path_label is not None:
            path_label.config(text=self._shorten_path(full_path))
        if path_tooltip is not None:
            path_tooltip.set_text(full_path)
        status_labels = getattr(self, f"{target}_status_glance_labels", {})
        for field, value in workspace.get("status_glance", []):
            if field in status_labels:
                status_labels[field].config(text=str(value or "Unknown"))
        self._set_workspace_thumbnail(target, workspace.get("cover", {}))
        integrity_text = self._format_integrity(workspace.get("integrity", {}))
        integrity_widget = getattr(self, f"{target}_integrity_text", None)
        if integrity_widget is not None:
            self._set_text_widget(integrity_widget, integrity_text)
        tab_integrity_widget = getattr(self, f"{target}_integrity_tab_text", None)
        if tab_integrity_widget is not None:
            self._set_text_widget(tab_integrity_widget, integrity_text)
        relationships_widget = getattr(self, f"{target}_relationships_text", None)
        if relationships_widget is not None:
            self._set_text_widget(relationships_widget, workspace.get("relationships_text", ""))
        files = workspace.get("files", {})
        files_text = self._format_archive_files(files, selected=bool(details), archive_path=full_path)
        files_widget = getattr(self, f"{target}_files_text", None)
        if files_widget is not None:
            self._set_text_widget(files_widget, files_text)
        nfo = workspace.get("nfo", {})
        setattr(self, f"{target}_current_nfo", nfo)
        if target == "archive":
            self.archive_current_tracklist = workspace.get("tracklist", {})
        view_nfo_button = getattr(self, f"{target}_view_nfo_button", None)
        if view_nfo_button is not None:
            view_nfo_button.config(state="normal" if nfo.get("path") else "disabled")
        view_nfo_tooltip = getattr(self, f"{target}_view_nfo_tooltip", None)
        if view_nfo_tooltip is not None:
            view_nfo_tooltip.set_text("" if nfo.get("path") else self._archive_evidence_reason("nfo", selected=True, archive_path=full_path))
        nfo_widget = getattr(self, f"{target}_nfo_text", None)
        if nfo_widget is not None:
            self._set_text_widget(nfo_widget, self._format_archive_nfo(nfo, selected=True, archive_path=full_path))
        return canonical, workspace

    def resolve_canonical_album(self, details: dict):
        return self.canonical_album_resolver().resolve(AlbumRef.from_row(details))

    def canonical_album_resolver(self) -> CanonicalAlbumResolver:
        archive_root = self.audio_settings.get("archive_paths", {}).get("main_archive_root", "")
        return CanonicalAlbumResolver(
            archive_registry=load_json(DATA_DIR / "archive_registry.json"),
            identity_registry=load_json(DATA_DIR / "identity_registry.json"),
            lifecycle_registry=load_json(DATA_DIR / "lifecycle_registry.json"),
            metadata_cache=load_json(DATA_DIR / "metadata_cache.json"),
            archive_root=Path(archive_root) if archive_root else None,
        )

    def _workspace_collection_albums(self) -> list[dict]:
        rows: list[dict] = []
        seen: set[tuple[str, str]] = set()
        for album in list(getattr(self, "archive_albums", [])) + list(getattr(self, "library_data", {}).get("albums", [])):
            key = (str(album.get("album_id") or ""), str(album.get("archive_path") or ""))
            if key in seen:
                continue
            seen.add(key)
            rows.append(album)
        return rows

    def _set_workspace_thumbnail(self, target: str, thumbnail: dict):
        label = getattr(self, f"{target}_thumbnail", None)
        status_label = getattr(self, f"{target}_artwork_status", None)
        if label is None:
            return
        image = self._set_album_cover(label, status_label, thumbnail)
        setattr(self, f"{target}_thumbnail_image", image)

    def _set_archive_empty_state(self):
        self._set_album_workspace_empty_state("archive")

    def _set_album_workspace_empty_state(self, target: str):
        if hasattr(self, "archive_header_artist_var"):
            if target == "archive":
                self.archive_header_artist_var.set("Select an album")
                self.archive_header_album_var.set("Select a release to view evidence.")
                self.archive_header_year_var.set("")
                for field, label in self.archive_header_badges.items():
                    label.config(text=f"{field}: No selection")
        for (section_id, field), label in getattr(self, f"{target}_presentation_labels", {}).items():
            label.config(text="")
        cover_title = getattr(self, f"{target}_cover_title", None)
        if cover_title is not None:
            cover_title.config(text="Select an album to inspect.")
        thumbnail = getattr(self, f"{target}_thumbnail", None)
        if thumbnail is not None:
            thumbnail.config(image="", text="No album selected")
        artwork_status = getattr(self, f"{target}_artwork_status", None)
        if artwork_status is not None:
            artwork_status.config(text="No artwork because no album is selected.")
        for label in getattr(self, f"{target}_status_glance_labels", {}).values():
            label.config(text="No selection")
        empty_text = "Select an album to inspect."
        for attr in (f"{target}_integrity_text", f"{target}_integrity_tab_text"):
            widget = getattr(self, attr, None)
            if widget is not None:
                self._set_text_widget(widget, empty_text)
        relationships = getattr(self, f"{target}_relationships_text", None)
        if relationships is not None:
            self._set_text_widget(relationships, "Select a release to view related albums.")
        files = getattr(self, f"{target}_files_text", None)
        if files is not None:
            self._set_text_widget(files, "Select a release to view filesystem evidence.")
        nfo = getattr(self, f"{target}_nfo_text", None)
        if nfo is not None:
            self._set_text_widget(nfo, "Select a release to view NFO evidence.")
        setattr(self, f"{target}_current_nfo", {})
        if target == "archive":
            self.archive_current_tracklist = {}
        view_nfo_button = getattr(self, f"{target}_view_nfo_button", None)
        if view_nfo_button is not None:
            view_nfo_button.config(state="disabled")
        view_nfo_tooltip = getattr(self, f"{target}_view_nfo_tooltip", None)
        if view_nfo_tooltip is not None:
            view_nfo_tooltip.set_text("Select an album before viewing NFO.")
        if target == "archive":
            self._update_archive_operation_enablement({}, {})

    def _update_archive_header(self, details: dict, workspace: dict):
        artist = str(details.get("artist") or "Unknown artist")
        album = str(details.get("title") or details.get("album") or "Unknown album")
        year = str(details.get("year") or "")
        self.archive_header_artist_var.set(artist)
        self.archive_header_album_var.set(album)
        self.archive_header_year_var.set(year)
        lifecycle = str(details.get("lifecycle_state") or details.get("archive_status") or "UNKNOWN").upper()
        readiness = str((details.get("archive_readiness") or {}).get("state") or "UNKNOWN").replace("_", " ")
        binding = "Filesystem Bound" if details.get("archive_path") else "No Filesystem Binding"
        self.archive_header_badges["Lifecycle"].config(text=lifecycle)
        self.archive_header_badges["Readiness"].config(text=readiness)
        self.archive_header_badges["Binding"].config(text=binding)

    def _format_archive_files(self, files: dict, *, selected: bool, archive_path: str) -> str:
        if not selected:
            return "Select a release to view filesystem evidence."
        if not archive_path:
            return "Unavailable: this album has no archive folder binding."
        items = files.get("items", [])
        if not items:
            return f"Missing: no files were found in the archive folder.\nPath: {files.get('path') or archive_path}"
        return f"Source: {files.get('source', 'filesystem')}\nPath: {files.get('path', '')}\n\n" + "\n".join(items)

    def _format_archive_nfo(self, nfo: dict, *, selected: bool, archive_path: str) -> str:
        if not selected:
            return "Select a release to view NFO evidence."
        if not archive_path:
            return "Unavailable: this album has no archive folder binding."
        if not nfo.get("path"):
            return "Missing: no NFO was found for this album."
        return f"Status: {nfo.get('status', 'Present')}\nPath: {nfo.get('path', '')}"

    def _archive_evidence_reason(self, evidence: str, *, selected: bool, archive_path: str) -> str:
        if not selected:
            return "Select an album first."
        if not archive_path:
            return "No archive folder is bound to this album."
        labels = {"nfo": "NFO", "playlist": "playlist"}
        return f"No {labels.get(evidence, evidence)} evidence is available for this album."

    def _tool_configured(self, operation_id: str) -> bool:
        tools = self.audio_settings.get("tools", {}) if isinstance(self.audio_settings.get("tools"), dict) else {}
        keys = {
            "generate_nfo": "nfo_generator_path",
            "generate_sfv": "sfv_generator_path",
            "revalidate_album": "flac_validator_path",
            "process_album": "audio_division_path",
        }
        key = keys.get(operation_id)
        return bool(not key or str(tools.get(key) or "").strip())

    def _operation_enablement(self, operation_id: str, details: dict, workspace: dict) -> tuple[bool, str]:
        if not details:
            return False, "Select an album first."
        target, reason = album_archive_operation_target(details)
        if operation_id == "queue":
            return True, ""
        if operation_id in {"revalidate_album", "generate_nfo", "generate_sfv", "process_album"} and not self._tool_configured(operation_id):
            return False, "Required tool path is not configured."
        if operation_id == "play_playlist":
            tracklist = workspace.get("tracklist", {})
            if tracklist.get("source") != "playlist" or not tracklist.get("path"):
                return False, self._archive_evidence_reason("playlist", selected=True, archive_path=str(details.get("archive_path") or ""))
        if not target:
            return False, reason
        return True, ""

    def _update_archive_operation_enablement(self, details: dict, workspace: dict):
        for operation_id, button in getattr(self, "archive_operation_buttons", {}).items():
            enabled, reason = self._operation_enablement(operation_id, details, workspace)
            button.config(state="normal" if enabled else "disabled")
            tooltip = self.archive_operation_tooltips.get(operation_id)
            if tooltip:
                tooltip.set_text("" if enabled else reason)

    def _set_archive_thumbnail(self, thumbnail: dict):
        self.archive_thumbnail_image = self._set_album_cover(
            self.archive_thumbnail,
            self.archive_artwork_status,
            thumbnail,
        )

    def show_archive_album_menu(self, event):
        row = self._select_tree_row_at_event(self.archive_album_tree, self.archive_album_rows, event)
        if row:
            self._show_context_menu(event, row, source="archive")

    def show_incoming_album_menu(self, event):
        row = self._select_tree_row_at_event(self.processing_queue_tree, self.closed_loop_rows, event)
        if row:
            self._show_context_menu(event, row, source="incoming")

    def show_maintenance_album_menu(self, event):
        row = self._select_tree_row_at_event(self.maintenance_album_tree, self.maintenance_album_rows, event)
        if row:
            self._show_context_menu(event, row, source="archive")

    def show_library_album_menu(self, event):
        row = self._select_tree_row_at_event(self.library_album_tree, self.library_album_rows, event)
        if row:
            details = album_details(self.library_data, row.get("album_id", "")) or row
            self.library_selected_album = details
            self.set_library_detail(details)
            self._show_context_menu(event, details, source="library")

    def _select_tree_row_at_event(self, tree, rows: list[dict], event) -> dict:
        item = tree.identify_row(event.y)
        if not item:
            return {}
        tree.selection_set(item)
        try:
            index = int(item)
        except ValueError:
            index = tree.index(item)
        return rows[index] if 0 <= index < len(rows) else {}

    def _show_context_menu(self, event, row: dict, *, source: str):
        menu = tk.Menu(self, tearoff=False)
        actions = context_actions(row)
        self._add_context_action(menu, "Jump to Archive", actions["jump_to_archive"], lambda: self.jump_context_to_archive(row))
        self._add_context_action(menu, "Jump to Curator", actions["jump_to_curator"], lambda: self.jump_context_to_curator(row))
        menu.add_separator()
        self._add_context_action(menu, "Open Folder", actions["open_folder"], lambda: self.open_context_folder(row))
        self._add_context_action(menu, "Open Parent Folder", actions["open_parent_folder"], lambda: self.open_context_parent_folder(row))
        self._add_context_action(menu, "Reveal Incoming Folder", actions["reveal_incoming_folder"], lambda: self.open_context_folder(row))
        menu.add_separator()
        self._add_context_action(menu, "Copy Album ID", actions["copy_album_id"], lambda: self.copy_context_album_id(row))
        self._add_context_action(menu, "Copy Deezer Link", actions["copy_deezer_link"], lambda: self.copy_context_deezer_link(row))
        self._add_context_action(menu, "Show Identity", actions["show_identity"], lambda: self.show_context_identity(row))
        menu.add_separator()
        self._add_context_action(menu, "Revalidate", actions["revalidate"], lambda: self.revalidate_context_album(row, source=source))
        self._add_context_action(menu, "Process Album", actions["process_album"], lambda: self.process_context_album(row, source=source))
        menu.tk_popup(event.x_root, event.y_root)

    def _add_context_action(self, menu, label: str, enabled: bool, command):
        menu.add_command(label=label, command=command, state=tk.NORMAL if enabled else tk.DISABLED)

    def jump_context_to_archive(self, row: dict):
        if not row:
            return
        self.open_release_archive_workspace(self._context_release_proxy(row))

    def jump_context_to_curator(self, row: dict):
        album_id = context_album_id(row) or album_id_from_url(context_deezer_link(row))
        if not album_id:
            return
        if self._select_curator_release_by_album_id(album_id):
            self.status.config(text="Opened release in Curator.")
            return
        self.status.config(text="Release is not currently visible in Curator.")

    def _select_curator_release_by_album_id(self, album_id: str) -> bool:
        self.tabs.select(0)
        for index, release in enumerate(self.acquisition_rows):
            if str(getattr(release, "deezer_album_id", "") or getattr(release, "album_id", "") or "") == album_id:
                self.acquisition_tree.selection_set(str(index))
                self.acquisition_tree.focus(str(index))
                self.acquisition_tree.see(str(index))
                self.selected_acquisition_release = release
                return True
        for list_index, filename in enumerate(self.artist_list.get(0, tk.END)):
            try:
                model = load_artist_file(ARTISTS_DIR / filename, DATA_DIR)
            except OSError:
                continue
            for release in model.releases:
                if str(getattr(release, "deezer_album_id", "") or "") != album_id:
                    continue
                self.artist_list.selection_clear(0, tk.END)
                self.artist_list.selection_set(list_index)
                self.artist_list.see(list_index)
                self.current_artist_filename = filename
                self.current_artist_model = model
                self.artist_release_lines = release_line_map(model)
                self.show_artist_mode()
                self.render_acquisition_grid()
                row_index = next(
                    (
                        idx
                        for idx, candidate in enumerate(self.acquisition_rows)
                        if str(getattr(candidate, "deezer_album_id", "") or "") == album_id
                    ),
                    None,
                )
                if row_index is not None:
                    self.acquisition_tree.selection_set(str(row_index))
                    self.acquisition_tree.focus(str(row_index))
                    self.acquisition_tree.see(str(row_index))
                    self.selected_acquisition_release = self.acquisition_rows[row_index]
                    return True
        return False

    def open_context_folder(self, row: dict):
        folder = context_folder(row)
        if folder:
            result = run_operation("open_album_folder", folder, self.audio_settings, OPERATION_HISTORY_FILE)
            self.set_archive_operation_result(f"Open Folder: {result['result'].title()} - {result['message']}")

    def open_context_parent_folder(self, row: dict):
        folder = context_parent_folder(row)
        if folder:
            result = run_operation("open_album_folder", folder, self.audio_settings, OPERATION_HISTORY_FILE)
            self.set_archive_operation_result(f"Open Parent Folder: {result['result'].title()} - {result['message']}")

    def copy_context_album_id(self, row: dict):
        album_id = context_album_id(row)
        if album_id:
            self.clipboard_clear()
            self.clipboard_append(album_id)
            self.status.config(text="Album ID copied.")

    def copy_context_deezer_link(self, row: dict):
        link = context_deezer_link(row)
        if link:
            self.clipboard_clear()
            self.clipboard_append(link)
            self.status.config(text="Deezer link copied.")

    def show_context_identity(self, row: dict):
        self.show_release_identity(self._context_release_proxy(row))

    def revalidate_context_album(self, row: dict, *, source: str):
        if source == "library":
            previous = self.library_selected_album
            self.library_selected_album = row
            self.run_library_album_operation("revalidate_album")
            self.library_selected_album = previous
            return
        self.archive_selected_album = self.resolve_archive_workspace_album(row)
        self.run_archive_album_operation("revalidate_album")

    def process_context_album(self, row: dict, *, source: str):
        if source == "incoming":
            self.processing_queue = queue_for_processing(
                self.processing_queue,
                queue_album_payload(row),
                source=row.get("source", "incoming"),
            )
            save_processing_queue(PROCESSING_QUEUE_FILE, self.processing_queue)
            self.refresh_processing_queue_view()
            self.set_archive_operation_result("Incoming album queued for processing.")
            return
        target, reason = album_archive_operation_target(row)
        if not target:
            self.set_archive_operation_result(f"Failure: {reason}")
            return
        self.archive_selected_album = self.resolve_archive_workspace_album(row)
        selection = self.capture_active_archive_context(active_tab=self.tabs.select())
        self.processing_queue = queue_for_processing(self.processing_queue, row, source=source)
        save_processing_queue(PROCESSING_QUEUE_FILE, self.processing_queue)
        result = run_audio_division_process_album(target, self.audio_settings, OPERATION_HISTORY_FILE)
        self.set_archive_operation_result(f"{result['result'].title()}: {result['message']}")
        self.restore_active_archive_context(selection)
        self.refresh_library()
        self.refresh_audio_dashboard()

    def set_archive_operation_result(self, message: str):
        if hasattr(self, "archive_operation_result_var"):
            self.archive_operation_result_var.set(message)
        if hasattr(self, "library_operation_result_var"):
            self.library_operation_result_var.set(message)
        self.status.config(text=message)

    def _finish_archive_operation(self, label: str, success: bool, message: str):
        state = "Completed" if success else "Failed"
        text = f"{label}: {state} - {message}"
        self.set_archive_operation_result(text)
        if hasattr(self, "archive_operation_last_run_var"):
            timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            self.archive_operation_last_run_var.set(f"Last run: {timestamp}")

    def _archive_operation_label(self, operation_id: str) -> str:
        return {
            "revalidate_album": "Revalidate",
            "generate_nfo": "Generate NFO",
            "generate_sfv": "Generate SFV",
            "open_album_folder": "Open Folder",
            "play_album": "Play Album",
            "play_playlist": "Playlist",
            "process_album": "Process Album",
        }.get(operation_id, operation_id)

    def _context_release_proxy(self, row: dict):
        album_id = context_album_id(row)
        return SimpleNamespace(
            title=row.get("title") or row.get("album") or "",
            artist=row.get("artist") or "",
            deezer_album_id=album_id,
            album_id=album_id,
            url=context_deezer_link(row),
            archive_path=row.get("archive_path") or row.get("folder") or "",
            archive_status=row.get("archive_status") or "",
            lifecycle_state=row.get("lifecycle_state") or row.get("state") or row.get("current_state") or "",
            validation_status=row.get("validation_status") or "",
            metadata_status=row.get("metadata_status") or "",
            identity_confidence=row.get("identity_confidence") or "",
            acquisition_recommendation=row.get("acquisition_recommendation") or row.get("pipeline_recommendation") or {},
        )

    def run_archive_album_operation(self, operation_id: str):
        label = self._archive_operation_label(operation_id)
        target, reason = album_archive_operation_target(self.archive_selected_album)
        if not target:
            self._finish_archive_operation(label, False, reason)
            return
        selection = self.capture_active_archive_context(active_tab=self.tabs.select())
        self.set_archive_operation_result(f"{label}: Running...")
        self.update_idletasks()
        result = run_operation(operation_id, target, self.audio_settings, OPERATION_HISTORY_FILE)
        self.restore_active_archive_context(selection)
        if selection.active_tab:
            self.tabs.select(selection.active_tab)
        self._finish_archive_operation(label, result.get("result") == "success", result.get("message", ""))
        self.refresh_audio_dashboard()

    def run_archive_album_playback(self, operation_id: str):
        label = self._archive_operation_label(operation_id)
        target, reason = album_archive_operation_target(self.archive_selected_album)
        if not target:
            self._finish_archive_operation(label, False, reason)
            return
        selection = self.capture_active_archive_context(active_tab=self.tabs.select())
        self.set_archive_operation_result(f"{label}: Running...")
        self.update_idletasks()
        result = run_playback_action(operation_id, target, self.audio_settings, OPERATION_HISTORY_FILE)
        self.restore_active_archive_context(selection)
        if selection.active_tab:
            self.tabs.select(selection.active_tab)
        self._finish_archive_operation(label, result.get("result") == "success", result.get("message", ""))
        self.refresh_audio_dashboard()

    def queue_selected_archive_album_for_processing(self):
        if not self.archive_selected_album:
            self._finish_archive_operation("Queue", False, "select an album first")
            return
        selection = self.capture_active_archive_context(active_tab=self.tabs.select())
        self.set_archive_operation_result("Queue: Running...")
        self.processing_queue = queue_for_processing(self.processing_queue, self.archive_selected_album, source="archive")
        save_processing_queue(PROCESSING_QUEUE_FILE, self.processing_queue)
        self.refresh_processing_queue_view()
        self.restore_active_archive_context(selection)
        if selection.active_tab:
            self.tabs.select(selection.active_tab)
        self._finish_archive_operation("Queue", True, "Queued for processing.")

    def process_selected_archive_album(self):
        target, reason = album_archive_operation_target(self.archive_selected_album)
        if not target:
            self._finish_archive_operation("Process Album", False, reason)
            return
        selection = self.capture_active_archive_context(active_tab=self.tabs.select())
        self.set_archive_operation_result("Process Album: Running...")
        self.update_idletasks()
        self.processing_queue = queue_for_processing(self.processing_queue, self.archive_selected_album, source="archive")
        save_processing_queue(PROCESSING_QUEUE_FILE, self.processing_queue)
        result = run_audio_division_process_album(target, self.audio_settings, OPERATION_HISTORY_FILE)
        self.restore_active_archive_context(selection)
        if selection.active_tab:
            self.tabs.select(selection.active_tab)
        self._finish_archive_operation("Process Album", result.get("result") == "success", result.get("message", ""))
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
        album = self.resolve_archive_workspace_album(album)
        artist_iid = f"artist:{album.get('artist_key', '')}"
        if self.archive_tree.exists(artist_iid):
            self.archive_tree.selection_set(artist_iid)
            self.archive_tree.see(artist_iid)
            self._load_archive_artist_albums(album.get("artist_key", ""), self._archive_album_key(album), None, active_album_from_row(album))
        self.archive_selected_album = album
        self.active_archive_album = active_album_from_row(album)
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
        self.archive_selected_album = self.resolve_archive_workspace_album(album)
        self.active_archive_album = active_album_from_row(self.archive_selected_album)
        selection = self.capture_active_archive_context(active_tab=self.tabs.select())
        result = run_operation(resolved_operation, target, self.audio_settings, OPERATION_HISTORY_FILE)
        self.archive_operation_result_var.set(
            f"{resolved_operation}: {result['result'].title()} - {result['message']}"
        )
        self.restore_active_archive_context(selection)
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
        self.set_library_detail({})

    def on_library_artist_selected(self, event=None):
        selection = self.library_artist_list.curselection()
        if not selection:
            return
        artist = self.library_artist_rows[selection[0]]
        self.library_album_rows = albums_for_artist(self.library_data, artist["artist_key"])
        for item in self.library_album_tree.get_children():
            self.library_album_tree.delete(item)
        for idx, album in enumerate(self.library_album_rows):
            self.library_album_tree.insert(
                "",
                tk.END,
                iid=str(idx),
                values=(
                    album.get("title", ""),
                    album.get("year") or "",
                    album.get("record_type") or "",
                    album.get("validation_status") or "",
                ),
            )
        self.set_library_detail({})

    def on_library_album_selected(self, event=None):
        selection = self.library_album_tree.selection()
        if not selection:
            return
        album = self.library_album_rows[int(selection[0])]
        self.library_selected_album = album_details(self.library_data, album["album_id"])
        self.set_library_detail(self.library_selected_album)

    def set_library_detail(self, details: dict):
        canonical, _workspace = self.update_album_workspace("library", details)
        self.library_selected_album = canonical

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

    def _build_settings_tab(self, parent):
        groups = [
            ("Roots", [
                ("archive_paths", "main_archive_root", "Main Archive Root"),
                ("archive_paths", "incoming_root", "Incoming Root"),
                ("archive_paths", "problematic_root", "Problematic Root"),
                ("archive_paths", "needs_validation_root", "Needs Validation Root"),
                ("validator", "validated_index_path", "Validated Index Path"),
                ("validator", "validation_log_root", "Validation Log Root"),
                ("metadata", "metadata_cache_path", "Metadata Cache Path"),
                ("reports", "reports_directory", "Reports Directory"),
            ]),
            ("Tools", [
                ("tools", "audio_division_path", "Audio Division Path"),
                ("tools", "nfo_generator_path", "NFO Generator Path"),
                ("tools", "sfv_generator_path", "SFV Generator Path"),
                ("tools", "flac_validator_path", "FLAC Validator Path"),
                ("tools", "file_manager_path", "File Manager Path"),
            ]),
            ("Providers", [
                ("playback", "provider", "Player Provider"),
                ("playback", "player_path", "Player Path"),
                ("playback", "player_args", "Player Arguments"),
            ]),
        ]
        sections = ttk.Notebook(parent)
        sections.pack(fill="both", expand=True)
        for title, fields in groups:
            form = ttk.Frame(sections, padding=10)
            sections.add(form, text=title)
            for row, (section, key, label) in enumerate(fields):
                ttk.Label(form, text=label).grid(row=row, column=0, sticky="w", padx=(0, 10), pady=4)
                var = tk.StringVar(value=self.audio_settings.get(section, {}).get(key, ""))
                entry = ttk.Entry(form, textvariable=var)
                entry.grid(row=row, column=1, sticky="ew", pady=4)
                self.audio_setting_vars[(section, key)] = var
            form.columnconfigure(1, weight=1)

        buttons = ttk.Frame(parent)
        buttons.pack(fill="x", pady=(10, 0))
        ttk.Button(buttons, text="Save Settings", command=self.save_audio_settings).pack(side="left")
        ttk.Button(buttons, text="Reload Settings", command=self.reload_audio_settings).pack(side="left", padx=(6, 0))

    def refresh_audio_dashboard(self):
        if not hasattr(self, "dashboard_value_labels"):
            return
        summary = dashboard_summary(DATA_DIR)
        for key, label in self.dashboard_value_labels.items():
            section, field = key.split(".", 1)
            value = summary.get(section, {}).get(field, 0)
            if isinstance(value, float):
                text = f"{value:.1%}"
            else:
                text = str(value)
            label.config(text=text)
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
        selection = self.capture_active_archive_context(active_tab=self.tabs.select())
        self._set_archive_audit_running(True, "Archive audit running...")
        thread = threading.Thread(
            target=self._run_archive_audit_thread,
            args=(registry, archive_root, reports_dir, selection),
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
        if hasattr(self, "archive_operation_result_var"):
            self.archive_operation_result_var.set(message)
        self.status.config(text=message)

    def _run_archive_audit_thread(self, registry: dict, archive_root: Path, reports_dir: Path, selection):
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
        self.after(0, lambda message=message: self._finish_archive_wide_operation("Run Audit", message, selection, self._set_archive_audit_running))

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
        selection = self.capture_active_archive_context(active_tab=self.tabs.select())
        self._set_archive_revalidation_running(True, "Archive revalidation running...")
        thread = threading.Thread(
            target=self._run_archive_revalidation_thread,
            args=(registry, archive_root, reports_dir, selection),
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
        if hasattr(self, "archive_operation_result_var"):
            self.archive_operation_result_var.set(message)
        self.status.config(text=message)

    def _run_archive_revalidation_thread(self, registry: dict, archive_root: Path, reports_dir: Path, selection):
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
        self.after(0, lambda message=message: self._finish_archive_wide_operation("Revalidate Archive", message, selection, self._set_archive_revalidation_running))

    def _finish_archive_wide_operation(self, label: str, message: str, selection, running_setter):
        success = " failed:" not in message.lower()
        running_setter(False, message)
        self.restore_active_archive_context(selection)
        if selection.active_tab:
            self.tabs.select(selection.active_tab)
        self._finish_archive_operation(label, success, message)

    def save_audio_settings(self):
        for (section, key), var in self.audio_setting_vars.items():
            self.audio_settings.setdefault(section, {})[key] = var.get()
        save_audio_division_settings(AUDIO_DIVISION_SETTINGS_FILE, self.audio_settings)
        self.status.config(text="Hub settings saved")

    def reload_audio_settings(self):
        self.audio_settings = load_audio_division_settings(AUDIO_DIVISION_SETTINGS_FILE)
        for (section, key), var in self.audio_setting_vars.items():
            var.set(self.audio_settings.get(section, {}).get(key, ""))
        self.status.config(text="Hub settings reloaded")

    # ---------------- Modes ----------------

    def show_artist_mode(self):
        self.main_mode = "artist"
        self.main_label.config(text="Acquisition")
        self.inbox_editable = False
        self.main_editor.pack_forget()
        self.acquisition_tree.pack(fill="both", expand=True)

    def show_inbox_mode(self):
        self.main_mode = "inbox"
        self.main_label.config(text="Inbox")
        self.inbox_editable = False
        self.current_artist_model = None
        self.artist_release_lines = {}
        self.selected_acquisition_release = None
        self.acquisition_tree.pack_forget()
        self.main_editor.pack(fill="both", expand=True)
        self.load_inbox()

    # ---------------- Inbox ----------------

    def load_inbox(self):
        self.main_editor.delete("1.0", tk.END)
        if INBOX_FILE.exists():
            self.main_editor.insert(tk.END, INBOX_FILE.read_text())

    def save_inbox(self):
        if self.main_mode != "inbox":
            return
        DATA_DIR.mkdir(exist_ok=True)
        INBOX_FILE.write_text(self.main_editor.get("1.0", tk.END))
        self.status.config(text="Inbox saved")

    # ---------------- Artist ----------------

    def refresh_artists(self):
        ARTISTS_DIR.mkdir(exist_ok=True)
        self.artist_list.delete(0, tk.END)
        for p in sorted(ARTISTS_DIR.glob("*.txt")):
            self.artist_list.insert(tk.END, p.name)

    def open_selected_artist(self, event=None):
        sel = self.artist_list.curselection()
        if not sel:
            return
        self.current_artist_filename = self.artist_list.get(sel[0])
        path = ARTISTS_DIR / self.current_artist_filename
        self.current_artist_model = load_artist_file(path, DATA_DIR)
        self.artist_release_lines = release_line_map(self.current_artist_model)
        self.show_artist_mode()
        self.render_acquisition_grid()

    def render(self, text: str):
        self.main_editor.delete("1.0", tk.END)
        self.main_editor.insert(tk.END, text)

    def render_acquisition_grid(self):
        for item in self.acquisition_tree.get_children():
            self.acquisition_tree.delete(item)
        self.acquisition_rows = list(self.current_artist_model.releases) if self.current_artist_model else []
        self.selected_acquisition_release = None
        for index, release in enumerate(self.acquisition_rows):
            recommendation = release.acquisition_recommendation.get(
                "recommendation",
                release.acquisition_status,
            )
            self.acquisition_tree.insert(
                "",
                tk.END,
                iid=str(index),
                values=(
                    recommendation,
                    release.title,
                    release.year,
                    release.type,
                    release.archive_status,
                    release.lifecycle_state,
                    release.validation_status,
                    release.metadata_status,
                ),
            )

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
            return
        index = int(selection[0])
        if index >= len(self.acquisition_rows):
            self.selected_acquisition_release = None
            return
        self.selected_acquisition_release = self.acquisition_rows[index]

    def on_acquisition_double_click(self, event=None):
        release = self.release_from_acquisition_event(event) or self.selected_acquisition_release
        if not release:
            return
        if release.archive_path:
            self.open_release_archive_workspace(release)
        else:
            self.selected_acquisition_release = release
            self.status.config(text=f"Selected for acquisition: {release.title}")

    def release_from_acquisition_event(self, event):
        if not event:
            return None
        iid = self.acquisition_tree.identify_row(event.y)
        if not iid:
            return None
        self.acquisition_tree.selection_set(iid)
        index = int(iid)
        if index >= len(self.acquisition_rows):
            return None
        return self.acquisition_rows[index]

    def show_acquisition_menu(self, event):
        release = self.release_from_acquisition_event(event)
        if not release:
            return
        self.selected_acquisition_release = release
        row = self._release_context_row(release)
        actions = context_actions(row)
        menu = tk.Menu(self, tearoff=False)
        menu.add_command(label="Acquire Album", command=lambda: self.select_release_for_acquisition(release))
        menu.add_command(label="Add To Acquisition", command=lambda: self.queue_release_for_acquisition(release))
        menu.add_separator()
        self._add_context_action(menu, "Jump to Archive", actions["jump_to_archive"], lambda: self.jump_context_to_archive(row))
        self._add_context_action(menu, "Jump to Curator", actions["jump_to_curator"], lambda: self.jump_context_to_curator(row))
        menu.add_separator()
        self._add_context_action(menu, "Open Folder", actions["open_folder"], lambda: self.open_context_folder(row))
        self._add_context_action(menu, "Open Parent Folder", actions["open_parent_folder"], lambda: self.open_context_parent_folder(row))
        self._add_context_action(menu, "Reveal Incoming Folder", actions["reveal_incoming_folder"], lambda: self.open_context_folder(row))
        menu.add_separator()
        menu.add_command(label="Open Deezer", command=lambda: webbrowser.open(release.url), state=tk.NORMAL if release.url else tk.DISABLED)
        self._add_context_action(menu, "Copy Album ID", actions["copy_album_id"], lambda: self.copy_context_album_id(row))
        self._add_context_action(menu, "Copy Deezer Link", actions["copy_deezer_link"], lambda: self.copy_context_deezer_link(row))
        self._add_context_action(menu, "Show Identity", actions["show_identity"], lambda: self.show_release_identity(release))
        menu.add_separator()
        self._add_context_action(menu, "Revalidate", actions["revalidate"], lambda: self.revalidate_context_album(row, source="archive"))
        self._add_context_action(menu, "Process Album", actions["process_album"], lambda: self.process_context_album(row, source="archive"))
        menu.add_separator()
        menu.add_command(label="Refresh Metadata", command=self.refresh_acquisition_metadata)
        menu.tk_popup(event.x_root, event.y_root)

    def _release_context_row(self, release) -> dict:
        return {
            "artist": self.current_artist_model.artist_name if self.current_artist_model else "",
            "title": getattr(release, "title", ""),
            "album": getattr(release, "title", ""),
            "deezer_album_id": getattr(release, "deezer_album_id", ""),
            "album_id": getattr(release, "deezer_album_id", ""),
            "url": getattr(release, "url", ""),
            "archive_path": getattr(release, "archive_path", ""),
            "identity_confidence": getattr(release, "identity_confidence", ""),
            "validation_status": getattr(release, "validation_status", ""),
            "metadata_status": getattr(release, "metadata_status", ""),
            "lifecycle_state": getattr(release, "lifecycle_state", ""),
            "acquisition_recommendation": getattr(release, "acquisition_recommendation", {}),
        }

    def select_release_for_acquisition(self, release):
        self.selected_acquisition_release = release
        self.status.config(text=f"Selected for acquisition: {release.title}")

    def queue_release_for_acquisition(self, release):
        self.custom_editor.insert(tk.END, release.url + "\n")
        record_attempt(self.attempts, release.deezer_album_id, release.url)
        save_attempts(ATTEMPTS_FILE, self.attempts)
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

    def acquire_selected_release(self, event=None):
        return self.fire_selected_lines(event)

    def show_release_identity(self, release):
        recommendation = release.acquisition_recommendation
        messagebox.showinfo(
            "Release Identity",
            "\n".join(
                [
                    f"Album: {release.title}",
                    f"Deezer album ID: {release.deezer_album_id}",
                    f"Artist file: {self.current_artist_filename or ''}",
                    f"Identity confidence: {release.identity_confidence}",
                    f"Archive path: {release.archive_path or 'not archived'}",
                    f"Lifecycle: {release.lifecycle_state}",
                    f"Validation: {release.validation_status}",
                    f"Metadata: {release.metadata_status}",
                    f"Recommendation: {recommendation.get('recommendation', 'UNKNOWN')}",
                    f"Reason: {recommendation.get('reason', '')}",
                    f"Next action: {recommendation.get('next_action', '')}",
                ]
            ),
        )

    def refresh_acquisition_metadata(self):
        self.refresh_archive_metadata()
        if self.current_artist_filename:
            path = ARTISTS_DIR / self.current_artist_filename
            self.current_artist_model = load_artist_file(path, DATA_DIR)
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
        if hasattr(self, "archive_tab"):
            self.tabs.select(self.archive_tab)
        if hasattr(self, "archive_sections") and self.archive_sections.tabs():
            self.archive_sections.select(self.archive_sections.tabs()[0])
        artist_iid = f"artist:{album.get('artist_key', '')}"
        if hasattr(self, "archive_tree") and self.archive_tree.exists(artist_iid):
            self.archive_tree.selection_set(artist_iid)
            self.archive_tree.see(artist_iid)
            self._load_archive_artist_albums(album.get("artist_key", ""), self._archive_album_key(album), None)
        self.archive_selected_album = album
        self.set_archive_detail(album)
        self.status.config(text=f"Opened archive workspace: {release.title}")

    # ---------------- Navigation ----------------

    def move_cursor(self, delta: int):
        index = self.main_editor.index("insert linestart")
        line = max(1, int(index.split(".")[0]) + delta)
        self.main_editor.mark_set("insert", f"{line}.0")
        self.main_editor.see(f"{line}.0")
        return "break"

    def extend_selection(self, delta: int):
        if not self.main_editor.tag_ranges(tk.SEL):
            start = self.main_editor.index("insert linestart")
            self.main_editor.tag_add(tk.SEL, start, start + " lineend")

        new_line = max(1, int(self.main_editor.index("insert").split(".")[0]) + delta)
        self.main_editor.tag_add(tk.SEL, tk.SEL_FIRST, f"{new_line}.end")
        self.main_editor.mark_set("insert", f"{new_line}.0")
        self.main_editor.see("insert")
        return "break"

    def clear_selection(self):
        self.main_editor.tag_remove(tk.SEL, "1.0", tk.END)
        return "break"

    # ---------------- Fire / Pull ----------------

    def fire_selected_lines(self, event=None):
        fired = []
        for release in self.selected_artist_releases():
            self.custom_editor.insert(tk.END, release.url + "\n")
            record_attempt(self.attempts, release.deezer_album_id, release.url)
            fired.append(release.url)

        if fired:
            save_attempts(ATTEMPTS_FILE, self.attempts)
            self.fire_history.append(fired)
            self.fire_history = self.fire_history[-self.MAX_FIRE_HISTORY :]
            self.status.config(text=f"Queued {len(fired)} album(s)")
        return "break"

    def pull_back(self, event=None):
        if not self.fire_history:
            self.status.config(text="Nothing to pull back")
            return "break"

        last = self.fire_history.pop()
        lines = self.custom_editor.get("1.0", tk.END).splitlines()

        for line in reversed(last):
            if line in lines:
                idx = lines.index(line)
                self.custom_editor.delete(f"{idx + 1}.0", f"{idx + 2}.0")
                lines.pop(idx)

        self.status.config(text=f"Pulled back {len(last)} album(s)")
        return "break"

    # ---------------- Confirmation ----------------

    def confirm_selected_albums(self):
        added = 0
        for release in self.selected_artist_releases():
            if confirm_album(
                self.confirmed,
                release.url,
                artist_file=self.current_artist_filename,
            ):
                added += 1

        if added:
            save_confirmed(CONFIRMED_FILE, self.confirmed)
            self.status.config(text=f"Confirmed {added} album(s)")
            self.open_selected_artist()

    def confirm_from_queue(self):
        try:
            text = self.custom_editor.get(tk.SEL_FIRST, tk.SEL_LAST)
        except tk.TclError:
            return

        added = 0
        for line in text.splitlines():
            if line.startswith("http"):
                if confirm_album(
                    self.confirmed,
                    line,
                    artist_file=self.current_artist_filename,
                ):
                    added += 1

        if added:
            save_confirmed(CONFIRMED_FILE, self.confirmed)
            self.status.config(text=f"Confirmed {added} album(s)")
            self.open_selected_artist()

    # ---------------- Ship to Server (NEW) ----------------

    def _set_ship_buttons_enabled(self, enabled: bool) -> None:
        state = "normal" if enabled else "disabled"
        for b in (getattr(self, "btn_ship_selected", None), getattr(self, "btn_ship_queue", None)):
            if b is not None:
                b.config(state=state)

    def _ship_thread(self, links: list[str], force: bool = False) -> None:
        try:
            if not links:
                self.after(0, lambda: self.status.config(text="Ship: queue empty"))
                return

            cfg = ShipConfig(
                ssh_host=self.ship_ssh_host,
                server_pending_dir=self.ship_pending_dir,
            )

            total = len(links)
            ok = 0
            fail = 0
            last_err = ""

            self.after(0, lambda t=total: self.status.config(text=f"Shipping 0/{t} job(s) to server…"))

            # Ship one-by-one to give progress feedback and keep going on errors
            for i, link in enumerate(links, start=1):
                try:
                    ship_urls([link], cfg, force=force)
                    ok += 1
                    self.after(
                        0,
                        lambda i=i, total=total: self.status.config(text=f"Shipped {i}/{total}…"),
                    )
                except Exception as e:
                    fail += 1
                    last_err = str(e)
                    self.after(
                        0,
                        lambda i=i, total=total, m=last_err: self.status.config(
                            text=f"Ship failed ({i}/{total}): {m}"
                        ),
                    )

            self.after(
                0,
                lambda ok=ok, fail=fail, total=total: self.status.config(
                    text=f"Ship done: {ok}/{total} ok, {fail} failed"
                ),
            )
        finally:
            self._ship_running = False
            self.after(0, lambda: self._set_ship_buttons_enabled(True))

    def ship_queue_to_server(self):
        if self._ship_running:
            self.status.config(text="Ship already running…")
            return
        links = extract_http_links(self.custom_editor.get("1.0", tk.END))
        self._ship_running = True
        self._set_ship_buttons_enabled(False)
        t = threading.Thread(target=self._ship_thread, args=(links,), daemon=True)
        t.start()

    def ship_selected_to_server(self):
        if self._ship_running:
            self.status.config(text="Ship already running…")
            return

        # If there is a selection in the queue editor, ship only those lines.
        # Otherwise, fall back to shipping the whole queue.
        try:
            text = self.custom_editor.get(tk.SEL_FIRST, tk.SEL_LAST)
            links = extract_http_links(text)
            if not links:
                links = extract_http_links(self.custom_editor.get("1.0", tk.END))
        except tk.TclError:
            links = extract_http_links(self.custom_editor.get("1.0", tk.END))

        self._ship_running = True
        self._set_ship_buttons_enabled(False)
        t = threading.Thread(target=self._ship_thread, args=(links,), daemon=True)
        t.start()

    # ---------------- Streamrip (local) ----------------

    def send_to_streamrip(self):
        links = [
            l.strip().split()[0]
            for l in self.custom_editor.get("1.0", tk.END).splitlines()
            if l.strip().startswith("http")
        ]
        if not links:
            self.status.config(text="Queue empty")
            return

        STREAMRIP_QUEUE.write_text("\n".join(links) + "\n")

        SHIPPED_DIR.mkdir(exist_ok=True)
        ts = datetime.now().strftime("%Y-%m-%d_%H-%M")
        (SHIPPED_DIR / f"{ts}_{len(links)}links_download_que.txt").write_text(
            "\n".join(links) + "\n"
        )

        subprocess.Popen(
            ["x-terminal-emulator", "-e", str(STREAMRIP_BIN), "file", str(STREAMRIP_QUEUE)]
        )
        self.status.config(text=f"Sent {len(links)} album(s) to streamrip")

    # ---------------- Curator ----------------

    def grep_section(self, section_name: str):
        if not self.current_artist_model:
            self.status.config(text="No artist selected")
            return
        selected = []

        for release in releases_for_section(self.current_artist_model, section_name):
            if release.deezer_album_id in self.confirmed:
                continue

            if len(selected) >= self.batch_size:
                break

            selected.append(release)

        for release in selected:
            self.custom_editor.insert(tk.END, release.url + "\n")
            record_attempt(self.attempts, release.deezer_album_id, release.url)

        save_attempts(ATTEMPTS_FILE, self.attempts)
        self.fire_history.append([release.url for release in selected])
        self.fire_history = self.fire_history[-self.MAX_FIRE_HISTORY :]
        self.status.config(text=f"Added {len(selected)} from {section_name}")

    def run_curator(self):
        if self.main_mode != "inbox":
            messagebox.showinfo("Switch mode", "Switch to Inbox mode first.")
            return

        self.save_inbox()
        self.status.config(text="Running curator…")

        thread = threading.Thread(target=self._run_curator_thread, daemon=True)
        thread.start()

    def _run_curator_thread(self):
        try:
            run_curation(INBOX_FILE, LOG_FILE, ARTISTS_DIR)
            self.after(0, self.full_refresh)
        finally:
            self.after(0, lambda: self.status.config(text="Idle"))

    # ---------------- Batch ----------------

    def on_batch_change(self, event=None):
        self.batch_size = int(self.batch_var.get())
        self.prefs["batch_size"] = self.batch_size

        # persist ship defaults too (so you can change them later if needed)
        self.prefs["ship_ssh_host"] = self.ship_ssh_host
        self.prefs["ship_pending_dir"] = self.ship_pending_dir

        save_preferences(PREFS_FILE, self.prefs)
        self.title(f"STiGMA Archive Hub — batch {self.batch_size}")


def main():
    app = DeezerCuratorGUI()
    app.mainloop()


if __name__ == "__main__":
    main()
