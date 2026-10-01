# Karanlık Taç'ın Laneti — Geliştirme Planı ve Süreç Takibi

> Bu belge oyunun **ölçülmüş** mevcut durumunu, tespit edilen sorunları ve aşama aşama
> yol haritasını tutar. Her fazın sonunda testleri çalıştırıp bu dosyayı güncelliyoruz.
> Böylece "neyi, neden, hangi kanıta dayanarak" değiştirdiğimiz kayıt altında kalır.

**Son güncelleme:** 2026-09-28 · **Oyun sürümü:** v5.0 · **Aktif faz:** Faz 5 (Faz 0-4 tamamlandı; oyun testi sonrası düzeltmeler yapıldı)

---

## 0. Nasıl çalıştırılır

```bash
# Oyunu oyna
python pixel_rpg.py

# Tüm testler (yol testleri + otomatik oynanış duman testi)
python -m unittest discover -s tests -v

# Otomatik oynanış + ekran görüntüsü + ölçüm raporu
python tests/test_gameplay_smoke.py
```

| Dosya | Görevi |
|---|---|
| `tests/test_file_paths.py` | Kaynak yolları (`settings.json`, `assets/fonts`) betiğin kendi dizinine göre mi çözümleniyor? |
| `tests/harness.py` | Oyunu testten süren koşum takımı (`pygame.display.flip` kancası ile) |
| `tests/test_gameplay_smoke.py` | Oyunu baştan sona otomatik oynar, 24 ekran görüntüsü üretir, ölçüm toplar |
| `tests/test_combat_feel.py` | Dövüş hissi ve arayüz katmanları (telegraf, yol bulma, karartma, rozet) |
| `tests/test_save_load.py` | Kayıt/yükleme turu ve bozuk kayda dayanıklılık |
| `tests/test_atmosphere.py` | Dekor, ışık halesi, NPC gezinmesi, daktilo diyalog |
| `tests/test_locales.py` | Dil dosyaları: eksik anahtar, yer tutucu, RTL, çevrilmemiş metin |
| `tests/test_shop.py` | Dükkân: alış/satış, altın kontrolü, sınıf kısıtı, konaklama |
| `tools/` | Tek seferlik metin çıkarma betikleri ve tüm dillerin kaynağı (`locales_data.py`) |
| `tests/screenshots/` | Test çıktısı kareler (her koşumda yeniden üretilir) |

Testler **penceresiz** (`SDL_VIDEODRIVER=dummy`) çalışır: ekran açılmaz, ses kartı gerekmez,
ama çizim gerçekten yapılır — yani görüntüler oyunun gerçek kareleridir.

---

## 1. Ölçümler (Faz 0 çıktısı)

| Ölçüm | Değer | Yorum |
|---|---|---|
| Oyuncu adım büyüklüğü | **yalnızca 32 px** | Ara kare yok — karakter ışınlanıyor |
| Hareket içeren kare oranı | **5 / 402** (%1,2) | Karelerin %99'unda ekranda hareket yok |
| Kamera adım büyüklüğü | **32 px** | Kamera da zıplıyor, yumuşatma yok |
| Çapraz hareket (↓+→ birlikte) | sonuç: yalnızca **sağa** | Çapraz yön desteklenmiyor |
| Ham kare maliyeti (köy) | **3,27 ms** (~306 FPS tavan) | 60 FPS için pay var, ama UI gereksiz pahalı |
| Kare başına `SysFont()` | **1,0** (ekranda 1 NPC varken) | Her NPC her karede font yüklüyor |
| En kötü tek kare | < 250 ms | Kilitlenme yok |
| Kullanılmayan yerelleştirme anahtarı | **36 anahtarın 21'i** | EN dili yarım çalışıyor · *Faz 1 sonrası: 15* |
| `FontManager` çağrısı | **0** | `assets/fonts` içindeki 8 font hiç kullanılmıyor · *Faz 1 sonrası: devrede* |

### Faz 2 sonrası (2026-09-28)

Akıcılık ölçümleri artık **işaretli yürüyüş penceresinden** alınıyor (`mark("yuru_basla")` →
`mark("yuru_bitti")`). Önceki "5/402" gibi oranlar tüm oturuma bölündüğü için yanıltıcıydı:
menüde ve diyalogda geçen kareler de paydaya giriyordu.

| Ölçüm | Faz 0 | Faz 2 | Kabul |
|---|---|---|---|
| Oyuncu adımı (en büyük) | 32 px (ışınlanma) | **3,2 px** | < 16 px ✔ |
| Hareketli kare oranı (yürürken) | %10 (10 karede 1 adım) | **%92** | > %80 ✔ |
| Kamera adımı (en büyük) | 32 px | **4 px** | < 16 px ✔ |
| Çapraz hareket | yok | **(31,25) → (34,28)** | iki eksen de ✔ |
| Kare başına `SysFont()` | 1,0 | **0** | 0 ✔ |
| Ham kare maliyeti (köy) | 3,27 ms (~306 FPS) | **~1,0 ms (~900 FPS)** | — |

Oyun hızı bilerek değişmedi: bir kare hâlâ `move_delay` kadar sürüyor (savaşçıda 10 kare),
yalnızca arası dolduruluyor. Çapraz adım `×1,41` sürüyor ki çapraz gitmek hızlı olmasın.

---

## 2. Bulgular

Şiddet: 🔴 kritik · 🟠 önemli · 🟡 iyileştirme · Satır başındaki **✅** o bulgunun çözüldüğünü gösterir.

### 2.1 Hatalar

