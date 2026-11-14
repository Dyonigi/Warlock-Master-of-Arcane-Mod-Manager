"""Warlock Mod Manager — game folder scan panel (left column)."""

from __future__ import annotations

import tkinter as tk
from tkinter import ttk
from typing import Callable


class ScanPanel(ttk.Frame):
    """Left column: installed packs + available mods + notes."""

    def __init__(
        self,
        parent: tk.Misc,
        *,
        on_uninstall: Callable[[], None],
        on_unpack_installed: Callable[[], None],
        on_install_bundle: Callable[[], None],
        on_unpack_bundle: Callable[[], None],
        on_bundle_selected: Callable[[str], None],
    ) -> None:
        super().__init__(parent)
        self._on_uninstall = on_uninstall
        self._on_unpack_installed = on_unpack_installed
        self._on_install_bundle = on_install_bundle
        self._on_unpack_bundle = on_unpack_bundle
        self._on_bundle_selected = on_bundle_selected

        self._build()

    def _build(self) -> None:
        inst = ttk.LabelFrame(self, text="Installed in game folder")
        inst.pack(fill="both", expand=True, pady=(0, 6))
        self.installed_tree = ttk.Treeview(inst, columns=("kind", "files"), show="headings", height=10)
        self.installed_tree.heading("kind", text="Pack")
        self.installed_tree.heading("files", text="Files")
        self.installed_tree.column("kind", width=140)
        self.installed_tree.column("files", width=60)
        self.installed_tree.pack(fill="both", expand=True)

        row = ttk.Frame(inst)
        row.pack(fill="x")
        ttk.Button(row, text="Uninstall selected", command=self._on_uninstall).pack(side="left", padx=2, pady=4)
        ttk.Button(row, text="Unpack selected pack", command=self._on_unpack_installed).pack(side="left", padx=2)

        avail = ttk.LabelFrame(self, text="Mods in /mods folder")
        avail.pack(fill="both", expand=True)
        self.avail_tree = ttk.Treeview(avail, columns=("name", "packs"), show="headings", height=8)
        self.avail_tree.heading("name", text="Mod")
        self.avail_tree.heading("packs", text="Packs")
        self.avail_tree.column("name", width=160)
        self.avail_tree.column("packs", width=50)
        self.avail_tree.pack(fill="both", expand=True)
        self.avail_tree.bind("<<TreeviewSelect>>", self._on_avail_select)

        row2 = ttk.Frame(avail)
        row2.pack(fill="x")
        ttk.Button(row2, text="Install selected", command=self._on_install_bundle, style="Accent.TButton").pack(
            side="left", padx=2, pady=4
        )
        ttk.Button(row2, text="Unpack selected", command=self._on_unpack_bundle).pack(side="left", padx=2)

        from theme import BG2, FG
        self.notes = tk.Text(self, height=8, bg=BG2, fg=FG, insertbackground=FG, wrap="word", relief="flat")
        self.notes.pack(fill="x", pady=(6, 0))

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------
    def clear_installed(self) -> None:
        self.installed_tree.delete(*self.installed_tree.get_children())

    def add_installed(self, iid: str, pack_label: str, files: int) -> None:
        self.installed_tree.insert("", "end", iid=iid, values=(pack_label, str(files)))

    def clear_available(self) -> None:
        self.avail_tree.delete(*self.avail_tree.get_children())

    def add_available(self, iid: str, name: str, packs: int) -> None:
        self.avail_tree.insert("", "end", iid=iid, values=(name, str(packs)))

    def selected_installed(self) -> list[str]:
        return list(self.installed_tree.selection())

    def selected_available(self) -> list[str]:
        return list(self.avail_tree.selection())

    def set_notes(self, text: str) -> None:
        self.notes.delete("1.0", "end")
        self.notes.insert("1.0", text)

    def _on_avail_select(self, _evt=None) -> None:
        sel = self.avail_tree.selection()
        if sel:
            self._on_bundle_selected(sel[0])