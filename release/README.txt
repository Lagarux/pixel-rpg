╔══════════════════════════════════════════════════════════════╗
║         KARANLIK TAC'IN LANETI  v5.0  — 2D Pixel RPG        ║
╚══════════════════════════════════════════════════════════════╝

KURULUM (EXE olarak çalıştırma)
─────────────────────────────────
  Windows:
    1. build_windows.bat dosyasını çift tıklayın
    2. dist\game\KaranlikTacinLaneti.exe dosyasını çalıştırın

  macOS / Linux:
    1. chmod +x build_mac_linux.sh && ./build_mac_linux.sh
    2. dist/game/KaranlikTacinLaneti çalıştırın

PYTHON İLE DOĞRUDAN ÇALIŞTIRMA
──────────────────────────────
  pip install pygame numpy
  python pixel_rpg.py

FONTlar (Otomatik İndir)
─────────────────────────
  python download_fonts.py
  (İnternet bağlantısı gerekir — opsiyonel, sistem fontu da çalışır)

KONTROLLER
──────────
  WASD / Ok Tuşları   Hareket
  E                   Konuş / Etkileşim / Onayla
  Space               Sınıfa Özel Saldırı
  1 / 2 / 3 / 4       Yetenek Kullan
  I                   Envanter / Ekipman  (Tab ile sekme değiştir)
  Q                   Görev Günlüğü
  U                   Nitelik Dağıtımı
  F1                  Ayarlar (ses, dil, tam ekran)
  F11                 Tam Ekran Aç/Kapat
  R (Oyun Bitti)      Yeniden Başla
  ESC                 Çık / Geri

SINIFLAR
─────────
  Savaşçı  — Melee koni saldırı, kalkan yetenekleri
  Büyücü   — Oto-nişan arcane bolt, meteor yetenekleri
  Okçu     — Hassas ok atışı, çoklu atış yetenekleri
  Şifacı   — Kutsal darbe + iyileşme, kalkan yetenekleri

ANA GÖREVLER (6 Bölüm)
───────────────────────
  1. Ashveil'de Yaşlı Aldric ile konuş
  2. Karanlık Orman'da Sir Roland'ı bul
  3. Antik Harabeler'den Toprak Kristali al
  4. Çöl'de Oracle Nyx'i bul
  5. Buz Mağarası'ndan Su Kristali al
  6. Gölge Kalesi'nde Malachar'ı yen!

YAN GÖREVLER (Mini Quests)
──────────────────────────
  • Parşömen Avı   — Gizemli Kütüphane: 3 parşömen topla
  • Domuz Avı      — Güney Çayırı: 3 yaban domuzu öldür
  • Balıkçı Yardımı — Batı Nehri: Balıkçı Riva ile konuş

HARİTALAR
──────────
  Ashveil Köyü → (sağ) Karanlık Orman → (kuzey) Antik Harabeler
  Ashveil      → (güney) Güney Çayırı
  Ashveil      → (batı) Batı Nehri → (kuzey) Gizemli Kütüphane
  Antik Harabeler → (doğu) Çöl Yolu → (doğu) Buz Mağarası
  Buz Mağarası → (alt portal) Gölge Kalesi
  Ashveil      → (güney yol) Köy Altı Zindanı

AYARLAR (settings.json)
────────────────────────
  F1 ile açın:
  - Tam Ekran açma/kapama
  - Ana Ses / Efekt / Müzik sesi (0-100)
  - Dil: Türkçe / English
  - FPS Göstergesi

SESler
───────
  Prosedürel ses sentezi (numpy) — harici ses dosyasına ihtiyaç yok!
  Tüm ses efektleri matematiksel dalga fonksiyonları ile üretilir.

LİSANS
───────
  Kaynak kod: MIT Lisansı
  Fontlar: Google Fonts — SIL Open Font License
  Ses: Prosedürel (telif hakkı yok)
