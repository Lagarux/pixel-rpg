#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Durum etkileri, hizli erisim yuvalari ve gorev kutusu anahtari.

Oyunda yalnizca iki gecici etki vardi (savas cigligi, kutsal kalkan) ve
dusmanlarin hicbir kalici etkisi yoktu: vuruyorlar, geciyordu. Iksir
icmek icin de envanteri acmak gerekiyordu - dovusun ortasinda hem yavas
hem de ekrani kapatiyordu.

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
    MOD = load_game_module("pixel_rpg_effects")
    pygame.init()
    pygame.display.set_mode((MOD.SW, MOD.SH))


def tearDownModule():
    pygame.quit()


def oyun(cls="warrior"):
    import tempfile
    MOD.SAVE_FILE = os.path.join(tempfile.mkdtemp(), "save1.json")
    g = MOD.Game.__new__(MOD.Game)
    g.ui = MOD.UI(); g.ps = MOD.PS(); g._reset()
    g.player = MOD.Player(5, 5, MOD.PlayerStats(cls))
    g.player.snap(*MOD._snap(g.cur_map, 30, 24))
    g.levelup_timer = 0
    g.tick = 0
    g.dmg_nums = []
    return g


class TestEtkiTablosu(unittest.TestCase):
    ISTENEN = ("poison", "burn", "freeze", "root", "curse",
               "regen", "resist", "immune")

    def test_istenen_etkiler_var(self):
        for eid in self.ISTENEN:
            self.assertIn(eid, MOD.EFFECTS, "%s etkisi yok" % eid)

    def test_tablo_eksiksiz(self):
        for eid, t in MOD.EFFECTS.items():
            with self.subTest(etki=eid):
                self.assertIn("name", t)
                self.assertIn("col", t)
                self.assertIn("good", t)
                self.assertEqual(len(t["col"]), 3)

    def test_iyi_kotu_ayrimi_dogru(self):
        for eid in ("poison", "burn", "freeze", "root", "curse"):
            self.assertFalse(MOD.EFFECTS[eid]["good"], "%s iyi sayiliyor" % eid)
            self.assertIn(eid, MOD.KOTU_ETKILER)
        for eid in ("regen", "resist", "immune"):
            self.assertTrue(MOD.EFFECTS[eid]["good"], "%s kotu sayiliyor" % eid)
            self.assertNotIn(eid, MOD.KOTU_ETKILER)

    def test_adlar_bes_dilde_cevrili(self):
        eski = MOD.CFG.data.get("language", "TR")
        try:
            for code in MOD.LANG_CODES:
                MOD.CFG.data["language"] = code
                for eid in MOD.EFFECTS:
                    ad = MOD.effect_name(eid)
                    with self.subTest(dil=code, etki=eid):
                        self.assertTrue(ad.strip())
                        self.assertFalse(ad.startswith(("fx.", "ui.")),
                                         "%s/%s cevrilmemis: %r" % (code, eid, ad))
        finally:
            MOD.CFG.data["language"] = eski

    def test_bulastirma_tablolari_gecerli(self):
        for tur, (eid, kare, olasi) in MOD.ENEMY_INFLICT.items():
            with self.subTest(tur=tur):
                self.assertIn(tur, MOD.BEHAVIORS, "%s diye bir tur yok" % tur)
                self.assertIn(eid, MOD.EFFECTS)
                self.assertFalse(MOD.EFFECTS[eid]["good"],
                                 "dusman IYI etki bulastiriyor: %s" % eid)
                self.assertGreater(kare, 0)
                self.assertTrue(0 < olasi <= 1)
        for pk, (eid, kare, olasi) in MOD.PROJ_INFLICT.items():
            with self.subTest(mermi=pk):
                self.assertIn(pk, MOD.PROJ_ELEM)
                self.assertIn(eid, MOD.EFFECTS)
        for el, (eid, kare, olasi) in MOD.PLAYER_INFLICT.items():
            with self.subTest(element=el):
                self.assertIn(el, MOD.ELEMENTS)
                self.assertIn(eid, MOD.EFFECTS)


