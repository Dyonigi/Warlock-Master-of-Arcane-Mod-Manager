"""Warlock Mod Manager — editor dedicato a locdata.md (stringhe).

Modello: il gioco legge UN SOLO locdata (quello del pack con numero più alto), quindi il
file prodotto deve essere COMPLETO. Il pannello parte dal vanilla (l100.pack, sola
lettura) e tiene le differenze (chiavi cambiate o nuove). get_data() applica le differenze
al vanilla senza spostare nulla: i testi cambiati vengono aggiunti in coda e la chiave
viene ripuntata lì, quindi la lunghezza dei testi è libera.

set_data(data, vanilla) riceve BYTE; get_data() restituisce BYTE (il locdata completo).
"""

from __future__ import annotations

import re
import tkinter as tk
from tkinter import messagebox, ttk
from typing import Callable, Dict, List, Optional

try:  # il pannello sta in panels/, accanto a locdata_keys.py
    from .locdata_keys import LocdataKeysError, all_pairs, apply_changes
except ImportError:  # esecuzione fuori dal package
    from locdata_keys import LocdataKeysError, all_pairs, apply_changes

_KEY_RE = re.compile(r"^[A-Z0-9_]+$")


class LocdataPanel(ttk.Frame):
    def __init__(
        self,
        parent: tk.Misc,
        *,
        on_dirty_changed: Optional[Callable[[], None]] = None,
    ) -> None:
        super().__init__(parent)
        self._on_dirty_changed = on_dirty_changed

        self._vanilla: Optional[bytes] = None
        self._vkeys: List[str] = []  # chiavi vanilla, in ordine
        self._vtext: Dict[str, str] = {}  # testo vanilla
        self._delta: Dict[str, str] = {}  # chiavi cambiate o nuove -> testo
        self._rows_cache: List[str] = []  # chiave di ogni riga (vanilla + nuove)
        self._filtered_indices: List[int] = []

        self.dirty = False
        self.search_var = tk.StringVar()
        self.key_var = tk.StringVar()
        self.status_var = tk.StringVar(value="")
        self._current_key: Optional[str] = None  # None = nessuna selezione / nuova

        self._build()

    # ------------------------------------------------------------------
    def _build(self) -> None:
        top = ttk.Frame(self)
        top.pack(fill="x", padx=6, pady=6)
        ttk.Label(top, text="Search (Key or Text):").pack(side="left")
        search_entry = ttk.Entry(top, textvariable=self.search_var)
        search_entry.pack(side="left", fill="x", expand=True, padx=6)
        search_entry.bind("<KeyRelease>", lambda e: self._refresh_tree())

        tree_frame = ttk.Frame(self)
        tree_frame.pack(fill="both", expand=True, padx=6, pady=(0, 6))
        self.tree = ttk.Treeview(tree_frame, columns=("key", "value"), show="headings")
        self.tree.heading("key", text="Key")
        self.tree.heading("value", text="Text")
        self.tree.column("key", width=260)
        self.tree.column("value", width=400)
        self.tree.pack(side="left", fill="both", expand=True)
        scroll = ttk.Scrollbar(tree_frame, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=scroll.set)
        scroll.pack(side="right", fill="y")
        self.tree.bind("<<TreeviewSelect>>", self._on_select)

        form = ttk.LabelFrame(self, text="Edit Selected String")
        form.pack(fill="x", padx=6, pady=(0, 6))

        row1 = ttk.Frame(form)
        row1.pack(fill="x", padx=6, pady=4)
        ttk.Label(row1, text="Key:", width=8).pack(side="left")
        key_entry = ttk.Entry(row1, textvariable=self.key_var)
        key_entry.pack(side="left", fill="x", expand=True)
        key_entry.bind("<FocusOut>", self._normalize_key)

        row2 = ttk.Frame(form)
        row2.pack(fill="x", padx=6, pady=4)
        ttk.Label(row2, text="Text:", width=8).pack(side="left", anchor="n")
        self.value_text = tk.Text(row2, height=5, wrap="word", undo=True)
        self.value_text.pack(side="left", fill="x", expand=True)

        ttk.Label(form, textvariable=self.status_var).pack(anchor="w", padx=6)

        btn_row = ttk.Frame(form)
        btn_row.pack(fill="x", padx=6, pady=6)
        ttk.Button(btn_row, text="Save Selection", command=self._save_selection,
                   style="Accent.TButton").pack(side="left", padx=4)
        ttk.Button(btn_row, text="New String", command=self._new_string).pack(side="left", padx=4)
        ttk.Button(btn_row, text="Revert / Delete", command=self._delete_selection).pack(side="left", padx=4)

    # ------------------------------------------------------------------
    # API pubblica
    # ------------------------------------------------------------------
    def set_data(self, data: bytes, vanilla: Optional[bytes] = None) -> None:
        """data = locdata del workspace (piccolo o completo); vanilla = locdata di l100."""
        base = vanilla if vanilla is not None else data
        try:
            vpairs = all_pairs(base)
            cur = all_pairs(data)
        except Exception as exc:  # struttura non riconosciuta
            self._vanilla = None
            messagebox.showerror("locdata", f"File non riconosciuto:\n{exc}")
            return
        self._vanilla = base
        self._vkeys = [k for k, _ in vpairs]
        self._vtext = dict(vpairs)
        # delta = tutto ciò che nel file corrente differisce dal vanilla
        self._delta = {k: t for k, t in cur if self._vtext.get(k) != t}
        self.dirty = False
        self._current_key = None
        self._clear_form()
        self._refresh_tree()

    def get_data(self) -> bytes:
        """locdata COMPLETO (vanilla + modifiche), da scrivere con 'wb'."""
        if self._vanilla is None:
            raise RuntimeError("Nessun locdata caricato.")
        return apply_changes(self._vanilla, self._delta)

    def mark_clean(self) -> None:
        self.dirty = False
        if self._on_dirty_changed:
            self._on_dirty_changed()

    # ------------------------------------------------------------------
    # Interni
    # ------------------------------------------------------------------
    @staticmethod
    def _one_line(text: Optional[str]) -> str:
        return (text or "").replace("\r", "").replace("\n", "\\n")

    def _text_of(self, key: str) -> str:
        return self._delta.get(key, self._vtext.get(key, ""))

    def _clear_form(self) -> None:
        self.key_var.set("")
        self.value_text.delete("1.0", "end")
        self.status_var.set("")

    def _refresh_tree(self) -> None:
        self.tree.delete(*self.tree.get_children())
        self._filtered_indices.clear()
        if self._vanilla is None:
            return
        news = [k for k in self._delta if k not in self._vtext]
        self._rows_cache = self._vkeys + news
        needle = self.search_var.get().strip().lower()
        for i, key in enumerate(self._rows_cache):
            text = self._text_of(key)
            if needle and needle not in key.lower() and needle not in text.lower():
                continue
            self._filtered_indices.append(i)
            mark = ""
            if key in self._delta:
                mark = "  [nuova]" if key not in self._vtext else "  [modificata]"
            self.tree.insert("", "end", iid=str(i), values=(key + mark, self._one_line(text)))

    def _on_select(self, _evt=None) -> None:
        sel = self.tree.selection()
        if not sel or self._vanilla is None:
            return
        key = self._rows_cache[int(sel[0])]
        self._current_key = key
        self.key_var.set(key)
        self.value_text.delete("1.0", "end")
        self.value_text.insert("1.0", self._text_of(key))
        self._update_status()

    def _update_status(self) -> None:
        key = self._current_key
        if key is None:
            self.status_var.set("Nuova chiave: testo di lunghezza libera.")
        elif key not in self._vtext:
            self.status_var.set("Chiave nuova (aggiunta al locdata).")
        elif key in self._delta:
            self.status_var.set("Chiave vanilla modificata: 'Revert' ripristina il testo originale.")
        else:
            self.status_var.set("Chiave vanilla non modificata. Salvando crei una sostituzione.")

    def _normalize_key(self, _evt=None) -> None:
        raw = self.key_var.get()
        clean = re.sub(r"[^a-zA-Z0-9_]", "_", raw)
        clean = re.sub(r"_+", "_", clean)
        self.key_var.set(clean.strip("_").upper())

    def _read_value(self) -> str:
        return self.value_text.get("1.0", "end-1c")

    def _trial_build(self, delta: Dict[str, str]) -> None:
        """Prova a secco: se la costruzione fallisce non si salva nulla."""
        assert self._vanilla is not None
        apply_changes(self._vanilla, delta)

    def _save_selection(self) -> None:
        if self._vanilla is None:
            return
        self._normalize_key()
        key = self.key_var.get()
        text = self._read_value()
        if not key:
            messagebox.showerror("Chiave", "Inserisci il nome della chiave.")
            return
        if not text:
            messagebox.showerror("Testo", "Il testo non può essere vuoto.")
            return
        if "\x00" in text:
            messagebox.showerror("Testo", "Il testo non può contenere byte nulli.")
            return

        creating = self._current_key is None
        if creating and key in self._vtext:
            messagebox.showerror("Chiave", f"{key} esiste già nel vanilla: selezionala nella lista per modificarla.")
            return
        if creating and key in self._delta:
            messagebox.showerror("Chiave", f"{key} esiste già tra le tue chiavi.")
            return
        if not creating and key != self._current_key:
            messagebox.showerror(
                "Chiave",
                "Per cambiare nome crea una chiave nuova (le chiavi vanilla si cercano per nome).",
            )
            self.key_var.set(self._current_key or "")
            return
        if not _KEY_RE.match(key):
            messagebox.showerror("Chiave", "La chiave può contenere solo A-Z, 0-9 e '_'.")
            return

        trial = dict(self._delta)
        if key in self._vtext and text == self._vtext[key]:
            trial.pop(key, None)  # uguale al vanilla: nessuna sostituzione
        else:
            trial[key] = text
        try:
            self._trial_build(trial)
        except LocdataKeysError as exc:
            messagebox.showerror("Non salvabile", str(exc))
            return
        self._delta = trial
        self._current_key = key
        self._mark_dirty()
        self._refresh_tree()
        self._update_status()

    def _new_string(self) -> None:
        self._current_key = None
        self._clear_form()
        self.key_var.set("NEW_KEY_")
        self._update_status()

    def _delete_selection(self) -> None:
        key = self._current_key
        if key is None or key not in self._delta:
            messagebox.showinfo(
                "Revert / Delete",
                "Seleziona una chiave modificata o nuova. Le chiavi vanilla non modificate "
                "non si possono eliminare.",
            )
            return
        what = "ripristinare il testo originale di" if key in self._vtext else "eliminare la chiave nuova"
        if not messagebox.askyesno("Revert / Delete", f"Vuoi {what} '{key}'?"):
            return
        del self._delta[key]
        self._mark_dirty()
        self._current_key = None
        self._clear_form()
        self._refresh_tree()

    def _mark_dirty(self) -> None:
        self.dirty = True
        if self._on_dirty_changed:
            self._on_dirty_changed()