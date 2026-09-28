# Karanlık Taç'ın Laneti — Geliştirme Planı ve Süreç Takibi

> Bu belge oyunun **ölçülmüş** mevcut durumunu, tespit edilen sorunları ve aşama aşama
> yol haritasını tutar. Her fazın sonunda testleri çalıştırıp bu dosyayı güncelliyoruz.
> Böylece "neyi, neden, hangi kanıta dayanarak" değiştirdiğimiz kayıt altında kalır.

**Son güncelleme:** 2026-09-28 · **Oyun sürümü:** v5.0 · **Aktif faz:** Faz 3 (Faz 0-1-2 tamamlandı)

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
| B9 | 🟡 | Üretilen ama hiç çalınmayan sesler: `walk`, `equip`, `error`, `trap`, `freeze`, `boss_alert` | `pixel_rpg.py:232-251` | İlgili olaylara bağla (ayak sesi, ekipman, tuzak, boss girişi) |
| 🔸 B10 | 🟡 | Dil seçeneği yarım: 36 çeviri anahtarının 21'i hiç kullanılmıyor; başlık, sınıf seçimi, ölüm/zafer ekranları sabit Türkçe | `pixel_rpg.py:63-143`, `:1833-1848` | Sabit metinleri `T_()` üzerinden geçir · **kısmen yapıldı:** Faz 1'de kullanılmayan anahtar 21 → 15 |
| ✅ B11 | 🟠 | **Almendra fontu `ğ` ve `ş` gliflerini içermiyor**, bu harfleri sessizce yutuyor: "Doğudaki … başla." → "Do udaki … ba la." Faz 1'de fontlar devreye alınırken ortaya çıktı; `font.metrics()` ve genişlik ölçümü bu durumu **yakalamıyor**, yalnızca çizilen pikseller yakalıyor | `tests/screenshots/_font_turkce.png` | Diyalog fontu MedievalSharp'a alındı; `FontManager` artık her adayı Türkçe alfabeyle sınayıp çizemeyeni eliyor |

### 2.2 Akıcılık

| ID | Şiddet | Bulgu | Kanıt | Öneri |
|---|---|---|---|---|
| ✅ A1 | 🔴 | **Kafes atlamalı hareket:** `_try_move` piksel konumunu anında hedefe atıyor, ara kare yok. Karakter 10 karede bir 32 px ışınlanıyor | ölçüm: adım = {32 px}, hareketli kare 5/402; `pixel_rpg.py:2277` | Kareler arası doğrusal geçiş: `move_progress` 0→1 ilerlerken `px/py` interpolasyonu + yürüme animasyonu |
| ✅ A2 | 🔴 | **Kamera sıçrıyor:** hedefe anında atanıyor | ölçüm: kamera adımı {32 px}; `pixel_rpg.py:2267` | Yumuşatma (`cam += (hedef-cam) * 0.15`) + küçük ölü bölge |
| ✅ A3 | 🟠 | Çapraz hareket yok; `elif` zinciri tek yön seçiyor, öncelik sol > sağ > yukarı > aşağı | ölçüm: ↓+→ → yalnız sağa; `pixel_rpg.py:2778-2781` | Yön vektörünü topla, çapraz hareketi de dene (duvara değince kaydır) |
| ✅ A4 | 🟠 | Tüm zamanlama **kare sayısına** bağlı (hareket gecikmesi, bekleme süreleri, dokunulmazlık). FPS düşerse oyun yavaşlar | `pixel_rpg.py:2782-2795` | `dt` tabanlı zamanlama |
| A5 | 🟠 | Düşman AI eksen-açgözlü: tek eksende ilerliyor, duvar köşesinde takılıyor; yol bulma yok (oysa BFS için `deque` projede zaten var) | `pixel_rpg.py:2540-2548`, `:1088` | Kısa menzilli BFS/A* + takılınca yan adım |
| ✅ A6 | 🟡 | `grad_bar` ve `panel` her karede piksel piksel çizgi çiziyor: HUD'da 3 bar + panel yüksekliği → kare başına ~1000 `draw.line` | `pixel_rpg.py:1738-1758`; ham kare 3,27 ms | Bar/panel yüzeylerini önbelleğe al, değişince yeniden üret |
| ✅ A7 | 🟡 | `NPC.draw` ve boss çizimi **her karede** `SysFont` çağırıyor | ölçüm: 1,0 çağrı/kare (tek NPC); `pixel_rpg.py:978`, `:1005` | Sınıf düzeyinde font önbelleği |

### 2.3 Etkileşim ve his

