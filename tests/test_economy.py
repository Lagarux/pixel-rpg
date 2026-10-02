#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Ekonomi, farming ve icerik cesitliligi testleri.

Olculen sorunlar, bir daha geri gelmesin diye:
  * Oyunda toplanabilecek TOPLAM altin 1730'du ve magazadaki 22 esyanin
    19'u sandiklardan BEDAVA cikiyordu - en pahali iki silah dahil.
    Altinin harcanacak yeri yoktu.
  * 90 dusman vardi ve her biri bir kez oluyordu: 5368 XP, tavan seviye 10.
    Oyun bitince yapacak bir sey kalmiyordu.
  * Seviye tavani 30 kondugunda eski 1.55'lik egri ona ulasmayi
    29,6 MILYON XP yapiyordu; ulasilamaz tavan tavan degildir.

Calistirmak icin: python -m unittest discover -s tests
"""
import math
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import unittest

import pygame

from harness import load_game_module

MOD = None
MAPS = {}
HARITA_ADLARI = ["ashveil", "dark_forest", "ruins", "desert", "ice_cave",
                 "shadow_castle", "village_dungeon", "south_meadow",
                 "west_river", "mystic_library", "rocky_pass", "misty_swamp",
                 "ember_valley"]


def setUpModule():
    global MOD, MAPS
    MOD = load_game_module("pixel_rpg_economy")
    pygame.init()
    pygame.display.set_mode((MOD.SW, MOD.SH))
    MAPS = {ad: getattr(MOD, "build_" + ad)() for ad in HARITA_ADLARI}


def tearDownModule():
    pygame.quit()


def tum_dusmanlar():
    for m in MAPS.values():
        for e in m.enemies:
            yield e


def sandik_icerigi():
    for ad, m in MAPS.items():
        for pos, loot in m.chests.items():
            for k in loot:
                yield ad, pos, k


class TestSandikDengesi(unittest.TestCase):
    EN_PAHALI = 210   # elixir

    def test_sandiktan_ust_kademe_cikmiyor(self):
        """Magazadaki 22 esyanin 19'u sandiktan bedava cikiyordu."""
        for ad, pos, k in sandik_icerigi():
            if k not in MOD.ITEM_PRICES:
                continue
            with self.subTest(harita=ad, esya=k):
                self.assertLessEqual(
                    MOD.ITEM_PRICES[k], self.EN_PAHALI,
                    "%s %s sandiginda %d altinlik %s var" % (ad, pos, MOD.ITEM_PRICES[k], k))

    def test_pahali_ekipman_yalnizca_satin_alinir(self):
        bedava = {k for _a, _p, k in sandik_icerigi()}
        for m in MAPS.values():
            for e in m.enemies:
                bedava |= set(e.loot)
        pahali = [k for k, f in MOD.ITEM_PRICES.items()
                  if f > 300 and k in MOD.EQUIP_ITEMS]
        self.assertGreaterEqual(len(pahali), 8, "ust kademe yeterince zengin degil")
        for k in pahali:
            with self.subTest(esya=k):
                self.assertNotIn(k, bedava, "%s (%d altin) bedava bulunabiliyor"
                                 % (k, MOD.ITEM_PRICES[k]))

    def test_her_sandik_bir_sey_veriyor(self):
        for ad, m in MAPS.items():
            for pos, loot in m.chests.items():
                with self.subTest(harita=ad, kare=pos):
                    self.assertTrue(loot, "%s %s bos sandik" % (ad, pos))
                    for k in loot:
                        self.assertIn(k, MOD.ALL_ITEMS, "%s: taninmayan esya %s" % (ad, k))