| ID | Şiddet | Bulgu | Kanıt | Öneri |
|---|---|---|---|---|
| ✅ B1 | 🟠 | Şifacı pasif yenilenmesi neredeyse hiç çalışmıyor: `self.tick % 120 == 0` kontrolü var ama `self.tick = pygame.time.get_ticks()` **milisaniye** döndürüyor; kare başına ~17 ms arttığı için 120'nin tam katına denk gelmek rastlantısal | `pixel_rpg.py:2617`, `:2792` | Ayrı bir kare sayacı (`self.frame_no`) tut, `% 120` onunla yapılsın |
| ✅ B2 | 🟠 | Envanterin "Ekipman" sekmesinde `E` yanlış yuvayı çıkarıyor: seçilen yuva `stat_sel` (nitelik dağıtım ekranının imleci) ile belirleniyor | `pixel_rpg.py:2730` | Sekmeye özel `eq_sel` imleci + ekranda görünür seçim çerçevesi |
| ✅ B3 | 🟠 | Seviye atlama açılır penceresi **ölüm ve zafer ekranının üstüne** çiziliyor | `tests/screenshots/23_olum.png`, `pixel_rpg.py:2854` | Çizimi `state == "playing"` koşuluna bağla |
| ✅ B4 | 🟡 | Oyun başlarken müzik iki kez başlatılıyor (aynı satır tekrarlı) | `pixel_rpg.py:2262-2263` | Fazla satırı sil |
| ✅ B5 | 🟡 | `MAP_MUSIC` tablosunda `rocky_pass` ve `misty_swamp` yok → tehlikeli geçitte köy müziği çalıyor | `pixel_rpg.py:2250` | İki haritayı tabloya ekle (`battle` / `dungeon`) |
| ✅ B6 | 🔴 | **Paketlenmiş oyunda ayarlar hiç kalıcı olmuyor:** `settings.json` `__file__`'ın yanına yazılıyor; build **onefile** olduğu için `__file__` çalışma anında geçici `_MEIxxxx` klasöründe kalır ve oyun kapanınca **o klasör silinir**. Üstelik kurulum `$PROGRAMFILES` altına yapıldığından yazma izni de yok. Hata `except: pass` ile sessizce yutuluyor, oyuncu hiçbir uyarı görmüyor | `pixel_rpg.py:33`, `:49-52`, `KaranlikTacinLaneti.spec:28-48` (onefile), `installer_windows.nsi:11` | Yazılabilir veriyi `%APPDATA%\KaranlikTacinLaneti\` altına al; `__file__` tabanlı yol yalnızca salt-okunur varlıklar (fontlar) için kalsın |
| ✅ B7 | 🟠 | `FontManager` sınıfı hiç çağrılmıyor; ayrıca aradığı dosya adları (`Cinzel-Bold.ttf`, `Almendra-Bold.ttf`, `UncialAntiqua-Regular.ttf`) `assets/fonts` içinde **yok** (var olanlar: `Cinzel-Regular`, `Almendra-Regular`, `MedievalSharp-Regular`) | `pixel_rpg.py:146-177` | Dosya adlarını düzelt ve `UI.__init__` içinde `SysFont` yerine `FontManager.get` kullan |
| ✅ B8 | 🟡 | Sürüm tutarsız: dosya başlığı v5.0, başlık ekranı ve konsol çıktısı v4.0 | `pixel_rpg.py:3`, `:1842`, `:2894` | Tek bir `VERSION` sabiti |
| ✅ B9 | 🟡 | Üretilen ama hiç çalınmayan sesler: `walk`, `equip`, `error`, `trap`, `freeze`, `boss_alert` | `pixel_rpg.py:232-251` | İlgili olaylara bağla (ayak sesi, ekipman, tuzak, boss girişi) |
| ✅ B10 | 🟡 | Dil seçeneği yarım: 36 çeviri anahtarının 21'i hiç kullanılmıyor; başlık, sınıf seçimi, ölüm/zafer ekranları sabit Türkçe | `pixel_rpg.py:63-143`, `:1833-1848` | Sabit metinleri `T_()` üzerinden geçir · **kısmen yapıldı:** Faz 1'de kullanılmayan anahtar 21 → 15 |
| ✅ B11 | 🟠 | **Almendra fontu `ğ` ve `ş` gliflerini içermiyor**, bu harfleri sessizce yutuyor: "Doğudaki … başla." → "Do udaki … ba la." Faz 1'de fontlar devreye alınırken ortaya çıktı; `font.metrics()` ve genişlik ölçümü bu durumu **yakalamıyor**, yalnızca çizilen pikseller yakalıyor | `tests/screenshots/_font_turkce.png` | Diyalog fontu MedievalSharp'a alındı; `FontManager` artık her adayı Türkçe alfabeyle sınayıp çizemeyeni eliyor |

### 2.2 Akıcılık

| ID | Şiddet | Bulgu | Kanıt | Öneri |
|---|---|---|---|---|
| ✅ A1 | 🔴 | **Kafes atlamalı hareket:** `_try_move` piksel konumunu anında hedefe atıyor, ara kare yok. Karakter 10 karede bir 32 px ışınlanıyor | ölçüm: adım = {32 px}, hareketli kare 5/402; `pixel_rpg.py:2277` | Kareler arası doğrusal geçiş: `move_progress` 0→1 ilerlerken `px/py` interpolasyonu + yürüme animasyonu |
| ✅ A2 | 🔴 | **Kamera sıçrıyor:** hedefe anında atanıyor | ölçüm: kamera adımı {32 px}; `pixel_rpg.py:2267` | Yumuşatma (`cam += (hedef-cam) * 0.15`) + küçük ölü bölge |
| ✅ A3 | 🟠 | Çapraz hareket yok; `elif` zinciri tek yön seçiyor, öncelik sol > sağ > yukarı > aşağı | ölçüm: ↓+→ → yalnız sağa; `pixel_rpg.py:2778-2781` | Yön vektörünü topla, çapraz hareketi de dene (duvara değince kaydır) |
| ✅ A4 | 🟠 | Tüm zamanlama **kare sayısına** bağlı (hareket gecikmesi, bekleme süreleri, dokunulmazlık). FPS düşerse oyun yavaşlar | `pixel_rpg.py:2782-2795` | `dt` tabanlı zamanlama |
| ✅ A5 | 🟠 | Düşman AI eksen-açgözlü: tek eksende ilerliyor, duvar köşesinde takılıyor; yol bulma yok (oysa BFS için `deque` projede zaten var) | `pixel_rpg.py:2540-2548`, `:1088` | Kısa menzilli BFS/A* + takılınca yan adım |
| ✅ A6 | 🟡 | `grad_bar` ve `panel` her karede piksel piksel çizgi çiziyor: HUD'da 3 bar + panel yüksekliği → kare başına ~1000 `draw.line` | `pixel_rpg.py:1738-1758`; ham kare 3,27 ms | Bar/panel yüzeylerini önbelleğe al, değişince yeniden üret |
| ✅ A7 | 🟡 | `NPC.draw` ve boss çizimi **her karede** `SysFont` çağırıyor | ölçüm: 1,0 çağrı/kare (tek NPC); `pixel_rpg.py:978`, `:1005` | Sınıf düzeyinde font önbelleği |

### 2.3 Etkileşim ve his

| ID | Şiddet | Bulgu | Kanıt | Öneri |
|---|---|---|---|---|
| ✅ E1 | 🔴 | Etkileşim ipucu yok: NPC/sandık yanındayken ekranda `[E]` göstergesi çıkmıyor; üstelik yalnızca tam karşı kare çalışıyor | `pixel_rpg.py:2559-2562` | Yakındaki hedefin üstünde yanıp sönen `[E]` rozeti + 1 karelik tolerans |
| ✅ E2 | 🟠 | Düşman saldırısı telegraflanmıyor: yan yana gelir gelmez otomatik hasar; hazırlanma animasyonu, uyarı yok. Üstelik **çaprazdan da** vuruyor (oyuncu çapraz gidemezken) | `pixel_rpg.py:2549` | Kısa "hazırlanma" fazı + saldırı animasyonu; çapraz vuruşu kaldır ya da oyuncuya da çapraz ver |
| ✅ E3 | 🟠 | Vuruş geri bildirimi zayıf: geri itme, kısa donma (hit-stop), ekran sarsıntısı yok | `pixel_rpg.py:2377-2385` | 3-5 karelik hit-stop + geri itme + boss vuruşunda hafif sarsıntı |
| ✅ E4 | 🟠 | Bölüm duyurusu **260 kare (~4,3 sn)** ekranın ortasını kaplıyor — savaşın tam ortasında bile | `19_saldiri.png`, `21_dusman_yapay_zeka.png`; `pixel_rpg.py:2301`, `:2855` | Süreyi kısalt, üst şeride taşı, savaşta ertele |
| ✅ E5 | 🟠 | Pencereler fazla şeffaf: envanter/görev günlüğü/nitelik ekranında arka plandaki dünya okunuyor. *(Düzeltme: ölüm ekranı zaten 185 alfa ile karartıyormuş — ilk tespitte yanlış yazmışım, sorun yalnızca panellerdeydi.)* | `11_envanter.png`, `13_gorev_gunlugu.png`, `23_olum.png` | Panel arkasına karartma katmanı (`alpha ~180`) |
| ✅ E6 | 🟡 | Diyalog sırasında yetenek çubuğu diyalog kutusuyla çakışıyor | `09_diyalog.png`; `pixel_rpg.py:2853` | Diyalogda alt HUD'u gizle |
| ✅ E7 | 🟡 | Diyalog daktilo efekti, portre ve konuşma sesi içermiyor; 4 satır birden beliriyor | `pixel_rpg.py:1936-1947` | Karakter karakter yazım + `E` ile anında tamamlama |
| E8 | 🟡 | Başlık ekranında `F1 Ayarlar` ipucu yazmıyor (çeviri anahtarı var, çizim yok); `ESC ile çıkış` da belirtilmemiş | `01_baslik.png`; `pixel_rpg.py:1848` | İpucu satırına ekle |

