#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Mini harita testleri.

Mini haritanin isi sadakat degil okunabilirlik: oyuncu nerede oldugunu ve
nereye gidebilecegini bir bakista gormeli. Testler bunu olcuyor -- yurunen
karelerin engellerden gercekten daha parlak oldugunu, isaretlerin dogru
kaydigini ve panelin yan gorev panelini ortmedigini.

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
    MOD = load_game_module("pixel_rpg_mini")
    TMP = tempfile.mkdtemp(prefix="pixelrpg_mini_")
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


def _frame(g, tick=0):
    """Mini haritayi bos bir yuzeye cizip yuzeyi verir."""
    surf = pygame.Surface((MOD.SW, MOD.SH))
    surf.fill((0, 0, 0))
    g.ui.draw_minimap(surf, g.cur_map, g.player, tick)
    return surf


def _white_pixels(surf):
    """Oyuncu noktasi: neredeyse beyaz pikseller."""
    out = []
    for x in range(MOD.SW - 200, MOD.SW):
        for y in range(0, 200):
            r, gg, b = surf.get_at((x, y))[:3]
            if r > 230 and gg > 230 and b > 230:
                out.append((x, y))
    return out


class TestLegibility(unittest.TestCase):
    def test_walkable_tiles_are_brighter_than_blocked(self):
        """Mini haritanin tek isi bu: yol ile duvar ayrilmali."""
        UI = MOD.UI
        for w, b in ((MOD.T.GRASS, MOD.T.TREE), (MOD.T.FLOOR, MOD.T.WALL),
                     (MOD.T.DIRT, MOD.T.STONE), (MOD.T.SAND, MOD.T.CACTUS)):
            wc, bc = UI.mini_tile_col(w), UI.mini_tile_col(b)
            self.assertGreater(sum(wc), sum(bc),
                               "yurunen kare (%s) engelden (%s) parlak degil" % (wc, bc))

    def test_every_tile_kind_has_a_colour(self):
        for name in dir(MOD.T):
            if name.startswith("_"):
                continue
            k = getattr(MOD.T, name)
            if not isinstance(k, int):
                continue
            c = MOD.UI.mini_tile_col(k)
            self.assertEqual(len(c), 3, "%s icin renk uretilmedi" % name)
            self.assertTrue(all(0 <= v <= 255 for v in c), "%s: gecersiz renk %s" % (name, c))