| ID | Şiddet | Bulgu | Kanıt | Öneri |
|---|---|---|---|---|
| E1 | 🔴 | Etkileşim ipucu yok: NPC/sandık yanındayken ekranda `[E]` göstergesi çıkmıyor; üstelik yalnızca tam karşı kare çalışıyor | `pixel_rpg.py:2559-2562` | Yakındaki hedefin üstünde yanıp sönen `[E]` rozeti + 1 karelik tolerans |
| E2 | 🟠 | Düşman saldırısı telegraflanmıyor: yan yana gelir gelmez otomatik hasar; hazırlanma animasyonu, uyarı yok. Üstelik **çaprazdan da** vuruyor (oyuncu çapraz gidemezken) | `pixel_rpg.py:2549` | Kısa "hazırlanma" fazı + saldırı animasyonu; çapraz vuruşu kaldır ya da oyuncuya da çapraz ver |
| E3 | 🟠 | Vuruş geri bildirimi zayıf: geri itme, kısa donma (hit-stop), ekran sarsıntısı yok | `pixel_rpg.py:2377-2385` | 3-5 karelik hit-stop + geri itme + boss vuruşunda hafif sarsıntı |
| E4 | 🟠 | Bölüm duyurusu **260 kare (~4,3 sn)** ekranın ortasını kaplıyor — savaşın tam ortasında bile | `19_saldiri.png`, `21_dusman_yapay_zeka.png`; `pixel_rpg.py:2301`, `:2855` | Süreyi kısalt, üst şeride taşı, savaşta ertele |
| E5 | 🟠 | Pencereler fazla şeffaf: envanter/görev günlüğünde arka plandaki dünya okunuyor; ölüm ekranında dünya hiç karartılmıyor | `11_envanter.png`, `13_gorev_gunlugu.png`, `23_olum.png` | Panel arkasına karartma katmanı (`alpha ~180`) |
| ✅ E6 | 🟡 | Diyalog sırasında yetenek çubuğu diyalog kutusuyla çakışıyor | `09_diyalog.png`; `pixel_rpg.py:2853` | Diyalogda alt HUD'u gizle |
| E7 | 🟡 | Diyalog daktilo efekti, portre ve konuşma sesi içermiyor; 4 satır birden beliriyor | `pixel_rpg.py:1936-1947` | Karakter karakter yazım + `E` ile anında tamamlama |
| E8 | 🟡 | Başlık ekranında `F1 Ayarlar` ipucu yazmıyor (çeviri anahtarı var, çizim yok); `ESC ile çıkış` da belirtilmemiş | `01_baslik.png`; `pixel_rpg.py:1848` | İpucu satırına ekle |

### 2.4 Sürükleyicilik ve içerik

| ID | Şiddet | Bulgu | Kanıt | Öneri |
|---|---|---|---|---|
| İ1 | 🔴 | **Kayıt/yükleme yok.** Ölünce her şey baştan; oyuncu ikinci oturuma dönemiyor | `pixel_rpg.py:2213` (`_reset`) | `%APPDATA%` altına slot bazlı JSON kayıt + başlık ekranında "Devam Et" |
| İ2 | 🟠 | Haritalar boş hissettiriyor: geniş çim alanlar, dekor nesnesi yok (ağaç, çit, fener, varil, çiçek, tabela) | `05_koy_ashveil.png` | Dekor tile'ları + rastgele serpiştirme; köy meydanına kuyu/pazar |
| İ3 | 🟠 | Karanlık Orman okunamayacak kadar karanlık: koyu tile paleti + `ambient` katmanı üst üste biniyor | `19_saldiri.png`, `21_dusman_yapay_zeka.png`; `pixel_rpg.py:1036-1037` | Ambient alfasını düşür, oyuncunun çevresine ışık halesi (vignette) ekle |
| İ4 | 🟠 | NPC'ler tamamen hareketsiz; boşta gezinme/iş yapma yok | `pixel_rpg.py:970-982` | Basit boşta gezinme (kendi bölgesinde 1-2 kare) + oyuncuya dönme |
| İ5 | 🟠 | Yön bulma zayıf: görev işaretçisi (`!` / `?`), mini harita ya da pusula yok | `05_koy_ashveil.png` | NPC üstünde görev simgesi + köşede mini harita |
| İ6 | 🟡 | Ses peyzajı yok: ayak sesi, ortam sesi yok; müzik harita geçişinde sert kesiliyor ve **her geçişte numpy ile yeniden üretiliyor** | `pixel_rpg.py:273-318`, `:2293` | Temaları bir kez üret + önbellekle, geçişte çapraz sönümleme |
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

### ⬜ Faz 3 — Dövüş hissi ve arayüz düzeni
- [ ] E1 — `[E]` etkileşim rozeti
- [ ] E2 — düşman saldırı telegrafı, çapraz vuruş düzeltmesi
- [ ] E3 — hit-stop, geri itme, ekran sarsıntısı
- [ ] E4 — bölüm duyurusunu üst şeride taşı
- [ ] E5, E6 — panel karartması, diyalogda HUD gizleme
- [ ] A5 — düşman yol bulma
- **Kabul:** Duman testine "saldırı sonrası düşman geri itildi" ve "panel açıkken arka plan karartıldı" doğrulamaları eklenir

### ⬜ Faz 4 — Atmosfer ve süreklilik
- [ ] İ1 — kayıt/yükleme + "Devam Et"
- [ ] İ3 — orman/mağara aydınlatması, oyuncu ışık halesi
- [ ] İ2 — harita dekorları
- [ ] İ4 — NPC boşta gezinme
- [ ] İ6, B9 — ayak sesi, ortam sesleri, müzik çapraz sönümleme
- [ ] E7 — daktilo efektli diyalog
- **Kabul:** Kaydet → çık → yükle turu testte doğrulanır; yeni ekran görüntüleriyle önce/sonra karşılaştırması

### ⬜ Faz 5 — İçerik derinliği
- [ ] İ5 — görev işaretçileri + mini harita
- [ ] İ7 — dükkân ve ekonomi
- [ ] İ8 — düşman davranış çeşitliliği
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

---

## 5. Karar kaydı

| Karar | Gerekçe |
|---|---|
| Testler `unittest` ile yazıldı, `pytest` eklenmedi | Projeye yeni bağımlılık girmesin; `requirements.txt` oyun bağımlılıklarına ayrılmış durumda |
| Oyun döngüsü `pygame.display.flip` kancalanarak sürülüyor | `Game.run` tek parça sonsuz döngü; kaynak kodu değiştirmeden test etmenin en az müdahaleci yolu. Faz 5'te `update`/`draw` ayrımı yapılınca kanca kaldırılabilir |
| Testlerde `SDL_VIDEODRIVER=dummy` | Pencere açılmadan gerçek kare çizimi; CI'da da çalışır |
| Testler `CFG.save`'i devre dışı bırakır | Test koşumu kullanıcının `settings.json` dosyasını bozmasın |
