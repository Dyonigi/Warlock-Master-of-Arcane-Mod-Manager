#!/usr/bin/env python3
"""Scan, merge, unpack, pack and install Warlock mods.

NOTA su locdata.md: è un file BINARIO ('mdmp') che il gioco carica così com'è.
Non va mai convertito in testo: unpack e repack lo trattano come byte opachi e
lo si modifica solo con LocdataFile (locdata_file.py), che riscrive la tabella
stringhe lasciando intatto il resto.
"""

from __future__ import annotations

import hashlib
import os
import re
import shutil
import zlib

try:  # i moduli locdata_* possono stare in panels/ oppure accanto a project.py
    from panels.locdata_file import LocdataFile, LocdataFormatError
    from panels.locdata_keys import all_pairs, build_small, check_consistency
except ImportError:  # pragma: no cover
    from locdata_file import LocdataFile, LocdataFormatError
    from locdata_keys import all_pairs, build_small, check_consistency

LOCDATA_MAGIC = b"mdmp"


def _maybe_decompress(raw: bytes) -> bytes:
    """Se i byte sembrano zlib (primo byte 0x78) prova a decomprimerli."""
    if len(raw) >= 2 and raw[0] == 0x78:
        try:
            return zlib.decompress(raw)
        except zlib.error:
            return raw
    return raw


def parse_locdata_to_text(*_args, **_kwargs):
    raise RuntimeError(
        "parse_locdata_to_text è stata rimossa: la conversione locdata -> testo "
        "perdeva dati (chiavi corte, accenti, a capo). Togli questa chiamata: "
        "locdata.md deve restare binario."
    )


def write_locdata_from_text(*_args, **_kwargs):
    raise RuntimeError(
        "write_locdata_from_text è stata rimossa: scriveva testo nel pack e il "
        "gioco non lo legge. Togli questa chiamata: locdata.md deve restare binario."
    )


from dataclasses import dataclass
from typing import Callable, Dict, Iterable, List, Optional, Tuple

from catalog import VANILLA_PACKS, is_editable_data_file, next_mod_pack_name, pack_sort_key
from packio import list_pack, pack_dir, read_entry
from txml import is_txml, txml_to_xml_string, xml_string_to_txml


LogFn = Callable[[str], None]


def _log(log: Optional[LogFn], msg: str) -> None:
    if log:
        log(msg)


def file_sha1(path: str) -> str:
    h = hashlib.sha1()
    with open(path, "rb") as f:
        while True:
            chunk = f.read(1024 * 1024)
            if not chunk:
                break
            h.update(chunk)
    return h.hexdigest()


def bytes_sha1(data: bytes) -> str:
    return hashlib.sha1(data).hexdigest()


@dataclass
class PackInfo:
    path: str
    name: str
    size: int
    sha1: str
    files: List[str]
    vanilla: bool


@dataclass
class ModBundle:
    name: str
    path: str
    packs: List[str]
    notes: str = ""


@dataclass
class GameScan:
    game_dir: str
    all_packs: List[PackInfo]
    installed_mods: List[PackInfo]
    vanilla_packs: List[PackInfo]
    available_mods: List[ModBundle]


# ---------------------------------------------------------------------------
# Game scanning
# ---------------------------------------------------------------------------

def list_game_packs(game_dir: str) -> List[PackInfo]:
    packs: List[PackInfo] = []
    for name in os.listdir(game_dir):
        if not name.lower().endswith(".pack"):
            continue
        path = os.path.join(game_dir, name)
        try:
            entries = list_pack(path)
            files = [e.name for e in entries]
        except Exception:
            files = []
        packs.append(
            PackInfo(
                path=path,
                name=name,
                size=os.path.getsize(path),
                sha1=file_sha1(path),
                files=files,
                vanilla=name.lower() in VANILLA_PACKS,
            )
        )
    packs.sort(key=lambda p: pack_sort_key(p.name))
    return packs


def _read_notes(folder: str) -> str:
    bits: List[str] = []
    for candidate in ("descript.ion", "README.txt", "readme.txt", "changelog.txt"):
        path = os.path.join(folder, candidate)
        if os.path.isfile(path):
            try:
                text = open(path, "r", encoding="utf-8", errors="ignore").read().strip()
            except OSError:
                continue
            if text:
                bits.append(text[:2000])
    for name in os.listdir(folder):
        if name.lower().startswith("changelog") and name.lower().endswith(".txt"):
            path = os.path.join(folder, name)
            try:
                bits.append(open(path, "r", encoding="utf-8", errors="ignore").read()[:4000])
            except OSError:
                pass
            break
    return "\n\n".join(bits)


