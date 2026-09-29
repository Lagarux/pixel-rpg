#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Envanter ve ekipman testleri.

Neden var: envanterde E'ye basmak oyunu cokertiyordu (T_ yerine fT_ yazilmis
bir isim) ve sinifina uymayan bir ekipmani giymeye calismak esyayi YOK EDIP
yerine hata metnini esya olarak envantere koyuyordu. Iki hatanin da ortak
noktasi, hicbir testin "her esyayi kullan" yolunu gecmemesiydi.

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


def setUpModule():
    global MOD, TMP
    MOD = load_game_module("pixel_rpg_inv")
    TMP = tempfile.mkdtemp(prefix="pixelrpg_inv_")
    MOD.SAVE_FILE = os.path.join(TMP, "save1.json")   # kullanicinin kaydina dokunma
    pygame.init()
    pygame.display.set_mode((MOD.SW, MOD.SH))


def tearDownModule():
    pygame.quit()
    shutil.rmtree(TMP, ignore_errors=True)


def _game(char_class="mage"):
    g = MOD.Game.__new__(MOD.Game)
    g.ui = MOD.UI()
    g.ps = MOD.PS()
    g._reset()
    g.temp_stats = MOD.PlayerStats(char_class)
    g._start_game()
    return g


def _use(g, items, sel=0):
    """Envanteri kur, sel'i sec, E'ye bas. (envanter, ekrana cikan yazilar)"""
    g.player.inventory = list(items)
    g.inv_sel = sel
    g.dmg_nums = []
    g._inv_use_item()
    return g.player.inventory, [d["txt"] for d in g.dmg_nums]


class TestUsingEveryItem(unittest.TestCase):
    """Envanterdeki HER esya icin E yolunu gec -- cokme birakma."""

    def test_every_item_is_usable_by_every_class(self):
        for cc in ("warrior", "mage", "archer", "healer"):
            g = _game(cc)
            for ik in MOD.ALL_ITEMS:
                with self.subTest(sinif=cc, esya=ik):
                    try:
                        _use(g, [ik])
                    except Exception as e:
                        self.fail("%s sinifi '%s' esyasini kullanirken coktu: %r" % (cc, ik, e))

    def test_no_bogus_entries_enter_inventory(self):
        """Envantere ALL_ITEMS'ta olmayan bir sey girmemeli."""
        for cc in ("warrior", "mage"):
            g = _game(cc)
            for ik in MOD.ALL_ITEMS:
                inv, _ = _use(g, [ik])
                bogus = [i for i in inv if i not in MOD.ALL_ITEMS]
                self.assertEqual(bogus, [], "%s: '%s' kullanilinca envantere sahte esya girdi: %s"
                                            % (cc, ik, bogus))

    def test_messages_are_translated_not_raw_keys(self):
        """Ekranda 'ui.equipped_msg' gibi ham anahtar gorunmemeli."""
        g = _game("mage")
        for ik in MOD.ALL_ITEMS:
            _, msgs = _use(g, [ik])
            for m in msgs:
                self.assertFalse(m.startswith("ui.") or m.startswith("dlg."),
                                 "'%s' icin cevrilmemis anahtar ekrana ciktu: %s" % (ik, m))
                self.assertTrue(m.strip(), "'%s' icin bos mesaj" % ik)

    def test_empty_inventory_is_safe(self):
        g = _game()
        g.player.inventory = []
        g.inv_sel = 0
        g._inv_use_item()          # patlamamali

    def test_selection_past_end_is_safe(self):
        g = _game()
        g.player.inventory = ["hp_pot"]
        g.inv_sel = 7
        g._inv_use_item()          # patlamamali


class TestEquipSlots(unittest.TestCase):
    def setUp(self):
        self.g = _game("mage")
        self.p = self.g.player
        self.p.stats.equipment = {s: None for s in MOD.EQUIP_SLOTS}

    def test_five_slots_are_independent(self):
        """Kullanicinin bildirdigi hata: mana tasi takinca hiz botu cikiyordu."""
        wear = {"weapon": "arcane_staff", "armor": "mage_robe", "boots": "swift_boots",
                "ring": "mage_focus", "amulet": "mana_gem"}
        for ik in wear.values():
            _use(self.g, [ik])
        self.assertEqual(self.p.stats.equipment, wear,
                         "bir yuvayi doldurmak digerini bosaltti")

    def test_incompatible_item_is_not_destroyed(self):
        """Buyucu plaka zirh giyemez; zirh envanterde KALMALI."""
        inv, msgs = _use(self.g, ["plate_mail"])
        self.assertEqual(inv, ["plate_mail"], "giyilemeyen ekipman envanterden silindi")
        self.assertIsNone(self.p.stats.equipment["armor"], "uymayan ekipman yine de giyildi")
        self.assertTrue(msgs, "neden gosterilmedi")

    def test_incompatible_item_reason_is_readable(self):
        _, msgs = _use(self.g, ["plate_mail"])
        self.assertEqual(msgs[0], MOD.T_("ui.shop_wrong_class"))
        self.assertNotIn("mage", msgs[0], "ic sinif adi oyuncuya gosteriliyor")

    def test_swap_returns_old_item_to_inventory(self):
        _use(self.g, ["arcane_staff"])
        self.assertEqual(self.p.stats.equipment["weapon"], "arcane_staff")
        inv, _ = _use(self.g, ["elder_staff"])
        self.assertEqual(self.p.stats.equipment["weapon"], "elder_staff")
        self.assertEqual(inv, ["arcane_staff"], "yuvadan cikan esya envantere donmedi")

    def test_reequipping_same_item_removes_it_without_loss(self):
        """Takili esyayi tekrar secmek onu cikarmali ve esya kaybolmamali."""
        self.p.stats.equipment["ring"] = "power_ring"
        inv, msgs = _use(self.g, ["power_ring"])
        self.assertIsNone(self.p.stats.equipment["ring"], "esya cikarilmadi")
        self.assertEqual(inv.count("power_ring"), 2,
                         "cikarilan esya envantere eklenmedi -- esya kayboldu")

    def test_equip_bonus_reaches_stats(self):
        base = self.p.stats.max_hp
        _use(self.g, ["mage_robe"])       # vit yok, wis/int var -> max_mp artmali
        self.assertGreaterEqual(self.p.stats.max_hp, base)
        self.assertEqual(self.p.stats.equipment["armor"], "mage_robe")

    def test_equip_reason_is_a_locale_key(self):
        """Neden, oyuncuya gosterilecek metin degil; ceviri anahtari olmali."""
        r = self.p.stats.equip_reason("plate_mail")
        self.assertTrue(r and r.startswith("ui."), "neden ceviri anahtari degil: %r" % r)
        self.assertIsNone(self.p.stats.equip_reason("mage_robe"))
        self.assertIsNone(self.p.stats.equip_reason("swift_boots"),
                          "sinif kisiti olmayan esya reddedildi")

    def test_equip_reason_translated_in_every_language(self):
        eski = MOD.CFG.data.get("language", "TR")
        try:
            for code in MOD.LANG_CODES:
                MOD.CFG.data["language"] = code
                txt = MOD.T_("ui.shop_wrong_class")
                self.assertTrue(txt.strip(), "%s: bos ceviri" % code)
                self.assertFalse(txt.startswith("ui."), "%s: cevrilmemis" % code)
        finally:
            MOD.CFG.data["language"] = eski


if __name__ == "__main__":
    unittest.main(verbosity=2)
