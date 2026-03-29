; ============================================================
; KARANLIK TAC'IN LANETI - Windows NSIS Installer Script
; pip install pyinstaller, sonra EXE oluştur, sonra bu çalıştır
; NSIS: https://nsis.sourceforge.io (ücretsiz)
; ============================================================

!define APP_NAME "Karanlik Tacin Laneti"
!define APP_VERSION "5.0"
!define APP_PUBLISHER "KTL Studio"
!define APP_EXE "KaranlikTacinLaneti.exe"
!define INSTALL_DIR "$PROGRAMFILES\${APP_NAME}"

Name "${APP_NAME} v${APP_VERSION}"
OutFile "KTL-Setup-Windows.exe"
InstallDir "${INSTALL_DIR}"
InstallDirRegKey HKLM "Software\${APP_NAME}" "Install_Dir"
RequestExecutionLevel admin
SetCompressor lzma

; Modern UI
!include "MUI2.nsh"
!define MUI_ABORTWARNING
!define MUI_ICON "assets\icon.ico"
!define MUI_UNICON "assets\icon.ico"
!define MUI_WELCOMEPAGE_TITLE "Karanlik Tac'in Laneti Kurulumu"
!define MUI_WELCOMEPAGE_TEXT "Kurulum sihirbazina hos geldiniz!$\r$\n$\r$\nGereksinimler: Windows 7+$\r$\nDisk alani: ~50 MB"

!insertmacro MUI_PAGE_WELCOME
!insertmacro MUI_PAGE_LICENSE "README.txt"
!insertmacro MUI_PAGE_DIRECTORY
!insertmacro MUI_PAGE_INSTFILES
!insertmacro MUI_PAGE_FINISH
!insertmacro MUI_UNPAGE_CONFIRM
!insertmacro MUI_UNPAGE_INSTFILES
!insertmacro MUI_LANGUAGE "Turkish"

Section "Ana Uygulama" SecMain
  SetOutPath "$INSTDIR"
  File "dist\game\${APP_EXE}"
  File /r "dist\game\assets"
  File "README.txt"
  ; Ayarlar dosyası (opsiyonel)
  IfFileExists "settings.json" 0 +2
    File "settings.json"
  ; Başlangıç menüsü
  CreateDirectory "$SMPROGRAMS\${APP_NAME}"
  CreateShortcut "$SMPROGRAMS\${APP_NAME}\${APP_NAME}.lnk" "$INSTDIR\${APP_EXE}"
  CreateShortcut "$SMPROGRAMS\${APP_NAME}\Kaldir.lnk" "$INSTDIR\Uninstall.exe"
  ; Masaüstü kısayolu
  CreateShortcut "$DESKTOP\${APP_NAME}.lnk" "$INSTDIR\${APP_EXE}"
  ; Registry
  WriteRegStr HKLM "Software\${APP_NAME}" "Install_Dir" "$INSTDIR"
  WriteRegStr HKLM "Software\Microsoft\Windows\CurrentVersion\Uninstall\${APP_NAME}" "DisplayName" "${APP_NAME}"
  WriteRegStr HKLM "Software\Microsoft\Windows\CurrentVersion\Uninstall\${APP_NAME}" "UninstallString" '"$INSTDIR\Uninstall.exe"'
  WriteRegStr HKLM "Software\Microsoft\Windows\CurrentVersion\Uninstall\${APP_NAME}" "DisplayVersion" "${APP_VERSION}"
  WriteRegStr HKLM "Software\Microsoft\Windows\CurrentVersion\Uninstall\${APP_NAME}" "Publisher" "${APP_PUBLISHER}"
  WriteUninstaller "$INSTDIR\Uninstall.exe"
SectionEnd

Section "Uninstall"
  Delete "$INSTDIR\${APP_EXE}"
  Delete "$INSTDIR\README.txt"
  Delete "$INSTDIR\Uninstall.exe"
  RMDir /r "$INSTDIR\assets"
  RMDir "$INSTDIR"
  Delete "$SMPROGRAMS\${APP_NAME}\${APP_NAME}.lnk"
  Delete "$SMPROGRAMS\${APP_NAME}\Kaldir.lnk"
  RMDir "$SMPROGRAMS\${APP_NAME}"
  Delete "$DESKTOP\${APP_NAME}.lnk"
  DeleteRegKey HKLM "Software\Microsoft\Windows\CurrentVersion\Uninstall\${APP_NAME}"
  DeleteRegKey HKLM "Software\${APP_NAME}"
SectionEnd