class TestOyuncuyaEtki(unittest.TestCase):
    def test_zehir_zamanla_can_goturuyor(self):
        g = oyun()
        st = g.player.stats
        st.hp = st.max_hp
        g._etki_ver(g.player, "poison", 600, oyuncu=True)
        per = MOD.EFFECTS["poison"]["tick"]
        for i in range(per * 4):
            g.tick = i
            g._etkileri_isle()
        self.assertLess(st.hp, st.max_hp, "zehir hic can goturmedi")

    def test_yanma_zehirden_hizli(self):
        def kayip(eid):
            g = oyun(); st = g.player.stats; st.hp = st.max_hp
            g._etki_ver(g.player, eid, 3000, oyuncu=True)
            for i in range(360):
                g.tick = i
                g._etkileri_isle()
            return st.max_hp - st.hp
        self.assertGreater(kayip("burn"), kayip("poison"),
                           "yanma zehirden daha yavas yakiyor")

    def test_iyilesme_can_veriyor(self):
        g = oyun()
        st = g.player.stats
        st.hp = 10
        g._etki_ver(g.player, "regen", 900, oyuncu=True)
        per = MOD.EFFECTS["regen"]["tick"]
        for i in range(per * 5):
            g.tick = i
            g._etkileri_isle()
        self.assertGreater(st.hp, 10, "iyilesme hic can vermedi")

    def test_lanet_mana_emiyor_ve_savunmayi_dusuruyor(self):
        g = oyun()
        st = g.player.stats
        st.mp = st.max_mp
        g._etki_ver(g.player, "curse", 900, oyuncu=True)
        per = MOD.EFFECTS["curse"]["tick"]
        for i in range(per * 3):
            g.tick = i
            g._etkileri_isle()
        self.assertLess(st.mp, st.max_mp, "lanet mana emmedi")
        self.assertLess(g._etki_carpani("def_mult"), 1.0, "lanet savunmayi dusurmuyor")

    def test_direnc_gelen_hasari_azaltiyor(self):
        import random as _r
        g = oyun()
        g.player.invincible = 0
        _r.seed(11)
        normal = g._player_take_hit(70)
        g.player.invincible = 0
        g.player.stats.hp = g.player.stats.max_hp
        g._etki_ver(g.player, "resist", 900, oyuncu=True)
        _r.seed(11)
        korumali = g._player_take_hit(70)
        self.assertLess(korumali, normal,
                        "direnc hasari azaltmadi: %d -> %d" % (normal, korumali))

    def test_donma_hareketi_ve_saldiriyi_durduruyor(self):
        g = oyun()
        once = (g.player.tx, g.player.ty)
        g._etki_ver(g.player, "freeze", 120, oyuncu=True)
        self.assertFalse(g._try_move(1, 0), "donmusken yurudu")
        self.assertEqual((g.player.tx, g.player.ty), once)
        g._auto_attack()
        self.assertFalse(g.player.attacking, "donmusken saldirdi")

    def test_sarmasik_tutuyor_ama_saldiriya_izin_veriyor(self):
        g = oyun()
        g._etki_ver(g.player, "root", 120, oyuncu=True)
        self.assertFalse(g._try_move(1, 0), "sarmasikken yurudu")
        g._auto_attack()
        self.assertTrue(g.player.attacking, "sarmasik saldiriyi da engelledi")

    def test_bagisiklik_kotu_etkiyi_tutmuyor(self):
        g = oyun()
        g._etki_ver(g.player, "immune", 600, oyuncu=True)
        self.assertFalse(g._etki_ver(g.player, "poison", 300, oyuncu=True),
                         "bagisikken zehir tuttu")
        self.assertNotIn("poison", g.player.stats.buffs)
        self.assertTrue(g._etki_ver(g.player, "regen", 300, oyuncu=True),
                        "bagisiklik IYI etkiyi de engelledi")

    def test_etkiler_suresi_dolunca_bitiyor(self):
        g = oyun()
        g._etki_ver(g.player, "poison", 3, oyuncu=True)
        for _ in range(6):
            g.player.stats.tick_buffs()
        self.assertNotIn("poison", g.player.stats.buffs, "etki hic bitmiyor")


