"""Aggiunta di chiavi nuove al locdata.md binario ('mdmp') di Warlock.

Formato ricostruito per analisi (NON verificato nel gioco):

  0   'mdmp'
  4   u32 A (803220)  - significato ignoto, lasciato invariato
  8   u32 B (1252)    - significato ignoto, lasciato invariato
  12  u32 nkeys       - numero di chiavi
  16  u32 N           - capacità del vettore V1 (13313)
  20  V1: N * u64     - per la chiave i: V1[2i]   = pos(chiave)   = bucket + NB*rank
                                         V1[2i+1] = pos(testo)    = bucket + NB*rank
                        (slot oltre 2*nkeys = 0xffffffff)
  ... V2: N * u64     - vuoto (0xffffffff)
  K   = 20 + 16*N     - inizio "heap": i puntatori sono relativi a K
  K   u32 NB, u32 NB  - numero di bucket (16641)
  K+8 NB bucket da 56 byte: u32 count, u32 cap(=4), 4 slot da 12 byte
                        slot = (ptr, len, x)   x = indice chiave, 0xffffffff per i testi
  R   u32 ocount, u32 ocap(=64), ocap slot da 12 byte: overflow (rank >= 4), in ordine
  size_pos u32 size (= byte tabella stringhe + 1), poi 5 byte 00 00 0c 00 00
  S   tabella stringhe: '#CHIAVE\\0testo\\0...'; i testi sono UNICI (le chiavi
      senza testo puntano al testo di un'altra chiave tramite V1)
  poi padding di zeri fino alla coda ('en').

  bucket(s) = h(s) % NB, con h = (h*31 + byte_con_segno) mod 2^32 sui byte UTF-8
  (compreso il '#' iniziale delle chiavi).
  pos = bucket + NB*j: j in 0..3 = slot nel bucket; j >= 4 = voce (j-4) della
  lista di overflow (indice globale). Il primo slot del bucket 0 è la stringa vuota.
  I bucket si riempiono in ordine di inserimento (ordine della tabella stringhe).
"""

from __future__ import annotations

import struct
from typing import Dict, List, Optional, Tuple

EMPTY = 0xFFFFFFFF
BUCKET_BYTES = 56
SLOT_BYTES = 12
ANCHOR = b"\x00\x00\x0c\x00\x00"


class LocdataKeysError(Exception):
    pass


def str_hash(b: bytes) -> int:
    h = 0
    for c in b:
        h = (h * 31 + (c - 256 if c > 127 else c)) & 0xFFFFFFFF
    return h


class Layout:
    def __init__(self, data: bytes) -> None:
        if data[:4] != b"mdmp":
            raise LocdataKeysError("Non è un locdata binario (manca 'mdmp').")
        u32 = lambda o: struct.unpack_from("<I", data, o)[0]
        self.nkeys = u32(12)
        self.N = u32(16)
        self.v1 = 20
        self.K = 20 + 16 * self.N
        self.NB = u32(self.K)
        self.bucket0 = self.K + 8
        self.R = self.bucket0 + self.NB * BUCKET_BYTES
        self.ocount = u32(self.R)
        self.ocap = u32(self.R + 4)
        self.oslots = self.R + 8
        self.size_pos = self.oslots + self.ocap * SLOT_BYTES
        if data[self.size_pos + 4 : self.size_pos + 9] != ANCHOR:
            raise LocdataKeysError("Struttura inattesa dopo la tabella overflow.")
        self.size = u32(self.size_pos)
        self.S = self.size_pos + 9
        self.table_end = self.S + self.size - 1  # primo byte dopo l'ultimo terminatore
        # inizio della coda (u32 2, u32 5, 'en'): primo byte non zero dopo la tabella
        tail = self.table_end + 1
        while tail < len(data) and data[tail] == 0:
            tail += 1
        self.tail = tail