class TestMalzeme(unittest.TestCase):
    def test_her_avlanabilir_turun_malzemesi_var(self):
        """Boss'lar kristal dusuruyor; avlanabilir her tur malzeme vermeli."""
        boss_turleri = {e.kind for e in tum_dusmanlar() if e.is_boss}
        turler = {e.kind for e in tum_dusmanlar() if not e.is_boss} - boss_turleri
        self.assertGreaterEqual(len(turler), 12, "avlanabilir tur sayisi dustu")
        for k in turler:
            with self.subTest(tur=k):
                self.assertIn(k, MOD.DROP_BY_KIND, "%s hicbir malzeme dusurmuyor" % k)

    def test_her_bossun_dusurdugu_bir_sey_var(self):
        for ad, m in MAPS.items():
            for e in m.enemies:
                if not e.is_boss: continue
                with self.subTest(harita=ad, tur=e.kind):
                    self.assertTrue(e.loot, "%s bossu bos dusuyor" % e.kind)

    def test_malzeme_satilabiliyor(self):
        for k, (_ad, _c, deger, _tur) in MOD.MATERIALS.items():
            with self.subTest(malzeme=k):
                self.assertEqual(MOD.sell_price(k), deger)
                self.assertGreater(deger, 0)

    def test_degerli_malzeme_guclu_dusmandan(self):
        """Yarasa kanadi golge kirigindan ucuz olmali."""
        guc = {}
        for e in tum_dusmanlar():
            if e.is_boss:
                continue
            guc.setdefault(e.kind, []).append(e.max_hp)
        ciftler = [(sum(v) / len(v), MOD.MATERIALS[MOD.DROP_BY_KIND[k]][2])
                   for k, v in guc.items() if k in MOD.DROP_BY_KIND]
        ciftler.sort()
        # En zayif ucun malzemesi, en guclu ucunkinden ucuz olmali
        zayif = sum(d for _h, d in ciftler[:3]) / 3.0
        guclu = sum(d for _h, d in ciftler[-3:]) / 3.0
        self.assertLess(zayif, guclu,
                        "zayif dusmanlar guclulerden degerli malzeme veriyor")

    def test_oldurunce_malzeme_dusuyor(self):
        """Sans tabanli; 400 oldurmede en az bir kez dusmeli."""
        g = MOD.Game.__new__(MOD.Game)
        g.ui = MOD.UI(); g.ps = MOD.PS(); g._reset()
        st = MOD.PlayerStats("warrior")
        g.player = MOD.Player(5, 5, st)
        g.levelup_timer = 0
        dusen = 0
        for _ in range(400):
            e = MOD.Enemy(6, 5, "wolf", 1, 1, 1, loot=[])
            g.cur_map.enemies.append(e)
            g.player.inventory = []
            g._kill(e)
            if "beast_pelt" in g.player.inventory:
                dusen += 1
        self.assertGreater(dusen, 0, "400 oldurmede hic malzeme dusmedi")
        oran = dusen / 400.0
        self.assertAlmostEqual(oran, MOD.MAT_DROP_CHANCE, delta=0.12,
                               msg="dusme orani %.2f, beklenen %.2f"
                                   % (oran, MOD.MAT_DROP_CHANCE))


class TestGeriDogum(unittest.TestCase):
    """Dusmanlar bir kez oluyordu: farming diye bir sey yoktu."""

    def _oyun(self):
        g = MOD.Game.__new__(MOD.Game)
        g.ui = MOD.UI(); g.ps = MOD.PS(); g._reset()
        g.player = MOD.Player(5, 5, MOD.PlayerStats("warrior"))
        g.levelup_timer = 0
        g.tick = 0
        return g

    def test_olen_dusman_geri_geliyor(self):
        g = self._oyun()
        e = next(x for x in g.cur_map.enemies if not x.is_boss)
        g.player.snap(e.home[0] + 30, e.home[1])      # oyuncu uzakta
        g._kill(e)
        self.assertFalse(e.alive)
        self.assertIsNotNone(e.respawn_at)
        g.tick = e.respawn_at - 1
        g._respawn_tick(g.cur_map)
        self.assertFalse(e.alive, "suresi dolmadan geri geldi")
        g.tick = e.respawn_at
        g._respawn_tick(g.cur_map)
        self.assertTrue(e.alive, "suresi dolunca geri gelmedi")
        self.assertEqual(e.hp, e.max_hp, "dolu canla gelmedi")
        self.assertEqual((e.tx, e.ty), e.home, "dogdugu karede degil")

    def test_oyuncu_yakindayken_belirmiyor(self):
        g = self._oyun()
        e = next(x for x in g.cur_map.enemies if not x.is_boss)
        g._kill(e)
        g.player.snap(*e.home)                         # dibinde duruyor
        g.tick = e.respawn_at + 600
        g._respawn_tick(g.cur_map)
        self.assertFalse(e.alive, "oyuncunun gozunun onunde belirdi")

    def test_boss_geri_gelmiyor(self):
        g = self._oyun()
        boss = None
        for m in g.maps.values():
            for e in m.enemies:
                if e.is_boss:
                    boss = e; mm = m; break
            if boss: break
        g.player.snap(1, 1)
        g.cur_map = mm
        g._kill(boss)
        self.assertIsNone(boss.respawn_at, "boss geri dogma sayaci aldi")
        g.tick = 10 ** 7
        g._respawn_tick(mm)
        self.assertFalse(boss.alive, "boss geri geldi")

    def test_dogum_karesi_yurunebilir(self):
        """home, yerlestirmeden SONRA alinmali; yoksa duvarin icinde kalir."""
        for ad, m in MAPS.items():
            for e in m.enemies:
                with self.subTest(harita=ad, tur=e.kind):
                    self.assertTrue(m.walkable(*e.home),
                                    "%s: %s dogum karesi %s yurunmez"
                                    % (ad, e.kind, e.home))


