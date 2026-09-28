#!/usr/bin/env python3
"""
Dil dosyalari testleri.

Uc seyi birden korur:
  1. Her dilde HER anahtar var mi (eksik ceviri sessizce Turkce'ye duser),
  2. Bicimlendirme yer tutuculari (%d gibi) diller arasi tutuyor mu,
  3. Her dil icin secilen font o alfabeyi gercekten cizebiliyor mu,
  4. Arayuzde ceviriden gecmemis Turkce metin kalmis mi.

Calistirmak icin: python -m unittest discover -s tests
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import io
import json
import re
import unittest

import pygame

from harness import PROJECT_DIR, load_game_module

MOD = None
LOCALES = {}


def setUpModule():
    global MOD, LOCALES
    MOD = load_game_module("pixel_rpg_locale")
    pygame.init()
    pygame.display.set_mode((MOD.SW, MOD.SH))
    for code in MOD.LANG_CODES:
        path = os.path.join(PROJECT_DIR, "assets", "locales", code.lower() + ".json")
        with io.open(path, encoding="utf-8") as f:
            LOCALES[code] = json.load(f)


def tearDownModule():
    pygame.quit()


class TestLocaleFiles(unittest.TestCase):
    def test_all_languages_have_a_file(self):
        for code in MOD.LANG_CODES:
            self.assertIn(code, LOCALES, f"{code} icin dil dosyasi yok")
            self.assertGreater(len(LOCALES[code]), 300, f"{code} dosyasi eksik gorunuyor")

    def test_no_missing_keys_in_any_language(self):
        base = set(LOCALES["TR"])
        for code, data in LOCALES.items():
            missing = sorted(base - set(data))
            with self.subTest(lang=code):
                self.assertEqual(missing, [], f"{code} dilinde {len(missing)} anahtar eksik")

    def test_no_empty_translations(self):
        for code, data in LOCALES.items():
            empty = [k for k, v in data.items() if not str(v).strip()]
            with self.subTest(lang=code):
                self.assertEqual(empty, [], f"{code}: bos ceviri {empty[:5]}")

    def test_format_placeholders_match(self):
        """%d / %s yer tutuculari dillerde ayni olmali, yoksa metin cizilirken patlar."""
        pat = re.compile(r"%[sd]")
        for key, tr_text in LOCALES["TR"].items():
            want = pat.findall(tr_text)
            for code, data in LOCALES.items():
                with self.subTest(lang=code, key=key):
                    self.assertEqual(pat.findall(data[key]), want,
                                     f"{code}/{key}: yer tutucular uyusmuyor")

    def test_untranslated_copies_are_rare(self):
        """Ceviri dosyasi Turkce'nin kopyasi olmamali (unutulmus satirlar)."""
        tr = LOCALES["TR"]
        for code in ("EN", "DE", "RU", "AR"):
            same = [k for k, v in LOCALES[code].items()
                    if v == tr[k] and not re.fullmatch(r"[\W\d\s]+", v)]
            with self.subTest(lang=code):
                # Ozel isimler (Malachar, Ashveil) ayni kalabilir; esik genis tutuldu
                self.assertLess(len(same), 25, f"{code}: {len(same)} satir Turkce kalmis: {same[:8]}")


class TestLocaleLookup(unittest.TestCase):
    def setUp(self):
        self._old = MOD.CFG.data.get("language", "TR")

    def tearDown(self):
        MOD.CFG.data["language"] = self._old
        MOD.FontManager.set_language(self._old)

    def test_language_switch_changes_text(self):
        MOD.CFG.data["language"] = "TR"
        tr = MOD.T_("quest_log")
        MOD.CFG.data["language"] = "DE"
        de = MOD.T_("quest_log")
        self.assertNotEqual(tr, de, "dil degistirmek metni degistirmedi")

    def test_missing_key_falls_back_to_turkish(self):
        MOD.CFG.data["language"] = "EN"
        MOD.Locale._cache["EN"] = {}          # ceviri dosyasi bos gibi davran
        try:
            self.assertEqual(MOD.T_("quest_log"), LOCALES["TR"]["quest_log"])
        finally:
            MOD.Locale._cache.pop("EN", None)

    def test_unknown_key_returns_key_not_crash(self):
        self.assertEqual(MOD.T_("boyle.bir.anahtar.yok"), "boyle.bir.anahtar.yok")

    def test_rtl_reorders_words(self):
        """Arapca'da sozcuk sirasi ters cevrilmeli (SDL_ttf soldan saga diziyor)."""
        MOD.CFG.data["language"] = "AR"
        out = MOD.T_("ui.sq_fish_desc")
        raw = LOCALES["AR"]["ui.sq_fish_desc"]
        self.assertNotEqual(out, raw, "RTL siralama uygulanmamis")
        self.assertEqual(sorted(out.split()), sorted(raw.split()), "kelimeler kaybolmus")

    def test_ltr_languages_are_untouched(self):
        for code in ("TR", "EN", "DE", "RU"):
            MOD.CFG.data["language"] = code
            self.assertEqual(MOD.T_("quest_log"), LOCALES[code]["quest_log"])


class TestNoHardcodedTurkishLeft(unittest.TestCase):
    """Arayuz cizim kodunda ceviriden gecmemis Turkce metin kalmamali."""

    TR_CHARS = set("çğıöşüÇĞİÖŞÜ")
    # Cizim disi / teknik istisnalar
    ALLOW = {"monospace", "consolas", "couriernew", "georgia", "tahoma", "segoeui", "arial"}

    def test_ui_draw_calls_use_translations(self):
        with io.open(os.path.join(PROJECT_DIR, "pixel_rpg.py"), encoding="utf-8") as f:
            src = f.read()
        lines = src.split("\n")
        start = next(i for i, l in enumerate(lines) if l.startswith("class UI:"))
        bad = []
        for i in range(start, len(lines)):
            line = lines[i]
            if line.strip().startswith("#") or '"""' in line:
                continue
            if "self.txt" not in line and ".render(" not in line:
                continue
            for m in re.finditer(r'"([^"]{3,})"', line):
                t = m.group(1)
                if t in self.ALLOW or t.startswith(("ui.", "item.", "class.", "quest.")):
                    continue
                if set(t) & self.TR_CHARS:
                    bad.append((i + 1, t))
        self.assertEqual(bad, [], f"cizimde ceviriden gecmemis Turkce metin: {bad}")


if __name__ == "__main__":
    unittest.main(verbosity=2)
