#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Masaustu / gorev cubugu ikonunu oyunun amblemi'nden uretir.

Oyunun IKI logosu var:
  * oyun ici amblem  -> PA.logo(), acilis animasyonunda ve baslik ekraninda
  * uygulama ikonu   -> bu betigin urettigi assets/icon.ico

Ikisi ayni tasarim dilini paylasiyor ama ikon kucuk boyda okunsun diye
sadelestirilmis cizimi (PA.logo(sade=True)) kullaniyor ve kare bir zemine
oturtuluyor.

Pillow gerekmiyor: ICO dosyasi PNG gomulu olarak elle yaziliyor
(Vista+ bicimi, Windows 10/11 destekliyor).

Calistirmak icin:  python tools/make_logo_icon.py
"""
import os
import struct
import sys
import tempfile

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")
os.environ.setdefault("PYGAME_HIDE_SUPPORT_PROMPT", "1")

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, os.path.join(ROOT, "tests"))

import pygame
from harness import load_game_module

BOYUTLAR = [256, 128, 64, 48, 32, 16]
SADE_ESIK = 32          # bu boyut ve altinda sadelestirilmis cizim
ASSETS = os.path.join(ROOT, "assets")


def ikon_karesi(PA, boy):
    """Amblemi kare bir zemine oturtur."""
    sade = boy <= SADE_ESIK
    s = pygame.Surface((256, 256), pygame.SRCALPHA)

    # Zemin: koyu mor yuvarlak kare + hafif hale
    pygame.draw.rect(s, (26, 18, 38), (0, 0, 256, 256), border_radius=46)
    pygame.draw.rect(s, (58, 38, 86), (0, 0, 256, 256), 6, border_radius=46)
    hale = pygame.Surface((256, 256), pygame.SRCALPHA)
    for r in range(9, 0, -1):
        pygame.draw.ellipse(hale, (120, 60, 180, 10),
                            (128 - r * 12, 128 - r * 9, r * 24, r * 18))
    s.blit(hale, (0, 0))

    # Amblem: kareye yayilsin
    lg = PA.logo(0.0 if sade else 1.0, sade=sade)
    lw, lh = lg.get_size()
    hedef_w = 210 if not sade else 230
    k = hedef_w / float(lw)
    big = pygame.transform.scale(lg, (int(lw * k), int(lh * k)))
    s.blit(big, (128 - big.get_width() // 2, 132 - big.get_height() // 2))

    if boy == 256:
        return s
    # Kucultme: pikselli kalsin diye once tam katina, sonra yumusak
    return pygame.transform.smoothscale(s, (boy, boy))


def png_bayt(surf):
    with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as f:
        yol = f.name
    try:
        pygame.image.save(surf, yol)
        with open(yol, "rb") as f:
            return f.read()
    finally:
        try:
            os.remove(yol)
        except OSError:
            pass


def ico_yaz(yol, kareler):
    """kareler: [(boy, png_baytlari), ...] -> ICO dosyasi."""
    n = len(kareler)
    basliklar = b""
    govde = b""
    ofset = 6 + 16 * n
    for boy, veri in kareler:
        w = h = 0 if boy >= 256 else boy
        basliklar += struct.pack("<BBBBHHII", w, h, 0, 0, 1, 32, len(veri), ofset)
        govde += veri
        ofset += len(veri)
    with open(yol, "wb") as f:
        f.write(struct.pack("<HHH", 0, 1, n))
        f.write(basliklar)
        f.write(govde)


def main():
    mod = load_game_module("pixel_rpg_icon")
    pygame.init()
    pygame.display.set_mode((64, 64))
    PA = mod.PA

    # Eski ikonu bir kereye mahsus sakla
    eski = os.path.join(ASSETS, "icon.ico")
    yedek = os.path.join(ASSETS, "icon_onceki.ico")
    if os.path.isfile(eski) and not os.path.isfile(yedek):
        with open(eski, "rb") as a, open(yedek, "wb") as b:
            b.write(a.read())
        print("eski ikon saklandi:", os.path.relpath(yedek, ROOT))

    kareler = []
    for boy in BOYUTLAR:
        yuz = ikon_karesi(PA, boy)
        kareler.append((boy, png_bayt(yuz)))
        print("  %3dpx%s" % (boy, "  (sade)" if boy <= SADE_ESIK else ""))

    ico_yaz(eski, kareler)
    print("yazildi:", os.path.relpath(eski, ROOT),
          "(%d boyut, %d bayt)" % (len(kareler), os.path.getsize(eski)))

    # Oyun ici / README icin PNG
    png256 = ikon_karesi(PA, 256)
    pygame.image.save(png256, os.path.join(ASSETS, "icon256.png"))
    pygame.image.save(pygame.transform.smoothscale(png256, (64, 64)),
                      os.path.join(ASSETS, "icon64.png"))
    print("yazildi: assets/icon256.png, assets/icon64.png")


if __name__ == "__main__":
    main()
