#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Zorluk seviyesi testleri.

Bes seviye: Kolay / Orta / Zor / Cok Zor / Hardcore.

Tasarim karari: carpanlar dusman kurulurken DEGIL, hasar hesaplanirken
uygulaniyor. Dusmanlarin can degerlerine dokunsaydik, kayitli bir oyun
baska bir zorlukta yuklendiginde eski degerlerle devam ederdi -- cunku
haritalar _reset()'te kuruluyor, kayit ondan sonra okunuyor. Bir test
bunu kayda geciriyor.

Calistirmak icin: python -m unittest discover -s tests
"""
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


def setUpModule():
    global MOD, TMP
    MOD = load_game_module("pixel_rpg_difficulty")
    TMP = tempfile.mkdtemp(prefix="pixelrpg_diff_")
    MOD.SAVE_FILE = os.path.join(TMP, "save1.json")
    pygame.init()
    pygame.display.set_mode((MOD.SW, MOD.SH))


def tearDownModule():
    pygame.quit()
    shutil.rmtree(TMP, ignore_errors=True)


def _game(did="normal"):
    MOD.CFG.data["difficulty"] = did
    g = MOD.Game.__new__(MOD.Game)
    g.ui = MOD.UI()
    g.ps = MOD.PS()
    g._reset()
    g.temp_stats = MOD.PlayerStats("warrior")
    g._start_game()
    return g


class TestTable(unittest.TestCase):
    def tearDown(self):
        MOD.CFG.data["difficulty"] = "normal"

    def test_five_levels(self):
        self.assertEqual(len(MOD.DIFFICULTIES), 5)
        self.assertEqual(MOD.DIFF_IDS,
                         ["easy", "normal", "hard", "brutal", "hardcore"])

    def test_normal_is_neutral(self):
        d = MOD.difficulty("normal")
        self.assertEqual((d[2], d[3], d[4], d[5]), (1.0, 1.0, 1.0, 1.0),
                         "Orta seviye notr olmali")

    def test_harder_means_you_hit_softer_and_get_hit_harder(self):
        onceki = None
        for did in MOD.DIFF_IDS:
            d = MOD.difficulty(did)
            if onceki:
                self.assertLess(d[2], onceki[2], "%s: verilen hasar artmis" % did)
                self.assertGreater(d[3], onceki[3], "%s: alinan hasar azalmis" % did)
            onceki = d

    def test_harder_pays_better(self):
        onceki = None
        for did in MOD.DIFF_IDS:
            d = MOD.difficulty(did)
            if onceki:
                self.assertGreaterEqual(d[4], onceki[4], "%s: altin odulu dusmus" % did)
                self.assertGreaterEqual(d[5], onceki[5], "%s: xp odulu dusmus" % did)
            onceki = d

    def test_only_hardcore_is_permanent(self):
        for did in MOD.DIFF_IDS:
            self.assertEqual(MOD.difficulty(did)[6], did == "hardcore",
                             "%s seviyesinde kalici olum yanlis" % did)

    def test_unknown_value_falls_back_to_normal(self):
        self.assertEqual(MOD.difficulty("olmayan_seviye")[0], "normal")

    def test_every_level_has_a_colour(self):
        for did in MOD.DIFF_IDS:
            self.assertIn(did, MOD.DIFF_COL, "%s icin renk yok" % did)


class TestDamage(unittest.TestCase):
    def tearDown(self):
        MOD.CFG.data["difficulty"] = "normal"

    def _dealt(self, did):
        g = _game(did)
        e = next(x for x in g.cur_map.enemies if x.alive)
        e.elem = "physical"
        e.hp = e.max_hp = 100000
        g.dmg_nums = []
        g._hit(e, 100, False, "physical")
        return 100000 - e.hp

    def _taken(self, did):
        g = _game(did)
        g.player.stats.hp = 100000      # max_hp salt okunur; olmemesi yeter
        g.player.invincible = 0
        return g._player_take_hit(60)

    def test_easy_hits_harder_than_hardcore(self):
        self.assertGreater(self._dealt("easy"), self._dealt("hardcore"),
                           "zorluk verilen hasari degistirmiyor")

    def test_hardcore_hurts_more_than_easy(self):
        self.assertGreater(self._taken("hardcore"), self._taken("easy"),
                           "zorluk alinan hasari degistirmiyor")

    def test_damage_never_drops_to_zero(self):
        for did in MOD.DIFF_IDS:
            g = _game(did)
            e = next(x for x in g.cur_map.enemies if x.alive)
            e.hp = e.max_hp = 100000
            g.dmg_nums = []
            g._hit(e, 1, False, "fire")
            self.assertGreaterEqual(100000 - e.hp, 1, "%s: hasar sifira dustu" % did)

    def test_enemy_health_is_the_same_on_every_difficulty(self):
        """Tasarim karari: carpanlar hasar aninda uygulaniyor, dusman
        kurulurken degil. Boylece kayit baska bir zorlukta yuklenebiliyor."""
        canlar = {}
        for did in MOD.DIFF_IDS:
            g = _game(did)
            canlar[did] = sorted(e.max_hp for e in g.maps["dark_forest"].enemies)
        ilk = canlar[MOD.DIFF_IDS[0]]
        for did, v in canlar.items():
            self.assertEqual(v, ilk,
                             "%s: dusman canlari degismis -- kayit yuklemede tutarsizlik olur" % did)


class TestPermadeath(unittest.TestCase):
    def setUp(self):
        self.yol = MOD.SAVE_FILE

    def tearDown(self):
        MOD.CFG.data["difficulty"] = "normal"
        if os.path.exists(self.yol):
            os.remove(self.yol)

    def _oldur(self, did):
        g = _game(did)
        g.save_game()
        self.assertTrue(os.path.isfile(self.yol), "kayit olusmadi")
        g.player.invincible = 0
        g.player.stats.hp = 1
        g._player_take_hit(9999)
        return g

    def test_hardcore_death_erases_the_save(self):
        g = self._oldur("hardcore")
        self.assertEqual(g.state, "gameover")
        self.assertFalse(os.path.isfile(self.yol), "hardcore'da kayit silinmedi")

    def test_normal_death_keeps_the_save(self):
        g = self._oldur("normal")
        self.assertEqual(g.state, "gameover")
        self.assertTrue(os.path.isfile(self.yol), "normal olumde kayit silindi")

    def test_no_resave_after_a_hardcore_death(self):
        """Olduken sonra otomatik kayit kaydi geri yazmamali."""
        g = self._oldur("hardcore")
        self.assertFalse(g.save_game(), "hardcore olumunden sonra tekrar kaydedildi")
        self.assertFalse(os.path.isfile(self.yol))


class TestSettings(unittest.TestCase):
    def tearDown(self):
        MOD.CFG.data["difficulty"] = "normal"

    def test_difficulty_is_remembered(self):
        self.assertIn("difficulty", MOD.Settings.DEFAULTS)
        self.assertEqual(MOD.Settings.DEFAULTS["difficulty"], "normal")

    def test_cycling_wraps_around(self):
        g = _game("normal")
        MOD.CFG.data["difficulty"] = MOD.DIFF_IDS[-1]
        g._cycle_difficulty(+1)
        self.assertEqual(MOD.CFG.data["difficulty"], MOD.DIFF_IDS[0], "ileri sarma donmuyor")
        g._cycle_difficulty(-1)
        self.assertEqual(MOD.CFG.data["difficulty"], MOD.DIFF_IDS[-1], "geri sarma donmuyor")

    def test_names_and_descriptions_translated(self):
        eski = MOD.CFG.data.get("language", "TR")
        try:
            for code in MOD.LANG_CODES:
                MOD.CFG.data["language"] = code
                for d in MOD.DIFFICULTIES:
                    for k in (d[1], d[1] + "_desc"):
                        txt = MOD.T_(k)
                        self.assertNotEqual(txt, k, "%s/%s cevrilmemis" % (code, k))
                        self.assertTrue(txt.strip())
                for k in ("ui.diff_title", "ui.diff_subtitle", "ui.diff_hint",
                          "ui.diff_permadeath", "ui.diff_dealt", "ui.diff_taken"):
                    self.assertNotEqual(MOD.T_(k), k, "%s/%s cevrilmemis" % (code, k))
        finally:
            MOD.CFG.data["language"] = eski

    def test_screen_is_not_blank(self):
        g = _game("normal")
        surf = pygame.Surface((MOD.SW, MOD.SH))
        surf.fill((0, 0, 0))
        g.ui.draw_difficulty(surf, 4, 0)
        boyali = sum(1 for x in range(0, MOD.SW, 4) for y in range(0, MOD.SH, 4)
                     if surf.get_at((x, y))[:3] != (0, 0, 0))
        self.assertGreater(boyali, 2000, "zorluk ekrani neredeyse bos")


if __name__ == "__main__":
    unittest.main(verbosity=2)
