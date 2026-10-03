#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Yan gorev testleri.

Neden var: ciftcinin domuz avi gorevi 3 domuz istiyordu ama oyuncunun o
sirada gidebildigi cayirda sadece 2 domuz vardi. Diger ikisi cok sonraki
bataklik haritasindaydi. Oyuncu 2/3'te takiliyor, gorevin bozuk oldugunu
saniyordu. Dunyada toplam 4 domuz oldugu icin "sayi yeterli" gibi
gorunuyordu -- asil sorun NEREDE olduklariydi.

Bu testler gorevin bitirilebilirligini haritadan haritaya olcuyor.

Calistirmak icin: python -m unittest discover -s tests
"""
import os
import shutil
import sys
import tempfile
from collections import deque

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import unittest

import pygame

from harness import load_game_module

MOD = None
TMP = None
G = None

# Gorev kimligi -> sayilan dusman turu
# Hangi gorev hangi turu olduruyor - ELLE TUTULMUYOR.
# Elle yazilan tablo yeni gorevler eklenince guncellenmiyordu: alti yeni
# dusman turu icin gorev eklendigi halde testler onlari hic denetlemedi.
# Artik ilerleme fonksiyonuna "kill_<tur>" bayragi verilip sonucun degisip
# degismedigine bakiliyor; yeni bir gorev kendiliginden kapsama giriyor.
def _oldurme_gorevleri(mod):
    out = {}
    turler = {e.kind for m in G.maps.values() for e in m.enemies}
    for sq in mod.SIDE_QUESTS:
        for kind in turler:
            if sq["progress"]({"kill_" + kind: 999})[0] > sq["progress"]({})[0]:
                out[sq["id"]] = kind
                break
    return out


OLDURME_GOREVI = {}


def setUpModule():
    global MOD, TMP, G
    MOD = load_game_module("pixel_rpg_quests")
    TMP = tempfile.mkdtemp(prefix="pixelrpg_quests_")
    MOD.SAVE_FILE = os.path.join(TMP, "save1.json")
    pygame.init()
    pygame.display.set_mode((MOD.SW, MOD.SH))
    G = MOD.Game.__new__(MOD.Game)
    G.ui = MOD.UI()
    G.ps = MOD.PS()
    G._reset()
    OLDURME_GOREVI.update(_oldurme_gorevleri(MOD))


def tearDownModule():
    pygame.quit()
    shutil.rmtree(TMP, ignore_errors=True)


def map_depth():
    """Her haritanin koyden kac gecit uzakta oldugu."""
    uz = {"ashveil": 0}
    q = deque(["ashveil"])
    while q:
        k = q.popleft()
        for v in {x for x in G.maps[k].transitions.values()}:
            if v[0] not in uz:
                uz[v[0]] = uz[k] + 1
                q.append(v[0])
    return uz


def counts_by_depth(kind):
    """{derinlik: o derinlikteki dusman sayisi}"""
    uz = map_depth()
    out = {}
    for key, m in G.maps.items():
        n = sum(1 for e in m.enemies if e.kind == kind)
        if n:
            out[uz[key]] = out.get(uz[key], 0) + n
    return out


def target_of(qid):
    for sq in MOD.SIDE_QUESTS:
        if sq["id"] == qid:
            return sq["progress"]({})[1]
    raise KeyError(qid)


class TestCompletable(unittest.TestCase):
    def test_every_kill_quest_can_be_finished(self):
        for qid, kind in OLDURME_GOREVI.items():
            hedef = target_of(qid)
            toplam = sum(counts_by_depth(kind).values())
            self.assertGreaterEqual(toplam, hedef,
                                    "%s gorevi %d istiyor ama dunyada %d %s var"
                                    % (qid, hedef, toplam, kind))

    def test_every_kill_quest_has_headroom(self):
        """Bir dusmani kacirmak ya da bir haritayi atlamak gorevi kilitlememeli."""
        for qid, kind in OLDURME_GOREVI.items():
            hedef = target_of(qid)
            toplam = sum(counts_by_depth(kind).values())
            self.assertGreaterEqual(toplam, hedef + 2,
                                    "%s: %d hedef icin sadece %d %s var, pay yok"
                                    % (qid, hedef, toplam, kind))

    def test_quests_do_not_strand_the_player_early(self):
        """Asil hata buydu: dusmanin cogu erken haritalardaysa, oyuncu orada
        bitirebilmeli. Yoksa bariz yerde arar, bulamaz, gorev bozuk sanir."""
        for qid, kind in OLDURME_GOREVI.items():
            hedef = target_of(qid)
            derin = counts_by_depth(kind)
            toplam = sum(derin.values())
            erken = sum(n for d, n in derin.items() if d <= 1)
            if toplam and erken / toplam >= 0.5:      # bu bir "erken" dusman
                self.assertGreaterEqual(
                    erken, hedef,
                    "%s gorevi %d istiyor; %s'lerin %d/%d'i erken haritalarda "
                    "ama orada sadece %d tane var -- oyuncu takilir"
                    % (qid, hedef, kind, erken, toplam, erken))

    def test_the_boar_quest_specifically(self):
        """Kullanicinin bildirdigi hata: cayirda 3 domuz bulunamiyordu."""
        cayir = sum(1 for e in G.maps["south_meadow"].enemies if e.kind == "boar")
        self.assertGreaterEqual(cayir, target_of("boar"),
                                "ciftcinin cayirinda sadece %d domuz var, gorev %d istiyor"
                                % (cayir, target_of("boar")))


class TestItemQuests(unittest.TestCase):
    """Esya toplama gorevleri.

    Parsomen gorevi bitirilemiyordu: kutuphaneci "harabelerde, colde ve buz
    magarasinda" diyordu ama uc parsomenin HICBIRI dunyada yoktu. Oldurme
    gorevlerini olcen testler bunu goremedi, cunku bu bir esya gorevi.
    """

    def world_items(self):
        """Dunyada ele gecirilebilen her esya: sandiklar + dusman ganimeti."""
        bulunan = {}
        for key, m in G.maps.items():
            for pos, icerik in m.chests.items():
                for it in icerik:
                    bulunan.setdefault(it, []).append((key, pos))
            for e in m.enemies:
                for it in (e.loot or []):
                    bulunan.setdefault(it, []).append((key, (e.tx, e.ty)))
        return bulunan

    def test_every_quest_item_exists_in_the_world(self):
        """ITEMS icinde quest_sq turundeki her esya bulunabilir olmali."""
        dunya = self.world_items()
        eksik = [ik for ik, row in MOD.ITEMS.items()
                 if row[2] == "quest_sq" and ik not in dunya]
        self.assertEqual(eksik, [], "gorev esyasi dunyada hic yok: %s" % eksik)

    def test_every_crystal_exists(self):
        dunya = self.world_items()
        for ik in ("earth_c", "water_c"):
            self.assertIn(ik, dunya, "%s dunyada yok -- ana gorev kilitlenir" % ik)

    def test_scrolls_are_where_the_librarian_says(self):
        """Kutuphaneci harabe, col ve buz magarasi diyor; sozu tutulmali."""
        dunya = self.world_items()
        soylenen = {"ruins", "desert", "ice_cave"}
        yerler = set()
        for ik in ("scroll1", "scroll2", "scroll3"):
            self.assertIn(ik, dunya, "%s hicbir yerde yok" % ik)
            yerler.update(h for h, _ in dunya[ik])
        self.assertTrue(yerler <= soylenen,
                        "parsomenler kutuphanecinin saymadigi haritalarda: %s"
                        % (yerler - soylenen))
        self.assertEqual(yerler, soylenen,
                         "soylenen haritalarin hepsinde parsomen yok: eksik %s"
                         % (soylenen - yerler))

    def test_scroll_quest_can_actually_be_completed(self):
        """Uc parsomeni alan oyuncu gorevi bitirebilmeli."""
        sq = next(s for s in MOD.SIDE_QUESTS if s["id"] == "scroll")
        f = {"sq_scroll1": True, "sq_scroll2": True, "sq_scroll3": True}
        self.assertTrue(MOD.sq_done(sq, f), "parsomenler toplandi ama gorev bitmiyor")

    def test_picking_a_scroll_sets_its_flag(self):
        """Sandiktan alinca bayrak kendiliginden set ediliyor mu?"""
        g = MOD.Game.__new__(MOD.Game)
        g.ui = MOD.UI(); g.ps = MOD.PS(); g._reset()
        g.temp_stats = MOD.PlayerStats("warrior"); g._start_game()
        g.cur_key = "ruins"; g.cur_map = g.maps["ruins"]
        yer = next(pos for pos, ic in g.cur_map.chests.items() if "scroll1" in ic)
        g.player.snap(yer[0], yer[1] - 1); g.player.direction = "down"
        g.dmg_nums = []
        g._interact()
        self.assertTrue(g.flags.get("sq_scroll1"), "parsomen alindi ama bayrak set edilmedi")
        self.assertIn("scroll1", g.player.inventory)


class TestQuestTable(unittest.TestCase):
    def test_ids_are_unique(self):
        ids = [sq["id"] for sq in MOD.SIDE_QUESTS]
        self.assertEqual(len(ids), len(set(ids)), "yinelenen gorev kimligi: %s" % ids)

    def test_every_quest_is_translated(self):
        eski = MOD.CFG.data.get("language", "TR")
        try:
            for code in MOD.LANG_CODES:
                MOD.CFG.data["language"] = code
                for sq in MOD.SIDE_QUESTS:
                    for alan in ("title", "desc", "unit"):
                        txt = MOD.T_(sq[alan])
                        self.assertNotEqual(txt, sq[alan],
                                            "%s/%s/%s cevrilmemis" % (code, sq["id"], alan))
                        self.assertTrue(txt.strip())
        finally:
            MOD.CFG.data["language"] = eski

    def test_rewards_grow_with_difficulty(self):
        """Gec oyun gorevleri erken gorevlerden fazla odemeli."""
        odul = {sq["id"]: sq["gold"] + sq["xp"] for sq in MOD.SIDE_QUESTS}
        erken = max(odul[q] for q in ("slime", "fish", "boar"))
        gec = min(odul[q] for q in ("icewolf", "knight"))
        self.assertGreater(gec, erken,
                           "gec oyun gorevleri (%d) erken gorevlerden (%d) fazla odemiyor"
                           % (gec, erken))

    def test_progress_is_bounded(self):
        """Ilerleme hedefi asmamali, yoksa panelde 9/3 gibi sayilar cikar."""
        cok = {"kill_%s" % k: 99 for k in OLDURME_GOREVI.values()}
        cok.update({"chests_opened": 99, "sq_fish_done": True, "sq_witch_done": True,
                    "sq_hermit_done": True, "sq_scroll1": True, "sq_scroll2": True,
                    "sq_scroll3": True})
        for sq in MOD.SIDE_QUESTS:
            got, need = sq["progress"](cok)
            self.assertLessEqual(got, need, "%s: ilerleme hedefi asiyor (%d/%d)"
                                            % (sq["id"], got, need))

    def test_there_are_enough_quests(self):
        self.assertGreaterEqual(len(MOD.SIDE_QUESTS), 12,
                                "yan gorev sayisi az: %d" % len(MOD.SIDE_QUESTS))


class TestBalikciGorevi(unittest.TestCase):
    """Kullanici bildirdi: "konustuktan sonra gorev tamamlaniyor,
    ilginc bir sekilde". Gercekten de tek yaptigi konusmakti."""

    def test_konusmak_gorevi_bitirmiyor(self):
        g = MOD.Game.__new__(MOD.Game)
        g.ui = MOD.UI(); g.ps = MOD.PS(); g._reset()
        g.player = MOD.Player(5, 5, MOD.PlayerStats("warrior"))
        riva = next(n for m in g.maps.values() for n in m.npcs
                    if n.name == "npc.balikci_riva")
        g._npc_side_effects(riva)
        sq = next(q for q in MOD.SIDE_QUESTS if q["id"] == "fish")
        got, need = sq["progress"](g.flags)
        self.assertEqual(got, 0, "konusunca gorev kendiliginden ilerledi")
        self.assertTrue(g.flags.get("sq_fish_started"), "gorev baslamadi")

    def test_uc_balik_dunyada_var(self):
        baliklar = {"fish_silver", "fish_gold", "fish_shadow"}
        bulunan = set()
        for ad, m in G.maps.items():
            for loot in m.chests.values():
                bulunan |= (set(loot) & baliklar)
        self.assertEqual(bulunan, baliklar,
                         "dunyada olmayan balik: %s" % (baliklar - bulunan))

    def test_baliklar_erisilebilir_haritalarda(self):
        """Parsomen hatasinin aynisi olmasin: esya dunyada ama ulasilmazsa
        gorev bitmez."""
        baliklar = {"fish_silver", "fish_gold", "fish_shadow"}
        for ad, m in G.maps.items():
            for pos, loot in m.chests.items():
                if set(loot) & baliklar:
                    komsu = any(m.walkable(pos[0] + dx, pos[1] + dy)
                                for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)))
                    with self.subTest(harita=ad, kare=pos):
                        self.assertTrue(komsu, "%s %s sandigina ulasilamiyor"
                                        % (ad, pos))

    def test_balik_alinca_bayrak_kuruluyor(self):
        g = MOD.Game.__new__(MOD.Game)
        g.ui = MOD.UI(); g.ps = MOD.PS(); g._reset()
        g.player = MOD.Player(5, 5, MOD.PlayerStats("warrior"))
        g.cur_map = g.maps["west_river"]
        kare = next(p for p, l in g.cur_map.chests.items() if "fish_silver" in l)
        g.player.snap(*MOD._snap(g.cur_map, kare[0] + 1, kare[1]))
        g.player.direction = "left"
        g._interact()
        self.assertTrue(g.flags.get("sq_fish_silver"), "balik bayragi kurulmadi")

    def test_uc_balikla_gorev_bitiyor(self):
        sq = next(q for q in MOD.SIDE_QUESTS if q["id"] == "fish")
        f = {"sq_fish_silver": True, "sq_fish_gold": True, "sq_fish_shadow": True}
        got, need = sq["progress"](f)
        self.assertEqual((got, need), (3, 3))
        self.assertTrue(MOD.sq_done(sq, f))

    def test_riva_uc_farkli_sey_soyluyor(self):
        riva = next(n for m in G.maps.values() for n in m.npcs
                    if n.name == "npc.balikci_riva")
        bas = tuple(riva.get_dialog({}))
        orta = tuple(riva.get_dialog({"sq_fish_started": True}))
        son = tuple(riva.get_dialog({"sq_fish_silver": True, "sq_fish_gold": True,
                                     "sq_fish_shadow": True}))
        self.assertEqual(len({bas, orta, son}), 3,
                         "Riva gorevin her asamasinda ayni seyi soyluyor")


