"""Warlock Mod Manager — finestre modali per creare/modificare un perk e i suoi effetti."""

from __future__ import annotations

import copy
import tkinter as tk
from tkinter import messagebox, ttk
from typing import Callable, Dict, List, Optional
import xml.etree.ElementTree as ET

import perk_schema as ps
from theme import ACCENT, BG, BG2, FG, MUTED


def _center(win: tk.Toplevel, parent: tk.Misc, w: int, h: int) -> None:
    win.update_idletasks()
    top = parent.winfo_toplevel()
    x = top.winfo_rootx() + max(0, (top.winfo_width() - w) // 2)
    y = top.winfo_rooty() + max(0, (top.winfo_height() - h) // 3)
    win.geometry(f"{w}x{h}+{x}+{y}")


def _make_modal(win: tk.Toplevel, parent: tk.Misc) -> None:
    win.transient(parent.winfo_toplevel())
    win.deiconify()

    def grab() -> None:
        try:
            win.grab_set()
            win.focus_set()
        except tk.TclError:
            pass

    win.after(30, grab)


def _xml_text(el: ET.Element) -> str:
    e = copy.deepcopy(el)
    ps.indent_item(e, 0)
    return ET.tostring(e, encoding="unicode").strip()


# ---------------------------------------------------------------------------
# Effetto
# ---------------------------------------------------------------------------

class EffectDialog(tk.Toplevel):
    RAW = "(XML grezzo)"

    def __init__(
        self, parent: tk.Misc, schema: ps.Schema, element: Optional[ET.Element],
        on_ok: Callable[[ET.Element], None],
    ) -> None:
        super().__init__(parent)
        self.withdraw()
        self.title("Effetto")
        self.configure(bg=BG)
        self.schema, self._on_ok, self._element = schema, on_ok, element
        self._vars: Dict[str, tk.StringVar] = {}

        values = ps.effect_values(schema, element) if element is not None else None
        if element is None:
            tag = sorted(schema.effects)[0] if schema.effects else self.RAW
        elif values is not None:
            tag = element.tag
        else:
            tag = self.RAW
        self.type_var = tk.StringVar(value=tag)

        top = ttk.Frame(self)
        top.pack(fill="x", padx=10, pady=(10, 4))
        ttk.Label(top, text="Tipo di effetto:").pack(side="left")
        self.type_combo = ttk.Combobox(top, textvariable=self.type_var, state="readonly", width=36,
                                       values=sorted(schema.effects) + [self.RAW])
        self.type_combo.pack(side="left", padx=6)
        self.type_combo.bind("<<ComboboxSelected>>", lambda _e: self._render(self._current_values()))

        self.body = ttk.Frame(self)
        self.body.pack(fill="both", expand=True, padx=10, pady=4)
        self.raw_text: Optional[tk.Text] = None

        btns = ttk.Frame(self)
        btns.pack(fill="x", padx=10, pady=10)
        ttk.Button(btns, text="OK", style="Accent.TButton", command=self._ok).pack(side="right", padx=4)
        ttk.Button(btns, text="Annulla", command=self.destroy).pack(side="right")

        self._render(values)
        self.protocol("WM_DELETE_WINDOW", self.destroy)
        _center(self, parent, 520, 150 + 34 * max(3, len(self._vars)))
        _make_modal(self, parent)

    # ------------------------------------------------------------------
    def _current_values(self) -> Dict[str, str]:
        return {p: v.get() for p, v in self._vars.items()}

    def _render(self, initial: Optional[Dict[str, str]]) -> None:
        for w in self.body.winfo_children():
            w.destroy()
        self._vars = {}
        self.raw_text = None
        tag = self.type_var.get()
        if tag == self.RAW:
            ttk.Label(self.body, foreground=MUTED, wraplength=480,
                      text="Scrivi l'XML dell'effetto (per tipi non presenti nello schema).").pack(anchor="w")
            self.raw_text = tk.Text(self.body, height=10, wrap="none", bg=BG2, fg=FG, insertbackground=FG,
                                    relief="flat")
            self.raw_text.pack(fill="both", expand=True, pady=4)
            if self._element is not None:
                self.raw_text.insert("1.0", _xml_text(self._element))
            else:
                self.raw_text.insert("1.0", "<NomeEffetto>\n</NomeEffetto>")
            return
        spec = self.schema.effects[tag]
        if not spec.fields:
            ttk.Label(self.body, foreground=MUTED, text="Questo effetto non ha parametri.").pack(anchor="w")
            return
        initial = initial or {}
        grid = ttk.Frame(self.body)
        grid.pack(fill="x")
        grid.columnconfigure(1, weight=1)
        for r, f in enumerate(spec.fields):
            ttk.Label(grid, text=f"{f.path}  ({f.type})").grid(row=r, column=0, sticky="w", padx=(0, 10), pady=3)
            default = (f.values[0] if f.values else "") if f.type == "string" else ("0.0" if f.type == "float" else "0")
            var = tk.StringVar(value=initial.get(f.path, default))
            self._vars[f.path] = var
            if f.type == "bool":
                w = ttk.Combobox(grid, textvariable=var, values=["0", "1"], state="readonly", width=8)
            elif f.values:
                w = ttk.Combobox(grid, textvariable=var, values=f.values)
            else:
                w = ttk.Entry(grid, textvariable=var)
            w.grid(row=r, column=1, sticky="ew", pady=3)

    def _ok(self) -> None:
        try:
            if self.type_var.get() == self.RAW:
                text = self.raw_text.get("1.0", "end").strip() if self.raw_text else ""
                try:
                    el = ET.fromstring(text)
                except ET.ParseError as exc:
                    raise ps.PerkError(f"XML non valido: {exc}") from exc
            else:
                el = ps.effect_element(self.schema, self.type_var.get(), self._current_values())
        except ps.PerkError as exc:
            messagebox.showerror("Effetto non valido", str(exc), parent=self)
            return
        self._on_ok(el)
        self.destroy()


# ---------------------------------------------------------------------------
# Perk
# ---------------------------------------------------------------------------

class PerkDialog(tk.Toplevel):
    def __init__(
        self, parent: tk.Misc, schema: ps.Schema, perk: ps.Perk, *, is_new: bool, title: str,
        on_save: Callable[[ps.Perk], None],
    ) -> None:
        super().__init__(parent)
        self.withdraw()
        self.title(title)
        self.configure(bg=BG)
        self.schema, self.is_new, self._on_save = schema, is_new, on_save
        self._conds: List[ET.Element] = [copy.deepcopy(c) for c in perk.conditions]
        self._effects: List[ET.Element] = [copy.deepcopy(e) for e in perk.effects]
        self._td = ps.terminators_data(perk.terminators)
        self._last_type = perk.perk_type
        self._build(perk)
        self.protocol("WM_DELETE_WINDOW", self.destroy)
        _center(self, parent, 800, 740)
        self.minsize(720, 560)
        _make_modal(self, parent)

    # ------------------------------------------------------------------
    def _build(self, perk: ps.Perk) -> None:
        # i pulsanti per primi, ancorati in basso: restano visibili anche con finestre basse
        btns = ttk.Frame(self)
        btns.pack(side="bottom", fill="x", padx=10, pady=10)
        ttk.Button(btns, text="Salva", style="Accent.TButton", command=self._save).pack(side="right", padx=4)
        ttk.Button(btns, text="Annulla", command=self.destroy).pack(side="right")

        nb = ttk.Notebook(self)
        nb.pack(fill="both", expand=True, padx=8, pady=(8, 0))
        tab = ttk.Frame(nb)
        nb.add(tab, text="Campi")
        prev = ttk.Frame(nb)
        nb.add(prev, text="Anteprima XML")
        self.preview = tk.Text(prev, wrap="none", bg=BG2, fg=FG, relief="flat", state="disabled")
        self.preview.pack(fill="both", expand=True)
        nb.bind("<<NotebookTabChanged>>", lambda _e: self._update_preview())

        # --- dati base ---
        box = ttk.LabelFrame(tab, text="Dati")
        box.pack(fill="x", padx=6, pady=6)
        box.columnconfigure(1, weight=1)
        self.name_var = tk.StringVar(value=perk.name)
        self.type_var = tk.StringVar(value=perk.perk_type)
        self.mana_var = tk.StringVar(value=str(perk.mana_upkeep))
        self.good_var = tk.BooleanVar(value=perk.is_good)
        self.ench_var = tk.BooleanVar(value=perk.is_enchant)
        self.move_var = tk.BooleanVar(value=perk.is_change_move_type)
        ttk.Label(box, text="name").grid(row=0, column=0, sticky="w", padx=6, pady=3)
        name_entry = ttk.Entry(box, textvariable=self.name_var)
        name_entry.grid(row=0, column=1, sticky="ew", padx=6)
        if not self.is_new:
            name_entry.state(["disabled"])
        ttk.Label(box, text="perkType").grid(row=1, column=0, sticky="w", padx=6, pady=3)
        ttk.Combobox(box, textvariable=self.type_var, values=self.schema.perk_types).grid(
            row=1, column=1, sticky="ew", padx=6)
        ttk.Label(box, text="manaUpkeep").grid(row=2, column=0, sticky="w", padx=6, pady=3)
        ttk.Spinbox(box, from_=0, to=100000, textvariable=self.mana_var, width=10).grid(
            row=2, column=1, sticky="w", padx=6)
        flags = ttk.Frame(box)
        flags.grid(row=3, column=0, columnspan=2, sticky="w", padx=6, pady=4)
        ttk.Checkbutton(flags, text="isGood", variable=self.good_var).pack(side="left", padx=(0, 16))
        ttk.Checkbutton(flags, text="isEnchant", variable=self.ench_var).pack(side="left", padx=(0, 16))
        ttk.Checkbutton(flags, text="isChangeMoveType", variable=self.move_var).pack(side="left")
        self.dlc_on = tk.BooleanVar(value=perk.dlc_id is not None)
        self.dlc_id_var = tk.StringVar(value=perk.dlc_id or "")
        self.dlc_idx_var = tk.StringVar(value=str(perk.dlc_idx))
        dlc = ttk.Frame(box)
        dlc.grid(row=4, column=0, columnspan=2, sticky="w", padx=6, pady=(0, 4))
        ttk.Checkbutton(dlc, text="Campi dlcId / dlcIdIdx (usati dai perk di fazione)", variable=self.dlc_on).pack(
            side="left", padx=(0, 10))
        ttk.Entry(dlc, textvariable=self.dlc_id_var, width=12).pack(side="left", padx=2)
        ttk.Entry(dlc, textvariable=self.dlc_idx_var, width=5).pack(side="left", padx=2)

        # --- conditions ---
        cbox = ttk.LabelFrame(tab, text="Conditions")
        cbox.pack(fill="x", padx=6, pady=6)
        self.cond_tree = ttk.Treeview(cbox, columns=("tipo", "client"), show="headings", height=2,
                                      selectmode="browse")
        self.cond_tree.heading("tipo", text="Tipo")
        self.cond_tree.heading("client", text="client")
        self.cond_tree.column("tipo", width=220)
        self.cond_tree.column("client", width=300)
        self.cond_tree.pack(fill="x", padx=6, pady=4)
        self.cond_tree.bind("<<TreeviewSelect>>", self._on_cond_select)
        crow = ttk.Frame(cbox)
        crow.pack(fill="x", padx=6, pady=(0, 6))
        ttk.Label(crow, text="client:").pack(side="left")
        self.client_var = tk.StringVar(value=self.schema.default_client.get(perk.perk_type, ""))
        ttk.Combobox(crow, textvariable=self.client_var, values=self.schema.clients, width=26).pack(
            side="left", padx=6)
        ttk.Button(crow, text="Aggiungi", command=self._cond_add).pack(side="left", padx=2)
        ttk.Button(crow, text="Sostituisci selezionata", command=self._cond_replace).pack(side="left", padx=2)
        ttk.Button(crow, text="Rimuovi", command=self._cond_remove).pack(side="left", padx=2)

        # --- effects ---
        ebox = ttk.LabelFrame(tab, text="Effects")
        ebox.pack(fill="both", expand=True, padx=6, pady=6)
        self.eff_tree = ttk.Treeview(ebox, columns=("tipo", "param"), show="headings", height=5,
                                     selectmode="browse")
        self.eff_tree.heading("tipo", text="Effetto")
        self.eff_tree.heading("param", text="Parametri")
        self.eff_tree.column("tipo", width=220)
        self.eff_tree.column("param", width=470)
        self.eff_tree.pack(fill="both", expand=True, padx=6, pady=4)
        self.eff_tree.bind("<Double-1>", lambda _e: self._eff_edit())
        erow = ttk.Frame(ebox)
        erow.pack(fill="x", padx=6, pady=(0, 6))
        for text, cmd in (("Aggiungi…", self._eff_add), ("Modifica…", self._eff_edit), ("Duplica", self._eff_dup),
                          ("Rimuovi", self._eff_remove), ("▲", lambda: self._eff_move(-1)),
                          ("▼", lambda: self._eff_move(1))):
            ttk.Button(erow, text=text, command=cmd, width=10 if len(text) > 2 else 4).pack(side="left", padx=2)

        # --- terminators ---
        tbox = ttk.LabelFrame(tab, text="Terminators")
        tbox.pack(fill="x", padx=6, pady=6)
        self.term_on = tk.BooleanVar(value=self._td.present)
        self.disp_var = tk.BooleanVar(value=self._td.dispellable)
        self.timer_on = tk.BooleanVar(value=self._td.timer_turns is not None)
        self.turns_var = tk.StringVar(value=str(self._td.timer_turns if self._td.timer_turns is not None else 3))
        trow = ttk.Frame(tbox)
        trow.pack(fill="x", padx=6, pady=6)
        ttk.Checkbutton(trow, text="Blocco Terminators", variable=self.term_on).pack(side="left", padx=(0, 16))
        ttk.Checkbutton(trow, text="Dispellable", variable=self.disp_var).pack(side="left", padx=(0, 16))
        ttk.Checkbutton(trow, text="StrategicTimer (turni):", variable=self.timer_on).pack(side="left")
        ttk.Spinbox(trow, from_=0, to=1000, textvariable=self.turns_var, width=6).pack(side="left", padx=6)

        self.type_var.trace_add("write", self._on_type_changed)
        self._refresh_conds()
        self._refresh_effects()

    # ------------------------------------------------------------------
    # Tipo di perk: per i perk nuovi aggiorna i default coerenti
    # ------------------------------------------------------------------
    def _on_type_changed(self, *_a) -> None:
        if not self.is_new:
            return
        new = self.type_var.get()
        old, self._last_type = self._last_type, new
        if new == old:
            return
        self.dlc_on.set(new == "Fraction")
        self.term_on.set(new != "Artifact")
        old_def = self.schema.default_client.get(old)
        new_def = self.schema.default_client.get(new)
        clients = [ps.condition_client(c) for c in self._conds]
        if new_def and (not self._conds or clients == [old_def]):
            self._conds = [ps.client_condition(new_def)]
            self.client_var.set(new_def)
            self._refresh_conds()

    # ------------------------------------------------------------------
    # Conditions
    # ------------------------------------------------------------------
    def _refresh_conds(self) -> None:
        self.cond_tree.delete(*self.cond_tree.get_children())
        for i, c in enumerate(self._conds):
            self.cond_tree.insert("", "end", iid=str(i), values=(c.tag, ps.condition_client(c) or "(XML)"))

    def _cond_sel(self) -> Optional[int]:
        sel = self.cond_tree.selection()
        return int(sel[0]) if sel else None

    def _on_cond_select(self, _e=None) -> None:
        i = self._cond_sel()
        if i is not None and ps.condition_client(self._conds[i]):
            self.client_var.set(ps.condition_client(self._conds[i]))

    def _cond_add(self) -> None:
        client = self.client_var.get().strip()
        if not client:
            messagebox.showerror("Condizione", "Indica il valore di client.", parent=self)
            return
        self._conds.append(ps.client_condition(client))
        self._refresh_conds()

    def _cond_replace(self) -> None:
        i = self._cond_sel()
        client = self.client_var.get().strip()
        if i is None or not client:
            return
        if ps.condition_client(self._conds[i]) is None:
            messagebox.showinfo("Condizione", "Questa condizione non è di tipo ClientConditionData.", parent=self)
            return
        self._conds[i] = ps.client_condition(client)
        self._refresh_conds()
        self.cond_tree.selection_set(str(i))

    def _cond_remove(self) -> None:
        i = self._cond_sel()
        if i is not None:
            del self._conds[i]
            self._refresh_conds()

    # ------------------------------------------------------------------
    # Effects
    # ------------------------------------------------------------------
    def _refresh_effects(self, select: Optional[int] = None) -> None:
        self.eff_tree.delete(*self.eff_tree.get_children())
        for i, e in enumerate(self._effects):
            raw = ps.effect_values(self.schema, e) is None
            self.eff_tree.insert("", "end", iid=str(i),
                                 values=(e.tag + ("  (XML)" if raw else ""), ps.effect_summary(e)))
        if select is not None and 0 <= select < len(self._effects):
            self.eff_tree.selection_set(str(select))
            self.eff_tree.see(str(select))

    def _eff_sel(self) -> Optional[int]:
        sel = self.eff_tree.selection()
        return int(sel[0]) if sel else None

    def _eff_add(self) -> None:
        def ok(el: ET.Element) -> None:
            self._effects.append(el)
            self._refresh_effects(len(self._effects) - 1)
        EffectDialog(self, self.schema, None, ok)

    def _eff_edit(self) -> None:
        i = self._eff_sel()
        if i is None:
            return

        def ok(el: ET.Element) -> None:
            self._effects[i] = el
            self._refresh_effects(i)
        EffectDialog(self, self.schema, self._effects[i], ok)

    def _eff_dup(self) -> None:
        i = self._eff_sel()
        if i is not None:
            self._effects.insert(i + 1, copy.deepcopy(self._effects[i]))
            self._refresh_effects(i + 1)

    def _eff_remove(self) -> None:
        i = self._eff_sel()
        if i is not None:
            del self._effects[i]
            self._refresh_effects(min(i, len(self._effects) - 1))

    def _eff_move(self, d: int) -> None:
        i = self._eff_sel()
        if i is None or not 0 <= i + d < len(self._effects):
            return
        self._effects[i], self._effects[i + d] = self._effects[i + d], self._effects[i]
        self._refresh_effects(i + d)

    # ------------------------------------------------------------------
    # Raccolta e salvataggio
    # ------------------------------------------------------------------
    @staticmethod
    def _int(text: str, label: str) -> int:
        try:
            return int(text.strip())
        except ValueError as exc:
            raise ps.PerkError(f"{label} deve essere un numero intero.") from exc

    def _collect(self) -> ps.Perk:
        td = ps.TerminatorsData(
            present=self.term_on.get(), dispellable=self.disp_var.get(),
            timer_turns=self._int(self.turns_var.get(), "I turni di StrategicTimer") if self.timer_on.get() else None,
            timer_first=self._td.timer_first, other=self._td.other,
        )
        dlc = self.dlc_on.get()
        return ps.Perk(
            name=self.name_var.get().strip(), perk_type=self.type_var.get().strip(),
            mana_upkeep=self._int(self.mana_var.get(), "manaUpkeep"),
            is_good=self.good_var.get(), is_enchant=self.ench_var.get(),
            is_change_move_type=self.move_var.get(),
            dlc_id=self.dlc_id_var.get() if dlc else None,
            dlc_idx=self._int(self.dlc_idx_var.get(), "dlcIdIdx") if dlc else 0,
            conditions=[copy.deepcopy(c) for c in self._conds],
            effects=[copy.deepcopy(e) for e in self._effects],
            terminators=ps.terminators_element(td),
        )

    def _update_preview(self) -> None:
        try:
            text = _xml_text(self._collect().to_element())
        except ps.PerkError as exc:
            text = f"(anteprima non disponibile: {exc})"
        self.preview.configure(state="normal")
        self.preview.delete("1.0", "end")
        self.preview.insert("1.0", text)
        self.preview.configure(state="disabled")

    def _save(self) -> None:
        try:
            perk = self._collect()
            perk.to_element()          # validazione
            self._on_save(perk)
        except ps.PerkError as exc:
            messagebox.showerror("Perk non valido", str(exc), parent=self)
            return
        except Exception as exc:  # errore di file, ecc.: la finestra resta aperta
            messagebox.showerror("Salvataggio non riuscito", f"{type(exc).__name__}: {exc}", parent=self)
            return
        self.destroy()