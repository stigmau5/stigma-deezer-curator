from __future__ import annotations

import base64
import subprocess
import tkinter as tk
from pathlib import Path
from typing import Any, Callable

from audio_division.artifacts import AlbumArtifacts, detect_artifacts


def album_cover_info(
    details: dict[str, Any],
    archive_path: Path | None = None,
    detected_artifacts: AlbumArtifacts | None = None,
) -> dict[str, str]:
    artwork = details.get("artwork", {}) if isinstance(details.get("artwork"), dict) else {}
    local = artwork.get("local")
    local_path = Path(local) if isinstance(local, (str, Path)) and local else None
    if local_path and local_path.exists() and local_path.is_file():
        return _present(local_path)

    if archive_path:
        selected = (detected_artifacts or detect_artifacts(archive_path)).selected_artwork
        if selected:
            return _present(selected)

    return {
        "status": "Missing",
        "source": "none",
        "path": "",
        "url": "",
        "display": "No artwork available",
    }


class CoverWidget:
    def __init__(
        self,
        label: tk.Label,
        status_label: Any | None = None,
        *,
        image_loader: Callable[[str, tk.Label], tk.PhotoImage] | None = None,
    ):
        self.label = label
        self.status_label = status_label
        self.image_loader = image_loader or self.load_image
        self.image = None

    def render(self, cover: dict[str, Any]):
        status = str(cover.get("status") or "Missing")
        display = str(cover.get("display") or "")
        if self.status_label is not None:
            self.status_label.config(text=f"Artwork: {status} - {display}".rstrip(" -"))

        path = str(cover.get("path") or "")
        if path:
            try:
                self.image = self.image_loader(path, self.label)
                self.label.config(image=self.image, text="")
                return self.image
            except (OSError, tk.TclError, subprocess.SubprocessError):
                self.image = None
                self.label.config(image="", text="Artwork unavailable")
                return None

        self.image = None
        self.label.config(image="", text="No artwork")
        return None

    @staticmethod
    def load_image(path: str, label: tk.Label) -> tk.PhotoImage:
        try:
            return fit_image(tk.PhotoImage(file=path), label)
        except tk.TclError:
            return converted_image(path, label)


def fit_image(image: tk.PhotoImage, label: tk.Label, fallback_size: int = 320) -> tk.PhotoImage:
    max_size = cover_max_size(label, fallback_size)
    largest = max(image.width(), image.height())
    factor = max(1, (largest + max_size - 1) // max_size)
    return image.subsample(factor, factor) if factor > 1 else image


def converted_image(path: str, label: tk.Label) -> tk.PhotoImage:
    max_size = cover_max_size(label)
    result = subprocess.run(
        ["convert", str(path), "-auto-orient", "-resize", f"{max_size}x{max_size}", "png:-"],
        check=True,
        capture_output=True,
    )
    data = base64.b64encode(result.stdout).decode("ascii")
    return tk.PhotoImage(data=data)


def cover_max_size(label: tk.Label, fallback_size: int = 320) -> int:
    label.update_idletasks()
    max_size = min(label.winfo_width(), label.winfo_height())
    return max_size if max_size >= 80 else fallback_size


def _present(path: Path) -> dict[str, str]:
    return {
        "status": "Present",
        "source": "local",
        "path": str(path),
        "url": "",
        "display": path.name,
    }
