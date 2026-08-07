# İlerleme Günlüğü — Otonom Otopark Projesi

Bu dosya, her adımda **ne yaptığımı, neden yaptığımı ve nasıl yaptığımı**
kaydettiğim bir öğrenme günlüğü. PROJE_BRIEF_OTOPARK.md'deki 12 adımlık
sıraya göre ilerliyoruz.

---

## "Gereklilikler" sayfası eklendi (in-app kurulum) + evrensel_toolset genelleştirildi (2026-08-07)

### Ne yaptım
1. **evrensel_toolset genelleştirildi (araç varsayımı kaldırıldı):**
   Ön-Etiketleme aracı eskiden COCO'nun sadece "car/truck/bus"
   class'larını arayacak şekilde SABİT kodlanmıştı -- yalnızca araç
   projeleri için işe yarıyordu. Artık kullanıcı hangi kaynak COCO
   class'ını (`person`, `dog,cat`, hiçbiri...) arayacağını arayüzden
   giriyor (boşsa en güvenilir kutu direkt kullanılır); alan yazarken
   COCO'nun 80 class'ından öneri de gösteriyor (virgülle ayrılmış
   yazımda sadece son/tamamlanmamış parçaya göre filtreleniyor). Model
   Eğitimi'nde "Başlangıç Modeli" artık zorunlu değil (boş bırakılırsa
   backend zaten yolo11n.pt'ye düşüyordu, sadece UI gereksiz yere
   engelliyordu) ve ".yaml" yazarak sıfırdan eğitime başlanabileceği
   açıklandı. Tüm "araç/clio3/clio4/egea" örnek metinleri nesne-nötr
   hale getirildi (Etiketleme, Veri Birleştir, Model Eğitimi tooltip'leri).
2. **Yeni "Gereklilikler" sayfası (hem evrensel_toolset hem
   etiketleme_arayuzu'nde):** hub'da yeni bir kart -- hangi kütüphanelerin
   kurulu/eksik olduğunu tablo halinde gösteriyor, GPU'yu (`nvidia-smi`)
   otomatik algılıyor, "EKSİKLERİ KUR" butonuyla arka planda
   `sys.executable -m pip install ...` çalıştırıp çıktıyı canlı log
   olarak akıtıyor (Model Eğitimi'ndeki canlı log deseniyle aynı arka
   plan thread + polling mimarisi). torch/torchvision GPU'ya göre
   CUDA'lı (cu121) ya da CPU'lu kuruluyor. yolo11n.pt yoksa
   `YOLO("yolo11n.pt")` çağrılarak otomatik indiriliyor. evrensel_toolset'te
   Fusion paketleri (fast-plate-ocr, pillow-heif) "opsiyonel" grubunda
   ayrı bir kutucukla; etiketleme_arayuzu'nde Fusion her zaman açık
   olduğu için hepsi tek "zorunlu" grupta.
3. **evrensel_toolset'e de KURULUM.bat/BASLAT.bat/_kurulum_kontrol.py
   eklendi** (etiketleme_arayuzu'nde zaten vardı, bu kopyada eksikti) --
   ilk açılış için gereken flask/pywebview/numpy/Pillow'u kurar (bunlar
   kurulu olmadan "Gereklilikler" sayfası da açılamaz, çünkü app.py'nin
   kendisi bunlara ihtiyaç duyuyor). KURULUM.bat sonunda "Gereklilikler"
   sayfasına da işaret ediyor.

### Test durumu
`ast.parse` (her iki app.py) + `node --check` (her iki gereklilikler.js)
temiz. Flask test client ile: her iki projede `/gereklilikler` ve
`/api/gereklilik/durum` 200 + doğru paket listesi/GPU/yolo11n durumu
döndü. `_pip_kur` gerçek bir pip komutuyla (zaten kurulu "pip" paketiyle)
test edildi, canlı log satır satır doğru yakalandı. `/api/gereklilik/
kur_baslat` + `kur_durum` akışı sahte (hızlı) bir arka plan fonksiyonuyla
uçtan uca test edildi -- "çalışıyor" durumu, bitince "tamamlandı", ve
kurulum sürerken tekrar başlatma isteğinin 400 ile reddedildiği
doğrulandı. Gerçek bir torch/ultralytics kurulumu (dakikalar sürebildiği
ve büyük indirme gerektirdiği için) bu oturumda tetiklenmedi -- kullanıcı
kendi PC'sinde denemeli.

### Neden
Kullanıcı önce evrensel_toolset'in GERÇEKTEN proje-nötr olmasını istedi
("herhangi biri için, fine-tuning'le başlamak istemiyor olabilir" gibi),
sonra "gerekenler diye bir kutu istiyorum, bir tuşla kütüphaneleri/
modelleri/COCO'yu kurabilsin" dedi -- "iyi olursa benimkine de ekle"
talimatıyla aynı özellik iki projeye de taşındı.

---

## Renk tespiti eklendi (eğitimsiz, HSV tabanlı) -- her yere entegre edildi (2026-08-07)

### Ne yaptım
PROJE_BRIEF'te planlanıp hiç uygulanmamış "renk tespiti" (bileşen 3)
eksiğini kapattım. Yeni model EĞİTMEK gerekmiyor -- `_renk_tespit_et()`
adında yeni bir yardımcı fonksiyon (`app.py`), tespit kutusunun ORTA
%50'lik bölgesini (kenar/tekerlek/cam/gölge payını dışarıda bırakmak
için) HSV renk uzayına çevirip medyan ton/doygunluk/parlaklık
değerlerine bakarak "beyaz / siyah / gri / gümüş / kırmızı / turuncu /
sarı / yeşil / turkuaz / mavi / mor" isimlerinden birini döndürüyor.
Medyan kullanıldı (ortalama değil) çünkü birkaç aşırı parlak/karanlık
piksel (yansıma/gölge) ortalamayı kolayca çarpıtabiliyordu.

Entegre edildiği yerler:
- **Fusion Tekli Görsel** (`/api/fusion/calistir`): her araç kutusu
  için hesaplanıp sonuç JSON'una (`renk`) ve ekrandaki tabloya eklendi.
- **Fusion Sürekli İzleme** (`_izleme_dongusu`): renk, görsel
  yakalamayla (`gorsel_kare`) AYNI karede hesaplanıyor -- yani hangi
  kare "en iyi/en net görünüm" olarak donduruluysa, renk de o karedeki
  kaporta rengini yansıtıyor.
- **Model Test** (Tekli Görsel + Klasör Toplu): tespit listesine renk
  bilgisi eklendi (`sonuc.orig_img`/`tahmin.orig_img` kullanılarak,
  dosyayı ayrıca okumaya gerek kalmadan).
- **Veritabanı**: `tespitler` tablosuna `renk TEXT` kolonu eklendi
  (eski DB dosyaları için `ALTER TABLE` ile otomatik migration, hata
  vermeden atlanıyor). `_fusion_db_kaydet()` artık renk de yazıyor.
- **Veritabanı Sorgu arayüzü**: yeni bağımsız "renk" arama kutusu
  (marka/model ve plaka kutularıyla aynı canlı/debounce'lu arama
  mantığında), backend `/api/veritabani/ara`'ya `renk` parametresi
  eklendi, sonuç tablosuna "Renk" sütunu eklendi.

### Test durumu
`ast.parse` (app.py) + `node --check` (fusion.js, test.js,
veritabani.js) temiz. Fonksiyonel testler: senkron renk kutuları
(beyaz/kırmızı/mavi/siyah) `_renk_tespit_et()`'e verilip doğru isimler
döndüğü doğrulandı; Flask test client ile `/api/veritabani/ara?renk=...`
gerçek bir kayıt ekleyip filtrelenmiş sonuçta doğru döndüğü, `/veritabani`
ve `/fusion` sayfalarının 200 döndüğü doğrulandı. Gerçek bir video/foto
ile kullanıcı tarafından henüz denenmedi.

### Neden
Kullanıcı, PROJE_BRIEF'te planlanmış ama hiç yapılmamış bu eksiği
sorunca ("renk tespiti zor mu?") -- eğitim gerektirmediği, sadece
mevcut tespit kutusundan HSV hesaplaması olduğu için basit olduğu
anlatıldı, ardından "evet ekle, gerekli her yerdekini güncelle" isteğiyle
tüm arayüzlere (Fusion, Model Test, Veritabanı Sorgu) uçtan uca eklendi.

---

## Fusion'a Webcam modu eklendi + İzleme'de 2 gerçek hata düzeltildi (2026-08-07)

### Ne yaptım
1. `_izleme_dongusu`'na `webcam_mi` parametresi eklendi -- webcam
   modunda `cv2.VideoCapture(0, CAP_DSHOW)` (fallback: `VideoCapture(0)`)
   ile açılıyor, Model Test'teki webcam mantığıyla aynı hata mesajları
   ve "ardarda başarısız okuma" toleransı kullanılıyor. Video dosyası
   modunda "kare gelmedi" = dosya bitti demekken, webcam modunda bu
   geçici bir okuma aksaklığı sayılıyor, döngü kırılmıyor.
2. Canlı önizleme: her karede güncel takip kutuları + o anki en iyi
   bilinen sınıf/plaka bilgisiyle çizilmiş bir görüntü JPEG'e kodlanıp
   `IZLEME_DURUMU["son_kare_jpeg"]`'e yazılıyor; yeni
   `/api/fusion/izleme_webcam_stream` route'u bunu MJPEG akışı olarak
   tarayıcıya veriyor (Model Test'teki `webcam_stream` ile aynı desen).
3. `fusion.html`'e "Video Dosyası / Webcam" kaynak seçici (yeni
   `.izleme-kaynak-btn` sınıfı -- mevcut `.test-mod-btn` ile
   çakışmaması için AYRI bir sınıf kullanıldı, aksi halde üst
   sekmelerle (Tekli Görsel/Sürekli İzleme) aynı JS handler'a
   yakalanıp ikisi de bozulurdu), `fusion.js`'e kaynak state'i +
   webcam modunda dosya seçimini atlayan/`webcam: true` gönderen
   mantık eklendi.
4. **Ayrıca aynı oturumda kullanıcının gerçek videolarla bulduğu iki
   hata düzeltildi:** (a) kaydedilecek görsel eskiden HER karede
   koşulsuz üzerine yazılıyordu -- araç kadrajdan çıkarken görülen
   (genelde en kırpık/en kötü) son kareyi kalıcı kılıyordu. Artık
   SADECE en yüksek güvenli sınıflandırmanın yapıldığı karede
   kaydediliyor. (b) Bu bile yetmedi -- kutu kare kenarına değiyorsa
   (aracın sadece bir köşesi görünüyorsa) model bazen yanlışlıkla
   yüksek güven veriyordu. Artık kutu kenara değip değmediği de
   kontrol ediliyor: tam görünümlü bir kare zaten kaydedilmişse, kısmi
   görünümlü daha yüksek güvenli bir kare onun üzerine yazamıyor.

### Test durumu
`ast.parse` + `node --check` temiz. Flask test client ile:
`/api/fusion/izleme_baslat` (webcam=true, model yolu boş) → doğru hata,
gerçek (fake) model yollarıyla → `{"ok": true}` + arka planda başladı,
`/api/fusion/izleme_durum` doğru durumu döndü, `/fusion` sayfası 200.
Gerçek bir webcam ile kullanıcı tarafından henüz denenmedi.

### Neden
Kullanıcı gerçek videolarla İzleme'yi test ederken hem "aynı araç
farklı karelerde farklı etiketleniyor" (zaten çözülmüştü, sınıf zaten
en-iyi-güven mantığıyla saklanıyordu) hem "kayıtlar hep aracın
bariyerde yarı kadraj dışı olduğu anı gösteriyor" (gerçek bir hataydı,
görsel yakalama sınıf yakalamayla senkron değildi) sorunlarını
bildirdi. Webcam modu ise kullanıcının "Fusion'a da webcam testi ekle"
isteğiyle, `nevfel.txt`/`app.py`'deki "ileride webcam'e bağlama" planı
zaten önceden not edilmişti, bu oturumda gerçekleştirildi.