class TestDusmanaEtki(unittest.TestCase):
    def _dusman(self, g):
        e = MOD.Enemy(10, 10, "wolf", 200, 5, 10, loot=[])
        g.cur_map.enemies.append(e)
        return e

    def test_zehir_dusmani_eritiyor(self):
        g = oyun()
        e = self._dusman(g)
        g._etki_ver(e, "poison", 900)
        per = MOD.EFFECTS["poison"]["tick"]
        for i in range(per * 4):
            g.tick = i
            g._etkileri_isle()
        self.assertLess(e.hp, e.max_hp, "dusman zehirden hic can kaybetmedi")

    def test_sarmasik_dusmani_yerinde_tutuyor(self):
        g = oyun()
        e = self._dusman(g)
        self.assertFalse(e.rooted)
        g._etki_ver(e, "root", 120)
        self.assertTrue(e.rooted, "sarmasik dusmani tutmuyor")

    def test_frozen_ozelligi_hala_calisiyor(self):
        """Eski cagri yerleri e.frozen=... yaziyor; bozulmamali."""
        g = oyun()
        e = self._dusman(g)
        e.frozen = max(e.frozen, 150)
        self.assertEqual(e.frozen, 150)
        self.assertEqual(e.effects.get("freeze"), 150)
        e.frozen = 0
        self.assertNotIn("freeze", e.effects)

    def test_etki_dusmani_oldurebiliyor(self):
        g = oyun()
        e = MOD.Enemy(10, 10, "wolf", 60, 5, 10, loot=[])
        g.cur_map.enemies.append(e)
        e.hp = 3
        g._etki_ver(e, "burn", 900)
        per = MOD.EFFECTS["burn"]["tick"]
        for i in range(per * 6):
            g.tick = i
            g._etkileri_isle()
        self.assertFalse(e.alive, "yanma dusmani oldurmedi")

    def test_diril_etkileri_temizliyor(self):
        g = oyun()
        e = self._dusman(g)
        g._etki_ver(e, "poison", 600)
        e.alive = False
        e.diril()
        self.assertEqual(e.effects, {}, "geri dogan dusman zehirli geldi")


class TestTuketilebilirler(unittest.TestCase):
    def test_panzehir_yalniz_kotuleri_siliyor(self):
        g = oyun()
        st = g.player.stats
        g._etki_ver(g.player, "poison", 600, oyuncu=True)
        g._etki_ver(g.player, "burn", 600, oyuncu=True)
        g._etki_ver(g.player, "regen", 600, oyuncu=True)
        g.player.inventory = ["antidote"]
        g.inv_sel = 0
        g._inv_use_item()
        self.assertNotIn("poison", st.buffs)
        self.assertNotIn("burn", st.buffs)
        self.assertIn("regen", st.buffs, "panzehir iyi etkiyi de sildi")

    def test_yemek_hem_can_hem_mana_veriyor(self):
        g = oyun()
        st = g.player.stats
        st.hp = 5; st.mp = 0
        g.player.inventory = ["honey_cake"]
        g.inv_sel = 0
        g._inv_use_item()
        self.assertGreater(st.hp, 5, "yemek can vermedi")
        self.assertGreater(st.mp, 0, "yemek mana vermedi")
        self.assertIn("regen", st.buffs, "yemek iyilesme baslatmadi")

    def test_fx_esyalari_etkiyi_veriyor(self):
        for k, eid in (("resist_draught", "resist"), ("ward_charm", "immune"),
                       ("travel_bread", "regen")):
            g = oyun()
            g.player.inventory = [k]
            g.inv_sel = 0
            g._inv_use_item()
            with self.subTest(esya=k):
                self.assertIn(eid, g.player.stats.buffs,
                              "%s %s etkisini vermedi" % (k, eid))


