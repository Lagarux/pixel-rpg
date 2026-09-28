#!/usr/bin/env python3
"""
Oyunu otomatik "oynatan" test kosum takimi.

pixel_rpg.py tek bir sonsuz dongu (Game.run) uzerine kurulu oldugu icin,
testten surmenin en temiz yolu dongunun kalp atisini -- pygame.display.flip --
kancalamaktir. Her karede:
  * senaryodaki bir sonraki komut uygulanir (tus gonder, tus basili tut,
    ekran goruntusu al, oyun durumunu degistir),
  * istenirse olcum (oyuncu konumu, kamera, SysFont cagri sayisi) toplanir.

Senaryo bitince _Done firlatilir ve Game.run temiz sekilde terk edilir;
boylece pygame.quit()/sys.exit() calismaz ve test surecine dokunmaz.

Video/ses surucusu "dummy" secildigi icin pencere acilmaz, ses karti gerekmez;
ancak cizim gercekten yapilir, dolayisiyla ekran goruntuleri gercek karelerdir.
"""
import os

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")
os.environ.setdefault("PYGAME_HIDE_SUPPORT_PROMPT", "1")

import importlib.util
import sys
import time

import pygame

PROJECT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SCRIPT_PATH = os.path.join(PROJECT_DIR, "pixel_rpg.py")
SHOT_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "screenshots")


class _Done(Exception):
    """Senaryo bitti -- oyun dongusunden cikmak icin."""


class _FakeClock:
    """FPS sinirlamasini kaldirir: ham mantik+cizim maliyetini olcmek icin."""

    def tick(self, *a, **k):
        return 0

    def get_fps(self):
        return 0.0


class _FakeKeys:
    """pygame.key.get_pressed() yerine: basili tutulan tuslari taklit eder."""

    def __init__(self, held):
        self._held = held

    def __getitem__(self, key):
        return key in self._held


def load_game_module(name="pixel_rpg_under_test"):
    """pixel_rpg.py'yi bagimsiz bir modul olarak yukler (proje dizininden)."""
    old_cwd = os.getcwd()
    os.chdir(PROJECT_DIR)
    try:
        spec = importlib.util.spec_from_file_location(name, SCRIPT_PATH)
        module = importlib.util.module_from_spec(spec)
        sys.modules[name] = module
        spec.loader.exec_module(module)
        return module
    finally:
        os.chdir(old_cwd)


