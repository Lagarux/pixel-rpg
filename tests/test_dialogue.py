#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""NPC diyalog testleri.

Diyaloglar yer tutucu gibiydi: "Dikkatli ol.", "Kuzeye git!", bir NPC tek
cumle soyluyordu. Kullanici daha uzun ve mantikli konusmalar istedi.
Bu testler ucunu birden olcuyor: her NPC yeterince konusuyor mu, her satir
BES dilde cevrili mi, ve oyun ilerleyince ayni seyleri mi tekrarliyor.

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
G = None

# Oyunun uc hali: basi, ortasi, sonu
# Oyunun gidisatini temsil eden bayrak durumlari. Her NPC dalinin en az
# bir senaryoda gorunmesi gerekiyor; TestKapsam bunu zorunlu kiliyor.
SENARYO = [
    {"ch": 1},
    {"ch": 4, "earth_crystal": True, "speak_aldric": True, "kill_wolf": 5, "kill_boar": 5},
    {"ch": 5, "earth_crystal": True, "water_crystal": True, "speak_aldric": True},
    {"ch": 6, "water_crystal": True, "earth_crystal": True, "malachar_defeated": True,
     "sq_fish_done": True, "sq_scroll1": True, "sq_scroll2": True, "sq_scroll3": True,
     "kill_wolf": 9, "kill_boar": 9},
    # Yeni sistemler: malzeme toplandi, yukseltme yapildi
    {"ch": 3, "materials_found": 8},
    {"ch": 4, "materials_found": 30, "max_upgrade": 3},
    # Parsomenler tamam: once tesekkur, sonra Sayfa Muhafizi uyarisi
    {"ch": 4, "sq_scroll1": True, "sq_scroll2": True, "sq_scroll3": True},
    {"ch": 4, "sq_scroll1": True, "sq_scroll2": True, "sq_scroll3": True,
     "libr_told": True},
    # Istege bagli kristaller alindi
    {"ch": 5, "light_crystal": True, "boss_light": True},
    {"ch": 5, "fire_crystal": True, "boss_fire": True},
    # Balikci gorevi: baslatildi ama baliklar eksik / tamamlandi
    {"ch": 3, "sq_fish_started": True},
    {"ch": 3, "sq_fish_started": True, "sq_fish_silver": True,
     "sq_fish_gold": True, "sq_fish_shadow": True},
]

EN_AZ_SATIR = 5


def setUpModule():
    global MOD, TMP, G
    MOD = load_game_module("pixel_rpg_dialogue")
    TMP = tempfile.mkdtemp(prefix="pixelrpg_dlg_")
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


def npcs():
    for key, m in G.maps.items():
        for n in m.npcs:
            yield key, n


def anahtar(giris):
    """Satir ("dlg.x", 3) gibi bicimli de olabiliyor."""
    return giris[0] if isinstance(giris, tuple) else giris


class TestLength(unittest.TestCase):
    def test_every_npc_says_enough(self):
        kisa = []
        for key, n in npcs():
            for bayrak in SENARYO:
                satir = n.get_dialog(dict(bayrak))
                if len(satir) < EN_AZ_SATIR:
                    kisa.append((key, n.name, len(satir)))
        self.assertEqual(kisa, [], "cok kisa konusan NPC'ler: %s" % kisa)

    def test_lines_are_sentences_not_fragments(self):
        """'Dikkat et!' gibi iki kelimelik yer tutucular geri gelmesin."""
        kirik = []
        for key, n in npcs():
            for e in n.get_dialog({"ch": 1}):
                metin = MOD.dlg_line(e)
                if metin.startswith("["):
                    continue            # [ Görev Güncellendi! ] gibi işaretler
                if len(metin) < 20:
                    kirik.append((n.name, metin))
        self.assertEqual(kirik, [], "fazla kisa satirlar: %s" % kirik)

    def test_average_is_a_real_conversation(self):
        toplam = adet = 0
        for key, n in npcs():
            for bayrak in SENARYO:
                toplam += len(n.get_dialog(dict(bayrak)))
                adet += 1
        ort = toplam / adet
        self.assertGreater(ort, 5.0, "ortalama konusma uzunlugu dusuk: %.1f satir" % ort)


class TestTranslation(unittest.TestCase):
    def test_every_line_is_translated_in_every_language(self):
        eski = MOD.CFG.data.get("language", "TR")
        try:
            for code in MOD.LANG_CODES:
                MOD.CFG.data["language"] = code
                eksik = []
                for key, n in npcs():
                    for bayrak in SENARYO:
                        for e in n.get_dialog(dict(bayrak)):
                            k = anahtar(e)
                            metin = MOD.dlg_line(e)
                            if metin == k or not metin.strip():
                                eksik.append(k)
                self.assertEqual(eksik, [], "%s dilinde cevrilmemis: %s"
                                            % (code, sorted(set(eksik))[:8]))
        finally:
            MOD.CFG.data["language"] = eski

    def test_placeholders_survive_translation(self):
        """Icinde %d olan satir her dilde %d tasimali, yoksa bicimleme patlar."""
        eski = MOD.CFG.data.get("language", "TR")
        try:
            tr_ile = set()
            MOD.CFG.data["language"] = "TR"
            for key, n in npcs():
                for bayrak in SENARYO:
                    for e in n.get_dialog(dict(bayrak)):
                        if "%d" in MOD.dlg_line(e):
                            tr_ile.add(anahtar(e))
            for code in MOD.LANG_CODES:
                MOD.CFG.data["language"] = code
                for k in tr_ile:
                    self.assertIn("%d", MOD.T_(k), "%s/%s: %%d kaybolmus" % (code, k))
        finally:
            MOD.CFG.data["language"] = eski