def _s_at(data: bytes, L: Layout, ptr: int, ln: int) -> bytes:
    return data[L.K + ptr : L.K + ptr + ln]


def resolve(data: bytes, L: Layout, pos: int) -> Optional[Tuple[int, int, int, bytes]]:
    """pos (bucket + NB*j) -> (ptr, len, x, stringa)."""
    b, j = pos % L.NB, pos // L.NB
    if j < 4:
        o = L.bucket0 + b * BUCKET_BYTES
        if j >= struct.unpack_from("<I", data, o)[0]:
            return None
        p, l, x = struct.unpack_from("<III", data, o + 8 + SLOT_BYTES * j)
    else:
        if j - 4 >= L.ocount:
            return None
        p, l, x = struct.unpack_from("<III", data, L.oslots + SLOT_BYTES * (j - 4))
    return p, l, x, _s_at(data, L, p, l)


def iter_entries(data: bytes, L: Layout):
    """Tutte le entry come (pos, ptr, len, x, stringa)."""
    for b in range(L.NB):
        o = L.bucket0 + b * BUCKET_BYTES
        count = struct.unpack_from("<I", data, o)[0]
        for j in range(count):
            p, l, x = struct.unpack_from("<III", data, o + 8 + SLOT_BYTES * j)
            yield b + L.NB * j, p, l, x, _s_at(data, L, p, l)
    for i in range(L.ocount):
        p, l, x = struct.unpack_from("<III", data, L.oslots + SLOT_BYTES * i)
        s = _s_at(data, L, p, l)
        yield str_hash(s) % L.NB + L.NB * (4 + i), p, l, x, s


def lookup(data: bytes, key: str) -> Optional[str]:
    """Simula la ricerca: chiave (senza '#') -> testo, o None."""
    L = Layout(data)
    kb = b"#" + key.upper().encode("utf-8")
    b = str_hash(kb) % L.NB
    cands = [(p, l, x, s) for pos, p, l, x, s in iter_entries(data, L) if pos % L.NB == b]
    for p, l, x, s in cands:
        if s == kb and x != EMPTY:
            vpos = struct.unpack_from("<Q", data, L.v1 + 8 * (2 * x + 1))[0]
            r = resolve(data, L, vpos)
            return r[3].decode("utf-8") if r else None
    return None


def check_consistency(data: bytes) -> List[str]:
    """Controlla che tabelle e tabella stringhe siano coerenti. Lista vuota = ok."""
    L = Layout(data)
    issues: List[str] = []
    keys_by_idx: Dict[int, Tuple[int, bytes]] = {}
    for pos, p, l, x, s in iter_entries(data, L):
        # solo le chiavi devono stare nel bucket giusto: i testi modificati sul posto
        # (stessa lunghezza) restano dove sono e il gioco li raggiunge via V1.
        if l and x != EMPTY and str_hash(s) % L.NB != pos % L.NB:
            issues.append(f"bucket sbagliato per {s[:30]!r}")
        if x != EMPTY:
            keys_by_idx[x] = (pos, s)
    if len(keys_by_idx) != L.nkeys:
        issues.append(f"chiavi in tabella {len(keys_by_idx)} != nkeys {L.nkeys}")
    for i in range(L.nkeys):
        if i not in keys_by_idx:
            issues.append(f"chiave {i} assente dai bucket")
            continue
        pos, s = keys_by_idx[i]
        a, vb = struct.unpack_from("<QQ", data, L.v1 + 16 * i)
        if a != pos:
            issues.append(f"V1[{2*i}] incoerente per {s[:30]!r}")
        r = resolve(data, L, vb)
        if r is None or not r[1] or r[3].startswith(b"#"):
            issues.append(f"V1[{2*i+1}] non punta a un testo per {s[:30]!r}")
    for j in range(2 * L.nkeys, L.N):
        if struct.unpack_from("<Q", data, L.v1 + 8 * j)[0] != EMPTY:
            issues.append(f"V1[{j}] dovrebbe essere vuoto")
            break
    return issues