### Proje geneli durum taraması (aynı istekle birlikte yapıldı)
`nevfel.txt`'in istediği 5 araç (Etiketleme, Splitter, Augment, Eğitim,
Test) ve PROJE_BRIEF'teki çekirdek bileşenler (1-7) hepsi tamam. İki
gerçek eksik bulundu:
- **Renk tespiti (bileşen 3'ün yarısı)** -- PROJE_BRIEF'te "HSV ile,
  eğitimsiz" diye planlanmıştı ama kodda hiç uygulanmadı, DB şemasında
  da `renk` diye bir alan yok (`marka_model` rengi içermiyor). Küçük
  bir iş: tespit edilen araç kutusu içindeki baskın rengi HSV'de
  hesaplayıp DB'ye eklemek.
- **Giriş/çıkış yön takibi (bileşen 8)** -- PROJE_BRIEF'te baştan
  "opsiyonel/genişletme, vakit kalırsa" diye ayrılmıştı, yapılmadı,
  yapılmaması da tasarım gereği kabul edilebilir.

---

## Model Test: "Klasör (Toplu)" modu eklendi (2026-08-07)

### Ne yaptım
Kullanıcı, etiketsiz bir klasördeki (ör. elle indirilmiş gerçek araç
fotoğrafları) TÜM görselleri tek tek Görsel modunda açmadan, toplu
şekilde gözle kontrol edebileceği bir yol istedi. `app.py`'ye
`/api/test/klasor` route'u eklendi: bir klasördeki desteklenen tüm
görselleri (`jpg/jpeg/png/bmp/webp`, en fazla 500) sırayla modelden
geçirip her biri için tahmin kutuları çizilmiş bir çıktı görseli +
tespit listesi (sınıf adı + güven) üretiyor, hepsini tek bir JSON
yanıtında döndürüyor. `templates/test.html`'e yeni bir "Klasör (Toplu)"
sekmesi, `static/test.js`'e klasör seçme (native) + istek/render mantığı,
`static/style.css`'e `.klasor-galeri-grid`/`.klasor-kart` sınıfları
eklendi. Aynı zamanda kullanıcının test galerisi script'inde
(`kod/09_test_galerisi.py`) sorduğu iki soruna da (tahmin edilen
sınıfın metin olarak görünmemesi, aynı araca 2 örtüşen kutu/"çift
tespit") çözüm eklendi: her kartın altına ✓/✗ işaretli tam tahmin
listesi, ve yüksek IoU'lu örtüşen tahmin çiftleri için "⚠ Olası çift
tespit" uyarısı; kaçırılan bir GT kutusunun yerinde başka bir sınıf
tahmin edilmişse de "⚠ X yerine Y tahmin edilmiş" (sınıf karışıklığı)
notu ekleniyor.

### Test durumu
`ast.parse` + `node --check` temiz. Flask test client ile: model/klasör
boşken doğru hata mesajları, var olmayan klasörle doğru hata, `/test`
sayfası 200 döndü. Gerçek bir modelle/klasörle henüz kullanıcı
tarafından denenmedi.

### Neden
Kullanıcı, sahibinden gibi kaynaklardan elle indirdiği gerçek araç
fotoğraflarıyla modelin genel doğruluğunu hızlıca gözle taramak
istiyor -- CompCars test setinin (Metrikler modu, mAP ~0.99) gerçek
dünya fotoğraflarını ne kadar temsil ettiği ayrı bir soru, bu araç o
farkı gözle görmek için.

---

## Tek tıkla kurulum: KURULUM.bat + BASLAT.bat (2026-08-06)

### Ne yaptım
Kullanıcı, ev PC'sinde ve arayüzü kullanacak herkes için gerekli Python
kütüphanelerini tek tıkla kurabileceği bir yol istedi (elle `pip install`
yazmadan). `etiketleme_arayuzu/` altına iki `.bat` dosyası eklendi:
1. `KURULUM.bat` -- Python'un kurulu olup olmadığını kontrol ediyor, yoksa
   kullanıcıyı python.org'a yönlendirip duruyor. Varsa `.venv` sanal ortamı
   oluşturuyor, `nvidia-smi` ile NVIDIA GPU olup olmadığını otomatik
   algılamaya çalışıyor (bulamazsa kullanıcıya soruyor), GPU varsa CUDA'lı
   (cu121) PyTorch'u, yoksa CPU'lu sürümü kuruyor, sonra
   `requirements.txt`'teki geri kalan her şeyi (flask, ultralytics,
   opencv-python, fast-plate-ocr, pillow-heif, vb.) kuruyor.
2. `BASLAT.bat` -- `.venv`'i etkinleştirip `app.py`'yi çalıştırıyor;
   kurulum yapılmadan çalıştırılırsa açıkça uyarıyor.
Mevcut `requirements.txt` zaten güncel ve eksiksizdi (flask, pyyaml,
pywebview, Pillow, numpy, ultralytics, opencv-python, imageio-ffmpeg,
fast-plate-ocr[onnx], pillow-heif) -- değiştirmedim, sadece kurulumu
otomatikleştirdim.

### Test durumu
Sandbox Linux ortamı olduğu için `.bat` dosyaları burada gerçek anlamda
çalıştırılamadı (Windows'a özgü); syntax'ı elle satır satır gözden
geçirdim (venv/activate/pip akışı standart Windows batch kalıpları).
Kullanıcının kendi Windows PC'sinde `KURULUM.bat`'a çift tıklayarak
denemesi gerekiyor -- ilk çalıştırmada hata çıkarsa (özellikle GPU
algılama veya PATH sorunları) bildirmesi lazım.

### Neden
`kod/`, `test2.py` gibi dosyalarda geçen `pandas`/`scipy`/`easyocr`
kütüphaneleri sadece deneme scriptlerinde kullanılıyor, ana uygulamanın
(`etiketleme_arayuzu/app.py`) çalışması için gerekli değil -- bu yüzden
`requirements.txt`'e eklenmedi, kurulum sadece gerçekten çalışan ana
arayüz için gerekenleri indiriyor.

---

## Veritabanı Sorgu arayüzü eklendi (2026-08-06)

### Ne yaptım
Kullanıcı, CompCars galerisini gözden geçirirken paralelde `db/otogoz.db`
içindeki (Fusion/Sürekli İzleme'nin biriktirdiği) "tespitler" tablosunu
marka/model/plaka/yıl'a göre arayabileceği bir arayüz istedi.
1. `etiketleme_arayuzu/app.py`'ye yeni bölüm: `/veritabani` sayfası +
   `/api/veritabani/ara` endpoint'i. Tek arama kutusu `marka_model` VEYA
   `plaka` içinde (büyük/küçük harf duyarsız, `LIKE %...%`) arıyor, ayrı
   bir "yıl" alanı `tespit_zamani`'nin yıl kısmına göre filtreliyor.
   **Önemli not (kullanıcıya da arayüzde gösterildi):** veritabanı aracın
   ÜRETİM yılını tutmuyor, sadece o kaydın NE ZAMAN tespit edildiğini —
   "yıl" filtresi bu yüzden tespit zamanına göre çalışıyor.
2. `_veritabani_gorsel_url()`: DB'deki mutlak dosya yolunu, `static/
   fusion_ciktilari` altındaysa tarayıcıdan erişilebilir `/static/...`
   URL'sine çeviriyor (path traversal riski yok, sadece o klasörün
   altındaysa URL üretiyor).
3. `templates/veritabani.html` + `static/veritabani.js` + `style.css`'e
   `.db-*` sınıfları + `index.html`'e hub kartı eklendi. Sonuç tablosu:
   ID, tespit zamanı, küçük görsel, marka/model+güven+durum, plaka+güven
   +durum. Sayfa açılır açılmaz filtresiz son kayıtları gösteriyor.

### Test durumu
`ast.parse` + `node --check` temiz. Flask test client ile canlı test
edildi: `/veritabani` → 200, `/api/veritabani/ara` (filtresiz) → gerçek
33 kayıt döndü, `?q=fiat&yil=2026` → doğru şekilde 10 kayda filtrelendi
(hepsi fiat_egea + 2026 yılında tespit edilmiş). `gorsel_url` bu Linux
test ortamında Windows yollarını çözemediği için None döndü — bu bir
kod hatası değil, gerçek Windows makinede `pathlib.WindowsPath` doğru
şekilde `C:\...` yollarını çözecek.

---

## Model Eğitimi: workers + cache parametreleri eklendi (2026-08-06)

### Ne yaptım
Kullanıcı öğretmeninden "eğitim sırasında VRAM doluyor ama GPU'yu
zorlamıyor, fan çalışmıyor, workers'ı artırıp zorlaman daha iyi olur"
tavsiyesini almıştı. Sebebi: `model.train()` çağrısında `workers` hiç
belirtilmiyordu (ultralytics varsayılanı 8), CPU yeterince hızlı veri
hazırlayamazsa GPU her batch'te veri bekleyip boş kalıyor (VRAM dolu
görünse de kullanım düşük kalıyor).
- `app.py`: `ayarlar` sözlüğüne `workers` (varsayılan 8) ve `cache`
  (varsayılan `False`, `"ram"`/`"disk"` seçilebilir) eklendi,
  `model.train(...)` çağrısına `workers=` ve `cache=` parametreleri eklendi.
- `templates/egitim.html`: Gelişmiş Alanlar tablosuna `workers` (number
  input) ve `cache` (dropdown: kapalı/ram/disk) satırları eklendi, CPU
  çekirdek sayısına göre ayarlama tavsiyesi açıklama metninde.
- `static/egitim.js`: `GELISMIS_ALAN_ID_LISTESI` dizisine `"workers"` ve
  `"cache"` eklendi (generic .value okuma mekanizması zaten ikisi için
  de çalışıyor, özel bir işleme gerek yoktu).

### Test durumu
`ast.parse` + `node --check` temiz.

---

## Model Eğitimi: cos_lr, lr0, warmup_epochs eklendi (2026-08-06, devam)

### Ne yaptım
Kullanıcının hocası "fine-tune'da başta öğrenme oranını düşük tut, pretrained
ağırlıkları bozma" tavsiyesi vermişti. Bu tam olarak warmup + düşük lr0
konusu — projede `lr0`/`warmup_epochs` hiç arayüzde açık değildi, hep
ultralytics'in gizli varsayılanı kullanılıyordu. `cos_lr` (kosinüs LR
azalma eğrisi, warmup'tan FARKLI bir mekanizma) de eklendi.
- `app.py`: `ayarlar` sözlüğüne `cos_lr` (varsayılan False), `lr0`
  (varsayılan 0.01, ultralytics'le aynı), `warmup_epochs` (varsayılan 3.0,
  ultralytics'le aynı) eklendi, `model.train(...)` çağrısına yansıtıldı.
- `templates/egitim.html` + `static/egitim.js`: Gelişmiş Alanlar'a üç
  yeni satır, fine-tune bağlamında ne işe yaradıkları açıklamalı.

### Test durumu
`ast.parse` + `node --check` temiz.

---

## CompCars "incele" klasörü — gözden geçirme için ham çıkarım (2026-08-06, devam)

### Neden geri döndüm
İlk aktarımda Renault Clio'yu yıl bilgisine bakarak kendi kafamdan clio3/clio4
diye ikiye bölmüştüm (`kod/08_compcars_import.py`, ilk versiyon). Kullanıcı
bunun hatalı olduğunu belirtti (clio3 etiketlemesi yanlış çıkmış). Bu 91
görsel+etiket çiftini `veri/images` ve `veri/labels`'tan geri çıkardım
(123/124 dosyaya döndü, projenin kendi verisi hiç etkilenmedi).

### Ne yaptım (yeni yaklaşım)
Kullanıcı sadece Renault/Fiat değil, Türkiye'de genel olarak görülen TÜM
markaları kendi gözüyle görüp kontrol etmek istiyor — CompCars'ın kendi
kaydettiği sınıf/klasör yapısını bozmadan (benim year-bazlı tahminimle değil).
1. `kod/09_compcars_incele_cikart.py` scriptini yazdım: 36 markanın (Türkiye
   pazarında yaygın olanlar — Fiat, Renault, VW, Ford, Opel, Toyota, Hyundai,
   Mercedes, BMW, Audi, Skoda, Dacia, Kia, Peugeot, Citroen, vb.; Bugatti/
   Ferrari gibi egzotikler ve Çin iç pazarına özgü markalar bilinçli
   dışlandı) CompCars'taki TÜM model klasörlerini, CompCars'ın kendi
   marka_id/model_id/yıl yapısını KORUYARAK, orijinal etiketleriyle
   (dönüştürmeden, ham CompCars formatında: satır1 açı, satır3 piksel bbox)
   `compcars_incele/<marka_adı>/<model_id>_<model_adı>/<yıl>/` altına
   kopyalıyor. Her marka klasörüne `_model_id_isim_listesi.txt` (o markadaki
   tüm model id → isim eşlemesi) ekliyor.
2. Bağlantı (OneDrive mount) çok sayıda küçük dosya için yavaş kaldığından
   (~40-150 dosya/dakika), model başına en fazla 12 örnek görsel (tüm
   yıllara yayılmış) kopyalanacak şekilde sınırladım — amaç TAM veri seti
   değil, gözden geçirme için yeterli örnek. Kullanıcı bir model/marka
   beğenirse o modelin TAMAMINI ayrıca çekerim.
3. Script idempotent: `_ilerleme.txt` ile hangi markaların bittiğini
   kaydediyor, tekrar çalıştırılınca kaldığı yerden devam ediyor (yavaş
   bağlantı yüzünden onlarca kez arka arkaya, 40 saniyelik parçalar halinde
   çalıştırmam gerekti).
4. Sonuç: `compcars/compcars_incele/` altında 36 marka, toplam 6113 görsel
   + orijinal CompCars etiketi. `veri/`e HİÇBİR ŞEY otomatik eklenmedi —
   kullanıcı önce gözden geçirecek.

### Test durumu
Her marka klasörü için `find ... -name "*.jpg" | wc -l` ile sayı doğrulandı,
36/36 marka `_ilerleme.txt`'de işaretli, script hatasız tamamlandı (son
çalıştırmada "Exit code 0", "Bu calistirmada kopyalanan gorsel: 22").

---

## CompCars veri seti aktarımı (2026-08-06)

### Ne yaptım
1. Kullanıcının indirdiği CompCars veri setini (13 parçaya bölünmüş Google
   Drive zip, ~18GB) inceledim, `misc/make_model_name.mat` içinden marka/model
   ID eşlemesini çıkardım (163 marka, 2004 model).
2. Fiat (id=134) ve Renault (id=160) altındaki modelleri kontrol ettim:
   - **Fiat Egea veri setinde YOK** — CompCars 2015 öncesi toplanmış, Egea
     2015 sonrası bir model. Bu class için CompCars kullanılamaz.
   - Renault Clio tek model_id (793) altında, yıl klasörüyle ayrılıyor:
     2009/2010 = Clio 3 (32 görsel), 2013/2014 = Clio 4 (59 görsel).
   - Marka/model isimleri Çince kaynaktan kötü çevrilmiş/OCR'lanmış
     ("Cleo"=Clio, "Megan Aa"=Megane gibi) ama klasör ID'leri ve görsel
     içerikleri doğru — sadece görünen isimler bozuk.
3. `kod/08_compcars_import.py` scriptini yazdım: CompCars'ın kendi label
   formatını (satır1: açı 1-5, satır3: piksel bbox `x1 y1 x2 y2`) YOLO
   formatına (`class xc yc w h`, normalize) çeviriyor, görüntü boyutunu
   PIL ile okuyup normalize ediyor, `veri/images`+`veri/labels`'a
   `compcars_<class>_<orijinal_ad>` adıyla ekliyor (çakışma önleme +
   var olan dosyaya dokunmama garantili).
4. Scripti çalıştırdım: **91 yeni görsel+etiket çifti eklendi** (32
   renault_clio3, 59 renault_clio4). `veri/images` 123→214,
   `veri/labels` 124→215 oldu.

### Test durumu
- Script çalıştırıldı, hata vermedi, eklenen dosya sayıları doğrulandı.
- Örnek bir dönüştürülmüş etiket dosyası elle kontrol edildi, YOLO formatına
  uygun (0-1 arası 4 ondalık değer + class id).
- fiat_egea class'ı için CompCars'tan hiçbir şey eklenmedi (bilinçli —
  veri setinde yok). Kullanıcının bu class için kendi görsellerini
  (sahibinden vb.) kendi arayüzünde elle etiketlemesi gerekiyor.

### Neden böyle yaptım
Kullanıcı zaten var olan `veri/data.yaml`'daki 3 class'ı (renault_clio3,
renault_clio4, fiat_egea) hedefliyordu. CompCars'tan sadece bu class'larla
eşleşen veriyi, mevcut YOLO formatına birebir uyumlu şekilde ekledim ki
kullanıcı kendi etiketleme arayüzünde direkt görebilsin ve karışık
(kendi + CompCars) veri setiyle eğitime devam edebilsin.

---

## Adım 1: Ortam + Klasör İskeleti (2026-07-28)

### Ne yaptım
1. Proje klasörünün (`otopark/`) içine 4 alt klasör oluşturdum:
   - `models/` — eğitilmiş/indirilmiş YOLO modelleri (plaka detect, classify) buraya kaydedilecek
   - `veri/` — marka/model classify eğitimi için topladığımız araç görselleri
   - `kayitlar/` — sistemin çalışırken kaydettiği thumbnail'ler (log şemasındaki `thumbnail_yolu` alanı buraya işaret edecek)
   - `db/` — SQLite veritabanı dosyası (`.db`) burada duracak
2. Python/pip ortamını kontrol ettim: Python 3.10.12, pip 25.3 kurulu.
3. Projenin ihtiyaç duyduğu 3 kütüphaneyi kurmaya başladım:
   - `ultralytics` → YOLO detect ve classify modellerini çalıştırmak/eğitmek için (bileşen 1, 3)
   - `opencv-python-headless` → görüntü okuma/kırpma/işleme için (kameradan gelen kareleri işlemek, plaka bölgesini kırpmak vs.)
   - `easyocr` → plaka üzerindeki yazıyı okumak için (bileşen 2)

### Neden bu şekilde
- Klasörleri en başta ayırmak, ileride "bu dosya nereye gidecek" karmaşasını
  önlüyor — brief'teki mimari tablo zaten bu 4 klasörü işaret ediyordu.
- `opencv-python-headless` kullandım (`opencv-python` yerine): headless sürüm
  GUI (ekran açma) bağımlılıkları içermiyor, sunucu/sandbox ortamlarda daha
  hafif ve sorunsuz kurulur. Senin kendi bilgisayarında görüntü göstermek
  istersen orada normal `opencv-python` de kullanılabilir, fark etmez.

### Nasıl yaptım (komutlar)
```bash
mkdir -p otopark/{models,veri,kayitlar,db}
pip3 install --break-system-packages ultralytics opencv-python-headless easyocr
```

### Durum ve önemli bir karar değişikliği

Kütüphaneleri benim (Claude'un) çalıştığı sanal ortamda kurmayı denedim,
ama bir sorunla karşılaştım — bunu anlatıyorum çünkü ileride sen de aynı
şeyi yaşarsan neden olduğunu bileceksin:

- `torch` (PyTorch, hem ultralytics hem easyocr'ın temel bağımlılığı)
  Linux'ta PyPI üzerinden kurulunca, GPU'n olmasa bile **CUDA
  kütüphanelerini de otomatik olarak indirmeye çalışıyor** (cuDNN tek
  başına ~366 MB, toplamda birkaç GB). Benim çalıştığım sanal ortamın
  interneti kısıtlı/proxy üzerinden ve diski küçük (9.6 GB) — bu yüzden
  bu devasa indirmeyi burada tamamlamak hem çok zaman alıyor hem de
  gereksiz (zaten GPU'suz bir ortamda CUDA kütüphanelerinin bir işi yok).

**Karar:** Kütüphane kurulumunu ve gerçek görüntü/video testlerini
**senin kendi bilgisayarında** yapacağız — orada hem internet kısıtlı
değil hem de gerçek bir Python ortamın var. Ben burada:
- Tüm kodu (detect, OCR, classify, fusion, DB, sorgu script'i) yazıp
  hazırlayacağım,
- Senin çalıştırman gereken komutları adım adım vereceğim,
- Çıktıları/hataları bana yapıştırırsan yorumlayıp düzelteceğim.

`requirements.txt` dosyasını klasöre ekledim. Kendi bilgisayarında
(otopark klasörünün olduğu yerde, bir terminalde) şunu çalıştırman
yeterli:
```
pip install -r requirements.txt
```
Not: Senin bilgisayarında NVIDIA GPU'n varsa ve PyTorch onu kullansın
istersen, kurulumdan önce şu adresten (https://pytorch.org/get-started/locally/)
kendi CUDA sürümüne uygun torch komutunu alıp önce onu çalıştırman,
sonra `pip install -r requirements.txt` demen daha doğru olur. GPU'n
yoksa/emin değilsen direkt yukarıdaki komut yeterli (CPU sürümünü kurar).

---

## Adım 2: Plaka Tespiti — Tekli Görüntüde Test (2026-07-28)

### Ne yaptım
- `kod/01_plaka_tespit_test.py` dosyasını yazdım.
- Kullanılacak hazır plaka tespit modelini araştırdım: web araması ve
  Hugging Face sayfasını kontrol ederek `Koushim/yolov8-license-plate-detection`
  modelinin gerçek, MIT lisanslı, **Ultralytics YOLOv8 formatında** (yani
  bizim `ultralytics` paketiyle doğrudan uyumlu) ve küçük (~6 MB) bir
  `best.pt` dosyası olduğunu doğruladım.
  - İlk denediğim `keremberke/yolov8n-license-plate` adresi gerçekte
    **yoktu** (arama sonuçlarında sadece YOLOv5 sürümü çıktı, ve o da
    farklı bir kütüphane formatında olduğu için bizim kodumuzla uyumsuz
    olurdu) — bu yüzden değiştirdim. Bunu sana anlatıyorum çünkü "ben
    bir link buldum, kullanıyorum" demek yetmiyor; linkin gerçekten var
    olduğunu ve doğru formatta olduğunu doğrulamak gerekiyor.

### Script ne yapıyor
1. Model dosyası yoksa Hugging Face'ten indirir (`models/plaka_tespit.pt`).
2. `veri/test_arac.jpg` dosyasındaki plakayı/plakaları tespit eder.
3. Her tespit için bbox koordinatı + güven skorunu terminale yazar.
4. Plaka bölgesini kırpıp `kayitlar/plaka_kirpik_0.jpg` gibi kaydeder
   (bunu bir sonraki adımda OCR'a vereceğiz).

### Senin yapman gerekenler
1. Kendi bilgisayarında bir terminal aç, `otopark` klasörüne geç.
2. `pip install -r requirements.txt`
3. Plakası net görünen bir araç fotoğrafını `veri/test_arac.jpg` olarak kaydet
   (kendi çekimin, ya da telefonundan bir fotoğraf — hayali senaryo olduğu
   için plaka gerçek biri ait olmasın, uydurma/örnek bir plaka görünse yeter).
4. `python kod/01_plaka_tespit_test.py`
5. Çıktıyı (terminal metni + varsa hata) bana yapıştır, birlikte
   yorumlayıp bir sonraki adıma (OCR) geçelim.

### Neden bu şekilde
- Gerçek görüntü işleme ve model indirme/çalıştırma benim (Claude'un)
  sanal ortamında pratik değil (bkz. Adım 1'deki torch/CUDA notu) —
  bu yüzden kodu ben yazıyorum, çalıştırmayı ve gerçek dünya testini
  (fotoğraf, kamera) sen yapıyorsun; çıktıyı birlikte yorumluyoruz.
- Model olarak halka açık, küçük, hesap gerektirmeyen bir seçenek
  seçtim ki kurulum ilk adımda takılmasın.

### Sonuç ✅
Sen çalıştırdın, çıktı:
```
1 license_plate, 269.0ms
Plaka #0: bbox=(278,184,362,213)  guven=0.90
    -> kaydedildi: kayitlar/plaka_kirpik_0.jpg
```
%90 güvenle tek plaka tespit edildi — model ilk denemede beklediğimiz gibi
çalıştı, ek ayar gerekmedi. Adım 2 tamamlandı.

---

## Adım 3: OCR Entegrasyonu — Tekli Görüntüde Test (2026-07-28)

### Ne yaptım
`kod/02_ocr_test.py` yazdım. Bu script:
1. Adım 2'nin çıktısı olan `kayitlar/plaka_kirpik_0.jpg`'i EasyOCR'a veriyor.
2. Ham OCR metnini ve güven skorunu yazdırıyor.
3. Türk plaka formatına göre bir temizleme/doğrulama uyguluyor.

### Türk plaka temizleme mantığı (neden gerekli)
Brief'te log şemasında `plaka_okunan` alanı vardı ve "kısmen bulanık okunsa
bile" ifadesi geçiyordu — yani OCR'ın ham çıktısına asla tam güvenemeyiz.
Bunu ele almak için üç katmanlı bir yaklaşım kurdum:
1. **Temizlik:** boşluk/nokta/tire gibi karakterleri sil, büyük harfe çevir.
2. **Regex doğrulama:** Türk plakası genel kalıbı `##[A-Z]{1,3}####`
   (il kodu + harf + rakam) ile eşleşiyor mu diye kontrol et.
3. **Sezgisel düzeltme:** Eşleşmezse, OCR'ın sık karıştırdığı karakterleri
   (O/0, I/1, S/5, B/8, Z/2) *pozisyona göre* düzeltmeyi dener — yani "34"
   beklenen yerde harf çıkmışsa rakama çevirir, harf beklenen ortada rakam
   çıkmışsa harfe çevirir. Bu, brief'teki `plaka_guven` skorunun (fusion
   formülündeki `ocr_guven * plaka_benzerlik(...)`) ilk parçasını besleyecek.

### Senin yapman gerekenler
1. Adım 2'yi zaten çalıştırdığın için `kayitlar/plaka_kirpik_0.jpg` hazır.
2. `python kod/02_ocr_test.py` çalıştır (ilk seferde EasyOCR kendi modelini
   indirecek, biraz sürebilir — internetin açık olsun).
3. Çıktıyı bana yapıştır: ham OCR metni ne çıktı, temizleme sonrası format
   geçerli mi değil mi.

### Durum — ilk deneme başarısız, sebep bulundu ve düzeltildi
Sen çalıştırdın, OCR "hiçbir metin bulamadı" dedi. Paylaştığın kırpık
görselde plaka aslında gayet net okunuyordu ("01 DRV 23" gibi) — sorun
OCR'ın metni anlayamaması değil, **kırpılan görüntünün çok küçük olması**
(bbox ~84x29 piksel). EasyOCR'ın metin tespit aşaması bu kadar küçük bir
alanda güvenilir çalışmıyor.

**Düzeltme** (`kod/01_plaka_tespit_test.py` güncellendi):
1. Kırpma öncesi bbox'a her yönde %15 pay ekledim (harfler kesilmesin).
2. Kırpılmış görüntüyü, genişliği en az 300 piksel olacak şekilde
   büyüttüm (`cv2.resize` + kübik interpolasyon).

Şimdi tekrar dene:
```
python kod/01_plaka_tespit_test.py
python kod/02_ocr_test.py
```
(01'i tekrar çalıştırman lazım ki `plaka_kirpik_0.jpg` yeni/büyütülmüş
haliyle kaydedilsin.)

### İkinci deneme sonucu — büyütme yetmedi, ek işleme gerekti
Kırpma/büyütme düzelmişti (300x103, gözle net okunuyor: "01 DRV 23"),
ama EasyOCR yine de yanlış okudu: `'Ia'` (güven=0.05 — yani model kendi
de emin değildi). Sebep muhtemelen: plaka görüntüsünün rengi/kontrastı
düşük (griye yakın, hafif bulanık) ve solundaki mavi şerit OCR'ı
şaşırtmış olabilir.

**Düzeltme** (`kod/02_ocr_test.py` güncellendi):
1. `on_isle()` fonksiyonu eklendi: görüntüyü 500px genişliğe büyütür,
   gri tonlamaya çevirir, CLAHE (kontrast artırma) uygular — bu genelde
   OCR için karakter kenarlarını belirginleştirir.
2. `allowlist` parametresiyle EasyOCR'a yalnızca harf+rakam beklediğimizi
   söyledik (noktalama/simge tahminlerini eledik).
3. Hem ham renkli hem işlenmiş gri versiyonu ayrı ayrı deniyoruz, hangisi
   daha yüksek güvenle sonuç verirse onu seçiyoruz — çünkü hangisinin
   daha iyi çalışacağı görüntüden görüntüye değişebilir, tek bir yönteme
   bağlı kalmak riskli.

Tekrar dene:
```
python kod/02_ocr_test.py
```
(01'i tekrar çalıştırmana gerek yok, kırpık dosya zaten aynı.)

### Üçüncü deneme sonucu — biraz iyileşti ama hâlâ düşük güven
Sonuç: ham renkli `'IA'` (guven 0.05), gri+kontrastlı `'61DAL'`
(guven 0.16, gerçek plaka "01 DRV 23"). Yani büyütme+kontrast biraz
iyileştirdi (karakter sayısı ve genel yapı gerçek plakaya yaklaştı: 5
karakter, rakam+harf karışımı) ama hâlâ yanlış okuyor, güven düşük.

**Ek düzeltme** (`kod/02_ocr_test.py`):
1. `sol_seridi_kirp()`: Avrupa tipi plakalardaki solda duran mavi/renkli
   şeridi (ülke kodu bandı) görüntüden kırpıp atıyorum — bu bant metin
   içermiyor ama OCR'ın metin tespit aşamasını yanıltabiliyor.
2. `otsu_esikleme()`: Görüntüyü siyah-beyaza (binary) çeviren klasik bir
   OCR ön-işleme adımı ekledim (Otsu yöntemiyle otomatik eşik seçimi) —
   karakterleri arka plandan keskin şekilde ayırmayı hedefliyor.
3. Artık 3 varyant deneniyor: ham renkli / gri+kontrast (şeritsiz) /
   siyah-beyaz eşiklenmiş — en yüksek güvenli olan seçiliyor.

**Önemli not (gerçekçi beklenti):** Paylaştığın fotoğraf muhtemelen biraz
bulanık/düşük çözünürlüklü çekilmiş — bu, gerçek dünyada da olağan bir
durum (brief'te zaten "kısmen bulanık okunsa bile" diye öngörülmüştü).
Eğer bu 3 varyantla da güven düşük kalırsa, bu bizim kodumuzdaki bir hata
değil, **kaynak görüntü kalitesinin sınırı** olabilir — böyle durumlarda
sistemin devamı zaten düşük OCR güvenini fusion skoruyla (marka/model
tanımayla birleştirip) telafi edecek şekilde tasarlandı (brief'teki
fusion formülü). Yani ideal senaryo net bir örnek fotoğrafla ~%80-90
güven görmek, ama düşük güvenli bir örnek de sistemin "emin değilim"
diyebilmesini test etmek için aslında faydalı.

Tekrar dene:
```
python kod/02_ocr_test.py
```

### Dördüncü deneme ve Adım 3 kararı
Sonuç: `gri+kontrast+buyutulmus` varyantı artık **2 ayrı blok** buldu:
`'M1'` (guven 0.12) ve `'DAL'` (guven 0.23) — gerçek plaka "01 DRV 23"
idi. Yapı olarak yaklaştı (baştaki 2 karakter blok + harf bloğu ayrı ayrı
yakalandı) ama karakterler hâlâ yanlış okunuyor, güven düşük kalıyor.

**Karar: Adım 3'ü burada kapatıyorum.** Sebep: OCR entegrasyonunun
kendisi (kırpma -> ön işleme -> EasyOCR -> temizleme/doğrulama -> güven
skoru) uçtan uca çalışıyor ve kod tarafında bir hata yok — düşük doğruluk,
kullandığımız tek test fotoğrafının kalitesinden (bulanıklık/açı/ışık)
kaynaklanıyor. Bunu daha fazla "fotoğraf özel" ince ayarla (o tek görüntüye
özel parametre kurcalamakla) uğraşmak zaman kaybı olur — brief'te fusion
mantığı zaten tam bu senaryo için var: düşük OCR güveni tek başına
yeterli değilse marka/model tanımayla birleşip karar veriliyor.

**Pratik sonuç:** Pipeline'ı olduğu gibi bırakıyoruz. İleride (Adım 8,
11 — uçtan uca test ve demo) daha net/yakın çekilmiş fotoğraflarla
OCR güveninin normalde %70-90'a çıktığını göreceğiz; düşük ışık/açı
durumlarında da sistemin "emin değilim" diyebilmesi zaten istenen
davranış.

### Bulunan gerçek hata: bloklar birleştirilmiyordu (2026-07-28, devam)
Sen daha net bir test fotoğrafıyla (`test_arac2.jpg`) tekrar denedin,
sonuçlar çok iyileşti (Otsu varyantında '31' guven=0.95, '585' guven=0.97,
'RS' guven=1.00) ama script sonunda sadece **'RS'** yazdırdı. Bu bir
tasarım hatasıydı: `en_iyi_sonucu_sec` fonksiyonu tüm bloklar arasından
tek en yüksek güvenli olanı seçiyordu, oysa plaka birden fazla parçaya
bölünmüş okunuyor ve hepsinin birleştirilip tam metni oluşturması
gerekiyordu.

**Düzeltme:** `bloklari_birlestir()` fonksiyonu eklendi — bir varyantın
tüm bloklarını, bbox'ın en sol x koordinatına göre soldan sağa sıralayıp
birleştiriyor, ortalama güveni hesaplıyor. `en_iyi_sonucu_sec` artık
varyantlar arasından (blok değil) en yüksek **ortalama** güvenli olanı
seçiyor ve o varyantın tam birleştirilmiş metnini döndürüyor.

Tekrar dene:
```
python kod/02_ocr_test.py
```
Artık örn. Otsu varyantı için `'31 585 RS'` gibi tam bir metin göreceksin
(temizleme adımı boşlukları zaten kaldırıp regex kontrolü yapacak).

---

## Adım 4: Marka/Model Veri Toplama — Mimari Kararı (2026-07-28)

### Senin sorunun ve neden önemliydi
Sordun: "beyaz Egea ile siyah Egea'yı ayrı ayrı mı öğrenecek, kendi
renklerini bilmiyor mu?" — bu, veri toplamaya başlamadan önce sormaya
değer bir soruydu, çünkü cevaba göre iş yükü katlanarak değişiyor.

**Cevap: Hayır, bir YOLO classify modeli renkleri "kendiliğinden" bilmez.**
Sınıfları "beyaz_egea" / "siyah_egea" diye ayrı verirsen, model bunları
tamamen bağımsız iki kategori sanır — aralarında "aynı model, farklı
renk" ilişkisi kurmaz. Bu da 5 model x birkaç renk = onlarca sınıf demek,
her biri için ayrı 30-40 görsel.

### Karar: Bileşen 3'ü ikiye ayırdım
1. **YOLO classify** → sadece marka/model öğrenir (sınıf: "egea", "clio"
   gibi, renk fark etmeksizin; hatta veride renk çeşitliliği olması
   modelin şekle odaklanmasına yardımcı olur).
2. **Renk tespiti** → eğitim gerektirmeyen, klasik bir görüntü işleme
   adımı: tespit edilen aracın kutusu içindeki baskın rengi HSV
   uzayında hesaplayıp en yakın renk ismine ("beyaz/siyah/gri/kırmızı/
   mavi" vb.) eşliyoruz. Bu ayrı bir küçük fonksiyon olacak, ileride
   fusion aşamasında marka/model tahminiyle birleştirilecek.

Bu kararı `PROJE_BRIEF_OTOPARK.md`'ye de işledim ("Güncelleme (2026-07-28)"
bölümü) — proje bağlamının tek doğru kaynağı orası olduğu için.

### Veri toplama etkisi
Artık her model için **tek klasör** yeterli (o modelin farklı
renklerdeki/açılardaki/ışıklardaki fotoğrafları karışık), renk başına
ayrı klasör gerekmiyor. Örnek yapı:
```
veri/
  egea/
  clio/
  corolla/
```

### Ek netleştirme 1: Nesil/kasa ayrımı
Sordun: Clio 20 yıl önce de vardı, kasa tamamen değişti — aynı sınıfta mı
öğretelim? Cevap: hayır, kasa görsel olarak neredeyse farklı bir araba
demek, bu yüzden sınıf isimlendirmesini `marka_model_nesil` şeklinde
yapıyoruz (renk hariç, o ayrı hesaplanıyordu). Marka'yı ayrı bir
sınıflandırma aşaması yapmaya gerek yok, düz/tek aşamalı sınıflandırma
yeterli (5-8 sınıf ölçeğinde hiyerarşinin faydası yok) — sadece etiket
ismi marka+model+nesili içersin yeter.

### Ek netleştirme 2: Asıl amaç "genel model tanıma", "kişi tanıma" değil
Sen düzelttin: sistem önceden bilinen kişilerin arabalarını tanımak için
değil, loglardaki HERHANGİ bir aracı (bilinen/bilinmeyen fark etmeksizin)
"marka/model/renk" bazında aranabilir kılmak için var. Bu, veri toplama
stratejisini değiştiriyor:
- Aynı fiziksel arabanın tekrar tekrar fotoğrafını çekmek yetersiz —
  model o arabaya özgü detayları (çizik, plaka, aksesuar) ezberleyip
  başka aynı model arabayı tanıyamayabilir (overfitting).
- Her sınıf için mümkünse **birden fazla farklı fiziksel araç örneği**
  toplanmalı (aynı model/nesil, farklı araçlar) ki model o modelin genel
  görünümünü öğrensin.
- Gerçek kamera görüntüsünde çalışması için eğitim verisinin gerçek
  kullanım açısına/mesafesine (galeri fotoğrafı değil, otopark kamerası
  gibi) yakın olması önemli — yoksa "domain shift" nedeniyle doğruluk
  düşebilir. Adım 8'de eğitim setinde olmayan bir görüntüyle bunu test
  edeceğiz.

### Durum — test sınıfları belirlendi, klasörler kuruldu
`renault_clio3`, `renault_clio4`, `fiat_egea` klasörlerini
`veri/` altında oluşturdum.

### Görsel toplama aracı
`kod/03_gorsel_indir.py` yazdım — bir URL listesi dosyasından
(`veri/<sinif>_urls.txt`) toplu görsel indirip sıralı isimlerle
(`0001.jpg`, `0002.jpg`, ...) ilgili klasöre kaydediyor.

**Neden ben otomatik toplu görsel taramıyorum:** Rastgele bir siteden
toplu telifli görsel çekmek telif hakkı açısından riskli. Bunun yerine
sen serbest lisanslı kaynaklardan (Wikimedia Commons, Openverse) veya
kendi fotoğraflarından URL/dosya topluyorsun, ben sadece indirme/
isimlendirme işini otomatikleştiriyorum.

### Senin yapman gerekenler
Her sınıf için ~15-20 görsel hedefliyoruz (test aşaması, tam üretimde
30-40 olacak), ve **birden fazla farklı fiziksel araç** olmasına dikkat
et (aynı arabanın tekrar tekrar fotoğrafı değil):

1. `veri/renault_clio3_urls.txt`, `veri/renault_clio4_urls.txt`,
   `veri/fiat_egea_urls.txt` dosyalarını oluştur, her satıra bir görsel
   URL'i yapıştır (Wikimedia Commons / Openverse'ten, ya da kendi
   fotoğraflarınsa direkt dosya olarak `veri/<sinif>/` klasörüne koy).
2. `python kod/03_gorsel_indir.py renault_clio3` (her sınıf için
   tekrarla).
3. Klasörleri gözden geçir — yanlış nesil/model kaçmışsa sil.

### Durum
Senin görselleri toplayıp indirmen bekleniyor.

---

## Adım 4 (devam): Classify'dan Detect'e Geçiş Kararı (2026-07-28)

### Ne konuştuk
Bana ayrı bir dosya (`nevfel.txt`) gösterdin — staj hocanın istediği,
seg/detect/pose için evrensel bir etiketleme + dataset bölme + augment +
eğitim + test araç seti listesi. Bunun otopark projesiyle ilgisini sordun.

**Tespitim:** Bu araç seti otopark'tan bağımsız, çok daha büyük ayrı bir
iş — otopark'ın brief'inde böyle bir arayüz hiç planlanmamıştı (tek
eğitim gereken kısım classify'dı, basit klasör-bazlı etiketleme
yetiyordu). Sana staj hocanla bunun otopark'a ek mi yoksa tamamen paralel
bir görev mi olduğunu netleştirmeni önerdim.

### Sonra sorduğun soru: classify yerine detect kullanıp o aracı otopark'ta da kullanabilir miyim?
Bunu tartıştık:
- **Neden classify seçmiştik:** Senaryo tek şeritli giriş (karede tek
  araç varsayımı), classify basit (klasöre sort yeter, kutu çizmeye gerek
  yok).
- **Detect'in avantajı:** Sen kendin fark ettin — classify tüm görsele
  TEK etiket verir, birden fazla/duran/kısmi araç olan bir sahnede
  (örn. sokak görüntüsü) bunları ayrı ayrı tanıyamaz. Detect her nesneyi
  ayrı bulup ayrı sınıflandırır, bu sınırı ortadan kaldırır.
- **Ek avantaj:** Detect'e geçince staj hocanın istediği araç seti
  (seg/detect/pose için) otopark'ın kendi verisiyle de kullanılabilir
  hale geliyor — iki iş birbirini besliyor.

**Karar: Bileşen 3 classify'dan DETECT'e çevrildi.**

### Bunun somut etkileri
1. Klasör yapısı değişti: sınıf başına klasör yerine artık
   `veri/images/` (tüm görseller) + `veri/labels/` (YOLO formatında kutu
   etiketleri) + `veri/data.yaml` (sınıf listesi). Bu yapıyı zaten kurdum.
   (Eski `veri/renault_clio3/` vb. klasörler artık kullanılmıyor,
   silinmeye izin vermedi ama boş, zararsız duruyorlar.)
2. Veri miktarı arttı: classify'daki 30-40 yerine artık sınıf başına
   **80-150** kutu etiketli görsel hedefliyoruz (test aşaması için
   ~80'den başlayacağız). Sebep: model artık hem "nerede" hem "ne"
   sorusunu birlikte öğreniyor, ama `yolo11n.pt` zaten COCO'da genel
   "araç" kavramını bildiği için (transfer learning) bu abartılı bir
   fark değil.
3. Kutu çizme işi (bounding box) staj hocanın aracı henüz hazır olmadığı
   için şimdilik harici bir araçla yapılacak (Roboflow Annotate veya
   LabelImg — ikisi de doğrudan YOLO formatında dışa aktarabiliyor).

Bu kararı `PROJE_BRIEF_OTOPARK.md`'ye de işledim.

### Durum
`veri/data.yaml` oluşturuldu (3 sınıf: renault_clio3=0,
renault_clio4=1, fiat_egea=2). Sıradaki: görselleri toplama +
kutu etiketleme aracı seçimi/kurulumu.

---

## Etiketleme Arayüzü (kendi aracın) — Geliştirme (2026-07-28)

### Bağlam
`nevfel.txt`'deki staj görevinin 1. maddesi ("data etiketleme arayüzü")
için, otopark'ın detect verisiyle de kullanılabilecek kendi etiketleme
arayüzünü kurduk. Bu, otopark'tan ayrı ama otopark'ın Adım 4'ünü (kutu
etiketleme) de karşılıyor.

### Mimari
- **Backend:** Flask (Python) yerel sunucu — `etiketleme_arayuzu/app.py`.
  Neden yerel sunucu: keyfi bir klasörü (sadece otopark değil, ileride
  başka veri setleri için de) okuyup yazabilmemiz lazım, tarayıcı
  güvenlik kısıtları rastgele klasöre erişime izin vermiyor.
- **Frontend:** Tek sayfa, canvas tabanlı — `templates/index.html`,
  `static/app.js`, `static/style.css`. Kutu koordinatları görselin
  gerçek (natural) piksel boyutunda tutuluyor, kaydederken YOLO'nun
  normalize (0-1) formatına çevriliyor.
- **İki girdi modu tek kod yoluyla çözüldü:** Etiket klasörü verilmezse
  görsel klasörünün yanında "labels" varsayılıyor (YOLO'nun standart
  images/+labels/ kardeş klasör kuralı) — bu hem "sadece images" hem
  "images+labels" modunu aynı mantıkla karşılıyor, ayrı kod dalı
  gerekmedi. Aynı şekilde data.yaml verilmezse görsel klasörünün yanında
  otomatik aranıyor, o da yoksa kullanıcının yazdığı sınıf listesinden
  otomatik oluşturuluyor.

### Doğrulama (smoke test)
Backend'i kendi ortamımda `curl` ile uçtan uca test ettim (gerçek
tarayıcı/fare etkileşimini test edemesem de, API mantığını doğruladım):
1. `veri/images/` klasörüne 2 geçici test görseli koydum.
2. `/api/yukle` çağrıldı, boş `data_yaml` alanına rağmen `veri/data.yaml`
   otomatik bulundu ve 3 sınıf doğru okundu. ✅
3. `/api/gorsel/test1.jpg` → 200 OK, doğru içerik tipiyle görsel döndü. ✅
4. `/api/etiket/test1.jpg` (GET) → başlangıçta boş liste. ✅
5. `/api/etiket/test1.jpg` (POST) örnek bir kutuyla → kaydedildi,
   `veri/labels/test1.txt` dosyası doğru YOLO formatında oluştu
   (`0 0.500000 0.500000 0.300000 0.200000`). ✅
6. Tekrar GET edince kaydedilen kutu doğru döndü. ✅
7. `/api/durum` → görsellerin etiketlenmiş/etiketlenmemiş durumu doğru. ✅
Test dosyalarını temizledim (senin gerçek verini karıştırmasın diye).

### Senin yapman gerekenler (Adım 16 — gerçek tarayıcı testi)
Fare ile kutu çizme, klavye kısayolları, görseller arası gezinme gibi
kısımları ben test edemiyorum (tarayıcı etkileşimi gerektiriyor). Sen:
1. `cd etiketleme_arayuzu`
2. `pip install -r requirements.txt`
3. `python app.py`
4. Tarayıcıda `http://localhost:5000` aç.
5. Görsel klasörü olarak `veri/images` (henüz boşsa, birkaç test görseli
   koy), sınıflar otomatik `data.yaml`'dan gelecek.
6. Birkaç kutu çiz, rakam tuşlarıyla sınıf değiştir, "Sonraki" ile geç,
   "Kaydet"e bas, `veri/labels/` altında `.txt` dosyalarının oluştuğunu
   kontrol et.
7. Sorun/garip davranış görürsen bana anlat, düzeltelim.

### Güncelleme: Tarayıcı yerine native uygulama penceresi
Sen SADEKTECH'in kendi etiketleme arayüzünün ekran görüntüsünü paylaştın
(keypoint için ama örnek olarak) — onunki gerçek bir uygulama penceresi
gibi açılıyor, tarayıcıda değil. Bizim mantığımız (keypoint değil detect)
farklı ama pencere biçimi konusunda haklısın, düzelttim.

**Ne değiştirdi:** Flask backend'i ve HTML/JS/CSS frontend'i AYNEN
korudum (zaten test edilmişti, tekrar yazmaya gerek yoktu). Sadece
başlatma şeklini değiştirdim: `pywebview` kütüphanesini ekledim — bu,
Flask sunucusunu arka planda bir thread'de sessizce çalıştırıp, kullanıcı
tarafında adres çubuğu/sekme olmayan gerçek bir uygulama penceresi
açıyor (Windows'ta yerleşik Edge WebView2 motorunu kullanıyor). Yani
`python app.py` dediğinde artık tarayıcıya gitmene gerek yok, doğrudan
bir uygulama penceresi açılacak.

**Test durumu:** Backend mantığını zaten curl ile doğrulamıştım (bir
üstteki bölüme bak), bu değişiklik sadece başlatma katmanını etkiliyor.
Python syntax hatası olmadığını kontrol ettim (`py_compile` ile), ama
gerçek pencerenin açılışını BEN test edemiyorum — benim çalıştığım
sanal ortamda ekran/görüntü sürücüsü yok (headless). Bunu senin kendi
bilgisayarında denemen gerekiyor.

### Senin yapman gerekenler (güncellendi)
```
cd etiketleme_arayuzu
pip install -r requirements.txt
python app.py
```
Artık tarayıcı açmana gerek yok — bir uygulama penceresi açılmalı.
Açılmazsa/hata verirse (örn. Windows'ta WebView2 çalışma zamanı eksikse)
hatayı bana yapıştır, birlikte çözelim.

### Güncelleme: Native klasör/dosya seçme pencereleri
Sen SADEKTECH'in keypoint arayüzünün ekran görüntüsünü paylaştın —
onlarda yol elle yazılmıyor, "KLASÖR SEÇ" gibi bir buton gerçek Windows
dosya gezginini açıyor. Bunu ekledim:

- `app.py`'ye `Api` sınıfı eklendi (`klasor_sec`, `dosya_sec` metodları)
  — pywebview'ın "js_api" köprüsü üzerinden JavaScript'in çağırabildiği
  Python fonksiyonları. Bunlar gerçek Windows klasör/dosya seçme
  penceresini açıp seçilen yolu JS'e döndürüyor.
- Yükleme ekranı tamamen değişti: artık metin kutusuna yol yazmak yerine
  "📁 KLASÖR SEÇ" / "📄 DOSYA SEÇ" butonları var (görsel klasörü zorunlu,
  etiket klasörü ve data.yaml opsiyonel — SADEKTECH'in arayüzündeki gibi
  seçilen yol buton altında yeşil yazıyla gösteriliyor).
- Sınıflar alanı hâlâ elle yazılıyor (bu bir dosya/klasör değil, kısa bir
  metin listesi olduğu için native seçiciye gerek yok).

**Test durumu:** Python (`py_compile`) ve JavaScript (`node --check`)
syntax kontrollerini yaptım, ikisi de temiz. Ama native pencerenin
gerçekten açılıp doğru klasörü döndürdüğünü BEN test edemiyorum (benim
ortamımda ekran/pencere sistemi yok) — bunu senin denemen gerekiyor.

### Senin yapman gerekenler
```
cd etiketleme_arayuzu
pip install -r requirements.txt
python app.py
```
Açılan pencerede "KLASÖR SEÇ" butonuna bas, `veri/images` klasörünü seç,
sonra "PROJEYİ YÜKLE"ye bas. Sınıfların otomatik `data.yaml`'dan geldiğini
göreceksin. Bir sorun olursa (buton tepki vermiyor, pencere açılmıyor,
hata mesajı vs.) bana anlat.

### Güncelleme: Ctrl+yakınlaştırma, crosshair, ve "etiketlendi mi" netliği
Sen SADEKTECH'in arayüzünden bir ekran görüntüsü daha paylaştın (fareyi
izleyen kesişen çizgiler / crosshair) ve üç şey sordun: zoom nasıl
olacak, crosshair nasıl eklenir, bir görselin etiketlenip
etiketlenmediğini nasıl anlayacaksın.

**Eklenenler (`static/app.js` önemli ölçüde yeniden yazıldı):**
1. **Ctrl + fare tekerleği = yakınlaştırma**, fare imlecinin altındaki
   nokta sabit kalacak şekilde (yani imlecin gösterdiği yer yakınlaşınca
   kaymıyor — "zoom to cursor"). Ctrl basılı değilken tekerlek normal
   sayfa davranışını bozmuyor.
2. **'R' tuşu:** yakınlaştırmayı sıfırlayıp görseli pencereye tam sığdırıyor.
3. **Crosshair:** Fareyi her hareket ettirende, canvas'ın tamamını
   kaplayan ince yatay+dikey iki çizgi fare konumunda kesişiyor — kutunun
   kenarlarını hizalarken referans noktası olsun diye.
4. **Koordinat sistemi mimarisi değişti:** Daha önce canvas'ın iç
   çözünürlüğü = görselin gerçek boyutuydu (zoom yoktu). Artık canvas
   sabit bir "pencere" (viewport), kutular hep görselin gerçek piksel
   uzayında tutuluyor, ekranda nasıl göründüğünü zoom+pan (kaydırma)
   belirliyor. Bu, ileride "sürükleyerek gezinme" gibi özellikler
   eklemeyi de kolaylaştırıyor.

**"Etiketlendi mi, işe yarıyor mu?" sorusuna cevap:**
- Sağ paneldeki görsel listesinde her dosyanın yanında ✓ (etiketlenmiş,
  en az 1 kutu kaydedilmiş) ya da ○ (henüz etiketlenmemiş) işareti VAR
  — bunu belki fark etmemişsindir, listeyi kontrol et.
- Sol panele artık "Etiketlenen: X / toplam" şeklinde genel bir ilerleme
  sayacı da ekledim, daha görünür olsun diye.
- Her kayıtta (elle "Kaydet" ya da otomatik, görsel değiştirirken) artık
  üst barda "✔ Kaydedildi (N kutu)" mesajı kısa süreliğine beliriyor.
- En somut doğrulama: bir görseli etiketleyip başka bir görsele geçtikten
  sonra GERİ dön — çizdiğin kutu(lar) aynı yerde, aynı sınıfla tekrar
  görünüyorsa, kayıt/okuma doğru çalışıyor demektir (bu, benim
  backend'de curl ile yaptığım "round-trip" testinin tarayıcı/uygulama
  üzerinden senin de tekrarlayabileceğin hali).

**Test durumu:** JS (`node --check`) ve Python (`py_compile`) syntax
kontrolleri temiz. Zoom/crosshair'in gerçek fare etkileşimini yine BEN
test edemiyorum — senin denemen gerekiyor.

### Güncelleme: Orta tuşla gezinme + kolay kutu silme + "işe yarıyor mu" netliği

**Senin sorunun (asıl önemlisi):** "Etiketlemenin işe yaradığını nasıl
göreceğim, kaç etiketleme/test yapmalıyım, hangi aşamadayız?" — Bunu
netleştirdim: Adım 4'teyiz (sadece veri toplama/etiketleme), "işe yarıyor
mu" ancak Adım 5 (eğitim) + Adım 8 (görmediği görsellerle test) sonrası
görülebilir. **Öneri: hemen 80-150/sınıfın tamamını etiketlemek yerine,
önce küçük bir pilot yap** — 15-20 görsel/sınıf (~45-60 toplam) etiketle,
Colab'da hızlı/düşük epoch'lu bir deneme eğitimi yap, birkaç yeni
görselle test et. İşe yaradığını görürsen tam veri setine (80-150) devam
et — böylece büyük emek harcamadan önce mekanizmanın çalıştığını
doğrulamış oluyoruz (plaka/OCR adımlarında izlediğimiz "önce küçük test,
sonra büyüt" mantığının aynısı).

**Detect eğitimi: tek araç mı, trafik sahnesi mi?** Sordun. Cevap: trafik
sahnesi (çok araçlı, hepsi etiketli) aslında DAHA İYİ — bir fotoğraftan
çok daha fazla eğitim sinyali çıkarır, modelin örtüşme/farklı
mesafe-boyut durumlarını öğrenmesine yardımcı olur. Tek kural: bizim 3
sınıfımıza ait OLMAYAN araçları etiketleme, boş bırak (etiketlenmeyen
nesneler otomatik "arka plan" sayılır, sorun çıkarmaz — ama yanlış
etiketlemek modeli yanıltır).

**Eklenen arayüz özellikleri (`static/app.js`):**
1. **Orta fare tuşuyla gezinme (pan):** Basılı tutup sürükleyince görsel
   kayıyor (zoom yapınca özellikle işe yarar, kenarlara gitmek için).
2. **Kutunun üstüne SOL tıklama = seçme** (daha önce hiçbir yerde
   `seciliKutuIndex` set edilmiyordu, yani Delete tuşu hiçbir zaman işe
   yaramıyordu — bunu fark edip düzelttim).
3. **Kutunun üstüne SAĞ tıklama = anında silme** (seçmeden, tek tıkla).

**Test durumu:** JS syntax kontrolü temiz. Bu üçünü de (pan, sol-tık-seç,
sağ-tık-sil) yine tarayıcı/fare etkileşimi gerektirdiği için ben test
edemiyorum.

---

## Proje adı ve senaryo kesinleşti: OtoGöz / AutoEye (2026-07-28)

Konuştuk: ana senaryo olarak otopark/dükkan girişini izleyen sabit
güvenlik kamerası çerçevesini seçtik (giriş/çıkış loglama +
aranabilirlik) — mimari zaten (detect sayesinde) daha geniş/çoklu araçlı
kamera görünümlerinde de çalışıyor, bu ayrı bir sistem değil aynı
mimarinin bir gücü. Basmakalıp olmama gerekçesi netleştirildi: salt
plaka okuma bilinen bir problem, projenin özgünlüğü fusion mantığında.
Giriş/çıkış için fiziksel çizgi gerekmediği, sanal referans + tracking
yeterli olduğu, dükkan/ev önünde de çalışacağı konuşuldu.

**Proje adı: OtoGöz / AutoEye.** Brief'in başlığına ve ilgili bölümlere işlendi.

### Durum
Pilot etiketlemeye başlanıyor.

---

## Hata düzeltmesi: "eski etiketler kayboldu" (2026-07-28)

Az önce klasör-çakışması hatasını düzeltirken (etiketleri `labels/`
yerine `labels/<klasör_adı>/` altına taşıdım), yeni bir sorun yarattım:
sen daha önce çalıştığın klasörde (eski, düz `labels/` konumunda)
etiketlemiştin, ama arayüz artık YENİ konuma bakıyor — orada dosya
olmadığı için etiketlerin "kaybolmuş" gibi göründü. Aslında hiçbir şey
silinmedi, sadece arayüz farklı bir yere bakıyordu.

**Düzeltme:** `app.py`'ye geriye dönük uyumluluk eklendi
(`_etiket_oku` fonksiyonu) — bir görselin etiketini ararken önce YENİ
konuma (`labels/<klasör_adı>/`) bakıyor, orada yoksa ESKİ düz konuma
(`labels/`) bakıyor. Yani eski çalışman kaybolmadı, otomatik bulunacak.
Bir görseli tekrar kaydettiğinde (Kaydet'e basınca ya da görsel
değiştirince otomatik) dosya YENİ konuma yazılacak — yani ilk açılışta
"eski konumdan okuyup göstermek", sonraki kayıtta "yeni konuma yazmak"
şeklinde kademeli bir geçiş oluyor, elle taşımana gerek yok.

**Test:** Bunu kendi tarafımda simüle ettim — sahte bir eski-konum
etiketi oluşturdum, arayüzün (Flask backend) bunu doğru bulup
gösterdiğini, tekrar kaydedince yeni konuma yazıp eski dosyaya
dokunmadığını `curl` ile doğruladım. ✅ (pywebview'ın kendisini yine
test edemedim, sadece backend mantığını.)

**Not:** Benim tarafımda `otopark/veri/fiat_egea` vb. klasörleri
kontrol ettiğimde boş görünüyor — muhtemelen senin bilgisayarındaki
değişiklikler henüz OneDrive'a senkronize olmadı, ya da farklı bir yol
seçmiş olabilirsin. Endişelenme, bu düzeltme senin kendi
bilgisayarındaki gerçek dosyalar için geçerli olacak.

### Senin yapman gerekenler
Uygulamayı yeniden başlat (`python app.py`), daha önce etiketlediğin
klasörü aç, etiketlerin geri geldiğini doğrula.

---

## Birleştirme script'i: sınıf klasörlerinden eğitime hazır yapıya (2026-07-28)

Sordun: "bundan sonra her etiketleme nereye kaydedilecek, eğitirken
nereyi kullanacağım?" Netleştirdim: şu an her sınıf kendi klasörüne
kaydediliyor (`veri/fiat_egea/` + `veri/labels/fiat_egea/` gibi) — bu
BİLİNÇLİ bir ara aşama, henüz eğitime hazır değil. Eğitim `veri/data.yaml`
üzerinden TEK bir `images/`+`labels/` (düz, birebir eşleşen) yapı
bekliyor.

**`kod/04_veri_birlestir.py` yazdım** — bu iki aşama arasındaki köprü:
- Her sınıf klasöründeki SADECE ETİKETLENMİŞ (dolu .txt'si olan)
  görselleri, sınıf adı ön ekiyle (çakışma olmasın diye, örn.
  `fiat_egea_0007.jpg`) `veri/images/` + `veri/labels/` içine kopyalıyor.
- Etiketlenmemiş görselleri atlıyor (uyarı olarak sayıyor, silmiyor).
- Kopyalama yapıyor, TAŞIMIYOR — orijinal sınıf klasörlerine dokunmuyor,
  etiketlemeye devam edip script'i tekrar çalıştırabilirsin (zaten
  kopyalanmış olanları atlar, sadece yenileri ekler).

**Test:** Sahte bir senaryo kurdum (2 sınıf, biri etiketli biri
etiketsiz görsel) ve script'i çalıştırıp doğru dosyaların doğru
isimlerle kopyalandığını, etiketsizin atlandığını doğruladım. ✅ Test
verilerini temizledim.

### Cevap — nereye kaydediliyor / eğitimde ne kullanılacak
- **Etiketleme sırasında:** her sınıf kendi klasörüne (`veri/<sınıf>/`
  + `veri/labels/<sınıf>/`).
- **Eğitimde:** `python kod/04_veri_birlestir.py` çalıştırıp hepsini
  `veri/images/` + `veri/labels/`'e birleştireceğiz, Colab'a bu ikisini
  (+ `data.yaml`) yükleyeceğiz.

### Durum
Pilot etiketleme devam ediyor (hedef: ~15-20/sınıf). Bitince
`04_veri_birlestir.py` çalıştırılacak, sonra Adım 5 (pilot eğitim).

---

## Hata: Klasör değiştirince aktif sınıf sıfırlanmıyordu (2026-07-28)

Sen: "clio4 klasöründe etiketledim, sonra klasör değiştirip clio3
seçtim, ama hâlâ clio4 olarak etiketliyor" dedin. Gerçek bir tasarım
hatasıydı: `aktifSinif` (o an hangi sınıfla kutu çizeceğini tutan
değişken) klasör/proje değiştirince HİÇ sıfırlanmıyordu — önceki
klasörde son bıraktığın sınıf sessizce yeni klasörde de aktif kalıyordu.
Sen sidebar'dan manuel tıklamayı unutursan (ya da tıkladığını
sanıyorsan ama aslında tıklamadıysan), farkında olmadan yanlış sınıfla
etiketlemeye devam ediyordun.

**Düzeltme (`static/app.js`):**
1. Her yeni proje/klasör yüklendiğinde `aktifSinif` artık HER ZAMAN
   sıfırlanıyor — eskisini asla sessizce taşımıyor.
2. Klasör adını sınıf isimleriyle otomatik eşleştirmeye çalışıyor
   (`sinifiOtomatikSecmeyeCalis`) — örneğin klasör adı "fiat_egea"
   içeriyorsa otomatik o sınıfı seçiyor. Eşleşme yoksa ilk sınıfa (1.
   sınıf) dönüyor.
3. Üst bara, gözden kaçması neredeyse imkansız, BÜYÜK ve RENKLİ bir
   "Aktif sınıf: X" göstergesi ekledim — artık sadece sol paneldeki
   küçük vurguya değil, ortadaki büyük banda da bakarak hangi sınıfla
   etiketlediğini her an görebilirsin.

**ÖNEMLİ — geçmiş veriyi kontrol et:** Bu hata nedeniyle, clio3
klasöründe iken yanlışlıkla clio4 sınıfıyla kaydedilmiş etiketler
olabilir. Etiketleme arayüzünde clio3 klasörünü tekrar aç, her kutunun
üzerindeki etiket adını (canvas üzerinde kutunun üstünde yazan isim)
kontrol et — "renault_clio4" (ya da hangisiyse clio4'ün karşılığı)
yazan kutular varsa, o görsele geri dönüp kutuyu silip doğru sınıfla
yeniden çizmen gerekiyor.

**Test durumu:** JS syntax kontrolü temiz, mantığı kod okuyarak
doğruladım. Gerçek fare/klasör değiştirme senaryosunu yine tarayıcı/
uygulama üzerinden senin test etmen gerekiyor.

---

## Kök sebep bulundu: data.yaml elle girilen sınıfları görmezden geliyordu (2026-07-28)

Bir önceki düzeltme yeterli olmadı — sen hâlâ "clio3 yazsam bile sınıfa
sadece clio4 çıkıyor" dedin. Asıl sebep farklıymış: `veri/data.yaml`
zaten VAR olduğu için, backend "Sınıflar" kutusuna ne yazdığını
TAMAMEN görmezden gelip sessizce eski dosyadaki isimleri
(`renault_clio3`, `renault_clio4`, `fiat_egea`) kullanıyordu.

**Düzeltme (`app.py`):** Öncelik sırası netleştirildi — artık elle
yazılan sınıf listesi HER ZAMAN en yüksek öncelikli; varsa var olan
`data.yaml`'ı bu yeni listeyle günceller. `data.yaml` ancak elle bir
şey yazılmadıysa devreye giriyor.

**Dikkat (sana ilettim, cevap bekleniyor):** Gerçek sınıf isimlerini
netleştirmemiz lazım — "clio3/clio4/egea" mi olacak yoksa
"renault_clio3/yeni" mi kalacak? Hangi isimde karar kılarsak
`data.yaml`'ı bir kere doğru kurup üzerinde sabit tutmalıyız; her
seferinde farklı yazmak sınıf ID eşlemesini karıştırıp önceki
etiketlerin anlamını bozabilir.

---

## Hub (ana menü) arayüzü kuruldu (2026-07-28)

nevfel.txt'nin "tüm arayüzlere tek bir arayüz üstünden erişilebilinir
olmalı" şartı için, adım adım dolduracağımız bir kabuk/hub kurduk:

- `templates/index.html` artık HUB (ana menü) — 5 aracın kartını
  gösteriyor: Data Etiketleme (Hazır, tıklanabilir), Dataset Splitter,
  Data Augment, Model Eğitimi, Model Test (hepsi "Yakında", pasif).
- Eski etiketleme arayüzü `templates/etiketleme.html`'e taşındı,
  `/etiketleme` route'unda açılıyor, üstünde "← Araç Seti'ne Dön"
  linki var.
- `app.py`: `/` hub'ı render ediyor, `/etiketleme` etiketleme sayfasını
  render ediyor. pywebview pencere başlığı "YOLO Araç Seti" oldu.
- Plan: Etiketleme'yi sağlamlaştırıp bitirdikten sonra sırayla Dataset
  Splitter → Augment → Eğitim arayüzü → Test arayüzü eklenecek, her biri
  bitip test edilmeden bir sonrakine geçilmeyecek (otopark'ta izlediğimiz
  yöntemin aynısı).

**Test:** Flask route'larını (`/` ve `/etiketleme`) curl ile test ettim,
ikisi de doğru içerikle 200 döndü. Native pencere navigasyonunu
(hub'dan etiketlemeye tıklayarak geçiş) yine sende test etmen gerekiyor.

---

## Sınıf isimleri kesinleşti + data.yaml güvenlik kilidi (2026-07-28)

### Yaşanan sorun
Sen "asd" diye yeni bir sınıf yazdığında, önceden "clio4" ile etiketlenmiş
60 görselin HEPSİ geriye dönük "asd" oldu. Sebep: YOLO etiket dosyaları
sınıfı sadece bir SAYI (ID) olarak tutar, isim tutmaz — o ID'nin anlamı
tamamen `data.yaml`'a bağlı. Aracımız daha önce, elle yazılan farklı bir
sınıf listesini var olan `data.yaml`'ın üzerine sessizce yazıyordu, bu da
paylaşılan dosyayı kullanan TÜM klasörlerin etiketlerinin anlamını
bozdu.

**Önemli:** Etiket `.txt` dosyalarının kendisi hiç bozulmadı/silinmedi —
sadece isim listesi karıştı. Yani veri kaybı yok, sadece isim eşlemesi
düzeltilmesi gerekiyor.

### Kalıcı düzeltme (`app.py`)
Artık **var olan bir `data.yaml`'ı bu araç ASLA sessizce üzerine
yazmıyor.** Elle yazılan sınıf listesi, dosyadaki mevcut listeden
FARKLIYSA işlem durduruluyor ve açık bir hata gösteriliyor (mevcut
sınıfları da hata mesajında listeliyor). Farklı bir şema gerekiyorsa
kullanıcı açıkça ayrı bir `data.yaml` dosyası seçmeli. Test ettim: aynı
liste kabul ediliyor, farklı liste reddediliyor, dosya bozulmuyor. ✅

### Sınıf isimleri kesinleşti
Nihai liste (mevcut sırayla, sadece isimler netleşti):
```
0: renault_clio3   (eski kasa)
1: renault_clio4   (yeni kasa)
2: fiat_egea
```
`veri/data.yaml`, `PROJE_BRIEF_OTOPARK.md`, `kod/03_gorsel_indir.py`,
`etiketleme_arayuzu/templates/etiketleme.html` içindeki tüm eski isim
referansları (`renault_clio_eski`/`renault_clio_yeni`) bu yeni isimlerle
güncellendi (bir subagent'a yaptırdım, sonra `grep` ile hiç eski isim
kalmadığını doğruladım).

### Senin yapman gerekenler — local data.yaml'ını düzelt
Kendi bilgisayarındaki `veri/data.yaml` dosyasını aç, `names:` bölümünü
tam olarak şu şekilde olacak şekilde düzelt (sıra ÖNEMLİ, mevcut
etiketlerinle uyumlu kalması için):
```yaml
names:
  0: renault_clio3
  1: renault_clio4
  2: fiat_egea
```
Bunu kaydettikten sonra, daha önce "clio4"/"asd" karışıklığı yaşadığın
görselleri tekrar aç — doğru isimle göründüklerini doğrula.

---

## Daha iyi tasarım: Hata yerine onay isteme (2026-07-28)

Sen haklı olarak sordun: "hata vermesin, defaultlar hep kalsın, yeni
sınıf girilirse eklemek ister misin diye sorsun, kullanıcı onayıyla
eklesin — bu daha doğru olmaz mı?" Evet, kesinlikle. Önceki
"farklıysa reddet" yaklaşımı kaba bir çözümdü. Yeni tasarım:

**`app.py`:**
- Var olan sınıflar ARTIK HİÇBİR ZAMAN silinmiyor/yeniden adlandırılmıyor/
  sırası değişmiyor — bunlar her zaman "varsayılan" olarak korunuyor.
- Elle yazılan listede var olanların dışında YENİ bir isim varsa, backend
  hemen kaydetmiyor — `{"onay_gerekli": true, "yeni_siniflar": [...],
  "mevcut_siniflar": [...]}` diye bir cevap dönüyor (hata değil, normal
  bir "onay bekleniyor" durumu).
- Frontend bunu görünce `confirm()` penceresi açıyor: "Şu yeni sınıflar
  var: X. Eklemek ister misin?" Onaylarsan `onay: true` ile tekrar
  gönderiliyor, backend yeni sınıfları var olanların SONUNA ekliyor
  (mevcut ID'ler asla kaymıyor). Onaylamazsan, yazdığın yeni isimler
  unutulup var olan sınıflarla devam ediliyor — hiçbir hata ekranı
  görmüyorsun.

**Yan hata ve düzeltmesi:** İlk testimde, sınıf eklerken `data.yaml`'ın
`path/train/val/test` alanlarının da yanlışlıkla o anki geçici klasör
adına göre üzerine yazıldığını fark ettim (`data_yaml_yaz` fonksiyonu
dosyayı komple yeniden oluşturuyordu). Ayrı bir fonksiyon
(`data_yaml_sinif_guncelle`) yazdım — bu SADECE `names` bölümünü
günceller, diğer alanlara dokunmaz. İzole bir test ortamında (gerçek
projeye dokunmadan) hem "onaysız -> dosya değişmiyor" hem "onaylı ->
sadece yeni sınıf ekleniyor, path'ler bozulmuyor" senaryolarını `curl`
ile doğruladım. ✅

(Not: bu düzeltmeyi test ederken gerçek `veri/data.yaml`'ı yanlışlıkla
bir kez bozdum — fark edip hemen doğru haline geri yazdım, veri kaybı
olmadı.)

### Durum
Kod tarafı hazır ve test edildi. Sende: uygulamayı yeniden başlat,
etiketlemeye devam et — artık ne yaparsan yap var olan sınıfların
bozulması mümkün değil, sadece gerçekten yeni bir isim yazarsan onay
sorulacak.

---

## Birleştirme script'i harici klasörleri de destekliyor (2026-07-28)

`04_veri_birlestir.py` çalıştırdın ama hepsi "toplam=0" döndü — sebep:
senin etikettelediğin `clio3`/`clio4`/`egea` klasörleri `otopark/veri/`
İÇİNDE değildi, `C:\Users\nvflb\OneDrive\Desktop\brave indirilen\` altında,
ayrı bir konumdaydı. Script sadece `veri/`'nin doğrudan içini tarıyordu,
o yüzden bu klasörleri hiç göremedi.

**Genel kural (bir dahaki sefere karışmasın diye):** Sınıf klasörleri
`otopark/veri/` içinde OLMALI. Fotoğraf/klasör başka bir yerdeyse
(Masaüstü, "brave indirilen" gibi), birleştirme script'i onları
otomatik bulamaz.

**Düzeltme:** `04_veri_birlestir.py`'yi, artık klasör yolu ARGÜMAN olarak
da kabul edecek şekilde güncelledim — bilgisayarındaki HERHANGİ bir
konumdaki klasörü işleyebiliyor artık, etiketleme arayüzüyle AYNI mantığı
kullanarak (önce `<klasör>/../labels/<klasör_adı>/`, yoksa eski düz
`<klasör>/../labels/`) etiket dosyalarını buluyor. **Test ettim** (harici
bir klasör simüle ederek): doğru şekilde bulup birleştirdi. ✅

### Senin çalıştırman gereken komut
```
python kod/04_veri_birlestir.py "C:\Users\nvflb\OneDrive\Desktop\brave indirilen\clio3" "C:\Users\nvflb\OneDrive\Desktop\brave indirilen\clio4" "C:\Users\nvflb\OneDrive\Desktop\brave indirilen\egea"
```
Çıktıdaki sayıları (toplam/kopyalanan/etiketsiz) bana yapıştır, kontrol
edip Adım 5'e (pilot eğitim) geçelim.

---

## Adım 6: Fusion — ilk gerçek test, bilinen bir OCR hatası bulundu (2026-07-30)

### Ne yaptım
Fusion mantığını (marka/model + plaka + OCR birleştirme) hem `kod/06_fusion.py`
(komut satırı) hem de Toolset'e `/fusion` sekmesi olarak ekledim. Gerçek bir
görselle (telcam1 klasöründeki WhatsApp fotoğrafı) ilk test yapıldı.

### Sonuç
- Marka/model tespiti mükemmel çalıştı: `fiat_egea`, güven 0.967 ("kesin").
- Plaka kutusu doğru bulundu (güven 0.94), eşleştirme de doğru araca yapıldı.
- **OCR'da bilinen bir hata var**: gerçek plaka "01 BCP 836" iken, OCR çıktısı
  "ITRIC01BCPFM4LDRE836" oldu. Muhtemel sebep: plakanın SOLUNDAKİ mavi/beyaz
  "TR" şerit bandı ve/veya plakanın ÜSTÜNDEKİ marka yazısı (bu örnekte "Maserati"
  logosu/yazısı kutunun içine girmiş olabilir) OCR tarafından plaka metniyle
  aynı bloğa karışıp birleştiriliyor. Sistem bunu YANLIŞLIKLA doğru göstermedi —
  `format_gecerli=False` olarak işaretledi (güven katmanlama tam da bunun için
  var), yani "kesin" değil "format geçersiz" dendi. Yani mantık ÇALIŞIYOR
  (yanlışı gizlemiyor), ama OCR'ın ham çıktısının kendisi kirli.

### TODO (henüz düzeltilmedi) — ESKİ NOT, ÇÖZÜLDÜ (bkz. altındaki güncelleme)
- ~~Plaka kırpma/pay (padding) oranını gözden geçir~~
- ~~`sol_seridi_kirp` oranını yeniden test et~~ (bu fonksiyon tamamen kaldırıldı)
- ~~Plaka kutusunun sadece alt yarısını OCR'a vermek~~
- ~~Birden fazla gerçek fotoğrafla tekrar test et~~

---

## OCR motoru değişimi: EasyOCR → fast-plate-ocr (2026-07-31)

### Ne yaptım
Yukarıdaki "kirli OCR okuma" sorununu kırpma-heuristiği ince ayarlarıyla
(beyaz bölgeye kırpma, sol şerit kırpma, güvenlik payı) çözmeye çalıştım,
kısmi iyileşme oldu ama sorun tam gitmedi (bazı fotoğraflarda bayilik
çerçevesi/yazısı hâlâ "beyaz bölge" sayılıp karışıyordu). Kullanıcı
sordu: "büyük yerler bu sorunu nasıl çözmüş?" — araştırdım.

### Kök sebep ve çözüm
Profesyonel ANPR (otomatik plaka tanıma) sistemleri genel amaçlı bir OCR
kullanmıyor; plaka TESPİTİNİ ayrı bir model (bizde zaten var:
`plaka_tespit.pt`), plaka METNİ OKUMASINI ise dar bir alanda (sadece
plaka karakterleri/formatları) özel eğitilmiş ikinci bir model yapıyor.
EasyOCR genel sahne-metni için eğitilmiş — mimarisi yanlış değildi
(CRNN+CTC, fast-plate-ocr ile aynı yaklaşım), ama eğitim VERİSİ plakaya
özel değildi, bu yüzden marka logosu/çerçeve yazısıyla karışıyordu.

**Çözüm:** `fast-plate-ocr` kütüphanesine (model: `cct-s-v2-global-model`)
geçildi — `fast-alpr`/`fastanpr` gibi alternatifler ELENDİ çünkü onlar
kendi plaka TESPİTLERİNİ de bundle ediyor, bizim kendi
`plaka_tespit.pt`'imizle çakışır/gereksiz tekrar olurdu. `fast-plate-ocr`
sadece OKUMA yapıyor (tespiti yok), tam olarak bizim mimarimize uyuyor.

### Değişen dosyalar
- `etiketleme_arayuzu/app.py`: `_fusion_ocr_okuyucusunu_yukle` artık
  `fast_plate_ocr.LicensePlateRecognizer` yüklüyor; `_fusion_plakayi_oku`
  yeniden yazıldı (RGB'ye çevirip `.run(rgb, return_confidence=True)`
  çağırıyor); EasyOCR'a özel `_fusion_on_isle`, `_fusion_otsu_esikleme`,
  `_fusion_bloklari_birlestir`, `_fusion_en_iyi_sonucu_sec` ve
  `FUSION_ALLOWLIST` kaldırıldı (artık gereksiz — fast-plate-ocr zaten
  tek/temiz bir metin döndürüyor, çok-bloklu birleştirmeye gerek yok).
- `kod/06_fusion.py` (CLI script): app.py ile senkronize edildi — aynı
  OCR motoru swap'ı + tanımlanmadı fallback + HEIC desteği + çizim
  ölçekleme app.py'den taşındı (daha önce CLI script geride kalmıştı).
- Her iki `requirements.txt`: `easyocr` çıkarıldı, `fast-plate-ocr[onnx]`
  eklendi (GPU'lu kullanım için `[onnx-gpu]` alternatifi not edildi).

### Durum
Kullanıcı test etti: "tamam iyi çalışıyor" onayı alındı. Sorun kapandı.

---

## Model Test'e gerçek zamanlı Webcam modu eklendi (2026-07-31)

### Ne yaptım
Model Test aracına üçüncü bir mod (Görsel/Video'nun yanına Webcam)
eklendi — canlı kamera görüntüsü üzerinde anlık tespit.

### Nasıl çalışıyor
Flask'ta bir MJPEG akış route'u (`/api/test/webcam_stream`,
`multipart/x-mixed-replace` içerikli) + arka plan thread'inde
`cv2.VideoCapture` ile kare okuyup modeli çalıştıran bir döngü
(`_webcam_yakalama_dongusu`). Frontend'de `<img>` etiketinin `src`'i
doğrudan bu akış adresine bağlanıyor — tarayıcı her yeni kareyi otomatik
gösteriyor, ekstra JS polling'e gerek yok (durum/hata bilgisi için ayrı,
hafif bir JSON polling var).

### Bulunan hata ve düzeltmesi
Kullanıcı "Canlı -- işlenen kare: 0" görüp görüntü göremedi, kameraya
bir şey de göstermemişti. Sebep: Windows'ta `cv2.VideoCapture.isOpened()`
`True` dönebiliyor ama `.read()` sürekli `False` dönebiliyor (genelde
kamera gizlilik izni engeli) — sessiz bir hata modu, hiç exception
fırlatmıyordu. Düzeltme: önce `cv2.CAP_DSHOW` backend'iyle dene (Windows
uyumluluğu daha iyi), ardışık ~100 başarısız okumadan sonra Windows
Ayarlar > Gizlilik ve Güvenlik > Kamera yoluna işaret eden açık bir hata
fırlat, ve kamera handle'ının `finally` bloğunda HER durumda (hata olsa
bile) serbest bırakıldığından emin ol. Kullanıcı Windows izinlerini
kontrol edip "tamam çalışıyor" dedi.

---

## Adım 7: SQLite şeması kuruldu (2026-07-31)

### Ne yaptım
`kod/07_veritabani.py` yazıldı: `db/otogoz.db` içinde tek bir
`tespitler` tablosu (id, tespit_zamani, gorsel_yolu, sonuc_gorsel_yolu,
marka_model, marka_model_guven, marka_model_durum, plaka, plaka_guven,
plaka_durum) + plaka/marka_model/zaman üzerinde index'ler. Fusion
(`app.py`'deki `/api/fusion/calistir`) artık her çalıştığında bu
tabloya da BİRİKİMLİ (üzerine yazmadan, EKLEYEREK) kayıt yazıyor --
`kayitlar/fusion_sonucu.json`'un aksine geçmiş kaybolmuyor.

### Tasarım kararları (nevfel ile birlikte)
- **Tek tablo** yeterli görüldü -- ayrı "araçlar"/"geçişler" tablosuna
  normalize etmedik, `WHERE plaka = ...` ile arama zaten mümkün.
- **Zaman damgası = Fusion'ın işlediği an** (fotoğrafın çekildiği an
  değil) -- projenin asıl senaryosu (sabit kamera, sürekli döngü) bu
  ikisini pratikte aynı ana getiriyor, EXIF okumak ekstra karmaşıklık +
  garanti olmayan bir veri kaynağı olurdu.
- **Görsel dosya YOLU tutuluyor, BLOB değil** -- binlerce görseli
  veritabanına gömmek dosyayı hızla büyütür, senkronizasyonu/incelemeyi
  zorlaştırır; mevcut `static/fusion_ciktilari/` klasör yaklaşımıyla
  zaten uyumlu.
- Yön takibi (#12) bilerek şemaya eklenmedi, ileride `ALTER TABLE` ile
  eklenecek.

### Hata toleransı
DB'ye yazma başarısız olursa (örn. dosya kilitli), hata sadece log'a
uyarı olarak düşülüyor -- Fusion'ın asıl çıktısı (görsel + JSON) BU
YÜZDEN bozulmuyor (`try/except` ile izole edildi).

### Durum
Kod hazır ve syntax doğrulandı. Kullanıcının kendi bilgisayarında bir
Fusion çalıştırıp `db/otogoz.db` dosyasının oluştuğunu ve
`SELECT * FROM tespitler;` ile satırların göründüğünü doğrulaması
bekleniyor.

### Doğrulama (kullanıcı tarafında)
DB Browser for SQLite ile açıp kontrol edildi -- şema doğru (tespitler
tablosu + 3 index), gerçek fotoğraflarla üretilen satırlar doğru
görünüyor (marka_model/plaka/güven/durum alanları tutarlı, aynı
görüntünün iki ayrı çalıştırması BİRİKİMLİ olarak iki ayrı satır
üretmiş -- üzerine yazma yok). Bir "tanımlanmadı" satırı da (plaka
okunamamış, `plaka=NULL`, `plaka_durum=okunamadi`) doğru şekilde
görüldü -- güven katmanlamanın gerçek/olumsuz durumu da dürüstçe
kaydettiği doğrulanmış oldu.

**Not:** DB Browser dosyayı açık tutarken aynı anda Fusion/İzleme
çalıştırılırsa "database is locked" hatası çıkabilir -- kullanıcıya
test öncesi DB Browser'ı kapatması/yenilemesi gerektiği söylendi.

**Brief'e göre #8 ("statik görüntüden uçtan uca zinciri birleştir")
bu noktada FİİLEN TAMAMLANMIŞ sayıldı** -- Fusion zaten
detect->OCR->classify->fusion->DB kayıt zincirini tek tıklamada
yapıyordu, DB entegrasyonuyla birlikte brief'teki tanım tam
karşılanmış oldu, ayrı bir kod yazmaya gerek kalmadı.

---

## Adım 9: Sürekli İzleme modu (video-kaynaklı MVP) (2026-07-31)

### Ne yaptım
Fusion sayfasına ikinci bir mod ("Sürekli İzleme (Video)") eklendi --
bir video dosyasını baştan sona kare kare işleyip, `model.track()`
(ByteTrack) ile her fiziksel araca kalıcı bir takip kimliği (ID)
atıyor. Bir ID ilk göründüğünde plaka tespiti+OCR çalıştırılıp DB'ye
kaydediliyor, aynı ID kadrajda kaldığı sürece TEKRAR kaydedilmiyor.

### Tasarım kararları (nevfel ile konuşuldu)
- **Dedup için plaka+zaman penceresi yerine tracking ID seçildi.**
  Sebep: plaka+zaman penceresi yaklaşımı plaka okunamadığında (NULL)
  hiçbir şeye dayanamazdı; tracking ID görsel/hareket bazlı olduğu için
  plakadan bağımsız çalışıyor. Ek avantaj: roadmap'teki #12 (giriş/
  çıkış yön takibi) da zaten `model.track()` istiyor, bu altyapı ileride
  #12'ye de temel oluşturacak.
- **Bilinen risk ve önlemi:** kullanıcı haklı olarak sordu -- "aynı
  karede 2 etiketleme yapıyordu, bu sorun olmaz mı?" Gerçek bir risk:
  marka/model modelinin class karışıklığından aynı fiziksel araca iki
  üst üste kutu vermesi, tracker'ın bunları iki ayrı ID sanmasına yol
  açabilirdi. Çözüm: `model.track(..., agnostic_nms=True)` -- kutuları
  TAHMİN EDİLEN SINIFI görmezden gelip sadece geometrik örtüşmeye göre
  birleştiriyor (normal NMS sadece aynı sınıftaki kutuları birleştirir).
- **Performans:** plaka tespiti HER karede değil, SADECE yeni bir
  track ID görülen karelerde çalıştırılıyor (her karede tüm modelleri
  çalıştırmak gereksiz yavaşlık olurdu).
- **Webcam'e bağlama bilerek bu MVP'ye dahil edilmedi** -- kullanıcının
  şu an webcam testi imkanı yoktu, video ile başlanması istendi. Ama
  döngünün çekirdeği (track -> yeni ID mi -> plaka eşle -> OCR -> DB)
  kaynaktan bağımsız yazıldı, ileride `cv2.VideoCapture(0)` + mevcut
  WEBCAM MJPEG akış altyapısıyla birleştirmek büyük bir değişiklik
  gerektirmeyecek.

### Değişen dosyalar
- `etiketleme_arayuzu/app.py`: yeni "FUSION -- SÜREKLİ İZLEME" bölümü
  (`IZLEME_DURUMU`, `_izleme_dongusu`, `/api/fusion/izleme_baslat`,
  `/api/fusion/izleme_durdur`, `/api/fusion/izleme_durum`).
- `templates/fusion.html`: "Tekli Görsel" / "Sürekli İzleme (Video)"
  mod sekmeleri eklendi (Model Test'teki mod-sekmesi deseniyle aynı).
- `static/fusion.js`: mod geçişi + izleme başlat/durdur/durum polling
  mantığı eklendi.

### Test durumu
Python (`ast.parse`) ve JavaScript (`node --check`) syntax kontrolleri
temiz. Gerçek bir video dosyasıyla uçtan uca test HENÜZ YAPILMADI --
kullanıcının kendi bilgisayarında bir test videosuyla denemesi
bekleniyor.

---

## Gerçek hata bulundu: aynı araç 2 farklı ID/2 DB kaydı aldı (2026-07-31)

### Sorun
Kullanıcı ilk video testinde, iki ayrı "izleme_*.jpg" kare görseli
paylaştı (id5 ve id9) -- ikisi de aynı beyaz araç gibi görünüyordu,
biri "renault_clio3" biri "renault_clio4" olarak etiketlenmiş, iki ayrı
DB satırı olarak kaydedilmişti. Sordu: "aynı arabaya 2 farklı frame
atmış... sorun nedir?"

### Teşhis
id5'in zaman damgası id9'dan ÖNCE -- yani muhtemelen aynı fiziksel araç
bir bariyer/geçiş kolu önünde kısa süre kaldı (kısmi kapanma) ya da
confidence dalgalandı, ByteTrack'in varsayılan `track_buffer=30` kare
(~1 saniye @ 30fps) toleransı yetmedi, eski ID silinip araç tekrar net
göründüğünde YENİ bir ID atandı. Sınıf tahmininin clio3/clio4 arasında
değişmesi (tablodaki düşük/"belirsiz" güven skorları bunu destekliyor)
büyük ihtimalle eğitim VERİSİ kaynaklı bir ayrı sorun (kullanıcı da
bunu fark etti) ama tracker ID kaybını TEK BAŞINA tetiklemiyor --
asıl etken düşük confidence'ın tracker'ı beslemekte kesintiye uğraması.

### Düzeltme (iki katmanlı)
1. **`etiketleme_arayuzu/bytetrack_ozel.yaml`** eklendi -- ultralytics'in
   varsayılan `bytetrack.yaml`'ından türetildi, `track_buffer` 30'dan
   90'a (yaklaşık 3-4 saniye toleransa), `track_low_thresh` 0.1'den
   0.05'e çekildi (düşük ama anlamsız olmayan tespitler de tracker'ı
   besliyor). `_izleme_dongusu`'nda `tracker="bytetrack.yaml"` yerine bu
   dosyanın tam yolu kullanılıyor artık.
2. **İkinci güvenlik ağı** (`_fusion_db_yakinda_ayni_plaka_var_mi`):
   tracker yine de ID kaybederse, DB'ye yazmadan hemen önce "bu plaka
   son 15 saniyede zaten kaydedildi mi" kontrolü yapılıyor -- öyleyse
   yeni kayıt ATLANIYOR (muhtemelen aynı aracın ID'si değişmiş).
   ÖNEMLİ: bu, daha önce "tracking ID mi plaka+zaman penceresi mi"
   tartışmasında ELENEN yaklaşımın, tracking'in YERİNE değil, ONA EK bir
   güvenlik katmanı olarak geri getirilmiş hali -- plaka okunamayan
   (NULL) durumlarda hâlâ çalışmıyor ama okunabilen durumlarda
   tracker'ın kaçırdığı tekrarları da yakalıyor.

### Test durumu
Syntax kontrolleri temiz, `bytetrack_ozel.yaml` geçerli YAML olarak
doğrulandı. Kullanıcının AYNI test videosuyla tekrar denemesi ve artık
tek kayıt/ID çıkıp çıkmadığını doğrulaması bekleniyor.

---

## İkinci hata: tek-kareli OCR ve "hayalet" tespit (2026-07-31, devam)

### Sorun
Kullanıcı bariyer önünde duran (far yanan, kısmen yansımalı) bir aracın
görselini paylaştı -- kutu, ARACIN OLMADIĞI boş bir bölgeye (bariyer
kolunun sağı) çizilmişti, "fiat_egea 0.398" gibi düşük güvenle. Ayrıca
DB'de plaka=NULL/"bulunamadi" olan satırların çokluğunu fark edip
sordu: "bir araba algılayınca algılar algılamaz mı plaka okumaya
çalışıyor? öyleyse bu okuyamama nedeni olabilir, araç frameden çıkana
kadar daha iyi okuyacağı an olabilir."

### Teşhis
1. **"Hayalet" kutu:** DB'de BİREBİR aynı güven değerlerinin (0.398,
   0.877) birden fazla satırda tekrar etmesi, bunun tracking hatası
   değil, marka/model modelinin sabit bir arka plan öğesinde (bariyer/
   zemin deseni) tekrarlayan düşük-güvenli bir YANLIŞ-POZİTİF ürettiğini
   gösteriyor -- modelin kendisiyle ilgili (eğitim verisi/hard-negative
   eksikliği), tracking/OCR mantığıyla ilgili değil.
2. **Tek-kareli OCR -- kullanıcı haklı çıktı:** Eski tasarım, bir araç
   YENİ bir track ID aldığı TEK karede plaka okumayı deniyor, sonucu
   (başarısız bile olsa) kalıcı kabul edip bir daha denemiyordu. İlk
   kare genelde en kötü kare olabiliyor (far yansıması, açı, kısmi
   görünürlük) -- DB'deki çok sayıdaki "bulunamadi" bunun somut kanıtı.

### Düzeltme
`_izleme_dongusu` baştan tasarlandı: artık bir araç YENİ bir "bekleyen"
kaydı açıyor (DB'ye HENÜZ yazılmıyor), araç kadrajda kaldığı SÜRE
BOYUNCA her karede (henüz format-geçerli bir plakası yoksa) plaka
okuma tekrar deneniyor, EN İYİ sonuç (önce format-geçerlilik, sonra en
yüksek OCR güveni) tutuluyor; marka/model tahmini de kareler arasında
EN YÜKSEK güvenli olanla güncelleniyor (tek kötü karenin class'ı
kalıcı kılmasını azaltmak için). Araç `IZLEME_KAYIP_ESIGI_KARE` (45
kare, ~1.5sn) boyunca hiç görünmezse YA DA video biterse, o ana kadarki
EN İYİ bilgiyle DB'ye FİNALİZE ediliyor (`_finalize_et` fonksiyonu).
Garbled/format-geçersiz plaka metni önceden olduğu gibi HÂLÂ siliniyor
DEĞİL -- ham (sadece harf/rakam) haliyle `plaka` sütununda tutuluyor
(`plaka_durum='format_gecersiz'`), yani kullanıcının bildiği kısmi
karakterlerle (`LIKE '%AZE%'` gibi) arama zaten mümkün.

"Hayalet" tespitler için kod tarafında agresif bir filtre EKLENMEDİ
(bilinçli karar) -- düşük güvenli ("belirsiz") kayıtlar artık log'da
"[DÜŞÜK GÜVEN -- muhtemelen yanlış/hayalet algılama olabilir]" notuyla
açıkça işaretleniyor, ama veri kaybetmemek için hâlâ kaydediliyor.
Kullanıcıya iki somut lever önerildi: (1) UI'daki "Confidence eşiği"ni
yükseltmek, (2) eğitim verisine boş/otopark arka planı gibi
hard-negative örnekler eklemek.

### Değişen dosyalar
`etiketleme_arayuzu/app.py` (`_izleme_dongusu` fonksiyonu baştan
yazıldı -- `bekleyenler` dict + `_finalize_et` iç fonksiyonu),
`templates/fusion.html` (açıklama metni yeni davranışı yansıtacak
şekilde güncellendi).

### Test durumu
Syntax kontrolü temiz. Kullanıcının AYNI test videosuyla tekrar
denemesi ve artık plaka okuma oranının/doğruluğunun arttığını
doğrulaması bekleniyor.

---

## Data Augment arayüz güncellemesi + Splitter seed + Eğitim grafikleri (2026-08-03)

### Ne yaptım
Data Augment arayüzünü kullanıcı geri bildirimiyle adım adım genişlettim:
"Tümünü Sıfırla" butonu eklendi, ardından bunun anlamlı olması için
gerçek görsel önizleme (orijinal + filtreli, yan yana) eklendi, sonra
sayfa Model Eğitimi ile aynı iki-sütun (sağda sabit önizleme paneli)
düzenine çevrildi ve önizleme her ayar değişince (debounce'lu) OTOMATİK
güncellenir hale getirildi. Ayrıca 3 yeni augment tekniği eklendi:
kontrast, gürültü (Gaussian pixel noise), sıkıştırma (JPEG round-trip
simülasyonu) -- artık 7 teknik var.

Dataset Splitter'a opsiyonel bir "Sabit seed" alanı eklendi
(`random.Random(seed)` izole örneği, global `random` state'ine
dokunmuyor); seed verilirse aynı bölme tekrar üretilebilir, `analiz.txt`
kullanılan seed'i (veya "verilmedi" notunu) raporluyor.

Model Eğitimi'ne, eğitim bitince ultralytics'in otomatik ürettiği
sonuç grafiklerini (`results.png`, `confusion_matrix.png`) gösteren bir
bölüm eklendi (`/api/egitim/grafik/<dosya_adi>`, sabit dosya-adı izin
listesiyle sınırlı).

### Opus ile kapsamlı review
Ardından tüm kod tabanını (app.py, kod/06_fusion.py, kod/07_veritabani.py,
tüm arayüz JS/HTML, README, bilgi_notlari) Opus modeliyle çalışan bir
subagent'a taratıp bulunan sorunları düzelttim:

- **Kritik:** Sürekli İzleme artık paylaşılan model önbelleğini DEĞİL,
  her çalıştırmada taze bir YOLO nesnesi kullanıyor -- `track(persist=True)`
  tracker state'ini kalıcı olarak Model nesnesine yazdığı için, önbellek
  paylaşılsaydı art arda iki İzleme çalıştırması ya da İzleme sonrası
  Tekli Görsel modu yanlış/tutarsız sonuç verebilirdi.
- **Kritik:** `kod/06_fusion.py`'ye, app.py'de zaten var olan boş-kırpık
  (`kirpik.size == 0`) guard'ı eklendi -- kadraj kenarına taşan bir plaka
  kutusunda CLI script'inin `ZeroDivisionError` ile çökmesini önlüyor.
- **Orta risk:** `/api/gorsel/<...>` DELETE route'unda path traversal
  kapatıldı (artık sadece dosya adı alınıp klasör altında olduğu
  doğrulanıyor); İzleme/Eğitim/Video-Test durum sözlükleri artık kilit
  altında okunup/yazılıyor (polling ile arka plan thread'i arasındaki
  nadir yarış riskine karşı); tüm model/OCR önbellek yükleyicileri artık
  `MODEL_ONBELLEK_KILIDI` ile korunuyor; `/api/etiket/...` route'larına
  "önce klasör yükle" kontrolü eklendi.
- **Küçük tutarsızlıklar:** İzleme'nin finalize adımındaki plaka durumu
  etiketi ("bulunamadi" → "okunamadi") tek-görsel moduyla aynı anlama
  getirildi; CLI'daki "tanımlanmadı" fallback aracının
  `marka_model_guven` değeri artık app.py gibi genel modelin güvenini
  yazıyor (önceden hep `None`'dı); bir yorumdaki eskimiş "EasyOCR"
  referansı düzeltildi; hata mesajları/açıklamalar 7 augment tekniğinin
  hepsini anıyor.
- **Doküman-kod çelişkileri:** `09_teknik_referans.txt`'deki "Splitter
  tekrarlanamaz" notu artık seed özelliğini yansıtıyor;
  `08_arayuz_araclari_rehberi.txt`'e webcam modu ve Sürekli
  İzleme/SQLite bahsi eklendi; README'deki eskimiş "ÖNİZLE butonu"
  referansları canlı önizlemeye güncellendi; `kod/06_fusion.py`'nin
  varsayılan görsel yolu gerçek konuma (`test edilecekler/telcam1/`)
  düzeltildi.

nevfel.txt gereksinim kontrolünde tek açık madde: mAP değerinin
arayüzde gösterilmesi (madde 5) -- şu an Test aracında yok, tek
görselde zaten hesaplanamaz, val seti üzerinde ayrı bir `model.val()`
metrik bölümü gerekebilir. Henüz kararlaştırılmadı/yapılmadı.

### Değişen dosyalar
`etiketleme_arayuzu/app.py`, `kod/06_fusion.py`,
`etiketleme_arayuzu/templates/augment.html`,
`etiketleme_arayuzu/static/augment.js`,
`etiketleme_arayuzu/templates/egitim.html`,
`etiketleme_arayuzu/static/egitim.js`,
`etiketleme_arayuzu/templates/splitter.html`,
`etiketleme_arayuzu/static/splitter.js`,
`etiketleme_arayuzu/static/style.css`, `README.md`,
`bilgi_notlari/08_arayuz_araclari_rehberi.txt`,
`bilgi_notlari/09_teknik_referans.txt`.

### Test durumu
Tüm değiştirilen `.py` dosyaları `ast.parse` ile, tüm `.js` dosyaları
`node --check` ile syntax kontrolünden geçirildi -- hepsi temiz.
Fonksiyonel test (Sürekli İzleme'nin art arda iki kez çalıştırılması,
Eğitim grafiklerinin gerçek bir eğitim sonunda görünmesi) kullanıcı
tarafında henüz yapılmadı.

---

## Model Test'e "Metrikler (mAP)" modu eklendi (2026-08-03, devamı)

### Ne yaptım
Yukarıdaki review'da bulunan tek nevfel.txt açığını (madde 5 -- mAP
değerinin arayüzde gösterilmesi) kapattım. Model Test sayfasına 4.
bir mod sekmesi eklendi: "Metrikler (mAP)". Kullanıcı bir model +
val bölümü içeren bir data.yaml (Dataset Splitter çıktısı gibi) seçip
"METRİKLERİ HESAPLA"ya basınca, arka planda ultralytics'in
`model.val()` fonksiyonu çalışıyor (video testindeki AYNI thread +
polling deseni -- val seti boyutuna göre sürebileceği için senkron
yapılmadı) ve sonuçta mAP50, mAP50-95, precision, recall sayıları
gösteriliyor. Tek görselde mAP hesaplanamadığı (ground-truth etiket
gerektiği) için bu modun ayrı bir val seti istemesi kasıtlı bir
tasarım kararı -- açıklama metninde de belirtildi.

### Değişen dosyalar
`etiketleme_arayuzu/app.py` (`METRIK_DURUMU`, `_metrik_hesapla_arka_planda`,
`/api/test/metrik_hesapla`, `/api/test/metrik_durum`),
`etiketleme_arayuzu/templates/test.html` (4. mod sekmesi + panel),
`etiketleme_arayuzu/static/test.js` (mod geçişi + polling mantığı),
`README.md`, `bilgi_notlari/08_arayuz_araclari_rehberi.txt`,
`bilgi_notlari/09_teknik_referans.txt`.

### Test durumu
`app.py` `ast.parse` ile, `test.html`/`test.js` okunabilirlik + id
eşleşmesi (`grep`) ile kontrol edildi -- hepsi temiz. Gerçek bir
model+val setiyle uçtan uca fonksiyonel test kullanıcı tarafında henüz
yapılmadı (ultralytics `DetMetrics.box` alanlarının -- `map50`, `map`,
`mp`, `mr` -- doğruluğu kütüphane API'sine dayanıyor, sandbox'ta
çalıştırılamadı).

---

## Klasör temizliği + "Evrensel Toolset" kopyası + nevfel.txt son denetim (2026-08-04/05)

### Ne yaptım
Kullanıcı "otopark klasörünü baştan sona düzenle, gereksizleri sil"
dedi. Önce tüm klasör ağacını (`du`, `find`, `runs/*/args.yaml`
içindeki `data:` yollarını çapraz kontrol ederek) inceledim, sonra
SADECE gerçekten gereksiz/süperlenmiş/boş olduğu doğrulanmış ~350 MB'lık
veriyi sildim (çalışma zamanı çıktı önbellekleri, boş klasörler, 3 eski
Augment denemesi, kullanılmayan bir model dosyası, kullanılmayan bir
`.venv`, eski bir `split.zip`). `ARABALAR/` klasörünü SİLMEDİM --
incelemede gerçekte `veri/images`'in kaynağı olduğu ortaya çıktı
(README yanlışlıkla "kullanılmıyor" diyordu), `veri/kaynak_gorseller/`
olarak taşıdım. Her kararın tam gerekçesi yeni `DUZENLEME_LOGU.md`
dosyasında.

Ardından `etiketleme_arayuzu/`'nün TAMAMININ bir kopyasını
`evrensel_toolset/` adıyla oluşturdum -- nevfel.txt'nin istediği 5
evrensel araç + 3 genel yardımcı araç aynen duruyor, ama OtoGöz'e özel
Fusion aracı bu kopyada VARSAYILAN KAPALI (ana sayfadaki bir anahtarla
tek tıkla açılabiliyor, `ayarlar.json`'da kalıcı). Kopyalanan kodda
Fusion'ın DB/kayıt yollarını da düzelttim (`parent.parent` →
`parent`) -- yoksa açılırsa otopark'ın kendi verisine karışırdı.
Orijinal `etiketleme_arayuzu/app.py`'ye kopya oluşturulduktan sonra
dokunulmadı.

Son olarak kullanıcı "nevfel.txt'deki arayüzler bitti diyebilir miyim"
diye sordu -- Opus subagent'a nevfel.txt'nin HER maddesini kod
okuyarak (dosya+satır kanıtıyla) tek tek doğrulattım. 5 maddeden 3'ü
(Etiketleme, Model Eğitimi, Model Test) tam karşılanıyordu. 2 gerçek
eksik bulundu ve düzelttim:

1. **Data Augment "sadece images + data.yaml" girdisini kabul
   etmiyordu** -- `_gorselleri_filtrele` etiket dosyası olmayan HER
   görseli filtre boşken bile listeden atıyordu (`app.py` eski
   satır 816-817), yani labels klasörü yoksa Augment "hiç görsel yok"
   hatası veriyordu. Düzeltme: fonksiyon artık `(gorsel, etiket_veya_None)`
   ikilileri döndürüyor, filtre boşken etiketsiz görseller de dahil
   ediliyor (filtre DOLUYSA hâlâ elenirler -- bir sınıfa
   filtrelenemezler çünkü etiketleri yok), çalıştırma döngüsü
   etiketsiz görseller için `shutil.copy2` yerine boş bir `.txt`
   yazıyor. `_etiketteki_sinif_idleri` de `None` girdiyi güvenle
   `set()` döndürecek şekilde güncellendi.
2. **Splitter'ın `analiz.txt`'si nevfel.txt'nin verdiği şablonla
   birebir değildi** -- emoji başlıklar (📊📂🎯) yoktu, "DETAYLI"
   kelimesi eksikti, "SINIF DAĞILIMI"/"Sınıf" yerine "CLASS
   DAĞILIMI"/"Class" yazıyordu. `_analiz_raporu_olustur`'daki 3 başlık
   satırı şablonla eşleşecek şekilde güncellendi (kolon genişlikleri
   şablonun kendisi iç tutarlı olmadığı için -- header ve data satırları
   farklı hizalarda -- birebir kopyalanmadı, ama okunabilir/yakın
   tutuldu).

Her iki düzeltme de HEM orijinal `etiketleme_arayuzu/app.py` HEM
`evrensel_toolset/app.py`'de (+ ilgili `augment.js` metin
düzeltmesi) aynı şekilde yapıldı.

### Değişen dosyalar
`DUZENLEME_LOGU.md` (yeni), `README.md`, `veri/` (ARABALAR taşındı),
`etiketleme_arayuzu/app.py`, `etiketleme_arayuzu/static/augment.js`,
`evrensel_toolset/` (yeni klasör: `app.py`, `templates/index.html`,
`templates/fusion_kapali.html` (yeni), `static/style.css`,
`static/augment.js`, `requirements.txt`, `README.md` (yeni)).

### Test durumu
`_analiz_raporu_olustur` gerçek sahte verilerle çalıştırılıp çıktı
gözle şablonla karşılaştırıldı (emoji/başlıklar birebir eşleşiyor).
`_gorselleri_filtrele`'nin "labels klasörü hiç yokken filtre boşsa tüm
görselleri, filtre doluyken hiçbirini döndürmesi" gerçek bir geçici
klasörle test edilip doğrulandı. Her iki `app.py` da `ast.parse`, her
iki `augment.js` da `node --check` ile temiz. Route sayıları
(`etiketleme_arayuzu/`: 42, `evrensel_toolset/`: 44 = 42 + `/api/ayarlar`
GET+POST) beklenen farkla eşleşiyor.

---
