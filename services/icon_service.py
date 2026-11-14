"""Servizio per le icone dei perk: legge c_icons.gfx e gli atlanti dai pack, elenca i perk
del workspace e disegna il contact sheet dell'atlante. Nessuna dipendenza da tkinter."""

from __future__ import annotations

import io
import os
import re
from dataclasses import dataclass
from typing import Callable, Dict, Iterable, List, Optional, Sequence, Tuple

from catalog import pack_sort_key
from gfx_icons import GfxIcons, ShapeInfo, SubImage
from packio import list_pack, read_entry

try:
    from PIL import Image, ImageDraw
    PIL_AVAILABLE = True
except ImportError:  # pragma: no cover
    Image = ImageDraw = None  # type: ignore[assignment]
    PIL_AVAILABLE = False

LogFn = Callable[[str], None]

GFX_NAME = "c_icons.gfx"
PERK_PREFIX = "fractionPerk_"
_PERK_RE = re.compile(r"fractionPerk_[A-Za-z0-9_]+")


# ---------------------------------------------------------------------------
# Lettura dai pack (vince l'ultimo pack che contiene il file, come nel gioco)
# ---------------------------------------------------------------------------

def find_in_packs(pack_paths: Iterable[str], name: str) -> Optional[Tuple[str, bytes]]:
    """Ritorna (nome del pack, contenuto) del file `name` nell'ultimo pack che lo contiene."""
    found: Optional[Tuple[str, bytes]] = None
    for path in sorted(pack_paths, key=lambda p: pack_sort_key(os.path.basename(p))):
        try:
            entries = list_pack(path)
        except Exception:
            continue
        for e in entries:
            if e.name.lower() == name.lower():
                found = (os.path.basename(path), read_entry(path, e))
    return found


def load_gfx(pack_paths: Sequence[str], log: Optional[LogFn] = None) -> Tuple[bytes, str]:
    """c_icons.gfx effettivo (quello che il gioco userebbe) e il pack da cui arriva."""
    hit = find_in_packs(pack_paths, GFX_NAME)
    if hit is None:
        raise FileNotFoundError(f"{GFX_NAME} non trovato in nessun pack del gioco.")
    if log:
        log(f"{GFX_NAME} letto da {hit[0]} ({len(hit[1])} byte).")
    return hit[1], hit[0]


def load_atlas_image(pack_paths: Sequence[str], filename: str):
    """Apre l'atlante .dds dal pack (RGBA). Solleva FileNotFoundError / eccezioni di Pillow."""
    if not PIL_AVAILABLE:
        raise RuntimeError("Serve Pillow: pip install Pillow")
    hit = find_in_packs(pack_paths, filename)
    if hit is None:
        raise FileNotFoundError(f"{filename} non trovato nei pack.")
    img = Image.open(io.BytesIO(hit[1]))
    img.load()
    return img.convert("RGBA")


# ---------------------------------------------------------------------------
# Perk del workspace
# ---------------------------------------------------------------------------

def perk_names_from_workspace(manifest: Dict[str, str]) -> List[str]:
    """Nomi fractionPerk_* trovati nei file perks* del workspace (qualunque formato XML)."""
    names: List[str] = []
    seen = set()
    for orig, path in manifest.items():
        low = orig.lower()
        if not low.startswith("perks") or not os.path.isfile(path):
            continue
        try:
            with open(path, "r", encoding="utf-8", errors="replace") as f:
                text = f.read()
        except OSError:
            continue
        for m in _PERK_RE.findall(text):
            if m not in seen:
                seen.add(m)
                names.append(m)
    return names


# ---------------------------------------------------------------------------
# Contact sheet
# ---------------------------------------------------------------------------

@dataclass
class Tile:
    shape_id: int
    sub_id: int
    x: int
    y: int
    w: int
    h: int


TILE_W = 76
TILE_H = 90
BOX = 64


def render_sheet(
    atlas, items: List[Tuple[SubImage, ShapeInfo]], cols: int = 10
):
    """Disegna le icone `items` (ritaglio, shape) in una griglia. Ritorna (immagine, tile)."""
    if not PIL_AVAILABLE:
        raise RuntimeError("Serve Pillow: pip install Pillow")
    rows = max(1, (len(items) + cols - 1) // cols)
    sheet = Image.new("RGBA", (cols * TILE_W, rows * TILE_H), (37, 36, 51, 255))
    draw = ImageDraw.Draw(sheet)
    tiles: List[Tile] = []
    for i, (sub, shape) in enumerate(items):
        ox, oy = (i % cols) * TILE_W, (i // cols) * TILE_H
        # sfondo scuro del riquadro, poi il ritaglio ridimensionato mantenendo le proporzioni
        draw.rectangle((ox + 5, oy + 3, ox + 5 + BOX + 1, oy + 3 + BOX + 1), fill=(27, 26, 34, 255))
        crop = atlas.crop((sub.x1, sub.y1, sub.x2, sub.y2))
        if crop.width and crop.height:
            k = min(BOX / crop.width, BOX / crop.height)
            crop = crop.resize((max(1, int(crop.width * k)), max(1, int(crop.height * k))), Image.LANCZOS)
            px = ox + 6 + (BOX - crop.width) // 2
            py = oy + 4 + (BOX - crop.height) // 2
            sheet.paste(crop, (px, py), crop)
        w, h = shape.size_px
        draw.text((ox + 6, oy + 70), f"sh {shape.id}", fill=(255, 220, 90, 255))
        draw.text((ox + 6, oy + 79), f"{w:g}x{h:g}", fill=(154, 146, 127, 255))
        tiles.append(Tile(shape.id, sub.id, ox, oy, TILE_W, TILE_H))
    return sheet, tiles


def tile_at(tiles: List[Tile], x: int, y: int) -> Optional[Tile]:
    for t in tiles:
        if t.x <= x < t.x + t.w and t.y <= y < t.y + t.h:
            return t
    return None


def icons_for_atlas(
    gfx: GfxIcons, atlas_id: int, size: Optional[Tuple[float, float]]
) -> List[Tuple[SubImage, ShapeInfo]]:
    """Icone dell'atlante, opzionalmente solo quelle che si vedono a una certa dimensione."""
    items = gfx.usable_icons(atlas_id)
    if size is not None:
        items = [(s, sh) for s, sh in items if sh.size_px == size]
    return items
