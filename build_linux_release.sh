#!/bin/bash
# ============================================================
# KARANLIK TAC'IN LANETI - Linux Paket Oluşturucu
# Hem .deb (Debian/Ubuntu) hem AppImage üretir
# ============================================================
set -e

APP="karanlik-tacin-laneti"
VERSION="5.0"
ARCH="amd64"
PUBLISHER="KTL Studio"
EXE_NAME="KaranlikTacinLaneti"

echo "============================================"
echo " KARANLIK TAC'IN LANETI - Linux Release"
echo "============================================"

# ── Gereksinimler ────────────────────────────────────────────
pip3 install pygame numpy pyinstaller --quiet

# ── Icon & Font ──────────────────────────────────────────────
python3 make_icon.py  || true
python3 download_fonts.py || true

# ── EXE Build ────────────────────────────────────────────────
echo "[1/4] EXE oluşturuluyor..."
pyinstaller --clean KaranlikTacinLaneti.spec || \
pyinstaller --onefile --name "$EXE_NAME" \
    --hidden-import pygame --hidden-import numpy \
    --add-data "assets:assets" \
    pixel_rpg.py

# ── .deb Paketi ──────────────────────────────────────────────
echo "[2/4] .deb paketi hazırlanıyor..."
DEB_DIR="build/${APP}_${VERSION}_${ARCH}"
rm -rf "$DEB_DIR"
mkdir -p "$DEB_DIR/DEBIAN"
mkdir -p "$DEB_DIR/usr/games"
mkdir -p "$DEB_DIR/usr/share/applications"
mkdir -p "$DEB_DIR/usr/share/icons/hicolor/256x256/apps"
mkdir -p "$DEB_DIR/usr/share/doc/${APP}"

# Çalıştırılabilir dosya
cp "dist/${EXE_NAME}" "$DEB_DIR/usr/games/${APP}"
chmod 755 "$DEB_DIR/usr/games/${APP}"

# Assets (font, icon)
if [ -d "assets" ]; then
    mkdir -p "$DEB_DIR/usr/share/${APP}"
    cp -r assets "$DEB_DIR/usr/share/${APP}/"
fi

# Icon (PNG gerekli, ICO'dan dönüştür)
if [ -f "assets/icon.ico" ]; then
    python3 -c "
try:
    from PIL import Image
    img=Image.open('assets/icon.ico')
    img.save('assets/icon_256.png','PNG')
    print('Icon PNG oluşturuldu')
except: pass
" 2>/dev/null || true
    [ -f "assets/icon_256.png" ] && cp "assets/icon_256.png" "$DEB_DIR/usr/share/icons/hicolor/256x256/apps/${APP}.png"
fi

# README
cp README.txt "$DEB_DIR/usr/share/doc/${APP}/"

# .desktop dosyası
cat > "$DEB_DIR/usr/share/applications/${APP}.desktop" << DESKTOP
[Desktop Entry]
Type=Application
Name=Karanlik Tacin Laneti
GenericName=2D Pixel RPG
Comment=Ortacag fantezi pixel RPG oyunu
Exec=/usr/games/${APP}
Icon=${APP}
Terminal=false
Categories=Game;RolePlaying;
Keywords=rpg;pixel;fantasy;medieval;
DESKTOP

# DEBIAN/control
cat > "$DEB_DIR/DEBIAN/control" << CTRL
Package: ${APP}
Version: ${VERSION}
Section: games
Priority: optional
Architecture: ${ARCH}
Maintainer: ${PUBLISHER}
Depends: libsdl2-2.0-0 | libsdl2-2.0-0t64
Description: Karanlik Tacin Laneti - 2D Pixel RPG
 Ortacag fantezi dunyaninda bir RPG macerasi.
 6 bolum ana hikaye, yan gorevler, ekipman sistemi.
 .
 Kontroller: WASD hareket, E etkiksim, Space saldir
 1-4 yetenek, I envanter, Q gorev, F1 ayarlar
CTRL

# Paket oluştur
dpkg-deb --build "$DEB_DIR" "release/${APP}_${VERSION}_${ARCH}.deb" 2>/dev/null && \
    echo "[OK] .deb: release/${APP}_${VERSION}_${ARCH}.deb" || \
    echo "[UYARI] dpkg-deb bulunamadı, .deb atlandı"

# ── AppImage ─────────────────────────────────────────────────
echo "[3/4] AppImage hazırlanıyor..."
APPDIR="build/AppDir"
rm -rf "$APPDIR"
mkdir -p "$APPDIR/usr/bin"
mkdir -p "$APPDIR/usr/share/applications"
mkdir -p "$APPDIR/usr/share/icons/hicolor/256x256/apps"

cp "dist/${EXE_NAME}" "$APPDIR/usr/bin/${APP}"
chmod 755 "$APPDIR/usr/bin/${APP}"
[ -d "assets" ] && cp -r assets "$APPDIR/usr/share/${APP}_assets"
[ -f "assets/icon_256.png" ] && cp "assets/icon_256.png" "$APPDIR/usr/share/icons/hicolor/256x256/apps/${APP}.png"
cp "$DEB_DIR/usr/share/applications/${APP}.desktop" "$APPDIR/usr/share/applications/"

# AppRun
cat > "$APPDIR/AppRun" << APPRUN
#!/bin/bash
SELF=\$(readlink -f "\$0")
HERE=\${SELF%/*}
export PATH="\${HERE}/usr/bin:\$PATH"
exec "\${HERE}/usr/bin/${APP}" "\$@"
APPRUN
chmod 755 "$APPDIR/AppRun"
cp "$APPDIR/usr/share/icons/hicolor/256x256/apps/${APP}.png" "$APPDIR/${APP}.png" 2>/dev/null || true
cp "$APPDIR/usr/share/applications/${APP}.desktop" "$APPDIR/${APP}.desktop" 2>/dev/null || true

# appimagetool ile AppImage
mkdir -p release
if command -v appimagetool &>/dev/null; then
    appimagetool "$APPDIR" "release/${EXE_NAME}-${VERSION}-x86_64.AppImage"
    echo "[OK] AppImage: release/${EXE_NAME}-${VERSION}-x86_64.AppImage"
else
    # appimagetool'u indir
    echo "appimagetool indiriliyor..."
    curl -Lo /tmp/appimagetool "https://github.com/AppImage/AppImageKit/releases/download/continuous/appimagetool-x86_64.AppImage" 2>/dev/null || true
    chmod +x /tmp/appimagetool 2>/dev/null || true
    if [ -f /tmp/appimagetool ]; then
        ARCH=x86_64 /tmp/appimagetool "$APPDIR" "release/${EXE_NAME}-${VERSION}-x86_64.AppImage" && \
            echo "[OK] AppImage oluşturuldu" || \
            echo "[UYARI] AppImage oluşturulamadı"
    else
        # appimagetool yoksa basit tar.gz
        echo "[UYARI] appimagetool bulunamadı, tar.gz oluşturuluyor..."
        tar -czf "release/${EXE_NAME}-${VERSION}-linux.tar.gz" -C "dist" "${EXE_NAME}" \
            -C ".." assets README.txt 2>/dev/null && \
            echo "[OK] tar.gz: release/${EXE_NAME}-${VERSION}-linux.tar.gz"
    fi
fi

# ── Sonuç ────────────────────────────────────────────────────
echo ""
echo "[4/4] Release dosyaları:"
ls -lh release/ 2>/dev/null || echo "(Henüz oluşturulmadı)"
echo ""
echo "============================================"
echo " Linux Release TAMAMLANDI!"
echo "============================================"
