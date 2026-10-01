#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Pazar meydani testleri.

Koyde altin harcanacak tek yer iki NPC'ydi. Guneybatidaki bos alana tas
doseli bir meydan, dort tezgah ve dort satici kondu. Testler: meydanin
ana yoldan yurunerek erisilebildigi, her saticinin yanina varilabildigi,
her tezgahin gercek bir dukkan oldugu ve tezgahlarin yurumeyi engelledigi.

Calistirmak icin: python -m unittest discover -s tests
"""
import os
import shutil
import sys
import tempfile
from collections import deque

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import unittest

import pygame

from harness import load_game_module

MOD = None
TMP = None
G = None

SATICILAR = ("npc.otaci_nesrin", "npc.avci_doruk", "npc.tuccar_salim", "npc.ciftci_hale")


def setUpModule():
    global MOD, TMP, G
    MOD = load_game_module("pixel_rpg_bazaar")
    TMP = tempfile.mkdtemp(prefix="pixelrpg_bazaar_")
    MOD.SAVE_FILE = os.path.join(TMP, "save1.json")
    pygame.init()
    pygame.display.set_mode((MOD.SW, MOD.SH))
    G = MOD.Game.__new__(MOD.Game)
    G.ui = MOD.UI()
    G.ps = MOD.PS()
    G._reset()


def tearDownModule():
    pygame.quit()
    shutil.rmtree(TMP, ignore_errors=True)


def village():
    return G.maps["ashveil"]


def reachable_from_spawn():
    """Oyuncunun dogdugu yerden gecise basmadan gezilebilen kareler."""
    m = village()
    start = MOD._snap(m, 29, 25)
    seen = {start}
    q = deque([start])
    while q:
        cx, cy = q.popleft()
        for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
            n = (cx + dx, cy + dy)
            if n in seen or not m.walkable(*n) or n in m.transitions:
                continue
            seen.add(n)
            q.append(n)
    return seen


def vendors():
    return [n for n in village().npcs if n.name in SATICILAR]


class TestVendors(unittest.TestCase):
    def test_all_four_vendors_are_placed(self):
        bulunan = {n.name for n in vendors()}
        self.assertEqual(bulunan, set(SATICILAR),
                         "eksik satici: %s" % (set(SATICILAR) - bulunan))

    def test_every_vendor_runs_a_shop(self):
        for ad in SATICILAR:
            self.assertIn(ad, MOD.SHOPS, "%s dukkansiz duruyor" % ad)
            self.assertTrue(MOD.SHOPS[ad]["stock"], "%s bos tezgah" % ad)

    def test_every_stocked_item_is_real_and_priced(self):
        for ad in SATICILAR:
            for ik in MOD.SHOPS[ad]["stock"]:
                self.assertIn(ik, MOD.ALL_ITEMS, "%s: tanimsiz esya %s" % (ad, ik))
                self.assertIn(ik, MOD.ITEM_PRICES,
                              "%s: %s icin fiyat yok, 20 altina satilir" % (ad, ik))

    def test_vendors_sell_different_things(self):
        """Dort tezgah ayni seyi satiyorsa pazar degil, kopya dukkan olur."""
        for ad in SATICILAR:
            kendi = set(MOD.SHOPS[ad]["stock"])
            for digeri in SATICILAR:
                if digeri == ad:
                    continue
                ortak = kendi & set(MOD.SHOPS[digeri]["stock"])
                self.assertLess(len(ortak), len(kendi),
                                "%s ile %s ayni stogu tasiyor" % (ad, digeri))

    def test_market_covers_items_the_old_shops_missed(self):
        """Pazarin varlik sebebi: eskiden hic satilmayan esyalar."""
        eski = set(MOD.SHOPS["npc.demirci_boran"]["stock"]) | set(MOD.SHOPS["npc.hanci_mira"]["stock"])
        yeni = set()
        for ad in SATICILAR:
            yeni |= set(MOD.SHOPS[ad]["stock"])
        self.assertTrue(yeni - eski, "pazar yeni hicbir sey satmiyor")


class TestLayout(unittest.TestCase):
    def test_square_is_reachable_on_foot(self):
        erisim = reachable_from_spawn()
        meydan = [(tx, ty) for ty in range(41, 45) for tx in range(15, 27)]
        kopuk = [p for p in meydan if village().walkable(*p) and p not in erisim]
        self.assertEqual(kopuk, [], "meydanin %d karesine yurunerek gidilemiyor" % len(kopuk))

    def test_every_vendor_can_be_approached(self):
        erisim = reachable_from_spawn()
        for n in vendors():
            yan = [(n.tx + dx, n.ty + dy) for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1))]
            acik = [p for p in yan if p in erisim]
            self.assertTrue(acik, "%s yanina varilamiyor (%s)" % (n.name, (n.tx, n.ty)))

    def test_stalls_block_movement(self):
        self.assertNotIn(MOD.T.STALL, MOD.WALKABLE)
        m = village()
        tezgah = [(tx, ty) for ty in range(38, 48) for tx in range(14, 28)
                  if m.get(tx, ty) == MOD.T.STALL]
        self.assertGreaterEqual(len(tezgah), 12, "tezgah kurulmamis: %d kare" % len(tezgah))

    def test_vendors_stand_on_walkable_ground(self):
        m = village()
        for n in vendors():
            self.assertTrue(m.walkable(n.tx, n.ty),
                            "%s yurunemez karede duruyor" % n.name)

    def test_vendors_are_not_on_top_of_each_other(self):
        yerler = [(n.tx, n.ty) for n in vendors()]
        self.assertEqual(len(set(yerler)), len(yerler), "iki satici ayni karede")

    def test_stall_tile_looks_different_from_road(self):
        a = pygame.transform.average_color(MOD.PA.tile(MOD.T.STALL))[:3]
        b = pygame.transform.average_color(MOD.PA.tile(MOD.T.ROAD))[:3]
        self.assertGreater(sum(abs(x - y) for x, y in zip(a, b)), 40,
                           "tezgah ile zemin ayni gorunuyor")


class TestDialogue(unittest.TestCase):
    def test_vendor_names_are_translated(self):
        eski = MOD.CFG.data.get("language", "TR")
        try:
            for code in MOD.LANG_CODES:
                MOD.CFG.data["language"] = code
                for ad in SATICILAR:
                    txt = MOD.T_(ad)
                    self.assertNotEqual(txt, ad, "%s/%s cevrilmemis" % (code, ad))
                    self.assertTrue(txt.strip())
        finally:
            MOD.CFG.data["language"] = eski

    def test_vendors_say_something_substantial(self):
        """Kullanici daha uzun ve mantikli konusmalar istedi."""
        for n in vendors():
            satirlar = n.get_dialog({"ch": 1})
            self.assertGreaterEqual(len(satirlar), 4,
                                    "%s yalnizca %d satir konusuyor" % (n.name, len(satirlar)))
            for anahtar in satirlar:
                metin = MOD.dlg_line(anahtar)
                self.assertNotEqual(metin, anahtar, "%s cevrilmemis" % anahtar)
                self.assertGreater(len(metin), 20, "%s cok kisa: %r" % (anahtar, metin))

    def test_dialogue_changes_with_progress(self):
        """Ilerleyince ayni cumleleri tekrarlamasinlar."""
        for n in vendors():
            bas = n.get_dialog({"ch": 1})
            ilerlemis = n.get_dialog({"ch": 6, "kill_wolf": 9, "kill_boar": 9})
            self.assertNotEqual(bas, ilerlemis,
                                "%s oyun ilerleyince ayni seyi soyluyor" % n.name)


if __name__ == "__main__":
    unittest.main(verbosity=2)