def scan_available_mods(mods_root: str) -> List[ModBundle]:
    bundles: List[ModBundle] = []
    if not os.path.isdir(mods_root):
        return bundles
    skip = {"warlock_mod_manager", "work", "__pycache__"}
    for name in sorted(os.listdir(mods_root)):
        if name in skip or name.startswith("."):
            continue
        path = os.path.join(mods_root, name)
        if os.path.isdir(path):
            packs = [
                os.path.join(path, f)
                for f in sorted(os.listdir(path))
                if f.lower().endswith(".pack")
            ]
            if packs:
                bundles.append(ModBundle(name=name, path=path, packs=packs, notes=_read_notes(path)))
        elif name.lower().endswith(".pack"):
            bundles.append(ModBundle(name=name, path=path, packs=[path], notes=""))
    return bundles


def scan_game(game_dir: str, mods_root: str) -> GameScan:
    packs = list_game_packs(game_dir)
    return GameScan(
        game_dir=game_dir,
        all_packs=packs,
        installed_mods=[p for p in packs if not p.vanilla],
        vanilla_packs=[p for p in packs if p.vanilla],
        available_mods=scan_available_mods(mods_root),
    )


# ---------------------------------------------------------------------------
# Workspace building
# ---------------------------------------------------------------------------

def merged_entries(
    pack_paths: Iterable[str],
    only_editable: bool = True,
    log: Optional[LogFn] = None,
) -> Dict[str, Tuple[str, bytes]]:
    """Later packs in pack_paths override earlier files with the same name."""
    merged: Dict[str, Tuple[str, bytes]] = {}
    ordered = sorted(pack_paths, key=lambda p: pack_sort_key(os.path.basename(p)))
    for pack_path in ordered:
        try:
            entries = list_pack(pack_path)
        except Exception as exc:
            _log(log, f"Could not read {pack_path}: {exc}")
            continue
        for entry in entries:
            if only_editable and not is_editable_data_file(entry.name):
                continue
            try:
                data = read_entry(pack_path, entry)
            except Exception as exc:
                _log(log, f"Skip {entry.name} from {os.path.basename(pack_path)}: {exc}")
                continue
            merged[entry.name] = (os.path.basename(pack_path), data)
        _log(log, f"Merged {os.path.basename(pack_path)} ({len(entries)} files)")
    return merged


def write_workspace(
    dest_dir: str,
    merged: Dict[str, Tuple[str, bytes]],
    convert_txml: bool = True,
    log: Optional[LogFn] = None,
) -> Dict[str, str]:
    """Write files into dest_dir. TXML binaries become <name>.xml for editing.

    Returns mapping of original packed name -> path of the file to edit.
    """
    if os.path.isdir(dest_dir):
        shutil.rmtree(dest_dir)
    os.makedirs(dest_dir, exist_ok=True)
    manifest: Dict[str, str] = {}
    for name, (_src, data) in sorted(merged.items()):
        if convert_txml and name.lower().endswith(".binary") and is_txml(data):
            xml_name = name + ".xml"
            xml_path = os.path.join(dest_dir, xml_name)
            try:
                xml_text = txml_to_xml_string(data)
            except Exception as exc:
                _log(log, f"TXML convert failed for {name}: {exc}; writing raw binary")
                out_path = os.path.join(dest_dir, name)
                with open(out_path, "wb") as f:
                    f.write(data)
                manifest[name] = out_path
                continue
            with open(xml_path, "w", encoding="utf-8") as f:
                f.write(xml_text)
            manifest[name] = xml_path
            _log(log, f"Converted {name} -> {xml_name}")
        else:
            out_path = os.path.join(dest_dir, name)
            with open(out_path, "wb") as f:
                f.write(data)
            manifest[name] = out_path
            _log(log, f"Wrote {name}")
    meta = os.path.join(dest_dir, "_manifest.txt")
    with open(meta, "w", encoding="utf-8") as f:
        for orig, path in sorted(manifest.items()):
            f.write(f"{orig}\t{os.path.basename(path)}\n")
    return manifest


