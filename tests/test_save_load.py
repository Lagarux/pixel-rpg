#!/usr/bin/env python3
"""
Faz 4: kayit/yukleme testleri.

Kayit dosyasi haritalari degil, oyuncunun DEGISTIRDIKLERINI tutuyor
(acilan sandiklar, olen dusmanlar). Bu testler tam turu dogruluyor:
oyna -> kaydet -> oyunu sifirla -> yukle -> her sey yerinde mi?

Calistirmak icin: python -m unittest discover -s tests
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import json
import shutil
import tempfile
import unittest

import pygame

from harness import load_game_module

MOD = None
TMP = None


def setUpModule():
    global MOD, TMP
    MOD = load_game_module("pixel_rpg_save")
    TMP = tempfile.mkdtemp(prefix="pixelrpg_save_")
    MOD.SAVE_FILE = os.path.join(TMP, "save1.json")   # kullanicinin kaydina dokunma
    pygame.init()
    pygame.display.set_mode((MOD.SW, MOD.SH))


def tearDownModule():
    pygame.quit()
    shutil.rmtree(TMP, ignore_errors=True)


def _fresh_game():
    """Pencere acmadan, haritalari kurulmus bir Game."""
    g = MOD.Game.__new__(MOD.Game)
    g.ui = MOD.UI()
    g.ps = MOD.PS()
    g._reset()
    return g


def _start_as(g, char_class="mage"):
    g.temp_stats = MOD.PlayerStats(char_class)
    g._start_game()
    return g.player


class TestSaveLoadRoundTrip(unittest.TestCase):
    def setUp(self):
        if os.path.exists(MOD.SAVE_FILE):
            os.remove(MOD.SAVE_FILE)
        self.g = _fresh_game()
        self.p = _start_as(self.g)

    def test_no_save_file_at_start(self):
        self.assertFalse(MOD.has_save(), "temiz baslangicta kayit gorunuyor")
        self.assertFalse(self.g.load_game(), "kayit yokken yukleme basarili dedi")

    def test_round_trip_preserves_player(self):
        st = self.p.stats
        st.level = 7
        st.gold = 321
        st.agi = 9
        st.xp = 40
        st.skill_points = 2
        st.hp = 33
        self.p.inventory = ["hp_pot", "hp_pot", "mp_pot"]
        self.p.quest_items = ["earth_c"]
        st.equipment["weapon"] = "arcane_staff"
        self.p.snap(12, 14)

        self.assertTrue(self.g.save_game(), "kayit yazilamadi")
        self.assertTrue(MOD.has_save())

        g2 = _fresh_game()
        self.assertTrue(g2.load_game(), "kayit okunamadi")
        s2 = g2.player.stats
        self.assertEqual(s2.char_class, "mage")
        self.assertEqual(s2.level, 7)
        self.assertEqual(s2.gold, 321)
        self.assertEqual(s2.agi, 9)
        self.assertEqual(s2.xp, 40)
        self.assertEqual(s2.skill_points, 2)
        self.assertEqual(s2.hp, 33)
        self.assertEqual(s2.equipment["weapon"], "arcane_staff")
        self.assertEqual(sorted(g2.player.inventory), sorted(["hp_pot", "hp_pot", "mp_pot"]))
        self.assertEqual(g2.player.quest_items, ["earth_c"])
        self.assertEqual((g2.player.tx, g2.player.ty), (12, 14))
        self.assertEqual(g2.state, "playing")

    def test_round_trip_preserves_progress_flags(self):
        self.g.flags["ch"] = 4
        self.g.flags["earth_crystal"] = True
        self.g.flags["sq_boar_count"] = 2
        self.g.save_game()

        g2 = _fresh_game()
        g2.load_game()
        self.assertEqual(g2.flags["ch"], 4)
        self.assertTrue(g2.flags["earth_crystal"])
        self.assertEqual(g2.flags["sq_boar_count"], 2)

    def test_opened_chests_stay_opened(self):
        m = self.g.cur_map
        pos = next(iter(m.chests))
        del m.chests[pos]
        m.set(pos[0], pos[1], MOD.T.FLOOR)
        self.g.save_game()

        g2 = _fresh_game()
        g2.load_game()
        m2 = g2.maps[self.g.cur_key]
        self.assertNotIn(pos, m2.chests, "acilan sandik yuklemede geri geldi")
        self.assertNotEqual(m2.get(pos[0], pos[1]), MOD.T.CHEST, "sandik karesi geri geldi")

    def test_untouched_chests_survive(self):
        total = len(self.g.cur_map.chests)
        self.g.save_game()
        g2 = _fresh_game()
        g2.load_game()
        self.assertEqual(len(g2.maps[self.g.cur_key].chests), total,
                         "dokunulmamis sandiklar kayboldu")

    def test_killed_enemies_stay_dead(self):
        m = self.g.maps["dark_forest"]
        victim = m.enemies[0]
        victim.alive = False
        self.g.save_game()

        g2 = _fresh_game()
        g2.load_game()
        self.assertFalse(g2.maps["dark_forest"].enemies[0].alive, "olen dusman dirildi")
        self.assertTrue(g2.maps["dark_forest"].enemies[1].alive, "yasayan dusman olu geldi")

    def test_current_map_is_restored(self):
        self.g.cur_key = "dark_forest"
        self.g.cur_map = self.g.maps["dark_forest"]
        self.g.save_game()
        g2 = _fresh_game()
        g2.load_game()
        self.assertEqual(g2.cur_key, "dark_forest")
        self.assertIs(g2.cur_map, g2.maps["dark_forest"])


class TestSaveRobustness(unittest.TestCase):
    def setUp(self):
        self.g = _fresh_game()
        _start_as(self.g)

    def test_corrupt_save_is_rejected_cleanly(self):
        with open(MOD.SAVE_FILE, "w", encoding="utf-8") as f:
            f.write("{ bu gecerli json degil")
        g2 = _fresh_game()
        self.assertFalse(g2.load_game(), "bozuk kayit yuklendi sayildi")
        self.assertEqual(g2.state, "title", "bozuk kayit sonrasi oyun tuhaf durumda")

    def test_future_save_version_is_rejected(self):
        self.g.save_game()
        with open(MOD.SAVE_FILE, encoding="utf-8") as f:
            data = json.load(f)
        data["version"] = MOD.SAVE_VERSION + 99
        with open(MOD.SAVE_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f)
        g2 = _fresh_game()
        self.assertFalse(g2.load_game(), "tanimadigi surumdeki kaydi yukledi")

    def test_save_is_written_atomically(self):
        """Yarim yazilmis kayit kalmamali: .tmp dosyasi geride birakilmamali."""
        self.g.save_game()
        leftovers = [f for f in os.listdir(os.path.dirname(MOD.SAVE_FILE)) if f.endswith(".tmp")]
        self.assertEqual(leftovers, [], f"gecici kayit dosyasi kaldi: {leftovers}")

    def test_hp_cannot_exceed_max_after_load(self):
        """Kayittaki HP, yuklenen niteliklerin izin verdigi tavani asmamali."""
        self.g.save_game()
        with open(MOD.SAVE_FILE, encoding="utf-8") as f:
            data = json.load(f)
        data["player"]["hp"] = 99999
        with open(MOD.SAVE_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f)
        g2 = _fresh_game()
        self.assertTrue(g2.load_game())
        self.assertLessEqual(g2.player.stats.hp, g2.player.stats.max_hp)


if __name__ == "__main__":
    unittest.main(verbosity=2)
