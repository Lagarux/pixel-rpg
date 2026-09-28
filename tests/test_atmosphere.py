#!/usr/bin/env python3
"""
Faz 4: atmosfer testleri — dekor, isik halesi, NPC gezinmesi, daktilo diyalog.

Calistirmak icin: python -m unittest discover -s tests
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import subprocess
import unittest

import pygame

from harness import PROJECT_DIR, SCRIPT_PATH, load_game_module

MOD = None


def setUpModule():
    global MOD
    MOD = load_game_module("pixel_rpg_atmos")
    pygame.init()
    pygame.display.set_mode((MOD.SW, MOD.SH))


def tearDownModule():
    pygame.quit()


class TestMapProps(unittest.TestCase):
    """I2: haritalar dekorla dolduruldu, ama oynanisa karismamali."""

    def setUp(self):
        self.m = MOD.build_ashveil()
        MOD._scatter_props(self.m)

    def test_props_are_actually_placed(self):
        self.assertGreater(len(self.m.props), 30, "harita hala bombos")

    def test_props_never_block_walkable_tiles(self):
        """Dekor ayri bir katman: zemin yurunebilirligini degistirmemeli."""
        for (tx, ty, _kind) in self.m.props:
            with self.subTest(pos=(tx, ty)):
                self.assertTrue(self.m.walkable(tx, ty) or self.m.get(tx, ty) not in MOD.WALKABLE)

    def test_props_avoid_npcs_chests_and_transitions(self):
        taken = {(n.tx, n.ty) for n in self.m.npcs}
        taken |= set(self.m.chests) | set(self.m.transitions)
        for (tx, ty, _k) in self.m.props:
            self.assertNotIn((tx, ty), taken, f"dekor dolu karenin ustune kondu: {(tx,ty)}")

    def test_layout_is_stable_across_processes(self):
        """Tohum kararli olmali: PYTHONHASHSEED degisse de ayni dekor cikmali.

        str.hash() surecler arasi rastgeledir; crc32 kullanilmasinin sebebi bu.
        """
        code = (
            "import os;os.environ['SDL_VIDEODRIVER']='dummy';"
            "import importlib.util;"
            f"spec=importlib.util.spec_from_file_location('m',r'{SCRIPT_PATH}');"
            "m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m);"
            "import pygame;pygame.init();"
            "mp=m.build_ashveil();m._scatter_props(mp);print(mp.props[:8])"
        )
        outs = []
        for seed in ("0", "12345"):
            env = dict(os.environ, PYTHONHASHSEED=seed, SDL_VIDEODRIVER="dummy",
                       SDL_AUDIODRIVER="dummy", PYGAME_HIDE_SUPPORT_PROMPT="1")
            r = subprocess.run([sys.executable, "-c", code], capture_output=True,
                               text=True, cwd=PROJECT_DIR, env=env)
            outs.append(r.stdout.strip().splitlines()[-1])
        self.assertEqual(outs[0], outs[1], "dekor her acilista yeniden diziliyor")


class TestLighting(unittest.TestCase):
    """I3: karanlik haritalarda oyuncunun cevresi acilmali."""

    def test_light_halo_is_brighter_at_centre(self):
        surf = pygame.Surface((MOD.SW, MOD.SH))
        surf.fill((200, 200, 200))
        MOD._draw_ambient(surf, (0, 20, 0), (MOD.SW // 2, MOD.SH // 2))
        centre = sum(surf.get_at((MOD.SW // 2, MOD.SH // 2))[:3])
        edge = sum(surf.get_at((8, 8))[:3])
        self.assertGreater(centre, edge + 60, "isik halesi yok: merkez ile kenar ayni")

    def test_light_falls_off_gradually(self):
        """Sert daire kenari olmamali: ara mesafede ara parlaklik olmali."""
        surf = pygame.Surface((MOD.SW, MOD.SH))
        surf.fill((200, 200, 200))
        cx, cy = MOD.SW // 2, MOD.SH // 2
        MOD._draw_ambient(surf, (0, 20, 0), (cx, cy))
        near = sum(surf.get_at((cx + 20, cy))[:3])
        mid = sum(surf.get_at((cx + int(MOD.LIGHT_R * 0.7), cy))[:3])
        far = sum(surf.get_at((cx + MOD.LIGHT_R + 40, cy))[:3])
        self.assertGreater(near, mid, "merkez ile orta mesafe arasinda gecis yok")
        self.assertGreater(mid, far, "hale kenari sert kesiliyor")

    def test_bright_maps_are_untouched(self):
        surf = pygame.Surface((MOD.SW, MOD.SH))
        surf.fill((200, 200, 200))
        m = MOD.GameMap(4, 4, "aydinlik")
        self.assertEqual(m.ambient, (0, 0, 0), "varsayilan harita karartmali olmamali")


class TestNpcWander(unittest.TestCase):
    """I4: NPC'ler kendi cevrelerinde dolasmali, ama uzaklasmamali."""

    def setUp(self):
        self.g = MOD.Game.__new__(MOD.Game)
        m = MOD.GameMap(20, 20, "bos")
        for ty in range(20):
            for tx in range(20):
                m.set(tx, ty, MOD.T.FLOOR)
        self.g.cur_map = m
        self.g.player = MOD.Player(1, 1, MOD.PlayerStats("warrior"))
        self.npc = MOD.NPC(10, 10, "Gezgin", (200, 100, 100), lambda f: ["selam"])
        m.npcs.append(self.npc)

    def test_npc_eventually_moves(self):
        start = (self.npc.tx, self.npc.ty)
        for _ in range(3000):
            self.g._update_npcs()
            if (self.npc.tx, self.npc.ty) != start:
                return
        self.fail("NPC 3000 karede hic kimildamadi")

    def test_npc_stays_near_home(self):
        for _ in range(6000):
            self.g._update_npcs()
            self.assertLessEqual(abs(self.npc.tx - 10), MOD.Game.NPC_WANDER_R)
            self.assertLessEqual(abs(self.npc.ty - 10), MOD.Game.NPC_WANDER_R)

    def test_npc_never_steps_on_player(self):
        self.g.player.snap(11, 10)
        for _ in range(4000):
            self.g._update_npcs()
            self.assertNotEqual((self.npc.tx, self.npc.ty), (11, 10), "NPC oyuncunun ustune bindi")