class TestHizliErisim(unittest.TestCase):
    def test_tus_tablosu_dort_yuva(self):
        self.assertEqual(MOD.QUICK_SLOTS, 4)
        yuvalar = set(MOD.QUICK_KEYS.values())
        self.assertEqual(yuvalar, {0, 1, 2, 3})
        for k in (pygame.K_5, pygame.K_6, pygame.K_7, pygame.K_8):
            self.assertIn(k, MOD.QUICK_KEYS, "ust sira tusu bagli degil")
        for k in (pygame.K_KP5, pygame.K_KP6, pygame.K_KP7, pygame.K_KP8):
            self.assertIn(k, MOD.QUICK_KEYS, "numerik klavye bagli degil")

    def test_yetenek_tuslariyla_cakismiyor(self):
        for k in (pygame.K_1, pygame.K_2, pygame.K_3, pygame.K_4,
                  pygame.K_KP1, pygame.K_KP2, pygame.K_KP3, pygame.K_KP4):
            self.assertNotIn(k, MOD.QUICK_KEYS, "yetenek tusu yuvaya baglanmis")

    def test_yalnizca_tuketilebilir_konabiliyor(self):
        self.assertTrue(MOD.quick_ok("hp_pot"))
        self.assertTrue(MOD.quick_ok("honey_cake"))
        self.assertTrue(MOD.quick_ok("antidote"))
        self.assertTrue(MOD.quick_ok("tonic_str"))
        self.assertFalse(MOD.quick_ok("iron_sword"), "silah yuvaya giriyor")
        self.assertFalse(MOD.quick_ok("iron_ore"), "malzeme yuvaya giriyor")
        self.assertFalse(MOD.quick_ok("earth_c"), "kristal yuvaya giriyor")

    def test_sandiktan_cikan_iksir_yuvaya_dusuyor(self):
        g = oyun()
        self.assertEqual(g.player.stats.quick, [None] * MOD.QUICK_SLOTS)
        g._quick_autofill("hp_pot")
        g._quick_autofill("mp_pot")
        self.assertEqual(g.player.stats.quick[:2], ["hp_pot", "mp_pot"])

    def test_ayni_esya_iki_yuvaya_dusmez(self):
        g = oyun()
        g._quick_autofill("hp_pot")
        g._quick_autofill("hp_pot")
        self.assertEqual(g.player.stats.quick.count("hp_pot"), 1)

    def test_atama_eski_yuvadan_kaldiriyor(self):
        g = oyun()
        g._quick_assign(0, "hp_pot")
        g._quick_assign(2, "hp_pot")
        self.assertEqual(g.player.stats.quick[0], None)
        self.assertEqual(g.player.stats.quick[2], "hp_pot")

    def test_yuvadan_kullanmak_cantadan_dusuyor(self):
        g = oyun()
        st = g.player.stats
        st.hp = 10
        g.player.inventory = ["hp_pot", "hp_pot", "mp_pot"]
        g._quick_assign(0, "hp_pot")
        g._quick_use(0)
        self.assertEqual(g.player.inventory.count("hp_pot"), 1, "iksir dusmedi")
        self.assertGreater(st.hp, 10, "iksir ise yaramadi")

    def test_bos_yuva_zarar_vermiyor(self):
        g = oyun()
        g.player.inventory = []
        g._quick_assign(1, "hp_pot")
        g._quick_use(1)          # cantada yok
        g._quick_use(3)          # yuva bos
        self.assertEqual(g.player.inventory, [])

    def test_yuvalar_kayitta_duruyor(self):
        g = oyun()
        g._quick_assign(0, "hp_pot")
        g._quick_assign(1, "antidote")
        g.player.inventory = ["hp_pot", "antidote"]
        self.assertTrue(g.save_game())
        g2 = MOD.Game.__new__(MOD.Game)
        g2.ui = MOD.UI(); g2.ps = MOD.PS(); g2._reset()
        self.assertTrue(g2.load_game())
        self.assertEqual(g2.player.stats.quick[:2], ["hp_pot", "antidote"])

    def test_bozuk_kayit_yuvayi_kirmaz(self):
        g = oyun()
        g.player.stats.quick = ["iron_sword", "yok_boyle_bir_sey", None, None]
        g.player.inventory = []
        self.assertTrue(g.save_game())
        g2 = MOD.Game.__new__(MOD.Game)
        g2.ui = MOD.UI(); g2.ps = MOD.PS(); g2._reset()
        self.assertTrue(g2.load_game())
        self.assertEqual(g2.player.stats.quick, [None] * MOD.QUICK_SLOTS)


