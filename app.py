#!/usr/bin/env python3
"""Warlock: Master of the Arcane — graphical mod manager."""

from __future__ import annotations

import os
import sys
import threading
import tkinter as tk
from tkinter import filedialog, messagebox, simpledialog, ttk
from typing import Dict, List, Optional
import xml.etree.ElementTree as ET

# --- Image support (optional) ---
try:
    from PIL import Image, ImageTk
    PIL_AVAILABLE = True
except ImportError:
    Image = None
    ImageTk = None
    PIL_AVAILABLE = False

# Allow running as a script from this folder
HERE = os.path.dirname(os.path.abspath(__file__))
if HERE not in sys.path:
    sys.path.insert(0, HERE)

from catalog import CATEGORIES, VANILLA_PACKS, category_for
from detect import find_game_dir, is_game_dir
from project import (
    GameScan,
    build_pack_from_workspace,
    install_packs,
    merged_entries,
    scan_game,
    suggest_pack_name,
    uninstall_packs,
    write_workspace,
)
from txml import is_value_node
from xmlmodel import (
    KNOWN_TYPES,
    add_container_child,
    add_value_child,
    delete_node,
    duplicate_node,
    node_label,
    parse_xml_file,
    write_xml_file,
)


MODS_ROOT = os.path.dirname(HERE)
WORK_ROOT = os.path.join(HERE, "work")
BG = "#1b1a22"
BG2 = "#252433"
FG = "#f3ead8"
ACCENT = "#c9a227"
MUTED = "#9a927f"