### 2.4 Sürükleyicilik ve içerik

| ID | Şiddet | Bulgu | Kanıt | Öneri |
|---|---|---|---|---|
| ✅ İ1 | 🔴 | **Kayıt/yükleme yok.** Ölünce her şey baştan; oyuncu ikinci oturuma dönemiyor | `pixel_rpg.py:2213` (`_reset`) | `%APPDATA%` altına slot bazlı JSON kayıt + başlık ekranında "Devam Et" |
| ✅ İ2 | 🟠 | Haritalar boş hissettiriyor: geniş çim alanlar, dekor nesnesi yok (ağaç, çit, fener, varil, çiçek, tabela) | `05_koy_ashveil.png` | Dekor tile'ları + rastgele serpiştirme; köy meydanına kuyu/pazar |
| ✅ İ3 | 🟠 | Karanlık Orman okunamayacak kadar karanlık: koyu tile paleti + `ambient` katmanı üst üste biniyor | `19_saldiri.png`, `21_dusman_yapay_zeka.png`; `pixel_rpg.py:1036-1037` | Ambient alfasını düşür, oyuncunun çevresine ışık halesi (vignette) ekle |
| ✅ İ4 | 🟠 | NPC'ler tamamen hareketsiz; boşta gezinme/iş yapma yok | `pixel_rpg.py:970-982` | Basit boşta gezinme (kendi bölgesinde 1-2 kare) + oyuncuya dönme |
| İ5 | 🟠 | Yön bulma zayıf: görev işaretçisi (`!` / `?`), mini harita ya da pusula yok | `05_koy_ashveil.png` | NPC üstünde görev simgesi + köşede mini harita |
| ✅ İ6 | 🟡 | Ses peyzajı yok: ayak sesi, ortam sesi yok; müzik harita geçişinde sert kesiliyor ve **her geçişte numpy ile yeniden üretiliyor** | `pixel_rpg.py:273-318`, `:2293` | Temaları bir kez üret + önbellekle, geçişte çapraz sönümleme |
| İ7 | 🟡 | Ekonomi işlevsiz: altın toplanıyor ama dükkân yok (demirci "altın getir" diyor, satın alma ekranı yok) | `pixel_rpg.py:1209` | Demirci/hancı için basit alım-satım ekranı |
| İ8 | 🟡 | Düşman davranış çeşitliliği yok: hepsi aynı takip mantığı | `pixel_rpg.py:2525-2557` | Menzilli, kaçan, sürü halinde saldıran türler |

### 2.5 Teknik borç

| ID | Şiddet | Bulgu | Öneri |
|---|---|---|---|
| T1 | 🟠 | Tek dosyada ~2900 satır; okunabilirlik ve test edilebilirlik düşük | Modüllere ayır: `core/`, `entities.py`, `maps/`, `ui.py`, `audio.py` |
| T2 | 🟡 | `Game.run` içinde olay/güncelleme/çizim iç içe; birim test zor | `update(dt)` ve `draw()` olarak ayır (koşum takımı şimdilik `flip` kancasıyla idare ediyor) |
| ✅ T3 | 🟡 | `.gitignore` yok; `__pycache__/`, `tests/screenshots/`, `settings.json` depoya sızabilir | `.gitignore` ekle |

---

## 3. Yol haritası

### ✅ Faz 0 — Ölçüm altyapısı (tamamlandı, 2026-09-27)
- [x] Kaynak yolu testleri (`tests/test_file_paths.py`)
- [x] Oyunu otomatik süren koşum takımı (`tests/harness.py`)
- [x] 24 adımlık otomatik oynanış + ekran görüntüsü testi
- [x] Akıcılık ve performans ölçümleri
- **Kabul:** `python -m unittest discover -s tests` → 7 test, hepsi geçiyor ✔

