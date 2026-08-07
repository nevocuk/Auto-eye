# Proje: OtoGöz (AutoEye) — Otonom Araç Tanıma ve Log Sistemi

## Proje adı (2026-07-28)
**OtoGöz / AutoEye** — "oto" hem "otomatik" hem "otomobil" çağrışımı
yapıyor. Rapor/sunumda bu isim kullanılacak.

## Senaryo netleştirmesi (2026-07-28)
Ana çerçeve: **otopark/dükkan girişini izleyen sabit güvenlik kamerası**
(giriş/çıkış loglama + aranabilirlik). Mimari (detect tabanlı bileşen 3
sayesinde) zaten çoklu araçlı/daha geniş kamera görünümlerinde de
çalışıyor — bu ayrı bir sistem değil, aynı mimarinin doğal bir gücü,
raporda "sağlamlık" notu olarak eklenecek.

**Basmakalıp olmama gerekçesi (staj raporu kuralı iii için önemli):**
Salt plaka okuma (ANPR) tek başına çok bilinen/ticari bir problem —
projenin özgünlüğü FUSION mantığında (plaka OCR + marka/model/renk
tanımayı belirsizlik altında birleştirip güven kademeli çıkarım yapmak)
ve zaman bazlı aranabilir log sisteminde. Raporda bu ayrım net
vurgulanmalı.

**Giriş/çıkış (bileşen 8) için fiziksel çizgi gerekmiyor** — kod içinde
tanımlanan sanal bir referans çizgi/bölge + `model.track()` ile takip
yeterli. Şart: kamera sabit olmalı, araçlar nispeten tutarlı bir
güzergahtan geçmeli (kaotik çok yönlü trafik değil). Otopark girişi ya
da dükkan/ev önü fark etmez, ikisi de uygun.

## Bağlam
- ATÜ Bilgisayar Mühendisliği, yaz stajı kapsamında geliştirilen kişisel
  prototip (staj hocasının "YOLO'nun farklı task tiplerini öğrenin"
  şartını karşılamak için, Sadektech NDA'sı nedeniyle kendi verimle
  oluşturulan ayrı bir çalışma).
- **Tamamen hayali senaryo**: hayali bir şirket/site otoparkı, hayali
  kişiler, hayali plaka-kişi eşleştirmeleri. Gerçek üçüncü kişi verisi
  KULLANILMIYOR — bu proje tasarımının temel kısıtı, KVKK/gizlilik
  riskini sıfırlamak için bilinçli olarak böyle kurgulandı.

## Ne yapıyor (özet)
Otopark girişini izleyen bir kamera senaryosunda, geçen her aracın hem
plakasını (kısmen bulanık okunsa bile) hem marka/rengini tanıyıp, bu iki
belirsiz sinyali birleştirerek "büyük ihtimalle kimin arabası" çıkarımı
yapan, ve tüm bu tespitleri aranabilir bir veritabanına otonom şekilde
loglayan bir sistem. Amaç: saatlerce kamera kaydı izlemek yerine,
"14:00-15:00 arası gri Egea var mıydı" gibi sorgularla saniyeler içinde
cevap bulmak.

## Mimari — bileşenler

| # | Bileşen | Yöntem | Eğitim gerekiyor mu |
|---|---------|--------|---------------------|
| 1 | Araç/plaka bölgesi tespiti | YOLO detect (hazır plaka tespit modeli, Roboflow Universe) | Hayır |
| 2 | Plaka okuma | OCR (EasyOCR ya da PaddleOCR) | Hayır |
| 3 | Marka/model/renk tanıma | YOLO classify (`yolo11n-cls.pt` fine-tune) | **Evet — kendi verimle** |
| 4 | Fusion (plaka + marka/model birleştirme) | Ağırlıklı güven skoru | Hayır, kendi mantığım |
| 5 | Log/veritabanı | SQLite | Hayır |
| 6 | Sürekli izleme döngüsü + tekrar kayıt önleme | Kendi kodum | Hayır |
| 7 | Arama/sorgu arayüzü | SQL sorguları (basit CLI script) | Hayır |
| 8 | (Opsiyonel/genişletme) Giriş-çıkış yön takibi | `model.track()` (ByteTrack) | Hayır |

