#!/usr/bin/env python3
"""
Faz 3 testleri: dovus hissi, etkilesim geri bildirimi ve arayuz katmanlari.

Bu testlerin cogu tek tek parcalari dogrudan cagirir (tum oyunu surmeden):
dusman telegrafi, yol bulma, panel karartmasi ve bolum seridi kendi
baslarina olculebilir davranislar.

Calistirmak icin: python -m unittest discover -s tests
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))  # harness'i bul

import unittest

import pygame

from harness import load_game_module

TILE_HALF = 16

MOD = None


def setUpModule():
    global MOD
    MOD = load_game_module("pixel_rpg_combat")
    pygame.init()
    pygame.display.set_mode((MOD.SW, MOD.SH))


def tearDownModule():
    pygame.quit()


def _blank_map(w=12, h=12, name="test"):
    """Tamami yurunebilir bos harita."""
    m = MOD.GameMap(w, h, name)
    for ty in range(h):
        for tx in range(w):
            m.set(tx, ty, MOD.T.FLOOR)
    return m


def fresh_game():
    """Gercek dunyayi kurulmus bir Game (pencere acmadan)."""
    import tempfile
    MOD.SAVE_FILE = os.path.join(tempfile.gettempdir(), "pixelrpg_cf_save.json")
    g = MOD.Game.__new__(MOD.Game)
    g.ui = MOD.UI()
    g.ps = MOD.PS()
    g._reset()
    return g


class TestEnemyTelegraph(unittest.TestCase):
    """E2: dusman once hazirlanmali, sonra vurmali."""

    def setUp(self):
        self.g = MOD.Game.__new__(MOD.Game)      # __init__ pencere acmasin
        g = self.g
        g.cur_map = _blank_map()
        g.maps = {"test": g.cur_map}
        g.cur_key = "test"
        g.state = "playing"
        g.ps = MOD.PS()
        g.dmg_nums = []
        g.hit_fx = []
        g.shake = 0
        g.shake_mag = 0
        g.hit_stop = 0
        g.flags = {"ch": 1}
        stats = MOD.PlayerStats("warrior")
        g.player = MOD.Player(5, 5, stats)
        self.enemy = MOD.Enemy(6, 5, "wolf", 50, 10, 10, agro=6)
        g.cur_map.enemies.append(self.enemy)

    def test_no_damage_during_windup(self):
        g = self.g
        hp0 = g.player.stats.hp
        g._update_enemies()                       # telegrafi baslatir
        self.assertGreater(self.enemy.wind_up, 0, "saldiri telegrafi baslamadi")
        for _ in range(MOD.Game.ENEMY_WINDUP - 1):
            g._update_enemies()
        self.assertEqual(g.player.stats.hp, hp0, "hazirlanma bitmeden hasar geldi")

    def test_damage_lands_after_windup(self):
        g = self.g
        hp0 = g.player.stats.hp
        for _ in range(MOD.Game.ENEMY_WINDUP + 1):
            g._update_enemies()
        self.assertLess(g.player.stats.hp, hp0, "telegraf bitince hasar gelmedi")

    def test_player_can_escape_during_windup(self):
        """Hazirlanma penceresinde uzaklasan oyuncu darbeyi yemez."""
        g = self.g
        hp0 = g.player.stats.hp
        g._update_enemies()
        g.player.snap(1, 1)                       # telegraf sirasinda kac
        for _ in range(MOD.Game.ENEMY_WINDUP + 1):
            g._update_enemies()
        self.assertEqual(g.player.stats.hp, hp0, "kacmak ise yaramadi -- telegraf anlamsiz")

    def test_enemy_does_not_move_while_winding_up(self):
        g = self.g
        g._update_enemies()
        pos = (self.enemy.tx, self.enemy.ty)
        for _ in range(MOD.Game.ENEMY_WINDUP - 1):
            g._update_enemies()
        self.assertEqual((self.enemy.tx, self.enemy.ty), pos, "hazirlanirken yer degistirdi")

    def test_hit_produces_stop_and_shake(self):
        """E3: kritik vurus kisa donma + sarsinti + geri itme uretmeli."""
        g = self.g
        before = (self.enemy.tx, self.enemy.ty)
        g._hit(self.enemy, 5, crit=True)
        self.assertGreater(g.hit_stop, 0, "vurusta kisa donma yok")
        self.assertGreater(g.shake, 0, "kritik vurusta ekran sarsintisi yok")
        self.assertNotEqual((self.enemy.tx, self.enemy.ty), before, "kritte geri itme yok")


class TestEnemyPathfinding(unittest.TestCase):
    """A5: duvar kosesinde takilmak yerine dolasmali."""

    def setUp(self):
        self.g = MOD.Game.__new__(MOD.Game)
        self.g.cur_map = _blank_map(12, 12)

    def test_walks_around_a_wall(self):
        m = self.g.cur_map
        # (5,y) sutunu duvar; sadece en asagidan dolasilabiliyor
        for ty in range(0, 9):
            m.set(5, ty, MOD.T.WALL)
        enemy = MOD.Enemy(4, 3, "wolf", 10, 1, 1)
        m.enemies.append(enemy)
        step = self.g._bfs_step(enemy, 6, 3, radius=10)
        self.assertIsNotNone(step, "yol bulunamadi")
        self.assertNotEqual(step, (5, 3), "duvarin icine adim atti")
        # Dogru cozum duvarin ucundan dolasmak: asagi inmeli
        self.assertEqual(step, (4, 4), f"duvari dolasmiyor, secilen adim: {step}")

    def test_returns_none_when_already_adjacent(self):
        enemy = MOD.Enemy(4, 4, "wolf", 10, 1, 1)
        self.g.cur_map.enemies.append(enemy)
        self.assertIsNone(self.g._bfs_step(enemy, 5, 4), "bitisikken bos adim uretti")

    def test_does_not_step_onto_another_enemy(self):
        m = self.g.cur_map
        enemy = MOD.Enemy(2, 4, "wolf", 10, 1, 1)
        blocker = MOD.Enemy(3, 4, "wolf", 10, 1, 1)
        m.enemies += [enemy, blocker]
        step = self.g._bfs_step(enemy, 6, 4)
        self.assertNotEqual(step, (3, 4), "baska dusmanin uzerine adim atti")


class TestUILayers(unittest.TestCase):
    """E4/E5: bolum duyurusu sadece ust seritte, paneller arkayi karartmali."""

    def setUp(self):
        self.ui = MOD.UI()
        self.surf = pygame.Surface((MOD.SW, MOD.SH))
        self.surf.fill((255, 255, 255))

    def test_chapter_banner_leaves_playfield_visible(self):
        self.ui.draw_chapter(self.surf, 2, 255)
        below = MOD.UI.CHAPTER_BANNER_H + 10
        self.assertEqual(
            self.surf.get_at((MOD.SW // 2, MOD.SH // 2))[:3], (255, 255, 255),
            "bolum duyurusu ekranin ortasini kapatiyor",
        )
        self.assertEqual(self.surf.get_at((10, below))[:3], (255, 255, 255))
        self.assertNotEqual(self.surf.get_at((10, 4))[:3], (255, 255, 255), "serit cizilmemis")

    def test_quest_log_dims_background(self):
        self.ui.draw_quest_log(self.surf, {"ch": 1, "sq_boar_count": 0}, 1)
        corner = self.surf.get_at((5, 5))[:3]
        self.assertLess(max(corner), 200, f"gorev gunlugu arkayi karartmiyor: {corner}")

    def test_inventory_dims_background(self):
        stats = MOD.PlayerStats("warrior")
        player = MOD.Player(1, 1, stats)
        self.ui.draw_inventory(self.surf, player, 0, 0, 0)
        corner = self.surf.get_at((5, 5))[:3]
        self.assertLess(max(corner), 200, f"envanter arkayi karartmiyor: {corner}")


class TestInteractTarget(unittest.TestCase):
    """E1: etkilesim hedefi bulunmali (rozet bunun uzerine ciziliyor)."""

    def setUp(self):
        self.g = MOD.Game.__new__(MOD.Game)
        self.g.cur_map = _blank_map()
        self.g.player = MOD.Player(5, 5, MOD.PlayerStats("warrior"))

    def _npc(self, tx, ty, name="Test NPC"):
        npc = MOD.NPC(tx, ty, name, (200, 100, 100), lambda f: ["merhaba"])
        self.g.cur_map.npcs.append(npc)
        return npc

    def test_finds_npc_in_front(self):
        npc = self._npc(5, 6)
        self.g.player.direction = "down"
        kind, obj = self.g._interact_target()
        self.assertEqual(kind, "npc")
        self.assertIs(obj, npc)

    def test_tolerates_one_tile_offset(self):
        """Yana bakiyor ama yalnizca bir aday var -> yine de bulunmali."""
        npc = self._npc(5, 6)
        self.g.player.direction = "left"
        target = self.g._interact_target()
        self.assertIsNotNone(target, "bir karelik tolerans calismiyor")
        self.assertIs(target[1], npc)

    def test_ambiguous_neighbours_need_facing(self):
        """Iki aday varsa tolerans devreye girmemeli (yanlis hedef secilmesin)."""
        self._npc(5, 6, "A")
        self._npc(4, 5, "B")
        self.g.player.direction = "up"       # (5,4) bos
        self.assertIsNone(self.g._interact_target(), "belirsizken rastgele hedef secti")

    def test_finds_chest(self):
        self.g.cur_map.chests[(6, 5)] = ["gold"]
        self.g.player.direction = "right"
        kind, obj = self.g._interact_target()
        self.assertEqual(kind, "chest")
        self.assertEqual(obj, (6, 5))

    def test_no_target_in_empty_space(self):
        self.g.player.direction = "down"
        self.assertIsNone(self.g._interact_target())


if __name__ == "__main__":
    unittest.main(verbosity=2)


class TestSideQuests(unittest.TestCase):
    """Yan gorev tablosu: ilerleme, odul ve tek seferlik odeme."""

    def setUp(self):
        self.g = MOD.Game.__new__(MOD.Game)
        g = self.g
        g.cur_map = _blank_map()
        g.maps = {"test": g.cur_map}
        g.cur_key = "test"
        g.state = "playing"
        g.ps = MOD.PS()
        g.dmg_nums = []
        g.hit_fx = []
        g.shake = g.shake_mag = g.hit_stop = 0
        g.flags = {}
        g.player = MOD.Player(5, 5, MOD.PlayerStats("warrior"))

    def test_every_quest_has_text_and_reward(self):
        for sq in MOD.SIDE_QUESTS:
            with self.subTest(quest=sq["id"]):
                self.assertTrue(MOD.T_(sq["title"]) != sq["title"], "baslik cevirisi yok")
                self.assertTrue(MOD.T_(sq["desc"]) != sq["desc"], "aciklama cevirisi yok")
                self.assertGreater(sq["gold"], 0)
                self.assertGreater(sq["xp"], 0)

    def test_progress_starts_at_zero(self):
        for sq in MOD.SIDE_QUESTS:
            got, need = sq["progress"](self.g.flags)
            with self.subTest(quest=sq["id"]):
                self.assertEqual(got, 0)
                self.assertGreater(need, 0)

    def test_kill_counter_advances_matching_quest(self):
        wolf = MOD.Enemy(6, 5, "wolf", 1, 1, 1)
        self.g.cur_map.enemies.append(wolf)
        for _ in range(5):
            self.g.flags["kill_wolf"] = self.g.flags.get("kill_wolf", 0) + 1
        sq = next(q for q in MOD.SIDE_QUESTS if q["id"] == "wolf")
        self.assertTrue(MOD.sq_done(sq, self.g.flags))

    def test_reward_is_paid_once(self):
        sq = next(q for q in MOD.SIDE_QUESTS if q["id"] == "wolf")
        self.g.flags["kill_wolf"] = 5
        gold0 = self.g.player.stats.gold
        self.g._check_side_quests()
        after = self.g.player.stats.gold
        self.assertEqual(after, gold0 + sq["gold"], "odul verilmedi")
        self.g._check_side_quests()
        self.assertEqual(self.g.player.stats.gold, after, "odul ikinci kez verildi")

    def test_killing_enemy_increments_counter(self):
        boar = MOD.Enemy(6, 5, "boar", 1, 1, 1, loot=[])
        self.g.cur_map.enemies.append(boar)
        self.g.levelup_timer = 0
        self.g._kill(boar)
        self.assertEqual(self.g.flags.get("kill_boar"), 1)


class TestQuestMarkers(unittest.TestCase):
    """I5: isi olan NPC'nin ustunde isaret gorunmeli, bitince kaybolmali."""

    def test_marker_shown_before_talking(self):
        self.assertTrue(MOD.npc_has_quest("npc.yasli_aldric", {}))

    def test_marker_disappears_after_talking(self):
        self.assertFalse(MOD.npc_has_quest("npc.yasli_aldric", {"speak_aldric": True}))

    def test_oracle_marker_waits_for_prerequisite(self):
        """Kahin, elinde kristal yokken isaret gostermemeli -- bosuna yurutmesin."""
        self.assertFalse(MOD.npc_has_quest("npc.oracle_nyx", {}))
        self.assertTrue(MOD.npc_has_quest("npc.oracle_nyx", {"earth_crystal": True}))
        self.assertFalse(MOD.npc_has_quest(
            "npc.oracle_nyx", {"earth_crystal": True, "speak_oracle": True}))

    def test_plain_npcs_have_no_marker(self):
        for key in ("npc.hanci_mira", "npc.gezgin", "npc.ciftlik_cocugu"):
            self.assertFalse(MOD.npc_has_quest(key, {}), key)

    def test_every_marked_npc_exists_in_a_map(self):
        """Isaret tablosundaki anahtarlar gercek NPC adlariyla eslesmeli."""
        names = set()
        for build in (MOD.build_ashveil, MOD.build_misty_swamp,
                      MOD.build_west_river, MOD.build_desert):
            for npc in build().npcs:
                names.add(npc.name)
        for key in MOD.NPC_MARKS:
            self.assertIn(key, names, f"{key} hicbir haritada yok")