### ✅ Faz 1 — Kritik hatalar ve hızlı kazanımlar (tamamlandı, 2026-09-28)
- [x] B6 — ayarlar `%APPDATA%\KaranlikTacinLaneti\` altına taşındı; eski konum geriye dönük okunuyor
- [x] B3 — seviye atlama ve bölüm duyurusu yalnızca oyun içindeyken çiziliyor
- [x] B2 — ekipman sekmesinin kendi imleci (`eq_sel`) + görünür seçim çerçevesi
- [x] B1 — şifacı pasif yenilenmesi kare sayacına (`frame_no`) bağlandı
- [x] B7 — `FontManager` devrede: başlıklar Cinzel, diyalog MedievalSharp
- [x] B11 — *(yeni bulgu)* Türkçe glif denetimi: `ğ/ş` çizemeyen font eleniyor
- [x] B4, B5, B8 — çift müzik çağrısı, eksik müzik eşleşmeleri, tek `VERSION` sabiti
- [x] E6 — *(erken alındı)* diyalog sırasında yetenek çubuğu gizleniyor
- [x] T3 — `.gitignore`
- **Kabul:** 21 test geçiyor; 5 yeni regresyon testi bu düzeltmeleri kilitliyor ✔

#### Faz 1'de ne değişti

| Bulgu | Değişiklik | Yer |
|---|---|---|
| B6 | `BASE_DIR` / `ASSET_DIR` / `USER_DIR` ayrımı; `_user_data_dir()` Windows/macOS/Linux; `LEGACY_SETTINGS_FILE` göçü; `save_failed` bayrağı | `pixel_rpg.py:32-60` |
| B7+B11 | `FontManager._renders_turkish()` her adayı sınıyor; `UI` başlıklarda Cinzel, diyalogda MedievalSharp; `txt_c()` ile font-bağımsız ortalama | `pixel_rpg.py:146-200`, `UI.__init__` |
| B3+E6 | `Game.HUD_STATES` sabiti; pencereler ve yetenek çubuğu duruma göre çiziliyor | `Game.run` çizim bloğu |
| B2 | `EQUIP_SLOTS` sabiti, `eq_sel` imleci, sekmeye özel tuş işleme ve ipucu satırı | `pixel_rpg.py:430`, `draw_inventory`, `Game.run` |
| B1 | `self.frame_no` sayacı (ms olan `self.tick` yerine) | `Game.run`, `_reset` |
| B10 (kısmi) | Başlık/sınıf/ölüm/zafer metinleri `T_()` üzerinden | `draw_title`, `draw_gameover`, `draw_victory`, `draw_class_select` |

**Yan etki:** Ortalamalar artık `len(metin)*8` gibi monospace varsayımlarıyla değil, gerçek font
genişliğiyle hesaplanıyor (`UI.txt_c`). Bu olmadan orantılı fontlara geçince tüm başlıklar kayıyordu.

### ✅ Faz 2 — Akıcılık (tamamlandı, 2026-09-28)
- [x] A1 — kareler arası yumuşak hareket + yürüme animasyonu
- [x] A2 — kamera yumuşatma ve ölü bölge
- [x] A3 — çapraz hareket (köşe kesmez, duvara sürtünerek kayar)
- [x] A4 — sabit adımlı zamanlama (FPS düşse de oyun yavaşlamaz)
- [x] A6, A7 — UI yüzey önbelleği, font önbelleği
- **Kabul:** 4 yeni akıcılık testi + ölçüm tablosu, hepsi geçti ✔

#### Faz 2'de ne değişti

| Bulgu | Değişiklik | Yer |
|---|---|---|
| A1 | `Entity` artık adım tabanlı: `start_step()` hedefi belirler, `advance_step()` pikseli her karede yaklaştırır, `snap()` ışınlanma için. `tx/ty` **anında** güncellenir; oyun mantığının tamamı (menzil, çarpışma, geçiş) dokunulmadan çalışmaya devam eder | `Entity`, `_try_move`, `_update_enemies` |
| A2 | `cam_fx/cam_fy` ondalık takip + `CAM_LERP=0.18`, `CAM_DEAD=24`; çizim tam sayı `cam_x/cam_y` kullanır. Harita geçişinde `_cam_snap()` | `_cam`, `_cam_target`, `_cam_snap` |
| A3 | `_read_move_input()` iki ekseni birden okur; `_move_player()` önce çaprazı dener, olmazsa tek eksene kayar. Köşe kesmeyi engellemek için çapraz adım komşu karelerden en az biri açıksa kabul edilir | `_read_move_input`, `_move_player`, `_try_move` |
| A4 | `_update()` ayrıldı, `_step_updates()` gerçek geçen süreye göre sabit 1/60 adım çalıştırır (en fazla 5 telafi adımı) | `Game.run` |
| A6 | `UI._bar_surface` / `UI._panel_surface` önbelleği: degrade bir kez üretilir, dolu kısım kırpılarak çizilir | `UI.grad_bar`, `UI.panel` |
| A7 | `_tag_font()` + `_tag_surf()` paylaşımlı önbellek; NPC adı ve boss yazısı her karede yeniden üretilmiyor | `NPC.draw`, `Enemy.draw` |

**Neden `dt` ile çarpmak yerine sabit adım?** Oyundaki her sayaç (yetenek bekleme, dokunulmazlık,
tuzak, mermi ömrü, düşman adımı) kare sayıyor. Hepsini `dt` ile ölçeklemek geniş ve riskli bir
değişiklikti; mantığı sabit 1/60 adımda tutup gecikmeyi telafi adımıyla kapatmak aynı sonucu
(FPS'ten bağımsız oyun hızı) mevcut sayaçları bozmadan veriyor.

**Test altyapısında:** `harness.mark()` ölçüm penceresi açıyor, `place_in_open_area()` oyuncuyu
hem tamamen açık hem de kameranın harita kenarına yaslanmadığı bir alana koyuyor — ilk denemede
çapraz test duvara, kamera testi de harita sınırına denk gelip sessizce anlamsızlaşmıştı.

### ✅ Faz 3 — Dövüş hissi ve arayüz düzeni (tamamlandı, 2026-09-28)
- [x] E1 — `[E]` etkileşim rozeti + bir karelik tolerans
- [x] E2 — düşman saldırı telegrafı (çapraz vuruş sorunu A3 ile kendiliğinden çözüldü)
- [x] E3 — hit-stop, geri itme, ekran sarsıntısı
- [x] E4 — bölüm duyurusu üst şeritte
- [x] E5, E6 — panel karartması, diyalogda HUD gizleme
- [x] A5 — düşman yol bulma (kısa menzilli BFS)
- **Kabul:** `tests/test_combat_feel.py` — 16 test, hepsi geçti ✔

#### Faz 3'te ne değişti

| Bulgu | Değişiklik | Yer |
|---|---|---|
| E1 | `_interact_target()` önce bakılan kareye, orada bir şey yoksa komşulara bakar; **tek** aday varsa onu seçer (iki aday varsa seçmez, yanlış hedefe konuşulmasın). Hedefin üstüne yanıp sönen `[E]` rozeti | `_interact_target`, `UI.draw_interact_badge` |
| E2 | Düşman artık bitişik olunca anında vurmuyor: `wind_up` 26 kare hazırlanıyor (kırmızı daralan halka + `!`), sonra vuruyor, ardından 34 kare bekliyor. Hazırlanırken yerinden kıpırdamıyor; oyuncu bu pencerede kaçarsa darbe boşa gidiyor | `_update_enemies`, `_enemy_strike`, `Enemy.draw` |
| E3 | `_hit()` her vuruşta 3 kare (kritte 5) donma; kritte ve boss vuruşunda ekran sarsıntısı; kritte düşman bir kare geri itiliyor (boss hariç). Oyuncu hasar alınca da sarsıntı | `_hit`, `_knockback`, `add_shake`, `_cam` |
| E4 | `draw_chapter` tam ekran karartma + ortada dev yazı yerine 92 px'lik üst şerit; süre 260 → 150 kare | `UI.draw_chapter`, `_advance` |
| E5 | Ortak `UI.dim()`; envanter, görev günlüğü, nitelik dağıtımı ve pause arkayı karartıyor | `UI.dim` + panel çizimleri |
| A5 | `_bfs_step()` kısa menzilli BFS (yarıçap 8, diğer düşmanlar engel). Yol yoksa eski basit takibe düşer | `Game._bfs_step` |

**Denge etkisi (izlenecek):** Telegraf düşmanları belirgin şekilde zayıflattı. Önceden bitişik
düşman her 40 karede bir kaçınılmaz hasar veriyordu; şimdi hazırlanma + bekleme ile en iyi
ihtimalle 60 karede bir vuruyor ve kaçılabiliyor. Faz 4'te oynanıp düşman hasarı/sayısı
yeniden ayarlanmalı.

**Test yaklaşımı:** Bu fazın testleri oyunu baştan sürmek yerine parçaları doğrudan çağırıyor
(`Game.__new__` ile pencere açmadan). Telegraf, yol bulma, karartma ve şerit tek başlarına
ölçülebilir davranışlar; duman testinden çok daha hızlı ve kesin sonuç veriyorlar.

### ✅ Faz 4 — Atmosfer ve süreklilik (tamamlandı, 2026-09-28)
- [x] İ1 — kayıt/yükleme, başlıkta "Devam Et", pause'da "Kaydet", harita geçişinde otomatik kayıt
- [x] İ3 — ortam ışığı + oyuncu ışık halesi
- [x] İ2 — harita dekorları (8 çeşit, haritaya göre kararlı dağılım)
- [x] İ4 — NPC boşta gezinme (evinden en çok 2 kare)
- [x] İ6, B9 — altı sesin hepsi bağlandı, müzik önbelleğe alındı
- [x] E7 — daktilo efektli diyalog
- [x] Faz 3'ten kalan denge notu — düşman saldırı ritmi geri ayarlandı
- **Kabul:** `test_save_load.py` (11) + `test_atmosphere.py` (13) = 24 yeni test ✔

#### Faz 4'te ne değişti

| Bulgu | Değişiklik | Yer |
|---|---|---|
| İ1 | `save_game()` / `load_game()` — `%APPDATA%\…\save1.json`. Kayıt **haritaları değil, oyuncunun değiştirdiklerini** tutuyor: açılan sandıklar (`base_chests` farkı) ve ölen düşmanlar (indeks). Böylece dosya ~800 bayt ve harita içeriği sonradan güncellenebiliyor. Yazma `os.replace` ile atomik; bozuk/yabancı sürümlü kayıt sessizce reddediliyor | `Game.save_game`, `load_game`, `GameMap.base_chests` |
| İ3 | `_draw_ambient()` + `_light_hole()`: düz karartma katmanına oyuncunun çevresinde yumuşak bir delik açılıyor (`BLEND_RGBA_MIN`). Maske yarıçapa **ve katman alfasına** göre önbellekte | `pixel_rpg.py` ortam ışığı bölümü |
| İ2 | `PA.prop_surf()` 8 dekor + `_scatter_props()`. Zemin türüne göre seçiliyor, dolu karelere konmuyor, yürümeyi engellemiyor | `PA.prop_surf`, `_scatter_props`, `GameMap.props` |
| İ4 | `_update_npcs()` — NPC'ler arada bir komşu kareye adım atıyor, oyuncunun/eşyanın üstüne basmıyor | `Game._update_npcs`, `NPC.__init__` |
| İ6/B9 | `walk`, `equip`, `error`, `trap`, `freeze`, `boss_alert` bağlandı. `play_music` üretilen parçayı önbelleğe alıyor ve **aynı tema zaten çalıyorsa yeniden başlatmıyor** (köy → çayır geçişinde müzik kesilmiyor) | `SoundManager`, ilgili olaylar |
| E7 | `dlg_reveal` sayacı; `E` önce yazıyı tamamlıyor, sonra sayfa çeviriyor | `_update`, `draw_dialog`, `_dlg_page_len` |
| Denge | `ENEMY_ATK_CD` 34 → 14. Telegraf (26) + bekleme (14) = 40 kare, yani Faz 3 öncesi ritmin aynısı — üstüne kaçma penceresi | `Game.ENEMY_ATK_CD` |

**Testlerin yakaladığı üç hata:** (1) Işık halesi ilk yazımda **tersti** — merkez karanlık,
kenar aydınlıktı; ekran görüntüsünde fark edildi. (2) Düzeltilince de degrade 0-255 aralığında
üretildiği için halenin dış %40'ı düz karanlığa doyuyor, geçiş sert kesiliyordu; maskenin tepe
alfası katman alfasına eşitlendi. (3) Dekor tohumu `hash(m.name)` ile üretiliyordu — Python'da
`str` özeti süreçler arası rastgele olduğu için **dekor her açılışta yeniden diziliyordu**;
`zlib.crc32`'ye geçildi ve iki ayrı süreçte aynı çıktıyı doğrulayan test eklendi.

**Test yalıtımı:** Oyun artık harita geçişinde otomatik kaydettiği için duman testi
kullanıcının gerçek `save1.json` dosyasını yazmaya başlamıştı (bir koşumda `%APPDATA%` altında
gerçekten oluştu, silindi). Koşum takımı artık `SAVE_FILE`'ı geçici dizine yönlendiriyor.

### ✅ Oyun testi düzeltmeleri (2026-09-28, kullanıcı geri bildirimi)

Oyunu elle oynayınca çıkan üç somut sorun + istenen dil desteği:

| # | Sorun | Çözüm |
|---|---|---|
| G1 | Görev çubuğunda ve pencerede oyunun logosu görünmüyordu | `pygame.display.set_icon` + Windows'ta `SetCurrentProcessExplicitAppUserModelID`. Kimlik ayarlanmazsa Windows pencereyi python.exe ile gruplayıp Python ikonunu gösteriyor. Kökteki `icon.png` 2048×2048 ve **pakete girmiyor**; `assets/icon64.png` üretildi (11 KB, assets ile birlikte paketleniyor) |
| G2 | Envanterde giyilenleri görmek için hangi tuşa basılacağı belli değildi | Pasif sekmenin üstünde yanıp sönen **[TAB]** rozeti; alt ipucu satırı sekmeye göre değişiyor ve büyütüldü |
| G3 | **Mana taşı alınca hız botu çıkıyordu** | Altı aksesuarın hepsi tek `"ring"` yuvasındaydı. Yuvalar türe ayrıldı: `weapon / armor / boots / ring / amulet`. Bot artık ayrı yuvada, yüzük ve muska da öyle |
| G4 | Çok dilli destek istendi | Aşağıya bakınız |

#### Dil desteği (TR / EN / DE / RU / AR)

Tüm metinler `assets/locales/<kod>.json` dosyalarına taşındı — **333 anahtar × 5 dil**.
Ayarlar menüsünde ok tuşlarıyla dil değişiyor, seçim kayıtla birlikte saklanıyor.

| Konu | Karar / bulgu |
|---|---|
| Çıkarma yöntemi | 99 diyalog satırını elle taşımak yazım ve kodlama hatası riskliydi (konsol cp1254 Türkçe'yi bozuyor). `tools/extract_locale.py` diyalogları ve adları, `tools/keyify_ui.py` arayüz metinlerini **açık eşleme listesiyle** anahtarladı; her ikisi de yazmadan önce `ast.parse` ile doğruluyor |
| İlk deneme başarısızlığı | Genel regex `ITEMS`/`ABILITIES` tablolarını bozdu ve `f.get("water_crystal")` gibi **bayrak adlarını** da çevirdi. Betik daraltıldı, tablolar elle düzenlendi |
| Yedek davranış | Python tablolarındaki Türkçe metinler kodda duruyor: dil dosyası bulunamazsa oyun yine okunur kalıyor. Eksik anahtar Türkçe'ye, o da yoksa anahtarın kendisine düşüyor |
| Font | Cinzel/MedievalSharp **Kiril ve Arap harflerini içermiyor**. `FontManager` artık dile göre aday listesi kullanıyor ve seçilen fontu o dilin alfabesiyle sınıyor |
| Glif tespiti (üç kez düzeltildi) | `font.metrics()` eksik glif için de değer döndürüyor; genişlik ölçümü de (glif yer ayırıyor, çizmiyor); "hiç piksel yok" ölçütü Almendra'yı yakalıyor ama **Cinzel'i kaçırıyor** — Cinzel eksik harfi boş değil **kutu** olarak çiziyor. Doğru yöntem: her harfin görüntüsünü, kesinlikle eksik olan bir kod noktasının görüntüsüyle karşılaştırmak |
| Arapça yazı yönü | Ölçüldü: pygame'in bu sürümünde `set_direction` **yok**; SDL_ttf harfleri doğru birleştiriyor (HarfBuzz) ama metni **soldan sağa** diziyor — `"المستوى 3"` çizilirken rakam kelimenin sağına ekleniyor, oysa solunda olmalı. `_rtl_reorder()` sözcük sırasını düzeltiyor; `python-bidi` kuruluysa tam Unicode algoritması kullanılıyor |
| Türkçe düzeltmeleri | Kaynak metinlerde eksik diakritikler vardı ("Saglik Iksiri" → "Sağlık İksiri", "Golge Yay" → "Gölge Yay"); hepsi düzeltildi |

**Arapça sınırı:** `python-bidi` kurulu değilse karışık yönlü metinler (örn. `[WASD]حركة`)
kusurlu dizilebilir. Saf Arapça cümleler doğru görünüyor. `pip install python-bidi` ile
tam Unicode bidi algoritmasına geçiliyor — kod bunu kendiliğinden algılıyor.

**Testler:** `tests/test_locales.py` (11 test) her dilde her anahtarın varlığını, `%d` yer
tutucularının tutarlılığını, eksik anahtarın Türkçe'ye düşmesini, RTL sıralamasını ve
**arayüzde çeviriden geçmemiş Türkçe metin kalmadığını** doğruluyor.

### ✅ Çizim ve görev genişlemesi (2026-09-28, kullanıcı önerisi)

Oyun testinde "moblar ve karakterlerin çizimi iyileştirilebilir, görevler artırılabilir"
denmişti. İkisi de yapıldı.

#### Çizim

| Konu | Değişiklik |
|---|---|
| Sistemik | Her sprite artık **taban gölgesi** ve **koyu kontur** alıyor (`PA._finish`). Karakterler zeminde yüzüyormuş gibi durmuyor ve karanlık haritalarda arka plandan ayrışıyorlar |
| Animasyon | Sürekli `sin(frame)` yerine **8 ayrık poz** (`PA.anim`): hem piksel sanatına yakışan basamaklı hareket, hem de sprite'ların önbelleğe alınabilmesi. Önceden her karede yeni yüzey üretiliyordu |
| Düşmanlar | Hepsi yeniden çizildi. Kurt, domuz ve akrep neredeyse aynı kahverengi lekelerdi; artık dört ayaklılar yandan (baş solda, kulak/burun/kuyruk/4 bacak), golem çatlaklı taş bloğu, akrep kıvrık kuyruk + kıskaç, gölge şövalyesi boynuzlu miğfer + pelerin |
| NPC'ler | Hepsi aynı gövdeydi, sadece renk değişiyordu. **14 meslek silueti**: muhafız (miğfer+mızrak+kalkan), şövalye (tüylü miğfer), yaşlı (sakal+asa), kâhin (kukuleta+yörünge), çiftçi (hasır şapka+dirgen), demirci (önlük+çekiç), hancı (önlük+bardak), balıkçı (olta), münzevi, kâtip (kitap), çocuk (küçük gövde), gezgin (sırt çantası), ruh (yarı saydam) |
| Denetim | `tools/sprite_sheet.py` tüm sprite'ları 3× büyütülmüş tabloda çıkarıyor — çizim değişiklikleri göz ile denetlenebiliyor |

#### Görevler

Yan görev sayısı **3 → 8**, üstelik artık **ödül veriyorlar** (önceden hiç ödül yoktu).

| Görev | Hedef | Ödül |
|---|---|---|
| Parşömen Avı | 3 parşömen | 80 altın + 60 XP |
| Domuz Avı | 3 domuz | 50 + 40 |
| Balıkçı Yardımı | Riva ile konuş | 40 + 30 |
| **Kurt Sürüsü** | 5 kurt | 70 + 70 |
| **Kemik Tarlası** | 6 iskelet | 90 + 90 |
| **Taş Bekçiler** | 2 golem | 120 + 120 |
| **Bataklığın Sesi** | Cadıyla konuş | 45 + 35 |
| **Uzletteki Bilge** | Münzeviyi bul | 45 + 35 |

- Görevler artık `SIDE_QUESTS` tablosunda: **yeni görev eklemek tek satır** (ilerleme
  fonksiyonu + ödül). Yan panel ve görev günlüğü tablodan üretiliyor.
- Öldürme sayacı türe göre genelleştirildi (`kill_<tür>`); eskiden yalnızca domuz sayılıyordu.
- **İ5 kısmen:** işi olan NPC'nin üstünde altın sarısı `!` işareti. Kâhin, elinde kristal
  yokken işaret göstermiyor — oyuncuyu boşuna yürütmesin.
- Görev günlüğü iki sütuna ayrıldı (solda ana hikâye, sağda 8 yan görev); tek sütuna sığmıyordu.

**Testin yakaladığı hata:** Yeni `kill_<tür>` sayaçları ve `sqpaid_<görev>` ödül işaretleri
önceden tanımlı bayraklar olmadığı için `load_game` bunları **atıyordu** — kayıt yükleyince
yan görev ilerlemesi sıfırlanıyor, ödüller tekrar verilebiliyordu. Yükleyici bu iki önekli
anahtarı da kabul ediyor artık; regresyon testi eklendi.

### ✅ Ekonomi ve düşman davranışları (2026-09-29)

#### İ7 — Dükkân

Altın toplanıyordu ama harcanacak yer yoktu; yan görev ödülleri de altın verdiği için
ekonominin işlevsizliği daha görünür hâle gelmişti.

| Konu | Karar |
|---|---|
| Dükkâncılar | **Demirci Boran** silah/zırh satıyor, **Hancı Mira** iksir/aksesuar satıyor ve konaklama sunuyor (18 altın → HP+MP tam dolar) |
| Erişim | Dükkâncıya `E` basmak doğrudan dükkânı açıyor. Üstlerinde altın para işareti var — görev `!` işaretinden ayrı |
| Arayüz | `[TAB]` ile Al/Sat sekmesi, ok tuşlarıyla seçim, `E` onay, `R` konaklama. Sınıfına uymayan ekipman **gri** gösteriliyor — parayı boşa vermeyesin |
| Fiyatlar | İksir 28-34, ekipman 85-280. Satış oranı %40 → alıp satarak para basılamıyor |

#### İ8 — Düşman davranışları

Çizimleri ayrışmıştı ama oynanışta hepsi aynı şekilde kovalıyordu. Artık dört davranış var:

| Davranış | Kimde | Ne yapar |
|---|---|---|
| `melee` | slime, iskelet, domuz, golem, gölge şövalyesi | Yanaşır, telegraflı vurur (eski davranış) |
| `ranged` | **akrep**, Malachar | 5-7 kare mesafeden mermi atar; oyuncu yanaşınca geri çekilir (Malachar hem yakın hem uzak dövüşür) |
| `skittish` | **goblin** | Canı %30'un altına düşünce kaçar |
| `pack` | **kurt, buz kurdu** | Yalnızken 2 karede durur, yanaşmaya çekinir; yanında sürüsü varsa cesaretlenip saldırır |

**Testin yakaladığı hata:** Menzilli düşmanlara mermi verdim ama `_update_projs` yalnızca
düşman çarpışmalarını kontrol ediyordu — **düşman mermileri oyuncunun içinden geçip gidiyordu**.
Mermiler artık sahibine göre ayrılıyor; oyuncuya hasar veren tek bir yol var
(`_player_take_hit`), yakın dövüş de aynı yolu kullanıyor.

`tests/test_shop.py` (11) + davranış testleri (7): sürüdeki kurtların yanaştığı ama yalnız
kurdun çekindiği, yaralı goblinin kaçtığı, düşman mermisinin oyuncuya değdiği ama oyuncunun
kendi mermisinin değmediği doğrulanıyor.

### ✅ Çökme, sessizlik ve ekipman yuvaları (2026-09-29, kullanıcı geri bildirimi)

Kullanıcı iki sorun bildirdi: envanterde `E` her basışta oyunu çökertiyordu ve
oyundan hiç ses gelmiyordu. İkisini kovalarken üçüncü ve dördüncü sorun çıktı.

#### H1 — Envanterde `E` çökmesi

```
NameError: name 'fT_' is not defined     (pixel_rpg.py:3925, _inv_use_item)
```

Yerelleştirme geçişinde bir arama-değiştirme f-string'i yutmuş: `f"Giyildi!"`
→ `fT_("ui.equipped_msg")`. Dört yerde aynı kaza vardı. Sözdizimi geçerli
olduğu için ne import ne de 106 test bunu gördü — hata ancak o satır
**çalışınca** ortaya çıkıyordu.

Tek tek düzeltmek yetmezdi; aynı kaza başka yerde de olabilirdi. Modülün
tamamı artık `symtable` ile taranıyor: bir fonksiyon modülde var olmayan bir
global ismi kullanıyorsa test kırılıyor. Tarayıcının kendisi de test ediliyor
(bilinen bir yazım hatasını yakalayabiliyor mu?).

#### H2 — Oyunda hiç ses yok

Asıl neden kodun içinde saklıydı:

```python
def _make(cls, ...):
    try:
        import numpy as np          # <-- kurulu degil
        ...
    except Exception: return None   # <-- hata sessizce yutuluyor
