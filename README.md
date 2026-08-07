# OtoGöz (AutoEye) — Otonom Araç Tanıma ve Log Sistemi

Bu depo iki iş içeriyor:

1. **OtoGöz / AutoEye** — sabit bir güvenlik kamerasının izlediği bir
   otopark/dükkan girişinde geçen araçları hem **plakasından** hem
   **marka/modelinden** tanıyıp, bu iki belirsiz sinyali birleştirerek
   ("Fusion") aranabilir bir veritabanına kaydeden kişisel bir staj
   prototipi. Tamamen hayali bir senaryo üzerine kurulu — gerçek üçüncü
   kişi verisi kullanılmıyor.
2. **Toolset** (`etiketleme_arayuzu/`) — YOLO tabanlı herhangi bir
   projede (sadece OtoGöz değil) kullanılabilecek, veri etiketleme /
   bölme / çoğaltma / eğitim / test için evrensel bir araç seti. Bu
   masaüstü uygulaması hem OtoGöz'ün kendi verisini üretmek için hem de
   bağımsız bir araç olarak kullanılıyor.

Projenin genel mantığı, güven katmanlaması ve bileşen mimarisi için:
[PROJE_BRIEF_OTOPARK.md](PROJE_BRIEF_OTOPARK.md). Gün gün ne yapıldığının
teknik dökümü için: [ILERLEME_GUNLUGU.md](ILERLEME_GUNLUGU.md). Staj
raporu için kısa özet: [STAJ_GUNLUK_OZET.md](STAJ_GUNLUK_OZET.md).

---

## 1) Kurulum

Gereksinim: Python 3.10+ (Windows'ta test edildi). NVIDIA GPU'n varsa
eğitim/çıkarım çok daha hızlı olur ama şart değil (CPU ile de çalışır,
sadece yavaş).

### Toolset'i (arayüz) çalıştırmak için

```
cd etiketleme_arayuzu
pip install -r requirements.txt
python app.py
```

Bu, tarayıcı AÇMAZ — doğrudan native bir uygulama penceresi açılır
(pywebview ile). Arka planda `http://127.0.0.1:5000` adresinde bir Flask
sunucusu çalışıyor ama bunu görmen/uğraşman gerekmiyor.

GPU kullanmak istiyorsan, `requirements.txt`'i kurmadan ÖNCE PyTorch'u
CUDA'lı sürümüyle elle kur (aksi halde `ultralytics`'in otomatik kuracağı
CPU'lu sürüm GPU'nu kullanmaz):

```
pip install torch torchvision --index-url https://download.pytorch.org/whl/cu121
```

