#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Tum sprite'lari tek tabloda buyutup kaydeder -- cizim degisikliklerini
goz ile denetlemek icin. Cikti: tests/screenshots/_sprite_tablosu.png
"""
import os
import sys

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")
os.environ.setdefault("PYGAME_HIDE_SUPPORT_PROMPT", "1")

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "tests"))

import pygame
from harness import load_game_module

mod = load_game_module("pixel_rpg_sheet")
pygame.init()
pygame.display.set_mode((64, 64))
PA, TILE = mod.PA, mod.TILE

ENEMIES = ["slime", "skeleton", "goblin", "wolf", "boar", "golem",
           "scorpion", "ice_wolf", "shadow_knight"]
CLASSES = ["warrior", "mage", "archer", "healer"]
NPC_STYLES = ["default", "guard", "knight", "elder", "oracle", "farmer",
              "smith", "inn", "fisher", "hermit", "scholar", "child", "traveler", "spirit"]

Z = 3
CELL = TILE * Z + 8
COLS = max(len(ENEMIES), len(NPC_STYLES), len(CLASSES) * 2)
rows = 4
out = pygame.Surface((COLS * CELL + 12, rows * (CELL + 18) + 10))
out.fill((38, 56, 38))
font = pygame.font.SysFont("consolas", 12, bold=True)


def row(y, label, items, fn):
    out.blit(font.render(label, True, (255, 255, 255)), (6, y))
    for i, it in enumerate(items):
        sp = fn(it)
        out.blit(pygame.transform.scale(sp, (sp.get_width() * Z, sp.get_height() * Z)),
                 (8 + i * CELL, y + 16))


y = 6
row(y, "Siniflar (durus / yuruyus)",
    [(c, f) for c in CLASSES for f in (0, 16)],
    lambda cf: PA.player_surf("down", cf[1], cf[0]))
y += CELL + 18
row(y, "NPC meslekleri", NPC_STYLES,
    lambda st: PA.npc_surf((150, 120, 190), 0, st))
y += CELL + 18
row(y, "Dusmanlar (durus)", ENEMIES, lambda k: PA.enemy_surf(k, 0))
y += CELL + 18
row(y, "Dusmanlar (yuruyus)", ENEMIES, lambda k: PA.enemy_surf(k, 16))

dest = os.path.join(ROOT, "tests", "screenshots", "_sprite_tablosu.png")
os.makedirs(os.path.dirname(dest), exist_ok=True)
pygame.image.save(out, dest)
print("kaydedildi:", dest, out.get_size())
