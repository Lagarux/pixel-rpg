#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Harman Senligi: uc mini oyun, jeton parasi ve kostumler.

Senlik oyunun tek dusmansiz alani. Jeton altinla alinmaz, altin da
jetonla alinmaz: iki ekonomi birbirine karismiyor.

Calistirmak icin: python -m unittest discover -s tests
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import unittest

import pygame

from harness import load_game_module

MOD = None


def setUpModule():
    global MOD
    MOD = load_game_module("pixel_rpg_festival")
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
    g.cur_key = "festival"; g.cur_map = g.maps["festival"]
    g.player.snap(*MOD._snap(g.cur_map, 22, 14))
    g.tick = 0
    g.dmg_nums = []
    return g


class TestSenlikAlani(unittest.TestCase):
    def test_harita_var_ve_dusmansiz(self):
        g = oyun()
        m = g.maps["festival"]
        self.assertEqual(m.enemies, [], "senlik alaninda dusman var")

    def test_cayirdan_gidilip_donuluyor(self):
        g = oyun()
        cayir = g.maps["south_meadow"]
        hedefler = {v[0] for v in cayir.transitions.values()}
        self.assertIn("festival", hedefler, "cayirdan senlige gecit yok")
        geri = {v[0] for v in g.maps["festival"].transitions.values()}
        self.assertIn("south_meadow", geri, "senlikten donus yok")

    def test_dort_tezgah_sahibi_duruyor(self):
        g = oyun()
        adlar = {n.name for n in g.maps["festival"].npcs}
        for npc in list(MOD.MG_BY_NPC) + ["npc.senlik_satici"]:
            self.assertIn(npc, adlar, "%s senlikte yok" % npc)

    def test_senlikte_can_yenilenmesi_calisiyor(self):
        """Guvenli alan: dinlenmek ise yaramali."""
        g = oyun()
        st = g.player.stats
        st.hp = 1
        g.combat_t = -10 ** 6
        for i in range(60 * 30):
            g.tick = i
            g._yenilenme()
        self.assertGreater(st.hp, 1)


class TestOyunTablosu(unittest.TestCase):
    def test_uc_oyun_var(self):
        self.assertEqual(len(MOD.MINIGAMES), 3)

    def test_her_oyunun_npc_si_var(self):
        for oid, (ad, npc, tur, jeton) in MOD.MINIGAMES.items():
            with self.subTest(oyun=oid):
                self.assertIn(npc, MOD.MG_BY_NPC)
                self.assertGreater(tur, 0)
                self.assertGreater(jeton, 0)

    def test_adlar_bes_dilde_cevrili(self):
        eski = MOD.CFG.data.get("language", "TR")
        try:
            for code in MOD.LANG_CODES:
                MOD.CFG.data["language"] = code
                for oid, (ad, _n, _t, _j) in MOD.MINIGAMES.items():
                    t = MOD.T_(ad)
                    with self.subTest(dil=code, oyun=oid):
                        self.assertTrue(t.strip() and not t.startswith("mg."))
        finally:
            MOD.CFG.data["language"] = eski


