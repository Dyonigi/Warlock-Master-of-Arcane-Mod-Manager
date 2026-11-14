"""Lettura/scrittura del locdata.md binario di Warlock: Master of the Arcane.

Formato (ricavato per analisi, non documentato):
  - header 'mdmp' + parte binaria (tabelle hash, ~1.1 MB) -> NON viene toccata
  - [u32 LE] dimensione tabella stringhe (= len(tabella) + 1)
  - 5 byte  00 00 0c 00 00
  - tabella stringhe UTF-8, elementi separati da \\0:
        #CHIAVE \\0 valore \\0 #CHIAVE2 \\0 valore2 \\0 ...
    ci sono chiavi SENZA valore (la chiave successiva segue subito)
    i valori possono contenere \\n e '#'
  - un \\0 extra finale, poi padding di zeri e coda ('en', ecc.) -> non toccata

Strategia: si riscrive solo la tabella stringhe e si aggiorna il campo
dimensione; tutto il resto resta identico byte per byte.
"""

from __future__ import annotations

import re
import struct
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Tuple

try:  # stesso package (panels/) oppure accanto a questo file
    from .locdata_keys import Layout, LocdataKeysError, add_keys
except ImportError:  # pragma: no cover
    from locdata_keys import Layout, LocdataKeysError, add_keys

_ANCHOR = re.compile(rb"\x00\x00\x0c\x00\x00#")
_KEY_RE = re.compile(r"^[A-Z0-9_]+$")


class LocdataFormatError(Exception):
    pass


class LocdataLayoutError(Exception):
    """Modifica che sposterebbe i byte del file (il gioco poi va in crash)."""


