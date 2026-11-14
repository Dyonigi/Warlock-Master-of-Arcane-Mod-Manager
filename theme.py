"""Warlock Mod Manager — colors and ttk theme."""

from __future__ import annotations

import tkinter as tk
from tkinter import ttk


BG = "#1b1a22"
BG2 = "#252433"
FG = "#f3ead8"
ACCENT = "#c9a227"
MUTED = "#9a927f"


def apply_theme(root: tk.Misc) -> None:
    style = ttk.Style(root)
    try:
        style.theme_use("clam")
    except tk.TclError:
        pass
    style.configure(".", background=BG, foreground=FG, fieldbackground=BG2)
    style.configure("TFrame", background=BG)
    style.configure("TLabel", background=BG, foreground=FG)
    style.configure("TButton", background=BG2, foreground=FG, padding=6)
    style.configure("Accent.TButton", background=ACCENT, foreground="#1b1a22", padding=6)
    style.configure("TNotebook", background=BG)
    style.configure("TNotebook.Tab", background=BG2, foreground=FG, padding=[10, 4])
    style.configure("TLabelframe", background=BG, foreground=ACCENT)
    style.configure("TLabelframe.Label", background=BG, foreground=ACCENT)
    style.configure("Treeview", background=BG2, foreground=FG, fieldbackground=BG2, rowheight=22)
    style.configure("Treeview.Heading", background="#323044", foreground=ACCENT)
    style.map("Treeview", background=[("selected", "#4a3f1f")], foreground=[("selected", FG)])
    style.configure("TEntry", fieldbackground=BG2, foreground=FG)
    style.configure("TCombobox", fieldbackground=BG2, foreground=FG)
    style.configure("Vertical.TScrollbar", background=BG2)