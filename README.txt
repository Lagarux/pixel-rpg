╔══════════════════════════════════════════════════════════════╗
║        KARANLIK TAÇ'IN LANETİ  v6.1  —  2D Pixel RPG         ║
╚══════════════════════════════════════════════════════════════╝

  Yüz yıl önce atalarımız Malachar'ı dört kristalle mühürledi.
  Mühür zayıflıyor.


NASIL OYNANIR
─────────────────────────────────────────────────────────────
  KaranlikTacinLaneti.exe dosyasını çalıştırın. Kurulum gerekmez.

  Oyuna ilk girişte kontrolleri gösteren bir tanıtım açılır.
  Sonradan görmek isterseniz: ESC → Kontroller


KONTROLLER
─────────────────────────────────────────────────────────────
  WASD / Ok tuşları  Hareket
  Space              Sınıfına özel saldırı
  1 2 3 4            Yetenekler
  E                  Konuş / Eşya al / Dükkân aç
  I                  Envanter ve Ekipman   (TAB: sekme değiştir)
  Q                  Görev günlüğü
  M                  Mini harita aç / kapat
  U                  Nitelik dağıtımı
  F1                 Ayarlar (ses, dil, tam ekran)
  F11                Tam ekran
  ESC                Duraklat / Geri


ELEMENTLER
─────────────────────────────────────────────────────────────
  Her düşmanın ve her saldırının bir elementi var. Can çubuğunun
  solundaki renkli taş düşmanın elementini gösterir; sol üstte de
  kendi saldırı elementiniz yazar.

    Ateş    güçlü: Doğa, Buz
    Buz     güçlü: Doğa, Toprak
    Doğa    güçlü: Toprak, Gölge
    Gölge   güçlü: Kutsal, Doğa
    Kutsal  güçlü: Gölge
    Toprak  güçlü: Ateş

  Her element kendine karşı dirençlidir. Fiziksel saldırı nötrdür:
  ne bonus alır ne ceza. Taktığınız silah temel saldırınızın
  elementini belirler, zırh ve muskalar bir elemente karşı korur.


İPUÇLARI
─────────────────────────────────────────────────────────────
  • Düşman saldırmadan önce kırmızı bir halka daralır — kaçın.
  • Kurtlar sürü hâlinde cesur, yalnızken çekingendir.
  • Goblinler yaralanınca kaçar; dar yerlere çekmelerine izin vermeyin.
  • Akrepler uzaktan atar, yanaşınca geri çekilir.
  • Pazar meydanı köyün güneybatısındadır; dört tezgâh farklı şeyler satar.
  • Handa konaklamak (18 altın) can ve manayı tam doldurur.
  • Oyun harita geçişlerinde kendiliğinden kaydeder.


DİL
─────────────────────────────────────────────────────────────
  Türkçe, İngilizce, Almanca, Rusça, Arapça.
  F1 → Dil satırında sol/sağ ok ile değiştirin. Tercihiniz saklanır.


KAYIT DOSYALARI NEREDE
─────────────────────────────────────────────────────────────
  Windows : %APPDATA%\KaranlikTacinLaneti\
  Linux   : ~/.local/share/KaranlikTacinLaneti/

  Oyunun kurulu olduğu klasöre hiçbir şey yazılmaz.


SORUN GİDERME
─────────────────────────────────────────────────────────────
  Ses gelmiyorsa    : F1 → Ses seviyelerini kontrol edin.
  Yazılar bozuksa   : assets/fonts klasörünün yanında olduğundan
                      emin olun; yoksa sistem yazı tipine düşer.
  Oyun açılmıyorsa  : Klasörü tam olarak, assets dahil kopyaladığınızdan
                      emin olun.


KAYNAK KOD
─────────────────────────────────────────────────────────────
  https://github.com/Lagarux/pixel-rpg

  Python ile doğrudan çalıştırmak isterseniz:
      pip install pygame
      python pixel_rpg.py

  Tek bağımlılık pygame'dir. Bütün grafikler ve sesler oyun
  çalışırken üretilir — yanında hiçbir görsel ya da ses dosyası yoktur.
