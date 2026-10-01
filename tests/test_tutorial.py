#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Kontrol tanitimi testleri.

Oyun ici soluk tus listesi yerine, oyuna baslarken BIR KEZ acilan klavye
gorseli. Testler: dogru anda acildigi, bir kez acildigi, herhangi bir tusla
kapandigi ve tercihin saklandigi.

Calistirmak icin: python -m unittest discover -s tests
"""
import os
import shutil
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import unittest

import pygame

from harness import Harness, load_game_module

MOD = None
TMP = None


def setUpModule():
    global MOD, TMP
    MOD = load_game_module("pixel_rpg_tutorial")
    TMP = tempfile.mkdtemp(prefix="pixelrpg_tut_")
    MOD.SAVE_FILE = os.path.join(TMP, "save1.json")
    pygame.init()
    pygame.display.set_mode((MOD.SW, MOD.SH))


def tearDownModule():
    pygame.quit()
    shutil.rmtree(TMP, ignore_errors=True)


def _game(seen):
    MOD.CFG.data["tutorial_seen"] = seen
    g = MOD.Game.__new__(MOD.Game)
    g.ui = MOD.UI()
    g.ps = MOD.PS()
    g._reset()
    g.temp_stats = MOD.PlayerStats("warrior")
    g._start_game()
    return g


class TestWhenItOpens(unittest.TestCase):
    def tearDown(self):
        MOD.CFG.data["tutorial_seen"] = True

    def test_first_game_opens_the_tutorial(self):
        self.assertEqual(_game(False).state, "tutorial")

    def test_later_games_skip_it(self):
        self.assertEqual(_game(True).state, "playing")

    def test_player_exists_behind_the_tutorial(self):
        """Tanitim kapaninca oyun hazir olmali; arkasi bos ekran olmasin."""
        g = _game(False)
        self.assertIsNotNone(g.player)
        self.assertEqual(g.cur_key, "ashveil")


class TestDismissal(unittest.TestCase):
    """Gercek tus olayiyla, oyun dongusu uzerinden."""

    def test_any_key_closes_it_and_is_remembered(self):
        mod = load_game_module("pixel_rpg_tut_run")
        mod.SAVE_FILE = os.path.join(TMP, "save2.json")
        mod.CFG.data["tutorial_seen"] = False
        kaydedildi = []

        def casus_kur(_g):
            # Kosum takimi CFG.save'i kendi kapatiyor; casusu ONDAN SONRA kur.
            mod.CFG.save = lambda: kaydedildi.append(True)

        H = Harness(mod, shot_prefix="_tut_")
        durumlar = []
        H.run(H.intro() + [
            H.do(lambda g: durumlar.append(g.state)),
            H.do(casus_kur),
            H.key(pygame.K_i, 6),                  # herhangi bir tus
            H.do(lambda g: durumlar.append(g.state)),
        ])
        self.assertEqual(durumlar[0], "tutorial", "oyun basinda tanitim acilmadi")
        self.assertEqual(durumlar[1], "playing", "tus basildi ama tanitim kapanmadi")
        self.assertTrue(mod.CFG.data["tutorial_seen"], "tercih isaretlenmedi")
        self.assertTrue(kaydedildi, "tercih diske yazilmadi -- her acilista tekrar cikar")


class TestPauseMenu(unittest.TestCase):
    def test_controls_entry_exists(self):
        etiketler = [e[0] for e in MOD.UI.pause_opts()]
        self.assertIn(MOD.T_("ui.pause_controls"), etiketler)

    def test_pause_options_follow_the_language(self):
        """Liste sabit bir sinif niteligiyken dil degisince eski dilde kaliyordu."""
        eski = MOD.CFG.data.get("language", "TR")
        try:
            MOD.CFG.data["language"] = "TR"
            tr = [e[0] for e in MOD.UI.pause_opts()]
            MOD.CFG.data["language"] = "DE"
            de = [e[0] for e in MOD.UI.pause_opts()]
            self.assertNotEqual(tr, de, "dil degisti ama duraklatma menusu degismedi")
        finally:
            MOD.CFG.data["language"] = eski


class TestDrawing(unittest.TestCase):
    def test_panel_is_not_blank(self):
        g = _game(True)
        surf = pygame.Surface((MOD.SW, MOD.SH))
        surf.fill((0, 0, 0))
        g.ui.draw_tutorial(surf, 0)
        boyali = sum(1 for x in range(0, MOD.SW, 4) for y in range(0, MOD.SH, 4)
                     if surf.get_at((x, y))[:3] != (0, 0, 0))
        self.assertGreater(boyali, 2000, "tanitim paneli neredeyse bos ciziliyor")

    def test_arrow_keycaps_draw_a_triangle(self):
        """Ok glifi her yazi tipinde yok; ucgen ciziyoruz."""
        g = _game(True)
        s1 = pygame.Surface((40, 40)); s1.fill((0, 0, 0))
        s2 = pygame.Surface((40, 40)); s2.fill((0, 0, 0))
        g.ui.keycap(s1, 2, 2, 34, 34, "", ok="left")
        g.ui.keycap(s2, 2, 2, 34, 34, "", ok="right")
        beyaz = lambda s: {(x, y) for x in range(40) for y in range(40)
                           if s.get_at((x, y))[:3] == (245, 246, 250)}
        a, b = beyaz(s1), beyaz(s2)
        self.assertTrue(a, "sol ok cizilmedi")
        self.assertTrue(b, "sag ok cizilmedi")
        self.assertNotEqual(a, b, "sol ve sag ok ayni ciziliyor")

    def test_hud_no_longer_lists_keys(self):
        """Soluk tus listesi kalkti; cevirileri de oksuz birakmadik."""
        kok = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        with open(os.path.join(kok, "pixel_rpg.py"), encoding="utf-8") as f:
            src = f.read()
        self.assertNotIn("ui.key_", src, "HUD hala tus listesi ciziyor")
        import json
        with open(os.path.join(kok, "assets", "locales", "tr.json"), encoding="utf-8") as f:
            keys = json.load(f)
        oksuz = [k for k in keys if k.startswith("ui.key_")]
        self.assertEqual(oksuz, [], "kullanilmayan ceviri anahtarlari kaldi: %s" % oksuz)


class TestTranslations(unittest.TestCase):
    def test_every_tutorial_string_is_translated(self):
        anahtarlar = ["ui.tut_title", "ui.tut_move", "ui.tut_or", "ui.tut_attack",
                      "ui.tut_interact", "ui.tut_ability", "ui.tut_inventory",
                      "ui.tut_quests", "ui.tut_minimap", "ui.tut_stats",
                      "ui.tut_settings", "ui.tut_pause", "ui.tut_fullscreen",
                      "ui.tut_again", "ui.tut_start", "ui.pause_controls"]
        eski = MOD.CFG.data.get("language", "TR")
        try:
            for code in MOD.LANG_CODES:
                MOD.CFG.data["language"] = code
                for k in anahtarlar:
                    txt = MOD.T_(k)
                    self.assertTrue(txt.strip(), "%s/%s bos" % (code, k))
                    self.assertNotEqual(txt, k, "%s/%s cevrilmemis" % (code, k))
        finally:
            MOD.CFG.data["language"] = eski


if __name__ == "__main__":
    unittest.main(verbosity=2)
