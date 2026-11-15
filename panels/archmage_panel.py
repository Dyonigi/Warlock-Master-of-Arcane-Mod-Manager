"""Warlock Mod Manager — tab Archmages: modifica/creazione degli archmage (FractionData) e degli
Improvements di fractions.binary, con i testi in locdata e la piccola icona in c_icons.gfx.

Per un archmage nuovo:
  1. si scrive il FractionData in coda a fractions.binary;
  2. si creano le chiavi locdata MAGE_<systemName> e MAGE_<systemName>_DESC con i testi inseriti;
  3. si aggiunge in c_icons.gfx il frame della piccola icona (label = systemName) che riusa il
     ritratto scelto (le immagini nuove non sono ancora supportate).
"""

from __future__ import annotations

import copy
import os
import tkinter as tk
from tkinter import messagebox, ttk
from typing import Callable, Dict, List, Optional, Set, Tuple

import archmage_schema as am
from gfx_icons import GfxError, GfxIcons
from panels.archmage_dialog import ArchmageDialog, ImprovementDialog
from services import archmage_service as ars
from services import icon_service as ics
from services import locdata_service as ls
from services import perk_service as pks
from theme import ACCENT, MUTED

Noop = lambda *_a, **_k: None  # noqa: E731


def _sprite_with_labels(gfx: GfxIcons, labels: Set[str]) -> Optional[int]:
    """Sprite che contiene il maggior numero delle label date."""
    best, best_n = None, 0
    for sp in sorted(gfx.sprites.values(), key=lambda s: s.id):
        n = sum(1 for f in sp.frames if f.label in labels)
        if n > best_n:
            best, best_n = sp.id, n
    return best


