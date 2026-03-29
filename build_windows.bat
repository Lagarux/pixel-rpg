@echo off
title Karanlik Tacin Laneti - Build Script
echo ============================================
echo  KARANLIK TAC'IN LANETI - Windows EXE Build
echo ============================================
echo.

python --version >nul 2>&1
if errorlevel 1 ( echo HATA: Python bulunamadi! & pause & exit /b 1 )

echo [1/5] Bagimliliklar yukleniyor...
pip install pygame numpy pyinstaller --quiet
if errorlevel 1 ( echo HATA: Bagimlilik hatasi! & pause & exit /b 1 )

echo [2/5] Fontlar indiriliyor (opsiyonel)...
python download_fonts.py
if errorlevel 1 echo UYARI: Fontlar indirilemedi.

echo [3/5] Ikon olusturuluyor...
python make_icon.py
if errorlevel 1 echo UYARI: Ikon olusturulamadi.

echo [4/5] EXE olusturuluyor...
pyinstaller --clean KaranlikTacinLaneti.spec
if errorlevel 1 (
    echo Spec basarisiz, dogrudan deneniyor...
    pyinstaller --onefile --windowed --name "KaranlikTacinLaneti" --hidden-import pygame --hidden-import numpy pixel_rpg.py
    if errorlevel 1 ( echo HATA: EXE olusturulamadi! & pause & exit /b 1 )
)

echo [5/5] Cikti dizini hazirlaniyor...
if not exist "dist\game" mkdir "dist\game"
if exist "dist\KaranlikTacinLaneti.exe" copy /Y "dist\KaranlikTacinLaneti.exe" "dist\game\" >nul
if exist "assets" xcopy /E /I /Y "assets" "dist\game\assets" >nul
if exist "README.txt" copy /Y "README.txt" "dist\game\" >nul

echo.
echo ============================================
echo  Build TAMAMLANDI! dist\game\ klasorune bakin.
echo ============================================
pause