class TestGeometry(unittest.TestCase):
    def test_every_map_fits_on_screen(self):
        g = _game()
        for key, m in g.maps.items():
            ppt = max(2, min(MOD.UI.MINI_W // m.w, MOD.UI.MINI_H // m.h))
            mw, mh = m.w * ppt, m.h * ppt
            px = MOD.SW - mw - 16
            self.assertGreaterEqual(px, 0, "%s: mini harita ekrandan tasiyor" % key)
            self.assertLessEqual(mw, MOD.UI.MINI_W + 2 * ppt, "%s: cok genis" % key)
            self.assertLessEqual(mh, MOD.UI.MINI_H + 2 * ppt, "%s: cok yuksek" % key)

    def test_does_not_cover_side_quest_panel(self):
        """Iki panel de sag tarafta; ust uste binmemeliler."""
        g = _game()
        en_yuksek = 0
        for m in g.maps.values():
            ppt = max(2, min(MOD.UI.MINI_W // m.w, MOD.UI.MINI_H // m.h))
            en_yuksek = max(en_yuksek, 6 + m.h * ppt + 10)   # ust bosluk + panel dolgusu
        # Yan gorev paneli: en fazla 4 satir
        sq_ph = 32 + 4 * 22
        sq_py = MOD.SH // 2 - sq_ph // 2 - 40
        self.assertLess(en_yuksek, sq_py,
                        "mini harita (alt kenar %d) yan gorev panelini (ust %d) ortuyor"
                        % (en_yuksek, sq_py))


class TestNoOverlap(unittest.TestCase):
    """Mini harita ile HUD ayni pikseli boyamamali.

    Mini harita ilk konuldugunda sag ust kosedeki kontrol ipuclarini tamamen
    ortuyordu; ipuclari sol panelin altina tasindi. Bu test iki katmani ayri
    yuzeylere cizip ortak boyanan piksel sayiyor -- renk tahminine gerek yok.
    """

    def _painted(self, cizen):
        surf = pygame.Surface((MOD.SW, MOD.SH))
        surf.fill((0, 0, 0))
        cizen(surf)
        return surf

    def test_minimap_does_not_cover_hud(self):
        g = _game()
        hud = self._painted(lambda s: g.ui.draw_hud(
            s, g.player, MOD.T_(g.cur_map.name), g.flags["ch"], "Test", 0))
        mini = self._painted(lambda s: g.ui.draw_minimap(s, g.cur_map, g.player, 0))
        cakisan = 0
        for x in range(MOD.SW):
            for y in range(MOD.SH):
                if hud.get_at((x, y))[:3] != (0, 0, 0) and mini.get_at((x, y))[:3] != (0, 0, 0):
                    cakisan += 1
        self.assertEqual(cakisan, 0, "mini harita HUD ile %d pikselde cakisiyor" % cakisan)

    def test_minimap_does_not_cover_ability_bar(self):
        g = _game()
        bar = self._painted(lambda s: g.ui.draw_ability_bar(s, g.player.stats, 0))
        mini = self._painted(lambda s: g.ui.draw_minimap(s, g.cur_map, g.player, 0))
        cakisan = sum(1 for x in range(MOD.SW) for y in range(MOD.SH)
                      if bar.get_at((x, y))[:3] != (0, 0, 0)
                      and mini.get_at((x, y))[:3] != (0, 0, 0))
        self.assertEqual(cakisan, 0, "mini harita yetenek cubugunu ortuyor")


class TestMarkers(unittest.TestCase):
    def setUp(self):
        self.g = _game()

    def test_player_dot_moves_with_the_player(self):
        self.g.player.snap(6, 6)
        sol = _white_pixels(_frame(self.g))
        self.assertTrue(sol, "oyuncu noktasi cizilmedi")
        self.g.player.snap(24, 20)
        sag = _white_pixels(_frame(self.g))
        self.assertTrue(sag, "oyuncu tasininca nokta kayboldu")
        self.assertGreater(min(x for x, _ in sag), min(x for x, _ in sol),
                           "oyuncu saga gitti ama nokta saga kaymadi")
        self.assertGreater(min(y for _, y in sag), min(y for _, y in sol),
                           "oyuncu asagi gitti ama nokta asagi kaymadi")

    def test_dead_enemies_are_not_shown(self):
        m = self.g.cur_map
        if not m.enemies:
            m = self.g.maps["dark_forest"]
            self.g.cur_key = "dark_forest"
            self.g.cur_map = m
        kirmizi = lambda s: sum(1 for x in range(MOD.SW - 200, MOD.SW) for y in range(0, 200)
                                if s.get_at((x, y))[:3] == MOD.UI_RD)
        once = kirmizi(_frame(self.g))
        for e in m.enemies:
            e.alive = False
        sonra = kirmizi(_frame(self.g))
        self.assertGreater(once, 0, "yasayan dusmanlar mini haritada gorunmuyor")
        self.assertEqual(sonra, 0, "olu dusmanlar mini haritada duruyor")

    def test_opened_chest_disappears_from_map_and_terrain(self):
        """Sandik karesi acilinca zemine donuyor; onbellege alinmis zemin
        bayat sandik gostermemeli."""
        m = self.g.cur_map
        self.assertTrue(m.chests, "koy haritasinda sandik yok, test anlamsiz")
        altin = lambda s: sum(1 for x in range(MOD.SW - 200, MOD.SW) for y in range(0, 200)
                              if s.get_at((x, y))[:3] == MOD.UI_GD)
        once = altin(_frame(self.g))
        for (tx, ty) in list(m.chests):
            del m.chests[(tx, ty)]
            m.set(tx, ty, MOD.T.FLOOR)
        sonra = altin(_frame(self.g))
        self.assertGreater(once, 0, "sandiklar mini haritada gorunmuyor")
        self.assertEqual(sonra, 0, "acilan sandik mini haritada kaldi")


class TestCaching(unittest.TestCase):
    def test_terrain_is_cached_per_map(self):
        g = _game()
        MOD.UI._mini_terrain.clear()
        _frame(g)
        self.assertEqual(len(MOD.UI._mini_terrain), 1)
        ilk = list(MOD.UI._mini_terrain.values())[0]
        _frame(g)
        self.assertEqual(len(MOD.UI._mini_terrain), 1, "ayni harita iki kez cizildi")
        self.assertIs(list(MOD.UI._mini_terrain.values())[0], ilk)
        g.cur_key = "dark_forest"
        g.cur_map = g.maps["dark_forest"]
        _frame(g)
        self.assertEqual(len(MOD.UI._mini_terrain), 2, "yeni harita onbellege girmedi")


class TestSetting(unittest.TestCase):
    def test_minimap_is_on_by_default(self):
        self.assertTrue(MOD.Settings.DEFAULTS["minimap"])

    def test_setting_survives_save_and_load(self):
        eski = MOD.CFG.data.get("minimap", True)
        try:
            MOD.CFG.data["minimap"] = False
            self.assertFalse(MOD.CFG.minimap)
            MOD.CFG.data["minimap"] = True
            self.assertTrue(MOD.CFG.minimap)
        finally:
            MOD.CFG.data["minimap"] = eski

    def test_label_is_translated_in_every_language(self):
        eski = MOD.CFG.data.get("language", "TR")
        try:
            for code in MOD.LANG_CODES:
                MOD.CFG.data["language"] = code
                txt = MOD.T_("set_minimap")
                self.assertTrue(txt.strip(), "%s: bos" % code)
                self.assertNotEqual(txt, "set_minimap", "%s: cevrilmemis" % code)
        finally:
            MOD.CFG.data["language"] = eski


if __name__ == "__main__":
    unittest.main(verbosity=2)
