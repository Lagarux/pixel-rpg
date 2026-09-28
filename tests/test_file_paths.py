#!/usr/bin/env python3
"""
Kaynak ve kayit yollari dogru cozumleniyor mu?

Iki ayri kural var:
  * SALT-OKUNUR varliklar (fontlar) betigin kendi dizinine gore bulunur --
    calisilan dizine (cwd) gore degil. PyInstaller paketinde de gecerlidir.
  * YAZILABILIR veri (settings.json) kullanici veri dizinine (%APPDATA% vb.)
    yazilir. Exe'nin yanina yazmak, Program Files kurulumunda izin hatasi;
    onefile paketinde ise oyun kapaninca silinen gecici dizin demektir.

Calistirmak icin: python -m unittest discover -s tests
"""
import importlib.util
import os
import sys
import tempfile
import unittest

PROJECT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SCRIPT_PATH = os.path.join(PROJECT_DIR, "pixel_rpg.py")


def _load_pixel_rpg_from(cwd: str):
    """pixel_rpg.py'yi verilen calisma dizinindeyken bagimsiz olarak yukler."""
    old_cwd = os.getcwd()
    os.chdir(cwd)
    try:
        spec = importlib.util.spec_from_file_location("pixel_rpg_under_test", SCRIPT_PATH)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        return module
    finally:
        os.chdir(old_cwd)


class TestCurrentFileDirectory(unittest.TestCase):
    """SETTINGS_FILE ve FontManager.FONT_DIR yollarinin dogru cozumlendigini test eder."""

    @classmethod
    def setUpClass(cls):
        cls.module = _load_pixel_rpg_from(PROJECT_DIR)

    def test_settings_file_is_in_user_data_dir(self):
        """Ayarlar kullanici veri dizinine yazilmali, exe'nin yanina degil."""
        settings = self.module.SETTINGS_FILE
        self.assertEqual(os.path.basename(settings), "settings.json")
        self.assertEqual(
            os.path.normcase(os.path.dirname(settings)),
            os.path.normcase(self.module.USER_DIR),
        )
        self.assertNotEqual(
            os.path.normcase(os.path.dirname(settings)),
            os.path.normcase(PROJECT_DIR),
            "settings.json hala betigin yaninda -- paketlenince kaybolur",
        )
        if sys.platform == "win32" and os.environ.get("APPDATA"):
            self.assertTrue(
                os.path.normcase(settings).startswith(os.path.normcase(os.environ["APPDATA"])),
                f"{settings} %APPDATA% altinda degil",
            )

    def test_user_data_dir_is_writable(self):
        probe = os.path.join(self.module.USER_DIR, ".write_probe")
        try:
            with open(probe, "w") as f:
                f.write("ok")
        finally:
            if os.path.exists(probe):
                os.remove(probe)

    def test_legacy_settings_path_still_readable(self):
        """Eski surumden kalan ayar dosyasi icin geriye donuk okuma yolu durmali."""
        self.assertEqual(
            os.path.normcase(os.path.dirname(self.module.LEGACY_SETTINGS_FILE)),
            os.path.normcase(PROJECT_DIR),
        )

    def test_font_dir_points_to_assets_fonts(self):
        expected = os.path.join(PROJECT_DIR, "assets", "fonts")
        self.assertEqual(
            os.path.normcase(self.module.FontManager.FONT_DIR),
            os.path.normcase(expected),
        )

    def test_font_dir_actually_exists(self):
        self.assertTrue(
            os.path.isdir(self.module.FontManager.FONT_DIR),
            f"{self.module.FontManager.FONT_DIR} bulunamadi",
        )

    def test_every_font_style_has_a_real_file(self):
        """FontManager'in aradigi her stil icin assets/fonts altinda gercek bir dosya olmali."""
        fm = self.module.FontManager
        for names in fm.PREFERRED:
            found = [n for n in names if os.path.isfile(os.path.join(fm.FONT_DIR, n))]
            with self.subTest(names=names):
                self.assertTrue(
                    found,
                    f"{names} icin dosya yok -- sistem fontuna dusulur, ortacag gorunumu kaybolur",
                )

    def test_chosen_fonts_actually_render_turkish(self):
        """Secilen font Turkce harfleri cizmeli.

        Almendra 'g' ve 's' glifi icermez; bunlari sessizce yutar
        ("Dogudaki ... basla." -> "Do udaki ... ba la.").
        """
        import pygame
        pygame.font.init()
        fm = self.module.FontManager
        for style in ("title", "dialog", "deco"):
            with self.subTest(style=style):
                font = fm.get(style, 20)
                for ch in fm.TR_PROBE:
                    surf = font.render(ch, True, (255, 255, 255))
                    self.assertGreater(
                        pygame.mask.from_surface(surf).count(), 0,
                        f"'{style}' fontu '{ch}' harfini bos ciziyor",
                    )

    def test_paths_are_absolute(self):
        self.assertTrue(os.path.isabs(self.module.SETTINGS_FILE))
        self.assertTrue(os.path.isabs(self.module.FontManager.FONT_DIR))

    def test_paths_independent_of_working_directory(self):
        """Betik farkli bir dizinden calistirilsa/yuklense bile yollar degismemeli."""
        with tempfile.TemporaryDirectory() as tmp_dir:
            other_module = _load_pixel_rpg_from(tmp_dir)

        self.assertEqual(other_module.SETTINGS_FILE, self.module.SETTINGS_FILE)
        self.assertEqual(other_module.FontManager.FONT_DIR, self.module.FontManager.FONT_DIR)


if __name__ == "__main__":
    unittest.main()