Fusion aracının plaka OCR'ı için `fast-plate-ocr` paketi bir ONNX
backend'i gerektiriyor — Windows'ta NVIDIA GPU'n varsa
`pip install fast-plate-ocr[onnx-gpu]`, yoksa `pip install fast-plate-ocr[onnx]`
(bu zaten `requirements.txt`'te tanımlı, ekstra bir şey yapmana gerek yok).

### Komut satırı script'lerini (`kod/`) çalıştırmak için

```
cd otopark            (proje kökü)
pip install -r requirements.txt
python kod/06_fusion.py "yol/gorsel.jpg"
```

Bu script'ler Toolset'in GUI'sinden BAĞIMSIZ, tek başına çalışan
versiyonlar — OtoGöz'ün çekirdek mantığının nasıl adım adım kurulduğunu
görmek/anlamak için tutuluyorlar (aşağıdaki dosya rehberine bakın).

---

## 2) Arayüzü Kullanma (kod bilmeden)

`python app.py` çalıştırınca açılan pencere bir **Hub (ana menü)** —
her biri ayrı bir kart olan araçlardan birine tıklayarak açarsın. Her
aracın sol üstünde "← Toolset" linkiyle hub'a geri dönebilirsin.

Tüm dosya/klasör seçimleri **gerçek Windows pencereleriyle** yapılıyor
("DOSYA SEÇ" / "KLASÖR SEÇ" butonları) — hiçbir yere elle yol yazmana
gerek yok.

**Data Etiketleme** — bir görsel klasörü seçip, fare ile araçların
etrafına kutu çizip hangi sınıfa (örn. `fiat_egea`) ait olduğunu
işaretlediğin yer. Ctrl+tekerlek ile yakınlaştırma, orta tuşla kaydırma,
rakam tuşlarıyla sınıf seçme, sağ tıkla kutu silme var. Her kutu otomatik
kaydedilir, elle "Kaydet"e basmana gerek yok.

**Dataset Splitter** — etiketlediğin görselleri otomatik olarak
eğitim/doğrulama/test (train/val/test) gruplarına rastgele böler, bir de
verinin ne kadar dengeli/kaliteli olduğunu özetleyen bir rapor (`analiz.txt`)
üretir.

**Data Augment** — var olan etiketli görsellere parlaklık, kontrast,
keskinlik, blur, gölge, gürültü, sıkıştırma gibi efektler uygulayıp YENİ
(etiketleri korunmuş) görseller üretir — az veriyle daha dayanıklı bir
model eğitmek için. SADECE eğitim (train) grubuna uygulanmalı. Sağdaki
önizleme, gerçek bir örnek görsel üzerinde ayarların nasıl göründüğünü
(orijinal + filtreli, yan yana) ayarları değiştirdikçe OTOMATİK (kısa
bir gecikmeyle) günceller; "Tümünü Sıfırla" butonu yanlışlıkla girilen
aşırı bir değeri (örn. blur=50) tek tıkla başlangıç ayarlarına
döndürür.

**Model Eğitimi** — seçtiğin veriyle bir YOLO modelini eğitir; temel
ayarların yanında "Gelişmiş Ayarlar" altında ileri düzey parametreler
de var (istersen varsayılanlarıyla bırakabilirsin). Yarıda kesilen bir
eğitime kaldığı yerden devam etmek de mümkün.

**Model Test** — eğittiğin bir modeli bir görsel, video, ya da CANLI
webcam üzerinde deneyip sonucu görmeni sağlar. Ayrıca bir "Metrikler
(mAP)" sekmesi var: etiketli bir val seti (data.yaml) seçip modelin
gerçek performansını (mAP50, mAP50-95, precision, recall) sayısal
olarak ölçebilirsin — tek bir görselde bu ölçülemez, gerçek etiketle
karşılaştırma gerektirir.

**Ön-Etiketleme** — bir klasördeki TÜM görsellerin aynı sınıfa ait
olduğunu biliyorsan (örn. hepsi aynı arabanın farklı fotoğrafları), hazır
bir modelle araçları otomatik bulup etiketler — elle kutu çizmek yerine
sadece kontrol etmen yeterli olur.

**Video'dan Kare Çıkar** — bir video dosyasından seyrek aralıklarla
fotoğraf (kare) çıkarıp ham veri üretir.

**Veri Birleştir** — sınıf sınıf ayrı klasörlerde topladığın etiketli
verileri, eğitime hazır tek bir yapıya (`images/`+`labels/`) birleştirir.

**Fusion** — OtoGöz'e özel araç: aynı görselde hem plaka hem marka/model
tespiti yapıp ikisini birleştiren, "Tekli Görsel" ve "Sürekli İzleme
(Video)" olmak üzere iki modu var. Sürekli İzleme modu, bir video
boyunca her aracı bir kez tespit edip veritabanına (`db/otogoz.db`)
otomatik kaydediyor — bu, OtoGöz'ün "gerçek kamera" senaryosunun ilk
çalışan hali.

---

## 3) Dosya Rehberi (mühendis için)

Aşağıdaki tablo, her dosyanın/klasörün NE İŞE YARADIĞINI özetliyor —
kod satır satır anlatılmıyor, sadece "bu dosya ne amaçla var, ne zaman
dokunulur" sorusuna cevap veriyor.

### Proje kökü

| Dosya/Klasör | Ne işe yarar |
|---|---|
| `README.md` | Bu dosya. |
| `PROJE_BRIEF_OTOPARK.md` | OtoGöz'ün tasarım dokümanı — senaryo, mimari (8 bileşen), fusion formülü, veri toplama stratejisi. Projenin "neden böyle" sorularının cevabı burada. |
| `ILERLEME_GUNLUGU.md` | Kronolojik, teknik seviyeli geliştirme günlüğü — hangi hata ne zaman bulundu, nasıl çözüldü. |
| `STAJ_GUNLUK_OZET.md` | Staj raporu için gün-gün kısa özet (teknik detay için yukarıdakine bakar). |
| `requirements.txt` | `kod/` klasöründeki bağımsız script'lerin ihtiyaç duyduğu Python paketleri. |
| `bilgi_notlari/` | Öğrenme amaçlı referans metinleri — data.yaml formatı, YOLO/transfer learning, train/val/test mantığı, augment, terimler sözlüğü, ve `09_teknik_referans.txt` (en kapsamlısı: her aracın "kalıcı mı/nereye yazıyor/class'a dokunuyor mu" gibi sorularının tek tek cevabı). |
| `models/` | Hazır/indirilmiş modeller (örn. `plaka_tespit.pt`). |
| `veri/` | OtoGöz'ün marka/model eğitim verisi: `kaynak_gorseller/` (sınıf-başına-klasör ham kaynak — Veri Birleştir'in girdisi, eskiden proje kökünde `ARABALAR/` idi, 2026-08-04'te buraya taşındı), `images/`+`labels/` (Veri Birleştir'in ürettiği, class-prefix'li birleştirilmiş veri), `data.yaml` (sınıf listesi), `split/` (Splitter çıktısı — şu anki `runs/egitim3`, `runs/egitim4` bu veriyle eğitildi), `augments/augment4/` (Splitter çıktısındaki augment görsellerinin izlenebilir kaynağı). |
| `runs/` | `ultralytics`'in ürettiği eğitim çalışmaları (`egitimN/weights/best.pt` vb.) — her klasör bir eğitim denemesi. |
| `kayitlar/` | Fusion'ın ürettiği tekil çıktı: `fusion_sonucu.json` (son çalıştırmanın özeti, her seferinde üzerine yazılır). |
| `db/otogoz.db` | SQLite veritabanı — `tespitler` tablosu, her araç tespitini BİRİKİMLİ (silinmeden) tutar. DB Browser for SQLite gibi bir araçla açılıp incelenebilir. |
| `kod/` | Bağımsız (Toolset'ten ayrı) komut satırı script'leri — aşağıda ayrı tabloda. |
| `etiketleme_arayuzu/` | Toolset uygulamasının kendisi — aşağıda ayrı tabloda. |
| `test edilecekler/` | Kullanıcının kendi test amaçlı fotoğraf/video koleksiyonu (proje kodunun bir parçası değil). |

### `kod/` — bağımsız script'ler (Toolset'e göre daha basit/tek işlevli)

| Dosya | Ne işe yarar |
|---|---|
| `01_plaka_tespit_test.py` | Hazır bir plaka tespit modeliyle tek bir fotoğrafta plaka bulur, kırpıp kaydeder. OtoGöz'ün bileşen 1'inin ilk/en basit hali. |
| `02_ocr_test.py` | 01'in ürettiği kırpık plaka görselini OCR'dan (EasyOCR) geçirip Türk plaka formatına göre temizler/doğrular. Bileşen 2'nin ilk hali. |
| `03_gorsel_indir.py` | Bir URL listesinden sınıf başına toplu görsel indirip sıralı isimlendirir (veri toplama yardımcı script'i). |
| `04_veri_birlestir.py` | Sınıf-başına-klasör yapısındaki etiketli verileri, eğitime hazır tek `images/`+`labels/` yapısına birleştirir (Toolset'teki "Veri Birleştir" aracının CLI hali/öncülü). |
| `05_video_kare_cikar.py` | Bir videodan seyrek aralıklarla kare çıkarır (Toolset'teki "Video'dan Kare Çıkar" aracının CLI hali/öncülü). |
| `06_fusion.py` | **OtoGöz'ün çekirdeği.** Marka/model tespiti + plaka tespiti + OCR + eşleştirme + güven katmanlama zincirini tek bir görsel için uçtan uca çalıştırır. `etiketleme_arayuzu/app.py`'deki Fusion özelliğiyle aynı mantığı taşır ama bağımsız/GUI'siz çalışır — kod okuyarak mantığı anlamak isteyen biri için en net referans nokta budur. |
| `07_veritabani.py` | SQLite şemasını (`tespitler` tablosu) kurar ve `fusion_sonucu.json`'daki sonucu veritabanına yazan yardımcı fonksiyonları içerir. `app.py`'de aynı mantık tekrar edilmiş durumda (numaralı dosya adları Python'da doğrudan import edilemediği için). |

Not: `01`-`05` içindeki dosya adları rakamla başlıyor çünkü PROJE_BRIEF'teki
adım sırasını takip ediyorlar — bu yüzden birbirlerini doğrudan
`import` edemiyorlar (Python kısıtı), gerekli fonksiyonlar Toolset
tarafında ayrıca (küçük ölçüde tekrarlanarak) tanımlanmış durumda.

### `etiketleme_arayuzu/` — Toolset uygulaması

| Dosya/Klasör | Ne işe yarar |
|---|---|
| `app.py` | **Tüm backend mantığı burada** — Flask route'ları, dosya okuma/yazma, model çalıştırma, veritabanı işlemleri. Dosya büyük olduğu için içinde bölüm başlıkları (`# ===...===`) var; her araç (Etiketleme, Splitter, Augment, Eğitim, Test, Ön-Etiketleme, Kare Çıkar, Veri Birleştir, Fusion) kendi bölümünde. |
| `requirements.txt` | Bu uygulamanın ihtiyaç duyduğu Python paketleri (Flask, pywebview, ultralytics, opencv, fast-plate-ocr, pillow-heif vb.). |
| `bytetrack_ozel.yaml` | Fusion'ın "Sürekli İzleme" modunda kullanılan, ultralytics'in varsayılan ByteTrack ayarlarından TÜRETİLMİŞ özel bir tracker yapılandırması — bir aracın kısa süreli kapanma/düşük confidence yüzünden takip kimliğini kaybetmemesi için bekleme süresi uzatıldı. |
| `yolo11n.pt` | Hazır (COCO üzerinde eğitilmiş) genel amaçlı YOLO modeli — Ön-Etiketleme'de ve Fusion'ın "tanımlanmadı" fallback taramasında kullanılıyor. İlk çalıştırmada ultralytics tarafından otomatik indirilir, burada önbelleklenmiş halde duruyor. (`yolo26n.pt` da burada indirilmiş duruyordu ama kodun hiçbir yerinde kullanılmadığı için 2026-08-04 temizliğinde silindi.) |
| `templates/*.html` | Her aracın arayüz iskeleti (bir HTML dosyası = bir sayfa/araç). `index.html` = Hub (ana menü). |
| `static/*.js` | Her HTML sayfasının etkileşim mantığı (buton tıklamaları, sunucuyla haberleşme) — dosya adı, ilgili `.html` ile eşleşiyor (örn. `augment.html` ↔ `augment.js`). |
| `static/style.css` | Tüm sayfaların ortak görsel stili. |
| `static/fusion_ciktilari/` | Fusion'ın ürettiği kutulu sonuç görselleri (hem Tekli Görsel hem Sürekli İzleme modundan), zaman damgalı dosya adlarıyla birikir. |
| `static/augment_onizleme/` | Data Augment'in canlı önizlemesinin ürettiği örnek görseller (`orijinal.jpg` + `filtreli.jpg`) — her güncellemede ÜZERİNE yazılır, birikmez. |
| `static/test_ciktilari/` | Model Test'in ürettiği sonuç görselleri/videoları. |
| `__pycache__/` | Python'un derlenmiş bytecode önbelleği — otomatik oluşur, elle dokunulmaz, silinse de sorun olmaz. |

---

## 4) Bilinen kısıtlamalar / güncel durum

Toolset'in 9 aracı da tamamlanmış ve test edilmiş durumda. OtoGöz
tarafında: tespit + OCR + fusion + SQLite kayıt + video-kaynaklı sürekli
izleme çalışıyor; webcam'in sürekli izlemeye bağlanması, arama/sorgu
script'i, giriş/çıkış yön takibi ve kapsamlı bir demo hazırlığı henüz
bekliyor. Güncel/detaylı durum için `bilgi_notlari/09_teknik_referans.txt`
dosyasının son bölümüne bakılabilir.