class Harness:
    """Bir Game ornegini senaryoya gore surer ve olcum toplar."""

    def __init__(self, module, shot_dir=SHOT_DIR, shot_prefix=""):
        self.mod = module
        self.shot_dir = shot_dir
        self.shot_prefix = shot_prefix
        os.makedirs(shot_dir, exist_ok=True)

        # Kullanicinin settings.json'ina dokunmayalim.
        module.CFG.data["fullscreen"] = False
        module.CFG.save = lambda *a, **k: None

        self.game = None
        self.shots = []
        self.errors = []
        self.frames = 0
        self.held = set()
        # Olcumler
        self.pos_trace = []        # (frame, px, py, cam_x, cam_y)
        self.frame_times = []      # kareler arasi gecen sure (ms)
        self.sysfont_calls = []    # kare basina pygame.font.SysFont cagrisi
        self._sysfont_n = 0
        self._unlimited_fps = False

    # ── Senaryo komutlari ────────────────────────────────────────
    @staticmethod
    def key(k, wait=3):
        return ("key", k, wait)

    @staticmethod
    def hold(keys, frames):
        return ("hold", tuple(keys), frames)

    @staticmethod
    def release():
        return ("release",)

    @staticmethod
    def wait(frames):
        return ("wait", frames)

    @staticmethod
    def shot(name):
        return ("shot", name)

    @staticmethod
    def do(fn):
        return ("do", fn)

    # ── Kosum ────────────────────────────────────────────────────
    def run(self, script, unlimited_fps=False, trace=False):
        """Senaryoyu calistirir. unlimited_fps: clock.tick devre disi (perf olcumu)."""
        pg_flip = pygame.display.flip
        pg_pressed = pygame.key.get_pressed
        pg_sysfont = pygame.font.SysFont
        self._unlimited_fps = unlimited_fps

        def counting_sysfont(*a, **k):
            self._sysfont_n += 1
            return pg_sysfont(*a, **k)

        cursor = {"i": 0, "wait": 0}
        last = [time.perf_counter()]

        def flip():
            pg_flip()
            now = time.perf_counter()
            self.frame_times.append((now - last[0]) * 1000.0)
            last[0] = now
            self.frames += 1
            self.sysfont_calls.append(self._sysfont_n)
            self._sysfont_n = 0
            g = self.game
            if trace and g.state == "playing" and g.player:
                self.pos_trace.append((self.frames, g.player.px, g.player.py, g.cam_x, g.cam_y))

            while True:
                if cursor["wait"] > 0:
                    cursor["wait"] -= 1
                    return
                if cursor["i"] >= len(script):
                    raise _Done
                cmd = script[cursor["i"]]
                cursor["i"] += 1
                self._apply(cmd, cursor)

        pygame.display.flip = flip
        pygame.key.get_pressed = lambda: _FakeKeys(self.held)
        pygame.font.SysFont = counting_sysfont
        try:
            self.game = self.mod.Game()
            if unlimited_fps:
                self.game.clock = _FakeClock()
            self.game.run()
        except _Done:
            pass
        except SystemExit:
            pass
        finally:
            pygame.display.flip = pg_flip
            pygame.key.get_pressed = pg_pressed
            pygame.font.SysFont = pg_sysfont
        return self

    def _apply(self, cmd, cursor):
        kind = cmd[0]
        if kind == "key":
            pygame.event.post(pygame.event.Event(pygame.KEYDOWN, key=cmd[1], mod=0, unicode=""))
            cursor["wait"] = cmd[2]
        elif kind == "hold":
            self.held = set(cmd[1])
            cursor["wait"] = cmd[2]
        elif kind == "release":
            self.held = set()
        elif kind == "wait":
            cursor["wait"] = cmd[1]
        elif kind == "shot":
            name = f"{self.shot_prefix}{cmd[1]}.png"
            path = os.path.join(self.shot_dir, name)
            pygame.image.save(self.game.screen, path)
            self.shots.append(path)
        elif kind == "do":
            try:
                cmd[1](self.game)
            except Exception as exc:  # senaryo yardimcisi patlarsa testi bilgilendir
                self.errors.append(f"{cmd[1].__name__}: {exc!r}")
        else:
            raise AssertionError(f"bilinmeyen komut: {cmd!r}")


# ── Senaryo yardimcilari ────────────────────────────────────────
def walkable_neighbor(game, tx, ty):
    """(tx,ty) komsusunda yurunebilir bir kare ve oraya bakan yon dondurur."""
    for (dx, dy, facing) in ((0, 1, "up"), (0, -1, "down"), (1, 0, "left"), (-1, 0, "right")):
        if game.cur_map.walkable(tx + dx, ty + dy):
            return tx + dx, ty + dy, facing
    return None


def place_player(game, tx, ty, facing):
    tile = sys.modules[type(game).__module__].TILE
    p = game.player
    p.tx, p.ty = tx, ty
    p.px, p.py = tx * tile, ty * tile
    p.direction = facing


def face_first_npc(game):
    npc = game.cur_map.npcs[0]
    spot = walkable_neighbor(game, npc.tx, npc.ty)
    assert spot, "NPC'nin yaninda yurunebilir kare yok"
    place_player(game, spot[0], spot[1], spot[2])


def face_first_chest(game):
    (cx, cy) = next(iter(game.cur_map.chests))
    spot = walkable_neighbor(game, cx, cy)
    assert spot, "sandigin yaninda yurunebilir kare yok"
    place_player(game, spot[0], spot[1], spot[2])


def goto_map(key):
    def _go(game):
        game.cur_key = key
        game.cur_map = game.maps[key]
    _go.__name__ = f"goto_map_{key}"
    return _go


def face_first_enemy(game):
    enemy = next(e for e in game.cur_map.enemies if e.alive and not e.is_boss)
    spot = walkable_neighbor(game, enemy.tx, enemy.ty)
    assert spot, "dusmanin yaninda yurunebilir kare yok"
    place_player(game, spot[0], spot[1], spot[2])
    game.player.stats.hp = game.player.stats.max_hp
