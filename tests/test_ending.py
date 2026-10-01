#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Kapanis testleri.

Malachar olunce oyun dogrudan uc satirlik bir zafer ekranina atliyordu.
Kullanici "senaryo ve kapanis oyunun en onemli kisimlarindan" dedi. Artik
sayfa sayfa bir epilog var ve oyuncunun NE YAPTIGINA gore degisiyor:
bitirilen yan gorevler epiloga kendi sayfasini ekliyor, kapanis kartinda
unvan ve yolculuk ozeti cikiyor.

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
    MOD = load_game_module("pixel_rpg_ending")
    TMP = tempfile.mkdtemp(prefix="pixelrpg_end_")
    MOD.SAVE_FILE = os.path.join(TMP, "save1.json")
    pygame.init()
    pygame.display.set_mode((MOD.SW, MOD.SH))


def tearDownModule():
    pygame.quit()
    shutil.rmtree(TMP, ignore_errors=True)


def _game():
    g = MOD.Game.__new__(MOD.Game)
    g.ui = MOD.UI()
    g.ps = MOD.PS()
    g._reset()
    g.temp_stats = MOD.PlayerStats("warrior")
    g._start_game()
    return g


def hepsi_bitmis():
    f = {"ch": 6, "earth_crystal": True, "water_crystal": True}
    for sq in MOD.SIDE_QUESTS:
        f["sqpaid_" + sq["id"]] = True
    return f


class TestTrigger(unittest.TestCase):
    def test_boss_defeat_opens_the_epilogue_not_the_victory_screen(self):
        g = _game()
        boss = next(e for e in g.maps["shadow_castle"].enemies if e.kind == "malachar")
        g.cur_key = "shadow_castle"
        g.cur_map = g.maps["shadow_castle"]
        boss.hp = 1
        g._hit(boss, 9999)
        self.assertTrue(g.flags["malachar_defeated"])
        self.assertEqual(g.state, "epilogue", "bos olunce epilog acilmadi")
        self.assertTrue(g.epi_pages, "epilog sayfasi uretilmedi")

    def test_enter_walks_through_and_ends_at_victory(self):
        g = _game()
        g.epi_pages = MOD.epilogue_pages(g.flags)
        g.epi_page = 0
        g.state = "epilogue"
        for _ in range(len(g.epi_pages)):
            self.assertEqual(g.state, "epilogue")
            g.epi_page += 1
            if g.epi_page >= len(g.epi_pages):
                g.state = "victory"
        self.assertEqual(g.state, "victory", "epilog zafer ekranina baglanmiyor")


class TestContent(unittest.TestCase):
    def test_epilogue_reacts_to_what_the_player_did(self):
        az = MOD.epilogue_pages({})
        cok = MOD.epilogue_pages(hepsi_bitmis())
        self.assertGreater(len(cok), len(az),
                           "yan gorevler kapanisi degistirmiyor (%d vs %d)" % (len(cok), len(az)))

    def test_minimum_epilogue_is_still_a_real_ending(self):
        az = MOD.epilogue_pages({})
        self.assertGreaterEqual(len(az), 3, "hicbir sey yapmayan oyuncuya kapanis yok")
        toplam = sum(len(sayfa) for sayfa in az)
        self.assertGreaterEqual(toplam, 10, "kapanis cok kisa: %d satir" % toplam)

    def test_every_page_has_lines(self):
        for kosul, satirlar in MOD.EPILOGUE:
            self.assertTrue(satirlar, "bos epilog sayfasi var")
            self.assertLessEqual(len(satirlar), 5, "sayfa ekrana sigmayacak kadar uzun")

    def test_rank_rises_with_completed_quests(self):
        hic = MOD.ending_rank({})
        hepsi = MOD.ending_rank(hepsi_bitmis())
        self.assertNotEqual(hic, hepsi, "unvan yan goreve gore degismiyor")
        self.assertEqual(hepsi, "epi.rank_legend", "hepsini bitirene en ust unvan verilmiyor")

    def test_every_rank_is_reachable(self):
        gorulen = set()
        for n in range(0, len(MOD.SIDE_QUESTS) + 1):
            f = {}
            for sq in MOD.SIDE_QUESTS[:n]:
                f["sqpaid_" + sq["id"]] = True
            gorulen.add(MOD.ending_rank(f))
        self.assertEqual(len(gorulen), len(MOD.ENDING_RANKS),
                         "bazi unvanlara hic ulasilamiyor: %s" % gorulen)


