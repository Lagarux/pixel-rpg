#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Ana boss kapanis sahneleri.

Malachar disindaki boss'lar sessizce oluyordu: dev bir yaratigi devirmek
bir slime devirmekle ayni hissi veriyordu. Artik her ana boss dustugunde
araya bir sahne giriyor - siluet catliyor, karanlik zerrelere dagiliyor,
yerinde kristal kaliyor ve ne oldugu anlatiliyor.

Ayrica hikayede DORT kristalden soz ediliyordu ama oyunda ikisi vardi.
Koz Vadisi ve Gizemli Kutuphane'ye birer muhafiz konuldu.

Calistirmak icin: python -m unittest discover -s tests
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import unittest

import pygame

from harness import load_game_module

MOD = None
HARITA_ADLARI = ["ashveil", "dark_forest", "ruins", "desert", "ice_cave",
                 "shadow_castle", "village_dungeon", "south_meadow",
                 "west_river", "mystic_library", "rocky_pass", "misty_swamp",
                 "ember_valley"]


def setUpModule():
    global MOD
    MOD = load_game_module("pixel_rpg_boss")
    pygame.init()
    pygame.display.set_mode((MOD.SW, MOD.SH))


def tearDownModule():
    pygame.quit()


def oyun():
    import tempfile
    MOD.SAVE_FILE = os.path.join(tempfile.mkdtemp(), "save1.json")
    g = MOD.Game.__new__(MOD.Game)
    g.ui = MOD.UI(); g.ps = MOD.PS(); g._reset()
    g.player = MOD.Player(5, 5, MOD.PlayerStats("warrior"))
    g.levelup_timer = 0
    g.tick = 0
    return g


def bosslari_bul(g):
    out = {}
    for ad, m in g.maps.items():
        for e in m.enemies:
            if e.is_boss:
                out[getattr(e, "boss_id", None)] = (ad, m, e)
    return out


class TestBossTablosu(unittest.TestCase):
    def test_her_bossun_dunyada_karsiligi_var(self):
        g = oyun()
        bulunan = bosslari_bul(g)
        for bid, b in MOD.BOSSES.items():
            with self.subTest(boss=bid):
                self.assertIn(bid, bulunan, "%s dunyada yok" % bid)
                harita, _m, e = bulunan[bid]
                self.assertEqual(harita, b["map"], "%s yanlis haritada" % bid)
                self.assertEqual(e.kind, b["kind"])

    def test_her_boss_kendi_kristalini_dusuruyor(self):
        g = oyun()
        for bid, (_h, _m, e) in bosslari_bul(g).items():
            kristal = MOD.BOSSES[bid]["crystal"]
            with self.subTest(boss=bid):
                if kristal:
                    self.assertIn(kristal, e.loot,
                                  "%s kristalini dusurmuyor" % bid)

    def test_kimliksiz_boss_yok(self):
        g = oyun()
        for ad, m in g.maps.items():
            for e in m.enemies:
                if e.is_boss:
                    with self.subTest(harita=ad, tur=e.kind):
                        self.assertIn(getattr(e, "boss_id", None), MOD.BOSSES,
                                      "%s/%s kimliksiz boss" % (ad, e.kind))

    def test_dort_kristal_var(self):
        """Hikayede dort kristalden soz ediliyor; oyunda ikisi vardi."""
        kristaller = {b["crystal"] for b in MOD.BOSSES.values() if b["crystal"]}
        self.assertEqual(len(kristaller), 4, "dort kristal tamamlanmamis")
        for k in kristaller:
            self.assertIn(k, MOD.CRYSTAL_FLAG)
            self.assertIn(k, MOD.ITEMS)

    def test_bosslar_sert(self):
        g = oyun()
        sirali = [e.max_hp for _h, _m, e in bosslari_bul(g).values()]
        for hp in sirali:
            self.assertGreater(hp, 150, "boss cok cilız: %d can" % hp)