class TestFitsOnScreen(unittest.TestCase):
    """Uzun cumleler yazdim; kutudan tasarlarsa kimse okuyamaz."""

    def test_no_line_overflows_the_dialogue_box(self):
        # draw_dialog: kutu bx=8, genislik SW-16, yazi bx+14'ten basliyor
        ic = (MOD.SW - 16) - 28
        eski = MOD.CFG.data.get("language", "TR")
        try:
            for code in MOD.LANG_CODES:
                MOD.CFG.data["language"] = code
                MOD.FontManager.set_language(code)
                ui = MOD.UI()
                tasan = []
                for key, n in npcs():
                    for bayrak in SENARYO:
                        for e in n.get_dialog(dict(bayrak)):
                            metin = MOD.dlg_line(e)
                            if ui.fdlg.size(metin)[0] > ic:
                                tasan.append((code, n.name, metin[:40]))
                self.assertEqual(tasan, [], "kutudan tasan satirlar: %s" % tasan[:4])
        finally:
            MOD.CFG.data["language"] = eski
            MOD.FontManager.set_language(eski)

    def test_pages_hold_four_lines(self):
        """Kutu sayfa basina 4 satir gosteriyor; sayfalama dogru olmali."""
        for key, n in npcs():
            satir = n.get_dialog({"ch": 1})
            sayfa = (len(satir) + 3) // 4
            self.assertGreaterEqual(sayfa, 1)
            self.assertLessEqual(sayfa, 4, "%s icin %d sayfa cok uzun" % (n.name, sayfa))


class TestKapsam(unittest.TestCase):
    """Her cevrilmis replik en az bir senaryoda gorunmeli.

    Yeni NPC dallari (demircinin yukseltme anlatimi, kutuphanecinin
    Sayfa Muhafizi uyarisi, Koz Bekcisi'nin Koz Devi sozleri) hicbir
    senaryoda calismiyordu: 36 replik yazildigi halde tek bir test
    onlara dokunmuyordu. Bu test bos replik birakilmasini engelliyor.
    """

    def _ulasilan(self):
        out = set()
        for f in SENARYO:
            for _k, n in npcs():
                for satir in n.get_dialog(f):
                    out.add(anahtar(satir))
        return out

    def test_hicbir_replik_olu_degil(self):
        import json
        import io as _io
        yol = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))),
                           "assets", "locales", "tr.json")
        tum = {k for k in json.load(_io.open(yol, encoding="utf-8"))
               if k.startswith("dlg.")}
        eksik = sorted(tum - self._ulasilan())
        self.assertEqual(eksik, [],
                         "hicbir senaryoda gorunmeyen %d replik: %s"
                         % (len(eksik), eksik[:8]))

    def test_yeni_sistemler_konusuluyor(self):
        """Demirci yukseltmeyi, kutuphaneci muhafizi anlatmali."""
        ulasilan = self._ulasilan()
        for k in ("dlg.smith.11", "dlg.libr.22", "dlg.koz.15"):
            self.assertIn(k, ulasilan, "%s hicbir durumda soylenmiyor" % k)


class TestProgression(unittest.TestCase):
    def test_some_npcs_react_to_progress(self):
        """Hepsi degil ama onemli bir kismi oyunun gidisatina tepki vermeli."""
        # Eskiden yalnizca ILK ve SON senaryo karsilastiriliyordu; senaryo
        # listesine araya yeni durum eklenince (son senaryo artik "oyunun
        # sonu" degil) test anlamsiz yere dusuyordu. Artik herhangi iki
        # durum arasinda farklilik ariyoruz - asil sorulan bu.
        degisen = 0
        for key, n in npcs():
            soylenenler = {tuple(anahtar(x) for x in n.get_dialog(dict(f)))
                           for f in SENARYO}
            if len(soylenenler) > 1:
                degisen += 1
        toplam = sum(1 for _ in npcs())
        self.assertGreaterEqual(degisen, toplam // 2,
                                "%d/%d NPC oyun boyunca ayni seyi soyluyor" %
                                (toplam - degisen, toplam))

    def test_vendors_react_to_what_the_player_did(self):
        """Pazar saticilarinin lafi oyuncunun isine gore degismeli."""
        pazar = {"npc.avci_doruk": {"kill_wolf": 5}, "npc.ciftci_hale": {"kill_boar": 5}}
        for key, n in npcs():
            if n.name not in pazar:
                continue
            once = n.get_dialog({"ch": 1})
            sonra = n.get_dialog(dict({"ch": 1}, **pazar[n.name]))
            self.assertNotEqual(once, sonra, "%s yaptigin isi fark etmiyor" % n.name)

    def test_no_npc_repeats_the_same_line_twice(self):
        for key, n in npcs():
            for bayrak in SENARYO:
                satir = [anahtar(e) for e in n.get_dialog(dict(bayrak))]
                self.assertEqual(len(satir), len(set(satir)),
                                 "%s ayni satiri tekrarliyor: %s" % (n.name, satir))


if __name__ == "__main__":
    unittest.main(verbosity=2)
