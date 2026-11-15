"""Warlock Mod Manager — tab Perks: modifica/creazione dei perk e assegnazione delle icone.

Il gioco sceglie l'icona di un perk dal FrameLabel di uno sprite dentro c_icons.gfx: un perk
senza frame con il proprio nome non ha icona. Questo pannello legge il c_icons.gfx effettivo
dai pack del gioco, mostra i perk del workspace e le icone degli atlanti (.dds), e salva un
c_icons.gfx modificato nel workspace, dove il normale "Repack workspace" lo include.
In più permette di creare e modificare i perk di perks.binary (inserimento in ordine
alfabetico, come richiede il gioco).
"""

from __future__ import annotations

import os
import tkinter as tk
from tkinter import messagebox, ttk
from typing import Callable, Dict, List, Optional, Tuple

try:
    from PIL import ImageTk
    PIL_AVAILABLE = True
except ImportError:  # pragma: no cover
    ImageTk = None
    PIL_AVAILABLE = False

import perk_schema as ps
from gfx_icons import GfxError, GfxIcons, apply_assignments
from panels.perk_dialog import PerkDialog
from services import icon_service as ics
from services import perk_service as pks
from theme import ACCENT, BG2, FG, MUTED



class PerkIconPanel(ttk.Frame):
    def __init__(
        self,
        parent: tk.Misc,
        *,
        get_scan: Callable[[], Optional[object]],
        get_workspace: Callable[[], Tuple[Optional[str], Dict[str, str]]],
        on_saved: Callable[[], None],
        log: Callable[[str], None],
        before_perks_write: Callable[[], None] = lambda: None,
        after_perks_write: Callable[[], None] = lambda: None,
    ) -> None:
        super().__init__(parent)
        self._get_scan = get_scan
        self._get_workspace = get_workspace
        self._on_saved = on_saved
        self._log = log
        self._before_perks_write = before_perks_write
        self._after_perks_write = after_perks_write

        self._base: Optional[bytes] = None     # c_icons.gfx effettivo (dal gioco)
        self._gfx: Optional[GfxIcons] = None
        self._source = ""
        self._pack_paths: List[str] = []
        self._assign: Dict[str, int] = {}      # perk -> shape (modifiche da salvare)
        self._extra_assign: Dict[str, Tuple[int, int]] = {}   # label -> (shape, sprite) chiesti da altri tab
        self._perk_types: Dict[str, str] = {}  # nome -> perkType, letti da perks.binary
        self._schema: ps.Schema = ps.base_schema()
        self._inversions = 0
        self._atlas_imgs: Dict[int, object] = {}
        self._atlas_ids: List[int] = []
        self._tiles: List[ics.Tile] = []
        self._photo = None
        self._sel_perk: Optional[str] = None
        self._sel_shape: Optional[int] = None
        self._ref_size: Optional[Tuple[float, float]] = None
        self._sprite_id: Optional[int] = None
        self._cols = 10

        self.status_var = tk.StringVar(value="")
        self.info_var = tk.StringVar(value="")
        self.warn_var = tk.StringVar(value="")
        self.search_var = tk.StringVar()
        self.filter_var = tk.StringVar(value="fraction")
        self.only_ref = tk.BooleanVar(value=True)
        self.atlas_var = tk.StringVar()

        self._build()

    # ------------------------------------------------------------------
    # UI
    # ------------------------------------------------------------------
    def _build(self) -> None:
        top = ttk.Frame(self)
        top.pack(fill="x", padx=6, pady=6)
        ttk.Button(top, text="Ricarica dal gioco", command=self.reload).pack(side="left")
        ttk.Label(top, textvariable=self.status_var, foreground=MUTED).pack(side="left", padx=10)

        paned = ttk.Panedwindow(self, orient="horizontal")
        paned.pack(fill="both", expand=True, padx=6, pady=(0, 6))

        # --- sinistra: perk ---
        left = ttk.LabelFrame(paned, text="Perk")
        paned.add(left, weight=1)
        srow = ttk.Frame(left)
        srow.pack(fill="x", padx=4, pady=4)
        ttk.Label(srow, text="Cerca:").pack(side="left")
        e = ttk.Entry(srow, textvariable=self.search_var)
        e.pack(side="left", fill="x", expand=True, padx=4)
        e.bind("<KeyRelease>", lambda _e: self._refresh_perks())
        frow = ttk.Frame(left)
        frow.pack(fill="x", padx=4)
        ttk.Radiobutton(frow, text="Perk di fazione", value="fraction", variable=self.filter_var,
                        command=self._refresh_perks).pack(side="left", padx=(0, 12))
        ttk.Radiobutton(frow, text="Tutti i perk", value="all", variable=self.filter_var,
                        command=self._refresh_perks).pack(side="left")

        tf = ttk.Frame(left)
        tf.pack(fill="both", expand=True, padx=4)
        self.tree = ttk.Treeview(tf, columns=("perk", "type", "icon"), show="headings", selectmode="browse")
        self.tree.heading("perk", text="Perk")
        self.tree.heading("type", text="Tipo")
        self.tree.heading("icon", text="Icona")
        self.tree.column("perk", width=185)
        self.tree.column("type", width=60)
        self.tree.column("icon", width=165)
        self.tree.tag_configure("pending", foreground=ACCENT)
        self.tree.tag_configure("missing", foreground=MUTED)
        sb = ttk.Scrollbar(tf, orient="vertical", command=self.tree.yview)
        self.tree.configure(yscrollcommand=sb.set)
        self.tree.pack(side="left", fill="both", expand=True)
        sb.pack(side="right", fill="y")
        self.tree.bind("<<TreeviewSelect>>", self._on_perk_selected)

        self.sort_warn = ttk.Label(left, foreground=ACCENT, wraplength=380, justify="left")
        self.sort_warn.pack(fill="x", padx=6)
        arow = ttk.Frame(left)
        arow.pack(fill="x", padx=4, pady=6)
        ttk.Button(arow, text="Nuovo perk…", style="Accent.TButton", command=self._new_perk).pack(side="left", padx=2)
        ttk.Button(arow, text="Modifica perk…", command=self._edit_perk).pack(side="left", padx=2)
        ttk.Button(arow, text="Duplica…", command=self._dup_perk).pack(side="left", padx=2)
        ttk.Button(arow, text="Ordina lista", command=self._sort_list).pack(side="left", padx=2)
        self.tree.bind("<Double-1>", lambda _e: self._edit_perk())

        # --- destra: atlante ---
        right = ttk.LabelFrame(paned, text="Icone disponibili")
        paned.add(right, weight=3)
        crow = ttk.Frame(right)
        crow.pack(fill="x", padx=4, pady=4)
        ttk.Label(crow, text="Atlante:").pack(side="left")
        self.atlas_combo = ttk.Combobox(crow, textvariable=self.atlas_var, state="readonly", width=34)
        self.atlas_combo.pack(side="left", padx=4)
        self.atlas_combo.bind("<<ComboboxSelected>>", lambda _e: self._show_atlas())
        ttk.Checkbutton(
            crow, text="Solo dimensione compatibile",
            variable=self.only_ref, command=self._show_atlas,
        ).pack(side="left", padx=8)

        cf = ttk.Frame(right)
        cf.pack(fill="both", expand=True, padx=4)
        self.canvas = tk.Canvas(cf, bg=BG2, highlightthickness=0)
        vs = ttk.Scrollbar(cf, orient="vertical", command=self.canvas.yview)
        self.canvas.configure(yscrollcommand=vs.set)
        self.canvas.pack(side="left", fill="both", expand=True)
        vs.pack(side="right", fill="y")
        self.canvas.bind("<Button-1>", self._on_canvas_click)
        self.canvas.bind("<Configure>", self._on_canvas_resize)
        self.canvas.bind("<Enter>", lambda _e: self.canvas.focus_set())
        self.canvas.bind("<MouseWheel>", self._on_wheel)

        ttk.Label(right, textvariable=self.info_var, wraplength=640, justify="left").pack(
            fill="x", padx=6, pady=(4, 0))
        ttk.Label(right, textvariable=self.warn_var, wraplength=640, justify="left",
                  foreground=ACCENT).pack(fill="x", padx=6)

        brow = ttk.Frame(right)
        brow.pack(fill="x", padx=4, pady=6)
        ttk.Button(brow, text="Assegna al perk selezionato", style="Accent.TButton",
                   command=self._assign_selected).pack(side="left", padx=2)
        ttk.Button(brow, text="Annulla modifica del perk", command=self._revert_selected).pack(side="left", padx=2)
        ttk.Button(brow, text="Salva c_icons.gfx nel workspace", style="Accent.TButton",
                   command=self.save).pack(side="right", padx=2)

    # ------------------------------------------------------------------
    # API per app.py
    # ------------------------------------------------------------------
    def on_show(self) -> None:
        """Chiamato quando il tab diventa visibile."""
        self._load_perks()
        if self._gfx is None:
            self.reload()
        else:
            self._refresh_perks()

    def reload(self) -> None:
        self._load_perks()
        scan = self._get_scan()
        if scan is None:
            self.status_var.set("Scansiona prima la cartella del gioco (per le icone).")
            self._refresh_perks()
            return
        self._pack_paths = [p.path for p in scan.all_packs]
        try:
            ws_gfx = self._workspace_gfx()
            if ws_gfx:
                with open(ws_gfx, "rb") as f:
                    data, source = f.read(), "workspace"
            else:
                data, source = ics.load_gfx(self._pack_paths, self._log)
            gfx = GfxIcons(data)
        except (OSError, GfxError) as exc:
            self._base = self._gfx = None
            messagebox.showerror("c_icons.gfx", str(exc))
            return
        self._base, self._gfx, self._source = data, gfx, source
        self._atlas_imgs.clear()
        if gfx.shape_errors:
            self._log(f"c_icons.gfx: {len(gfx.shape_errors)} shape non lette (ignorate).")

        ids = [a.id for a in sorted(gfx.atlases.values(), key=lambda a: a.id) if gfx.usable_icons(a.id)]
        self._atlas_ids = ids
        self.atlas_combo["values"] = [
            f"{gfx.atlases[i].filename}  ({len(gfx.usable_icons(i))} icone)" for i in ids
        ]
        if ids:
            self.atlas_combo.current(0)
        self.status_var.set(
            f"c_icons.gfx da {source} · {len(gfx.labels())} label · {len(gfx.sprites)} sprite"
        )
        self._refresh_perks()
        self._show_atlas()

    def _workspace_gfx(self) -> Optional[str]:
        _ws, manifest = self._get_workspace()
        path = (manifest or {}).get(ics.GFX_NAME)
        return path if path and os.path.isfile(path) else None

    def ensure_gfx(self) -> Optional[GfxIcons]:
        """c_icons.gfx letto (lo carica se serve): lo usano anche gli altri tab."""
        if self._gfx is None:
            self.reload()
        return self._gfx

    def pack_paths(self) -> List[str]:
        return list(self._pack_paths)

    def assign_and_save(self, assignments: Dict[str, Tuple[int, int]]) -> str:
        """Aggiunge frame (label -> (shape, sprite)) e scrive c_icons.gfx nel workspace, senza finestre.
        Solleva GfxError / OSError / RuntimeError se non riesce."""
        if self.ensure_gfx() is None or self._base is None:
            raise RuntimeError("c_icons.gfx non disponibile: scansiona la cartella del gioco.")
        self._extra_assign.update(assignments)
        try:
            return self._write_gfx()
        except Exception:
            for k in assignments:
                self._extra_assign.pop(k, None)
            raise

    def _write_gfx(self) -> str:
        ws, manifest = self._get_workspace()
        if not ws:
            raise RuntimeError("Carica prima un workspace (es. 'Load merged game data').")
        merged: Dict[str, object] = dict(self._assign)
        merged.update(self._extra_assign)
        data = apply_assignments(self._base, merged)
        os.makedirs(ws, exist_ok=True)
        path = os.path.join(ws, ics.GFX_NAME)
        with open(path, "wb") as f:
            f.write(data)
        manifest[ics.GFX_NAME] = path
        self._log(f"Salvato {ics.GFX_NAME} ({len(merged)} frame) in {path}")
        self._on_saved()
        return path

    # ------------------------------------------------------------------
    # Perk
    # ------------------------------------------------------------------
    def _perk_names(self) -> List[str]:
        names = set(self._assign) | set(self._perk_types)
        if self._gfx is not None:
            names |= {l for l in self._gfx.labels() if l.startswith(ics.PERK_PREFIX)}
        if not self._perk_types:   # perks.binary non letto: ripiega sulla ricerca di testo
            _ws, manifest = self._get_workspace()
            names |= set(ics.perk_names_from_workspace(manifest or {}))
        if self.filter_var.get() == "fraction":
            names = {n for n in names if n.startswith(ics.PERK_PREFIX)}
        return sorted(names, key=str.lower)

    def _current_shape(self, perk: str) -> Optional[int]:
        if perk in self._assign:
            return self._assign[perk]
        if self._gfx is None:
            return None
        fr = self._gfx.labels().get(perk)
        return fr.char if fr is not None else None

    def _row_text(self, perk: str) -> Tuple[str, str]:
        if perk in self._assign:
            return f"→ shape {self._assign[perk]}  (da salvare)", "pending"
        if self._gfx is None:
            return "—", ""
        fr = self._gfx.labels().get(perk)
        if fr is None or fr.char is None:
            return "nessuna icona", "missing"
        return f"frame {fr.number} · shape {fr.char}", ""

    def _refresh_perks(self) -> None:
        keep = self._sel_perk
        self.tree.delete(*self.tree.get_children())
        needle = self.search_var.get().strip().lower()
        for perk in self._perk_names():
            if needle and needle not in perk.lower():
                continue
            text, tag = self._row_text(perk)
            self.tree.insert("", "end", iid=perk, values=(perk, self._perk_types.get(perk, "—"), text),
                             tags=(tag,) if tag else ())
        if keep and self.tree.exists(keep):
            self.tree.selection_set(keep)

    # ------------------------------------------------------------------
    # perks.binary: lettura, modifica, creazione
    # ------------------------------------------------------------------
    def _perks_file(self, quiet: bool = False) -> Optional[str]:
        _ws, manifest = self._get_workspace()
        path = pks.perks_path(manifest or {})
        if not path or not os.path.isfile(path):
            if not quiet:
                messagebox.showinfo(
                    "Perks",
                    "Carica prima un workspace che contenga perks.binary "
                    "(per esempio 'Load merged game data').",
                )
            return None
        return path

    def _load_perks(self) -> None:
        path = self._perks_file(quiet=True)
        self._perk_types, self._inversions = {}, 0
        self._schema = ps.base_schema()
        if path:
            try:
                self._perk_types, self._schema, self._inversions = pks.read_info(path)
            except Exception as exc:
                self._log(f"perks.binary non letto: {type(exc).__name__}: {exc}")
        if self._inversions:
            self.sort_warn.configure(
                text="perks.binary non è in ordine alfabetico: il gioco può non trovare alcuni perk. "
                     "Usa 'Ordina lista'.")
        else:
            self.sort_warn.configure(text="")
        self._refresh_perks()

    def _write_perks(self, fn):
        """Salva nel file con i hook verso l'editor del manager: se perks.binary è aperto lì,
        prima si salvano le sue modifiche e dopo lo si ricarica."""
        self._before_perks_write()
        try:
            return fn()
        finally:
            self._after_perks_write()
            self._load_perks()

    def _default_perk(self) -> ps.Perk:
        fraction = self.filter_var.get() == "fraction"
        ptype = "Fraction" if fraction else "Unit"
        client = self._schema.default_client.get(ptype, "")
        return ps.Perk(
            name=ics.PERK_PREFIX if fraction else "",
            perk_type=ptype,
            dlc_id="" if fraction else None,
            conditions=[ps.client_condition(client)] if client else [],
            terminators=ps.terminators_element(ps.TerminatorsData()),
        )

    def _ensure_sorted(self, path: str) -> bool:
        if not self._inversions:
            return True
        if not messagebox.askyesno(
            "Ordine alfabetico",
            "perks.binary non è in ordine alfabetico, quindi il nuovo perk non si può inserire "
            "nel posto giusto.\n\nOrdinare prima la lista?"):
            return False
        self._sort_list(ask=False)
        return not self._inversions

    def _new_perk(self, template: Optional[ps.Perk] = None) -> None:
        path = self._perks_file()
        if not path or not self._ensure_sorted(path):
            return
        perk = template or self._default_perk()

        def save(p: ps.Perk) -> None:
            pos = self._write_perks(lambda: pks.add_perk(path, p))
            self._sel_perk = p.name
            self.status_var.set(f"Perk {p.name} aggiunto in posizione {pos + 1} (ordine alfabetico). "
                                "Ora fai il repack del workspace.")
            self._log(f"Perk {p.name} aggiunto a perks.binary (posizione {pos + 1}).")

        PerkDialog(self, self._schema, perk, is_new=True,
                   title="Duplica perk" if template else "Nuovo perk", on_save=save)

    def _selected_perk_name(self) -> Optional[str]:
        sel = self.tree.selection()
        if not sel:
            messagebox.showinfo("Perks", "Seleziona prima un perk nella lista.")
            return None
        return sel[0]

    def _load_selected(self, path: str, name: str) -> Optional[ps.Perk]:
        self._before_perks_write()
        try:
            return pks.get_perk(path, name)
        except ps.PerkError as exc:
            messagebox.showerror("Perk", str(exc))
            return None

    def _edit_perk(self) -> None:
        path = self._perks_file()
        name = self._selected_perk_name() if path else None
        if not path or not name:
            return
        perk = self._load_selected(path, name)
        if perk is None:
            return

        def save(p: ps.Perk) -> None:
            self._write_perks(lambda: pks.update_perk(path, p))
            self.status_var.set(f"Perk {p.name} modificato. Ora fai il repack del workspace.")
            self._log(f"Perk {p.name} modificato in perks.binary.")

        PerkDialog(self, self._schema, perk, is_new=False, title=f"Modifica perk: {name}", on_save=save)

    def _dup_perk(self) -> None:
        path = self._perks_file()
        name = self._selected_perk_name() if path else None
        if not path or not name:
            return
        perk = self._load_selected(path, name)
        if perk is None:
            return
        perk.name = name + "_copy"
        self._new_perk(template=perk)

    def _sort_list(self, ask: bool = True) -> None:
        path = self._perks_file()
        if not path:
            return
        if ask and not self._inversions:
            messagebox.showinfo("Ordina lista", "La lista è già in ordine alfabetico.")
            return
        if ask and not messagebox.askyesno(
                "Ordina lista", "Riordinare alfabeticamente tutti i perk di perks.binary?"):
            return
        try:
            moved = self._write_perks(lambda: pks.sort_list(path))
        except Exception as exc:
            messagebox.showerror("Ordina lista", f"{type(exc).__name__}: {exc}")
            return
        self.status_var.set(f"Lista ordinata ({moved} perk spostati). Ora fai il repack del workspace.")

    def _on_perk_selected(self, _evt=None) -> None:
        sel = self.tree.selection()
        if not sel or self._gfx is None:
            return
        self._sel_perk = sel[0]
        self._ref_size = None
        self._sprite_id = None
        try:
            sp = self._gfx.sprite_for_label(self._sel_perk)
            self._sprite_id = sp.id
            self._ref_size = self._gfx.reference_size(sp.id)
        except GfxError:
            pass
        cur = self._current_shape(self._sel_perk)
        sub = self._gfx.subimage_of_shape(cur)
        if sub is not None and sub.atlas in self._atlas_ids:
            idx = self._atlas_ids.index(sub.atlas)
            if self.atlas_combo.current() != idx:
                self.atlas_combo.current(idx)
        self._sel_shape = cur
        self._show_atlas()
        self._update_info()

    # ------------------------------------------------------------------
    # Atlante
    # ------------------------------------------------------------------
    def _current_atlas_id(self) -> Optional[int]:
        i = self.atlas_combo.current()
        return self._atlas_ids[i] if 0 <= i < len(self._atlas_ids) else None

    def _atlas_image(self, aid: int):
        if aid not in self._atlas_imgs:
            assert self._gfx is not None
            self._atlas_imgs[aid] = ics.load_atlas_image(self._pack_paths, self._gfx.atlases[aid].filename)
        return self._atlas_imgs[aid]

    def _show_atlas(self) -> None:
        self.canvas.delete("all")
        self._tiles = []
        aid = self._current_atlas_id()
        if self._gfx is None or aid is None:
            return
        if not PIL_AVAILABLE:
            self.info_var.set("Serve Pillow per mostrare le icone:  pip install Pillow")
            return
        try:
            atlas = self._atlas_image(aid)
        except Exception as exc:  # file mancante o formato .dds non letto
            self.info_var.set(f"Atlante non leggibile: {exc}")
            return
        size = self._ref_size if self.only_ref.get() else None
        items = ics.icons_for_atlas(self._gfx, aid, size)
        sheet, self._tiles = ics.render_sheet(atlas, items, cols=self._cols)
        self._photo = ImageTk.PhotoImage(sheet)
        self.canvas.create_image(0, 0, image=self._photo, anchor="nw")
        self.canvas.configure(scrollregion=(0, 0, sheet.width, sheet.height))
        self.canvas.yview_moveto(0)
        if not items:
            self.info_var.set("Nessuna icona con questa dimensione in questo atlante: togli il filtro o cambia atlante.")
        self._highlight()

    def _highlight(self) -> None:
        self.canvas.delete("hl")
        cur = self._current_shape(self._sel_perk) if self._sel_perk else None
        for t in self._tiles:
            if t.shape_id == self._sel_shape:
                self.canvas.create_rectangle(t.x + 1, t.y + 1, t.x + t.w - 2, t.y + t.h - 2,
                                             outline=ACCENT, width=2, tags="hl")
            elif t.shape_id == cur:
                self.canvas.create_rectangle(t.x + 1, t.y + 1, t.x + t.w - 2, t.y + t.h - 2,
                                             outline="#6fbf73", width=2, dash=(4, 3), tags="hl")

    def _on_canvas_resize(self, evt) -> None:
        cols = max(3, evt.width // ics.TILE_W)
        if cols != self._cols:
            self._cols = cols
            self.after_idle(self._show_atlas)

    def _on_wheel(self, evt) -> None:
        self.canvas.yview_scroll(-1 if evt.delta > 0 else 1, "units")

    def _on_canvas_click(self, evt) -> None:
        t = ics.tile_at(self._tiles, int(self.canvas.canvasx(evt.x)), int(self.canvas.canvasy(evt.y)))
        if t is None:
            return
        self._sel_shape = t.shape_id
        self._highlight()
        self._update_info()

    def _update_info(self) -> None:
        self.warn_var.set("")
        g = self._gfx
        if g is None or self._sel_shape is None or self._sel_shape not in g.shapes:
            self.info_var.set("")
            return
        sh = g.shapes[self._sel_shape]
        sub = g.subimages.get(sh.subimage) if sh.subimage is not None else None
        if sub is None:
            self.info_var.set(f"Shape {sh.id}: non usa nessun ritaglio.")
            return
        atlas = g.atlases.get(sub.atlas)
        w, h = sh.size_px
        self.info_var.set(
            f"Shape {sh.id} · ritaglio {sub.id} · {atlas.filename if atlas else sub.atlas} "
            f"({sub.x1},{sub.y1})–({sub.x2},{sub.y2}) · {sub.w}×{sub.h} px · si vede a {w:g}×{h:g} px"
        )
        if self._ref_size and sh.size_px != self._ref_size:
            rw, rh = self._ref_size
            self.warn_var.set(
                f"Attenzione: le altre icone di questo tipo si vedono a {rw:g}×{rh:g} px, "
                f"questa a {w:g}×{h:g}: nel gioco apparirebbe di dimensione diversa."
            )

    # ------------------------------------------------------------------
    # Assegna / annulla / salva
    # ------------------------------------------------------------------
    def _assign_selected(self) -> None:
        if self._gfx is None or self._base is None:
            return
        if not self._sel_perk:
            messagebox.showinfo("Assegna", "Seleziona prima un perk nella lista a sinistra.")
            return
        if self._sel_shape is None or self._sel_shape not in self._gfx.shapes:
            messagebox.showinfo("Assegna", "Clicca prima l'icona da usare.")
            return
        sh = self._gfx.shapes[self._sel_shape]
        if self._ref_size and sh.size_px != self._ref_size:
            if not messagebox.askyesno(
                "Dimensione diversa",
                f"Questa icona si vede a {sh.size_px[0]:g}×{sh.size_px[1]:g} px, le altre di questo tipo "
                f"a {self._ref_size[0]:g}×{self._ref_size[1]:g}. Assegnarla comunque?",
            ):
                return
        trial = dict(self._assign)
        trial[self._sel_perk] = self._sel_shape
        try:
            apply_assignments(self._base, trial)  # prova a secco, rilegge e verifica
        except GfxError as exc:
            messagebox.showerror("Non assegnabile", str(exc))
            return
        self._assign = trial
        self._refresh_perks()
        self._highlight()
        self.status_var.set(f"{len(self._assign)} modifica/e da salvare.")

    def _revert_selected(self) -> None:
        if self._sel_perk and self._sel_perk in self._assign:
            del self._assign[self._sel_perk]
            self._sel_shape = self._current_shape(self._sel_perk)
            self._refresh_perks()
            self._highlight()
            self._update_info()
            self.status_var.set(f"{len(self._assign)} modifica/e da salvare.")

    def save(self) -> None:
        if self._base is None or self._gfx is None:
            return
        if not self._assign and not self._extra_assign:
            messagebox.showinfo("Salva", "Nessuna modifica da salvare.")
            return
        ws, _manifest = self._get_workspace()
        if not ws:
            messagebox.showinfo(
                "Salva",
                "Carica prima un workspace (es. 'Load merged game data'): "
                "c_icons.gfx viene salvato lì, accanto a perks.",
            )
            return
        try:
            path = self._write_gfx()
        except GfxError as exc:
            messagebox.showerror("Salvataggio annullato", str(exc))
            return
        self.status_var.set(f"Salvato in {path}")
        messagebox.showinfo(
            "Salvato",
            f"{ics.GFX_NAME} salvato nel workspace.\n\n"
            "Ora usa 'Repack workspace → pack file': seleziona perks.binary e c_icons.gfx "
            "(o niente, per includere tutto il workspace).",
        )
