import tkinter as tk
from tkinter import ttk, messagebox
from pathlib import Path
from datetime import datetime
import subprocess

from curator.curate import run_curation
from curator.write import write_by_artist

# ---------------- Paths ----------------

DATA_DIR = Path("data")
INBOX = DATA_DIR / "inbox.txt"
LOG = DATA_DIR / "curated.log"
ARTISTS_DIR = DATA_DIR / "artists"
SHIPPED_DIR = DATA_DIR / "shipped"

STREAMRIP_BIN = Path(
    "/home/stigma/Dokument/projekt/streamrip/.venv/bin/rip"
)

STREAMRIP_QUEUE = Path(
    "/home/stigma/Dokument/projekt/streamrip/download_que.txt"
)


# ---------------- GUI ----------------


class DeezerCuratorGUI(tk.Tk):
    def __init__(self):
        super().__init__()

        self.title("STiGMA Deezer Curator — v0.1")
        self.geometry("1400x700")

        self.main_mode = "artist"  # artist | inbox
        self.custom_file_path = STREAMRIP_QUEUE

        self._build_layout()
        self.refresh_artists()
        self.load_inbox()
        self.load_custom_queue()

    # ---------------- UI ----------------

    def _build_layout(self):
        main = ttk.Panedwindow(self, orient="horizontal")
        main.pack(fill="both", expand=True)

        # ===== LEFT: Artist list =====
        left = ttk.Frame(main, padding=6)
        main.add(left, weight=1)

        ttk.Label(left, text="Artists").pack(anchor="w")
        self.artist_list = tk.Listbox(left)
        self.artist_list.pack(fill="both", expand=True)
        self.artist_list.bind("<<ListboxSelect>>", self.open_selected_artist)

        # ===== CENTER: Main editor (Artist / Inbox) =====
        center = ttk.Frame(main, padding=6)
        main.add(center, weight=2)

        self.main_label = ttk.Label(center, text="Artist file")
        self.main_label.pack(anchor="w")

        self.main_editor = tk.Text(center, wrap="none")
        self.main_editor.pack(fill="both", expand=True)

        # ===== RIGHT: Custom editor (streamrip queue) =====
        right = ttk.Frame(main, padding=6)
        main.add(right, weight=2)

        ttk.Label(right, text="Streamrip queue").pack(anchor="w")
        self.custom_editor = tk.Text(right, wrap="none")
        self.custom_editor.pack(fill="both", expand=True)

        # ===== Bottom bar =====
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
            bottom, text="Send to streamrip", command=self.send_to_streamrip
        ).pack(side="left", padx=12)

        ttk.Button(
            bottom, text="Run Curator (Inbox)", command=self.run_from_inbox
        ).pack(side="left", padx=12)

        self.status = ttk.Label(bottom, text="Idle")
        self.status.pack(side="right")

    # ---------------- Modes ----------------

    def show_artist_mode(self):
        self.main_mode = "artist"
        self.main_label.config(text="Artist file")
        self.main_editor.config(state="disabled")
        self.status.config(text="Artist mode")

    def show_inbox_mode(self):
        self.main_mode = "inbox"
        self.main_label.config(text="Inbox (data/inbox.txt)")
        self.main_editor.config(state="normal")
        self.load_inbox()
        self.status.config(text="Inbox mode")

    # ---------------- Artist ----------------

    def refresh_artists(self):
        ARTISTS_DIR.mkdir(parents=True, exist_ok=True)
        self.artist_list.delete(0, tk.END)

        for path in sorted(ARTISTS_DIR.glob("*.txt")):
            self.artist_list.insert(tk.END, path.name)

    def open_selected_artist(self, event=None):
        selection = self.artist_list.curselection()
        if not selection:
            return

        filename = self.artist_list.get(selection[0])
        path = ARTISTS_DIR / filename

        self.show_artist_mode()
        self.main_editor.config(state="normal")
        self.main_editor.delete("1.0", tk.END)

        try:
            self.main_editor.insert(tk.END, path.read_text(encoding="utf-8"))
            self.status.config(text=f"Viewing {filename}")
        except Exception as exc:
            messagebox.showerror("Error", str(exc))

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
        self.status.config(text="Inbox saved")

    # ---------------- Custom / Streamrip ----------------

    def load_custom_queue(self):
        self.custom_editor.delete("1.0", tk.END)
        if STREAMRIP_QUEUE.exists():
            self.custom_editor.insert(
                tk.END, STREAMRIP_QUEUE.read_text(encoding="utf-8")
            )

    def _extract_links(self, text: str) -> list[str]:
        return [
            line.strip()
            for line in text.splitlines()
            if line.strip().startswith(("http://", "https://"))
        ]

    def send_to_streamrip(self):
        if not STREAMRIP_BIN.exists():
            messagebox.showerror(
                "Streamrip not found",
                f"streamrip not found at:\n{STREAMRIP_BIN}",
            )
            return

        raw_text = self.custom_editor.get("1.0", tk.END)
        links = self._extract_links(raw_text)

        if not links:
            messagebox.showwarning(
                "No links", "No valid URLs found to send to streamrip."
            )
            return

        # Write cleaned queue to canonical streamrip file
        STREAMRIP_QUEUE.write_text("\n".join(links) + "\n", encoding="utf-8")

        # Archive copy
        SHIPPED_DIR.mkdir(parents=True, exist_ok=True)
        timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M")
        archive_name = f"{timestamp}_{len(links)}links_download_que.txt"
        archive_path = SHIPPED_DIR / archive_name
        archive_path.write_text("\n".join(links) + "\n", encoding="utf-8")

        # Fire-and-forget streamrip
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
            text=f"Sent {len(links)} links to streamrip • archived as {archive_name}"
        )

    # ---------------- Curator ----------------

    def _run_curator(self, inbox_path: Path, source_name: str):
        self.status.config(text=f"Running curator from {source_name}…")
        self.update_idletasks()

        album_links = run_curation(inbox_path=inbox_path, log_path=LOG)
        total = len(album_links)

        for idx, url in enumerate(album_links, start=1):
            short = url.rsplit("/", 1)[-1]
            self.status.config(
                text=f"Processing {idx}/{total}: album/{short}"
            )
            self.update_idletasks()
            write_by_artist([url], ARTISTS_DIR)

        self.refresh_artists()
        self.status.config(text="Done")

        messagebox.showinfo(
            "Done",
            f"Curator finished.\n\nSource: {source_name}\nAlbums written: {total}",
        )

    def run_from_inbox(self):
        self.show_inbox_mode()
        self.save_inbox()
        self._run_curator(INBOX, "Inbox")


def main():
    app = DeezerCuratorGUI()
    app.mainloop()


if __name__ == "__main__":
    main()