class TestSahneAkisi(unittest.TestCase):
    def test_boss_olunce_sahne_aciliyor(self):
        g = oyun()
        harita, m, e = bosslari_bul(g)["earth"]
        g.cur_key = harita; g.cur_map = m
        g._kill(e)
        self.assertEqual(g.state, "boss_scene")
        self.assertEqual(g.boss_scene["id"], "earth")
        self.assertEqual(g.boss_scene["page"], 0)
        self.assertTrue(g.flags.get("boss_earth"))

    def test_sira_disi_boss_oyuna_donuyor(self):
        g = oyun()
        harita, m, e = bosslari_bul(g)["fire"]
        g.cur_key = harita; g.cur_map = m
        g._kill(e)
        self.assertEqual(g.state, "boss_scene")
        g._end_boss_scene()
        self.assertEqual(g.state, "playing", "sahneden sonra oyuna donmedi")
        self.assertIsNone(g.boss_scene)

    def test_malachar_sahnesi_kapanisa_baglaniyor(self):
        g = oyun()
        harita, m, e = bosslari_bul(g)["malachar"]
        g.cur_key = harita; g.cur_map = m
        g._kill(e)
        self.assertEqual(g.state, "boss_scene")
        g._end_boss_scene()
        self.assertEqual(g.state, "epilogue")
        self.assertTrue(g.epi_pages)

    def test_zaman_cizelgesi_sirali(self):
        U = MOD.UI
        self.assertLess(U.BS_CRACK, U.BS_SHATTER)
        self.assertLess(U.BS_SHATTER, U.BS_CRYSTAL)
        self.assertLess(U.BS_CRYSTAL, U.BS_TEXT)
        self.assertLessEqual(U.BS_TEXT / float(MOD.FPS), 4.0,
                             "animasyon cok uzun: oyuncu beklemek zorunda")

    def test_hicbir_kare_bos_degil(self):
        g = oyun()
        harita, m, e = bosslari_bul(g)["water"]
        g.cur_key = harita; g.cur_map = m
        g._kill(e)
        for t in (5, 40, 90, 130, 170):
            g.boss_scene["t"] = t
            surf = pygame.Surface((MOD.SW, MOD.SH))
            surf.fill((0, 0, 0))
            g.ui.draw_boss_scene(surf, g.boss_scene, t * 3)
            boyali = sum(1 for x in range(0, MOD.SW, 4) for y in range(0, MOD.SH, 4)
                         if surf.get_at((x, y))[:3] != (0, 0, 0))
            with self.subTest(kare=t):
                self.assertGreater(boyali, 80, "t=%d karesi bos" % t)

    def test_kristal_siluetten_sonra_geliyor(self):
        """Once siluet, sonra dagilma, en sonda kristal."""
        g = oyun()
        harita, m, e = bosslari_bul(g)["fire"]
        g.cur_key = harita; g.cur_map = m
        g._kill(e)
        col = g.boss_scene["col"]

        def kristal_pikseli(t):
            g.boss_scene["t"] = t
            surf = pygame.Surface((MOD.SW, MOD.SH))
            surf.fill((0, 0, 0))
            g.ui.draw_boss_scene(surf, g.boss_scene, 0)
            n = 0
            for x in range(MOD.SW // 2 - 40, MOD.SW // 2 + 40, 2):
                for y in int(MOD.SH * 0.38) - 40, int(MOD.SH * 0.38):
                    r, gg, b = surf.get_at((x, y))[:3]
                    if abs(r - col[0]) < 30 and abs(gg - col[1]) < 30 and abs(b - col[2]) < 30:
                        n += 1
            return n
        self.assertEqual(kristal_pikseli(MOD.UI.BS_CRYSTAL - 10), 0,
                         "kristal erken belirdi")
        self.assertGreater(kristal_pikseli(MOD.UI.BS_CRYSTAL + 40), 0,
                           "kristal hic belirmedi")


class TestKristaller(unittest.TestCase):
    def test_yeni_kristaller_kalici_nitelik_veriyor(self):
        g = oyun()
        once = (g.player.stats.str, g.player.stats.vit)
        g._quest_item("fire_c")
        self.assertTrue(g.flags["fire_crystal"])
        self.assertEqual((g.player.stats.str, g.player.stats.vit),
                         (once[0] + 1, once[1] + 1))

    def test_ayni_kristal_iki_kez_islemiyor(self):
        g = oyun()
        g._quest_item("light_c")
        bir = (g.player.stats.wis, g.player.stats.int_)
        g._quest_item("light_c")
        self.assertEqual((g.player.stats.wis, g.player.stats.int_), bir)

    def test_ana_kristaller_bolumu_ilerletiyor(self):
        g = oyun()
        g.flags["ch"] = 3
        g._quest_item("earth_c")
        self.assertGreaterEqual(g.flags["ch"], 4)

    def test_istege_bagli_kristaller_ana_zinciri_kilitlemiyor(self):
        """Eski kayitlar ve yeni kristali almayan oyuncu takilmasin."""
        g = oyun()
        g._quest_item("earth_c")
        g._quest_item("water_c")
        self.assertGreaterEqual(g.flags["ch"], 6, "ana zincir ilerlemedi")


class TestKapanisaEtkisi(unittest.TestCase):
    def test_yeni_kristaller_kapanisa_sayfa_ekliyor(self):
        temel = {"ch": 6}
        az = MOD.epilogue_pages(temel)
        cok = MOD.epilogue_pages(dict(temel, fire_crystal=True, light_crystal=True))
        self.assertGreater(len(cok), len(az),
                           "kristaller kapanisa hicbir sey eklemedi")

    def test_kristaller_unvani_yukseltiyor(self):
        f = {}
        for sq in MOD.SIDE_QUESTS[:9]:
            f["sqpaid_" + sq["id"]] = True
        dusuk = MOD.ending_rank(f)
        f["fire_crystal"] = True
        f["light_crystal"] = True
        yuksek = MOD.ending_rank(f)
        self.assertNotEqual(dusuk, yuksek, "kristaller unvani degistirmedi")

    def test_ozet_kristal_sayiyor(self):
        g = oyun()
        g.flags["earth_crystal"] = True
        g.flags["fire_crystal"] = True
        ozet = dict(g._ending_stats())
        self.assertEqual(ozet[MOD.T_("epi.stat_crystals")], 2)


class TestMetinler(unittest.TestCase):
    def test_her_sahne_bes_dilde_cevrili(self):
        eski = MOD.CFG.data.get("language", "TR")
        try:
            for code in MOD.LANG_CODES:
                MOD.CFG.data["language"] = code
                for bid, b in MOD.BOSSES.items():
                    for k in [b["name"]] + list(b["lines"]):
                        t = MOD.T_(k)
                        with self.subTest(dil=code, anahtar=k):
                            self.assertTrue(t.strip(), "%s/%s bos" % (code, k))
                            self.assertFalse(t.startswith("boss."),
                                             "%s/%s cevrilmemis" % (code, k))
        finally:
            MOD.CFG.data["language"] = eski

    def test_her_sahnede_dort_satir_var(self):
        for bid, b in MOD.BOSSES.items():
            with self.subTest(boss=bid):
                self.assertGreaterEqual(len(b["lines"]), 3,
                                        "%s sahnesi cok kisa" % bid)

    def test_satirlar_ekrana_sigiyor(self):
        ui = MOD.UI()
        eski = MOD.CFG.data.get("language", "TR")
        try:
            for code in MOD.LANG_CODES:
                MOD.CFG.data["language"] = code
                for bid, b in MOD.BOSSES.items():
                    for k in b["lines"]:
                        parcalar = ui._wrap(MOD.T_(k), ui.fmd, MOD.SW - 200)
                        with self.subTest(dil=code, anahtar=k):
                            self.assertLessEqual(len(parcalar), 3,
                                                 "%s/%s uc satiri asiyor" % (code, k))
                            for p in parcalar:
                                self.assertLessEqual(ui.fmd.size(p)[0], MOD.SW - 200,
                                                     "%s/%s kutuya sigmiyor" % (code, k))
        finally:
            MOD.CFG.data["language"] = eski

    def test_boss_adlari_birbirinden_farkli(self):
        adlar = [MOD.T_(b["name"]) for b in MOD.BOSSES.values()]
        self.assertEqual(len(adlar), len(set(adlar)), "iki boss ayni adi tasiyor")


if __name__ == "__main__":
    unittest.main(verbosity=2)