def apply_changes(data: bytes, changes: Dict[str, str]) -> bytes:
    """Applica cambi di testo (chiavi esistenti) e chiavi nuove SENZA spostare nulla.

    - chiave esistente: il nuovo testo viene aggiunto in coda alla tabella stringhe e la
      coppia V1 della chiave viene puntata lì (il vecchio testo resta, inutilizzato);
      lunghezza libera, e cambia solo quella chiave anche se il testo era condiviso.
    - chiave nuova: aggiunta in coda (chiave + testo) come prima.
    changes = {CHIAVE: testo}.
    """
    L = Layout(data)
    if not changes:
        return data
    buf = bytearray(data)

    key_idx: Dict[bytes, int] = {}
    text_pos: Dict[bytes, int] = {}  # testo esistente -> pos
    for pos, p, l, x, s in iter_entries(data, L):
        if x != EMPTY:
            key_idx[s] = x
        elif l and not s.startswith(b"#"):
            text_pos.setdefault(s, pos)

    new_keys = [k for k in changes if b"#" + k.upper().encode("utf-8") not in key_idx]
    if L.nkeys + len(new_keys) > L.N // 2:
        raise LocdataKeysError(
            f"Troppe chiavi nuove: spazio per {L.N // 2 - L.nkeys} senza ampliare V1."
        )

    cursor = L.table_end
    nkeys = L.nkeys
    ocount = L.ocount

    def put_entry(s: bytes, x: int) -> int:
        nonlocal cursor, ocount
        if cursor + len(s) + 2 > L.tail:
            raise LocdataKeysError("Spazio esaurito nella tabella stringhe.")
        buf[cursor : cursor + len(s)] = s
        buf[cursor + len(s)] = 0
        ptr = cursor - L.K
        cursor += len(s) + 1
        b = str_hash(s) % L.NB
        o = L.bucket0 + b * BUCKET_BYTES
        count = struct.unpack_from("<I", buf, o)[0]
        ent = struct.pack("<III", ptr, len(s), x)
        if count < 4:
            buf[o + 8 + SLOT_BYTES * count : o + 8 + SLOT_BYTES * (count + 1)] = ent
            struct.pack_into("<I", buf, o, count + 1)
            return b + L.NB * count
        if ocount >= L.ocap:
            raise LocdataKeysError("Overflow pieno: troppe modifiche in questo file.")
        buf[L.oslots + SLOT_BYTES * ocount : L.oslots + SLOT_BYTES * (ocount + 1)] = ent
        ocount += 1
        return b + L.NB * (4 + ocount - 1)

    def text_position(tb: bytes) -> int:
        if tb in text_pos:
            return text_pos[tb]
        pos = put_entry(tb, EMPTY)
        text_pos[tb] = pos
        return pos

    for key, text in changes.items():
        ks = b"#" + key.upper().encode("utf-8")
        tb = text.encode("utf-8")
        if not tb:
            raise LocdataKeysError(f"{key}: testo vuoto non supportato.")
        if b"\x00" in tb:
            raise LocdataKeysError(f"{key}: il testo contiene byte nulli.")
        if ks in key_idx:  # esistente: ripunta il testo
            x = key_idx[ks]
            cur = resolve(bytes(buf), L, struct.unpack_from("<Q", buf, L.v1 + 16 * x + 8)[0])
            if cur is not None and cur[3] == tb:
                continue
            struct.pack_into("<Q", buf, L.v1 + 16 * x + 8, text_position(tb))
        else:  # nuova
            kpos = put_entry(ks, nkeys)
            key_idx[ks] = nkeys
            struct.pack_into("<QQ", buf, L.v1 + 16 * nkeys, kpos, text_position(tb))
            nkeys += 1

    struct.pack_into("<I", buf, 12, nkeys)
    struct.pack_into("<I", buf, L.R, ocount)
    struct.pack_into("<I", buf, L.size_pos, cursor - L.S + 1)  # +1: NUL extra finale
    return bytes(buf)