## Fusion mantığı (önemli, önceden tasarlandı)
```
plaka_skoru = ocr_guven * plaka_benzerlik(okunan, bilinen_plakalar)
toplam_skor = 0.6 * plaka_skoru + 0.4 * classify_guven

>0.75  -> "büyük ihtimalle X'in arabası"
>0.45  -> "olabilir: X (emin değilim)"
altı   -> "eşleşme yok"
```
Ağırlıklar (0.6/0.4) test sırasında kalibre edilecek, kesin değil.

## Log şeması (SQLite tablo)
| Alan | Tip | Örnek |
|------|-----|-------|
| zaman_damgasi | datetime | 2026-07-28 14:32:07 |
| yon | text (opsiyonel, genişletme aşamasında) | giriş / çıkış |
| plaka_okunan | text | "34ABC123" veya kısmi "34A_C1_3" |
| plaka_guven | float | 0.42 |
| marka_model_tahmin | text | "gri_egea" |
| marka_model_guven | float | 0.81 |
| birlesik_guven | float | 0.65 |
| eslesen_kisi | text | "Nevfel" / "Bilinmiyor" |
| thumbnail_yolu | text | /kayitlar/2026-07-28_14-32-07.jpg |

## Veri ihtiyacı
- Marka/model classify için: 5-8 hayali araç × 30-40 görsel = ~200-300 görsel
- Plaka tespiti ve OCR: veri gerekmiyor, hazır modeller

## Eğitim nerede/nasıl
Sadece marka/model classify eğitiliyor — Colab ücretsiz GPU, transfer
learning (`yolo11n-cls.pt` üzerinden), 50-100 epoch, ~20-40 dakika.

## ÖNEMLİ: Kapsam önceliklendirmesi (zaman riski nedeniyle)
Toplam iş yükü ~37-57 saat tahmin edildi, dört haftalık sürece göre
riskli. Bu yüzden ikiye bölündü:

**ÇEKİRDEK (mutlaka bitirilecek, ~22-35 sa):**
- Bileşen 1-6 (detect, OCR, classify, fusion, log, sürekli döngü)
- Yön ayrımı YOK, sadece "araç görüldü + ne zaman + hangi güvenle" logu
- Arama/sorgu (bileşen 7)

**GENİŞLETME (vakit kalırsa, ~15-22 sa ek):**
- Giriş/çıkış yön takibi (bileşen 8, tracking gerektiriyor)

## Adım adım geliştirme sırası (öneri)

1. **Ortam + klasör iskeleti** (~1 sa)
   - `pip install ultralytics opencv-python easyocr` (paddleocr alternatif)
   - Klasör yapısı: `models/`, `veri/`, `kayitlar/`, `db/`

2. **Plaka tespiti tekli görüntüde test** (~2 sa)
   - Roboflow'dan hazır plaka detect modelini indir, tek bir statik
     fotoğrafta dene, bbox çıktığını doğrula

3. **OCR entegrasyonu tekli görüntüde test** (~2-3 sa)
   - Kırpılmış plaka görüntüsünü EasyOCR'a ver, metin+güven çıktısını gör
   - Türk plaka formatına göre regex temizleme ekle

4. **Marka/model veri toplama** (~2-3 sa)
   - 5-8 hayali araç seç, her biri için 30-40 görsel topla
     (toplu indirme aracı veya kendi çekimin)

5. **Classify eğitimi** (~1 sa + Colab bekleme)
   - `yolo classify train data=... model=yolo11n-cls.pt epochs=60`

6. **Fusion mantığını kodla ve tek görüntüde test et** (~2-3 sa)
   - Plaka + marka/model çıktısını birleştirip skor üret

7. **SQLite şemasını kur** (~2 sa)
   - Tablo oluştur, örnek kayıt ekle/oku fonksiyonları yaz

8. **Statik görüntüden uçtan uca zinciri birleştir** (~2-3 sa)
   - detect -> OCR -> classify -> fusion -> DB kayıt, tek görüntüyle
     baştan sona çalıştığını doğrula

9. **Sürekli çalışan döngüye çevir (webcam/video)** (~3-4 sa)
   - Tuş yerine otomatik tetikleme, aynı aracın tekrar tekrar
     kaydedilmesini önleyen basit bir cooldown/dedup mantığı

10. **Arama/sorgu script'i yaz** (~2-3 sa)
    - Komut satırından "marka=egea" veya "tarih aralığı" gibi
      filtrelerle SQL sorgusu çalıştıran basit bir araç

