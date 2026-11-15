"""Test di archmage_schema / archmage_service / locdata_service sui file REALI.

Uso:  python test_archmage_schema.py [percorso\\fractions.binary.xml]
Cerca fractions.binary.xml anche in: variabile FRACTIONS_XML, cartella dello script,
work\\merged_all\\. Per i test locdata serve work\\merged_all\\_loc\\locdata.md (si salta se manca).
"""
import copy
import os
import shutil
import sys
import tempfile
import unittest
import xml.etree.ElementTree as ET

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)
import archmage_schema as am  # noqa: E402


def _find(names, extra=None):
    cands = [os.environ.get(extra)] if extra else []
    cands += [os.path.join(HERE, n) for n in names]
    cands += [os.path.join(HERE, "work", "merged_all", n) for n in names]
    return next((c for c in cands if c and os.path.isfile(c)), None)


if len(sys.argv) > 1 and sys.argv[1].lower().endswith(".xml"):
    os.environ["FRACTIONS_XML"] = sys.argv.pop(1)
PATH = _find(["fractions.binary.xml", "fractions_real.xml"], "FRACTIONS_XML")
LOC = _find([os.path.join("_loc", "locdata.md")])


def canon(e):
    return (e.tag, tuple(sorted(e.attrib.items())), (e.text or "").strip(), tuple(canon(c) for c in e))


@unittest.skipUnless(PATH, "fractions.binary.xml non trovato")
class Real(unittest.TestCase):
    def setUp(self):
        self.root = ET.fromstring(open(PATH, encoding="utf-8").read().replace("\r", ""))
        self.names = {i.name for i in am.read_improvements(self.root)}

    def test_roundtrip(self):
        for f, a in zip(am.fractions_section(self.root).findall("FractionData"), am.read_archmages(self.root)):
            self.assertEqual(canon(a.to_element(self.names)), canon(f), a.system_name)
        for e, i in zip(am.improvements_section(self.root).findall("Improvement"), am.read_improvements(self.root)):
            self.assertEqual(canon(i.to_element()), canon(e), i.name)

    def test_append_at_end_and_errors(self):
        a = copy.deepcopy(am.read_archmages(self.root)[4])
        a.system_name, a.name_key = "f_test", "#mage_f_test"
        n = len(am.read_archmages(self.root))
        pos = am.append_fraction(self.root, a.to_element(self.names))
        got = am.read_archmages(self.root)
        self.assertEqual((pos, len(got), got[-1].system_name), (n, n + 1, "f_test"))
        with self.assertRaises(am.ArchmageError):                       # doppione
            am.append_fraction(self.root, a.to_element(self.names))
        a.improvements = ["non_esiste"]
        with self.assertRaises(am.ArchmageError):
            a.to_element(self.names)
        with self.assertRaises(am.ArchmageError):
            am.Archmage(system_name="con spazi", character_icon="x", name_key="#mage_x").validate()
        self.assertEqual((a.loc_name_key, a.loc_desc_key), ("MAGE_F_TEST", "MAGE_F_TEST_DESC"))

    def test_replace_keeps_position(self):
        a = am.read_archmages(self.root)[5]
        a.improvements = a.improvements[:-1]
        idx = am.replace_fraction(self.root, a.system_name, a.to_element(self.names))
        self.assertEqual(idx, 5)
        self.assertEqual(len(am.read_archmages(self.root)[5].improvements), len(a.improvements))
        with self.assertRaises(am.ArchmageError):                       # il systemName non si cambia
            b = copy.deepcopy(a)
            b.system_name = "altro"
            am.replace_fraction(self.root, a.system_name, b.to_element(self.names))

    def test_improvements(self):
        imp = am.Improvement(name="adv_test", cost=2, gold=10, spells=["sp_a", "sp_b"])
        am.append_improvement(self.root, imp.to_element())
        self.assertIn("adv_test", {i.name for i in am.read_improvements(self.root)})
        with self.assertRaises(am.ArchmageError):
            am.append_improvement(self.root, imp.to_element())
        with self.assertRaises(am.ArchmageError):
            am.Improvement(name="x", spells=["a", "a"]).validate()
        self.assertTrue(am.improvement_users(self.root, "adv_fractionPerk_Researcher"))


@unittest.skipUnless(PATH and LOC, "fractions.binary.xml o locdata.md non trovati")
class Services(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.mkdtemp()
        shutil.copy(PATH, os.path.join(self.tmp, "fractions.binary.xml"))
        shutil.copy(LOC, os.path.join(self.tmp, "locdata.md"))

    def tearDown(self):
        shutil.rmtree(self.tmp, ignore_errors=True)

    def test_archmage_file_ops(self):
        from services import archmage_service as svc
        path = os.path.join(self.tmp, "fractions.binary.xml")
        info = svc.read_info(path)
        a = copy.deepcopy(info.archmages[1])
        a.system_name, a.name_key = "f_x", "#mage_f_x"
        svc.add_archmage(path, a)
        self.assertEqual(svc.read_info(path).archmages[-1].system_name, "f_x")

    def test_locdata_write_and_read(self):
        from services import locdata_service as ls
        manifest = {"locdata.md": os.path.join(self.tmp, "locdata.md")}
        ls.write_texts(self.tmp, manifest, [], {"MAGE_F_X": "Nome", "MAGE_F_X_DESC": "Desc\nriga 2"})
        data = open(manifest["locdata.md"], "rb").read()
        t = ls.get_texts(data, ["MAGE_F_X", "MAGE_F_X_DESC", "MAGE_F_WIZARD"])
        self.assertEqual((t["MAGE_F_X"], t["MAGE_F_X_DESC"]), ("Nome", "Desc\nriga 2"))
        self.assertEqual(t["MAGE_F_WIZARD"], "Miralbus the Hat")
        with self.assertRaises(ls.LocdataError):
            ls.write_texts(self.tmp, manifest, [], {"MAGE_F_X": "  "})


if __name__ == "__main__":
    unittest.main(verbosity=2)