def add_keys(data: bytes, new: Dict[str, str]) -> bytes:
    """Compatibilità: solo chiavi nuove (errore se una chiave esiste già)."""
    L = Layout(data)
    existing = {s for _, _, _, x, s in iter_entries(data, L) if x != EMPTY}
    for key in new:
        if b"#" + key.upper().encode("utf-8") in existing:
            raise LocdataKeysError(f"La chiave {key.upper()} esiste già.")
    return apply_changes(data, new)


def empty_template(data: bytes) -> bytes:
    """Stessa geometria del file dato (N, bucket, capacità pool) ma senza chiavi."""
    L = Layout(data)
    buf = bytearray(data)
    struct.pack_into("<I", buf, 12, 0)
    for j in range(L.N):
        struct.pack_into("<Q", buf, L.v1 + 8 * j, EMPTY)
    empty_slot = struct.pack("<III", 0, 0, EMPTY)
    for b in range(L.NB):
        o = L.bucket0 + b * BUCKET_BYTES
        struct.pack_into("<II", buf, o, 0, 4)
        buf[o + 8 : o + BUCKET_BYTES] = empty_slot * 4
    # il primo slot del bucket 0 è la stringa vuota: punta a un byte NUL (fine ancora)
    o0 = L.bucket0
    struct.pack_into("<I", buf, o0, 1)
    buf[o0 + 8 : o0 + 8 + SLOT_BYTES] = struct.pack("<III", L.S - 1 - L.K, 0, EMPTY)
    struct.pack_into("<I", buf, L.R, 0)
    for i in range(L.ocap):
        buf[L.oslots + SLOT_BYTES * i : L.oslots + SLOT_BYTES * (i + 1)] = empty_slot
    buf[L.S : L.tail] = b"\x00" * (L.tail - L.S)
    struct.pack_into("<I", buf, L.size_pos, 1)
    return bytes(buf)


def build_small(vanilla: bytes, pairs: Dict[str, str]) -> bytes:
    """locdata con SOLO le chiavi date (sostituzioni di chiavi vanilla e chiavi nuove)."""
    return apply_changes(empty_template(vanilla), pairs)


def all_pairs(data: bytes) -> List[Tuple[str, str]]:
    """Tutte le chiavi del file con il testo risolto, in ordine di indice."""
    L = Layout(data)
    by_idx: Dict[int, bytes] = {}
    for pos, p, l, x, s in iter_entries(data, L):
        if x != EMPTY:
            by_idx[x] = s
    out: List[Tuple[str, str]] = []
    for i in range(L.nkeys):
        key = by_idx.get(i)
        if key is None:
            continue
        vpos = struct.unpack_from("<Q", data, L.v1 + 8 * (2 * i + 1))[0]
        r = resolve(data, L, vpos)
        text = r[3].decode("utf-8", "replace") if r else ""
        out.append((key[1:].decode("utf-8", "replace"), text))
    return out


if __name__ == "__main__":  # uso: python locdata_keys.py in.md out.md CHIAVE "testo" [CHIAVE "testo" ...]
    import sys

    if len(sys.argv) < 5 or len(sys.argv) % 2 == 0:
        raise SystemExit(__doc__.split("Formato")[0] + "\nUso: python locdata_keys.py in.md out.md CHIAVE \"testo\" [...]")
    with open(sys.argv[1], "rb") as f:
        src = f.read()
    pairs = dict(zip(sys.argv[3::2], sys.argv[4::2]))
    out = add_keys(src, pairs)
    problems = check_consistency(out)
    if problems:
        raise SystemExit("Incoerenze: " + "; ".join(problems[:3]))
    with open(sys.argv[2], "wb") as f:
        f.write(out)
    print(f"Scritto {sys.argv[2]}: +{len(pairs)} chiavi")