#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Dunya baglantisi ve gecit testleri.

Neden var: oyuncu nehir haritasindan koye donunce iki harita arasinda
SIKISIYORDU. Uc sorun ust uste binmisti:

  1. Koyun ana yollari T.STONE ile ciziliyordu ama STONE magara duvari --
     yani yollar yurunemez. Varis noktasi (3,24) bir duvarin ustundeydi.
  2. Bu yuzden _snap oyuncuyu (2,24)'e tasiyordu; orasi gecis karesinin TA
     KENDISIYDI.
  3. Gecis seritleri kenar boyunca 6-10 kare uzunlugundaydi, dolayisiyla o
     karenin butun yurunebilir komsulari da gecisti.

Sonuc: gecise basmadan ulasilabilen kare sayisi 1. Her adim ya duvara
carpiyor ya oyuncuyu geri yolluyordu. Bu testler ucunu de olcuyor.

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


def setUpModule():
    global MOD, TMP, G
    MOD = load_game_module("pixel_rpg_world")
    TMP = tempfile.mkdtemp(prefix="pixelrpg_world_")
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


def free_area(m, start):
    """Gecise BASMADAN ulasilabilen kareler."""
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


def links():
    """(kaynak harita, hedef harita, istenen varis) uclulerinin tamami."""
    out = []
    for key, m in G.maps.items():
        for val in {v for v in m.transitions.values()}:
            out.append((key, val[0], (val[1], val[2])))
    return out


def ring(m):
    pts = []
    for tx in range(m.w):
        pts += [(tx, 0), (tx, m.h - 1)]
    for ty in range(m.h):
        pts += [(0, ty), (m.w - 1, ty)]
    return set(pts)


class TestNoTrap(unittest.TestCase):
    """Oyuncu hicbir gecisten sonra sikismamali."""

    def test_arrival_leads_to_a_real_area(self):
        for src, dst, want in links():
            dm = G.maps[dst]
            arrive = MOD._arrival_tile(dm, *want)
            alan = len(free_area(dm, arrive))
            self.assertGreater(alan, 200,
                               "%s -> %s: varis %s, gecise basmadan sadece %d kare "
                               "gezilebiliyor (sikisma)" % (src, dst, arrive, alan))

    def test_arrival_is_never_on_a_transition(self):
        for src, dst, want in links():
            dm = G.maps[dst]
            arrive = MOD._arrival_tile(dm, *want)
            self.assertNotIn(arrive, dm.transitions,
                             "%s -> %s: oyuncu gecis karesine dusuyor, sonsuz donguye girer"
                             % (src, dst))

    def test_arrival_is_not_next_to_a_transition(self):
        """Gecise bitisik dogmak da kotu: tek yanlis adim geri gonderiyor."""
        for src, dst, want in links():
            dm = G.maps[dst]
            ax, ay = MOD._arrival_tile(dm, *want)
            yakin = [(ax + dx, ay + dy) for dx in (-1, 0, 1) for dy in (-1, 0, 1)
                     if (ax + dx, ay + dy) in dm.transitions]
            self.assertEqual(yakin, [], "%s -> %s: varis gecise bitisik (%s)"
                                        % (src, dst, yakin))

    def test_arrival_is_walkable(self):
        for src, dst, want in links():
            dm = G.maps[dst]
            self.assertTrue(dm.walkable(*MOD._arrival_tile(dm, *want)),
                            "%s -> %s: varis karesi yurunemez" % (src, dst))


