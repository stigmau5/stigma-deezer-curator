import tkinter as tk
from tkinter import ttk, messagebox
from pathlib import Path
from datetime import datetime
import subprocess
import json
import re
import threading

from curator.curate import run_curation

# ---------------- Base paths ----------------

BASE_DIR = Path(__file__).resolve().parent

DATA_DIR = BASE_DIR / "data"
INBOX = DATA_DIR / "inbox.txt"
LOG = DATA_DIR / "curated.log"
ARTISTS_DIR = DATA_DIR / "artists"
SHIPPED_DIR = DATA_DIR / "shipped"
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

        self._build_layout()
        self.refresh_artists()
        self.load_inbox()
        self.load_custom_queue()

    # ---------------- UI ----------------

    def _build_layout(self):
        main = ttk.Panedwindow(self, orient="horizontal")
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
        bottom = ttk.Frame(self, padding=8)
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
