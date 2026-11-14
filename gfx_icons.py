"""Lettura e modifica di c_icons.gfx (Scaleform GFX) di Warlock: Master of the Arcane.

Come il gioco sceglie l'icona di un perk (verificato sul file reale):

    nome del perk  ->  FrameLabel di un frame di uno sprite (DefineSprite)
                   ->  oggetto (shape) piazzato in quel frame
                   ->  fill bitmap della shape = id di un DefineSubImage
                   ->  rettangolo (x1,y1,x2,y2) di un atlante .dds (DefineExternalImage2)

Per dare un'icona a un perk che non ha frame si aggiunge un frame in coda allo sprite
che contiene gli altri perk dello stesso tipo, con la label uguale al nome del perk.

Questo modulo non dipende da tkinter e non ha effetti collaterali all'import.
Solo GFX non compresso ('GFX'); i 'CFX' (zlib) vengono rifiutati con un errore chiaro.
"""

from __future__ import annotations

import struct
from collections import Counter
from dataclasses import dataclass, field
from typing import Dict, Iterator, List, Optional, Tuple

# codici tag SWF / GFX usati
T_END = 0
T_SHOWFRAME = 1
T_DEFINESHAPE = 2
T_PLACEOBJECT = 4
T_DEFINESHAPE2 = 22
T_PLACEOBJECT2 = 26
T_REMOVEOBJECT2 = 28
T_DEFINESHAPE3 = 32
T_DEFINESPRITE = 39
T_FRAMELABEL = 43
T_DEFINESHAPE4 = 83
T_SUBIMAGE = 1008
T_EXTIMAGE2 = 1009

SHAPE_TAGS = (T_DEFINESHAPE, T_DEFINESHAPE2, T_DEFINESHAPE3, T_DEFINESHAPE4)
NO_BITMAP = 0xFFFF  # segnaposto "nessun bitmap" nei fill style


class GfxError(Exception):
    """File GFX non riconosciuto o modifica non applicabile."""


# ---------------------------------------------------------------------------
# Tag e lettura bit
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class Tag:
    code: int
    start: int   # offset dell'header del tag
    body: int    # offset del corpo
    length: int  # lunghezza del corpo

    @property
    def end(self) -> int:
        return self.body + self.length


def iter_tags(data: bytes, pos: int, end: int) -> Iterator[Tag]:
    """Scorre i tag in data[pos:end]; si ferma dopo un End tag."""
    while pos + 2 <= end:
        start = pos
        header = struct.unpack_from("<H", data, pos)[0]
        pos += 2
        code, length = header >> 6, header & 0x3F
        if length == 0x3F:
            if pos + 4 > end:
                raise GfxError("Tag troncato (lunghezza lunga oltre la fine).")
            length = struct.unpack_from("<I", data, pos)[0]
            pos += 4
        if pos + length > end:
            raise GfxError(f"Tag {code} troncato: serve {length} byte, ne restano {end - pos}.")
        yield Tag(code, start, pos, length)
        pos += length
        if code == T_END:
            return


class _Bits:
    def __init__(self, data: bytes, pos: int) -> None:
        self.data, self.pos, self.bit = data, pos, 0

    def read(self, n: int, signed: bool = False) -> int:
        v = 0
        for _ in range(n):
            try:
                byte = self.data[self.pos]
            except IndexError as exc:
                raise GfxError("Dati bit oltre la fine del tag.") from exc
            v = (v << 1) | ((byte >> (7 - self.bit)) & 1)
            self.bit += 1
            if self.bit == 8:
                self.bit = 0
                self.pos += 1
        if signed and n and v >> (n - 1):
            v -= 1 << n
        return v

    def align(self) -> int:
        if self.bit:
            self.bit = 0
            self.pos += 1
        return self.pos


def _rect(data: bytes, pos: int) -> Tuple[Tuple[int, int, int, int], int]:
    r = _Bits(data, pos)
    n = r.read(5)
    xmin, xmax, ymin, ymax = (r.read(n, True) for _ in range(4))
    return (xmin, xmax, ymin, ymax), r.align()


def _matrix(data: bytes, pos: int) -> int:
    r = _Bits(data, pos)
    if r.read(1):
        n = r.read(5)
        r.read(n), r.read(n)
    if r.read(1):
        n = r.read(5)
        r.read(n), r.read(n)
    n = r.read(5)
    r.read(n, True), r.read(n, True)
    return r.align()


# ---------------------------------------------------------------------------
# Modello
# ---------------------------------------------------------------------------

@dataclass
class SubImage:
    id: int
    atlas: int  # id dell'immagine esterna (atlante)
    x1: int
    y1: int
    x2: int
    y2: int

    @property
    def w(self) -> int:
        return self.x2 - self.x1

    @property
    def h(self) -> int:
        return self.y2 - self.y1