class TestEnemyBehaviors(unittest.TestCase):
    """I8: her dusman turunun kendi davranisi olmali."""

    def _game(self):
        g = MOD.Game.__new__(MOD.Game)
        g.cur_map = _blank_map(24, 24)
        g.maps = {"test": g.cur_map}
        g.cur_key = "test"
        g.state = "playing"
        g.ps = MOD.PS()
        g.dmg_nums = []
        g.hit_fx = []
        g.projectiles = []
        g.shake = g.shake_mag = g.hit_stop = 0
        g.flags = {"ch": 1}
        g.player = MOD.Player(10, 10, MOD.PlayerStats("warrior"))
        return g

    def test_every_enemy_kind_has_a_behavior(self):
        kinds = set()
        for build in (MOD.build_ashveil, MOD.build_dark_forest, MOD.build_ruins,
                      MOD.build_desert, MOD.build_ice_cave, MOD.build_shadow_castle,
                      MOD.build_south_meadow, MOD.build_rocky_pass, MOD.build_misty_swamp):
            for e in build().enemies:
                kinds.add(e.kind)
        for k in kinds:
            with self.subTest(kind=k):
                self.assertIn(k, MOD.BEHAVIORS, f"{k} icin davranis tanimlanmamis")

    def test_ranged_enemy_fires_a_projectile(self):
        g = self._game()
        scorp = MOD.Enemy(14, 10, "scorpion", 40, 8, 10, agro=10)
        g.cur_map.enemies.append(scorp)
        for _ in range(MOD.Game.ENEMY_WINDUP + 5):
            g._update_enemies()
        self.assertTrue(g.projectiles, "menzilli dusman ates etmedi")
        self.assertEqual(g.projectiles[0].owner, "enemy")

    def test_enemy_projectile_damages_player(self):
        """Dusman mermisi oyuncuyu vurmali -- once yalnizca dusmanlara carpiyordu."""
        g = self._game()
        p = g.player
        hp0 = p.stats.hp
        pr = MOD.Projectile(float(p.px + TILE_HALF), float(p.py + TILE_HALF),
                            1.0, 0.0, 1.0, 20, "shadow_bolt", "enemy")
        g.projectiles.append(pr)
        g._update_projs()
        self.assertLess(p.stats.hp, hp0, "dusman mermisi hasar vermedi")

    def test_player_projectile_does_not_hurt_player(self):
        g = self._game()
        p = g.player
        hp0 = p.stats.hp
        pr = MOD.Projectile(float(p.px + TILE_HALF), float(p.py + TILE_HALF),
                            1.0, 0.0, 1.0, 20, "arrow", "player")
        g.projectiles.append(pr)
        g._update_projs()
        self.assertEqual(p.stats.hp, hp0, "oyuncu kendi mermisinden hasar aldi")

    def test_skittish_enemy_runs_when_wounded(self):
        g = self._game()
        gob = MOD.Enemy(12, 10, "goblin", 100, 5, 10, agro=10)
        gob.hp = 10                      # canı azaldı
        g.cur_map.enemies.append(gob)
        start = abs(gob.tx - g.player.tx)
        for _ in range(120):
            g._update_enemies()
            gob.advance_step()
        self.assertGreater(abs(gob.tx - g.player.tx), start, "urkek dusman kacmadi")

    def test_lone_pack_enemy_keeps_distance(self):
        """Yalniz kurt yanasmaya cekinmeli."""
        g = self._game()
        wolf = MOD.Enemy(13, 10, "wolf", 40, 5, 10, agro=10)
        g.cur_map.enemies.append(wolf)
        for _ in range(150):
            g._update_enemies()
            wolf.advance_step()
        self.assertGreaterEqual(max(abs(wolf.tx - 10), abs(wolf.ty - 10)), 2,
                                "yalniz kurt yine de yanasti")

    def test_wolves_in_a_pack_do_close_in(self):
        """Yaninda dostu olan kurt cesaretlenip yanasmali."""
        g = self._game()
        w1 = MOD.Enemy(13, 10, "wolf", 40, 5, 10, agro=10)
        w2 = MOD.Enemy(14, 11, "wolf", 40, 5, 10, agro=10)
        g.cur_map.enemies += [w1, w2]
        for _ in range(200):
            g._update_enemies()
            w1.advance_step(); w2.advance_step()
        closest = min(max(abs(w.tx - 10), abs(w.ty - 10)) for w in (w1, w2))
        self.assertLessEqual(closest, 1, "surudeki kurtlar yanasmadi")


