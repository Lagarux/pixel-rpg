#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Zorluk egrisi ve boss adlari.

Kullanici bildirdi: "Savasci sinifinda Gizemli Kutuphane'de zorlandim"
ve "boss adi ingilizce verilmis".

Olcum ikisini de dogruladi:
  * Kutuphane baslangictan IKI adim otede ama 91 HP / 15.1 atk
    ortalamasiyla DORT adim otedeki buz magarasindan (77 / 12.6) sertti;
    ustelik 362 canlik bir boss vardi. Zindan da bir adim otedeyken
    100 HP / 15.3 atk ile ayni sorunu yasiyordu.
  * Can cubugunun ustundeki etiket tur kimligini yaziyordu:
    "PAGE_WARDEN", "EMBER_TITAN" ve iki kristal muhafizi icin "GOLEM".
    Yalnizca Malachar dogru gorunuyordu, cunku kimligi zaten adiydi.

Calistirmak icin: python -m unittest discover -s tests
"""
import math
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
    MOD = load_game_module("pixel_rpg_curve")
    pygame.init()
    pygame.display.set_mode((MOD.SW, MOD.SH))
    MAPS = {ad: getattr(MOD, "build_" + ad)() for ad in HARITA_ADLARI}


def tearDownModule():
    pygame.quit()


def adim_uzakligi():
    """Her haritanin Ashveil'den kac gecis otede oldugu."""
    uzak = {"ashveil": 0}
    q = deque(["ashveil"])
    while q:
        k = q.popleft()
        for (dst, _x, _y) in MAPS[k].transitions.values():
            if dst not in uzak:
                uzak[dst] = uzak[k] + 1
                q.append(dst)
    return uzak


def ortalama(m):
    normal = [e for e in m.enemies if not e.is_boss]
    if not normal:
        return (0, 0)
    return (sum(e.max_hp for e in normal) / float(len(normal)),
            sum(e.atk for e in normal) / float(len(normal)))


class TestKademeTablosu(unittest.TestCase):
    def test_her_harita_kademeli(self):
        for ad, m in MAPS.items():
            with self.subTest(harita=ad):
                self.assertIn(m.name, MOD.MAP_TIER, "%s kademesiz" % ad)

    def test_kademe_gercek_uzakliga_uyuyor(self):
        """Elle yazilan kademe, gecis grafigindeki adim sayisini izlemeli."""
        uzak = adim_uzakligi()
        for ad, m in MAPS.items():
            with self.subTest(harita=ad):
                self.assertIn(ad, uzak, "%s hicbir yerden ulasilamiyor" % ad)
                self.assertEqual(MOD.MAP_TIER[m.name], uzak[ad],
                                 "%s %d adim otede ama kademesi %d"
                                 % (ad, uzak[ad], MOD.MAP_TIER[m.name]))

    def test_hedef_tablosu_artan(self):
        hp = [MOD.TIER_TARGET[k][0] for k in sorted(MOD.TIER_TARGET)]
        atk = [MOD.TIER_TARGET[k][1] for k in sorted(MOD.TIER_TARGET)]
        self.assertEqual(hp, sorted(hp), "kademe hedefi canda artmiyor")
        self.assertEqual(atk, sorted(atk), "kademe hedefi saldiride artmiyor")
        self.assertEqual(len(set(hp)), len(hp), "iki kademe ayni canda")