11. **Test videosuyla uçtan uca demo hazırlığı** (~3-4 sa)
    - Birkaç araç görselini/maketini kameranın önünden geçirerek
      gerçekçi bir demo senaryosu kaydet

12. **(Genişletme, vakit kalırsa) Yön takibi ekle** (~15-22 sa)
    - `model.track()` ile ID takibi, giriş/çıkış ayrımı

## Tasarım kararları (unutulmamalı)
- Sistemin özgünlüğü fusion mantığında (iki belirsiz sinyali birleştirme) —
  raporda ana katkı olarak bunu vurgula
- Tüm veri hayali/sentetik, gerçek üçüncü kişi kullanılmıyor
- Zaman riski nedeniyle çekirdek/genişletme ayrımı bilinçli bir
  mühendislik kararı, raporda "neden önceliklendirdim" diye anlat

## Güncelleme (2026-07-28): Bileşen 3 ikiye ayrıldı — marka/model vs. renk
İlk tasarımda "marka/model/renk tanıma" tek bir YOLO classify modeline,
tek sınıf olarak veriliyordu (örn. sınıf adı "gri_egea"). Adım 4'te veri
toplamaya başlarken şu sorun ortaya çıktı: bu şekilde her renk-model
kombinasyonu ayrı bir sınıf/veri seti gerektirir (5 model x birkaç renk =
onlarca sınıf), bu da veri toplama yükünü katlanarak artırır — ayrıca
YOLO classify böyle eğitilirse "beyaz Egea" ile "siyah Egea" arasında hiç
ilişki kurmaz, iki bambaşka sınıf gibi öğrenir.

**Yeni yaklaşım:**
- **YOLO classify** sadece **marka/model** öğrenir (sınıflar: "egea",
  "clio", "corolla" gibi — renkten bağımsız). Eğitim verisinde renk
  çeşitliliği olması aslında modelin rengi değil şekli/hatları öğrenmesine
  yardımcı olur.
- **Renk tespiti eğitim gerektirmez** — tespit edilen araç kutusu
  içindeki baskın renk HSV uzayında hesaplanıp ("beyaz/siyah/gri/kırmızı/
  mavi" gibi) en yakın renk ismine eşlenir (basit, klasik görüntü işleme).
- Log'a yazılırken ikisi birleştirilir (`marka_model_tahmin` alanı yine
  "gri_egea" gibi görünür ama artık iki ayrı, bağımsız hesaplamanın
  birleşimi).

**Veri toplama etkisi:** Artık her model için TEK klasör yeterli (o
modelin farklı renklerdeki/açılardaki/ışıklardaki fotoğrafları karışık
şekilde aynı klasörde), renk başına ayrı klasör GEREKMİYOR.

## Güncelleme (2026-07-28, devam): Nesil/kasa ayrımı ve sınıf isimlendirme

Aynı model adı (örn. Clio) yıllar içinde kasa/görünüm olarak tamamen
değişebiliyor (eski kasa vs. yeni kasa görsel olarak neredeyse farklı
araba gibi). Bu yüzden sınıf ismi sadece marka+model değil, gerektiğinde
**nesil/kasa** bilgisini de içermeli:
- İsimlendirme kalıbı: `marka_model_nesil` (renk hariç — renk ayrı
  hesaplanıyor, yukarıya bakınız). Örnek: `renault_clio3`,
  `renault_clio4`, `fiat_egea`.
- Marka'yı ayrı bir hiyerarşi/aşama yapmaya gerek yok — düz (flat) tek
  aşamalı sınıflandırma yeterli, sadece etiket isminin içinde marka da
  geçsin (5-8 sınıflık ölçekte iki aşamalı marka->model hiyerarşisinin
  faydası yok).

## Güncelleme (2026-07-28, devam 2): Sistemin asıl amacı — genel model tanıma