class TestSummary(unittest.TestCase):
    def test_summary_counts_the_journey(self):
        g = _game()
        g.flags.update({"kill_wolf": 6, "kill_slime": 4, "chests_opened": 7})
        g.player.stats.level = 9
        g.player.stats.gold = 321
        ozet = dict(g._ending_stats())
        self.assertEqual(ozet[MOD.T_("epi.stat_level")], 9)
        self.assertEqual(ozet[MOD.T_("epi.stat_kills")], 10, "oldurulen dusman toplanmiyor")
        self.assertEqual(ozet[MOD.T_("epi.stat_chests")], 7)
        self.assertEqual(ozet[MOD.T_("epi.stat_gold")], 321)

    def test_summary_survives_an_empty_run(self):
        g = _game()
        ozet = g._ending_stats()
        self.assertEqual(len(ozet), 6)      # zorluk + 5 sayac
        for ad, deger in ozet:
            self.assertTrue(str(ad).strip())


class TestPresentation(unittest.TestCase):
    def test_all_ending_text_is_translated(self):
        anahtarlar = {"epi.title"}
        for kosul, satirlar in MOD.EPILOGUE:
            anahtarlar.update(satirlar)
        anahtarlar.update(a for _, a in MOD.ENDING_RANKS)
        anahtarlar.update(["epi.stat_level", "epi.stat_quests", "epi.stat_kills",
                           "epi.stat_chests", "epi.stat_gold"])
        eski = MOD.CFG.data.get("language", "TR")
        try:
            for code in MOD.LANG_CODES:
                MOD.CFG.data["language"] = code
                for k in sorted(anahtarlar):
                    txt = MOD.T_(k)
                    self.assertNotEqual(txt, k, "%s/%s cevrilmemis" % (code, k))
                    self.assertTrue(txt.strip())
        finally:
            MOD.CFG.data["language"] = eski

    def test_lines_fit_on_screen(self):
        eski = MOD.CFG.data.get("language", "TR")
        try:
            for code in MOD.LANG_CODES:
                MOD.CFG.data["language"] = code
                MOD.FontManager.set_language(code)
                ui = MOD.UI()
                for kosul, satirlar in MOD.EPILOGUE:
                    for k in satirlar:
                        w = ui.fmd.size(MOD.T_(k))[0]
                        self.assertLess(w, MOD.SW - 40,
                                        "%s/%s ekrandan tasiyor (%d px)" % (code, k, w))
        finally:
            MOD.CFG.data["language"] = eski
            MOD.FontManager.set_language(eski)

    def test_screens_are_not_blank(self):
        g = _game()
        for cizim in (lambda s: g.ui.draw_epilogue(s, MOD.EPILOGUE[0][1], 0, 5, 0),
                      lambda s: g.ui.draw_victory(s, 0, g._ending_stats(),
                                                  MOD.ending_rank(hepsi_bitmis()))):
            surf = pygame.Surface((MOD.SW, MOD.SH))
            surf.fill((0, 0, 0))
            cizim(surf)
            boyali = sum(1 for x in range(0, MOD.SW, 4) for y in range(0, MOD.SH, 4)
                         if surf.get_at((x, y))[:3] != (0, 0, 0))
            self.assertGreater(boyali, 500, "kapanis ekrani neredeyse bos")


if __name__ == "__main__":
    unittest.main(verbosity=2)