```

`numpy` kurulu olmadığı için **18 efektin ve 7 müzik temasının hepsi** `None`
dönüyor, ses bankası boş kalıyor ve oyun sessizce susuyordu. Ses ayarları
(80/80/60) sorunun kaynağı değildi.

| Konu | Karar |
|---|---|
| Çözüm | numpy kurmak yerine sentez **saf Python**'a taşındı: örnekler stdlib `array` ile üretilip `mixer.Sound(buffer=...)`e veriliyor |
| Neden | Oyun ek bağımlılık istemiyor, PyInstaller çıktısı küçük kalıyor, `requirements.txt` yalnız pygame |
| Biçim | Mixer'in **gerçekten açtığı** hız/kanal `get_init()` ile okunuyor; cihaz 48 kHz açarsa ses tiz çalmıyor |
| Sessizlik artık sessiz değil | Hiçbir ses üretilemezse oyun nedenini `stderr`'e yazıyor ve `_fail` alanında tutuyor |
| Ek iyileştirme | Akorlara 6 ms giriş/çıkış rampası — eskiden her akor "tık" ile kesiliyordu |
| Maliyet | Açılışta 194 ms (toplam açılış 361 ms). Müzik teması ilk çalışında 50-90 ms, sonra önbellekten |

#### H3 — Yeni karakterde bot/muska takmak çöküyordu

Yeni testler yazılırken çıktı. Yuvalar 3'ten 5'e çıkarılmıştı ama
`PlayerStats.__init__` hâlâ elle `{"weapon","armor","ring"}` yazıyordu:

```python
self.equipment = {"weapon":None,"armor":None,"ring":None}   # boots/amulet YOK
```

Yani **yeni başlayan** bir karakterde hız botu ya da mana taşı takmak
`KeyError` veriyordu. Kayıttan yüklenen oyunlarda sorun yoktu (yükleyici beş
yuvayı da kuruyor), bu yüzden kullanıcı henüz çarpmamıştı. Sözlük artık
`EQUIP_SLOTS`'tan türetiliyor — iki liste bir daha ayrışamaz.

#### H4 — Sınıfına uymayan ekipman eşyayı yok ediyordu

`equip()` hem "yuvadan çıkan eşya"yı hem de hata metnini **aynı dönüş
değerinde** taşıyordu. Büyücüyle plaka zırh giymeye çalışınca:

```
önce : ['plate_mail']
sonra: ['Bu ekipmani mage kullanamaz']     <-- zirh yok oldu
```

Çağıran hata cümlesini eşya sanıp envantere koyuyordu. Neden artık ayrı bir
`equip_reason()` metodunda ve çeviri anahtarı döndürüyor; `equip()` yalnız
yuvadan çıkan eşyayı veriyor. Ayrıca takılı eşyayı tekrar seçmek onu artık
envantere geri koyuyor (eskiden kayboluyordu).

`tests/test_inventory.py` (13) + `tests/test_sound.py` (12) +
`tests/test_source_sanity.py` (8): her sınıfın her eşyayı kullanabildiği, ses
bankasının dolu **ve sessiz olmadığı**, beş yuvanın bağımsız çalıştığı ve
modülde tanımsız isim kalmadığı doğrulanıyor.

### ✅ Mini harita (2026-09-29)

Faz 5'in kalan içerik maddesi. Sağ üst köşede, `M` ile açılıp kapanıyor,
tercih ayarlarda saklanıyor (F1 → Mini Harita).

| Konu | Karar |
|---|---|
| Renkler | Elle renk tablosu yok: her kare türünün rengi **asıl dokusunun ortalaması**. Doku değişirse mini harita kendiliğinden uyuyor |
| Okunabilirlik | Ortalamalar olduğu gibi kullanılınca harita okunmuyordu — oyunun paleti koyu. Yürünen kareler ×1.7 açılıyor, engeller ×0.45 koyulaşıyor. Amaç sadakat değil, **yolun görünmesi** |
| İşaretler | Mor = çıkışlar, altın = sandıklar, camgöbeği = NPC, kırmızı = yaşayan düşman, beyaz nabız = oyuncu |
| Başarım | Zemin harita başına bir kez çizilip önbelleğe alınıyor; her karede yalnız işaretler çiziliyor |
| Bayatlama | Sandık karesi açılınca zemine dönüşüyor. Zemin katmanında sandıklar **hiç** çizilmiyor, işaret olarak çiziliyor — önbellek bayatlamıyor |

**Yerleşim çakışması:** Mini harita ilk konulduğunda sağ üstteki kontrol
ipuçlarını tamamen örtüyordu — ekran görüntüsünde görüldü. İpuçları sol HUD
panelinin altına taşındı (ve `[M]Harita` satırı eklendi). Çakışmayı kalıcı
yakalamak için iki katman ayrı yüzeylere çizilip ortak boyanan piksel
sayılıyor; renk tahmini gerekmiyor.

`tests/test_minimap.py` (13): her haritanın ekrana sığdığı, yürünen karelerin
engellerden parlak olduğu, oyuncu noktasının doğru yöne kaydığı, ölen düşman
ve açılan sandık işaretlerinin kaybolduğu, zeminin önbelleğe alındığı ve
panelin HUD ile yetenek çubuğunu örtmediği doğrulanıyor.

### ✅ Harita geçitleri ve sıkışma hatası (2026-10-01, kullanıcı geri bildirimi)

Kullanıcı nehir haritasından köye dönerken **iki harita arasında sıkışıyordu**:
duvara takılıyor, bir adım atsa yine batıya gönderiliyordu. Ölçtüm — geçişe
basmadan ulaşılabilen kare sayısı **1**. Gerçekten hapis.

Üç hata üst üste binmişti:

| # | Hata | Neden görünmedi |
|---|---|---|
| 1 | Köyün ana yolları `T.STONE` ile çiziliyordu, ama STONE mağara duvarı — **yollar yürünemezdi** | Ekranda yol gibi görünüyor; kimse üstünden geçmeyi denememiş |
| 2 | Varış noktası (3,24) o duvarın üstünde olduğu için `_snap` oyuncuyu (2,24)'e taşıyordu — **geçiş karesinin ta kendisi** | `_snap` yalnız "yürünebilir mi" diye bakıyordu |
| 3 | Geçiş şeritleri kenar boyunca 6-10 kare uzunluktaydı, o yüzden o karenin **bütün** yürünebilir komşuları da geçişti | Şeritler haritayı bağlamak için fazlasıyla geniş tutulmuştu |

#### Yapılanlar

| Konu | Karar |
|---|---|
| `T.ROAD` | Yürünebilir arnavut kaldırımı. Köy yolları artık gerçekten yol; `T.STONE` mağara duvarı olarak kalıyor |
| `T.GATE` | Geçişin kendisi bir kare türü: taş çerçeveli karanlık bir açıklık. Dört kenarı simetrik, böylece yan yana üç kare tek bir geçit ağzı gibi okunuyor |
| Geçit boyutu | Kenar şeridi (6-10 kare) → **3 kare**, tam sınırda. Sınırın birkaç kare önünde duran şeridin bıraktığı boşluk kalktı |
| Koridor | Geçitten içeri 3 kare genişliğinde çerçeveli bir koridor açılıyor ve **açık araziye değene kadar** uzuyor. Yalnızca en dıştaki kare geçişi tetikliyor — koridorda yürümek haritayı değiştirmiyor |
| Kenar kapatma | `_seal_border` her haritanın kenarını haritanın kendi engeliyle (ormanda ağaç, mağarada kaya) kapatıyor. Çıkış yalnızca geçitlerden |
| Varış | `_arrival_tile`: yürünebilir **ve** bir kare yakınında geçiş olmayan en yakın kare. Geçişe düşmek ya da bitişik doğmak artık imkânsız |
| Görsel | Geniş mor bant gitti; geçit karesi kapı gibi çiziliyor, ok kehribar rengine döndü |

#### Ölçüm

| | Önce | Sonra |
|---|---|---|
| Köy–nehir dönüşünde serbest alan | **1 kare** | 2504 kare |
| Haritadaki geçiş karesi (köy) | 23 | 12 |
| Her geçit genişliği | 6-10 kare | 3 kare |
| Sıkışmalı bağlantı (28 bağlantı) | en az 1 | 0 |
| Kapanmamış harita kenarı | çok | 0 |

`tests/test_world.py` (15): 28 bağlantının hepsinde varışın geçiş karesi
olmadığı, geçişe bitişik olmadığı ve 200'den fazla kareye açıldığı; her
geçidin 3 kare olup sınırda durduğu; kenarların kapalı olduğu; köyün ana
yolunun yürünebildiği; mağara kayasının hâlâ blok olduğu ve köyden her
haritaya ulaşılabildiği doğrulanıyor.

### ⬜ Faz 5 — İçerik derinliği
- [x] İ5 — görev işaretçileri **ve mini harita yapıldı**
- [x] İ7 — dükkân ve ekonomi **yapıldı**
- [x] İ8 — düşman davranış çeşitliliği **yapıldı** (melee / ranged / skittish / pack)
- [ ] B10 — yerelleştirmeyi tamamla
- [ ] T1, T2 — modülerleştirme
- **Kabul:** Kullanılmayan çeviri anahtarı sayısı 21 → 0; tek dosya birden fazla modüle bölünmüş, testler geçiyor

---

## 4. Süreç günlüğü

| Tarih | Faz | Yapılan | Sonuç |
|---|---|---|---|
| 2026-09-27 | 0 | Kaynak yolu testleri yazıldı | 5 test geçti |
| 2026-09-27 | 0 | Otomatik oynanış koşum takımı + 24 ekran görüntülü duman testi | 7 test geçti, ölçümler alındı |
| 2026-09-27 | 0 | Kod ve görüntü incelemesi; 28 bulgu kayda geçti | Bu belge oluşturuldu |
| 2026-09-28 | 1 | 9 hata düzeltildi (B1-B8, E6, T3), fontlar devreye alındı | 21 test geçiyor (5'i yeni regresyon testi) |
| 2026-09-28 | 1 | Fontlar açılınca **B11** ortaya çıktı: Almendra `ğ/ş` yutuyor | Diyalog fontu değişti + `FontManager`'a Türkçe denetimi eklendi |
| 2026-09-28 | 1 | Faz 1 tek commit olarak kaydedildi (`faz-1-kritik-hatalar` dalı) | 21 test |
| 2026-09-28 | 2 | Yumuşak hareket, kamera takibi, çapraz yön, sabit adımlı zamanlama, UI/font önbelleği | Adım 32 → 3,2 px; hareketli kare %10 → %92; render 3,27 → 1,0 ms |
| 2026-09-28 | 2 | Ölçüm penceresi düzeltildi: çapraz ve kamera testleri sessizce anlamsız çalışıyordu | 16 duman testi + 8 yol testi geçiyor |
| 2026-09-28 | 2 | Faz 2 commit'lendi (`faz-2-akicilik` dalı) | 25 test |
| 2026-09-28 | 3 | Saldırı telegrafı, hit-stop/geri itme/sarsıntı, `[E]` rozeti, üst şerit duyuru, panel karartması, BFS yol bulma | `tests/test_combat_feel.py` ile 16 yeni test; toplam 41 test geçiyor |
| 2026-09-28 | 3 | Faz 3 commit'lendi (`faz-3-dovus-hissi` dalı) | 41 test |
| 2026-09-28 | 4 | Kayıt/yükleme, ışık halesi, harita dekorları, NPC gezinmesi, ses bağlantıları, daktilo diyalog | 24 yeni test; toplam 65 test geçiyor |
| 2026-09-28 | 4 | Testler kullanıcının gerçek kayıt dosyasını yazıyordu — koşum takımı geçici dizine yönlendirildi | Kirlenen dosya silindi |
| 2026-09-28 | 4 | Faz 4 commit'lendi (`faz-4-atmosfer` dalı) | 65 test |
| 2026-09-28 | — | **Oyun testi geri bildirimi:** pencere/görev çubuğu ikonu, envanterde TAB keşfedilebilirliği, ekipman yuvası çakışması | Üçü de düzeltildi |
| 2026-09-28 | — | 5 dilli yerelleştirme (TR/EN/DE/RU/AR), 333 anahtar | `tests/test_locales.py` ile 11 yeni test; toplam 77 test |
| 2026-09-28 | — | Tüm fazlar `main`'e alındı (fast-forward) | 5 dal zinciri |
| 2026-09-28 | — | Sprite'lara gölge+kontur+ayrık animasyon; düşman ve NPC çizimleri yenilendi | `tools/sprite_sheet.py` ile göz denetimi |
| 2026-09-28 | — | Yan görev tablosu: 3 → 8 görev, ödüller, `!` işaretçileri | 11 yeni test; toplam 88 test |
| 2026-09-29 | 5 | Dükkân sistemi (demirci + hancı, al/sat/konakla) ve düşman davranış çeşitliliği | 18 yeni test; toplam 106 test |
| 2026-09-29 | — | **Oyun testi geri bildirimi:** envanterde `E` çökmesi (`fT_`) ve oyunda hiç ses olmaması | İkisi de düzeltildi; ses numpy'sız sentezle çalışıyor |
| 2026-09-29 | — | Testler iki hata daha buldu: yeni karakterde bot/muska `KeyError`, uymayan ekipman eşyayı yok ediyor | 33 yeni test; toplam 139 test |
| 2026-09-29 | 5 | Mini harita (`M`), kontrol ipuçları sol panelin altına taşındı | 13 yeni test; toplam 152 test |
| 2026-10-01 | — | **Oyun testi geri bildirimi:** harita geçişlerinde sıkışma; geçiş bölgeleri yeniden tasarlandı | 15 yeni test; toplam 167 test |

---

## 5. Karar kaydı

| Karar | Gerekçe |
|---|---|
| Testler `unittest` ile yazıldı, `pytest` eklenmedi | Projeye yeni bağımlılık girmesin; `requirements.txt` oyun bağımlılıklarına ayrılmış durumda |
| Oyun döngüsü `pygame.display.flip` kancalanarak sürülüyor | `Game.run` tek parça sonsuz döngü; kaynak kodu değiştirmeden test etmenin en az müdahaleci yolu. Faz 5'te `update`/`draw` ayrımı yapılınca kanca kaldırılabilir |
| Testlerde `SDL_VIDEODRIVER=dummy` | Pencere açılmadan gerçek kare çizimi; CI'da da çalışır |
| Testler `CFG.save`'i devre dışı bırakır | Test koşumu kullanıcının `settings.json` dosyasını bozmasın |
| Ses sentezi numpy yerine saf Python | numpy kurulu değildi ve oyun bu yüzden sessizdi. Bağımlılık eklemek yerine stdlib `array` ile üretmek hem kurulumu hem paketlemeyi basit tutuyor; açılış maliyeti 194 ms |
| Üretilemeyen ses artık sessizce yutulmuyor | Asıl hata `except Exception: return None` yüzünden aylarca görünmedi. Ses bankası boş kalırsa neden `stderr`'e yazılıyor |
| Yuva/eşya listeleri tek kaynaktan türetiliyor | `EQUIP_SLOTS` elle kopyalandığı için yuva eklenince `PlayerStats` güncellenmeden kalmıştı |
| Mini harita renkleri doku ortalamasından | Elle tutulan bir renk tablosu, doku değiştiğinde sessizce yanlış kalır. Ortalama almak tabloyu gereksiz kılıyor; okunabilirlik için yalnız parlaklık ayarı uygulanıyor |
| `symtable` ile tanımsız isim taraması | `fT_` gibi yazım hataları sözdizimi denetiminden geçiyor; ancak o satır çalışınca patlıyor. Tarama, oynamadan yakalıyor |