@dataclass
class Atlas:
    id: int
    filename: str
    width: int
    height: int


@dataclass
class ShapeInfo:
    id: int
    tag: Tag
    bitmaps: List[int]            # id bitmap dei fill style (0xFFFF escluso)
    size_px: Tuple[float, float]  # dimensione del riquadro della shape, in pixel

    @property
    def subimage(self) -> Optional[int]:
        return self.bitmaps[0] if self.bitmaps else None


@dataclass
class FrameInfo:
    sprite: int
    number: int                   # 1-based
    label: Optional[str] = None
    char: Optional[int] = None    # ultimo oggetto piazzato nel frame (None = nessuno)
    depth: Optional[int] = None
    place_tag: Optional[Tag] = None


@dataclass
class SpriteInfo:
    id: int
    tag: Tag
    declared_frames: int
    frames: List[FrameInfo] = field(default_factory=list)
    end_tag: Optional[Tag] = None


def _parse_shape(data: bytes, tag: Tag) -> ShapeInfo:
    sid = struct.unpack_from("<H", data, tag.body)[0]
    bounds, p = _rect(data, tag.body + 2)
    if tag.code == T_DEFINESHAPE4:
        _, p = _rect(data, p)
        p += 1  # flag
    rgba = tag.code in (T_DEFINESHAPE3, T_DEFINESHAPE4)
    n = data[p]
    p += 1
    if n == 0xFF and tag.code != T_DEFINESHAPE:
        n = struct.unpack_from("<H", data, p)[0]
        p += 2
    bitmaps: List[int] = []
    for _ in range(n):
        t = data[p]
        p += 1
        if t == 0x00:
            p += 4 if rgba else 3
        elif t in (0x10, 0x12, 0x13):
            p = _matrix(data, p)
            ng = data[p] & 0x0F
            p += 1 + ng * (1 + (4 if rgba else 3))
            if t == 0x13:
                p += 2
        elif 0x40 <= t <= 0x43:
            bid = struct.unpack_from("<H", data, p)[0]
            p += 2
            p = _matrix(data, p)
            if bid != NO_BITMAP:
                bitmaps.append(bid)
        else:
            raise GfxError(f"Fill style {t:#x} sconosciuto nella shape {sid}.")
    xmin, xmax, ymin, ymax = bounds
    return ShapeInfo(sid, tag, bitmaps, ((xmax - xmin) / 20.0, (ymax - ymin) / 20.0))


def _parse_sprite(data: bytes, tag: Tag) -> SpriteInfo:
    sid, nframes = struct.unpack_from("<HH", data, tag.body)
    sp = SpriteInfo(sid, tag, nframes)
    cur = FrameInfo(sid, 1)
    for t in iter_tags(data, tag.body + 4, tag.end):
        if t.code == T_FRAMELABEL:
            cur.label = data[t.body:t.end].split(b"\0", 1)[0].decode("latin-1")
        elif t.code == T_PLACEOBJECT2:
            flags = data[t.body]
            if flags & 0x02:  # HasCharacter
                cur.depth, cur.char = struct.unpack_from("<HH", data, t.body + 1)
                cur.place_tag = t
        elif t.code == T_PLACEOBJECT:
            cur.char, cur.depth = struct.unpack_from("<HH", data, t.body)
            cur.place_tag = t
        elif t.code == T_SHOWFRAME:
            sp.frames.append(cur)
            cur = FrameInfo(sid, cur.number + 1)
        elif t.code == T_END:
            sp.end_tag = t
    return sp


