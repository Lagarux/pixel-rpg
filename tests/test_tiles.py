#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Karo gorselleri, gecit agizlari ve harita duzeni testleri.

Olculen sorunlari bir daha geri gelmesin diye kayda geciriyor:
  * Haritalarin yarisinda baskin zemin %99-100'du (harabeler %100 FLOOR,
    kayalik gecit %99 DIRT): 16 kareye kadar tek tip blok.
  * _PROPS_BY_TILE'da ASH ve ICE yoktu, Koz Vadisi dekor yogunlugu %0.7'ydi.
  * misty_swamp -> ashveil TEK YONLUYDU; donusu yoktu.
  * mystic_library'nin iki gecidi de ayni kareye, ustelik nehrin icine
    cikiyordu.
  * Sisli Bataklik'ta uc kum adacigi suyun ortasinda ulasilamaz kaliyordu.

Calistirmak icin: python -m unittest discover -s tests
"""
import os
import sys
from collections import deque

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import unittest

import pygame

from harness import load_game_module

MOD = None
MAPS = {}
HARITA_ADLARI = ["ashveil", "dark_forest", "ruins", "desert", "ice_cave",
                 "shadow_castle", "village_dungeon", "south_meadow",
                 "west_river", "mystic_library", "rocky_pass", "misty_swamp",
                 "ember_valley", "festival"]


def setUpModule():
    global MOD, MAPS
    MOD = load_game_module("pixel_rpg_tiles")
    pygame.init()
    pygame.display.set_mode((MOD.SW, MOD.SH))
    MAPS = {ad: getattr(MOD, "build_" + ad)() for ad in HARITA_ADLARI}
    for m in MAPS.values():
        MOD._scatter_props(m)


def tearDownModule():
    pygame.quit()


def renkler(surf):
    """Karodaki benzersiz renk sayisi."""
    return len({surf.get_at((x, y))[:3]
                for x in range(surf.get_width())
                for y in range(surf.get_height())})


def bolgeler(m):
    """Yurunebilir karelerin baglantili bolgeleri."""
    gor = set()
    out = []
    for ty in range(m.h):
        for tx in range(m.w):
            if not m.walkable(tx, ty) or (tx, ty) in gor:
                continue
            q = deque([(tx, ty)])
            gor.add((tx, ty))
            b = []
            while q:
                cx, cy = q.popleft()
                b.append((cx, cy))
                for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                    n = (cx + dx, cy + dy)
                    if n in gor or not (0 <= n[0] < m.w and 0 <= n[1] < m.h):
                        continue
                    if m.walkable(*n):
                        gor.add(n)
                        q.append(n)
            out.append(b)
    return sorted(out, key=len, reverse=True)


class TestYeniKarolar(unittest.TestCase):
    YENI = ("PATH", "MEADOW", "HEDGE", "MOSS", "RUBBLE", "GRAVEL", "PINE",
            "SHALLOW", "CRACKED")

    def test_hepsi_tanimli(self):
        for ad in self.YENI:
            self.assertTrue(hasattr(MOD.T, ad), "%s karosu yok" % ad)

    def test_hicbiri_duz_renk_degil(self):
        """Duz tek renk karo, yan yana dizilince izgara gibi gorunur."""
        for ad in self.YENI:
            with self.subTest(karo=ad):
                n = renkler(MOD.PA.tile(getattr(MOD.T, ad)))
                self.assertGreaterEqual(n, 4, "%s karosunda %d renk var" % (ad, n))

    def test_birbirinden_ayirt_edilebilir(self):
        """Iki karo ayni gorunuyorsa oyuncu zemin degisimini fark edemez."""
        goruntu = {}
        for ad in self.YENI + ("GRASS", "DIRT", "SAND", "SNOW", "STONE", "FLOOR"):
            s = MOD.PA.tile(getattr(MOD.T, ad))
            goruntu[ad] = pygame.image.tostring(s, "RGB")
        adlar = sorted(goruntu)
        for i, a in enumerate(adlar):
            for b in adlar[i + 1:]:
                self.assertNotEqual(goruntu[a], goruntu[b],
                                    "%s ve %s birebir ayni cizim" % (a, b))

    def test_yurunebilirler_yurunebilir_kalmis(self):
        for ad in ("PATH", "MEADOW", "MOSS", "RUBBLE", "GRAVEL", "SHALLOW", "CRACKED"):
            self.assertIn(getattr(MOD.T, ad), MOD.WALKABLE, "%s yurunmez" % ad)
        for ad in ("HEDGE", "PINE"):
            self.assertNotIn(getattr(MOD.T, ad), MOD.WALKABLE, "%s engel degil" % ad)


class TestGecitAgizlari(unittest.TestCase):
    def test_her_uslup_farkli_cizim(self):
        goruntu = {}
        for st in MOD.GATE_STYLES:
            s = MOD.PA.tile(MOD.T.GATE, 0, st)
            goruntu[st] = pygame.image.tostring(s, "RGB")
            self.assertGreaterEqual(renkler(s), 5, "%s geciti neredeyse duz" % st)
        adlar = sorted(goruntu)
        for i, a in enumerate(adlar):
            for b in adlar[i + 1:]:
                self.assertNotEqual(goruntu[a], goruntu[b],
                                    "%s ve %s geciti ayni" % (a, b))

    def test_her_gecit_karesinin_uslubu_var(self):
        for ad, m in MAPS.items():
            for p in m.transitions:
                with self.subTest(harita=ad, kare=p):
                    self.assertIn(p, m.gate_kind, "%s %s uslupsuz" % (ad, p))
                    self.assertIn(m.gate_kind[p], MOD.GATE_STYLES)

    def test_uslup_gidilen_yere_uyuyor(self):
        """Buz magarasina buz, kaleye kapi, Koz Vadisine kul agzi."""
        beklenen = {
            ("desert", "ice_cave"): "ice",
            ("ice_cave", "shadow_castle"): "door",
            ("shadow_castle", "ice_cave"): "door",
            ("desert", "ember_valley"): "ash",
            ("ember_valley", "desert"): "ash",
            ("ashveil", "village_dungeon"): "cave",
            ("village_dungeon", "ashveil"): "cave",
            ("west_river", "mystic_library"): "door",
            ("mystic_library", "west_river"): "door",
            ("dark_forest", "ruins"): "ruin",
        }
        for (kaynak, hedef), uslup in beklenen.items():
            m = MAPS[kaynak]
            bulunan = {m.gate_kind[p] for p, v in m.transitions.items() if v[0] == hedef}
            with self.subTest(gecis="%s->%s" % (kaynak, hedef)):
                self.assertEqual(bulunan, {uslup},
                                 "%s->%s uslubu %s, %s bekleniyordu"
                                 % (kaynak, hedef, bulunan, uslup))

    def test_ok_yalnizca_agzin_ortasinda(self):
        """Uc karenin ucunde birden yanip sonen ok kapinin cizimini bastiriyordu."""
        for ad, m in MAPS.items():
            with self.subTest(harita=ad):
                self.assertLess(len(m.trans_hints), len(m.transitions),
                                "%s: her gecit karesinde ok var" % ad)
                for p in m.trans_hints:
                    self.assertIn(p, m.transitions, "%s: oksuz gecit isareti" % ad)


class TestZeminCesitliligi(unittest.TestCase):
    """Tek tip genis zeminler: olculen sorun, geri gelmesin."""

    def _dagilim(self, m):
        sayim = {}
        for ty in range(m.h):
            for tx in range(m.w):
                t = m.tiles[ty][tx]
                if t in MOD.WALKABLE:
                    sayim[t] = sayim.get(t, 0) + 1
        return sayim

    def test_hicbir_harita_tek_zeminle_kapli_degil(self):
        for ad, m in MAPS.items():
            sayim = self._dagilim(m)
            yur = sum(sayim.values())
            oran = 100.0 * max(sayim.values()) / yur
            with self.subTest(harita=ad):
                self.assertLess(oran, 90.0,
                                "%s: yurunebilir alanin %%%.0f'i tek karo" % (ad, oran))

    def test_her_haritada_en_az_dort_zemin_turu(self):
        for ad, m in MAPS.items():
            with self.subTest(harita=ad):
                self.assertGreaterEqual(len(self._dagilim(m)), 4,
                                        "%s: yalnizca %d zemin turu"
                                        % (ad, len(self._dagilim(m))))

    def test_en_buyuk_tek_tip_blok_makul(self):
        """16x16 karelik tek tip blok vardi; goz tutunacak sey bulamiyordu."""
        for ad, m in MAPS.items():
            sayim = self._dagilim(m)
            bask = max(sayim, key=sayim.get)
            dp = [[0] * m.w for _ in range(m.h)]
            best = 0
            for y in range(m.h):
                for x in range(m.w):
                    if m.tiles[y][x] != bask:
                        continue
                    dp[y][x] = 1 if (x == 0 or y == 0) else \
                        1 + min(dp[y - 1][x], dp[y][x - 1], dp[y - 1][x - 1])
                    best = max(best, dp[y][x])
            with self.subTest(harita=ad):
                self.assertLessEqual(best, 12,
                                     "%s: %dx%d karelik tek tip blok" % (ad, best, best))


class TestDekor(unittest.TestCase):
    def test_her_haritada_yeterli_dekor(self):
        """Koz Vadisi %0.7'de kalmisti: ASH listede yoktu."""
        for ad, m in MAPS.items():
            yur = sum(1 for y in range(m.h) for x in range(m.w) if m.walkable(x, y))
            oran = 100.0 * len(m.props) / yur
            with self.subTest(harita=ad):
                self.assertGreater(oran, 3.0, "%s: dekor yogunlugu %%%.1f" % (ad, oran))

    def test_yaygin_zeminlerin_dekor_kaydi_var(self):
        """Bir haritanin %10'unu kaplayan zeminin dekoru olmali."""
        for ad, m in MAPS.items():
            sayim = {}
            for ty in range(m.h):
                for tx in range(m.w):
                    t = m.tiles[ty][tx]
                    if t in MOD.WALKABLE:
                        sayim[t] = sayim.get(t, 0) + 1
            yur = sum(sayim.values())
            for t, n in sayim.items():
                if n < yur * 0.10:
                    continue
                if t in (MOD.T.GATE, MOD.T.DOOR, MOD.T.WHEAT, MOD.T.FARMLAND,
                         MOD.T.BRIDGE, MOD.T.STAIRS_UP, MOD.T.STAIRS_DN,
                         MOD.T.PORTAL):
                    continue
                with self.subTest(harita=ad, karo=t):
                    self.assertIn(t, MOD._PROPS_BY_TILE,
                                  "%s: %d numarali karo alanin %%%.0f'ini kapliyor "
                                  "ama dekor kaydi yok" % (ad, t, 100.0 * n / yur))

    def test_dekor_gecit_karesine_konmuyor(self):
        for ad, m in MAPS.items():
            for (px, py, _k) in m.props:
                with self.subTest(harita=ad):
                    self.assertNotIn((px, py), m.transitions)
                    self.assertNotIn((px, py), m.gate_kind)


