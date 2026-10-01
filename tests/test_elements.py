#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Element sistemi ve dusman dayanikliligi testleri.

Kullanici "bazi dusmanlar cok cabuk yeniliyor" dedi. Olctum: balcik sv1
savascinin 2 vurusunda oluyordu. Cozum sadece HP eklemek degil -- o dovusu
uzatir, ilginc yapmaz. Her dusmana ve her saldiriya bir element verildi:
dogru elementle vurmak odullendiriyor, yanlisiyla vurmak dusmani belirgin
bicimde dayanikli yapiyor.

Testler iki seyi koruyor: denge (hicbir dusman 3 vurustan cabuk olmesin,
hicbiri de abartili dayanikli olmasin) ve adalet (hicbir sinif bir dusman
turune karsi caresiz kalmasin).

Calistirmak icin: python -m unittest discover -s tests
"""
import math
import os
import shutil
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import unittest

import pygame

from harness import load_game_module

MOD = None
TMP = None
G = None


def setUpModule():
    global MOD, TMP, G
    MOD = load_game_module("pixel_rpg_elements")
    TMP = tempfile.mkdtemp(prefix="pixelrpg_elem_")
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


def enemy_kinds():
    turler = {}
    for key, m in G.maps.items():
        for e in m.enemies:
            turler.setdefault(e.kind, []).append(e)
    return turler


def _game(char_class="warrior"):
    g = MOD.Game.__new__(MOD.Game)
    g.ui = MOD.UI()
    g.ps = MOD.PS()
    g._reset()
    g.temp_stats = MOD.PlayerStats(char_class)
    g._start_game()
    return g


class TestChart(unittest.TestCase):
    def test_every_enemy_has_a_known_element(self):
        for kind, liste in enemy_kinds().items():
            el = MOD.ENEMY_ELEM.get(kind)
            self.assertIsNotNone(el, "%s icin element tanimlanmamis" % kind)
            self.assertIn(el, MOD.ELEMENTS, "%s tanimsiz element kullaniyor: %s" % (kind, el))
            for e in liste:
                self.assertEqual(e.elem, el, "%s ornegi farkli element tasiyor" % kind)

    def test_physical_is_neutral(self):
        """Fiziksel herkesin temel saldirisi; cezalandirilirsa savasci ve okcu
        gol ge dusmanlara karsi caresiz kalir."""
        for hedef in MOD.ELEMENTS:
            self.assertEqual(MOD.elem_mult("physical", hedef), 1.0,
                             "fiziksel %s karsisinda notr degil" % hedef)

    def test_elements_resist_themselves(self):
        for el in MOD.ELEMENTS:
            if el == "physical":
                continue
            self.assertLess(MOD.elem_mult(el, el), 1.0,
                            "%s kendi elementine karsi dirensiz" % el)

    def test_multipliers_stay_in_a_sane_range(self):
        for saldiri, tablo in MOD.ELEM_CHART.items():
            for hedef, k in tablo.items():
                self.assertGreaterEqual(k, 0.35, "%s->%s carpani cok dusuk" % (saldiri, hedef))
                self.assertLessEqual(k, 2.0, "%s->%s carpani cok yuksek" % (saldiri, hedef))

    def test_every_enemy_element_has_a_counter(self):
        """Her dusman elementine karsi en az bir ustun element olmali."""
        for el in set(MOD.ENEMY_ELEM.values()):
            en_iyi = max(MOD.ELEMENTS, key=lambda a: MOD.elem_mult(a, el))
            self.assertGreater(MOD.elem_mult(en_iyi, el), 1.2,
                               "%s elementine karsi iyi bir secenek yok" % el)

    def test_element_names_are_translated(self):
        eski = MOD.CFG.data.get("language", "TR")
        try:
            for code in MOD.LANG_CODES:
                MOD.CFG.data["language"] = code
                for el in MOD.ELEMENTS:
                    ad = MOD.elem_name(el)
                    self.assertTrue(ad.strip() and not ad.startswith("ui."),
                                    "%s/%s cevrilmemis: %r" % (code, el, ad))
        finally:
            MOD.CFG.data["language"] = eski


class TestDifficulty(unittest.TestCase):
    """Kullanicinin sikayeti: bazi dusmanlar cok cabuk yeniliyor."""

    def hits_to_kill(self, kind, char_class="warrior"):
        st = MOD.PlayerStats(char_class)
        vurus = max(1, int(st.attack * 1.1))
        hp = min(e.max_hp for e in enemy_kinds()[kind])
        k = MOD.elem_mult("physical", MOD.ENEMY_ELEM.get(kind, "physical"))
        return math.ceil(hp / max(1, int(vurus * k)))

    def test_nothing_dies_in_two_hits(self):
        for kind in enemy_kinds():
            if kind == "malachar":
                continue
            n = self.hits_to_kill(kind)
            self.assertGreaterEqual(n, 3, "%s sv1 oyuncunun %d vurusunda oluyor" % (kind, n))

    def test_trash_enemies_are_not_sponges(self):
        """Zorluk dayaniklilikla degil elementle gelmeli; cop dusman da
        dakikalarca dovusmemeli."""
        for kind in ("slime", "wolf", "boar", "goblin"):
            n = self.hits_to_kill(kind)
            self.assertLessEqual(n, 6, "%s cok dayanikli: %d vurus" % (kind, n))

    def test_the_boss_is_a_boss(self):
        self.assertGreaterEqual(min(e.max_hp for e in enemy_kinds()["malachar"]), 500)

    def test_tuning_applies_to_every_instance(self):
        """Carpanlar tek yerde; her Enemy(...) satirini elle duzeltmek gerekmesin."""
        for kind, (hp_k, atk_k) in MOD.ENEMY_TUNE.items():
            ornek = enemy_kinds().get(kind)
            if not ornek:
                continue
            self.assertGreater(hp_k, 0.5)
            self.assertLess(hp_k, 3.0)

    def test_right_element_is_clearly_better(self):
        """Dogru elementi secmek fark yaratmali, yoksa sistem suslemeden ibaret."""
        for kind in enemy_kinds():
            el = MOD.ENEMY_ELEM.get(kind, "physical")
            en_iyi = max(MOD.ELEMENTS, key=lambda a: MOD.elem_mult(a, el))
            kazanc = MOD.elem_mult(en_iyi, el) / MOD.elem_mult("physical", el)
            self.assertGreater(kazanc, 1.15, "%s icin element secmek fark etmiyor" % kind)


class TestFairness(unittest.TestCase):
    def test_no_class_is_helpless_against_any_enemy(self):
        """Her sinifin her dusman turune karsi en az notr bir secenegi olmali."""
        for cc, temel in MOD.CLASS_ELEM.items():
            secenek = {temel}
            for ab in MOD.ABILITIES[cc]:
                secenek.add(MOD.ABILITY_ELEM.get(ab["id"], "physical"))
            for kind, el in MOD.ENEMY_ELEM.items():
                en_iyi = max(MOD.elem_mult(a, el) for a in secenek)
                self.assertGreaterEqual(en_iyi, 1.0,
                                        "%s sinifinin %s karsisinda notr secenegi bile yok"
                                        % (cc, kind))

    def test_weapons_change_the_attack_element(self):
        g = _game("mage")
        varsayilan = g._attack_elem()
        g.player.stats.equipment["weapon"] = "elder_staff"
        self.assertEqual(g._attack_elem(), "ice", "silah elementi temel saldiriya gecmiyor")
        g.player.stats.equipment["weapon"] = None
        self.assertEqual(g._attack_elem(), varsayilan)

    def test_every_weapon_has_an_element(self):
        for ik, row in MOD.EQUIP_ITEMS.items():
            if row[3] != "weapon":
                continue
            self.assertIn(ik, MOD.WEAPON_ELEM, "%s silahinin elementi yok" % ik)


class TestDamageApplication(unittest.TestCase):
    def setUp(self):
        self.g = _game("warrior")
        self.e = next(e for e in self.g.cur_map.enemies if e.alive)

    def vur(self, elem, dmg=40):
        self.e.hp = self.e.max_hp = 9999
        self.g.dmg_nums = []
        self.g._hit(self.e, dmg, False, elem)
        return 9999 - self.e.hp

    def test_weakness_increases_damage(self):
        self.e.elem = "nature"
        self.assertGreater(self.vur("fire"), self.vur("physical"),
                           "zayif oldugu element fazla hasar vermiyor")

    def test_resistance_reduces_damage(self):
        self.e.elem = "fire"
        self.assertLess(self.vur("fire"), self.vur("physical"),
                        "dirençli oldugu element az hasar vermiyor")

    def test_damage_is_never_zero(self):
        self.e.elem = "fire"
        self.assertGreaterEqual(self.vur("fire", 1), 1, "hasar sifira dustu")

    def test_player_sees_why(self):
        """Az/cok vurdugunu anlamali, yoksa sistem gorunmez kalir."""
        self.e.elem = "nature"
        self.vur("fire")
        yazilar = [d.get("txt") for d in self.g.dmg_nums]
        self.assertIn(MOD.T_("ui.elem_weak"), yazilar, "zayiflik ekranda soylenmiyor")
        self.e.elem = "fire"
        self.vur("fire")
        yazilar = [d.get("txt") for d in self.g.dmg_nums]
        self.assertIn(MOD.T_("ui.elem_resist"), yazilar, "direnc ekranda soylenmiyor")


class TestPlayerResistance(unittest.TestCase):
    def test_armour_reduces_matching_damage(self):
        g = _game("warrior")
        g.player.stats.equipment = {s: None for s in MOD.EQUIP_SLOTS}
        ciplak = g._player_resist("fire")
        g.player.stats.equipment["armor"] = "mage_robe"      # ates direnci
        self.assertLess(g._player_resist("fire"), ciplak, "zirh ates hasarini azaltmiyor")
        self.assertEqual(g._player_resist("ice"), ciplak, "ilgisiz elemente de etki ediyor")

    def test_resistances_stack_but_stay_sane(self):
        g = _game("warrior")
        g.player.stats.equipment = {s: None for s in MOD.EQUIP_SLOTS}
        g.player.stats.equipment["armor"] = "plate_mail"       # physical 0.75
        g.player.stats.equipment["amulet"] = "warrior_crest"   # physical 0.85
        k = g._player_resist("physical")
        self.assertLess(k, 0.75)
        self.assertGreater(k, 0.5, "direncler birikip hasari sifira yaklastirmamali")

    def test_every_resist_item_is_a_real_item(self):
        for ik in MOD.EQUIP_RESIST:
            self.assertIn(ik, MOD.EQUIP_ITEMS, "%s diye bir ekipman yok" % ik)
            el, k = MOD.EQUIP_RESIST[ik]
            self.assertIn(el, MOD.ELEMENTS)
            self.assertTrue(0.6 <= k < 1.0, "%s koruma carpani uygunsuz: %s" % (ik, k))


if __name__ == "__main__":
    unittest.main(verbosity=2)
