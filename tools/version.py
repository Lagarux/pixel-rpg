#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Oyunun surumunu yazdirir: derleme betikleri tek kaynaktan okusun.

Surum elle yazildiginda kayiyordu - oyun 6.1'deyken build_linux_release.sh
hala 5.0 uretiyordu. Betikler artik bunu cagiriyor.

    python tools/version.py     ->  6.2
"""
import io
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
KAYNAK = os.path.join(ROOT, "pixel_rpg.py")


def surum() -> str:
    metin = io.open(KAYNAK, encoding="utf-8").read()
    m = re.search(r'^VERSION\s*=\s*"([^"]+)"', metin, re.M)
    if not m:
        raise SystemExit("pixel_rpg.py icinde VERSION bulunamadi")
    return m.group(1)


if __name__ == "__main__":
    sys.stdout.write(surum())
