#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Logo ve acilis animasyonu testleri.

Oyunun IKI logosu var:
  * oyun ici amblem  -> PA.logo(), acilis animasyonu ve baslik ekrani
  * uygulama ikonu   -> assets/icon.ico (tools/make_logo_icon.py uretir)

Ikisi ayni tasarimi paylasiyor; ikon kucuk boyda okunsun diye
sadelestirilmis cizimi kullaniyor.

Calistirmak icin: python -m unittest discover -s tests
"""
import os
import struct
import sys
import tempfile

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import unittest

import pygame

from harness import load_game_module

MOD = None
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def setUpModule():
    global MOD
    MOD = load_game_module("pixel_rpg_logo")
    MOD.SAVE_FILE = os.path.join(tempfile.mkdtemp(), "save1.json")
    pygame.init()
    pygame.display.set_mode((MOD.SW, MOD.SH))


def tearDownModule():
    pygame.quit()


def ink(surf):
    """Saydam olmayan piksel sayisi."""
    return pygame.mask.from_surface(surf).count()


class TestEmblem(unittest.TestCase):
    def test_logo_is_actually_drawn(self):
        lg = MOD.PA.logo(1.0)
        self.assertGreater(ink(lg), 500, "amblem neredeyse bos")
        self.assertEqual(lg.get_size(), (72, 52))

    def test_crack_grows_with_the_parameter(self):
        """Acilis animasyonu catlagi kademeli ciziyor."""
        def catlak_pikseli(c):
            lg = MOD.PA.logo(c)
            return sum(1 for x in range(lg.get_width()) for y in range(lg.get_height())
                       if lg.get_at((x, y))[:3] == (255, 244, 210))
        yok, yari, tam = catlak_pikseli(0.0), catlak_pikseli(0.5), catlak_pikseli(1.0)
        self.assertEqual(yok, 0, "catlaksiz surumde catlak var")
        self.assertGreater(yari, 0, "yarida catlak cizilmemis")
        self.assertGreater(tam, yari, "catlak ilerlemiyor")

    def test_logo_is_cached(self):
        a = MOD.PA.logo(1.0)
        b = MOD.PA.logo(1.0)
        self.assertIs(a, b, "amblem her cagrida yeniden ciziliyor")

    def test_simple_variant_has_fewer_details(self):
        """Kucuk boyda okunsun diye sade surumde ayrinti az olmali."""
        def renk_sayisi(surf):
            return len({surf.get_at((x, y))[:3]
                        for x in range(surf.get_width())
                        for y in range(surf.get_height())
                        if surf.get_at((x, y))[3] > 0})
        tam = renk_sayisi(MOD.PA.logo(0.0, sade=False))
        sade = renk_sayisi(MOD.PA.logo(0.0, sade=True))
        self.assertLess(sade, tam, "sade surum tam surumden ayrintili")

    def test_emblem_reads_at_icon_size(self):
        """16 piksele kuculdugunde hala bir sey gorunmeli."""
        kucuk = pygame.transform.smoothscale(MOD.PA.logo(0.0, sade=True), (16, 12))
        self.assertGreater(ink(kucuk), 40, "16 pikselde amblem kayboluyor")


class TestSplash(unittest.TestCase):
    def _game(self):
        g = MOD.Game.__new__(MOD.Game)
        g.ui = MOD.UI()
        g.ps = MOD.PS()
        g._reset()
        g.state = "splash"
        g.splash_t = 0
        return g

    def test_timeline_is_ordered(self):
        U = MOD.UI
        self.assertLess(U.SPLASH_IN, U.SPLASH_RISE)
        self.assertLess(U.SPLASH_RISE, U.SPLASH_TEXT)
        self.assertLess(U.SPLASH_TEXT, U.SPLASH_CRACK)
        self.assertLess(U.SPLASH_CRACK, U.SPLASH_END)

    def test_it_does_not_last_too_long(self):
        """Her acilista izlenecek; 4 saniyeyi gecmesin."""
        self.assertLessEqual(MOD.UI.SPLASH_END / float(MOD.FPS), 4.0,
                             "acilis animasyonu cok uzun")

    def test_it_ends_at_the_title(self):
        g = self._game()
        for _ in range(MOD.UI.SPLASH_END + 5):
            g._update()
        self.assertEqual(g.state, "title", "acilis baslik ekranina baglanmiyor")

    def test_frames_are_not_blank(self):
        g = self._game()
        for t in (5, 40, 80, 110, 160):
            surf = pygame.Surface((MOD.SW, MOD.SH))
            surf.fill((0, 0, 0))
            g.ui.draw_splash(surf, t, t * 3)
            boyali = sum(1 for x in range(0, MOD.SW, 4) for y in range(0, MOD.SH, 4)
                         if surf.get_at((x, y))[:3] != (0, 0, 0))
            self.assertGreater(boyali, 100, "t=%d karesi bos" % t)

    def test_the_crown_grows(self):
        """Tac yukselip buyumeli: erken karede gec kareden az yer kaplamali."""
        g = self._game()
        def dolu(t):
            surf = pygame.Surface((MOD.SW, MOD.SH), pygame.SRCALPHA)
            surf.fill((0, 0, 0, 255))
            g.ui.draw_splash(surf, t, 0)
            # ustteki yarida mor/altin pikselleri say
            n = 0
            for x in range(0, MOD.SW, 3):
                for y in range(0, MOD.SH // 2, 3):
                    r, gg, b = surf.get_at((x, y))[:3]
                    if b > 60 and b > gg:
                        n += 1
            return n
        self.assertGreater(dolu(60), dolu(25), "tac buyumuyor")


class TestAppIcon(unittest.TestCase):
    def test_icon_file_has_several_sizes(self):
        yol = os.path.join(ROOT, "assets", "icon.ico")
        self.assertTrue(os.path.isfile(yol), "assets/icon.ico yok")
        with open(yol, "rb") as f:
            veri = f.read()
        _, tip, n = struct.unpack("<HHH", veri[:6])
        self.assertEqual(tip, 1, "ICO dosyasi degil")
        self.assertGreaterEqual(n, 4, "ikon yeterince boyut tasimiyor: %d" % n)
        boylar = set()
        for i in range(n):
            w = veri[6 + 16 * i]
            boylar.add(w or 256)
        for gerekli in (16, 32, 256):
            self.assertIn(gerekli, boylar, "%dpx boyutu eksik" % gerekli)

    def test_window_icon_asset_exists(self):
        """Oyun acilista assets/icon64.png yukluyor."""
        yol = os.path.join(ROOT, "assets", "icon64.png")
        self.assertTrue(os.path.isfile(yol), "assets/icon64.png yok")
        im = pygame.image.load(yol)
        self.assertEqual(im.get_size(), (64, 64))
        self.assertGreater(ink(im.convert_alpha()), 400, "pencere ikonu bos")

    def test_previous_icon_is_kept(self):
        """Eski ikon ustune yazilmadi, yedegi duruyor."""
        self.assertTrue(os.path.isfile(os.path.join(ROOT, "assets", "icon_onceki.ico")),
                        "eski ikonun yedegi yok")


class TestTitleText(unittest.TestCase):
    def test_displayed_title_uses_turkish_letters(self):
        """TITLE sabiti ASCII (pencere basligi icin); ekranda gorulen baslik
        Turkce karakterleri tasimali."""
        eski = MOD.CFG.data.get("language", "TR")
        try:
            MOD.CFG.data["language"] = "TR"
            t = MOD.game_title()
            self.assertIn("ç", t.lower() + t, "ekran basliginda Turkce karakter yok: %r" % t)
            self.assertNotEqual(t, MOD.TITLE, "ekran basligi hala ASCII")
        finally:
            MOD.CFG.data["language"] = eski

    def test_title_is_translated_everywhere(self):
        eski = MOD.CFG.data.get("language", "TR")
        try:
            for code in MOD.LANG_CODES:
                MOD.CFG.data["language"] = code
                t = MOD.game_title()
                self.assertTrue(t.strip())
                self.assertNotEqual(t, "ui.game_title", "%s: cevrilmemis" % code)
        finally:
            MOD.CFG.data["language"] = eski


if __name__ == "__main__":
    unittest.main(verbosity=2)
