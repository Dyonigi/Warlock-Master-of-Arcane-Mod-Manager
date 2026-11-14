"""Warlock Mod Manager — workspace panel (middle column)."""

from __future__ import annotations

import tkinter as tk
from tkinter import ttk
from typing import Callable


class WorkspacePanel(ttk.Frame):
    """Middle column: load/repack buttons and pack-name entry."""

    def __init__(
        self,
        parent: tk.Misc,
        *,
        pack_name_var: tk.StringVar,
        on_load_merged: Callable[[], None],
        on_new_vanilla: Callable[[], None],
        on_hint_empty: Callable[[], None],
        on_save_current: Callable[[], None],
        on_repack_workspace: Callable[[], None],
        on_repack_and_install: Callable[[], None],
    ) -> None:
        super().__init__(parent)
        self._pack_name_var = pack_name_var

        act = ttk.LabelFrame(self, text="Workspace")
        act.pack(fill="x")
        ttk.Button(act, text="Load merged game data (vanilla + installed mods)",
                   command=on_load_merged).pack(fill="x", padx=6, pady=3)
        ttk.Button(act, text="New mod from vanilla only",
                   command=on_new_vanilla).pack(fill="x", padx=6, pady=3)
        ttk.Button(act, text="Empty new mod (copy selected files from workspace)",
                   command=on_hint_empty).pack(fill="x", padx=6, pady=3)

        pack_row = ttk.Frame(act)
        pack_row.pack(fill="x", padx=6, pady=6)
        ttk.Label(pack_row, text="Output pack").pack(side="left")
        ttk.Entry(pack_row, textvariable=pack_name_var, width=16).pack(side="left", padx=6)

        ttk.Button(act, text="Save current file",
                   command=on_save_current).pack(fill="x", padx=6, pady=3)
        ttk.Button(act, text="Repack workspace → pack file",
                   command=on_repack_workspace).pack(fill="x", padx=6, pady=3)
        ttk.Button(act, text="Repack and install into game",
                   command=on_repack_and_install,
                   style="Accent.TButton").pack(fill="x", padx=6, pady=3)

    def get_output_pack_name(self) -> str:
        return self._pack_name_var.get()

    def set_output_pack_name(self, name: str) -> None:
        self._pack_name_var.set(name)