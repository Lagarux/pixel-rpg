#!/usr/bin/env python3
"""
Dukkan testleri: alis, satis, altin kontrolu, sinif kisiti, konaklama.

Ekonominin sessizce bozulmamasi icin: altin negatife dusmemeli, ayni
esya iki kez satilmamali, sinifina uymayan ekipman satin alinamamali.
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
    MOD = load_game_module("pixel_rpg_shop")
    pygame.init()
    pygame.display.set_mode((MOD.SW, MOD.SH))


def tearDownModule():
    pygame.quit()


class TestShop(unittest.TestCase):
    SMITH = "npc.demirci_boran"
    INN = "npc.hanci_mira"

    def setUp(self):
        g = MOD.Game.__new__(MOD.Game)
        g.state = "playing"
        g.player = MOD.Player(1, 1, MOD.PlayerStats("warrior"))
        g.shop_npc = self.SMITH
        g.shop_tab = 0
        g.shop_sel = 0
        g.shop_msg = None
        self.g = g

    # ── Fiyatlandirma ────────────────────────────────────────────
    def test_every_stocked_item_has_a_price(self):
        """Senlik tezgahi jetonla calisiyor; fiyati TOKEN_PRICES'ta."""
        for npc, sh in MOD.SHOPS.items():
            jeton = MOD.shop_currency(sh) != "gold"
            tablo = MOD.TOKEN_PRICES if jeton else MOD.ITEM_PRICES
            for item in sh["stock"]:
                with self.subTest(npc=npc, item=item):
                    self.assertIn(item, tablo)
                    self.assertGreater(tablo[item], 0)


    def test_sell_price_is_below_buy_price(self):
        """Alip satarak sonsuz para kazanilmamali."""
        for key in MOD.ITEM_PRICES:
            with self.subTest(item=key):
                self.assertLess(MOD.sell_price(key), MOD.item_price(key))

    # ── Satin alma ───────────────────────────────────────────────
    def test_buy_deducts_gold_and_gives_item(self):
        st = self.g.player.stats
        st.gold = 500
        key, price, ok = self.g._shop_rows()[0]
        self.assertTrue(ok)
        self.g._shop_confirm()
        self.assertEqual(st.gold, 500 - price)
        self.assertIn(key, self.g.player.inventory)

    def test_cannot_buy_without_gold(self):
        st = self.g.player.stats
        st.gold = 0
        before = list(self.g.player.inventory)
        self.g._shop_confirm()
        self.assertEqual(st.gold, 0, "altin negatife dustu")
        self.assertEqual(self.g.player.inventory, before, "parasiz esya alindi")
        self.assertIsNotNone(self.g.shop_msg)

    def test_cannot_buy_other_class_equipment(self):
        """Savasci buyucu asasi alamamali."""
        st = self.g.player.stats
        st.gold = 9999
        rows = self.g._shop_rows()
        idx = next(i for i, (k, _p, _o) in enumerate(rows) if k == "arcane_staff")
        self.assertFalse(rows[idx][2], "sinifa uymayan ekipman alinabilir gorunuyor")
        self.g.shop_sel = idx
        self.g._shop_confirm()
        self.assertNotIn("arcane_staff", self.g.player.inventory)
        self.assertEqual(st.gold, 9999, "basarisiz alimda altin gitti")

    # ── Satma ────────────────────────────────────────────────────
    def test_sell_removes_item_and_adds_gold(self):
        st = self.g.player.stats
        st.gold = 0
        self.g.player.inventory = ["hp_pot"]
        self.g.shop_tab = 1
        self.g.shop_sel = 0
        self.g._shop_confirm()
        self.assertEqual(self.g.player.inventory, [])
        self.assertEqual(st.gold, MOD.sell_price("hp_pot"))

    def test_cannot_sell_same_item_twice(self):
        st = self.g.player.stats
        st.gold = 0
        self.g.player.inventory = ["hp_pot"]
        self.g.shop_tab = 1
        self.g._shop_confirm()
        gold_after = st.gold
        self.g._shop_confirm()
        self.assertEqual(st.gold, gold_after, "olmayan esya tekrar satildi")

    def test_sell_list_has_no_duplicates(self):
        self.g.player.inventory = ["hp_pot", "hp_pot", "mp_pot"]
        self.g.shop_tab = 1
        keys = [k for k, _p, _o in self.g._shop_rows()]
        self.assertEqual(sorted(keys), ["hp_pot", "mp_pot"])

    # ── Konaklama ────────────────────────────────────────────────
    def test_rest_heals_for_gold(self):
        self.g.shop_npc = self.INN
        st = self.g.player.stats
        st.gold = 100
        st.hp = 5
        st.mp = 0
        self.g._shop_rest()
        self.assertEqual(st.hp, st.max_hp)
        self.assertEqual(st.mp, st.max_mp)
        self.assertEqual(st.gold, 100 - MOD.REST_PRICE)

    def test_rest_refused_without_gold(self):
        self.g.shop_npc = self.INN
        st = self.g.player.stats
        st.gold = 0
        st.hp = 5
        self.g._shop_rest()
        self.assertEqual(st.hp, 5, "parasiz iyilesildi")

    def test_smith_has_no_rest(self):
        st = self.g.player.stats
        st.gold = 100
        st.hp = 5
        self.g._shop_rest()          # demircide konaklama yok
        self.assertEqual(st.hp, 5)
        self.assertEqual(st.gold, 100)


if __name__ == "__main__":
    unittest.main(verbosity=2)