class TestAggroRanges(unittest.TestCase):
    """Fark etme ve birakma mesafeleri.

    Eskiden her Enemy(...) satirinda elle yaziliyordu ve 4-7 arasinda
    dagınıktı: golem ayni haritada 4, 5, 6 ve 7 ile doguyordu. Daha kotusu
    akrep 5 kareden ates ettigi halde ancak 5-6 karede fark ediyor, mevzi
    alamadan menzile giriyordu. Artik tur bazinda ve davranisla tutarli.
    """

    def kinds(self):
        g = fresh_game()
        turler = {}
        for m in g.maps.values():
            for e in m.enemies:
                turler.setdefault(e.kind, e)
        return turler

    def test_every_kind_has_a_declared_range(self):
        for kind in self.kinds():
            self.assertIn(kind, MOD.AGGRO, "%s icin mesafe tanimlanmamis" % kind)

    def test_ranges_are_consistent_within_a_kind(self):
        """Ayni turden iki dusman farkli mesafeyle dogmamali."""
        g = fresh_game()
        gorulen = {}
        for m in g.maps.values():
            for e in m.enemies:
                onceki = gorulen.setdefault(e.kind, (e.agro_range, e.leash_range))
                self.assertEqual((e.agro_range, e.leash_range), onceki,
                                 "%s farkli mesafelerle doguyor" % e.kind)

    def test_leash_is_longer_than_aggro(self):
        """Birakma mesafesi fark etmeden kisa olursa dusman surekli
        kovalamaya baslayip biraktigi icin titrer."""
        for kind, e in self.kinds().items():
            self.assertGreater(e.leash_range, e.agro_range,
                               "%s: birakma mesafesi fark etmeden kisa" % kind)

    def test_nothing_aggros_from_off_screen(self):
        """Goremedigin bir seyin seni kovalamaya baslamasi adil degil.
        Ekranin yarisi dikeyde 10 kare."""
        yari = (MOD.SH // MOD.TILE) // 2
        for kind, e in self.kinds().items():
            if e.is_boss:
                continue          # boss odasinda zaten karsi karsiyasin
            self.assertLessEqual(e.agro_range // MOD.TILE, yari,
                                 "%s ekran disindan (%d kare) kovaliyor"
                                 % (kind, e.agro_range // MOD.TILE))

    def test_ranged_enemies_notice_before_they_can_shoot(self):
        """Menzilli dusman atis menzilinden uzakta fark etmeli, yoksa mevzi
        alamadan menzile girer ve geri cekilip durur."""
        for kind, e in self.kinds().items():
            bh = MOD.behavior(kind)
            if bh.get("type") != "ranged":
                continue
            atis = bh.get("range", 5)
            self.assertGreater(e.agro_range // MOD.TILE, atis,
                               "%s atis menzilinden (%d) once fark etmiyor" % (kind, atis))

    def test_pack_hunters_notice_earlier_than_slow_melee(self):
        """Tasarim: kurt kokuyla avlanir, balcik bir yigindir."""
        t = self.kinds()
        self.assertGreater(t["wolf"].agro_range, t["slime"].agro_range,
                           "kurt balciktan daha gec fark ediyor")

    def test_the_golem_gives_up_last(self):
        """Golem gec fark eder ama bir kez uyandi mi birakmaz."""
        t = self.kinds()
        self.assertGreaterEqual(t["golem"].leash_range,
                                max(e.leash_range for k, e in t.items() if not e.is_boss),
                                "golem en inatci kovalayan degil")
