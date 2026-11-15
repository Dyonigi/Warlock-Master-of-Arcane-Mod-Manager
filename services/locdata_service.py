"""Chiavi di testo (locdata.md) per gli editor: lettura e aggiunta/modifica nel workspace.
Nessun tkinter.

Il locdata del workspace è il file binario completo ('mdmp'); "Repack & install" lo applica a
l100.pack. Se il workspace non lo contiene, si parte da quello effettivo dei pack del gioco
(l100.pack, comprese eventuali modifiche già applicate)."""

from __future__ import annotations

import os
from typing import Callable, Dict, Iterable, Optional, Sequence

try:  # il modulo sta in panels/ nel progetto
    from panels.locdata_keys import LocdataKeysError, apply_changes, check_consistency, lookup
except ImportError:  # fuori dal progetto (test)
    from locdata_keys import LocdataKeysError, apply_changes, check_consistency, lookup

from services.icon_service import find_in_packs

LOCDATA_NAME = "locdata.md"
MAGIC = b"mdmp"
LogFn = Callable[[str], None]


class LocdataError(Exception):
    pass


def workspace_locdata(manifest: Dict[str, str]) -> Optional[str]:
    for orig, path in manifest.items():
        if orig.lower() == LOCDATA_NAME and os.path.isfile(path):
            return path
    return None


def read_current(manifest: Dict[str, str], pack_paths: Sequence[str]) -> bytes:
    path = workspace_locdata(manifest)
    if path:
        with open(path, "rb") as f:
            data = f.read()
    else:
        hit = find_in_packs(pack_paths, LOCDATA_NAME)
        if hit is None:
            raise LocdataError("locdata.md non trovato né nel workspace né nei pack del gioco.")
        data = hit[1]
    if not data.startswith(MAGIC):
        raise LocdataError("locdata.md non è nel formato binario atteso ('mdmp').")
    return data


def get_texts(data: bytes, keys: Iterable[str]) -> Dict[str, Optional[str]]:
    out: Dict[str, Optional[str]] = {}
    for k in keys:
        try:
            out[k] = lookup(data, k)
        except Exception:
            out[k] = None
    return out


def write_texts(
    workspace_dir: str,
    manifest: Dict[str, str],
    pack_paths: Sequence[str],
    pairs: Dict[str, str],
    log: Optional[LogFn] = None,
) -> str:
    """Aggiunge/modifica le chiavi nel locdata del workspace (lo crea se manca) e lo verifica."""
    if not pairs:
        raise LocdataError("Nessuna chiave da scrivere.")
    for k, t in pairs.items():
        if not t or not t.strip():
            raise LocdataError(f"Il testo di {k} non può essere vuoto.")
        if "\x00" in t:
            raise LocdataError(f"Il testo di {k} contiene byte nulli.")
    data = read_current(manifest, pack_paths)
    try:
        new = apply_changes(data, {k.upper(): t for k, t in pairs.items()})
        issues = check_consistency(new)
    except LocdataKeysError as exc:
        raise LocdataError(str(exc)) from exc
    if issues:
        raise LocdataError(f"locdata incoerente dopo la modifica: {issues[0]}")
    path = workspace_locdata(manifest) or os.path.join(workspace_dir, LOCDATA_NAME)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "wb") as f:
        f.write(new)
    manifest[LOCDATA_NAME] = path
    if log:
        log(f"locdata.md: scritte {len(pairs)} chiavi ({', '.join(sorted(pairs))}).")
    return path
