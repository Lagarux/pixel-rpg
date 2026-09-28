#!/usr/bin/env python3
"""
pixel_rpg.py icindeki DIYALOG ve AD metinlerini anahtarlara cevirir.

Neden betik? 99 diyalog satirini elle tasimak hem yazim hatasi hem de
kodlama bozulmasi riski tasiyordu (konsol cp1254'te Turkce karakterleri
bozuyor). Veri tablolari (ITEMS, QUESTS, CLASS_INFO ...) kucuk oldugu icin
onlar elle duzenlendi -- ilk denemede genel regex o tablolari bozmustu.

Uretilen: assets/locales/tr.json (anahtar -> Turkce metin)
Bir kez calistirilmak uzere; tekrar calistirilirsa metinler zaten anahtar
oldugu icin yeni bir sey bulmaz.
"""
import ast
import io
import json
import os
import re

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
SRC = os.path.join(ROOT, "pixel_rpg.py")
OUT = os.path.join(ROOT, "assets", "locales", "tr.json")

loc = {}


def put(key, text):
    if key in loc and loc[key] != text:
        raise SystemExit(f"anahtar cakismasi: {key}: {loc[key]!r} != {text!r}")
    loc[key] = text
    return key


def slug(text):
    t = text.translate(str.maketrans("çğıöşüÇĞİÖŞÜ", "cgiosuCGIOSU")).lower()
    return re.sub(r"[^a-z0-9]+", "_", t).strip("_")


def main():
    s = io.open(SRC, encoding="utf-8").read()

    # ── Diyaloglar ──────────────────────────────────────────────
    def dialog_body(m):
        head, body = m.group(1), m.group(2)
        name = re.match(r"\s*def (\w+)_d\(f\)", head).group(1)
        n = [0]

        def repl(sm):
            text = sm.group(1)
            # Bayrak adlarini (f.get("water_crystal") gibi) ceviriye alma:
            # goruntulenen metinde mutlaka bosluk ya da buyuk harf olur.
            if len(text) < 3 or text.startswith("dlg."):
                return sm.group(0)
            if re.fullmatch(r"[a-z_0-9]+", text):
                return sm.group(0)
            if sm.string[max(0, sm.start() - 5):sm.start()].endswith(".get("):
                return sm.group(0)
            n[0] += 1
            return '"%s"' % put("dlg.%s.%d" % (name, n[0]), text)

        return head + re.sub(r'"([^"]*)"', repl, body)

    s = re.sub(r"(\s*def \w+_d\(f\):)(.*?)"
               r"(?=\n    [a-zA-Z_]+ *=|\n    m\.|\n    _snap_all|\n    for |\ndef |\Z)",
               dialog_body, s, flags=re.S)

    # ── NPC adlari ──────────────────────────────────────────────
    def npc_repl(m):
        name = m.group(2)
        if name.startswith("npc."):
            return m.group(0)
        return m.group(1) + '"%s"' % put("npc." + slug(name), name) + m.group(3)

    s = re.sub(r'(NPC\(\s*\d+\s*,\s*\d+\s*,\s*)"([^"]+)"(\s*,)', npc_repl, s)

    # ── Harita adlari ───────────────────────────────────────────
    def map_repl(m):
        name = m.group(2)
        if name.startswith("map."):
            return m.group(0)
        return m.group(1) + '"%s"' % put("map." + slug(name), name) + m.group(3)

    s = re.sub(r'(GameMap\(\s*\d+\s*,\s*\d+\s*,\s*)"([^"]+)"(\s*[,)])', map_repl, s)

    # Yazmadan once sozdizimi dogrula -- bozuk dosya diske gitmesin
    ast.parse(s)

    os.makedirs(os.path.dirname(OUT), exist_ok=True)
    existing = {}
    if os.path.exists(OUT):
        existing = json.load(io.open(OUT, encoding="utf-8"))
    existing.update(loc)
    with io.open(OUT, "w", encoding="utf-8") as f:
        json.dump(existing, f, ensure_ascii=False, indent=1, sort_keys=True)
    io.open(SRC, "w", encoding="utf-8").write(s)
    print("%d metin cikarildi -> %s" % (len(loc), os.path.relpath(OUT, ROOT)))
    for pref in ("dlg.", "npc.", "map."):
        print("   %-6s %d" % (pref, sum(1 for k in loc if k.startswith(pref))))


if __name__ == "__main__":
    main()
