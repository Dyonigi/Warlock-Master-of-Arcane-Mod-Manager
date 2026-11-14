"""Warlock Mod Manager — image preview tab."""

from __future__ import annotations

import os
import tkinter as tk
from tkinter import ttk
from typing import Dict, Optional

try:
    from PIL import Image, ImageTk
    PIL_AVAILABLE = True
except ImportError:
    Image = None
    ImageTk = None
    PIL_AVAILABLE = False

from theme import BG, BG2, MUTED


class PreviewPanel(ttk.Frame):
    """A self-contained image preview tab.

    Usage:
        panel = PreviewPanel(parent)
        panel.show_image("/path/to/foo.dds")

    The panel handles its own canvas resize and keeps strong references
    to PhotoImage objects internally, so callers never have to worry
    about garbage collection.
    """

    IMAGE_EXTS = {".dds", ".jpg", ".jpeg", ".png", ".tga", ".bmp", ".gif"}

    def __init__(self, parent: tk.Misc) -> None:
        super().__init__(parent)
        self._image_cache: Dict[str, object] = {}
        self._current_path: Optional[str] = None

        self.canvas = tk.Canvas(self, bg=BG2, highlightthickness=0)
        self.canvas.pack(fill="both", expand=True)
        self.canvas.bind("<Configure>", self._on_resize)

        self.info = ttk.Label(self, text="", background=BG, foreground=MUTED)
        self.info.pack(fill="x", padx=6, pady=4)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------
    @classmethod
    def is_image_file(cls, path: str) -> bool:
        return os.path.splitext(path)[1].lower() in cls.IMAGE_EXTS

    def show_image(self, path: str) -> None:
        """Render the image at `path`, or an error message on failure."""
        self._current_path = path
        self.canvas.delete("all")
        self._image_cache.clear()

        if not PIL_AVAILABLE:
            self.info.configure(
                text="Install Pillow to preview images:  pip install Pillow"
            )
            return

        if not os.path.isfile(path):
            self.info.configure(text=f"File not found: {path}")
            return

        try:
            img = Image.open(path)
            img.load()
        except Exception as exc:
            self.info.configure(text=f"Could not load image: {exc}")
            return

        orig_size = img.size
        cw = max(self.canvas.winfo_width(), 1)
        ch = max(self.canvas.winfo_height(), 1)
        iw, ih = orig_size
        scale = min(cw / iw, ch / ih, 1.0)
        new_size = (max(int(iw * scale), 1), max(int(ih * scale), 1))
        if new_size != (iw, ih):
            img = img.resize(new_size, Image.LANCZOS)

        if img.mode not in ("RGB", "RGBA"):
            img = img.convert("RGBA")

        photo = ImageTk.PhotoImage(img)
        key = f"img{len(self._image_cache)}"
        self._image_cache[key] = photo
        self.canvas.create_image(cw // 2, ch // 2, image=photo, anchor="center")

        self.info.configure(
            text=f"{os.path.basename(path)}  {orig_size[0]}×{orig_size[1]}  "
                 f"shown at {new_size[0]}×{new_size[1]}  mode={img.mode}"
        )

    def clear(self) -> None:
        self.canvas.delete("all")
        self._image_cache.clear()
        self._current_path = None
        self.info.configure(text="")

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------
    def _on_resize(self, _evt=None) -> None:
        if self._current_path and self.is_image_file(self._current_path):
            self.show_image(self._current_path)