class TestNisanAtisi(unittest.TestCase):
    def test_yesil_alanda_vurmak_jeton_veriyor(self):
        g = oyun()
        g._mg_start("target")
        g.mg["x"] = float(g.mg["merkez"])      # tam ortada
        g._mg_target_hit()
        self.assertGreater(g.mg["jeton"], 0, "tam isabet jeton vermedi")

    def test_disarida_vurmak_jeton_vermiyor(self):
        g = oyun()
        g._mg_start("target")
        g.mg["x"] = float((g.mg["merkez"] + 300) % MOD.Game.MG_T_W)
        if abs(g.mg["x"] - g.mg["merkez"]) <= g.mg["bolge"]:
            g.mg["x"] = 0.0 if g.mg["merkez"] > 200 else float(MOD.Game.MG_T_W)
        g._mg_target_hit()
        self.assertEqual(g.mg["jeton"], 0, "iskalayinca da jeton verdi")

    def test_nisangah_seritte_gidip_geliyor(self):
        g = oyun()
        g._mg_start("target")
        gorulen = set()
        for i in range(600):
            g.tick = i
            g._mg_update()
            gorulen.add(int(g.mg["x"]) // 40)
        self.assertGreater(len(gorulen), 4, "nisangah kipirdamadi")
        self.assertLessEqual(max(gorulen) * 40, MOD.Game.MG_T_W)

    def test_halka_tur_tur_daraliyor(self):
        g = oyun()
        g._mg_start("target")
        ilk = g.mg["bolge"]
        g._mg_next()
        self.assertLess(g.mg["bolge"], ilk, "halka daralmiyor")


class TestCanSirasi(unittest.TestCase):
    def test_dogru_sira_jeton_veriyor(self):
        g = oyun()
        g._mg_start("bells")
        g.mg["durum"] = "oynuyor"
        for nota in list(g.mg["dizi"]):
            g._mg_bells_key(nota)
        self.assertGreater(g.mg["jeton"], 0, "dogru sira jeton vermedi")

    def test_yanlis_nota_turu_bitiriyor(self):
        g = oyun()
        g._mg_start("bells")
        g.mg["durum"] = "oynuyor"
        dizi = list(g.mg["dizi"])
        tur0 = g.mg["tur"]
        g._mg_bells_key((dizi[0] + 1) % 4)
        self.assertEqual(g.mg["jeton"], 0)
        self.assertGreater(g.mg["tur"], tur0, "yanlis notada tur ilerlemedi")

    def test_dizi_tur_tur_uzuyor(self):
        g = oyun()
        g._mg_start("bells")
        ilk = len(g.mg["dizi"])
        g._mg_next()
        self.assertGreater(len(g.mg["dizi"]), ilk, "dizi uzamiyor")

    def test_gosterim_oynamaya_gecer(self):
        g = oyun()
        g._mg_start("bells")
        self.assertEqual(g.mg["durum"], "gosteriyor")
        for i in range(34 * (len(g.mg["dizi"]) + 2)):
            g.tick = i
            g._mg_update()
        self.assertIn(g.mg["durum"], ("oynuyor", "gosteriyor"))


class TestOlta(unittest.TestCase):
    def test_kanca_tusla_yukari_cikiyor(self):
        g = oyun()
        g._mg_start("fish")
        basili = g.mg["kanca"]
        import harness
        eski = pygame.key.get_pressed
        pygame.key.get_pressed = lambda: harness._FakeKeys({pygame.K_SPACE})
        try:
            for i in range(60):
                g.tick = i
                g._mg_update()
        finally:
            pygame.key.get_pressed = eski
        self.assertLess(g.mg["kanca"], basili, "bosluk tusu kancayi kaldirmiyor")

    def test_hizalaninca_cubuk_doluyor(self):
        g = oyun()
        g._mg_start("fish")
        g.mg["balik"] = 50.0; g.mg["kanca"] = 50.0; g.mg["b_hiz"] = 0.0
        once = g.mg["dolu"]
        g.tick = 1
        g._mg_update()
        self.assertGreater(g.mg["dolu"], once, "hizaliyken cubuk dolmadi")

    def test_sure_dolunca_balik_kaciyor(self):
        g = oyun()
        g._mg_start("fish")
        tur0 = g.mg["tur"]
        g.mg["sure"] = 1
        g.tick = 1
        g._mg_update()
        self.assertGreater(g.mg["tur"], tur0, "sure bitince tur ilerlemedi")


class TestJetonEkonomisi(unittest.TestCase):
    def test_oyun_bitince_jeton_cantaya_giriyor(self):
        g = oyun()
        g._mg_start("target")
        g.mg["jeton"] = 5
        g.mg["tur"] = g.mg["max_tur"] - 1
        g._mg_next()
        self.assertEqual(g.mg["durum"], "bitti")
        self.assertEqual(g.player.inventory.count("festival_token"), 5)

    def test_senlik_tezgahi_jetonla_calisiyor(self):
        shop = MOD.SHOPS["npc.senlik_satici"]
        self.assertEqual(MOD.shop_currency(shop), "festival_token")
        self.assertEqual(MOD.UI.shop_tabs(shop), ["ui.shop_buy"],
                         "jeton tezgahinda satis sekmesi var")

    def test_altin_jeton_yerine_gecmiyor(self):
        g = oyun()
        g.player.stats.gold = 99999
        g.player.inventory = []
        rows = MOD.UI.shop_rows(g.player, MOD.SHOPS["npc.senlik_satici"], 0)
        self.assertTrue(rows)
        self.assertFalse(any(ok for _k, _f, ok in rows),
                         "altinla senlik mali alinabiliyor")

    def test_jetonla_alinca_jeton_dusuyor(self):
        g = oyun()
        g.player.inventory = ["festival_token"] * 40
        g.shop_npc = "npc.senlik_satici"; g.shop_tab = 0; g.shop_msg = None
        rows = MOD.UI.shop_rows(g.player, MOD.SHOPS[g.shop_npc], 0)
        i = next(i for i, (k, _f, _o) in enumerate(rows) if k == "fair_blade")
        g.shop_sel = i
        g._shop_confirm()
        self.assertIn("fair_blade", g.player.inventory, "esya alinmadi")
        self.assertEqual(g.player.inventory.count("festival_token"),
                         40 - MOD.token_price("fair_blade"), "jeton dusmedi")

    def test_senlik_esyasi_altin_tablosunda_degil(self):
        """Jetonla alinan sey altinla da alinabilseydi senligin anlami kalmazdi."""
        for k in MOD.SHOPS["npc.senlik_satici"]["stock"]:
            if k in ("honey_cake", "elixir"):
                continue          # bunlar her yerde satiliyor
            with self.subTest(esya=k):
                self.assertNotIn(k, MOD.ITEM_PRICES,
                                 "%s hem altinla hem jetonla alinabiliyor" % k)


class TestKostumler(unittest.TestCase):
    def test_alti_kostum_var(self):
        self.assertGreaterEqual(len(MOD.COSTUMES), 6)

    def test_adlar_bes_dilde_cevrili(self):
        eski = MOD.CFG.data.get("language", "TR")
        try:
            for code in MOD.LANG_CODES:
                MOD.CFG.data["language"] = code
                for k in MOD.COSTUMES:
                    ad = MOD.costume_name(k)
                    with self.subTest(dil=code, kostum=k):
                        self.assertTrue(ad.strip() and not ad.startswith("costume."))
        finally:
            MOD.CFG.data["language"] = eski

    def test_satin_alinca_gardiroba_giriyor(self):
        g = oyun()
        g.player.inventory = ["festival_token"] * 40
        g.shop_npc = "npc.senlik_satici"; g.shop_tab = 0; g.shop_msg = None
        rows = MOD.UI.shop_rows(g.player, MOD.SHOPS[g.shop_npc], 0)
        i = next(i for i, (k, _f, _o) in enumerate(rows) if k == "costume_harvest")
        g.shop_sel = i
        g._shop_confirm()
        self.assertIn("harvest", g.player.stats.costumes)
        self.assertEqual(g.player.stats.costume, "harvest", "alinan kostum giyilmedi")
        self.assertNotIn("costume_harvest", g.player.inventory,
                         "kostum cantada yer kapliyor")

    def test_ayni_kostum_iki_kez_satilmiyor(self):
        g = oyun()
        g.player.inventory = ["festival_token"] * 60
        g.player.stats.costumes = ["harvest"]
        rows = MOD.UI.shop_rows(g.player, MOD.SHOPS["npc.senlik_satici"], 0)
        ok = next(o for k, _f, o in rows if k == "costume_harvest")
        self.assertFalse(ok, "sahip olunan kostum tekrar satiliyor")

    def test_cizim_kostumle_degisiyor(self):
        a = MOD.PA.player_surf("down", 0, "warrior", None)
        b = MOD.PA.player_surf("down", 0, "warrior", "royal")
        self.assertNotEqual(pygame.image.tostring(a, "RGBA"),
                            pygame.image.tostring(b, "RGBA"),
                            "kostum cizimi degistirmiyor")

    def test_her_kostum_birbirinden_farkli(self):
        goruntu = {}
        for k in MOD.COSTUMES:
            goruntu[k] = pygame.image.tostring(
                MOD.PA.player_surf("down", 0, "warrior", k), "RGBA")
        self.assertEqual(len(set(goruntu.values())), len(goruntu),
                         "iki kostum ayni gorunuyor")

    def test_kostum_kayitta_duruyor(self):
        g = oyun()
        g.player.stats.costumes = ["harvest", "royal"]
        g.player.stats.costume = "royal"
        self.assertTrue(g.save_game())
        g2 = MOD.Game.__new__(MOD.Game)
        g2.ui = MOD.UI(); g2.ps = MOD.PS(); g2._reset()
        self.assertTrue(g2.load_game())
        self.assertEqual(g2.player.stats.costume, "royal")
        self.assertIn("harvest", g2.player.stats.costumes)

    def test_sahip_olunmayan_kostum_yuklenmiyor(self):
        g = oyun()
        g.player.stats.costumes = []
        g.player.stats.costume = "royal"       # bozuk kayit
        self.assertTrue(g.save_game())
        g2 = MOD.Game.__new__(MOD.Game)
        g2.ui = MOD.UI(); g2.ps = MOD.PS(); g2._reset()
        self.assertTrue(g2.load_game())
        self.assertIsNone(g2.player.stats.costume)


class TestCizimVeTuslar(unittest.TestCase):
    def test_her_oyun_ciziliyor(self):
        for oid in MOD.MINIGAMES:
            g = oyun()
            g._mg_start(oid)
            for i in range(90):
                g.tick = i
                g._mg_update()
            yuzey = pygame.Surface((MOD.SW, MOD.SH))
            yuzey.fill((0, 0, 0))
            g.ui.draw_minigame(yuzey, g.mg, 60)
            boyali = sum(1 for x in range(0, MOD.SW, 4) for y in range(0, MOD.SH, 4)
                         if yuzey.get_at((x, y))[:3] != (0, 0, 0))
            with self.subTest(oyun=oid):
                self.assertGreater(boyali, 200, "%s ekrani bos" % oid)

    def test_bitis_ekrani_ciziliyor(self):
        g = oyun()
        g._mg_start("fish")
        g.mg["durum"] = "bitti"; g.mg["jeton"] = 4
        yuzey = pygame.Surface((MOD.SW, MOD.SH))
        yuzey.fill((0, 0, 0))
        g.ui.draw_minigame(yuzey, g.mg, 60)
        boyali = sum(1 for x in range(0, MOD.SW, 4) for y in range(0, MOD.SH, 4)
                     if yuzey.get_at((x, y))[:3] != (0, 0, 0))
        self.assertGreater(boyali, 200)

    def test_esc_oyundan_cikariyor(self):
        g = oyun()
        g._mg_start("target")
        g.state = "minigame"
        g._mg_key(pygame.K_ESCAPE)
        self.assertEqual(g.state, "playing")
        self.assertIsNone(g.mg)

    def test_uzun_kosum_patlamiyor(self):
        for oid in MOD.MINIGAMES:
            g = oyun()
            g._mg_start(oid)
            with self.subTest(oyun=oid):
                for i in range(4000):
                    g.tick = i
                    g._mg_update()
                    if g.mg["durum"] == "bitti":
                        break


if __name__ == "__main__":
    unittest.main(verbosity=2)
