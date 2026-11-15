#!/usr/bin/env python3
"""Warlock: Master of the Arcane — graphical mod manager."""

from __future__ import annotations

import os
import sys
import threading
import tkinter as tk
from tkinter import filedialog, messagebox, ttk
from typing import Dict, List, Optional, Tuple
import xml.etree.ElementTree as ET

# Allow running as a script from this folder
HERE = os.path.dirname(os.path.abspath(__file__))
if HERE not in sys.path:
    sys.path.insert(0, HERE)

from catalog import CATEGORIES, category_for
from detect import find_game_dir, is_game_dir
from panels.browser_panel import BrowserPanel
from panels.archmage_panel import ArchmagePanel
from panels.perk_icon_panel import PerkIconPanel
from panels.preview_panel import PreviewPanel
from panels.scan_panel import ScanPanel
from panels.workspace_panel import WorkspacePanel
from project import build_pack_from_workspace, install_packs, patch_locdata_in_l100, read_vanilla_locdata
from services import scan_service, workspace_service
from state import ModManagerState
from theme import BG, FG, MUTED, apply_theme
from txml import is_value_node
from xmlmodel import parse_xml_file, write_xml_file


MODS_ROOT = os.path.dirname(HERE)
WORK_ROOT = os.path.join(HERE, "work")