class TestYukseltme(unittest.TestCase):
    def test_bedel_tablosu_tutarli(self):
        self.assertEqual(len(MOD.UPGRADE_COST), MOD.UPGRADE_MAX)
        altinlar = [a for a, _m in MOD.UPGRADE_COST]
        mallar = [m for _a, m in MOD.UPGRADE_COST]
        self.assertEqual(altinlar, sorted(altinlar), "altin bedeli artmiyor")
        self.assertEqual(mallar, sorted(mallar), "malzeme bedeli artmiyor")
        self.assertIsNone(MOD.upgrade_cost(MOD.UPGRADE_MAX))

    def test_yukseltme_nitelik_katiyor(self):
        st = MOD.PlayerStats("warrior")
        st.equipment["weapon"] = "steel_sword"
        once = st.attack
        st.upgrades["steel_sword"] = 5
        sonra = st.attack
        self.assertGreater(sonra, once, "yukseltme saldiriyi arttirmadi")

    def test_ana_nitelik_degismiyor(self):
        """Kilic yukseltilince kilic kalmali: en guclu nitelik hangisiyse o artar."""
        for k, (_a, _c, bonus, _s, _cl) in MOD.EQUIP_ITEMS.items():
            if not bonus:
                continue
            ana = sorted(bonus, key=lambda x: (-bonus[x], x))[0]
            with self.subTest(esya=k):
                self.assertEqual(MOD.upgrade_bonus(k, 3, ana), 3)
                for st_k in ("str", "int", "agi", "vit", "wis"):
                    if st_k not in bonus:
                        self.assertEqual(MOD.upgrade_bonus(k, 3, st_k), 0,
                                         "%s olmayan niteligi arttiriyor" % k)

    def test_demircide_yukseltme_sekmesi_var(self):
        demirci = MOD.SHOPS["npc.demirci_boran"]
        self.assertIn("ui.shop_upgrade", MOD.UI.shop_tabs(demirci))
        han = MOD.SHOPS["npc.hanci_mira"]
        self.assertNotIn("ui.shop_upgrade", MOD.UI.shop_tabs(han))

    def test_yukseltme_altin_ve_malzeme_harciyor(self):
        g = MOD.Game.__new__(MOD.Game)
        g.ui = MOD.UI(); g.ps = MOD.PS(); g._reset()
        st = MOD.PlayerStats("warrior")
        st.gold = 500
        st.equipment["weapon"] = "iron_sword"
        g.player = MOD.Player(5, 5, st)
        g.player.inventory = ["iron_ore"] * 5
        g.shop_npc = "npc.demirci_boran"; g.shop_tab = 2; g.shop_sel = 0
        g.shop_msg = None
        altin0 = st.gold
        g._shop_upgrade()
        self.assertEqual(st.upgrades.get("iron_sword"), 1, "kademe artmadi")
        self.assertEqual(st.gold, altin0 - MOD.UPGRADE_COST[0][0], "altin dusmedi")
        self.assertEqual(len(g.player.inventory), 5 - MOD.UPGRADE_COST[0][1],
                         "malzeme harcanmadi")

    def test_malzemesiz_yukseltme_olmuyor(self):
        g = MOD.Game.__new__(MOD.Game)
        g.ui = MOD.UI(); g.ps = MOD.PS(); g._reset()
        st = MOD.PlayerStats("warrior")
        st.gold = 9999
        st.equipment["weapon"] = "iron_sword"
        g.player = MOD.Player(5, 5, st)
        g.player.inventory = []
        g.shop_npc = "npc.demirci_boran"; g.shop_tab = 2; g.shop_sel = 0
        g.shop_msg = None
        g._shop_upgrade()
        self.assertEqual(st.upgrades.get("iron_sword", 0), 0,
                         "malzemesiz yukseltme yapildi")