class TestGunlukKaydirma(unittest.TestCase):
    """Olcum: hic gorev bitmemisken 14 yan gorevin yalnizca 8'i
    gorunuyordu ve liste SESSIZCE kesiliyordu."""

    def test_hepsi_sigmiyorsa_kaydirma_aciliyor(self):
        enb = MOD.UI.quest_scroll_max({})
        self.assertGreater(enb, 0,
                           "liste tasiyor ama kaydirma yok: gorevler gizli kalir")

    def test_her_gorev_bir_kaydirmada_gorunuyor(self):
        """Hicbir gorev erisilemez kalmamali."""
        flags = {}
        enb = MOD.UI.quest_scroll_max(flags)
        gorulen = set()
        for kay in range(enb + 1):
            y = 0
            for sq in MOD.SIDE_QUESTS[kay:]:
                yuk = MOD.UI.quest_row_h(sq, flags)
                if y + yuk > MOD.UI.QUEST_AREA_H:
                    break
                gorulen.add(sq["id"])
                y += yuk
        eksik = {sq["id"] for sq in MOD.SIDE_QUESTS} - gorulen
        self.assertEqual(eksik, set(), "hicbir kaydirmada gorunmeyen gorev: %s" % eksik)

    def test_son_gorev_en_alt_kaydirmada_gorunuyor(self):
        flags = {}
        kay = MOD.UI.quest_scroll_max(flags)
        y = 0
        son = None
        for sq in MOD.SIDE_QUESTS[kay:]:
            yuk = MOD.UI.quest_row_h(sq, flags)
            if y + yuk > MOD.UI.QUEST_AREA_H:
                break
            son = sq["id"]
            y += yuk
        self.assertEqual(son, MOD.SIDE_QUESTS[-1]["id"],
                         "en alta kaydirinca son gorev gorunmuyor")

    def test_hepsi_bitince_kaydirma_kapaniyor(self):
        """Bitmis gorev satiri kisa; hepsi bitince liste sigmali."""
        flags = {}
        for sq in MOD.SIDE_QUESTS:
            got, need = sq["progress"]({})
            flags["sqpaid_" + sq["id"]] = True
        # bitmis saymasi icin ilerlemeyi doldur
        flags.update({"kill_boar": 99, "kill_wolf": 99, "kill_skeleton": 99,
                      "kill_golem": 99, "kill_slime": 99, "kill_goblin": 99,
                      "kill_scorpion": 99, "kill_ice_wolf": 99,
                      "kill_shadow_knight": 99, "kill_spider": 99,
                      "kill_bat": 99, "kill_bandit": 99, "kill_treant": 99,
                      "kill_wraith": 99, "kill_lava_imp": 99,
                      "chests_opened": 99, "materials_found": 99,
                      "max_upgrade": 9,
                      "sq_fish_silver": True, "sq_fish_gold": True,
                      "sq_fish_shadow": True,
                      "sq_witch_done": True, "sq_hermit_done": True,
                      "sq_scroll1": True, "sq_scroll2": True, "sq_scroll3": True})
        self.assertEqual(MOD.UI.quest_scroll_max(flags), 0,
                         "hepsi bitmisken bile kaydirma gerekiyor")

    def test_cizim_kaydirmayla_patlamiyor(self):
        ui = MOD.UI()
        yuzey = pygame.Surface((MOD.SW, MOD.SH))
        for kay in (0, 3, MOD.UI.quest_scroll_max({}), 999):
            with self.subTest(kaydirma=kay):
                yuzey.fill((0, 0, 0))
                ui.draw_quest_log(yuzey, {}, 3, kay)