class ModManagerApp(tk.Tk):
    def __init__(self) -> None:
        super().__init__()
        self.title("Warlock Mod Manager")
        self.geometry("1280x820")
        self.minsize(960, 640)
        self.configure(bg=BG)
        try:
            self.state("zoomed")
        except tk.TclError:
            pass  # non-Windows: mantieni la geometry di default

        self.game_dir = tk.StringVar()
        self.status = tk.StringVar(value="Detecting game…")
        self.pack_name_var = tk.StringVar()

        self.state = ModManagerState()

        apply_theme(self)
        self._build()
        self.after(50, self.auto_detect)

    # ------------------------------------------------------------------
    # Build
    # ------------------------------------------------------------------
    def _build(self) -> None:
        top = ttk.Frame(self)
        top.pack(fill="x", padx=10, pady=8)
        ttk.Label(top, text="Game folder").pack(side="left")
        ttk.Entry(top, textvariable=self.game_dir).pack(side="left", fill="x", expand=True, padx=8)
        ttk.Button(top, text="Browse…", command=self.browse_game).pack(side="left", padx=2)
        ttk.Button(top, text="Detect", command=self.auto_detect).pack(side="left", padx=2)
        ttk.Button(top, text="Refresh", command=self.refresh_scan).pack(side="left", padx=2)

        # ---- Main horizontal split: left column + right editor ----
        paned = ttk.Panedwindow(self, orient="horizontal")
        paned.pack(fill="both", expand=True, padx=10, pady=(0, 6))
        self.after(100, lambda: self._set_main_sash(paned, 340))
        # Left column: scan on top, workspace below it
        left_column = ttk.Panedwindow(paned)
        paned.add(left_column, weight=0)

        self.scan_panel = ScanPanel(
            left_column,
            on_uninstall=self.uninstall_selected,
            on_unpack_installed=self.unpack_selected_installed,
            on_install_bundle=self.install_selected_bundle,
            on_unpack_bundle=self.unpack_selected_bundle,
            on_bundle_selected=self._on_bundle_selected,
        )
        left_column.add(self.scan_panel, weight=1)

        self.workspace_panel = WorkspacePanel(
            left_column,
            pack_name_var=self.pack_name_var,
            on_load_merged=self.load_merged,
            on_new_vanilla=self.new_from_vanilla,
            on_hint_empty=self.hint_empty,
            on_save_current=self.save_current,
            on_repack_workspace=self.repack_workspace,
            on_repack_and_install=self.repack_and_install,
        )
        left_column.add(self.workspace_panel, weight=0)
        self.after(150, lambda: self._snap_workspace_sash(left_column))

        # Right column: browser + preview notebook
        right = ttk.Frame(paned)
        paned.add(right, weight=1)

        editor = ttk.LabelFrame(right, text="What this data does — edit anything")
        editor.pack(fill="both", expand=True)
        self.nb = ttk.Notebook(editor)
        self.nb.pack(fill="both", expand=True)

        self.browser = BrowserPanel(
            self.nb,
            on_file_selected=self._on_file_selected_from_browser,
            on_dirty_changed=self._on_browser_dirty,
            on_jump_requested=self.jump_to_definition,
            localization_getter=lambda: self.state.localization,
        )
        self.nb.add(self.browser, text="Editor")

        self.preview_panel = PreviewPanel(self.nb)
        self.nb.add(self.preview_panel, text="Image preview")

        self.perk_icon_panel = PerkIconPanel(
            self.nb,
            get_scan=lambda: self.state.scan,
            get_workspace=lambda: (self.state.workspace_dir, self.state.manifest),
            on_saved=self.rebuild_file_tree,
            log=self.log_msg,
            before_perks_write=lambda: self._sync_before("perks.binary"),
            after_perks_write=lambda: self._sync_after("perks.binary"),
        )
        self.nb.add(self.perk_icon_panel, text="Perks")

        self.archmage_panel = ArchmagePanel(
            self.nb,
            get_scan=lambda: self.state.scan,
            get_workspace=lambda: (self.state.workspace_dir, self.state.manifest),
            get_gfx=lambda: self.perk_icon_panel.ensure_gfx(),
            get_pack_paths=lambda: [p.path for p in self.state.scan.all_packs] if self.state.scan else [],
            assign_icons=self.perk_icon_panel.assign_and_save,
            on_saved=self.rebuild_file_tree,
            log=self.log_msg,
            before_write=self._sync_before,
            after_write=self._sync_after,
        )
        self.nb.add(self.archmage_panel, text="Archmages")
        self.nb.bind("<<NotebookTabChanged>>", self._on_tab_changed)

        self.browser.set_filter_callback(self.rebuild_file_tree)

        bottom = ttk.Frame(self)
        bottom.pack(fill="x", padx=10, pady=(0, 8))
        ttk.Label(bottom, textvariable=self.status).pack(side="left")
        self.log = tk.Text(self, height=7, bg="#121118", fg=MUTED, insertbackground=FG, wrap="word")
        self.log.pack(fill="x", padx=10, pady=(0, 8))
    def _set_main_sash(self, paned: ttk.Panedwindow, x: int) -> None:
        try:
            paned.sashpos(0, x)
        except tk.TclError:
            pass
    def _snap_workspace_sash(self, paned: ttk.Panedwindow) -> None:
        try:
            # altezza richiesta dal WorkspacePanel
            h = self.workspace_panel.winfo_reqheight()
            total = paned.winfo_height()
            if h > 0 and total > h:
                paned.sashpos(0, total - h)
        except tk.TclError:
            pass
    # ------------------------------------------------------------------
    # Logging
    # ------------------------------------------------------------------
    def log_msg(self, msg: str) -> None:
        def _do() -> None:
            self.log.insert("end", msg + "\n")
            self.log.see("end")
            self.status.set(msg)

        self.after(0, _do)

    def _on_tab_changed(self, _evt=None) -> None:
        cur = self.nb.select()
        if cur == str(self.perk_icon_panel):
            self.perk_icon_panel.on_show()
        elif cur == str(self.archmage_panel):
            self.archmage_panel.on_show()

    def _sync_before(self, orig: str) -> None:
        """Un tab sta per leggere/scrivere il file `orig`: se è aperto nell'editor con modifiche
        non salvate, le salva prima, così non si perdono."""
        if self.state.current_orig == orig and self.state.dirty:
            self.save_current()

    def _sync_after(self, orig: str) -> None:
        """Ricarica `orig` nell'editor (altrimenti il repack lo riscriverebbe con la versione
        vecchia) e torna al tab da cui si stava lavorando."""
        if self.state.current_orig == orig:
            tab = self.nb.select()
            self.state.dirty = False
            self.open_file(orig)
            self.nb.select(tab)

    # ------------------------------------------------------------------
    # Game detection and scan
    # ------------------------------------------------------------------
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
                messagebox.showwarning(
                    "Not a game folder",
                    "That folder does not look like a Warlock install (Game.exe + .pack files).",
                )

    def refresh_scan(self) -> None:
        game = self.game_dir.get().strip()
        if not is_game_dir(game):
            messagebox.showerror("Game folder", "Set a valid Warlock installation folder first.")
            return
        self.state.scan = scan_service.rescan(game, MODS_ROOT)

        self.scan_panel.clear_installed()
        for p in self.state.scan.all_packs:
            kind = "vanilla" if p.vanilla else "mod"
            self.scan_panel.add_installed(p.name, f"{p.name}  [{kind}]", len(p.files))

        self.scan_panel.clear_available()
        for b in self.state.scan.available_mods:
            self.scan_panel.add_available(b.name, b.name, len(b.packs))

        self.pack_name_var.set(scan_service.next_output_pack_name(game))
        mods_n = len(self.state.scan.installed_mods)
        avail_n = len(self.state.scan.available_mods)
        self.log_msg(f"Scan complete: {mods_n} installed mod pack(s), {avail_n} bundle(s) in mods folder.")

    def _on_bundle_selected(self, name: str) -> None:
        if not self.state.scan:
            return
        for b in self.state.scan.available_mods:
            if b.name == name:
                self.scan_panel.set_notes(b.notes or "(no description file)")
                return

    def install_selected_bundle(self) -> None:
        if not self.state.scan:
            return
        sel = self.scan_panel.selected_available()
        if not sel:
            messagebox.showinfo("Install", "Select a mod in the mods folder list.")
            return
        bundle = next(b for b in self.state.scan.available_mods if b.name == sel[0])
        n = scan_service.install_bundle(bundle.packs, self.state.scan.game_dir, self.log_msg)
        self.refresh_scan()
        messagebox.showinfo("Installed", f"Copied {n} pack(s) into the game folder.")

    def uninstall_selected(self) -> None:
        if not self.state.scan:
            return
        sel = self.scan_panel.selected_installed()
        if not sel:
            return
        skipped = scan_service.skipped_vanilla(sel)
        if skipped:
            messagebox.showwarning("Vanilla", "Vanilla packs will not be deleted: " + ", ".join(skipped))
        removed = scan_service.uninstall(sel, self.state.scan.game_dir, self.log_msg)
        if not removed:
            return
        self.refresh_scan()

    def hint_empty(self) -> None:
        messagebox.showinfo(
            "New mod",
            "Load merged or vanilla data first, edit only the files you care about, "
            "then when repacking you can choose to pack just the files you changed.\n\n"
            "Use 'New mod from vanilla only' for a clean base without other mods.",
        )

    # ------------------------------------------------------------------
    # Background work
    # ------------------------------------------------------------------
    def _run_bg(self, fn) -> None:
        if self.state.busy:
            messagebox.showinfo("Busy", "A pack operation is already running.")
            return
        self.state.busy = True

        def wrap() -> None:
            try:
                fn()
            except Exception as exc:
                self.log_msg(f"ERROR: {exc}")
                self.after(0, lambda: messagebox.showerror("Error", str(exc)))
            finally:
                self.state.busy = False

        threading.Thread(target=wrap, daemon=True).start()

    def unpack_selected_installed(self) -> None:
        if not self.state.scan:
            return
        sel = self.scan_panel.selected_installed()
        if not sel:
            return
        paths = [os.path.join(self.state.scan.game_dir, iid) for iid in sel]
        self._run_bg(lambda: self._load_packs(paths, os.path.join(WORK_ROOT, "unpacked_pack"), only_editable=False))

    def unpack_selected_bundle(self) -> None:
        if not self.state.scan:
            return
        sel = self.scan_panel.selected_available()
        if not sel:
            return
        bundle = next(b for b in self.state.scan.available_mods if b.name == sel[0])
        dest = os.path.join(WORK_ROOT, bundle.name)
        self._run_bg(lambda: self._load_packs(bundle.packs, dest, only_editable=False))

    def load_merged(self) -> None:
        if not self.state.scan:
            self.refresh_scan()
        if not self.state.scan:
            return
        paths = [p.path for p in self.state.scan.all_packs]
        dest = os.path.join(WORK_ROOT, "merged_all")
        self._run_bg(lambda: self._load_packs(paths, dest, only_editable=True))

    def new_from_vanilla(self) -> None:
        if not self.state.scan:
            self.refresh_scan()
        if not self.state.scan:
            return
        paths = [p.path for p in self.state.scan.vanilla_packs]
        dest = os.path.join(WORK_ROOT, "new_mod_vanilla")
        self._run_bg(lambda: self._load_packs(paths, dest, only_editable=True))

    def _load_packs(self, paths: List[str], dest: str, only_editable: bool) -> None:
        self.log_msg("Merging packs…")
        manifest = workspace_service.load_workspace(paths, dest, only_editable=only_editable, log=self.log_msg)
        self.state.workspace_dir = dest
        self.state.manifest = manifest
        self.state.current_orig = None
        self.state.tree_xml = None

        if self.state.scan:
            self.state.localization = workspace_service.load_localization_from_pack(
                self.state.scan.game_dir, dest, log=self.log_msg
            )
        else:
            self.state.localization = {}

        self.after(0, self.rebuild_file_tree)
        self.after(0, self._index_workspace)
        self.log_msg(f"Workspace ready: {dest}")

    # ------------------------------------------------------------------
    # File tree
    # ------------------------------------------------------------------
    def rebuild_file_tree(self) -> None:
        if not self.state.manifest:
            self.browser.clear_file_tree()
            return
        needle = self.browser.filter_var.get().strip().lower()
        cats: Dict[str, List[str]] = {}
        labels: Dict[str, str] = {}
        for orig in self.state.manifest:
            cid, label = category_for(orig)
            labels[cid] = label
            if needle and needle not in orig.lower() and needle not in label.lower():
                continue
            cats.setdefault(cid, []).append(orig)
        order = [c[0] for c in CATEGORIES] + ["assets", "models", "audio_files", "other"]
        self.browser.populate_file_tree(cats, labels, order)

    def _on_file_selected_from_browser(self, orig: str) -> None:
        self.open_file(orig)

    def _on_browser_dirty(self) -> None:
        self.state.dirty = True

    # ------------------------------------------------------------------
    # File open / save
    # ------------------------------------------------------------------
    def save_current(self) -> None:
        if not self.state.current_orig or not self.state.workspace_dir:
            return
        path = self.state.manifest[self.state.current_orig]
        if path.lower().endswith(".xml") and self.browser.get_tree() is not None:
            if self.browser.is_raw_tab_active():
                self.browser.apply_raw(silent=True)
            write_xml_file(self.browser.get_tree(), path)
        elif self.browser.is_locdata_active():
            # locdata binario: va scritto come BYTE, mai come testo
            with open(path, "wb") as f:
                f.write(self.browser.get_locdata_bytes())
        else:
            text = self.browser.get_raw_text()
            with open(path, "w", encoding="utf-8", newline="\n") as f:
                f.write(text)
        self.state.dirty = False
        self.browser.mark_clean()
        if hasattr(self.browser, 'locdata_panel'):
             self.browser.locdata_panel.mark_clean()
        self.log_msg(f"Saved {os.path.basename(path)}")

    @staticmethod
    def _is_locdata(path: str) -> bool:
        try:
            with open(path, "rb") as f:
                return f.read(4) == b"mdmp"
        except OSError:
            return False

    def open_file(self, orig: str) -> None:
        if self.state.dirty:
            if messagebox.askyesno("Unsaved", "Save changes to the current file first?"):
                self.save_current()
        self.state.current_orig = orig
        path = self.state.manifest[orig]

        if path.lower().endswith(".xml"):
            try:
                tree = parse_xml_file(path)
            except Exception as exc:
                messagebox.showerror("XML", str(exc))
                return
            self.browser.show_root(orig, path, tree)
            self.nb.select(0)
        elif self._is_locdata(path):
            # locdata binario (magic "mdmp"): niente lettura come testo
            vanilla = read_vanilla_locdata(self.game_dir.get().strip())
            if vanilla is None:
                messagebox.showwarning(
                    "locdata",
                    "l100.pack non trovato: uso il file aperto come base (le modifiche non "
                    "saranno separate dal vanilla).",
                )
            self.browser.show_locdata(orig, path, vanilla=vanilla)
            self.nb.select(0) # Il selettore esterno del browser
        else:
            try:
                text = open(path, encoding="utf-8", errors="replace").read()
            except OSError:
                text = ""
            self.browser.show_raw_text(orig, path, text)
            self.nb.select(0)

        self.state.dirty = False

        if PreviewPanel.is_image_file(path):
            self.nb.select(1)
            self.after(50, lambda p=path: self.preview_panel.show_image(p))

        if self.state.pending_jump:
            value = self.state.pending_jump
            self.state.pending_jump = None
            self.after(20, lambda v=value: self.browser.focus_identity(v))

        cat = category_for(orig)[1]
        self.log_msg(f"Editing {orig}  —  {cat}")

    # ------------------------------------------------------------------
    # Cross-file reference navigation
    # ------------------------------------------------------------------
    def _index_workspace(self) -> None:
        self.state.workspace_index = workspace_service.build_reference_index(
            self.state.manifest, log=self.log_msg
        )

    def _resolve_reference(self, value: str) -> Optional[Tuple[str, ET.Element]]:
        for orig, idx in self.state.workspace_index.items():
            if value in idx:
                return orig, idx[value]
        return None

    def jump_to_definition(self, value: Optional[str] = None) -> None:
        if not value:
            return
        if not self.state.workspace_index:
            self._index_workspace()
        found = self._resolve_reference(value)
        if not found:
            messagebox.showinfo("Go to definition", f"No record declares '{value}'.")
            return
        target_orig, _target_node = found
        if target_orig != self.state.current_orig:
            self.state.pending_jump = value
            self.open_file(target_orig)
        else:
            self.browser.focus_identity(value)

    # ------------------------------------------------------------------
    # Packing
    # ------------------------------------------------------------------
    def _files_to_pack(self) -> Optional[List[str]]:
        if not self.state.manifest:
            messagebox.showinfo("Pack", "Load or unpack a workspace first.")
            return None
        sel = self.browser.file_tree.selection()
        names: List[str] = []
        for iid in sel:
            if iid.startswith("cat:"):
                for child in self.browser.file_tree.get_children(iid):
                    names.append(child)
            elif iid in self.state.manifest:
                names.append(iid)
        if not names:
            if not messagebox.askyesno("Pack all", "No files selected. Pack the entire workspace?"):
                return None
            names = list(self.state.manifest.keys())
        return names

    def repack_workspace(self) -> None:
        names = self._files_to_pack()
        if names is None or not self.state.workspace_dir or not self.state.scan:
            return
        self.save_current()
        out_name = self.pack_name_var.get().strip() or scan_service.next_output_pack_name(self.state.scan.game_dir)
        if not out_name.lower().endswith(".pack"):
            out_name += ".pack"
        dest = os.path.normpath(os.path.join(self.state.workspace_dir, "..", "built"))
        os.makedirs(dest, exist_ok=True)
        pack_path = os.path.join(dest, out_name)

        # locdata.md non va in un pack mod: il gioco lo legge da l100.pack
        # (si applica con "Repack & install").
        names = [n for n in names if n != "locdata.md"]
        if not names:
            messagebox.showinfo(
                "Pack",
                "locdata.md non va in un pack mod: usa 'Repack & install' per applicarlo a l100.pack.",
            )
            return

        def work() -> None:
            build_pack_from_workspace(self.state.workspace_dir, pack_path, names, self.log_msg)
            self.after(0, lambda: messagebox.showinfo("Packed", f"Wrote {pack_path}"))

        self._run_bg(work)

    def repack_and_install(self) -> None:
        names = self._files_to_pack()
        if names is None or not self.state.workspace_dir or not self.state.scan:
            return
        self.save_current()
        out_name = self.pack_name_var.get().strip() or scan_service.next_output_pack_name(self.state.scan.game_dir)
        if not out_name.lower().endswith(".pack"):
            out_name += ".pack"
        dest = os.path.normpath(os.path.join(self.state.workspace_dir, "..", "built"))
        os.makedirs(dest, exist_ok=True)
        pack_path = os.path.join(dest, out_name)
        game = self.state.scan.game_dir

        patch_loc = "locdata.md" in names
        pack_names = [n for n in names if n != "locdata.md"]

        def work() -> None:
            done: List[str] = []
            if patch_loc:
                if patch_locdata_in_l100(self.state.workspace_dir, game, self.log_msg):
                    done.append("locdata.md applicato a l100.pack (backup: l100.pack.bak)")
            if pack_names:
                build_pack_from_workspace(self.state.workspace_dir, pack_path, pack_names, self.log_msg)
                install_packs([pack_path], game, self.log_msg)
                done.append(f"installato {out_name}")
            self.after(0, self.refresh_scan)
            msg = "; ".join(done) if done else "Nessuna modifica applicata (vedi log)."
            self.after(0, lambda: messagebox.showinfo("Installed", msg))

        self._run_bg(work)


def main() -> None:
    os.makedirs(WORK_ROOT, exist_ok=True)
    app = ModManagerApp()
    app.mainloop()


if __name__ == "__main__":
    main()