class TestSeviyeEgrisi(unittest.TestCase):
    def test_tavan_ulasilabilir(self):
        toplam = sum(MOD.xp_to_next(lv) for lv in range(1, MOD.MAX_LEVEL))
        self.assertLess(toplam, 400000,
                        "tavana ulasmak %d XP istiyor: ulasilamaz tavan" % toplam)
        self.assertGreater(toplam, 50000, "tavan cok kolay")

    def test_esik_hep_artiyor(self):
        esikler = [MOD.xp_to_next(lv) for lv in range(1, MOD.MAX_LEVEL)]
        self.assertEqual(esikler, sorted(esikler))

    def test_ilk_seviyeler_hizli_kaldi(self):
        """Hikayenin temposu bozulmasin: ilk 7 seviye eski egride."""
        for lv in range(1, 8):
            self.assertEqual(MOD.xp_to_next(lv), int(50 * (1.55 ** (lv - 1))))

    def test_tavanda_xp_durur(self):
        st = MOD.PlayerStats("warrior")
        st.level = MOD.MAX_LEVEL
        self.assertFalse(st.gain_xp(10 ** 6))
        self.assertEqual(st.level, MOD.MAX_LEVEL)


class TestAltinHedefi(unittest.TestCase):
    def test_harcanacak_yer_kazanilandan_fazla(self):
        """Eskiden 1730 altin kazanilip 0'i harcaniyordu."""
        kazanc = 0.0
        for e in tum_dusmanlar():
            kazanc += 2.5 + 5 * sum(1 for i in e.loot if i == "gold")
            mat = MOD.DROP_BY_KIND.get(e.kind)
            if mat:
                p = 1.0 if e.is_boss else MOD.MAT_DROP_CHANCE
                kazanc += p * MOD.MATERIALS[mat][2]
        for _a, _p, k in sandik_icerigi():
            if k == "gold":
                kazanc += MOD.ITEMS["gold"][3]
        kazanc += sum(q["gold"] for q in MOD.SIDE_QUESTS) + 20
        hedef = sum(MOD.item_price(k) for k in MOD.ITEM_PRICES
                    if MOD.item_price(k) > 300)
        hedef += sum(a for a, _m in MOD.UPGRADE_COST) * len(MOD.EQUIP_SLOTS)
        self.assertGreater(hedef, kazanc * 1.5,
                           "harcanacak yer (%d) kazanca (%d) gore yetersiz"
                           % (hedef, kazanc))

    def test_her_satilan_esyanin_fiyati_var(self):
        for npc, sh in MOD.SHOPS.items():
            for k in sh["stock"]:
                with self.subTest(npc=npc, esya=k):
                    self.assertIn(k, MOD.ITEM_PRICES, "%s fiyatsiz satiliyor" % k)
                    self.assertIn(k, MOD.ALL_ITEMS)

    def test_her_sinifin_ust_kademesi_var(self):
        for cls in MOD.CLASS_INFO:
            ust = [k for k, (_a, _c, _b, slot, cl) in MOD.EQUIP_ITEMS.items()
                   if slot == "weapon" and MOD.item_price(k) > 500
                   and (cl is None or cls in cl)]
            with self.subTest(sinif=cls):
                self.assertTrue(ust, "%s sinifinin ust kademe silahi yok" % cls)