class TestEgriArtiyor(unittest.TestCase):
    def test_uzaklastikca_sertlesiyor(self):
        """Iki adim otedeki kutuphane dort adim otedeki magaradan sertti."""
        kademe = {}
        for ad, m in MAPS.items():
            hp, atk = ortalama(m)
            if hp:
                kademe.setdefault(MOD.MAP_TIER[m.name], []).append((hp, atk, ad))
        sirali = sorted(kademe)
        for a, b in zip(sirali, sirali[1:]):
            ort_a = sum(x[0] for x in kademe[a]) / len(kademe[a])
            ort_b = sum(x[0] for x in kademe[b]) / len(kademe[b])
            self.assertLess(ort_a, ort_b,
                            "kademe %d (%.0f can) kademe %d'den (%.0f) sert degil"
                            % (a, ort_a, b, ort_b))
            atk_a = sum(x[1] for x in kademe[a]) / len(kademe[a])
            atk_b = sum(x[1] for x in kademe[b]) / len(kademe[b])
            self.assertLess(atk_a, atk_b, "saldiri kademe %d -> %d artmiyor" % (a, b))

    def test_hicbir_harita_kademesinden_sapmiyor(self):
        for ad, m in MAPS.items():
            hp, atk = ortalama(m)
            if not hp:
                continue
            hedef_hp, hedef_atk = MOD.TIER_TARGET[MOD.MAP_TIER[m.name]]
            with self.subTest(harita=ad):
                self.assertAlmostEqual(hp / hedef_hp, 1.0, delta=0.12,
                                       msg="%s: ortalama can %.0f, hedef %d"
                                           % (ad, hp, hedef_hp))
                self.assertAlmostEqual(atk / hedef_atk, 1.0, delta=0.12,
                                       msg="%s: ortalama saldiri %.1f, hedef %d"
                                           % (ad, atk, hedef_atk))

    def test_yakin_harita_uzak_haritadan_sert_degil(self):
        """Kullanicinin yasadigi sorun: tam olarak bu."""
        for ad1, m1 in MAPS.items():
            for ad2, m2 in MAPS.items():
                k1, k2 = MOD.MAP_TIER[m1.name], MOD.MAP_TIER[m2.name]
                if k1 + 1 >= k2:
                    continue          # yalnizca en az iki kademe fark
                hp1, atk1 = ortalama(m1)
                hp2, atk2 = ortalama(m2)
                if not hp1 or not hp2:
                    continue
                with self.subTest(yakin=ad1, uzak=ad2):
                    self.assertLess(hp1, hp2,
                                    "%s (adim %d) %s'den (adim %d) sert"
                                    % (ad1, k1, ad2, k2))
                    self.assertLess(atk1, atk2,
                                    "%s (adim %d) %s'den (adim %d) sert vuruyor"
                                    % (ad1, k1, ad2, k2))


class TestSinirlar(unittest.TestCase):
    def test_hicbir_dusman_tabanin_altinda_degil(self):
        """1. seviye savasci 15 vuruyor; uc vurustan az dayanan dusman olmasin."""
        for ad, m in MAPS.items():
            for e in m.enemies:
                with self.subTest(harita=ad, tur=e.kind):
                    self.assertGreaterEqual(e.max_hp, MOD.TABAN_HP,
                                            "%s/%s %d can" % (ad, e.kind, e.max_hp))

    def test_siradan_dusman_bossu_gecmiyor(self):
        """Olceklemeden sonra bataklik agac koku bossundan sert vuruyordu."""
        for ad, m in MAPS.items():
            hedef_atk = MOD.TIER_TARGET[MOD.MAP_TIER[m.name]][1]
            boss_atk = hedef_atk * MOD.BOSS_ATK_X
            for e in m.enemies:
                if e.is_boss:
                    continue
                with self.subTest(harita=ad, tur=e.kind):
                    self.assertLess(e.atk, boss_atk,
                                    "%s/%s %d vuruyor, kademe bossu %.0f"
                                    % (ad, e.kind, e.atk, boss_atk))

    def test_bosslar_kademesiyle_guclenir(self):
        bosslar = []
        for ad, m in MAPS.items():
            for e in m.enemies:
                if e.is_boss:
                    bosslar.append((MOD.MAP_TIER[m.name], e.max_hp, e.kind))
        bosslar.sort()
        for (k1, hp1, n1), (k2, hp2, n2) in zip(bosslar, bosslar[1:]):
            if k1 == k2:
                continue
            self.assertLess(hp1, hp2, "%s (adim %d) %s'den (adim %d) guclu"
                            % (n1, k1, n2, k2))

    def test_boss_kendi_haritasinin_en_sertidir(self):
        for ad, m in MAPS.items():
            boss = [e for e in m.enemies if e.is_boss]
            if not boss:
                continue
            en_sert = max(e.max_hp for e in m.enemies if not e.is_boss)
            with self.subTest(harita=ad):
                self.assertGreater(boss[0].max_hp, en_sert,
                                   "%s: boss siradan dusmandan zayif" % ad)

    def test_xp_sertlikle_birlikte_artiyor(self):
        """Sert harita cok kazandirmali, yoksa seviye egrinin gerisinde kalir."""
        veri = []
        for ad, m in MAPS.items():
            normal = [e for e in m.enemies if not e.is_boss]
            if not normal:
                continue
            veri.append((MOD.MAP_TIER[m.name],
                         sum(e.xp_r for e in normal) / float(len(normal))))
        ilk = [x for k, x in veri if k <= 1]
        son = [x for k, x in veri if k >= 4]
        self.assertLess(sum(ilk) / len(ilk), sum(son) / len(son),
                        "uzak haritalar daha cok XP vermiyor")