class ModManagerApp(tk.Tk):
    def __init__(self) -> None:
        super().__init__()
        self.title("Warlock Mod Manager")
        self.geometry("1280x820")
        self.minsize(960, 640)
        self.configure(bg=BG)

        self.game_dir = tk.StringVar()
        self.status = tk.StringVar(value="Detecting game…")
        self.filter_var = tk.StringVar()
        self.pack_name_var = tk.StringVar()

        self.scan: Optional[GameScan] = None
        self.workspace_dir: Optional[str] = None
        self.manifest: Dict[str, str] = {}
        self.current_orig: Optional[str] = None
        self.tree_xml: Optional[ET.ElementTree] = None
        self.iid_to_node: Dict[str, ET.Element] = {}
        self.iid_to_parent: Dict[str, Optional[ET.Element]] = {}
        self.dirty = False
        self._busy = False

        self._style()
        self._build()
        self.after(50, self.auto_detect)

    def _style(self) -> None:
        style = ttk.Style(self)
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

    def _build(self) -> None:
        top = ttk.Frame(self)
        top.pack(fill="x", padx=10, pady=8)
        ttk.Label(top, text="Game folder").pack(side="left")
        ent = ttk.Entry(top, textvariable=self.game_dir)
        ent.pack(side="left", fill="x", expand=True, padx=8)
        ttk.Button(top, text="Browse…", command=self.browse_game).pack(side="left", padx=2)
        ttk.Button(top, text="Detect", command=self.auto_detect).pack(side="left", padx=2)
        ttk.Button(top, text="Refresh", command=self.refresh_scan).pack(side="left", padx=2)

        paned = ttk.Panedwindow(self, orient="horizontal")
        paned.pack(fill="both", expand=True, padx=10, pady=(0, 6))

        left = ttk.Frame(paned)
        mid = ttk.Frame(paned)
        right = ttk.Frame(paned)
        paned.add(left, weight=1)
        paned.add(mid, weight=1)
        paned.add(right, weight=2)

        inst = ttk.LabelFrame(left, text="Installed in game folder")
        inst.pack(fill="both", expand=True, pady=(0, 6))
        self.installed_tree = ttk.Treeview(inst, columns=("kind", "files"), show="headings", height=10)
        self.installed_tree.heading("kind", text="Pack")
        self.installed_tree.heading("files", text="Files")
        self.installed_tree.column("kind", width=140)
        self.installed_tree.column("files", width=60)
        self.installed_tree.pack(fill="both", expand=True)
        row = ttk.Frame(inst)
        row.pack(fill="x")
        ttk.Button(row, text="Uninstall selected", command=self.uninstall_selected).pack(side="left", padx=2, pady=4)
        ttk.Button(row, text="Unpack selected pack", command=self.unpack_selected_installed).pack(side="left", padx=2)

        avail = ttk.LabelFrame(left, text="Mods in /mods folder")
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
        ttk.Button(row2, text="Install selected", command=self.install_selected_bundle, style="Accent.TButton").pack(
            side="left", padx=2, pady=4
        )
        ttk.Button(row2, text="Unpack selected", command=self.unpack_selected_bundle).pack(side="left", padx=2)

        self.notes = tk.Text(left, height=8, bg=BG2, fg=FG, insertbackground=FG, wrap="word", relief="flat")
        self.notes.pack(fill="x", pady=(6, 0))

        act = ttk.LabelFrame(mid, text="Workspace")
        act.pack(fill="x")
        ttk.Button(act, text="Load merged game data (vanilla + installed mods)", command=self.load_merged).pack(
            fill="x", padx=6, pady=3
        )
        ttk.Button(act, text="New mod from vanilla only", command=self.new_from_vanilla).pack(fill="x", padx=6, pady=3)
        ttk.Button(act, text="Empty new mod (copy selected files from workspace)", command=self.hint_empty).pack(
            fill="x", padx=6, pady=3
        )
        pack_row = ttk.Frame(act)
        pack_row.pack(fill="x", padx=6, pady=6)
        ttk.Label(pack_row, text="Output pack").pack(side="left")
        ttk.Entry(pack_row, textvariable=self.pack_name_var, width=16).pack(side="left", padx=6)
        ttk.Button(act, text="Save current file", command=self.save_current).pack(fill="x", padx=6, pady=3)
        ttk.Button(act, text="Repack workspace → pack file", command=self.repack_workspace).pack(fill="x", padx=6, pady=3)
        ttk.Button(
            act, text="Repack and install into game", command=self.repack_and_install, style="Accent.TButton"
        ).pack(fill="x", padx=6, pady=3)

        files = ttk.LabelFrame(mid, text="Editable files by category")
        files.pack(fill="both", expand=True, pady=(8, 0))
        filt = ttk.Frame(files)
        filt.pack(fill="x")
        ttk.Label(filt, text="Filter").pack(side="left", padx=4)
        fe = ttk.Entry(filt, textvariable=self.filter_var)
        fe.pack(side="left", fill="x", expand=True, padx=4, pady=4)
        fe.bind("<KeyRelease>", lambda e: self.rebuild_file_tree())
        self.file_tree = ttk.Treeview(files, show="tree")
        self.file_tree.pack(fill="both", expand=True)
        self.file_tree.bind("<<TreeviewSelect>>", self._on_file_select)

        editor = ttk.LabelFrame(right, text="What this data does — edit anything")
        editor.pack(fill="both", expand=True)
        self.nb = ttk.Notebook(editor)
        self.nb.pack(fill="both", expand=True)

        rec = ttk.Frame(self.nb)
        src = ttk.Frame(self.nb)
        self.nb.add(rec, text="Structured editor")
        self.nb.add(src, text="Raw XML / text")

        rec_paned = ttk.Panedwindow(rec, orient="vertical")
        rec_paned.pack(fill="both", expand=True)
        tree_fr = ttk.Frame(rec_paned)
        form_fr = ttk.Frame(rec_paned)
        rec_paned.add(tree_fr, weight=3)
        rec_paned.add(form_fr, weight=2)

        xml_filt = ttk.Frame(tree_fr)
        xml_filt.pack(fill="x")
        ttk.Label(xml_filt, text="Find").pack(side="left", padx=4)
        self.xml_filter_var = tk.StringVar()
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
        self.form_vars: Dict[str, tk.StringVar] = {}
        self._xml_find_from = ""

        self.raw = tk.Text(src, bg=BG2, fg=FG, insertbackground=FG, wrap="none", undo=True)
        self.raw.pack(fill="both", expand=True)
        ttk.Button(src, text="Apply raw text to structured tree", command=self.apply_raw).pack(pady=4)

        bottom = ttk.Frame(self)
        bottom.pack(fill="x", padx=10, pady=(0, 8))
        ttk.Label(bottom, textvariable=self.status).pack(side="left")
        self.log = tk.Text(self, height=7, bg="#121118", fg=MUTED, insertbackground=FG, wrap="word")
        self.log.pack(fill="x", padx=10, pady=(0, 8))

    def log_msg(self, msg: str) -> None:
        def _do() -> None:
            self.log.insert("end", msg + "\n")
            self.log.see("end")
            self.status.set(msg)

        self.after(0, _do)

    def auto_detect(self) -> None:
        found = find_game_dir(self.game_dir.get().strip() or None)
        if found:
            self.game_dir.set(found)
            self.log_msg(f"Game found: {found}")
            self.refresh_scan()
        else:
            self.status.set("Game not found — browse to the Warlock folder (contains Game.exe).")
            self.log_msg("Could not auto-detect the game. Use Browse.")

    def browse_game(self) -> None:
        path = filedialog.askdirectory(title="Select Warlock - Master of the Arcane folder")
        if path:
            self.game_dir.set(path)
            if is_game_dir(path):
                self.refresh_scan()
            else:
                messagebox.showwarning("Not a game folder", "That folder does not look like a Warlock install (Game.exe + .pack files).")

    def refresh_scan(self) -> None:
        game = self.game_dir.get().strip()
        if not is_game_dir(game):
            messagebox.showerror("Game folder", "Set a valid Warlock installation folder first.")
            return
        self.scan = scan_game(game, MODS_ROOT)
        self.installed_tree.delete(*self.installed_tree.get_children())
        for p in self.scan.all_packs:
            kind = "vanilla" if p.vanilla else "mod"
            self.installed_tree.insert("", "end", iid=p.name, values=(f"{p.name}  [{kind}]", str(len(p.files))))
        self.avail_tree.delete(*self.avail_tree.get_children())
        for b in self.scan.available_mods:
            self.avail_tree.insert("", "end", iid=b.name, values=(b.name, str(len(b.packs))))
        self.pack_name_var.set(suggest_pack_name(game))
        mods_n = len(self.scan.installed_mods)
        avail_n = len(self.scan.available_mods)
        self.log_msg(f"Scan complete: {mods_n} installed mod pack(s), {avail_n} bundle(s) in mods folder.")

    def _on_avail_select(self, _evt=None) -> None:
        if not self.scan:
            return
        sel = self.avail_tree.selection()
        if not sel:
            return
        name = sel[0]
        for b in self.scan.available_mods:
            if b.name == name:
                self.notes.delete("1.0", "end")
                self.notes.insert("1.0", b.notes or "(no description file)")
                break

    def install_selected_bundle(self) -> None:
        if not self.scan:
            return
        sel = self.avail_tree.selection()
        if not sel:
            messagebox.showinfo("Install", "Select a mod in the mods folder list.")
            return
        name = sel[0]
        bundle = next(b for b in self.scan.available_mods if b.name == name)
        install_packs(bundle.packs, self.scan.game_dir, self.log_msg)
        self.refresh_scan()
        messagebox.showinfo("Installed", f"Copied {len(bundle.packs)} pack(s) into the game folder.")

    def uninstall_selected(self) -> None:
        if not self.scan:
            return
        sel = self.installed_tree.selection()
        if not sel:
            return
        names = [iid for iid in sel if iid.lower() not in VANILLA_PACKS]
        skipped = [iid for iid in sel if iid.lower() in VANILLA_PACKS]
        if skipped:
            messagebox.showwarning("Vanilla", "Vanilla packs will not be deleted: " + ", ".join(skipped))
        if not names:
            return
        if not messagebox.askyesno("Uninstall", "Remove these pack files from the game folder?\n" + "\n".join(names)):
            return
        uninstall_packs(names, self.scan.game_dir, self.log_msg)
        self.refresh_scan()

    def hint_empty(self) -> None:
        messagebox.showinfo(
            "New mod",
            "Load merged or vanilla data first, edit only the files you care about, "
            "then when repacking you can choose to pack just the files you changed.\n\n"
            "Use 'New mod from vanilla only' for a clean base without other mods.",
        )

    def _run_bg(self, fn) -> None:
        if self._busy:
            messagebox.showinfo("Busy", "A pack operation is already running.")
            return
        self._busy = True

        def wrap() -> None:
            try:
                fn()
            except Exception as exc:
                self.log_msg(f"ERROR: {exc}")
                self.after(0, lambda: messagebox.showerror("Error", str(exc)))
            finally:
                self._busy = False

        threading.Thread(target=wrap, daemon=True).start()

    def unpack_selected_installed(self) -> None:
        if not self.scan:
            return
        sel = self.installed_tree.selection()
        if not sel:
            return
        paths = [os.path.join(self.scan.game_dir, iid) for iid in sel]
        self._run_bg(lambda: self._load_packs(paths, os.path.join(WORK_ROOT, "unpacked_pack"), only_editable=False))

    def unpack_selected_bundle(self) -> None:
        if not self.scan:
            return
        sel = self.avail_tree.selection()
        if not sel:
            return
        bundle = next(b for b in self.scan.available_mods if b.name == sel[0])
        dest = os.path.join(WORK_ROOT, bundle.name)
        self._run_bg(lambda: self._load_packs(bundle.packs, dest, only_editable=False))

    def load_merged(self) -> None:
        if not self.scan:
            self.refresh_scan()
        if not self.scan:
            return
        paths = [p.path for p in self.scan.all_packs]
        dest = os.path.join(WORK_ROOT, "merged_all")
        self._run_bg(lambda: self._load_packs(paths, dest, only_editable=True))

    def new_from_vanilla(self) -> None:
        if not self.scan:
            self.refresh_scan()
        if not self.scan:
            return
        paths = [p.path for p in self.scan.vanilla_packs]
        dest = os.path.join(WORK_ROOT, "new_mod_vanilla")
        self._run_bg(lambda: self._load_packs(paths, dest, only_editable=True))

    def _load_packs(self, paths: List[str], dest: str, only_editable: bool) -> None:
        self.log_msg("Merging packs…")
        merged = merged_entries(paths, only_editable=only_editable, log=self.log_msg)
        self.log_msg(f"Converting {len(merged)} files to editable form…")
        manifest = write_workspace(dest, merged, convert_txml=True, log=self.log_msg)
        self.workspace_dir = dest
        self.manifest = manifest
        self.current_orig = None
        self.tree_xml = None
        self.after(0, self.rebuild_file_tree)
        self.log_msg(f"Workspace ready: {dest}")

    def rebuild_file_tree(self) -> None:
        self.file_tree.delete(*self.file_tree.get_children())
        if not self.manifest:
            return
        needle = self.filter_var.get().strip().lower()
        cats: Dict[str, List[str]] = {}
        labels: Dict[str, str] = {}
        for orig in self.manifest:
            cid, label = category_for(orig)
            labels[cid] = label
            if needle and needle not in orig.lower() and needle not in label.lower():
                continue
            cats.setdefault(cid, []).append(orig)
        order = [c[0] for c in CATEGORIES] + ["assets", "models", "audio_files", "other"]
        seen = set()
        for cid in order + list(cats):
            if cid in seen or cid not in cats:
                continue
            seen.add(cid)
            parent = self.file_tree.insert("", "end", iid=f"cat:{cid}", text=f"{labels.get(cid, cid)} ({len(cats[cid])})")
            for orig in sorted(cats[cid], key=str.lower):
                self.file_tree.insert(parent, "end", iid=orig, text=orig)

    def _on_file_select(self, _evt=None) -> None:
        sel = self.file_tree.selection()
        if not sel:
            return
        iid = sel[0]
        if iid.startswith("cat:"):
            return
        self.open_file(iid)

    def save_current(self) -> None:
        if not self.current_orig or not self.workspace_dir:
            return
        path = self.manifest[self.current_orig]
        if path.lower().endswith(".xml") and self.tree_xml is not None:
            if self.nb.index(self.nb.select()) == 1:
                self.apply_raw(silent=True)
            write_xml_file(self.tree_xml, path)
        else:
            text = self.raw.get("1.0", "end-1c")
            with open(path, "w", encoding="utf-8", newline="\n") as f:
                f.write(text)
        self.dirty = False
        self.log_msg(f"Saved {os.path.basename(path)}")

    def open_file(self, orig: str) -> None:
        if self.dirty:
            if messagebox.askyesno("Unsaved", "Save changes to the current file first?"):
                self.save_current()
        self.current_orig = orig
        path = self.manifest[orig]
        self.form_clear()
        self.xml_tree.delete(*self.xml_tree.get_children())
        self.iid_to_node.clear()
        self.iid_to_parent.clear()
        self.raw.delete("1.0", "end")
        if path.lower().endswith(".xml"):
            try:
                self.tree_xml = parse_xml_file(path)
            except Exception as exc:
                messagebox.showerror("XML", str(exc))
                return
            self._fill_xml_tree("", self.tree_xml.getroot(), None)
            self.raw.insert("1.0", open(path, encoding="utf-8").read())
            self.nb.select(0)
        else:
            self.tree_xml = None
            try:
                text = open(path, encoding="utf-8", errors="replace").read()
            except OSError:
                text = ""
            self.raw.insert("1.0", text)
            self.nb.select(1)
        self.dirty = False
        cat = category_for(orig)[1]
        self.log_msg(f"Editing {orig}  —  {cat}")

    def _fill_xml_tree(self, parent_iid: str, node: ET.Element, parent_node: Optional[ET.Element]) -> None:
        iid = f"n{len(self.iid_to_node)}"
        self.iid_to_node[iid] = node
        self.iid_to_parent[iid] = parent_node
        self.xml_tree.insert(parent_iid, "end", iid=iid, text=node_label(node))
        for child in node:
            self._fill_xml_tree(iid, child, node)

    def _on_xml_select(self, _evt=None) -> None:
        sel = self.xml_tree.selection()
        if not sel:
            return
        node = self.iid_to_node.get(sel[0])
        if node is None:
            return
        self.form_clear()
        ttk.Label(self.form, text=f"Tag: {node.tag}").pack(anchor="w", padx=6, pady=4)
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
        if is_value_node(node):
            ttk.Label(self.form, text="This is a typed game value (TXML). Changing type/value writes back into the binary on pack.").pack(
                anchor="w", padx=6, pady=8
            )

    def _attr_changed(self, node: ET.Element, key: str) -> None:
        var = self.form_vars.get(key)
        if var is None:
            return
        node.set(key, var.get())
        self.dirty = True
        sel = self.xml_tree.selection()
        if sel:
            self.xml_tree.item(sel[0], text=node_label(node))

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
            label = self.xml_tree.item(iid, "text")
            if needle in str(label).lower():
                self.xml_tree.see(iid)
                self.xml_tree.selection_set(iid)
                self.xml_tree.focus(iid)
                self._on_xml_select()
                return
        messagebox.showinfo("Find", f"No match for '{needle}'.")

    def form_clear(self) -> None:
        for w in self.form.winfo_children():
            w.destroy()
        self.form_vars.clear()

    def _selected_xml(self):
        sel = self.xml_tree.selection()
        if not sel:
            return None, None, None
        iid = sel[0]
        return iid, self.iid_to_node[iid], self.iid_to_parent[iid]

    def dup_node(self) -> None:
        iid, node, parent = self._selected_xml()
        if node is None or parent is None:
            messagebox.showinfo("Duplicate", "Select a child node (not the document root).")
            return
        clone = duplicate_node(parent, node)
        self.dirty = True
        self._reload_tree_keep(clone)

    def del_node(self) -> None:
        iid, node, parent = self._selected_xml()
        if node is None or parent is None:
            return
        if not messagebox.askyesno("Delete", f"Delete {node.tag}?"):
            return
        delete_node(parent, node)
        self.dirty = True
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
        self.dirty = True
        self._reload_tree_keep(target)

    def add_group(self) -> None:
        iid, node, parent = self._selected_xml()
        if node is None:
            return
        tag = simpledialog.askstring("Group name", "XML tag for the new group (e.g. Perks)")
        if not tag:
            return
        add_container_child(node, tag)
        self.dirty = True
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
        from io import StringIO
        # reuse serializer via write to temp string through xmlmodel
        import tempfile

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
        if self.current_orig and self.manifest.get(self.current_orig, "").lower().endswith(".xml"):
            try:
                root = ET.fromstring(text)
            except ET.ParseError as exc:
                if not silent:
                    messagebox.showerror("XML parse", str(exc))
                return
            self.tree_xml = ET.ElementTree(root)
            self.dirty = True
            self.xml_tree.delete(*self.xml_tree.get_children())
            self.iid_to_node.clear()
            self.iid_to_parent.clear()
            self._fill_xml_tree("", root, None)
            if not silent:
                self.log_msg("Raw XML applied to the structured tree.")
        else:
            self.dirty = True

    def _files_to_pack(self) -> Optional[List[str]]:
        if not self.manifest:
            messagebox.showinfo("Pack", "Load or unpack a workspace first.")
            return None
        sel = self.file_tree.selection()
        names: List[str] = []
        for iid in sel:
            if iid.startswith("cat:"):
                for child in self.file_tree.get_children(iid):
                    names.append(child)
            elif iid in self.manifest:
                names.append(iid)
        if not names:
            if not messagebox.askyesno(
                "Pack all",
                "No files selected in the category list. Pack the entire workspace?",
            ):
                return None
            names = list(self.manifest.keys())
        return names

    def repack_workspace(self) -> None:
        names = self._files_to_pack()
        if names is None or not self.workspace_dir or not self.scan:
            return
        self.save_current()
        out_name = self.pack_name_var.get().strip() or suggest_pack_name(self.scan.game_dir)
        if not out_name.lower().endswith(".pack"):
            out_name += ".pack"
        dest = os.path.join(self.workspace_dir, "..", "built")
        dest = os.path.normpath(dest)
        os.makedirs(dest, exist_ok=True)
        pack_path = os.path.join(dest, out_name)

        def work() -> None:
            build_pack_from_workspace(self.workspace_dir, pack_path, names, self.log_msg)
            self.after(0, lambda: messagebox.showinfo("Packed", f"Wrote {pack_path}"))

        self._run_bg(work)

    def repack_and_install(self) -> None:
        names = self._files_to_pack()
        if names is None or not self.workspace_dir or not self.scan:
            return
        self.save_current()
        out_name = self.pack_name_var.get().strip() or suggest_pack_name(self.scan.game_dir)
        if not out_name.lower().endswith(".pack"):
            out_name += ".pack"
        dest = os.path.normpath(os.path.join(self.workspace_dir, "..", "built"))
        os.makedirs(dest, exist_ok=True)
        pack_path = os.path.join(dest, out_name)
        game = self.scan.game_dir

        def work() -> None:
            build_pack_from_workspace(self.workspace_dir, pack_path, names, self.log_msg)
            install_packs([pack_path], game, self.log_msg)
            self.after(0, self.refresh_scan)
            self.after(0, lambda: messagebox.showinfo("Installed", f"Installed {out_name} into the game folder."))

        self._run_bg(work)


def main() -> None:
    os.makedirs(WORK_ROOT, exist_ok=True)
    app = ModManagerApp()
    app.mainloop()


if __name__ == "__main__":
    main()