class TestYeniTurler(unittest.TestCase):
    YENI = ("bat", "spider", "bandit", "wraith", "treant", "lava_imp")

    def test_hepsi_dunyada_var(self):
        turler = {e.kind for e in tum_dusmanlar()}
        for k in self.YENI:
            with self.subTest(tur=k):
                self.assertIn(k, turler, "%s hicbir haritada yok" % k)

    def test_tablolar_eksiksiz(self):
        for k in self.YENI:
            with self.subTest(tur=k):
                self.assertIn(k, MOD.BEHAVIORS)
                self.assertIn(k, MOD.ENEMY_ELEM)
                self.assertIn(k, MOD.AGGRO)
                self.assertIn(k, MOD.ENEMY_TUNE)
                self.assertIn(MOD.ENEMY_ELEM[k], MOD.ELEMENTS)

    def test_cizimleri_bos_degil_ve_ayri(self):
        goruntu = {}
        for k in {e.kind for e in tum_dusmanlar()}:
            sp = MOD.PA.enemy_surf(k, 0)
            self.assertGreater(pygame.mask.from_surface(sp).count(), 60,
                               "%s neredeyse bos" % k)
            goruntu[k] = pygame.image.tostring(sp, "RGBA")
        adlar = sorted(goruntu)
        for i, a in enumerate(adlar):
            for b in adlar[i + 1:]:
                self.assertNotEqual(goruntu[a], goruntu[b],
                                    "%s ve %s ayni cizim" % (a, b))

    def test_menzilli_turlerin_mermisi_tanimli(self):
        for k, bh in MOD.BEHAVIORS.items():
            if bh.get("type") != "ranged":
                continue
            with self.subTest(tur=k):
                proj = bh.get("proj")
                self.assertIn(proj, MOD.PROJ_ELEM, "%s mermisi elementsiz" % k)
                sp = MOD.PA.proj_surf(proj, 0)
                self.assertGreater(pygame.mask.from_surface(sp).count(), 5,
                                   "%s mermisi bos" % proj)

    def test_hiz_tablosu_makul(self):
        for k, v in MOD.SPEED_MOD.items():
            with self.subTest(tur=k):
                self.assertIn(k, MOD.BEHAVIORS, "%s diye bir tur yok" % k)
                self.assertLess(abs(v), 15)