class TestBossAdi(unittest.TestCase):
    """Kullanici bildirdi: boss adi ingilizce gorunuyordu."""

    def test_hicbir_boss_adi_ham_kimlik_degil(self):
        for ad, m in MAPS.items():
            for e in m.enemies:
                if not e.is_boss:
                    continue
                bid = getattr(e, "boss_id", None)
                gorunen = MOD.boss_name(bid, e.kind)
                with self.subTest(harita=ad, tur=e.kind):
                    # Ad ceviri tablosundan gelmeli, tur kimliginden degil.
                    # (Malachar'in ozel adi kimligiyle AYNI oldugu icin
                    # "kimlige esit olmasin" kurali yanlis alarm veriyordu.)
                    self.assertIn(bid, MOD.BOSSES, "%s kimliksiz boss" % e.kind)
                    self.assertEqual(gorunen, MOD.T_(MOD.BOSSES[bid]["name"]),
                                     "%s adi ceviri tablosundan gelmiyor" % e.kind)
                    self.assertNotIn("_", gorunen,
                                     "%r ham kimlik gibi duruyor" % gorunen)

    def test_boss_adi_bes_dilde_degisiyor(self):
        """Ad gercekten cevriliyorsa diller arasinda farklilasir."""
        eski = MOD.CFG.data.get("language", "TR")
        try:
            for bid, b in MOD.BOSSES.items():
                if bid == "malachar":
                    continue           # ozel ad, her dilde ayni
                gorulen = set()
                for code in MOD.LANG_CODES:
                    MOD.CFG.data["language"] = code
                    gorulen.add(MOD.boss_name(bid, b["kind"]))
                with self.subTest(boss=bid):
                    self.assertGreater(len(gorulen), 1,
                                       "%s her dilde ayni: cevrilmemis olabilir" % bid)
        finally:
            MOD.CFG.data["language"] = eski

    def test_ad_can_cubuguna_siğiyor(self):
        """Etiket "AD can/maxcan" seklinde; kutuyu tasmasin."""
        yazi = MOD._tag_font()
        eski = MOD.CFG.data.get("language", "TR")
        try:
            for code in MOD.LANG_CODES:
                MOD.CFG.data["language"] = code
                for bid, b in MOD.BOSSES.items():
                    etiket = "%s 999/999" % MOD.boss_name(bid, b["kind"])
                    with self.subTest(dil=code, boss=bid):
                        self.assertLess(yazi.size(etiket)[0], MOD.SW // 2,
                                        "%s/%s etiketi cok uzun" % (code, bid))
        finally:
            MOD.CFG.data["language"] = eski


if __name__ == "__main__":
    unittest.main(verbosity=2)
