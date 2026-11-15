"""Test di gfx_icons / icon_service sul c_icons.gfx REALE.

Uso:  python test_gfx_icons.py [percorso\\c_icons.gfx]
Il file si cerca anche in: variabile C_ICONS_GFX, cartella di questo script,
work\\unpacked_pack\\c_icons.gfx.
"""
import os
import struct
import sys
import unittest

HERE = os.path.dirname(os.path.abspath(__file__))
if HERE not in sys.path:
    sys.path.insert(0, HERE)

from gfx_icons import GfxError, GfxIcons, apply_assignments, verify_change  # noqa: E402


def _find_gfx():
    cands = [os.environ.get("C_ICONS_GFX"), os.path.join(HERE, "c_icons.gfx"),
             os.path.join(HERE, "work", "unpacked_pack", "c_icons.gfx")]
    if len(sys.argv) > 1 and sys.argv[1].lower().endswith(".gfx"):
        cands.insert(0, sys.argv.pop(1))
    return next((c for c in cands if c and os.path.isfile(c)), None)


GFX = _find_gfx()
DATA = open(GFX, "rb").read() if GFX else None


@unittest.skipUnless(GFX, "c_icons.gfx non trovato")
class RealFile(unittest.TestCase):
    def setUp(self):
        self.g = GfxIcons(DATA)

    def test_parse(self):
        g = self.g
        self.assertEqual(g.shape_errors, [])
        self.assertEqual(len(g.atlases), 17)
        self.assertEqual(g.atlases[1].filename, "c_icons_i7.dds")
        self.assertEqual((g.atlases[1].width, g.atlases[1].height), (2048, 2048))

    def test_magnate_chain(self):
        g = self.g
        fr = g.labels()["fractionPerk_Magnate"]
        self.assertEqual((fr.sprite, fr.number, fr.char), (841, 7, 823))
        sub = g.subimage_of_shape(823)
        self.assertEqual((sub.id, sub.atlas, sub.x1, sub.y1, sub.x2, sub.y2), (822, 1, 1872, 130, 1936, 194))
        self.assertEqual(g.shapes[823].size_px, (48.0, 48.0))
        self.assertEqual(g.reference_size(841), (48.0, 48.0))
        self.assertEqual(g.sprite_for_label("fractionPerk_Butcher").id, 841)

    def test_append_new_label(self):
        g = self.g
        new = g.set_perk_icon("fractionPerk_Butcher", 825)
        g2 = GfxIcons(new)
        verify_change(g, g2, "fractionPerk_Butcher", 825)
        sp = g2.sprites[841]
        self.assertEqual((len(sp.frames), sp.declared_frames), (22, 22))
        last = sp.frames[-1]
        self.assertEqual((last.label, last.char, last.depth), ("fractionPerk_Butcher", 825, 4))
        self.assertEqual(len(new) - len(DATA), 41)
        self.assertEqual(struct.unpack_from("<I", new, 4)[0], len(new))
        # i frame originali non cambiano
        for f in g.sprites[841].frames:
            self.assertEqual((g2.sprites[841].frames[f.number - 1].label, g2.sprites[841].frames[f.number - 1].char),
                             (f.label, f.char))

    def test_retarget_existing(self):
        g = self.g
        new = g.set_perk_icon("fractionPerk_Magnate", 825)
        self.assertEqual(len(new), len(DATA))
        g2 = GfxIcons(new)
        verify_change(g, g2, "fractionPerk_Magnate", 825)
        self.assertEqual(g2.labels()["fractionPerk_Magnate"].char, 825)
        self.assertEqual(len(g2.sprites[841].frames), 21)

    def test_assignments_sequence_and_rerun(self):
        out = apply_assignments(DATA, {"fractionPerk_Butcher": 825, "fractionPerk_Other": 827})
        g = GfxIcons(out)
        self.assertEqual(len(g.sprites[841].frames), 23)
        # riapplicare su un file già modificato aggiorna invece di duplicare
        again = apply_assignments(out, {"fractionPerk_Butcher": 829})
        g2 = GfxIcons(again)
        self.assertEqual(len(g2.sprites[841].frames), 23)
        self.assertEqual(g2.labels()["fractionPerk_Butcher"].char, 829)

    def test_errors(self):
        for label, shape in (("x", 99999), ("", 823), ("é", 823)):
            with self.assertRaises(GfxError):
                self.g.set_perk_icon(label, shape)
        no_bitmap = next(s.id for s in self.g.shapes.values() if not s.bitmaps)
        with self.assertRaises(GfxError):
            self.g.set_perk_icon("fractionPerk_Butcher", no_bitmap)
        with self.assertRaises(GfxError):
            self.g.set_perk_icon("zzz_unknownprefix", 823)  # nessuno sprite con quel prefisso

    def test_bad_files(self):
        with self.assertRaises(GfxError):
            GfxIcons(b"CFX" + DATA[3:])
        with self.assertRaises(GfxError):
            GfxIcons(DATA[:-10])  # lunghezza dichiarata != reale
        with self.assertRaises(GfxError):
            GfxIcons(b"not a gfx file at all")

    def test_append_small_icon_sprite(self):
        """Sprite delle piccole icone degli archmage: il frame nuovo deve togliere DUE depth."""
        g = self.g
        small = g.labels().get("f_wizard")
        if small is None:
            self.skipTest("label f_wizard assente in questo c_icons.gfx")
        new = g.set_perk_icon("f_custom_test", small.char)
        g2 = GfxIcons(new)
        verify_change(g, g2, "f_custom_test", small.char)
        last = g2.sprites[small.sprite].frames[-1]
        self.assertEqual((last.label, last.char, last.depth), ("f_custom_test", small.char, 1))
        self.assertEqual(sorted(last.removes), [1, 4])

    def test_append_portrait_sprite_last_frame_is_icon(self):
        """Sprite dei ritratti: l'ultimo frame è già un'icona, il nuovo la sostituisce con Move+Character."""
        g = self.g
        port = g.labels().get("wizard")
        if port is None:
            self.skipTest("label wizard assente in questo c_icons.gfx")
        new = g.set_perk_icon("custom_mage_test", port.char, port.sprite)
        g2 = GfxIcons(new)
        verify_change(g, g2, "custom_mage_test", port.char)
        last = g2.sprites[port.sprite].frames[-1]
        self.assertEqual((last.label, last.place_flags, last.removes), ("custom_mage_test", 0x03, []))

    def test_assignments_with_explicit_sprite(self):
        small = self.g.labels().get("f_wizard")
        if small is None:
            self.skipTest("label f_wizard assente")
        out = apply_assignments(DATA, {"Custom": (small.char, small.sprite)})   # label senza prefisso '_'
        self.assertIn("Custom", GfxIcons(out).labels())

    def test_usable_icons(self):
        u = self.g.usable_icons(1)
        self.assertGreater(len(u), 100)
        self.assertTrue(all(s.atlas == 1 for s, _ in u))


class Sheet(unittest.TestCase):
    @unittest.skipUnless(GFX, "c_icons.gfx non trovato")
    def test_render_sheet(self):
        dds = os.path.join(os.path.dirname(GFX), "c_icons_i7.dds")
        if not os.path.isfile(dds):
            dds = os.path.join(HERE, "c_icons_i7.dds")
        if not os.path.isfile(dds):
            self.skipTest("c_icons_i7.dds non trovato")
        try:
            from PIL import Image
        except ImportError:
            self.skipTest("Pillow mancante")
        from services import icon_service as ics
        g = GfxIcons(DATA)
        items = ics.icons_for_atlas(g, 1, (48.0, 48.0))
        sheet, tiles = ics.render_sheet(Image.open(dds).convert("RGBA"), items)
        self.assertEqual(len(tiles), len(items))
        t = tiles[3]
        self.assertEqual(ics.tile_at(tiles, t.x + 5, t.y + 5).shape_id, t.shape_id)


if __name__ == "__main__":
    unittest.main(verbosity=2)