def _locdata_for_pack(path: str, log: Optional[LogFn]) -> Optional[bytes]:
    """Legge locdata.md dal workspace e verifica che sia ancora il binario valido."""
    with open(path, "rb") as f:
        data = _maybe_decompress(f.read())
    if not data.startswith(LOCDATA_MAGIC):
        _log(log, "ERRORE: locdata.md nel workspace non è binario ('mdmp' mancante): "
                  "NON incluso nel pack. Ricarica il workspace dal pack vanilla.")
        return None
    try:
        issues = check_consistency(data)
    except Exception as exc:
        _log(log, f"ERRORE: locdata.md non valido ({exc}): NON incluso nel pack.")
        return None
    if issues:
        _log(log, f"ERRORE: locdata.md incoerente ({issues[0]}): NON incluso nel pack.")
        return None
    return data


def build_pack_from_workspace(
    workspace_dir: str,
    pack_path: str,
    selected_original_names: Optional[Iterable[str]] = None,
    log: Optional[LogFn] = None,
) -> str:
    staging = os.path.join(os.path.dirname(workspace_dir), "_pack_staging")
    if os.path.isdir(staging):
        shutil.rmtree(staging)
    os.makedirs(staging)

    wanted = set(selected_original_names) if selected_original_names is not None else None

    for name in sorted(os.listdir(workspace_dir)):
        if name.startswith("_"):
            continue
        path = os.path.join(workspace_dir, name)
        if not os.path.isfile(path):
            continue

        # --- LOCDATA: byte opachi, mai convertito ---
        if name == "locdata.loc":
            _log(log, "Ignorato locdata.loc (formato testuale obsoleto e lossy): "
                      "ricarica il workspace.")
            continue
        if name == "locdata.md":
            if wanted is not None and name not in wanted:
                continue
            data = _locdata_for_pack(path, log)
            if data is None:
                continue
            with open(os.path.join(staging, name), "wb") as f:
                f.write(data)
            _log(log, "Copied locdata.md (binario)")
            continue

        # --- TXML (.binary.xml) ---
        if name.endswith(".binary.xml"):
            original = name[: -len(".xml")]
            if wanted is not None and original not in wanted:
                continue
            with open(path, "r", encoding="utf-8") as f:
                xml_text = f.read()
            binary = xml_string_to_txml(xml_text)
            with open(os.path.join(staging, original), "wb") as f:
                f.write(binary)
            _log(log, f"Repacked TXML {original}")
            continue

        # --- file normali ---
        if wanted is not None and name not in wanted:
            continue
        shutil.copy2(path, os.path.join(staging, name))
        _log(log, f"Copied {name}")

    pack_dir(staging, pack_path)
    shutil.rmtree(staging, ignore_errors=True)
    _log(log, f"Created {pack_path}")
    return pack_path


L100_NAME = "l100.pack"


def patch_locdata_in_l100(workspace_dir: str, game_dir: str, log: Optional[LogFn] = None) -> bool:
    """Sostituisce locdata.md dentro l100.pack (il gioco legge il locdata da lì).

    - crea l100.pack.bak la prima volta e riparte SEMPRE da quel backup;
    - tutte le altre entry di l100.pack restano identiche byte per byte;
    - rifiuta di fare il backup se l100.pack non sembra l'originale.
    """
    from patch_pack import replace_in_pack

    src = os.path.join(workspace_dir, "locdata.md")
    if not os.path.isfile(src):
        _log(log, "locdata.md non trovato nel workspace: niente da applicare a l100.pack.")
        return False
    data = _locdata_for_pack(src, log)
    if data is None:
        return False

    pack = os.path.join(game_dir, L100_NAME)
    bak = pack + ".bak"
    if not os.path.isfile(pack):
        raise RuntimeError(f"{L100_NAME} non trovato in {game_dir}")

    if not os.path.exists(bak):
        names = [e.name for e in list_pack(pack)]
        if "locdata.md" not in names or len(names) < 2:
            raise RuntimeError(
                f"{L100_NAME} non sembra l'originale (entry: {names}). "
                "Ripristinalo (Steam: Verifica integrità file) prima di continuare."
            )
        shutil.copy2(pack, bak)
        _log(log, f"Backup creato: {os.path.basename(bak)}")

    tmp = pack + ".tmp"
    try:
        replace_in_pack(bak, "locdata.md", data, tmp)
        entries = {e.name: e for e in list_pack(tmp)}
        if read_entry(tmp, entries["locdata.md"]) != data:
            raise RuntimeError("Verifica fallita: locdata.md scritto non coincide.")
        os.replace(tmp, pack)
    finally:
        if os.path.exists(tmp):
            os.remove(tmp)
    _log(log, f"locdata.md applicato a {L100_NAME} (le altre entry sono invariate).")
    return True