Netleştirme: sistem, önceden bilinen belirli kişilerin arabalarını "tanımak"
için değil, **loglardaki her aracı** (tanıdık ya da tanımadık fark etmeksizin)
marka/model/renk bazında arama yapılabilir kılmak için var ("14:00-15:00
arası gri Egea var mıydı" sorusuna cevap verebilmek). `eslesen_kisi` alanı
sadece plaka biliniyorsa dolduruluyor, classify'ın asıl işi bu değil.

**Veri toplama etkisi (önemli):** Bu yüzden bir sınıf için aynı fiziksel
arabanın tekrar tekrar fotoğrafını çekmek YETERLİ DEĞİL — model o
tek arabanın kendine özgü detaylarını (çizik, aksesuar, plaka konumu)
ezberleyip başka bir aynı model/nesil arabayı tanıyamayabilir
("overfitting"). Her sınıf için mümkünse **birden fazla farklı fiziksel
araç örneği** (aynı model/nesil, farklı plaka/detay) toplanmalı ki model
gerçekten o modelin genel görünümünü öğrensin.

**Gerçek kamera görüntüsü riski (domain shift):** Eğitim fotoğrafları
galeri/stüdyo tarzı parlak çekimler olursa, gerçek otopark kamerası
açısı/mesafesi/ışığı farklı olduğunda doğruluk düşebilir. Mümkün
olduğunca eğitim verisi gerçek kullanım senaryosuna (kamera açısı,
mesafe, gün ışığı koşulları) yakın seçilmeli; Adım 8'de eğitim setinde
olmayan bir görüntüyle genelleme test edilecek.

**İlk test sınıfları (küçük ölçekte pipeline'ı doğrulamak için):**
`renault_clio3`, `renault_clio4`, `fiat_egea`

## Güncelleme (2026-07-28, devam 3): Bileşen 3 classify'dan DETECT'e çevrildi

**Sebep 1 — sahne kısıtı:** Classify tüm görsele TEK bir etiket verir,
görüntüdeki nesneleri birbirinden ayıramaz/konumlandıramaz. Otopark
senaryosu şu an tek şeritli giriş (karede tek araç) varsayıyor ama bu
kısıtlayıcı — yavaş geçen/duran/kadrajda birden fazla araç olan bir
sahnede (örn. genel bir sokak/otopark görünümü) classify işe yaramaz.
Detect ise her aracı ayrı ayrı bulur VE sınıflandırır, sahne karışıklığına
karşı sağlam.

**Sebep 2 — staj hocasının aracıyla uyum:** `nevfel.txt`'de tarif edilen
genel amaçlı etiketleme/split/augment/eğitim/test araç seti seg/detect/pose
için tasarlanmış, classify'ı kapsamıyor. Detect'e geçince, o araç seti
otopark'ın kendi verisi üzerinde de kullanılabilir hale geliyor —
"evrensel araç" şartını doğal yoldan kanıtlıyor, iş tekrarını önlüyor.
(Not: nevfel.txt'deki araç seti otopark projesinden AYRI bir görev/talep
gibi görünüyor — staj hocasıyla bunun otopark'a ek bir gereksinim mi,
tamamen paralel bir ödev mi olduğu netleştirilmeli.)

**Veri/format etkisi:**
- Artık sınıf başına klasör YOK — tüm görseller `veri/images/`, etiketler
  standart YOLO detect formatında `veri/labels/` (her görsel için aynı
  isimde `.txt`: `sinif_id x_merkez y_merkez genislik yukseklik`,
  normalize 0-1 arası), sınıf listesi `veri/data.yaml`'da.
- Bu yapı (`images/ + labels/ + data.yaml`) tam olarak nevfel.txt'deki
  dataset splitter aracının beklediği girdi formatıyla aynı — ileride
  o araç bittiğinde doğrudan kullanılabilir.
- Veri miktarı: classify'daki 30-40'tan fazla, çünkü model artık hem
  "nerede" hem "ne" sorusunu birlikte öğreniyor. Transfer learning
  (`yolo11n.pt` zaten COCO'da "araç" kavramını biliyor, sıfırdan
  öğrenmiyor) sayesinde abartılı değil: sınıf başına **80-150** kutu
  etiketli görsel hedefleniyor (test aşaması için alt sınır ~80'den
  başlanacak).
- Kutu etiketleme (bounding box çizme) staj hocasının aracı henüz hazır
  olmadığı için GEÇİCİ olarak harici bir araçla yapılacak (Roboflow
  Annotate veya LabelImg — ikisi de YOLO formatında dışa aktarabiliyor).

**İlk test sınıfları (sınıf ID'leri, `data.yaml`'da tanımlı):**
0: `renault_clio3`, 1: `renault_clio4`, 2: `fiat_egea`
