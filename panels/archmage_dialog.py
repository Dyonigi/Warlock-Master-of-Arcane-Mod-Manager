"""Warlock Mod Manager — finestre modali per Archmages e Improvements."""

from __future__ import annotations

import copy
import tkinter as tk
from tkinter import messagebox, ttk
from typing import Callable, Dict, List, Optional
import xml.etree.ElementTree as ET

import archmage_schema as am
from panels.perk_dialog import _center, _make_modal, _xml_text
from services.archmage_service import FractionsInfo
from theme import ACCENT, BG, BG2, FG, MUTED

try:
    from PIL import ImageTk
except ImportError:  # pragma: no cover
    ImageTk = None


def _listbox(parent: tk.Misc, height: int = 12, width: int = 34) -> tk.Listbox:
    return tk.Listbox(parent, height=height, width=width, bg=BG2, fg=FG, selectbackground="#4a3f1f",
                      selectforeground=FG, relief="flat", exportselection=False, activestyle="none",
                      highlightthickness=0)


# ---------------------------------------------------------------------------
# Archmage
# ---------------------------------------------------------------------------

class ArchmageDialog(tk.Toplevel):
    def __init__(
        self,
        parent: tk.Misc,
        *,
        info: FractionsInfo,
        archmage: am.Archmage,
        is_new: bool,
        title: str,
        portraits: List[str],
        portrait_image: Callable[[str], Optional[object]],
        name_text: str,
        desc_text: str,
        on_save: Callable[[am.Archmage, str, str], None],
    ) -> None:
        super().__init__(parent)
        self.withdraw()
        self.title(title)
        self.configure(bg=BG)
        self.info, self.is_new, self._on_save = info, is_new, on_save
        self._portraits, self._portrait_image = portraits, portrait_image
        self._orig = copy.deepcopy(archmage)
        self._orig_name, self._orig_desc = name_text, desc_text
        self._costs = {i.name: i.cost for i in info.improvements}
        self._chosen: List[str] = list(archmage.improvements)
        self._photo = None
        self._build(archmage, name_text, desc_text)
        self.protocol("WM_DELETE_WINDOW", self.destroy)
        _center(self, parent, 860, 700)
        self.minsize(760, 560)
        _make_modal(self, parent)

    # ------------------------------------------------------------------
    def _build(self, a: am.Archmage, name_text: str, desc_text: str) -> None:
        btns = ttk.Frame(self)
        btns.pack(side="bottom", fill="x", padx=10, pady=10)
        ttk.Button(btns, text="Salva", style="Accent.TButton", command=self._save).pack(side="right", padx=4)
        ttk.Button(btns, text="Annulla", command=self.destroy).pack(side="right")

        nb = ttk.Notebook(self)
        nb.pack(fill="both", expand=True, padx=8, pady=(8, 0))
        tab1, tab2, tab3 = ttk.Frame(nb), ttk.Frame(nb), ttk.Frame(nb)
        nb.add(tab1, text="Archmage")
        nb.add(tab2, text="Improvements")
        nb.add(tab3, text="Anteprima XML")
        nb.bind("<<NotebookTabChanged>>", lambda _e: self._update_preview())
        self.preview = tk.Text(tab3, wrap="none", bg=BG2, fg=FG, relief="flat", state="disabled")
        self.preview.pack(fill="both", expand=True)

        # --- identità ---
        box = ttk.LabelFrame(tab1, text="Dati")
        box.pack(fill="x", padx=6, pady=6)
        box.columnconfigure(1, weight=1)
        self.sys_var = tk.StringVar(value=a.system_name)
        self.race_var = tk.StringVar(value=a.race)
        self.color_var = tk.StringVar(value=str(a.selected_color))
        self.pre_var = tk.BooleanVar(value=a.predefined)
        self.dlc_var = tk.StringVar(value=str(a.dlc_id))
        ttk.Label(box, text="systemName").grid(row=0, column=0, sticky="w", padx=6, pady=3)
        e = ttk.Entry(box, textvariable=self.sys_var)
        e.grid(row=0, column=1, sticky="ew", padx=6)
        if not self.is_new:
            e.state(["disabled"])
        self.keys_var = tk.StringVar()
        ttk.Label(box, textvariable=self.keys_var, foreground=MUTED).grid(row=1, column=1, sticky="w", padx=6)
        ttk.Label(box, text="race").grid(row=2, column=0, sticky="w", padx=6, pady=3)
        ttk.Combobox(box, textvariable=self.race_var, values=self.info.races).grid(row=2, column=1, sticky="ew", padx=6)
        ttk.Label(box, text="selectedColor").grid(row=3, column=0, sticky="w", padx=6, pady=3)
        ttk.Combobox(box, textvariable=self.color_var, values=[str(c) for c in self.info.colors], width=8).grid(
            row=3, column=1, sticky="w", padx=6)
        row = ttk.Frame(box)
        row.grid(row=4, column=0, columnspan=2, sticky="w", padx=6, pady=4)
        ttk.Checkbutton(row, text="predefined", variable=self.pre_var).pack(side="left", padx=(0, 16))
        ttk.Label(row, text="dlcId").pack(side="left")
        ttk.Spinbox(row, from_=0, to=99, textvariable=self.dlc_var, width=5).pack(side="left", padx=6)
        self.sys_var.trace_add("write", lambda *_: self._update_keys())

        # --- ritratto ---
        pbox = ttk.LabelFrame(tab1, text="Ritratto (characterIcon)")
        pbox.pack(fill="x", padx=6, pady=6)
        self.icon_var = tk.StringVar(value=a.character_icon)
        left = ttk.Frame(pbox)
        left.pack(side="left", fill="x", expand=True, padx=6, pady=6)
        ttk.Label(left, text="Immagine:").pack(anchor="w")
        ttk.Combobox(left, textvariable=self.icon_var, values=self._portraits).pack(fill="x", pady=4)
        ttk.Label(left, foreground=MUTED, wraplength=380, justify="left",
                  text="Si scelgono i ritratti già presenti in c_icons.gfx. Per un archmage nuovo il pannello "
                       "aggiunge da solo la piccola icona (systemName) che usa lo stesso ritratto.").pack(anchor="w")
        self.portrait_label = ttk.Label(pbox)
        self.portrait_label.pack(side="right", padx=10, pady=6)
        self.icon_var.trace_add("write", lambda *_: self._update_portrait())

        # --- testi locdata ---
        tbox = ttk.LabelFrame(tab1, text="Testi (locdata)")
        tbox.pack(fill="both", expand=True, padx=6, pady=6)
        tbox.columnconfigure(1, weight=1)
        self.name_var = tk.StringVar(value=name_text)
        ttk.Label(tbox, text="Nome").grid(row=0, column=0, sticky="w", padx=6, pady=3)
        ttk.Entry(tbox, textvariable=self.name_var).grid(row=0, column=1, sticky="ew", padx=6)
        ttk.Label(tbox, text="Descrizione").grid(row=1, column=0, sticky="nw", padx=6, pady=3)
        self.desc_text = tk.Text(tbox, height=5, wrap="word", bg=BG2, fg=FG, insertbackground=FG, relief="flat")
        self.desc_text.grid(row=1, column=1, sticky="nsew", padx=6, pady=3)
        self.desc_text.insert("1.0", desc_text)
        tbox.rowconfigure(1, weight=1)

        # --- personality ---
        qbox = ttk.LabelFrame(tab1, text="Personality")
        qbox.pack(fill="x", padx=6, pady=6)
        self.pers_vars: Dict[str, tk.StringVar] = {}
        self._pers_types: Dict[str, str] = {}
        for i, (tag, typ, val) in enumerate(a.personality):
            ttk.Label(qbox, text=f"{tag} ({typ})").grid(row=i // 2, column=(i % 2) * 2, sticky="w", padx=6, pady=2)
            v = tk.StringVar(value=val)
            self.pers_vars[tag] = v
            self._pers_types[tag] = typ
            ttk.Entry(qbox, textvariable=v, width=10).grid(row=i // 2, column=(i % 2) * 2 + 1, sticky="w", padx=6)

        # --- improvements ---
        tab2.columnconfigure(0, weight=1)
        tab2.columnconfigure(2, weight=1)
        tab2.rowconfigure(1, weight=1)
        ttk.Label(tab2, text="Disponibili").grid(row=0, column=0, sticky="w", padx=6, pady=(8, 0))
        ttk.Label(tab2, text="Scelti (in quest'ordine)").grid(row=0, column=2, sticky="w", padx=6, pady=(8, 0))
        self.avail = _listbox(tab2)
        self.avail.grid(row=1, column=0, sticky="nsew", padx=6, pady=4)
        mid = ttk.Frame(tab2)
        mid.grid(row=1, column=1, padx=4)
        for text, cmd in (("Aggiungi ▶", self._imp_add), ("◀ Rimuovi", self._imp_remove),
                          ("▲", lambda: self._imp_move(-1)), ("▼", lambda: self._imp_move(1))):
            ttk.Button(mid, text=text, command=cmd, width=11).pack(pady=3)
        self.chosen = _listbox(tab2)
        self.chosen.grid(row=1, column=2, sticky="nsew", padx=6, pady=4)
        self.avail.bind("<Double-1>", lambda _e: self._imp_add())
        self.chosen.bind("<Double-1>", lambda _e: self._imp_remove())
        self.filter_var = tk.StringVar()
        frow = ttk.Frame(tab2)
        frow.grid(row=2, column=0, sticky="ew", padx=6)
        ttk.Label(frow, text="Filtra:").pack(side="left")
        ttk.Entry(frow, textvariable=self.filter_var).pack(side="left", fill="x", expand=True, padx=4)
        self.filter_var.trace_add("write", lambda *_: self._refresh_imps())
        self.total_var = tk.StringVar()
        ttk.Label(tab2, textvariable=self.total_var, foreground=ACCENT).grid(row=2, column=2, sticky="w", padx=6)
        self._update_keys()
        self._refresh_imps()
        self._update_portrait()

    # ------------------------------------------------------------------
    def _update_keys(self) -> None:
        sysname = self.sys_var.get().strip()
        key = ("mage_" + sysname).upper()
        self.keys_var.set(f"Chiavi locdata: {key}  /  {key}_DESC" if sysname else "")

    def _update_portrait(self) -> None:
        img = self._portrait_image(self.icon_var.get().strip()) if self._portrait_image else None
        if img is None or ImageTk is None:
            self.portrait_label.configure(image="", text="(nessuna anteprima)")
            self._photo = None
            return
        im = img.copy()
        im.thumbnail((150, 192))
        self._photo = ImageTk.PhotoImage(im)
        self.portrait_label.configure(image=self._photo, text="")

    def _refresh_imps(self) -> None:
        needle = self.filter_var.get().strip().lower()
        self.avail.delete(0, "end")
        self._avail_names = [n for n in sorted(self._costs, key=str.lower)
                             if n not in self._chosen and (not needle or needle in n.lower())]
        for n in self._avail_names:
            self.avail.insert("end", f"{n}   ({self._costs[n]})")
        self.chosen.delete(0, "end")
        for n in self._chosen:
            self.chosen.insert("end", f"{n}   ({self._costs.get(n, '?')})")
        total = sum(self._costs.get(n, 0) for n in self._chosen)
        self.total_var.set(f"{len(self._chosen)} improvements · costo totale {total}")

    def _imp_add(self) -> None:
        for i in self.avail.curselection():
            self._chosen.append(self._avail_names[i])
        self._refresh_imps()

    def _imp_remove(self) -> None:
        for i in sorted(self.chosen.curselection(), reverse=True):
            del self._chosen[i]
        self._refresh_imps()

    def _imp_move(self, d: int) -> None:
        sel = self.chosen.curselection()
        if len(sel) != 1 or not 0 <= sel[0] + d < len(self._chosen):
            return
        i = sel[0]
        self._chosen[i], self._chosen[i + d] = self._chosen[i + d], self._chosen[i]
        self._refresh_imps()
        self.chosen.selection_set(i + d)

    # ------------------------------------------------------------------
    def _collect(self) -> am.Archmage:
        sysname = self.sys_var.get().strip()
        pers = []
        for tag, typ, _val in self._orig.personality:
            pers.append((tag, typ, self.pers_vars[tag].get()))
        return am.Archmage(
            system_name=sysname, race=self.race_var.get().strip(), character_icon=self.icon_var.get().strip(),
            selected_color=am._int(self.color_var.get(), "selectedColor"),
            name_key=self._orig.name_key if not self.is_new else "#mage_" + sysname,
            national=self._orig.national, cp=self._orig.cp, improvements=list(self._chosen),
            predefined=self.pre_var.get(), dlc_id=am._int(self.dlc_var.get(), "dlcId"),
            personality=pers, fr_version=self._orig.fr_version, ud_version=self._orig.ud_version,
        )

    def _update_preview(self) -> None:
        try:
            text = _xml_text(self._collect().to_element(set(self._costs)))
        except am.PerkError as exc:
            text = f"(anteprima non disponibile: {exc})"
        self.preview.configure(state="normal")
        self.preview.delete("1.0", "end")
        self.preview.insert("1.0", text)
        self.preview.configure(state="disabled")

    def _save(self) -> None:
        try:
            a = self._collect()
            a.to_element(set(self._costs))          # validazione
            name = self.name_var.get().strip()
            desc = self.desc_text.get("1.0", "end").strip()
            if self.is_new and (not name or not desc):
                raise am.ArchmageError("Per un archmage nuovo servono sia il nome sia la descrizione: "
                                       "vengono salvati nel locdata.")
            if not name:
                raise am.ArchmageError("Il nome non può essere vuoto.")
            self._on_save(a, name, desc)
        except am.PerkError as exc:
            messagebox.showerror("Archmage non valido", str(exc), parent=self)
            return
        except Exception as exc:
            messagebox.showerror("Salvataggio non riuscito", f"{type(exc).__name__}: {exc}", parent=self)
            return
        self.destroy()


# ---------------------------------------------------------------------------
# Improvement
# ---------------------------------------------------------------------------

class ImprovementDialog(tk.Toplevel):
    def __init__(
        self, parent: tk.Misc, *, imp: am.Improvement, is_new: bool, title: str, perk_names: List[str],
        spells_seen: List[str], used_by: List[str], on_save: Callable[[am.Improvement], None],
    ) -> None:
        super().__init__(parent)
        self.withdraw()
        self.title(title)
        self.configure(bg=BG)
        self.is_new, self._on_save = is_new, on_save
        self._spells: List[str] = list(imp.spells)
        self._spells_seen = spells_seen
        self._build(imp, perk_names, used_by)
        self.protocol("WM_DELETE_WINDOW", self.destroy)
        _center(self, parent, 560, 640)
        self.minsize(520, 520)
        _make_modal(self, parent)

    def _build(self, imp: am.Improvement, perk_names: List[str], used_by: List[str]) -> None:
        btns = ttk.Frame(self)
        btns.pack(side="bottom", fill="x", padx=10, pady=10)
        ttk.Button(btns, text="Salva", style="Accent.TButton", command=self._save).pack(side="right", padx=4)
        ttk.Button(btns, text="Annulla", command=self.destroy).pack(side="right")

        box = ttk.LabelFrame(self, text="Improvement")
        box.pack(fill="x", padx=10, pady=8)
        box.columnconfigure(1, weight=1)
        self.v: Dict[str, tk.StringVar] = {}

        def field(row: int, label: str, key: str, value, values: Optional[List[str]] = None, spin: bool = False,
                  disabled: bool = False) -> None:
            ttk.Label(box, text=label).grid(row=row, column=0, sticky="w", padx=6, pady=3)
            var = tk.StringVar(value=str(value))
            self.v[key] = var
            if values is not None:
                w = ttk.Combobox(box, textvariable=var, values=values)
            elif spin:
                w = ttk.Spinbox(box, from_=0, to=100000, textvariable=var, width=10)
            else:
                w = ttk.Entry(box, textvariable=var)
            w.grid(row=row, column=1, sticky="ew" if not spin else "w", padx=6)
            if disabled:
                w.state(["disabled"])

        field(0, "name", "name", imp.name, disabled=not self.is_new)
        field(1, "cost", "cost", imp.cost, spin=True)
        field(2, "gold", "gold", imp.gold, spin=True)
        field(3, "mana", "mana", imp.mana, spin=True)
        field(4, "perk", "perk", imp.perk, values=[""] + perk_names)
        field(5, "unitName", "unit_name", imp.unit_name)
        field(6, "resourceName", "resource_name", imp.resource_name)
        field(7, "dlcId", "dlc_id", imp.dlc_id, spin=True)
        field(8, "dlc", "dlc", imp.dlc)
        field(9, "Relation / godName", "god_name", imp.god_name)
        field(10, "Relation / relationDelta", "relation_delta", imp.relation_delta, spin=True)
        if used_by:
            ttk.Label(box, text=f"Usato da: {', '.join(used_by)}", foreground=MUTED, wraplength=480).grid(
                row=11, column=0, columnspan=2, sticky="w", padx=6, pady=4)

        sbox = ttk.LabelFrame(self, text="Spells")
        sbox.pack(fill="both", expand=True, padx=10, pady=8)
        self.spell_list = _listbox(sbox, height=6, width=40)
        self.spell_list.pack(fill="both", expand=True, padx=6, pady=4)
        row = ttk.Frame(sbox)
        row.pack(fill="x", padx=6, pady=(0, 6))
        self.spell_var = tk.StringVar()
        ttk.Combobox(row, textvariable=self.spell_var, values=self._spells_seen, width=34).pack(side="left", padx=2)
        ttk.Button(row, text="Aggiungi", command=self._spell_add).pack(side="left", padx=2)
        ttk.Button(row, text="Rimuovi", command=self._spell_remove).pack(side="left", padx=2)
        self._refresh_spells()

    def _refresh_spells(self) -> None:
        self.spell_list.delete(0, "end")
        for s in self._spells:
            self.spell_list.insert("end", s)

    def _spell_add(self) -> None:
        s = self.spell_var.get().strip()
        if s and s not in self._spells:
            self._spells.append(s)
            self._refresh_spells()
        self.spell_var.set("")

    def _spell_remove(self) -> None:
        for i in sorted(self.spell_list.curselection(), reverse=True):
            del self._spells[i]
        self._refresh_spells()

    def _save(self) -> None:
        g = lambda k: self.v[k].get()
        try:
            imp = am.Improvement(
                name=g("name").strip(), cost=am._int(g("cost"), "cost"), gold=am._int(g("gold"), "gold"),
                mana=am._int(g("mana"), "mana"), perk=g("perk").strip(), unit_name=g("unit_name").strip(),
                resource_name=g("resource_name").strip(), dlc_id=am._int(g("dlc_id"), "dlcId"), dlc=g("dlc").strip(),
                god_name=g("god_name").strip(), relation_delta=am._int(g("relation_delta"), "relationDelta"),
                spells=list(self._spells),
            )
            imp.to_element()          # validazione
            self._on_save(imp)
        except am.PerkError as exc:
            messagebox.showerror("Improvement non valido", str(exc), parent=self)
            return
        except Exception as exc:
            messagebox.showerror("Salvataggio non riuscito", f"{type(exc).__name__}: {exc}", parent=self)
            return
        self.destroy()