def read_vanilla_locdata(game_dir: str) -> Optional[bytes]:
    """locdata.md vanilla da l100.pack (preferisce l100.pack.bak se esiste)."""
    pack = os.path.join(game_dir, "l100.pack")
    for cand in (pack + ".bak", pack):
        if not os.path.isfile(cand):
            continue
        for e in list_pack(cand):
            if e.name == "locdata.md":
                data = read_entry(cand, e)
                if data.startswith(LOCDATA_MAGIC):
                    return data
    return None


LOC_MARKER_NAME = "wmm_locdata.txt"  # riconosce i pack creati da questo manager
LOC_MARKER_TEXT = b"Warlock Mod Manager: pack locdata (solo chiavi cambiate o nuove)\n"
_LOC_PACK_RE = re.compile(r"^l(\d+)\.pack$", re.IGNORECASE)


def _l_pack_numbers(game_dir: str) -> Dict[str, int]:
    out: Dict[str, int] = {}
    for name in os.listdir(game_dir):
        m = _LOC_PACK_RE.match(name)
        if m:
            out[name] = int(m.group(1))
    return out


def next_locdata_pack_name(game_dir: str) -> str:
    """Primo l<N>.pack libero con N maggiore di tutti i pack l esistenti (almeno 101)."""
    nums = list(_l_pack_numbers(game_dir).values())
    return f"l{max([100] + nums) + 1}.pack"


def _is_manager_locdata_pack(path: str) -> bool:
    try:
        return {e.name for e in list_pack(path)} == {"locdata.md", LOC_MARKER_NAME}
    except Exception:
        return False


def install_locdata_pack(
    workspace_dir: str,
    game_dir: str,
    log: Optional[LogFn] = None,
    remove_old: bool = True,
) -> Optional[str]:
    """Installa il locdata.md del workspace come NUOVO pack l<N>.pack (mai sovrascrive).

    - l100.pack e i pack di altre mod non vengono toccati.
    - i pack precedenti creati da questo manager (marcati con wmm_locdata.txt) sono
      superati dal nuovo: se remove_old li elimina (errori ignorati);
    - le chiavi presenti nei vecchi pack nostri ma non più nel locdata (ripristinate)
      vengono scritte nel nuovo pack con il testo vanilla, così restano ripristinate
      anche se un vecchio pack non si riesce a eliminare.
    Ritorna il nome del pack creato, oppure None.
    """
    import tempfile

    src = os.path.join(workspace_dir, "locdata.md")
    if not os.path.isfile(src):
        _log(log, "locdata.md non trovato nel workspace: niente da installare.")
        return None
    data = _locdata_for_pack(src, log)
    if data is None:
        return None

    olds = sorted(
        name for name in _l_pack_numbers(game_dir)
        if _is_manager_locdata_pack(os.path.join(game_dir, name))
    )

    vanilla = read_vanilla_locdata(game_dir)
    if olds and vanilla is not None:
        try:
            mine = dict(all_pairs(data))
            vtext = dict(all_pairs(vanilla))
            reverts: Dict[str, str] = {}
            for name in olds:
                path = os.path.join(game_dir, name)
                entry = next(e for e in list_pack(path) if e.name == "locdata.md")
                for key, text in all_pairs(read_entry(path, entry)):
                    if key not in mine and key in vtext:
                        reverts[key] = vtext[key]
            if reverts:
                data = build_small(vanilla, {**reverts, **mine})
                _log(log, f"{len(reverts)} chiavi ripristinate scritte col testo vanilla nel nuovo pack.")
        except Exception as exc:  # non blocca l'installazione
            _log(log, f"Avviso: non ho potuto calcolare i ripristini ({exc}).")

    new_name = next_locdata_pack_name(game_dir)
    dest = os.path.join(game_dir, new_name)
    tmp_dir = tempfile.mkdtemp(prefix="locdata_pack_")
    tmp_pack = dest + ".tmp"
    try:
        with open(os.path.join(tmp_dir, "locdata.md"), "wb") as f:
            f.write(data)
        with open(os.path.join(tmp_dir, LOC_MARKER_NAME), "wb") as f:
            f.write(LOC_MARKER_TEXT)
        pack_dir(tmp_dir, tmp_pack)
        entries = {e.name: e for e in list_pack(tmp_pack)}
        if read_entry(tmp_pack, entries["locdata.md"]) != data:
            raise RuntimeError("Verifica fallita: locdata.md nel pack non coincide.")
        os.replace(tmp_pack, dest)
    finally:
        shutil.rmtree(tmp_dir, ignore_errors=True)
        if os.path.exists(tmp_pack):
            os.remove(tmp_pack)
    _log(log, f"locdata.md installato come {new_name} (l100.pack non modificato).")

    if remove_old:
        for name in olds:
            try:
                os.remove(os.path.join(game_dir, name))
                _log(log, f"Rimosso il pack precedente {name} (superato da {new_name}).")
            except OSError as exc:
                _log(log, f"Non rimosso {name}: {exc}. Resta, ma {new_name} lo supera.")
    return new_name