class TestDunyaBaglantisi(unittest.TestCase):
    def test_her_gecisin_donusu_var(self):
        """misty_swamp -> ashveil tek yonluydu: donus yoktu."""
        for ad, m in MAPS.items():
            for hedef in {v[0] for v in m.transitions.values()}:
                dm = MAPS[hedef]
                with self.subTest(gecis="%s->%s" % (ad, hedef)):
                    self.assertIn(ad, {v[0] for v in dm.transitions.values()},
                                  "%s -> %s var ama donusu yok" % (ad, hedef))

    def test_iki_gecit_ayni_yere_cikmiyor(self):
        """Kutuphanenin iki kapisi da west_river (26,3)/(26,4) karesine cikiyordu."""
        for ad, m in MAPS.items():
            hedefler = [v for v in {tuple(v) for v in m.transitions.values()}]
            varislar = {}
            for (dst, dx, dy) in hedefler:
                for (odst, odx, ody), p in list(varislar.items()):
                    if odst == dst and abs(odx - dx) + abs(ody - dy) <= 2:
                        self.fail("%s: iki ayri gecit %s icinde bitisik karelere "
                                  "cikiyor: %s ve %s" % (ad, dst, (odx, ody), (dx, dy)))
                varislar[(dst, dx, dy)] = True

    def test_varis_tam_istenen_karede(self):
        """Varis yurunmez bir kareye konursa oyuncu baska yere kayiyor."""
        for ad, m in MAPS.items():
            for p, (dst, dx, dy) in m.transitions.items():
                dm = MAPS[dst]
                a = MOD._arrival_tile(dm, dx, dy)
                sapma = abs(a[0] - dx) + abs(a[1] - dy)
                with self.subTest(gecis="%s->%s" % (ad, dst)):
                    self.assertLessEqual(sapma, 1,
                                         "%s -> %s: istenen %s, gercek %s"
                                         % (ad, dst, (dx, dy), a))

    def test_ulasilamayan_adacik_yok(self):
        """Bataklikta uc kum adacigi suyun ortasinda kalmisti."""
        for ad, m in MAPS.items():
            bs = bolgeler(m)
            kopuk = [b for b in bs[1:] if len(b) >= 2]
            with self.subTest(harita=ad):
                self.assertEqual(kopuk, [],
                                 "%s: ana bolgeden kopuk %d adacik (ornek %s)"
                                 % (ad, len(kopuk), kopuk[0][0] if kopuk else None))

    def test_cikmaz_bolge_sayisi_sinirli(self):
        """Tek kapili bolge olabilir (zindan, kale) ama dunya agac degil halka olmali."""
        tek_kapili = []
        for ad, m in MAPS.items():
            if len({v[0] for v in m.transitions.values()}) <= 1:
                tek_kapili.append(ad)
        # Tek kapili bes bolge var ve hepsi VARIS noktasi, gecis degil:
        # golge kalesi, koy alti zindani, Koz Vadisi, kutuphane, senlik.
        self.assertLessEqual(len(tek_kapili), 5,
                             "cok fazla cikmaz bolge: %s" % tek_kapili)


if __name__ == "__main__":
    unittest.main(verbosity=2)