class TestEsyaKullanimi(unittest.TestCase):
    """Her esya tipi envanterde gercekten BIR SEY yapmali.

    Kusur: _inv_use_item yalnizca heal/mana/quest_sq/stat_*/equip
    tiplerini taniyordu. "full" (Tam Sifa Iksiri) ve "buff_*" (ucu de
    tonik) sessizce dusuyordu - oyuncu iksiri iciyor, hicbir sey
    olmuyordu. Hicbir test bunu yakalamamisti.
    """

    def _oyun(self):
        g = MOD.Game.__new__(MOD.Game)
        g.ui = MOD.UI(); g.ps = MOD.PS(); g._reset()
        st = MOD.PlayerStats("warrior")
        g.player = MOD.Player(5, 5, st)
        g.dmg_nums = []
        return g

    def test_her_tip_isleniyor(self):
        """Taninmayan tip = sessizce dusen esya."""
        BILINEN = {"heal", "mana", "full", "material", "quest", "quest_sq",
                   "equip", "gold", "stat_str", "stat_int", "stat_agi",
                   "stat_vit", "stat_wis", "buff_str", "buff_def", "buff_agi"}
        for k, satir in MOD.ALL_ITEMS.items():
            with self.subTest(esya=k):
                self.assertIn(satir[2], BILINEN, "%s taninmayan tipte: %s" % (k, satir[2]))

    def test_tuketilebilirler_tukeniyor_ve_etki_ediyor(self):
        for k, satir in MOD.ALL_ITEMS.items():
            typ = satir[2]
            if typ not in ("heal", "mana", "full") and not typ.startswith(("buff_", "stat_")):
                continue
            g = self._oyun()
            st = g.player.stats
            st.hp = 1; st.mp = 0
            g.player.inventory = [k]
            g.inv_sel = 0
            once = (st.hp, st.mp, st.str, st.int_, st.agi, st.vit, st.wis,
                    dict(st.buffs))
            g._inv_use_item()
            sonra = (st.hp, st.mp, st.str, st.int_, st.agi, st.vit, st.wis,
                     dict(st.buffs))
            with self.subTest(esya=k):
                self.assertEqual(g.player.inventory, [],
                                 "%s kullanildi ama envanterden dusmedi" % k)
                self.assertNotEqual(once, sonra,
                                    "%s kullanildi ama HICBIR SEY degismedi" % k)

    def test_tam_sifa_iksiri_ikisini_de_dolduruyor(self):
        g = self._oyun()
        st = g.player.stats
        st.hp = 1; st.mp = 1
        g.player.inventory = ["elixir"]; g.inv_sel = 0
        g._inv_use_item()
        self.assertEqual(st.hp, st.max_hp)
        self.assertEqual(st.mp, st.max_mp)

    def test_tonikler_dovuse_etki_ediyor(self):
        st = MOD.PlayerStats("warrior")
        vurus0, krit0 = st.attack, st.crit
        st.buffs["tonic_str"] = 900
        self.assertGreater(st.attack, vurus0, "Guc Tonigi saldiriyi arttirmadi")
        del st.buffs["tonic_str"]
        st.buffs["tonic_agi"] = 900
        self.assertGreater(st.crit, krit0, "Ruzgar Tonigi kritigi arttirmadi")

    def test_tas_derisi_hasari_azaltiyor(self):
        g = self._oyun()
        g.cur_map = g.maps["ashveil"]
        st = g.player.stats
        st.hp = st.max_hp
        g.player.invincible = 0
        import random as _r
        _r.seed(7)
        normal = g._player_take_hit(60)
        g.player.invincible = 0
        st.buffs["tonic_def"] = 900
        _r.seed(7)
        korumali = g._player_take_hit(60)
        self.assertLess(korumali, normal,
                        "Tas Derisi hasari azaltmadi: %d -> %d" % (normal, korumali))

    def test_malzeme_tukenmiyor_ama_aciklama_veriyor(self):
        g = self._oyun()
        g.player.inventory = ["iron_ore"]; g.inv_sel = 0
        g._inv_use_item()
        self.assertEqual(g.player.inventory, ["iron_ore"],
                         "malzeme bosuna harcandi")
        self.assertTrue(g.dmg_nums, "malzemeye basinca hicbir sey soylenmiyor")

    def test_tonik_sureleri_makul(self):
        for k, satir in MOD.ALL_ITEMS.items():
            if not satir[2].startswith("buff_"):
                continue
            sure = satir[3] / float(MOD.FPS)
            with self.subTest(esya=k):
                self.assertGreaterEqual(sure, 5, "%s cok kisa: %.0f sn" % (k, sure))
                self.assertLessEqual(sure, 60, "%s cok uzun: %.0f sn" % (k, sure))


