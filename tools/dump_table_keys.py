#!/usr/bin/env python3
"""
Veri tablolarindaki (ITEMS, QUESTS, CLASS_INFO ...) Turkce metinleri
assets/locales/tr.json'a ekler.

Bu betik pixel_rpg.py'yi DEGISTIRMEZ, sadece okur. Tablolardaki Turkce
metinler kodda yedek olarak kaliyor: ceviri dosyasi bulunamazsa oyun yine
Turkce calisiyor.
"""
import io
import json
import os

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")
os.environ.setdefault("PYGAME_HIDE_SUPPORT_PROMPT", "1")

import importlib.util

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, "assets", "locales", "tr.json")

spec = importlib.util.spec_from_file_location("pr", os.path.join(ROOT, "pixel_rpg.py"))
pr = importlib.util.module_from_spec(spec)
spec.loader.exec_module(pr)

loc = json.load(io.open(OUT, encoding="utf-8")) if os.path.exists(OUT) else {}
before = len(loc)


def put(k, v):
    loc.setdefault(k, v)


for k, row in pr.ITEMS.items():
    put(f"item.{k}.name", row[0])
    put(f"item.{k}.desc", row[4])
for k, row in pr.EQUIP_ITEMS.items():
    put(f"item.{k}.name", row[0])
for n, (title, desc) in pr.QUESTS.items():
    put(f"quest.{n}.title", title)
    put(f"quest.{n}.desc", desc)
for cls, info in pr.CLASS_INFO.items():
    for field in ("name", "desc", "lore", "atk_name", "atk_desc"):
        put(f"class.{cls}.{field}", info[field])
for cls, abilities in pr.ABILITIES.items():
    for ab in abilities:
        put(f"ability.{ab['id']}", ab["name"])
for k, name in pr.STAT_NAMES:
    put(f"stat.{k}", name)
for k, desc in pr.STAT_DESCS.items():
    put(f"stat.{k}.desc", desc)
for i, (line, _col) in enumerate(pr.STORY_LINES, 1):
    if line.strip():
        put(f"story.{i}", line)

with io.open(OUT, "w", encoding="utf-8") as f:
    json.dump(loc, f, ensure_ascii=False, indent=1, sort_keys=True)
print(f"{len(loc) - before} yeni anahtar eklendi, toplam {len(loc)}")