def restore_l100(game_dir: str, log: Optional[LogFn] = None) -> bool:
    pack = os.path.join(game_dir, L100_NAME)
    bak = pack + ".bak"
    if not os.path.isfile(bak):
        _log(log, "Nessun backup di l100.pack da ripristinare.")
        return False
    shutil.copy2(bak, pack)
    _log(log, f"{L100_NAME} ripristinato dal backup.")
    return True



def install_packs(pack_paths: Iterable[str], game_dir: str, log: Optional[LogFn] = None) -> List[str]:
    installed = []
    for src in pack_paths:
        dest = os.path.join(game_dir, os.path.basename(src))
        shutil.copy2(src, dest)
        installed.append(dest)
        _log(log, f"Installed {os.path.basename(src)}")
    return installed


def uninstall_packs(pack_names: Iterable[str], game_dir: str, log: Optional[LogFn] = None) -> None:
    for name in pack_names:
        if name.lower() in VANILLA_PACKS:
            _log(log, f"Refusing to delete vanilla pack {name}")
            continue
        path = os.path.join(game_dir, name)
        if os.path.isfile(path):
            os.remove(path)
            _log(log, f"Removed {name}")


def suggest_pack_name(game_dir: str) -> str:
    names = [n for n in os.listdir(game_dir) if n.lower().endswith(".pack")]
    return next_mod_pack_name(names)


# ---------------------------------------------------------------------------
# Localization (locdata.md)
# ---------------------------------------------------------------------------

def load_localization(locdata_path: str) -> Dict[str, str]:
    """locdata.md binario -> {CHIAVE_MAIUSCOLA: testo} (solo chiavi con testo)."""
    if not os.path.isfile(locdata_path):
        return {}
    with open(locdata_path, "rb") as f:
        raw = _maybe_decompress(f.read())
    if not raw.startswith(LOCDATA_MAGIC):
        return {}
    try:
        parsed = LocdataFile.from_bytes(raw)
    except LocdataFormatError:
        return {}
    out: Dict[str, str] = {}
    for key, value in parsed.entries:
        k = key.upper()
        if value and (k not in out or not out[k]):
            out[k] = value
    return out


# Category prefixes used by locdata keys. The empty string first tries the
# raw uppercased internal name, then each prefixed variant.
_LOC_PREFIXES = ("", "UNIT_", "PERK_", "ACT_", "SP_", "BLD_", "ASKS_")


def _candidate_keys(internal: str) -> List[str]:
    """Generate plausible locdata keys for an internal record name."""
    if not internal:
        return []
    up = internal.upper()
    out: List[str] = [up]
    for p in _LOC_PREFIXES[1:]:
        out.append(p + up)
    # If the internal name already carries a known prefix, try the bare suffix
    for p in _LOC_PREFIXES[1:]:
        if up.startswith(p):
            out.append(up[len(p):])
            break
    # Some records use e_ prefix for elves; strip that too as a long shot.
    if up.startswith("E_") and not up.startswith("E_E"):
        out.append("UNIT_" + up)
    return out


def localization_lookup(names: Dict[str, str], internal: str) -> str:
    """Resolve an internal name like 'perk_summon_unit' to its display string."""
    if not names or not internal:
        return ""
    for key in _candidate_keys(internal):
        if key in names and names[key]:
            return names[key]
    return ""


def localization_lookup_desc(names: Dict[str, str], internal: str) -> str:
    """Resolve the _DESC tooltip string for a record."""
    if not names or not internal:
        return ""
    up = internal.upper()
    for p in _LOC_PREFIXES[1:]:
        for key in (p + up + "_DESC", up + "_DESC"):
            if key in names and names[key]:
                return names[key]
    return ""