class GfxIcons:
    """c_icons.gfx letto in strutture; `data` non viene mai modificato."""

    def __init__(self, data: bytes) -> None:
        if data[:3] == b"CFX":
            raise GfxError("GFX compresso (CFX): non supportato, serve un GFX non compresso.")
        if data[:3] != b"GFX":
            raise GfxError("Firma 'GFX' non trovata: non è un file GFX.")
        if len(data) < 12 or struct.unpack_from("<I", data, 4)[0] != len(data):
            raise GfxError("Lunghezza dichiarata diversa da quella reale: file corrotto?")
        self.data = bytes(data)
        _, p = _rect(self.data, 8)
        self.first_tag = p + 4  # frame rate + frame count
        self.tags: List[Tag] = list(iter_tags(self.data, self.first_tag, len(self.data)))
        if not self.tags or self.tags[-1].code != T_END:
            raise GfxError("End tag finale mancante.")

        self.atlases: Dict[int, Atlas] = {}
        self.subimages: Dict[int, SubImage] = {}
        self.shapes: Dict[int, ShapeInfo] = {}
        self.sprites: Dict[int, SpriteInfo] = {}
        self.shape_errors: List[str] = []
        for t in self.tags:
            if t.code == T_EXTIMAGE2:
                self._parse_atlas(t)
            elif t.code == T_SUBIMAGE:
                s = SubImage(*struct.unpack_from("<6H", self.data, t.body))
                self.subimages[s.id] = s
            elif t.code in SHAPE_TAGS:
                try:
                    sh = _parse_shape(self.data, t)
                    self.shapes[sh.id] = sh
                except (GfxError, struct.error, IndexError) as exc:
                    self.shape_errors.append(f"tag {t.code} @ {t.start}: {exc}")
            elif t.code == T_DEFINESPRITE:
                sp = _parse_sprite(self.data, t)
                self.sprites[sp.id] = sp

        self._shape_of_sub: Dict[int, List[int]] = {}
        for sh in self.shapes.values():
            for b in sh.bitmaps:
                self._shape_of_sub.setdefault(b, []).append(sh.id)

    # ------------------------------------------------------------------
    def _parse_atlas(self, t: Tag) -> None:
        b = self.data
        aid = struct.unpack_from("<H", b, t.body)[0]
        w, h = struct.unpack_from("<HH", b, t.body + 6)
        n = b[t.body + 11]
        name = b[t.body + 12:t.body + 12 + n].decode("latin-1")
        self.atlases[aid] = Atlas(aid, name, w, h)

    # ------------------------------------------------------------------
    # Interrogazioni
    # ------------------------------------------------------------------
    def labels(self) -> Dict[str, FrameInfo]:
        """label -> frame (se una label compare più volte vince l'ultima)."""
        out: Dict[str, FrameInfo] = {}
        for sp in self.sprites.values():
            for fr in sp.frames:
                if fr.label:
                    out[fr.label] = fr
        return out

    def shapes_for_subimage(self, sub_id: int) -> List[int]:
        return list(self._shape_of_sub.get(sub_id, []))

    def subimage_of_shape(self, shape_id: Optional[int]) -> Optional[SubImage]:
        sh = self.shapes.get(shape_id) if shape_id is not None else None
        if sh is None or sh.subimage is None:
            return None
        return self.subimages.get(sh.subimage)

    def usable_icons(self, atlas_id: int) -> List[Tuple[SubImage, ShapeInfo]]:
        """Icone dell'atlante già pronte all'uso: una voce per ogni shape che usa un ritaglio."""
        out: List[Tuple[SubImage, ShapeInfo]] = []
        for shape_id in sorted(self.shapes):
            sh = self.shapes[shape_id]
            s = self.subimages.get(sh.subimage) if sh.subimage is not None else None
            if s is not None and s.atlas == atlas_id:
                out.append((s, sh))
        return out

    def reference_size(self, sprite_id: int) -> Optional[Tuple[float, float]]:
        """Dimensione (px) più comune delle icone con label in uno sprite."""
        sizes = Counter(
            self.shapes[f.char].size_px
            for f in self.sprites[sprite_id].frames
            if f.label and f.char in self.shapes and self.shapes[f.char].bitmaps
        )
        return sizes.most_common(1)[0][0] if sizes else None

    def sprite_for_label(self, label: str) -> SpriteInfo:
        """Sprite che contiene le label più simili (stesso prefisso fino al primo '_')."""
        prefix = label.split("_", 1)[0] + "_" if "_" in label else label
        best: Optional[SpriteInfo] = None
        best_n = 0
        for sp in sorted(self.sprites.values(), key=lambda s: s.id):
            n = sum(1 for f in sp.frames if f.label and f.label.lower().startswith(prefix.lower()))
            if n > best_n:
                best, best_n = sp, n
        if best is None:
            raise GfxError(
                f"Nessuno sprite contiene label con prefisso '{prefix}': "
                "indica lo sprite a mano (sprite_id)."
            )
        return best

    # ------------------------------------------------------------------
    # Modifica
    # ------------------------------------------------------------------
    def set_perk_icon(self, label: str, shape_id: int, sprite_id: Optional[int] = None) -> bytes:
        """Ritorna i nuovi byte del GFX con `label` collegata a `shape_id`.

        - label già esistente: cambia solo l'id della shape nel frame (stessa lunghezza);
        - label nuova: aggiunge un frame in coda allo sprite dei perk dello stesso tipo.
        """
        label = label.strip()
        if not label or "\0" in label or not label.isascii():
            raise GfxError("La label deve essere testo ASCII non vuoto.")
        if shape_id not in self.shapes:
            raise GfxError(f"La shape {shape_id} non esiste in questo GFX.")
        if not self.shapes[shape_id].bitmaps:
            raise GfxError(f"La shape {shape_id} non usa nessun ritaglio (non è un'icona).")

        existing = self.labels().get(label)
        if existing is not None:
            return self._retarget(existing, shape_id)
        return self._append_frame(label, shape_id, sprite_id)

    def _retarget(self, fr: FrameInfo, shape_id: int) -> bytes:
        t = fr.place_tag
        if t is None:
            raise GfxError(f"Il frame '{fr.label}' non piazza nessun oggetto da sostituire.")
        off = t.body + (3 if t.code == T_PLACEOBJECT2 else 0)
        buf = bytearray(self.data)
        struct.pack_into("<H", buf, off, shape_id)
        return bytes(buf)

    def _append_frame(self, label: str, shape_id: int, sprite_id: Optional[int]) -> bytes:
        sp = self.sprites.get(sprite_id) if sprite_id is not None else self.sprite_for_label(label)
        if sp is None:
            raise GfxError(f"Lo sprite {sprite_id} non esiste.")
        if sp.end_tag is None:
            raise GfxError(f"Lo sprite {sp.id} non ha un End tag.")
        depths = Counter(f.depth for f in sp.frames if f.label and f.depth is not None)
        if not depths:
            raise GfxError(f"Lo sprite {sp.id} non ha frame con label e oggetto da cui copiare il depth.")
        depth = depths.most_common(1)[0][0]

        lab = label.encode("latin-1") + b"\0"
        new_tags = (
            # RemoveObject2: toglie quello che il frame precedente lascia al depth
            struct.pack("<HH", (T_REMOVEOBJECT2 << 6) | 2, depth)
            # FrameLabel (header lungo, come negli altri frame)
            + struct.pack("<HI", (T_FRAMELABEL << 6) | 0x3F, len(lab)) + lab
            # PlaceObject2: nuovo oggetto (flags 0x06 = carattere + matrice), matrice identità
            + struct.pack("<HBHHB", (T_PLACEOBJECT2 << 6) | 6, 0x06, depth, shape_id, 0x00)
            + struct.pack("<H", T_SHOWFRAME << 6)
        )
        sprite_tag = sp.tag
        body = bytearray(self.data[sprite_tag.body:sprite_tag.end])
        cut = sp.end_tag.start - sprite_tag.body
        body[cut:cut] = new_tags
        struct.pack_into("<H", body, 2, sp.declared_frames + 1)
        if len(body) < 0x3F:
            header = struct.pack("<H", (T_DEFINESPRITE << 6) | len(body))
        else:
            header = struct.pack("<HI", (T_DEFINESPRITE << 6) | 0x3F, len(body))
        out = bytearray(self.data[:sprite_tag.start] + header + bytes(body) + self.data[sprite_tag.end:])
        struct.pack_into("<I", out, 4, len(out))
        return bytes(out)


