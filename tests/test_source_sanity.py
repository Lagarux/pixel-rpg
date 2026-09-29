#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Kaynak kodu saglik testleri.

Neden var: envanterde E'ye basmak `NameError: name 'fT_' is not defined` ile
cokuyordu. Bir arama-degistirme f-string'i bozmus, `f"..."` ile `T_(...)`
birlesip `fT_(...)` olmustu. Sozdizimi gecerli oldugu icin ne import ne de
testler bunu gormedi -- hata ancak o satir CALISINCA ortaya cikiyordu.

Burada modulun tamami `symtable` ile taraniyor: bir fonksiyon, modulde var
olmayan bir global ismi kullaniyorsa test kirilir. Boylece yazim hatalari o
satiri oynamadan yakalanir.

Calistirmak icin: python -m unittest discover -s tests
"""
import builtins
import io
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import symtable
import unittest

import pygame

from harness import load_game_module

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
GAME = os.path.join(ROOT, "pixel_rpg.py")

MOD = None
SRC = None


def setUpModule():
    global MOD, SRC
    MOD = load_game_module("pixel_rpg_sanity")
    with io.open(GAME, encoding="utf-8") as f:
        SRC = f.read()
    pygame.init()
    pygame.display.set_mode((MOD.SW, MOD.SH))


def tearDownModule():
    pygame.quit()


def undefined_global_uses():
    """(kapsam yolu, isim) -- modulde tanimli olmayan her global kullanim."""
    top = symtable.symtable(SRC, "pixel_rpg.py", "exec")
    # Modul gercekten yuklendi: izin verilen isimler onun kendi ad alani.
    allowed = set(vars(MOD)) | set(dir(builtins)) | {"__file__", "__name__", "__doc__"}
    found = []

    def walk(table, path):
        for sym in table.get_symbols():
            if sym.is_global() and sym.is_referenced() and sym.get_name() not in allowed:
                found.append((path, sym.get_name()))
        for child in table.get_children():
            walk(child, "%s.%s" % (path, child.get_name()))

    for child in top.get_children():
        walk(child, child.get_name())
    return found


class TestNoUndefinedNames(unittest.TestCase):
    def test_no_function_uses_an_undefined_global(self):
        found = undefined_global_uses()
        if found:
            satirlar = "\n".join("  %s icinde tanimsiz isim: %s" % (p, n) for p, n in found)
            self.fail("Tanimsiz isim kullanimi (calisinca NameError olur):\n" + satirlar)

    def test_detector_actually_catches_a_typo(self):
        """Tarayici ise yariyor mu? Kasten bozuk bir ornekte yakalamali."""
        src = "import math\nX=1\ndef f(a):\n    return fT_(a)+math.sin(X)\n"
        top = symtable.symtable(src, "ornek.py", "exec")
        allowed = {s.get_name() for s in top.get_symbols()} | set(dir(builtins))
        hits = []
        for child in top.get_children():
            for sym in child.get_symbols():
                if sym.is_global() and sym.is_referenced() and sym.get_name() not in allowed:
                    hits.append(sym.get_name())
        self.assertEqual(hits, ["fT_"], "tarayici bilinen yazim hatasini kacirdi")


class TestNoStrayDependencies(unittest.TestCase):
    def test_game_does_not_need_numpy(self):
        """Ses sentezi numpy'a donmemeli: kurulu olmadigi icin oyun sessiz kalmisti."""
        bad = [ln.strip() for ln in SRC.splitlines()
               if "import numpy" in ln or "np." in ln or "sndarray" in ln]
        self.assertEqual(bad, [], "numpy kullanimi geri gelmis: %s" % bad)

    def test_only_stdlib_and_pygame_are_imported(self):
        """Ust duzey import'lar stdlib + pygame olmali (paketleme bunu varsayiyor)."""
        izin = {"pygame", "sys", "math", "random", "os", "json", "zlib", "array",
                "collections", "typing", "dataclasses", "ctypes", "tempfile",
                "shutil", "time", "traceback", "unicodedata"}
        import ast
        disari = []
        for node in ast.walk(ast.parse(SRC)):
            if isinstance(node, ast.Import):
                for a in node.names:
                    kok = a.name.split(".")[0]
                    if kok not in izin: disari.append(kok)
            elif isinstance(node, ast.ImportFrom) and node.module and node.level == 0:
                kok = node.module.split(".")[0]
                if kok not in izin: disari.append(kok)
        # bidi istege bagli: varsa kullaniliyor, yoksa yedek yol var
        disari = [m for m in disari if m not in ("bidi",)]
        self.assertEqual(sorted(set(disari)), [],
                         "beklenmeyen dis bagimlilik: %s" % sorted(set(disari)))


class TestSlotTablesStayInSync(unittest.TestCase):
    """Yuva listeleri ayri ayri yazilirsa biri guncellenmeden kaliyor."""

    def test_fresh_stats_have_every_slot(self):
        for cc in ("warrior", "mage", "archer", "healer"):
            st = MOD.PlayerStats(cc)
            self.assertEqual(sorted(st.equipment), sorted(MOD.EQUIP_SLOTS),
                             "%s: yeni karakterde yuvalar eksik" % cc)

    def test_every_equip_item_targets_a_real_slot(self):
        for ik, row in MOD.EQUIP_ITEMS.items():
            self.assertIn(row[3], MOD.EQUIP_SLOTS, "%s tanimsiz yuvaya isaret ediyor: %s" % (ik, row[3]))

    def test_every_slot_has_a_name_and_colour(self):
        for slot in MOD.EQUIP_SLOTS:
            self.assertIn(slot, MOD.SLOT_NAMES, "%s icin ad yok" % slot)
            self.assertIn(slot, MOD.SLOT_COLORS, "%s icin renk yok" % slot)

    def test_every_slot_has_an_icon(self):
        for slot in MOD.EQUIP_SLOTS:
            icon = MOD.PA.equip_icon(slot, (200, 200, 200))
            self.assertTrue(pygame.mask.from_surface(icon).count() > 0,
                            "%s yuvasinin simgesi bos ciziliyor" % slot)


if __name__ == "__main__":
    unittest.main(verbosity=2)