class TestDukkanTusAkisi(unittest.TestCase):
    """Gercek tus yolundan: TAB uc sekme arasinda donmeli.

    Birim testler _shop_upgrade()'i dogrudan cagiriyor; bu test oyunu
    gercekten surerek sekme dolasimini ve E tusunu deniyor.
    """

    def test_tab_uc_sekme_arasinda_donuyor(self):
        from harness import Harness
        h = Harness(MOD, shot_prefix="ekonomi_")
        goruldu = []

        def dukkani_ac(g):
            g.player.stats.gold = 900
            g.player.stats.equipment["weapon"] = "iron_sword"
            g.player.inventory = ["iron_ore"] * 4
            g._open_shop(type("N", (), {"name": "npc.demirci_boran"})())

        def kaydet(g):
            goruldu.append(g.shop_tab)

        script = h.intro() + [
            h.do(dukkani_ac), h.wait(3), h.do(kaydet),
            h.key(pygame.K_TAB, 3), h.do(kaydet),
            h.key(pygame.K_TAB, 3), h.do(kaydet),
            h.key(pygame.K_TAB, 3), h.do(kaydet),
            h.wait(2),
        ]
        h.run(script)
        self.assertEqual(goruldu, [0, 1, 2, 0],
                         "TAB sekmeleri dolasmiyor: %s" % goruldu)
        self.assertEqual(h.errors, [], "hata: %s" % h.errors)

    def test_e_tusu_yukseltiyor(self):
        from harness import Harness
        h = Harness(MOD, shot_prefix="ekonomi2_")
        sonuc = {}

        def hazirla(g):
            g.player.stats.gold = 900
            g.player.stats.equipment["weapon"] = "iron_sword"
            g.player.inventory = ["iron_ore"] * 4
            g._open_shop(type("N", (), {"name": "npc.demirci_boran"})())
            g.shop_tab = 2
            g.shop_sel = 0

        def oku(g):
            sonuc["kademe"] = g.player.stats.upgrades.get("iron_sword", 0)
            sonuc["altin"] = g.player.stats.gold

        script = h.intro() + [
            h.do(hazirla), h.wait(3),
            h.key(pygame.K_e, 4),
            h.do(oku), h.wait(2),
        ]
        h.run(script)
        self.assertEqual(sonuc.get("kademe"), 1, "E tusu yukseltmedi")
        self.assertEqual(sonuc.get("altin"), 900 - MOD.UPGRADE_COST[0][0])
        self.assertEqual(h.errors, [], "hata: %s" % h.errors)


class TestYeniEsyaCevirileri(unittest.TestCase):
    def test_her_esyanin_adi_bes_dilde_var(self):
        eski = MOD.CFG.data.get("language", "TR")
        try:
            for code in MOD.LANG_CODES:
                MOD.CFG.data["language"] = code
                for k in MOD.ALL_ITEMS:
                    ad = MOD.item_name(k)
                    with self.subTest(dil=code, esya=k):
                        self.assertTrue(ad.strip(), "%s/%s bos" % (code, k))
                        self.assertFalse(ad.startswith("item."),
                                         "%s/%s cevrilmemis: %r" % (code, k, ad))
        finally:
            MOD.CFG.data["language"] = eski

    def test_yukseltme_metinleri_cevrili(self):
        eski = MOD.CFG.data.get("language", "TR")
        anahtarlar = ("ui.shop_upgrade", "ui.upg_materials", "ui.upg_nothing",
                      "ui.shop_keys_upgrade", "ui.upg_max", "ui.upg_mat_unit",
                      "ui.upg_already_max", "ui.upg_no_material", "ui.upg_done")
        try:
            for code in MOD.LANG_CODES:
                MOD.CFG.data["language"] = code
                for k in anahtarlar:
                    with self.subTest(dil=code, anahtar=k):
                        t = MOD.T_(k, 1, 2)
                        self.assertTrue(t.strip() and not t.startswith("ui."),
                                        "%s/%s cevrilmemis" % (code, k))
        finally:
            MOD.CFG.data["language"] = eski


class TestKayit(unittest.TestCase):
    def test_yukseltmeler_kayitta_duruyor(self):
        import tempfile
        MOD.SAVE_FILE = os.path.join(tempfile.mkdtemp(), "save1.json")
        g = MOD.Game.__new__(MOD.Game)
        g.ui = MOD.UI(); g.ps = MOD.PS(); g._reset()
        st = MOD.PlayerStats("warrior")
        st.equipment["weapon"] = "iron_sword"
        st.upgrades = {"iron_sword": 3}
        g.player = MOD.Player(5, 5, st)
        g.player.inventory = ["iron_ore", "bone_dust"]
        self.assertTrue(g.save_game())
        g2 = MOD.Game.__new__(MOD.Game)
        g2.ui = MOD.UI(); g2.ps = MOD.PS(); g2._reset()
        self.assertTrue(g2.load_game())
        self.assertEqual(g2.player.stats.upgrades.get("iron_sword"), 3)
        self.assertIn("iron_ore", g2.player.inventory)


if __name__ == "__main__":
    unittest.main(verbosity=2)
