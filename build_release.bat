@echo off
title KTL Release Builder
echo ============================================================
echo  KARANLIK TAC'IN LANETI v5.0 - Tam Kurulum Paketi Olusturucu
echo ============================================================
echo.

:: Python kontrolu
python --version >nul 2>&1
if errorlevel 1 ( echo HATA: Python bulunamadi! & pause & exit /b 1 )

:: release klasoru
if not exist "release" mkdir "release"

echo [1/6] Bagimliliklar yukleniyor...
pip install pygame numpy pyinstaller --quiet
if errorlevel 1 ( echo HATA: pip basarisiz! & pause & exit /b 1 )

echo [2/6] Ikon olusturuluyor...
python make_icon.py
if errorlevel 1 echo UYARI: Ikon olusturulamadi.

echo [3/6] Fontlar indiriliyor (opsiyonel)...
python download_fonts.py
if errorlevel 1 echo UYARI: Fontlar indirilemedi.

echo [4/6] Windows EXE olusturuluyor...
pyinstaller --clean KaranlikTacinLaneti.spec
if errorlevel 1 (
    echo Spec basarisiz, dogrudan build deneniyor...
    pyinstaller --onefile --windowed --name "KaranlikTacinLaneti" ^
        --hidden-import pygame --hidden-import numpy ^
        --add-data "assets;assets" ^
        pixel_rpg.py
    if errorlevel 1 ( echo HATA: EXE olusturulamadi! & pause & exit /b 1 )
)

:: dist\game hazirla
if not exist "dist\game" mkdir "dist\game"
if exist "dist\KaranlikTacinLaneti.exe" copy /Y "dist\KaranlikTacinLaneti.exe" "dist\game\" >nul
if exist "assets" xcopy /E /I /Y "assets" "dist\game\assets" >nul
if exist "README.txt" copy /Y "README.txt" "dist\game\" >nul

echo [5/6] Windows ZIP hazirlanıyor...
powershell -Command "Compress-Archive -Force -Path 'dist\game\*' -DestinationPath 'release\KaranlikTacinLaneti-v5.0-Windows.zip'" 2>nul
if exist "release\KaranlikTacinLaneti-v5.0-Windows.zip" (
    echo [OK] ZIP: release\KaranlikTacinLaneti-v5.0-Windows.zip
) else (
    echo UYARI: ZIP olusturulamadi, dist\game klasorunu kullanin.
)

echo [6/6] NSIS Installer kontrol ediliyor...
:: NSIS yukluyse installer olustur
where makensis >nul 2>&1
if not errorlevel 1 (
    echo NSIS bulundu, installer olusturuluyor...
    makensis installer_windows.nsi
    if not errorlevel 1 echo [OK] Installer: KTL-Setup-Windows.exe
) else (
    echo UYARI: NSIS bulunamadi. https://nsis.sourceforge.io adresinden indirin.
    echo        installer_windows.nsi dosyasini NSIS ile derleyebilirsiniz.
)

echo.
echo ============================================================
echo  RELEASE DOSYALARI:
echo.
dir /b "release\" 2>nul
if not exist "release\" echo  (Hicbir release dosyasi yok)
echo.
echo  dist\game\KaranlikTacinLaneti.exe  - Dogrudan calistirilabilir
echo ============================================================
pause