class TestGates(unittest.TestCase):
    def test_gates_are_narrow(self):
        """Her gecit 3 kare. Eskiden kenarin yarisi gecisti."""
        for key, m in G.maps.items():
            gruplar = {}
            for pt, val in m.transitions.items():
                gruplar.setdefault(val, []).append(pt)
            for val, pts in gruplar.items():
                self.assertEqual(len(pts), 3,
                                 "%s -> %s gecidi %d kare genisliginde" % (key, val[0], len(pts)))

    def test_transition_tiles_are_drawn_as_gates(self):
        for key, m in G.maps.items():
            for (tx, ty) in m.transitions:
                self.assertEqual(m.get(tx, ty), MOD.T.GATE,
                                 "%s %s: gecis karesi kapi gibi cizilmiyor" % (key, (tx, ty)))

    def test_edge_gates_sit_exactly_on_the_border(self):
        """Sinirin birkac kare onunde duran serit, arada cirkin bir bosluk
        birakiyordu."""
        for key, m in G.maps.items():
            kenar = ring(m)
            for (tx, ty) in m.transitions:
                ic_gecit = 3 < tx < m.w - 4 and 3 < ty < m.h - 4
                if ic_gecit:
                    continue        # zindan agzi gibi harita ici girisler
                self.assertIn((tx, ty), kenar,
                              "%s %s: gecit sinirda degil" % (key, (tx, ty)))

    def test_borders_are_sealed(self):
        """Kenardan disari cikis yalnizca gecitlerden olmali."""
        for key, m in G.maps.items():
            acik = [p for p in ring(m)
                    if m.walkable(*p) and m.get(*p) != MOD.T.GATE]
            self.assertEqual(acik, [], "%s: kenarda %d kapanmamis kare var: %s"
                                       % (key, len(acik), acik[:6]))

    def test_every_gate_is_reachable_from_the_map(self):
        for key, m in G.maps.items():
            ic = next((tx, ty) for ty in range(m.h) for tx in range(m.w)
                      if m.walkable(tx, ty) and (tx, ty) not in m.transitions)
            alan = free_area(m, ic)
            for pt in m.transitions:
                komsu = any((pt[0] + dx, pt[1] + dy) in alan
                            for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)))
                self.assertTrue(komsu, "%s: %s gecidine ana alandan ulasilamiyor" % (key, pt))


class TestTerrain(unittest.TestCase):
    def test_village_roads_are_walkable(self):
        """Koyun ana yollari duvardi: T.STONE hem magara kayasi hem yol olarak
        kullaniliyordu."""
        m = G.maps["ashveil"]
        yol = [(tx, 24) for tx in range(10, 50)]
        kapali = [p for p in yol if not m.walkable(*p)]
        self.assertEqual(kapali, [], "ana yolun %d karesi yurunemiyor: %s"
                                     % (len(kapali), kapali[:6]))

    def test_stone_is_still_a_wall(self):
        """Magara ve zindanlar oyulmus kayadan: STONE blok kalmali."""
        self.assertNotIn(MOD.T.STONE, MOD.WALKABLE)
        self.assertIn(MOD.T.ROAD, MOD.WALKABLE)
        self.assertIn(MOD.T.GATE, MOD.WALKABLE)

    def test_road_and_stone_look_different(self):
        a = pygame.transform.average_color(MOD.PA.tile(MOD.T.ROAD))[:3]
        b = pygame.transform.average_color(MOD.PA.tile(MOD.T.STONE))[:3]
        fark = sum(abs(x - y) for x, y in zip(a, b))
        self.assertGreater(fark, 20, "yol ve duvar ayni gorunuyor: %s / %s" % (a, b))


class TestConnectivity(unittest.TestCase):
    def test_every_map_is_reachable_from_the_village(self):
        gorulen = {"ashveil"}
        q = deque(["ashveil"])
        while q:
            k = q.popleft()
            for val in {v for v in G.maps[k].transitions.values()}:
                if val[0] not in gorulen:
                    gorulen.add(val[0])
                    q.append(val[0])
        eksik = set(G.maps) - gorulen
        self.assertEqual(eksik, set(), "koyden ulasilamayan haritalar: %s" % eksik)

    def test_links_point_at_real_maps(self):
        for src, dst, _ in links():
            self.assertIn(dst, G.maps, "%s haritasi olmayan '%s' hedefine baglaniyor" % (src, dst))

    def test_round_trip_lands_back_in_the_open(self):
        """Gecitten gecip geri donunce yine acik alanda olmaliyiz."""
        for src, dst, want in links():
            dm = G.maps[dst]
            arrive = MOD._arrival_tile(dm, *want)
            geri = [v for v in dm.transitions.values() if v[0] == src]
            if not geri:
                continue
            back = MOD._arrival_tile(G.maps[src], geri[0][1], geri[0][2])
            self.assertGreater(len(free_area(G.maps[src], back)), 200,
                               "%s -> %s -> %s: donuste sikisma" % (src, dst, src))
            self.assertIn(arrive, free_area(dm, arrive))


if __name__ == "__main__":
    unittest.main(verbosity=2)