class TestGorevKutusu(unittest.TestCase):
    def test_ayar_var_ve_varsayilan_acik(self):
        self.assertIn("quest_hud", MOD.Settings.DEFAULTS)
        self.assertTrue(MOD.Settings.DEFAULTS["quest_hud"])

    def test_metinler_cevrili(self):
        eski = MOD.CFG.data.get("language", "TR")
        try:
            for code in MOD.LANG_CODES:
                MOD.CFG.data["language"] = code
                for k in ("ui.quest_hud_on", "ui.quest_hud_off",
                          "ui.tut_quick", "ui.tut_questbox"):
                    t = MOD.T_(k)
                    with self.subTest(dil=code, anahtar=k):
                        self.assertTrue(t.strip() and not t.startswith("ui."))
        finally:
            MOD.CFG.data["language"] = eski


class TestCizim(unittest.TestCase):
    def test_etki_seridi_ciziliyor(self):
        g = oyun()
        st = g.player.stats
        yuzey = pygame.Surface((MOD.SW, MOD.SH))
        yuzey.fill((0, 0, 0))
        g.ui.draw_effects(yuzey, st, 60)
        bos = sum(1 for x in range(0, 300, 3) for y in range(135, 260, 3)
                  if yuzey.get_at((x, y))[:3] != (0, 0, 0))
        self.assertEqual(bos, 0, "etki yokken serit ciziliyor")
        st.buffs.update({"poison": 300, "regen": 600})
        g.ui.draw_effects(yuzey, st, 60)
        dolu = sum(1 for x in range(0, 300, 3) for y in range(135, 260, 3)
                   if yuzey.get_at((x, y))[:3] != (0, 0, 0))
        self.assertGreater(dolu, 50, "etki seridi cizilmedi")

    def test_hizli_cubuk_yetenek_cubuguyla_cakismiyor(self):
        g = oyun()
        st = g.player.stats
        st.quick = ["hp_pot", None, None, None]
        g.player.inventory = ["hp_pot"] * 3
        a = pygame.Surface((MOD.SW, MOD.SH)); a.fill((0, 0, 0))
        g.ui.draw_ability_bar(a, st, 60)
        b = pygame.Surface((MOD.SW, MOD.SH)); b.fill((0, 0, 0))
        g.ui.draw_quick_bar(b, g.player, 60)
        cakisma = 0
        for x in range(0, MOD.SW, 2):
            for y in range(MOD.SH - 80, MOD.SH, 2):
                if a.get_at((x, y))[:3] != (0, 0, 0) and b.get_at((x, y))[:3] != (0, 0, 0):
                    cakisma += 1
        self.assertEqual(cakisma, 0, "%d pikselde ust uste biniyorlar" % cakisma)

    def test_hizli_cubuk_ekrandan_tasmiyor(self):
        g = oyun()
        g.player.stats.quick = ["hp_pot", "mp_pot", "elixir", "antidote"]
        g.player.inventory = ["hp_pot"]
        yuzey = pygame.Surface((MOD.SW, MOD.SH))
        yuzey.fill((0, 0, 0))
        g.ui.draw_quick_bar(yuzey, g.player, 60)
        sag = sum(1 for y in range(MOD.SH - 80, MOD.SH)
                  if yuzey.get_at((MOD.SW - 1, y))[:3] != (0, 0, 0))
        self.assertEqual(sag, 0, "cubuk ekranin sag kenarini asiyor")


if __name__ == "__main__":
    unittest.main(verbosity=2)
