╔══════════════════════════════════════════════════════════════╗
║        KARANLIK TAÇ'IN LANETİ  v6.3  —  2D Pixel RPG         ║
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
                     Dükkânda TAB: Satın Al / Sat / Yükselt
  Q                  Görev günlüğü  (W / S ile kaydır)
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


AVLANMA, MALZEME VE YÜKSELTME
─────────────────────────────────────────────────────────────
  Boss dışındaki düşmanlar bir dakika sonra kendi yerlerinde geri
  doğar. Yakınındaysan beklerler; gözünün önünde belirmezler.

  Her düşman türünün kendi malzemesi var (yeşil öz, demir cevheri,
  gölge kırığı...). Bunları satabilir ya da demircide harcayabilirsin.

  Demirci giydiğin her parçayı +5'e kadar yükseltir: altın ve malzeme
  ister. Her kademe parçanın en güçlü niteliğini bir arttırır.

  En iyi ekipman hiçbir sandıktan çıkmaz; yalnızca satın alınır.
  Yani avlanmanın bir karşılığı var.

  Seviye tavanı 30.


ANA BOSS'LAR
─────────────────────────────────────────────────────────────
  Beş ana boss var. Dördü birer kristal muhafızı:

    Taş Muhafız      Antik Harabeler    Toprak Kristali
    Buzul Devi       Buz Mağarası       Su Kristali
    Köz Devi         Köz Vadisi         Ateş Kristali    (isteğe bağlı)
    Sayfa Muhafızı   Gizemli Kütüphane  Işık Kristali    (isteğe bağlı)
    MALACHAR         Gölge Kalesi       son savaş

  Her biri düştüğünde araya bir sahne girer ve mühürden hangi parçanın
  geri alındığı anlatılır. Son iki kristal zorunlu değil ama kapanışı
  ve unvanını değiştirir.


İPUÇLARI
─────────────────────────────────────────────────────────────
  • Düşman saldırmadan önce kırmızı bir halka daralır — kaçın.
  • Kurtlar sürü hâlinde cesur, yalnızken çekingendir.
  • Goblinler yaralanınca kaçar; dar yerlere çekmelerine izin vermeyin.
  • Akrepler uzaktan atar, yanaşınca geri çekilir.
  • Pazar meydanı köyün güneybatısındadır; dört tezgâh farklı şeyler satar.
  • Handa konaklamak (18 altın) can ve manayı tam doldurur.
  • Oyun harita geçişlerinde kendiliğinden kaydeder.
  • Ağaç kök çok dayanıklı ama çok yavaş: kaçarak yıpratabilirsin.
  • Haydutlar canları azalınca kaçar; yolu kesmeden önce köşeye sıkıştır.
  • Dev örümcek ağ atar, yaklaşınca da vurur.
  • Malzemeleri hepsini satma: yükseltme için de gerekiyorlar.
  • Yirmi iki yan görev var; günlükte W/S ile hepsini gezebilirsin.
  • Haritalar köyden uzaklaştıkça sertleşir. Sıra atlamak zorlar.


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
