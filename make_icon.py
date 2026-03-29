"""
Oyun ikonu oluşturucu — assets/icon.ico
PIL/Pillow yoksa pygame ile BMP oluşturur, sonra ICO'ya dönüştürür.
"""
import os, struct, sys

ASSETS_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "assets")
os.makedirs(ASSETS_DIR, exist_ok=True)
ICO_PATH = os.path.join(ASSETS_DIR, "icon.ico")

def make_ico_pillow():
    from PIL import Image, ImageDraw
    sizes = [256, 128, 64, 32, 16]
    imgs = []
    for sz in sizes:
        img = Image.new("RGBA", (sz, sz), (0, 0, 0, 0))
        d = ImageDraw.Draw(img)
        # Arka plan (koyu mor)
        d.ellipse([0, 0, sz-1, sz-1], fill=(33, 16, 52, 255))
        # Taç (altın)
        cx, cy = sz//2, sz//2
        crown_w = int(sz * 0.65)
        crown_h = int(sz * 0.40)
        tx = cx - crown_w//2
        ty = cy - crown_h//4
        d.rectangle([tx, ty, tx+crown_w, ty+crown_h], fill=(200, 155, 30, 255))
        # Taç dişleri
        tooth_w = crown_w // 5
        for i in range(3):
            dx = tx + i * (tooth_w*2) + tooth_w//2
            d.rectangle([dx, ty-int(sz*0.18), dx+tooth_w, ty+2], fill=(230, 180, 40, 255))
        # Ortadaki kristal
        r = sz // 10
        d.ellipse([cx-r, cy-r, cx+r, cy+r], fill=(140, 80, 230, 255))
        imgs.append(img)
    imgs[0].save(ICO_PATH, format="ICO", sizes=[(s,s) for s in sizes])
    return True

def make_ico_raw():
    """Pillow olmadan minimal 32x32 ICO dosyası oluştur."""
    sz = 32
    # 32x32 RGBA piksel verisi oluştur
    pixels = []
    for y in range(sz):
        row = []
        for x in range(sz):
            cx, cy = sz//2, sz//2
            dx, dy = x-cx, y-cy
            dist = (dx*dx + dy*dy) ** 0.5
            if dist < sz//2 - 1:
                # Mor arka plan
                r, g, b, a = 60, 20, 100, 255
                # Taç alanı (ortada)
                if sz//4 <= y <= sz//2+4 and sz//5 <= x <= sz-sz//5:
                    r, g, b = 200, 155, 30
                # Diş
                if y < sz//4 and (sz//4 <= x <= sz//4+4 or sz//2-2 <= x <= sz//2+2 or sz-sz//4-4 <= x <= sz-sz//4):
                    r, g, b = 220, 175, 40
                # Merkez kristal
                if dx*dx+dy*dy < 12:
                    r, g, b = 140, 80, 230
            else:
                r, g, b, a = 0, 0, 0, 0
            row.extend([b, g, r, a])  # BGRA
        pixels.extend(row)

    img_data = bytes(pixels)

    # BMP InfoHeader (BITMAPINFOHEADER)
    width, height = sz, sz
    bpp = 32
    img_size = width * height * 4  # BGRA
    info_hdr = struct.pack('<IiiHHIIiiII',
        40,         # biSize
        width,      # biWidth
        -height,    # biHeight (negative = top-down)
        1,          # biPlanes
        bpp,        # biBitCount
        0,          # biCompression (BI_RGB)
        img_size,   # biSizeImage
        0, 0, 0, 0  # resolution + colors
    )

    # ICO header (1 görüntü)
    ico_hdr = struct.pack('<HHH', 0, 1, 1)  # reserved, type=1, count=1
    img_offset = 6 + 16  # ICO header + 1 directory entry
    bmp_data = info_hdr + img_data
    dir_entry = struct.pack('<BBBBHHII',
        sz, sz,      # width, height
        0, 0,        # colorCount, reserved
        1, bpp,      # planes, bitCount
        len(bmp_data),
        img_offset
    )

    with open(ICO_PATH, 'wb') as f:
        f.write(ico_hdr + dir_entry + bmp_data)
    return True

if __name__ == "__main__":
    if os.path.exists(ICO_PATH):
        print(f"[OK] İkon zaten mevcut: {ICO_PATH}")
        sys.exit(0)

    print("İkon oluşturuluyor...")
    ok = False

    # Pillow ile dene
    try:
        import PIL
        ok = make_ico_pillow()
        print(f"[OK] Pillow ile ikon oluşturuldu: {ICO_PATH}")
    except ImportError:
        pass
    except Exception as e:
        print(f"[UYARI] Pillow hatası: {e}")

    # Pillow yoksa raw yaz
    if not ok:
        try:
            make_ico_raw()
            print(f"[OK] Ham ICO oluşturuldu: {ICO_PATH}")
            ok = True
        except Exception as e:
            print(f"[HATA] İkon oluşturulamadı: {e}")
            sys.exit(1)

    print("İkon hazır.")