class TestYeniSistemBayraklari(unittest.TestCase):
    """Malzeme ve yukseltme gorevleri bayrak sayaclarina dayaniyor."""

    def _oyun(self):
        g = MOD.Game.__new__(MOD.Game)
        g.ui = MOD.UI(); g.ps = MOD.PS(); g._reset()
        g.player = MOD.Player(5, 5, MOD.PlayerStats("warrior"))
        g.levelup_timer = 0
        g.tick = 0
        return g

    def test_malzeme_dusunce_sayac_artiyor(self):
        g = self._oyun()
        once = g.flags.get("materials_found", 0)
        dustu = 0
        for _ in range(300):
            e = MOD.Enemy(6, 5, "wolf", 1, 1, 1, loot=[])
            g.cur_map.enemies.append(e)
            g._kill(e)
        sonra = g.flags.get("materials_found", 0)
        self.assertGreater(sonra, once, "malzeme sayaci hic artmadi")
        self.assertEqual(sonra, sum(1 for k in g.player.inventory
                                    if k in MOD.MATERIALS),
                         "sayac cantadakiyle uyusmuyor")

    def test_yukseltme_sayaci_gorevi_ilerletiyor(self):
        g = self._oyun()
        st = g.player.stats
        st.gold = 9999
        st.equipment["weapon"] = "iron_sword"
        g.player.inventory = ["iron_ore"] * 30
        g.shop_npc = "npc.demirci_boran"; g.shop_tab = 2; g.shop_sel = 0
        g.shop_msg = None
        sq = next(q for q in MOD.SIDE_QUESTS if q["id"] == "forge")
        for _ in range(3):
            g._shop_upgrade()
        got, need = sq["progress"](g.flags)
        self.assertEqual(got, need, "yukseltme gorevi ilerlemiyor: %d/%d" % (got, need))


class TestRewardPayout(unittest.TestCase):
    def setUp(self):
        self.g = MOD.Game.__new__(MOD.Game)
        self.g.ui = MOD.UI()
        self.g.ps = MOD.PS()
        self.g._reset()
        self.g.temp_stats = MOD.PlayerStats("warrior")
        self.g._start_game()
        self.g.toasts = getattr(self.g, "toasts", [])

    def test_reward_is_paid_once(self):
        self.g.flags["kill_boar"] = 5
        altin = self.g.player.stats.gold
        self.g._check_side_quests()
        sonra = self.g.player.stats.gold
        self.assertGreater(sonra, altin, "gorev bitti ama odul verilmedi")
        self.g._check_side_quests()
        self.assertEqual(self.g.player.stats.gold, sonra, "odul ikinci kez verildi")

    def test_chest_counter_feeds_the_quest(self):
        self.assertEqual(self.g.flags.get("chests_opened", 0), 0)
        self.g.flags["chests_opened"] = 8
        sq = next(s for s in MOD.SIDE_QUESTS if s["id"] == "chest")
        self.assertTrue(MOD.sq_done(sq, self.g.flags), "sandik gorevi ilerlemiyor")


if __name__ == "__main__":
    unittest.main(verbosity=2)