class TestTypewriterDialog(unittest.TestCase):
    """E7: diyalog harf harf akmali, E ile once tamamlanmali."""

    def setUp(self):
        self.g = MOD.Game.__new__(MOD.Game)
        self.g.dlg_lines = ["Birinci satir burada.", "Ikinci satir da var."]
        self.g.dlg_page = 0
        self.g.dlg_reveal = 0

    def test_page_length_counts_visible_characters(self):
        self.assertEqual(self.g._dlg_page_len(), sum(len(l) for l in self.g.dlg_lines))

    def test_reveal_is_gradual(self):
        total = self.g._dlg_page_len()
        self.assertLess(MOD.Game.DLG_SPEED, total, "daktilo hizi tum sayfayi tek karede aciyor")

    @staticmethod
    def _bright_pixels(surf, rect, threshold=330):
        """Bolgedeki acik renkli (metin) piksel sayisi.

        mask.from_surface burada ise yaramaz: alfasiz yuzeyde her pikseli
        dolu sayar. Metin panelden acik renkli oldugu icin esikle sayiyoruz.
        """
        n = 0
        for y in range(rect.top, rect.bottom, 2):
            for x in range(rect.left, rect.right, 2):
                if sum(surf.get_at((x, y))[:3]) > threshold:
                    n += 1
        return n

    def test_partial_reveal_draws_prefix_only(self):
        ui = MOD.UI()
        rect = pygame.Rect(14, MOD.SH - 100, 420, 90)   # diyalog metin alani
        counts = {}
        for name, rev in (("bos", 0), ("kismi", 6), ("tam", None)):
            surf = pygame.Surface((MOD.SW, MOD.SH))
            surf.fill((0, 0, 0))
            ui.draw_dialog(surf, "Test", self.g.dlg_lines, 1, 1, revealed=rev)
            counts[name] = self._bright_pixels(surf, rect)
        self.assertLess(counts["bos"], counts["kismi"], "hic harf gosterilmiyor")
        self.assertLess(counts["kismi"], counts["tam"], "daktilo yok: 6 harf ile hepsi ayni")


if __name__ == "__main__":
    unittest.main(verbosity=2)
