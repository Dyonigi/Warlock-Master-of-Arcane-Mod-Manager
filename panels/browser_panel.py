"""Warlock Mod Manager — structured XML editor + raw text tab + file tree."""

from __future__ import annotations

import os
import tkinter as tk
from tkinter import messagebox, simpledialog, ttk
from typing import Callable, Dict, List, Optional
import xml.etree.ElementTree as ET

from theme import ACCENT, BG, BG2, FG, MUTED
from txml import is_value_node
from xmlmodel import (
    KNOWN_TYPES,
    add_container_child,
    add_value_child,
    delete_node,
    duplicate_node,
    node_label,
    record_identity,
)
from panels.locdata_panel import LocdataPanel


# Callbacks the panel expects from its host.
FileSelectedFn = Callable[[str], None]      # user clicked a file in the tree
DirtyChangedFn = Callable[[], None]         # user edited something
JumpFn = Callable[[str], None]              # user clicked "Go to definition"


class BrowserPanel(ttk.Frame):
    """The editor pane: structured XML view, form, raw text, and file tree.

    The panel owns no file state. It receives a root element to display,
    and calls back into the host when the user does something that
    requires host knowledge (open another file, save, jump to a reference).
    """

    REFERENCE_TAGS = {
        "ActionData", "Item", "Perk", "Spell", "SpellData", "Unit", "UnitData",
        "Building", "BuildingData", "Upgrade", "UpgradeData", "Effect",
        "PerkData", "QuestData", "ArtifactData",
    }

    def __init__(
        self,
        parent: tk.Misc,
        *,
        on_file_selected: Optional[FileSelectedFn] = None,
        on_dirty_changed: Optional[DirtyChangedFn] = None,
        on_jump_requested: Optional[JumpFn] = None,
        localization_getter: Optional[Callable[[], Dict[str, str]]] = None,
    ) -> None:
        super().__init__(parent)
        self._on_file_selected = on_file_selected
        self._on_dirty_changed = on_dirty_changed
        self._on_jump_requested = on_jump_requested
        self._loc_getter = localization_getter or (lambda: {})

        self.tree_xml: Optional[ET.ElementTree] = None
        self.iid_to_node: Dict[str, ET.Element] = {}
        self.iid_to_parent: Dict[str, Optional[ET.Element]] = {}
        self.current_orig: Optional[str] = None
        self._current_path: Optional[str] = None
        self.dirty = False

        self.form_vars: Dict[str, tk.StringVar] = {}

        self.filter_var = tk.StringVar()
        self.xml_filter_var = tk.StringVar()

        self._build()

    # ------------------------------------------------------------------
    # Properties for the host
    # ------------------------------------------------------------------
    @property
    def localization(self) -> Dict[str, str]:
        return self._loc_getter()

    # ------------------------------------------------------------------
    # Build
    # ------------------------------------------------------------------
    def _build(self) -> None:
        self.paned = ttk.Panedwindow(self, orient="horizontal")
        self.paned.pack(fill="both", expand=True)

        left = ttk.Frame(self.paned)
        right = ttk.Frame(self.paned)
        self.paned.add(left, weight=1)
        self.paned.add(right, weight=4)   # <-- da 2 a 4

        self._build_file_tree(left)
        self._build_editor(right)

        # Forza il sash a ~260px dopo che il widget ha una geometria reale
        self.after(100, lambda: self._set_sash(260))

    def _set_sash(self, x: int) -> None:
        try:
            self.paned.sashpos(0, x)
        except tk.TclError:
            pass

    def _build_file_tree(self, parent: ttk.Frame) -> None:
        files = ttk.LabelFrame(parent, text="Editable files by category")
        files.pack(fill="both", expand=True)
        filt = ttk.Frame(files)
        filt.pack(fill="x")
        ttk.Label(filt, text="Filter").pack(side="left", padx=4)
        fe = ttk.Entry(filt, textvariable=self.filter_var)
        fe.pack(side="left", fill="x", expand=True, padx=4, pady=4)
        fe.bind("<KeyRelease>", lambda e: self._on_filter_changed())
        self.file_tree = ttk.Treeview(files, show="tree")
        self.file_tree.pack(fill="both", expand=True)
        self.file_tree.bind("<<TreeviewSelect>>", self._on_file_tree_select)

        self._filter_callback: Optional[Callable[[], None]] = None

    def set_filter_callback(self, cb: Callable[[], None]) -> None:
        """Host provides a callback invoked when the filter text changes."""
        self._filter_callback = cb

    def _on_filter_changed(self) -> None:
        if self._filter_callback:
            self._filter_callback()

    def _build_editor(self, parent: ttk.Frame) -> None:
        editor = ttk.LabelFrame(parent, text="What this data does — edit anything")
        editor.pack(fill="both", expand=True)
        self.nb = ttk.Notebook(editor)
        self.nb.pack(fill="both", expand=True)

        rec = ttk.Frame(self.nb)
        src = ttk.Frame(self.nb)
        self.nb.add(rec, text="Structured editor")
        self.nb.add(src, text="Raw XML / text")

        # Localization panel
        self.locdata_panel = LocdataPanel(self.nb, on_dirty_changed=self._mark_dirty)
        self.nb.add(self.locdata_panel, text="Localization")

        rec_paned = ttk.Panedwindow(rec, orient="vertical")
        rec_paned.pack(fill="both", expand=True)
        tree_fr = ttk.Frame(rec_paned)
        form_fr = ttk.Frame(rec_paned)
        rec_paned.add(tree_fr, weight=3)
        rec_paned.add(form_fr, weight=2)

        xml_filt = ttk.Frame(tree_fr)
        xml_filt.pack(fill="x")
        ttk.Label(xml_filt, text="Find").pack(side="left", padx=4)
        xf = ttk.Entry(xml_filt, textvariable=self.xml_filter_var)
        xf.pack(side="left", fill="x", expand=True, padx=4, pady=4)
        xf.bind("<Return>", lambda e: self.find_in_xml())
        ttk.Button(xml_filt, text="Find next", command=self.find_in_xml).pack(side="left", padx=4)

        self.xml_tree = ttk.Treeview(tree_fr, show="tree")
        ys = ttk.Scrollbar(tree_fr, orient="vertical", command=self.xml_tree.yview)
        self.xml_tree.configure(yscrollcommand=ys.set)
        self.xml_tree.pack(side="left", fill="both", expand=True)
        ys.pack(side="right", fill="y")
        self.xml_tree.bind("<<TreeviewSelect>>", self._on_xml_select)

        btns = ttk.Frame(form_fr)
        btns.pack(fill="x")
        ttk.Button(btns, text="Duplicate", command=self.dup_node).pack(side="left", padx=2, pady=4)
        ttk.Button(btns, text="Delete", command=self.del_node).pack(side="left", padx=2)
        ttk.Button(btns, text="Add value field", command=self.add_value).pack(side="left", padx=2)
        ttk.Button(btns, text="Add group", command=self.add_group).pack(side="left", padx=2)

        self.form = ttk.Frame(form_fr)
        self.form.pack(fill="both", expand=True)

        self.raw = tk.Text(src, bg=BG2, fg=FG, insertbackground=FG, wrap="none", undo=True)
        self.raw.pack(fill="both", expand=True)
        ttk.Button(src, text="Apply raw text to structured tree", command=self.apply_raw).pack(pady=4)

    # ------------------------------------------------------------------
    # Public API used by the host
    # ------------------------------------------------------------------
    def populate_file_tree(self, cats: Dict[str, List[str]], labels: Dict[str, str], order: List[str]) -> None:
        self.file_tree.delete(*self.file_tree.get_children())
        seen = set()
        for cid in order + list(cats):
            if cid in seen or cid not in cats:
                continue
            seen.add(cid)
            parent = self.file_tree.insert(
                "", "end", iid=f"cat:{cid}",
                text=f"{labels.get(cid, cid)} ({len(cats[cid])})",
            )
            for orig in sorted(cats[cid], key=str.lower):
                self.file_tree.insert(parent, "end", iid=orig, text=orig)

    def clear_file_tree(self) -> None:
        self.file_tree.delete(*self.file_tree.get_children())

    def show_root(self, orig: str, path: str, tree: ET.ElementTree) -> None:
        """Display the given XML tree as the current document."""
        self.current_orig = orig
        self._current_path = path
        self.tree_xml = tree
        self.form_clear()
        self.xml_tree.delete(*self.xml_tree.get_children())
        self.iid_to_node.clear()
        self.iid_to_parent.clear()
        self.raw.delete("1.0", "end")
        self._fill_xml_tree("", tree.getroot(), None)
        self.raw.insert("1.0", open(path, encoding="utf-8").read())
        self.nb.select(0)
        self.dirty = False

    def show_raw_text(self, orig: str, path: str, text: str) -> None:
        """Display a non-XML file as plain text."""
        self.current_orig = orig
        self._current_path = path
        self.tree_xml = None
        self.form_clear()
        self.xml_tree.delete(*self.xml_tree.get_children())
        self.iid_to_node.clear()
        self.iid_to_parent.clear()
        self.raw.delete("1.0", "end")
        self.raw.insert("1.0", text)
        self.nb.select(1)
        self.dirty = False
    def show_locdata(self, orig: str, path: str, text: str = "", vanilla: Optional[bytes] = None) -> None:
        self.current_orig = orig
        self._current_path = path
        self.tree_xml = None
        self.dirty = False

        with open(path, "rb") as f:
            self.locdata_panel.set_data(f.read(), vanilla)
        self.nb.select(2)
    def is_locdata_active(self) -> bool:
        return self.nb.index(self.nb.select()) == 2

    def get_locdata_bytes(self) -> bytes:
        return self.locdata_panel.get_data()

    def get_raw_text(self) -> str:
        return self.raw.get("1.0", "end-1c")
        
    def is_raw_tab_active(self) -> bool:
        # Consideriamo attivo sia il raw che il locdata
        return self.nb.index(self.nb.select()) in (1, 2)

    def get_tree(self) -> Optional[ET.ElementTree]:
        return self.tree_xml

    def mark_clean(self) -> None:
        self.dirty = False

    def focus_identity(self, value: str) -> None:
        """Find the record whose identity matches `value` and select it."""
        from xmlmodel import iter_identity_values
        for iid, node in self.iid_to_node.items():
            if is_value_node(node):
                continue
            for v, _tag in iter_identity_values(node):
                if v == value:
                    self.xml_tree.see(iid)
                    self.xml_tree.selection_set(iid)
                    self.xml_tree.focus(iid)
                    self._on_xml_select()
                    return

    # ------------------------------------------------------------------
    # File tree events
    # ------------------------------------------------------------------
    def _on_file_tree_select(self, _evt=None) -> None:
        sel = self.file_tree.selection()
        if not sel:
            return
        iid = sel[0]
        if iid.startswith("cat:"):
            return
        if self._on_file_selected:
            self._on_file_selected(iid)

    def select_file_iid(self, orig: str) -> None:
        try:
            self.file_tree.selection_set(orig)
            self.file_tree.see(orig)
        except tk.TclError:
            pass

    # ------------------------------------------------------------------
    # XML tree and form
    # ------------------------------------------------------------------
    def _fill_xml_tree(self, parent_iid: str, node: ET.Element, parent_node: Optional[ET.Element]) -> None:
        iid = f"n{len(self.iid_to_node)}"
        self.iid_to_node[iid] = node
        self.iid_to_parent[iid] = parent_node
        self.xml_tree.insert(parent_iid, "end", iid=iid, text=node_label(node, self.localization))
        for child in node:
            self._fill_xml_tree(iid, child, node)

    def rebuild_visible_tree(self) -> None:
        """Re-render the currently open XML tree (e.g. after localization loads)."""
        if self.tree_xml is None:
            return
        self.xml_tree.delete(*self.xml_tree.get_children())
        self.iid_to_node.clear()
        self.iid_to_parent.clear()
        self._fill_xml_tree("", self.tree_xml.getroot(), None)

    def _on_xml_select(self, _evt=None) -> None:
        sel = self.xml_tree.selection()
        if not sel:
            return
        node = self.iid_to_node.get(sel[0])
        if node is None:
            return
        self.form_clear()

        header = f"Tag: {node.tag}"
        if not is_value_node(node):
            ident = record_identity(node)
            if ident:
                from project import localization_lookup
                friendly = localization_lookup(self.localization, ident)
                if friendly:
                    header += f"   —   {friendly}"
        ttk.Label(self.form, text=header, foreground=ACCENT).pack(anchor="w", padx=6, pady=4)

        self.form_vars.clear()
        for key, val in node.attrib.items():
            row = ttk.Frame(self.form)
            row.pack(fill="x", padx=6, pady=2)
            ttk.Label(row, text=key, width=14).pack(side="left")
            var = tk.StringVar(value=val)
            self.form_vars[key] = var
            e = ttk.Entry(row, textvariable=var)
            e.pack(side="left", fill="x", expand=True)
            var.trace_add("write", lambda *_a, k=key, n=node: self._attr_changed(n, k))

        if not is_value_node(node):
            ident = record_identity(node)
            if ident and self.localization:
                from project import localization_lookup_desc
                desc = localization_lookup_desc(self.localization, ident)
                if desc:
                    ttk.Label(
                        self.form, text=desc, foreground=MUTED,
                        wraplength=520, justify="left",
                    ).pack(anchor="w", padx=6, pady=(4, 8))

        if is_value_node(node) and self._is_reference_node(node):
            ref_val = node.attrib.get("value", "")
            btn_row = ttk.Frame(self.form)
            btn_row.pack(fill="x", padx=6, pady=6)
            ttk.Label(btn_row, text=f"→ {ref_val}", foreground=ACCENT).pack(side="left")
            ttk.Button(
                btn_row, text="Go to definition",
                command=lambda v=ref_val: self._request_jump(v),
            ).pack(side="left", padx=6)
        if is_value_node(node):
            ttk.Label(
                self.form,
                text="This is a typed game value (TXML). Changing type/value writes back into the binary on pack.",
            ).pack(anchor="w", padx=6, pady=8)

    def _request_jump(self, value: str) -> None:
        if self._on_jump_requested:
            self._on_jump_requested(value)

    def _attr_changed(self, node: ET.Element, key: str) -> None:
        var = self.form_vars.get(key)
        if var is None:
            return
        node.set(key, var.get())
        self.dirty = True
        if self._on_dirty_changed:
            self._on_dirty_changed()
        sel = self.xml_tree.selection()
        if sel:
            self.xml_tree.item(sel[0], text=node_label(node, self.localization))

    def _is_reference_node(self, node: ET.Element) -> bool:
        if not is_value_node(node):
            return False
        if node.attrib.get("type") != "string":
            return False
        if node.tag in self.REFERENCE_TAGS:
            return True
        if node.tag.endswith("Name") or node.tag.endswith("Data"):
            return True
        return False

    def form_clear(self) -> None:
        for w in self.form.winfo_children():
            w.destroy()
        self.form_vars.clear()

    # ------------------------------------------------------------------
    # Find
    # ------------------------------------------------------------------
    def find_in_xml(self) -> None:
        needle = self.xml_filter_var.get().strip().lower()
        if not needle:
            return

        iids = list(self.iid_to_node.keys())
        start = 0
        sel = self.xml_tree.selection()
        if sel:
            try:
                start = iids.index(sel[0]) + 1
            except ValueError:
                start = 0
        ordered = iids[start:] + iids[:start]

        for iid in ordered:
            node = self.iid_to_node.get(iid)
            if node is None:
                continue

            label = str(self.xml_tree.item(iid, "text")).lower()
            if needle in label:
                self._jump_to_iid(iid)
                return

            if not is_value_node(node):
                ident = record_identity(node)
                if ident:
                    if needle in ident.lower():
                        self._jump_to_iid(iid)
                        return
                    from project import localization_lookup, localization_lookup_desc
                    friendly = localization_lookup(self.localization, ident).lower()
                    if friendly and needle in friendly:
                        self._jump_to_iid(iid)
                        return
                    desc = localization_lookup_desc(self.localization, ident).lower()
                    if desc and needle in desc:
                        self._jump_to_iid(iid)
                        return

            if is_value_node(node):
                val = str(node.attrib.get("value", "")).lower()
                if needle in val or needle in node.tag.lower():
                    self._jump_to_iid(iid)
                    return

        messagebox.showinfo("Find", f"No match for '{needle}'.")

    def _jump_to_iid(self, iid: str) -> None:
        self.xml_tree.see(iid)
        self.xml_tree.selection_set(iid)
        self.xml_tree.focus(iid)
        self._on_xml_select()

    # ------------------------------------------------------------------
    # Node operations
    # ------------------------------------------------------------------
    def _selected_xml(self):
        sel = self.xml_tree.selection()
        if not sel:
            return None, None, None
        iid = sel[0]
        return iid, self.iid_to_node[iid], self.iid_to_parent[iid]

    def _mark_dirty(self) -> None:
        self.dirty = True
        if self._on_dirty_changed:
            self._on_dirty_changed()

    def dup_node(self) -> None:
        iid, node, parent = self._selected_xml()
        if node is None or parent is None:
            messagebox.showinfo("Duplicate", "Select a child node (not the document root).")
            return
        clone = duplicate_node(parent, node)
        self._mark_dirty()
        self._reload_tree_keep(clone)

    def del_node(self) -> None:
        iid, node, parent = self._selected_xml()
        if node is None or parent is None:
            return
        if not messagebox.askyesno("Delete", f"Delete {node.tag}?"):
            return
        delete_node(parent, node)
        self._mark_dirty()
        self._reload_tree_keep(parent)

    def add_value(self) -> None:
        iid, node, parent = self._selected_xml()
        target = node
        if target is None:
            return
        tag = simpledialog.askstring("Field name", "XML tag for the new value (e.g. buildingCost)")
        if not tag:
            return
        type_str = simpledialog.askstring("Type", "TXML type", initialvalue="integer")
        if not type_str or type_str not in KNOWN_TYPES:
            messagebox.showerror("Type", "Known types: " + ", ".join(KNOWN_TYPES))
            return
        value = simpledialog.askstring("Value", "Initial value", initialvalue="0") or "0"
        add_value_child(target, tag, type_str, value)
        self._mark_dirty()
        self._reload_tree_keep(target)

    def add_group(self) -> None:
        iid, node, parent = self._selected_xml()
        if node is None:
            return
        tag = simpledialog.askstring("Group name", "XML tag for the new group (e.g. Perks)")
        if not tag:
            return
        add_container_child(node, tag)
        self._mark_dirty()
        self._reload_tree_keep(node)

    def _reload_tree_keep(self, focus: ET.Element) -> None:
        if self.tree_xml is None:
            return
        self.xml_tree.delete(*self.xml_tree.get_children())
        self.iid_to_node.clear()
        self.iid_to_parent.clear()
        self._fill_xml_tree("", self.tree_xml.getroot(), None)
        for iid, n in self.iid_to_node.items():
            if n is focus:
                self.xml_tree.see(iid)
                self.xml_tree.selection_set(iid)
                break
        self._sync_raw_from_tree()

    def _sync_raw_from_tree(self) -> None:
        if self.tree_xml is None:
            return
        import tempfile
        from xmlmodel import write_xml_file

        fd, tmp = tempfile.mkstemp(suffix=".xml")
        os.close(fd)
        try:
            write_xml_file(self.tree_xml, tmp)
            self.raw.delete("1.0", "end")
            self.raw.insert("1.0", open(tmp, encoding="utf-8").read())
        finally:
            os.remove(tmp)

    def apply_raw(self, silent: bool = False) -> None:
        text = self.raw.get("1.0", "end-1c")
        if self._current_path and self._current_path.lower().endswith(".xml"):
            try:
                root = ET.fromstring(text)
            except ET.ParseError as exc:
                if not silent:
                    messagebox.showerror("XML parse", str(exc))
                return
            self.tree_xml = ET.ElementTree(root)
            self._mark_dirty()
            self.xml_tree.delete(*self.xml_tree.get_children())
            self.iid_to_node.clear()
            self.iid_to_parent.clear()
            self._fill_xml_tree("", root, None)
        else:
            self._mark_dirty()