# ---------------------------------------------------------------------------
# API di alto livello
# ---------------------------------------------------------------------------

def apply_assignments(data: bytes, assignments: Dict[str, int]) -> bytes:
    """Applica {label: shape_id} in sequenza e verifica ogni passo rileggendo il risultato."""
    cur = data
    for label, shape in assignments.items():
        before = GfxIcons(cur)
        new = before.set_perk_icon(label, shape)
        verify_change(before, GfxIcons(new), label, shape)
        cur = new
    return cur


def verify_change(before: GfxIcons, after: GfxIcons, label: str, shape_id: int) -> None:
    """Controlla che la modifica sia quella voluta e non abbia toccato altro."""
    if after.shape_errors:
        raise GfxError("Dopo la modifica alcune shape non si leggono più: " + after.shape_errors[0])
    lab = after.labels().get(label)
    if lab is None or lab.char != shape_id:
        raise GfxError(f"Verifica fallita: la label '{label}' non punta alla shape {shape_id}.")
    old_labels = before.labels()
    new_labels = after.labels()
    for name, fr in old_labels.items():
        if name == label:
            continue
        nf = new_labels.get(name)
        if nf is None or nf.char != fr.char or nf.number != fr.number or nf.sprite != fr.sprite:
            raise GfxError(f"Verifica fallita: il frame '{name}' è cambiato.")
    if set(new_labels) - set(old_labels) - {label}:
        raise GfxError("Verifica fallita: comparse label inattese.")
    if set(before.shapes) != set(after.shapes) or set(before.subimages) != set(after.subimages):
        raise GfxError("Verifica fallita: shape o ritagli cambiati.")
    if before.atlases != after.atlases:
        raise GfxError("Verifica fallita: gli atlanti sono cambiati.")
    if struct.unpack_from("<I", after.data, 4)[0] != len(after.data):
        raise GfxError("Verifica fallita: lunghezza del file incoerente.")
    # tutto ciò che sta fuori dagli sprite modificati deve restare identico byte per byte
    top_before = [(t.code, before.data[t.start:t.end]) for t in before.tags if t.code != T_DEFINESPRITE]
    top_after = [(t.code, after.data[t.start:t.end]) for t in after.tags if t.code != T_DEFINESPRITE]
    if top_before != top_after:
        raise GfxError("Verifica fallita: tag fuori dagli sprite modificati.")
