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
OLDURME_GOREVI = {
    "boar": "boar", "wolf": "wolf", "bone": "skeleton", "golem": "golem",
    "slime": "slime", "goblin": "goblin", "scorpion": "scorpion",
    "icewolf": "ice_wolf", "knight": "shadow_knight",
}


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