class ArchmagePanel(ttk.Frame):
    def __init__(
        self,
        parent: tk.Misc,
        *,
        get_scan: Callable[[], Optional[object]],
        get_workspace: Callable[[], Tuple[Optional[str], Dict[str, str]]],
        get_gfx: Callable[[], Optional[GfxIcons]],
        get_pack_paths: Callable[[], List[str]],
        assign_icons: Callable[[Dict[str, Tuple[int, int]]], str],
        on_saved: Callable[[], None],
        log: Callable[[str], None],
        before_write: Callable[[str], None] = Noop,
        after_write: Callable[[str], None] = Noop,
    ) -> None:
        super().__init__(parent)
        self._get_scan, self._get_workspace = get_scan, get_workspace
        self._get_gfx, self._get_pack_paths = get_gfx, get_pack_paths
        self._assign_icons, self._on_saved, self._log = assign_icons, on_saved, log
        self._before, self._after = before_write, after_write
        self._info = ars.FractionsInfo()
        self._names: Dict[str, str] = {}
        self._atlas_cache: Dict[str, object] = {}
        self.status_var = tk.StringVar(value="")
        self._build()

    # ------------------------------------------------------------------
    # UI
    # ------------------------------------------------------------------
    def _build(self) -> None:
        top = ttk.Frame(self)
        top.pack(fill="x", padx=6, pady=6)
        ttk.Button(top, text="Ricarica", command=self.on_show).pack(side="left")
        ttk.Label(top, textvariable=self.status_var, foreground=MUTED, wraplength=900, justify="left").pack(
            side="left", padx=10)
        nb = ttk.Notebook(self)
        nb.pack(fill="both", expand=True, padx=6, pady=(0, 6))
        a_tab, i_tab = ttk.Frame(nb), ttk.Frame(nb)
        nb.add(a_tab, text="Archmages")
        nb.add(i_tab, text="Improvements")

        self.a_tree = self._tree(a_tab, (("sys", "systemName", 170), ("name", "Nome", 200), ("race", "race", 80),
                                         ("icon", "Ritratto", 120), ("n", "Impr.", 50), ("dlc", "dlc", 40)))
        self.a_tree.bind("<Double-1>", lambda _e: self._edit_archmage())
        self._buttons(a_tab, (("Nuovo archmage…", self._new_archmage, True), ("Modifica…", self._edit_archmage, False),
                              ("Duplica…", self._dup_archmage, False)))
        self.i_tree = self._tree(i_tab, (("name", "Improvement", 260), ("cost", "costo", 50), ("perk", "perk", 200),
                                         ("sp", "spells", 50), ("users", "archmage", 60), ("dlc", "dlc", 40)))
        self.i_tree.bind("<Double-1>", lambda _e: self._edit_improvement())
        self._buttons(i_tab, (("Nuovo improvement…", self._new_improvement, True), ("Modifica…", self._edit_improvement, False),
                              ("Duplica…", self._dup_improvement, False)))

    @staticmethod
    def _tree(parent: tk.Misc, cols) -> ttk.Treeview:
        f = ttk.Frame(parent)
        f.pack(fill="both", expand=True, padx=4, pady=4)
        t = ttk.Treeview(f, columns=[c[0] for c in cols], show="headings", selectmode="browse")
        for key, title, width in cols:
            t.heading(key, text=title)
            t.column(key, width=width, anchor="w")
        sb = ttk.Scrollbar(f, orient="vertical", command=t.yview)
        t.configure(yscrollcommand=sb.set)
        t.pack(side="left", fill="both", expand=True)
        sb.pack(side="right", fill="y")
        return t

    @staticmethod
    def _buttons(parent: tk.Misc, items) -> None:
        row = ttk.Frame(parent)
        row.pack(fill="x", padx=4, pady=(0, 6))
        for text, cmd, accent in items:
            ttk.Button(row, text=text, command=cmd, style="Accent.TButton" if accent else "TButton").pack(
                side="left", padx=2)

    # ------------------------------------------------------------------
    # File e testi
    # ------------------------------------------------------------------
    def _file(self, quiet: bool = False) -> Optional[str]:
        _ws, manifest = self._get_workspace()
        path = ars.fractions_path(manifest or {})
        if not path or not os.path.isfile(path):
            if not quiet:
                messagebox.showinfo("Archmages", "Carica prima un workspace che contenga fractions.binary "
                                                 "(per esempio 'Load merged game data').")
            return None
        return path

    def _loc_data(self) -> Optional[bytes]:
        _ws, manifest = self._get_workspace()
        try:
            return ls.read_current(manifest or {}, self._get_pack_paths())
        except Exception as exc:
            self._log(f"locdata non letto: {exc}")
            return None

    def on_show(self) -> None:
        path = self._file(quiet=True)
        self._info = ars.FractionsInfo()
        if not path:
            self.status_var.set("Carica un workspace con fractions.binary (es. 'Load merged game data').")
            self._refresh()
            return
        try:
            self._info = ars.read_info(path)
        except Exception as exc:
            self.status_var.set(f"fractions.binary non letto: {type(exc).__name__}: {exc}")
            self._refresh()
            return
        data = self._loc_data()
        keys = [a.loc_name_key for a in self._info.archmages]
        self._names = {k: (v or "") for k, v in ls.get_texts(data, keys).items()} if data else {}
        self.status_var.set(f"{len(self._info.archmages)} archmage · {len(self._info.improvements)} improvements")
        self._refresh()

    def _refresh(self) -> None:
        for t in (self.a_tree, self.i_tree):
            t.delete(*t.get_children())
        users: Dict[str, int] = {}
        for a in self._info.archmages:
            for i in a.improvements:
                users[i] = users.get(i, 0) + 1
            self.a_tree.insert("", "end", iid=a.system_name, values=(
                a.system_name, self._names.get(a.loc_name_key, ""), a.race, a.character_icon,
                len(a.improvements), a.dlc_id or ""))
        for i in self._info.improvements:
            self.i_tree.insert("", "end", iid=i.name, values=(
                i.name, i.cost, i.perk, len(i.spells), users.get(i.name, 0), i.dlc_id or ""))

    def _write(self, orig: str, fn):
        """Scrittura con i hook verso l'editor del manager (salva prima / ricarica dopo)."""
        self._before(orig)
        try:
            return fn()
        finally:
            self._after(orig)

    # ------------------------------------------------------------------
    # Ritratti (c_icons.gfx)
    # ------------------------------------------------------------------
    def _portrait_sprite(self, gfx: GfxIcons) -> Optional[int]:
        return _sprite_with_labels(gfx, {a.character_icon for a in self._info.archmages})

    def _small_sprite(self, gfx: GfxIcons) -> Optional[int]:
        return _sprite_with_labels(gfx, {a.system_name for a in self._info.archmages})

    def _portrait_labels(self, gfx: Optional[GfxIcons]) -> List[str]:
        if gfx is None:
            return sorted({a.character_icon for a in self._info.archmages})
        sid = self._portrait_sprite(gfx)
        labels = [f.label for f in gfx.sprites[sid].frames if f.label] if sid is not None else []
        return sorted(set(labels) | {a.character_icon for a in self._info.archmages}, key=str.lower)

    def _portrait_image(self, gfx: Optional[GfxIcons], label: str):
        if gfx is None or not label:
            return None
        fr = gfx.labels().get(label)
        sh = gfx.shapes.get(fr.char) if fr is not None and fr.char is not None else None
        if sh is None or not sh.bitmaps or sh.bitmaps[0] not in gfx.atlases:
            return None
        name = gfx.atlases[sh.bitmaps[0]].filename
        if name not in self._atlas_cache:
            try:
                self._atlas_cache[name] = ics.load_atlas_image(self._get_pack_paths(), name)
            except Exception:
                self._atlas_cache[name] = None
        return self._atlas_cache[name]

    def _small_icon_assignment(self, gfx: Optional[GfxIcons], a: am.Archmage) -> Optional[Dict[str, Tuple[int, int]]]:
        """Frame della piccola icona (label = systemName) che riusa il ritratto scelto."""
        if gfx is None:
            return None
        if a.system_name in gfx.labels():
            return {}
        small = self._small_sprite(gfx)
        port = gfx.labels().get(a.character_icon)
        if small is None or port is None or port.char not in gfx.shapes:
            return None
        bmp = gfx.shapes[port.char].bitmaps[:1]
        for f in gfx.sprites[small].frames:
            if f.label and f.char in gfx.shapes and gfx.shapes[f.char].bitmaps[:1] == bmp:
                return {a.system_name: (f.char, small)}
        alt = gfx.labels().get("f_" + a.character_icon)
        if alt is not None and alt.char in gfx.shapes:
            return {a.system_name: (alt.char, small)}
        return None

    # ------------------------------------------------------------------
    # Archmages
    # ------------------------------------------------------------------
    def _selected(self, tree: ttk.Treeview, what: str) -> Optional[str]:
        sel = tree.selection()
        if not sel:
            messagebox.showinfo("Archmages", f"Seleziona prima {what} nella lista.")
            return None
        return sel[0]

    def _new_archmage(self, template: Optional[am.Archmage] = None) -> None:
        self._open_archmage(template, is_new=True)

    def _edit_archmage(self) -> None:
        name = self._selected(self.a_tree, "un archmage")
        if name:
            self._open_archmage(next(a for a in self._info.archmages if a.system_name == name), is_new=False)

    def _dup_archmage(self) -> None:
        name = self._selected(self.a_tree, "un archmage")
        if not name:
            return
        a = copy.deepcopy(next(x for x in self._info.archmages if x.system_name == name))
        a.system_name = name + "_copy"
        a.name_key = "#mage_" + a.system_name
        a.predefined = True
        a.dlc_id = 0
        self._open_archmage(a, is_new=True, texts_from=name)

    def _open_archmage(self, a: Optional[am.Archmage], *, is_new: bool, texts_from: Optional[str] = None) -> None:
        path = self._file()
        if not path:
            return
        self._before("fractions.binary")
        try:
            self._info = ars.read_info(path)
        except Exception as exc:
            messagebox.showerror("Archmages", f"fractions.binary non letto: {exc}")
            return
        gfx = self._get_gfx()
        portraits = self._portrait_labels(gfx)
        if a is None:
            first = self._info.archmages[0] if self._info.archmages else am.Archmage()
            a = am.Archmage(race=first.race, character_icon=portraits[0] if portraits else "",
                            personality=list(first.personality), fr_version=first.fr_version,
                            ud_version=first.ud_version, selected_color=first.selected_color)
        src = next((x for x in self._info.archmages if x.system_name == (texts_from or a.system_name)), None)
        data = self._loc_data()
        name_text = desc_text = ""
        if src is not None and data:
            t = ls.get_texts(data, [src.loc_name_key, src.loc_desc_key])
            name_text, desc_text = t[src.loc_name_key] or "", t[src.loc_desc_key] or ""
        orig_name, orig_desc = name_text, desc_text

        def save(new: am.Archmage, name: str, desc: str) -> None:
            self._save_archmage(path, new, name, desc, is_new, orig_name, orig_desc, gfx)

        ArchmageDialog(
            self, info=self._info, archmage=a, is_new=is_new,
            title="Nuovo archmage" if is_new else f"Modifica archmage: {a.system_name}",
            portraits=portraits, portrait_image=lambda lab: self._portrait_image(gfx, lab),
            name_text=name_text, desc_text=desc_text, on_save=save)

    def _save_archmage(self, path: str, a: am.Archmage, name: str, desc: str, is_new: bool,
                       orig_name: str, orig_desc: str, gfx: Optional[GfxIcons]) -> None:
        ws, manifest = self._get_workspace()
        if not ws:
            raise am.ArchmageError("Nessun workspace caricato.")
        pairs: Dict[str, str] = {}
        if is_new:
            data = self._loc_data()
            existing = ls.get_texts(data, [a.loc_name_key, a.loc_desc_key]) if data else {}
            dup = [k for k, v in existing.items() if v is not None]
            if dup:
                raise am.ArchmageError(f"Le chiavi locdata esistono già ({', '.join(dup)}): scegli un altro systemName.")
            pairs = {a.loc_name_key: name, a.loc_desc_key: desc}
        else:
            if name != orig_name:
                pairs[a.loc_name_key] = name
            if desc and desc != orig_desc:
                pairs[a.loc_desc_key] = desc
        icon_assign = self._small_icon_assignment(gfx, a) if is_new else {}
        notes: List[str] = []
        if is_new and icon_assign is None:
            notes.append("nessuna piccola icona trovata per il ritratto scelto: l'archmage non ne avrà una")
            icon_assign = {}

        # prima ciò che è innocuo se il resto fallisce (frame e testi inutilizzati), per ultimo il file dati
        if icon_assign:
            self._assign_icons(icon_assign)
            notes.append("piccola icona aggiunta a c_icons.gfx")
        if pairs:
            self._write("locdata.md", lambda: ls.write_texts(ws, manifest, self._get_pack_paths(), pairs, self._log))
            notes.append("testi scritti nel locdata")
        if is_new:
            self._write("fractions.binary", lambda: ars.add_archmage(path, a))
        else:
            self._write("fractions.binary", lambda: ars.update_archmage(path, a))
        self._on_saved()
        self.on_show()
        self.status_var.set(f"Archmage {a.system_name} {'aggiunto' if is_new else 'modificato'}"
                            + (f" ({'; '.join(notes)})" if notes else "") + ". Ora fai il repack del workspace.")
        self._log(f"Archmage {a.system_name} {'aggiunto' if is_new else 'modificato'}: {'; '.join(notes) or 'solo fractions.binary'}")

    # ------------------------------------------------------------------
    # Improvements
    # ------------------------------------------------------------------
    def _perk_names(self) -> List[str]:
        _ws, manifest = self._get_workspace()
        path = pks.perks_path(manifest or {})
        if path and os.path.isfile(path):
            try:
                return sorted(pks.read_info(path)[0], key=str.lower)
            except Exception:
                pass
        return sorted({i.perk for i in self._info.improvements if i.perk})

    def _new_improvement(self, template: Optional[am.Improvement] = None) -> None:
        self._open_improvement(template or am.Improvement(), is_new=True)

    def _edit_improvement(self) -> None:
        name = self._selected(self.i_tree, "un improvement")
        if name:
            self._open_improvement(next(i for i in self._info.improvements if i.name == name), is_new=False)

    def _dup_improvement(self) -> None:
        name = self._selected(self.i_tree, "un improvement")
        if not name:
            return
        i = copy.deepcopy(next(x for x in self._info.improvements if x.name == name))
        i.name = name + "_copy"
        self._new_improvement(i)

    def _open_improvement(self, imp: am.Improvement, *, is_new: bool) -> None:
        path = self._file()
        if not path:
            return
        self._before("fractions.binary")
        try:
            self._info = ars.read_info(path)
        except Exception as exc:
            messagebox.showerror("Archmages", f"fractions.binary non letto: {exc}")
            return
        used = [a.system_name for a in self._info.archmages if imp.name in a.improvements]

        def save(new: am.Improvement) -> None:
            fn = (lambda: ars.add_improvement(path, new)) if is_new else (lambda: ars.update_improvement(path, new))
            self._write("fractions.binary", fn)
            self._on_saved()
            self.on_show()
            self.status_var.set(f"Improvement {new.name} {'aggiunto' if is_new else 'modificato'}. "
                                "Ora fai il repack del workspace.")
            self._log(f"Improvement {new.name} {'aggiunto' if is_new else 'modificato'} in fractions.binary.")

        ImprovementDialog(self, imp=imp, is_new=is_new,
                          title="Nuovo improvement" if is_new else f"Modifica improvement: {imp.name}",
                          perk_names=self._perk_names(), spells_seen=self._info.spells_seen, used_by=used,
                          on_save=save)