@dataclass
class LocdataFile:
    prefix: bytes  # tutto fino alla tabella stringhe (incluso il campo dimensione)
    suffix: bytes  # tutto dopo la tabella stringhe (incluso il \0 extra)
    entries: List[Tuple[str, Optional[str]]]  # (chiave senza '#', valore o None)
    # layout originale: lunghezza in byte di ogni valore (None = chiave senza testo)
    slots: List[Optional[int]] = field(default_factory=list)
    keys0: List[str] = field(default_factory=list)
    # chiavi nuove aggiunte in questa sessione (testo libero): {CHIAVE: testo}
    new_keys: Dict[str, str] = field(default_factory=dict)

    # ------------------------------------------------------------------
    @classmethod
    def from_bytes(cls, data: bytes) -> "LocdataFile":
        if data[:4] != b"mdmp":
            raise LocdataFormatError("Header 'mdmp' non trovato: non è un locdata binario.")

        try:
            lay = Layout(data)  # percorre la struttura invece di cercare byte
        except (LocdataKeysError, struct.error) as exc:
            raise LocdataFormatError(f"Struttura non riconosciuta: {exc}") from exc
        start = lay.S
        size_pos = lay.size_pos
        size = lay.size

        end = start + size  # fine tabella (incluso \0 extra)
        if end > len(data) or data[end - 2 : end] != b"\x00\x00":
            raise LocdataFormatError(
                "Campo dimensione incoerente con la tabella stringhe "
                f"(size={size}); formato diverso da quello atteso."
            )

        table = data[start : end - 2]  # senza i due \0 finali
        items = table.split(b"\x00") if table else []

        entries: List[Tuple[str, Optional[str]]] = []
        i = 0
        while i < len(items):
            raw = items[i]
            if not raw.startswith(b"#"):
                raise LocdataFormatError(f"Atteso una chiave '#...' ma trovato: {raw[:40]!r}")
            key = raw[1:].decode("utf-8")
            value: Optional[str] = None
            if i + 1 < len(items) and not items[i + 1].startswith(b"#"):
                value = items[i + 1].decode("utf-8")
                i += 2
            else:
                i += 1
            entries.append((key, value))

        obj = cls(prefix=data[:start], suffix=data[end - 1 :], entries=entries)
        obj.slots = [None if v is None else len(v.encode("utf-8")) for _, v in entries]
        obj.keys0 = [k for k, _ in entries]
        return obj

    @classmethod
    def load(cls, path: str) -> "LocdataFile":
        with open(path, "rb") as f:
            return cls.from_bytes(f.read())

    # ------------------------------------------------------------------
    # Modifica che NON sposta i byte: il file contiene tabelle con posizioni
    # assolute, quindi cambiare la lunghezza di un testo fa crashare il gioco.
    def max_bytes(self, index: int) -> Optional[int]:
        """Byte disponibili per il testo di questa voce (None = nessun testo)."""
        return self.slots[index] if index < len(self.slots) else None

    def set_value(self, index: int, text: str) -> None:
        key, _old = self.entries[index]
        slot = self.max_bytes(index)
        if slot is None:
            raise LocdataLayoutError(
                f"'{key}' non ha un testo originale: non c'è spazio per aggiungerlo "
                "senza spostare il resto del file."
            )
        raw = text.encode("utf-8")
        if len(raw) > slot:
            raise LocdataLayoutError(
                f"Testo troppo lungo: {len(raw)} byte, massimo {slot} "
                "(la lunghezza originale). Accorcialo."
            )
        raw += b" " * (slot - len(raw))  # padding con spazi: lunghezza invariata
        self.entries[index] = (key, raw.decode("utf-8"))

    def check_layout(self) -> None:
        if len(self.entries) != len(self.slots):
            raise LocdataLayoutError("Chiavi aggiunte o eliminate: il layout del file cambierebbe.")
        for i, (key, value) in enumerate(self.entries):
            if key != self.keys0[i]:
                raise LocdataLayoutError(f"Chiave rinominata ('{self.keys0[i]}' -> '{key}').")
            n = None if value is None else len(value.encode("utf-8"))
            if n != self.slots[i]:
                raise LocdataLayoutError(f"'{key}': la lunghezza del testo è cambiata.")

    # ------------------------------------------------------------------
    # Chiavi nuove: aggiunte in coda e tabelle ricalcolate da locdata_keys.add_keys
    def add_new(self, key: str, text: str) -> str:
        key = key.strip().upper()
        if not _KEY_RE.match(key):
            raise LocdataLayoutError("La chiave può contenere solo A-Z, 0-9 e '_'.")
        if key in self.keys0 or key in self.new_keys:
            raise LocdataLayoutError(f"La chiave {key} esiste già.")
        if not text:
            raise LocdataLayoutError("Il testo non può essere vuoto.")
        candidate = dict(self.new_keys)
        candidate[key] = text
        self._apply_new(self._existing_bytes(True), candidate)  # prova a secco
        self.new_keys[key] = text
        return key

    def max_new_keys(self) -> int:
        """Quante chiavi nuove si possono ancora aggiungere (spazio in V1)."""
        total = len(self.entries) + len(self.new_keys)
        cap = struct.unpack_from("<I", self.prefix, 16)[0] // 2
        return max(0, cap - total)

    def set_new_text(self, key: str, text: str) -> None:
        if not text:
            raise LocdataLayoutError("Il testo non può essere vuoto.")
        candidate = dict(self.new_keys)
        candidate[key] = text
        self._apply_new(self._existing_bytes(True), candidate)
        self.new_keys[key] = text

    def remove_new(self, key: str) -> None:
        self.new_keys.pop(key, None)

    @staticmethod
    def _apply_new(base: bytes, new: Dict[str, str]) -> bytes:
        try:
            return add_keys(base, new)
        except LocdataKeysError as exc:
            raise LocdataLayoutError(str(exc)) from exc

    def to_bytes(self, strict: bool = True) -> bytes:
        base = self._existing_bytes(strict)
        if self.new_keys:
            base = self._apply_new(base, self.new_keys)
        return base

    def _existing_bytes(self, strict: bool = True) -> bytes:
        if strict:
            self.check_layout()
        parts: List[bytes] = []
        for key, value in self.entries:
            parts.append(b"#" + key.encode("utf-8") + b"\x00")
            if value is not None and value != "":
                parts.append(value.encode("utf-8") + b"\x00")
        table = b"".join(parts)  # termina con \0 dell'ultimo elemento
        size = len(table) + 1  # +1: \0 extra finale (incluso nel suffix)

        prefix = bytearray(self.prefix)
        struct.pack_into("<I", prefix, len(prefix) - 9, size)
        return bytes(prefix) + table + self.suffix

    def save(self, path: str) -> None:
        with open(path, "wb") as f:
            f.write(self.to_bytes())