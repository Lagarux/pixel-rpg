#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Ses uretimi testleri.

Neden var: oyun aylarca sessiz calisti. Sentez numpy'a dayaniyordu, numpy
kurulu degildi ve uretici `except Exception: return None` ile hatayi yutuyordu.
Ses bankasi bos kaliyor, kimse fark etmiyordu. Bu testler sesin GERCEKTEN
uretildigini ve dolu oldugunu dogruluyor -- "cagri patlamadi" yetmiyor.

Calistirmak icin: python -m unittest discover -s tests
"""
import array
import io
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import unittest

import pygame

from harness import load_game_module

MOD = None
SM = None

# init() icinde uretilmesi beklenen efektlerin tamami
EXPECTED = ("hit", "hit_heavy", "heal", "level_up", "chest", "walk", "spell",
            "arrow", "menu_sel", "menu_back", "boss_alert", "victory", "death",
            "equip", "error", "open_ui", "trap", "freeze")


def setUpModule():
    global MOD, SM
    MOD = load_game_module("pixel_rpg_sound")
    pygame.init()
    pygame.display.set_mode((MOD.SW, MOD.SH))
    SM = MOD.SoundManager
    SM.init()


def tearDownModule():
    pygame.quit()


def samples(snd):
    """Sound'un ham PCM'ini signed 16-bit ornek dizisi olarak verir."""
    a = array.array("h")
    a.frombytes(snd.get_raw())
    return a


class TestEffectBank(unittest.TestCase):
    def test_every_effect_is_generated(self):
        missing = [k for k in EXPECTED if k not in SM._sounds]
        self.assertEqual(missing, [], "uretilemeyen efektler: %s (neden: %s)"
                                      % (missing, SM._fail))

    def test_sound_stays_enabled(self):
        self.assertTrue(SM._enabled, "ses kapandi, neden: %s" % SM._fail)
        self.assertEqual(SM._fail, "", "uretim sirasinda hata: %s" % SM._fail)

    def test_effects_are_not_silent(self):
        """Asil tuzak buydu: Sound nesnesi vardi ama ici bostu."""
        for k in EXPECTED:
            a = samples(SM._sounds[k])
            self.assertGreater(len(a), 0, "%s: bos tampon" % k)
            peak = max(max(a), -min(a))
            self.assertGreater(peak, 1000, "%s: duyulamayacak kadar sessiz (tepe=%d)" % (k, peak))

    def test_buffer_matches_mixer_format(self):
        """Ornek sayisi, mixer'in acildigi hiz ve kanal sayisiyla tutarli olmali;
        yoksa ses ya hizli ya kalin calar."""
        sr, _, chans = pygame.mixer.get_init()
        self.assertEqual(SM._format, (sr, max(1, chans)),
                         "sentez, mixer'in gercek bicimini izlemiyor")
        a = samples(SM._sounds["hit"])           # _make(220, 0.12, ...)
        self.assertEqual(len(a), int(sr * 0.12) * max(1, chans),
                         "hit sesinin uzunlugu istenen sureye uymuyor")

    def test_envelope_starts_and_ends_quiet(self):
        """Zarf ters cevrilirse ses patlayarak baslar ve aniden kesilir."""
        a = samples(SM._sounds["hit"])           # attack=0.005, decay=0.11
        self.assertEqual(a[0], 0, "ses sifirdan baslamiyor (zarf ters olabilir)")
        self.assertEqual(max(abs(v) for v in a[-40:]), 0, "ses sonunda susmuyor")
        self.assertGreater(max(max(a), -min(a)), 1000, "ortada ses yok")

    def test_pcm_clamps_instead_of_wrapping(self):
        """Tasan ornek isaret degistirirse ses citirtiya doner."""
        snd = SM._pcm([2.0, -2.0, 0.0])
        a = samples(snd)
        chans = SM._format[1]
        self.assertEqual(a[0], 32767, "pozitif tasma kirpilmadi")
        self.assertEqual(a[chans], -32767, "negatif tasma kirpilmadi")

    def test_play_tolerates_unknown_name(self):
        SM.play("bilinmeyen_ses")   # patlamamali


class TestMusic(unittest.TestCase):
    def setUp(self):
        SM.stop_music()
        SM._music_cache.clear()
        SM._music_theme = None

    def test_music_is_generated_and_audible(self):
        SM.play_music("village")
        snd = SM._music_cache.get("village")
        self.assertIsNotNone(snd, "muzik uretilemedi")
        a = samples(snd)
        self.assertGreater(max(max(a), -min(a)), 500, "muzik sessiz")
        self.assertGreater(snd.get_length(), 1.0, "muzik loop'u fazla kisa")

    def test_theme_is_cached_not_resynthesized(self):
        SM.play_music("village")
        first = SM._music_cache["village"]
        SM.play_music("forest")
        SM.play_music("village")
        self.assertIs(SM._music_cache["village"], first,
                      "ayni tema yeniden sentezlendi -- harita gecisi takilir")

    def test_same_theme_twice_does_not_restart(self):
        SM.play_music("village")
        ch = SM._music_channel
        SM.play_music("village")
        self.assertIs(SM._music_channel, ch, "ayni tema muzigi bastan baslatti")

    def test_unknown_theme_falls_back_to_village(self):
        SM.play_music("olmayan_tema")
        self.assertIn("village", SM._music_cache,
                      "tanimsiz tema icin yedek tema calmadi")

    def test_every_map_theme_can_be_generated(self):
        """MAP_MUSIC'teki her tema gercekten uretilebilmeli."""
        themes = set(MOD.Game.MAP_MUSIC.values())
        for t in sorted(themes):
            SM.play_music(t)
            self.assertIsNotNone(SM._music_cache.get(t), "tema uretilemedi: %s" % t)


if __name__ == "__main__":
    unittest.main(verbosity=2)
