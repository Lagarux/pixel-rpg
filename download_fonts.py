"""
Font indirici — Google Fonts (ucretsiz, OFL lisansli)
Fantasy / Orta Cag temali fontlar: Cinzel, MedievalSharp, Almendra
"""
import os, sys, urllib.request, zipfile, io, shutil, json, re

FONTS_DIR = os.path.join("assets", "fonts")
os.makedirs(FONTS_DIR, exist_ok=True)

FONT_FAMILIES = ["Cinzel", "MedievalSharp", "Almendra"]

def download_via_api(family_name):
    api_url = f"https://fonts.googleapis.com/css2?family={family_name.replace(' ', '+')}:wght@400;700&display=swap"
    headers = {"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36"}
    try:
        req = urllib.request.Request(api_url, headers=headers)
        with urllib.request.urlopen(req, timeout=15) as r:
            css = r.read().decode('utf-8')
        urls = re.findall(r'url\((https://fonts\.gstatic\.com/[^)]+\.ttf)\)', css)
        if not urls:
            return False
        downloaded = 0
        for url in urls:
            fname = url.split('/')[-1]
            dest = os.path.join(FONTS_DIR, f"{family_name.replace(' ','')}-{fname}")
            if os.path.exists(dest):
                print(f"  [OK] {fname} zaten var."); downloaded += 1; continue
            print(f"  Indiriliyor: {fname}...")
            req2 = urllib.request.Request(url, headers=headers)
            with urllib.request.urlopen(req2, timeout=15) as r2:
                data = r2.read()
            with open(dest, 'wb') as f:
                f.write(data)
            print(f"  [OK] {fname} ({len(data)//1024} KB)")
            downloaded += 1
        simple = os.path.join(FONTS_DIR, f"{family_name.replace(' ','')}-Regular.ttf")
        if not os.path.exists(simple):
            for fn in os.listdir(FONTS_DIR):
                if family_name.replace(' ','') in fn and fn.endswith('.ttf'):
                    shutil.copy(os.path.join(FONTS_DIR, fn), simple); break
        return downloaded > 0
    except Exception as e:
        print(f"  [HATA] {family_name}: {e}"); return False

if __name__ == "__main__":
    print("="*50)
    print("Font Indirme Basliyor")
    print(f"Hedef: {os.path.abspath(FONTS_DIR)}")
    print("="*50)
    existing = [f for f in os.listdir(FONTS_DIR) if f.endswith('.ttf')]
    if existing:
        print(f"\n[OK] {len(existing)} font zaten mevcut:")
        for f in existing: print(f"  - {f}")
        sys.exit(0)
    ok = False
    for family in FONT_FAMILIES:
        print(f"\n  {family}:")
        if download_via_api(family): ok = True
    if not ok:
        print("\nInternet baglantisi yok veya fontlar indirilemedi.")
        print("Sistem fontu kullanilacak - oyun yine de calisir.")
        sys.exit(0)
    existing = [f for f in os.listdir(FONTS_DIR) if f.endswith('.ttf')]
    print(f"\nTamamlandi: {len(existing)} font hazir.")
