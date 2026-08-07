# Karşılaşılan Sorunlar ve Çözümleri

Bu klasör, OtoGöz + Toolset projesi boyunca karşılaşılan GERÇEK
sorunları (bug'lar, eksik/yanlış davranışlar, tasarım hataları) ve
bunların nasıl bulunup nasıl çözüldüğünü kayıt altına almak için
tutuluyor. Amaç: (1) staj sunumunda/raporunda "şu sorunla karşılaştım,
şöyle çözdüm" diye anlatabileceğin somut örnekler, (2) ileride benzer
bir sorun tekrar çıkarsa "bunu daha önce görmüş müydük" diye
bakabileceğin bir arşiv.

Her madde şu düzende: **Sorun** (ne çalışmıyordu/yanlış çalışıyordu) →
**Nasıl fark edildi** (kullanıcı testi mi, kod incelemesi mi) → **Kök
neden** (asıl teknik sebep) → **Çözüm** (ne yapıldı).

---

## 1) Fusion / Plaka Tanıma

### 1.1 — EasyOCR plaka okumada güvenilir değildi
**Sorun:** Genel amaçlı EasyOCR kütüphanesi, plaka kırpıklarında karakter
karıştırma ve eksik okuma yapıyordu (örn. "0" ile "O", "1" ile "I"
karışması, bazı plakalar hiç okunamıyordu).
**Nasıl fark edildi:** Gerçek fotoğraflarla test sırasında kullanıcı
gözlemi.
**Kök neden:** EasyOCR plaka OKUMAYA özel eğitilmemiş, genel amaçlı bir
OCR motoru.
**Çözüm:** Plakaya özel eğitilmiş `fast-plate-ocr` kütüphanesine
geçildi (kendi plaka tespit modelimizle birlikte kullanılabiliyor,
kendi tespiti yok — sadece okuma yapıyor). `requirements.txt`,
`app.py`, `kod/06_fusion.py` güncellendi.

### 1.2 — Sürekli İzleme'de aynı araç 2 farklı ID/2 kayıt alıyordu
**Sorun:** Bir araç, bariyer gibi bir engelin arkasından kısa süreliğine
kaybolup tekrar göründüğünde, tracker ona YENİ bir track ID veriyordu —
sonuç: veritabanına aynı araç için 2 ayrı kayıt düşüyordu.
**Nasıl fark edildi:** Kullanıcının gerçek test videosuyla denemesi ve
ekran görüntüleriyle "aynı arabaya 2 farklı frame'de, 2 kayıt yapmış"
diye bildirmesi.
**Kök neden:** ByteTrack'in varsayılan `track_buffer` (bir track'in
kayıp sayılıp silinmeden önce beklenen kare sayısı) çok kısaydı (~1
saniye) — kısa bir kapanma/düşük-confidence anını atlatamıyordu.
**Çözüm:** İki katmanlı düzeltme: (1) `bytetrack_ozel.yaml` ile
`track_buffer=90` (aksi 30), `track_low_thresh=0.05` (aksi 0.1) —
tracker'a daha fazla "sabır" verildi. (2) `agnostic_nms=True` eklendi
(aynı karede aynı nesneye 2 farklı class kutusu düşmesini önlüyor). (3)
Ek güvenlik ağı: aynı plaka metni son 15 saniye içinde zaten
kaydedilmişse tekrar kaydetmeyen bir kontrol (`_fusion_db_yakinda_ayni_plaka_var_mi`).

### 1.3 — Sürekli İzleme'de plaka sadece İLK karede, TEK SEFERLİK okunuyordu
**Sorun:** Bir araç kadraja girer girmez plaka OCR'ı bir kez deneniyor,
sonuç ne olursa olsun (boş bile olsa) kalıcı kabul ediliyordu — araç
kadrajda kalmaya devam etse, açısı/ışığı daha iyi bir kareye gelse bile
tekrar denenmiyordu.
**Nasıl fark edildi:** Kullanıcının kendi mantık yürütmesiyle önceden
sorduğu bir soru ("bir araba algılayınca algılar algılamaz mı plaka
okumaya çalışıyor? araç frame'den çıkana kadar daha iyi okuyacağı an
olabilir") — kod incelemesiyle doğrulandı.
**Kök neden:** Orijinal tasarım, her track ID için sadece "ilk görülen
karede" bir kere OCR deneyip sonucu kalıcı yazıyordu.
**Çözüm:** `_izleme_dongusu` baştan yazıldı — artık her track ID için
bir `bekleyenler` sözlüğü tutuluyor, araç kadrajda kaldığı SÜRE
BOYUNCA her karede (henüz geçerli-formatlı bir plaka okunmadıysa) OCR
tekrar deneniyor, en iyi (formatı geçerli > en yüksek OCR güveni)
sonuç saklanıyor. Araç kadrajdan kaybolunca ya da video bitince o ana
kadarki EN İYİ sonuç DB'ye yazılıyor (`_finalize_et`).

### 1.4 — "Hayalet" (var olmayan araç) tespitleri
**Sorun:** Bazı DB kayıtlarında gerçekte araç olmayan bir yerde
(bariyer/zemin deseni gibi) düşük güvenli tespitler oluşuyordu.
**Nasıl fark edildi:** Kullanıcının ekran görüntüsü + DB tablosunda
tekrar eden, aynı güven değerine sahip garip kayıtlar fark etmesi.
**Kök neden:** Bu bir KOD hatası değil, bir EĞİTİM VERİSİ sorunu —
marka/model modeli o bölgeyi düşük ama sıfır olmayan bir güvenle bir
araca benzetiyor.
**Çözüm:** Kod tarafında agresif bir filtre eklenmedi (bilinçli karar —
düşük güvenli ama GERÇEK tespitleri de kaybetmemek için). Bunun yerine
düşük güvenli kayıtlar artık log'da "[DÜŞÜK GÜVEN -- muhtemelen
yanlış/hayalet algılama olabilir]" notuyla işaretleniyor. Kullanıcıya
iki gerçek çözüm yolu tarif edildi: UI'daki confidence eşiğini
yükseltmek, ya da eğitim setine o bölgenin boş halini "hard negative"
örnek olarak eklemek.

---

## 2) Sürekli İzleme + Model Test — Mimari / eşzamanlılık sorunları
### (2026-08-03 Opus code review'unda bulundu)

### 2.1 — Model önbelleği, tracker ile "kirleniyordu" (KRİTİK)
**Sorun:** İzleme modu, marka/model modelini PAYLAŞILAN bir önbellekten
alıp üzerinde `model.track(persist=True)` çalıştırıyordu. Ultralytics
bu çağrıda tracker durumunu (ID'ler, kayıp-track tamponu) doğrudan o
Model NESNESİNE kalıcı olarak yazıyor. Sonuç: İzleme art arda iki kez
çalıştırılsa, önceki videodan kalan track ID'ler yeni videodaki
araçlarla yanlış eşleşebilirdi; İzleme'den sonra aynı model dosyasıyla
Tekli Görsel Fusion çalıştırılırsa o da fark etmeden tracker hattından
geçip farklı davranırdı.
**Nasıl fark edildi:** Kod incelemesi (henüz kullanıcı tarafından canlı
olarak yaşanmamıştı — önlem amaçlı bulundu/düzeltildi).
**Kök neden:** Paylaşılan model önbelleği deseni, tracker'ın
"stateful" (durum tutan) doğasıyla uyumsuzdu.
**Çözüm:** İzleme artık PAYLAŞILAN önbelleği hiç kullanmıyor — her
çalıştırmada taze, kendine özel bir `YOLO(...)` nesnesi yüklüyor.

### 2.2 — Paylaşılan durum sözlüklerine kilitsiz erişim
**Sorun:** `IZLEME_DURUMU`, `EGITIM_DURUMU`, `VIDEO_TEST_DURUMU` gibi
sözlükler, arka plan thread'i yazarken aynı anda ön uçtan polling ile
okunuyordu — nadir durumlarda tutarsız/yarım okuma riski.
**Kök neden:** Log listesi gibi alanlar `[-N:]` ile YENİDEN atanıyordu
(mutasyon değil), bu da eşzamanlı bir `jsonify()` sırasında teorik bir
yarış durumu yaratabiliyordu.
**Çözüm:** Hem yazma (`_izleme_log`, `_egitim_logla`) hem okuma
(durum route'ları) artık ilgili `threading.Lock()` altında yapılıyor.

### 2.3 — Model/OCR önbellek yükleyicileri thread-safe değildi
**Sorun:** "Önbellekte var mı? Yoksa yükle" deseni kilitsizdi — iki
istek (örn. Test ve Fusion arka arkaya) aynı anda "yok" görüp aynı
modeli iki kez yükleyebilir ya da biri `.clear()` çağırırken diğeri
okuyabilirdi.
**Çözüm:** Tüm model/OCR önbellek yükleyicileri tek bir paylaşılan
`MODEL_ONBELLEK_KILIDI` ile korunacak şekilde güncellendi.

### 2.4 — Silme route'unda path traversal riski
**Sorun:** `/api/gorsel/<path:dosya_adi>` DELETE route'u, gelen dosya
adını doğrudan `gorsel_klasoru / dosya_adi` ile birleştiriyordu —
`dosya_adi` içine `../../` gibi bir yol verilirse klasör dışındaki bir
dosya silinebilirdi (teorik risk, yerel/tek-kullanıcılı bir araç
olduğu için gerçek saldırı yüzeyi düşük).
**Çözüm:** Artık sadece dosya adı (`Path(dosya_adi).name`) alınıyor ve
sonucun gerçekten hedef klasör altında olduğu doğrulanıyor.

### 2.5 — CLI script'inde (`kod/06_fusion.py`) boş-kırpık çökmesi
**Sorun:** `app.py`'de kadraj kenarına taşan bir plaka kutusu için
"kırpık boşsa atla" kontrolü vardı ama bu kontrol CLI script'ine hiç
taşınmamıştı — aynı durumda CLI `ZeroDivisionError` ile çökerdi.
**Çözüm:** Aynı guard CLI script'ine de eklendi.

---

## 3) Data Augment Arayüzü

### 3.1 — "Tümünü Sıfırla" butonu yoktu
**Sorun:** Kullanıcı absürt bir augment değeri (örn. blur=50) girdikten
sonra tüm ayarları tek tek elle geri çevirmek zorundaydı.
**Çözüm:** Tüm teknik değerlerini/checkbox'ları/modu varsayılana
döndüren bir "Tümünü Sıfırla" butonu eklendi.

### 3.2 — Önizleme sadece SAYI gösteriyordu, GERÇEK görsel yoktu
**Sorun:** "Sıfırla" butonunun anlamlı olması için kullanıcının
uyguladığı filtrenin GERÇEKTEN nasıl göründüğünü görmesi gerekiyordu,
ama önizleme sadece "kaç görsel etkilenecek" sayısını gösteriyordu.
**Çözüm:** Gerçek bir örnek görsel üzerinde orijinal + filtreli halin
yan yana gösterildiği bir önizleme eklendi.

### 3.3 — Önizleme, değer değiştirince ANLIK güncellenmiyordu
**Sorun:** Önizleme sadece ayrı bir "ÖNİZLE" butonuna basılınca
yenileniyordu — kullanıcı bir kaydırıcıyı değiştirdiğinde ekran
güncellenmiyordu.
**Kök neden:** Önizleme yenileme mantığı sadece o butonun `click`
olayına bağlıydı.
**Çözüm:** Tüm teknik kontrollerine (`change`/`input`) debounce'lu
dinleyiciler eklendi; ayrıca yavaş/eski bir isteğin daha yeni bir
isteğin sonucunu ezmesini önlemek için bir istek-sıra-numarası (race
guard) eklendi.

### 3.4 — Dikey, verimsiz tek-sütun düzen
**Sorun:** Augment sayfası (ve benzerleri) aşağı doğru uzun bir
tek-sütun düzendeydi, ekranı verimsiz kullanıyordu.
**Çözüm:** Model Eğitimi'ndeki gibi iki-sütunlu (solda kontroller, sağda
sabit/sticky önizleme) bir düzene çevrildi.

### 3.5 — "Sadece images + data.yaml" girdisi çalışmıyordu (2026-08-05)
Bkz. bu sohbetteki ayrıntılı anlatım yukarıda — kısaca: labels klasörü
olmadan (ya da bir görselin etiketi olmadan) Augment o görseli filtre
boş olsa bile tamamen listeden atıyordu, nevfel.txt'nin istediği bir
girdi modunu fiilen çalışmaz hale getiriyordu. `_gorselleri_filtrele`
artık etiketsiz görselleri de (filtre boşken) dahil ediyor, çoğaltma
sırasında onlar için boş bir `.txt` yazıyor.

---

## 4) Dataset Splitter

### 4.1 — Bölme tekrarlanabilir değildi (seed yoktu)
**Sorun:** `random.shuffle` sabit bir seed kullanmıyordu — aynı klasörü
iki kez bölünce train/val/test'e FARKLI görseller düşebiliyordu. Bir
modeli aynı bölmeyle tekrar eğitip karşılaştırmak isteyen biri için bu
sorun.
**Çözüm:** Opsiyonel bir "Sabit seed" alanı eklendi — izole bir
`random.Random(seed)` örneği kullanılıyor (global `random` modülünün
durumunu bozmadan, çünkü Augment'in "dinamik" modu da ona bağımlı).
Kullanılan seed (ya da "verilmedi" notu) `analiz.txt`'ye de yazılıyor.

### 4.2 — `analiz.txt` formatı nevfel.txt şablonuyla birebir değildi (2026-08-05)
**Sorun:** Rapor başlıklarında emoji yoktu (📊📂🎯), ana başlıkta
"DETAYLI" kelimesi eksikti, "SINIF DAĞILIMI"/"Sınıf" yerine "CLASS
DAĞILIMI"/"Class" yazıyordu.
**Nasıl fark edildi:** nevfel.txt'nin her maddesini kod okuyarak tek
tek doğrulayan bir denetim turunda (bkz. madde 6).
**Çözüm:** `_analiz_raporu_olustur`'daki 3 başlık satırı şablonla
eşleşecek şekilde güncellendi. (Kolon genişlikleri BİREBİR
kopyalanmadı çünkü şablonun kendisi iç tutarlı değil — örnekteki
başlık satırı ve veri satırları farklı hizalarda; içerik/başlıklar
önceliklendirildi.)

---

## 5) Dokümantasyon — Kod ile Çelişen/Eskimiş Notlar

Bunlar "bug" değil ama gerçek sorunlar: kod değişti, doküman
güncellenmedi, birbirini yalanlayan iki kaynak ortaya çıktı.

- `09_teknik_referans.txt` hâlâ "Splitter tekrarlanamaz, seed yok"
  diyordu — seed eklendikten SONRA fark edilip güncellendi.
- `08_arayuz_araclari_rehberi.txt`, Model Test'in webcam modundan ve
  Fusion'ın Sürekli İzleme/SQLite kaydından hiç bahsetmiyordu (o
  özellikler eklendikten sonra dokümana yansıtılmamıştı).
- `README.md`, Augment'in kaldırılan "ÖNİZLE" butonundan hâlâ söz
  ediyordu (canlı önizlemeye geçildikten sonra güncellenmemişti).
- `kod/06_fusion.py`'nin varsayılan test görseli yolu (`veri/test_arac2.jpg`)
  artık var olmayan bir konumu gösteriyordu (gerçek konum
  `test edilecekler/telcam1/test_arac2.jpg`).
- **En çarpıcı örnek:** `README.md`, proje kökündeki `ARABALAR/`
  klasörünü "kullanılmıyor, tarihi kalıntı" diye işaretlemişti — 2026-08-04
  klasör temizliği sırasında dosya adlarını karşılaştırarak
  bunun YANLIŞ olduğu ortaya çıktı: `ARABALAR/` aslında
  `veri/images`'in GERÇEK kaynağıydı (Veri Birleştir aracının
  birleştirdiği ham, sınıf-başına klasörler). Silinmedi,
  `veri/kaynak_gorseller/` olarak taşınıp doküman düzeltildi. Ders:
  "silmeden önce doğrula" — bir dosyanın eski bir yorumda "kullanılmıyor"
  yazması, gerçekten kullanılmadığı anlamına gelmiyor.

---

## 6) Proje Organizasyonu

### 6.1 — Çalışma zamanı çıktıları sınırsız birikiyordu
**Sorun:** `fusion_ciktilari/`, `test_ciktilari/` klasörleri hiç
temizlenmiyordu, zamanla 300+ MB'a ulaşmıştı (bazı tekil dosyalar
28-33 MB'a kadar çıkmıştı — İzleme modunun büyük kare kayıtları).
**Kök neden:** Bu davranış zaten bilinçli bir tasarım kararıydı
("otomatik temizlik yok" diye dokümante edilmişti) ama kimse elle
temizlemiyordu.
**Çözüm:** 2026-08-04 klasör temizliğinde bu klasörlerin içeriği
boşaltıldı (kod zaten `mkdir(exist_ok=True)` ile yeniden oluşturuyor,
işlevsellik etkilenmedi).

### 6.2 — `evrensel_toolset/` kopyası, orijinal projenin verisine
    karışabilirdi (kopyalama sırasında yakalandı, hiç üretime çıkmadı)
**Sorun:** `etiketleme_arayuzu/`'yü `evrensel_toolset/`'e kopyalarken,
kopyalanan koddaki `FUSION_DB_YOLU` ve `kayitlar_klasoru` değişkenleri
`Path(__file__).parent.parent` kullanıyordu — bu, kopyanın BİR ÜST
klasörüne (yani otopark'ın kendisine) işaret ediyordu. Fusion o kopyada
açılıp çalıştırılsaydı, ürettiği veri yanlışlıkla orijinal projenin
CANLI veritabanına yazılırdı.
**Nasıl fark edildi:** Kopyalama sonrası yeni eklenen kod satırlarını
tek tek gözden geçirirken.
**Çözüm:** İki değişken de `parent` (tek seviye) olacak şekilde
düzeltildi — artık kopyanın ürettiği her şey kendi içinde kalıyor.

---

## Genel gözlem

Bu listedeki sorunların çoğu iki kaynaktan geldi: (1) **gerçek kullanıcı
testi** (özellikle İzleme modundaki 2 kritik bug, sadece kod okumakla
fark edilemeyecek, gerçek videoyla denemeden ortaya çıkmayacak
türdendi), (2) **sistemli kod denetimi** (bir subagent'a "her satırı
kanıtla doğrula" diye görev verildiğinde, gözle bakınca atlanan path
traversal, kilitsiz state, eskimiş dokümantasyon gibi şeyler ortaya
çıktı). İkisi de birbirini tamamlıyor — sadece kod okuyarak
bulunamayacak sorunlar var (davranışsal/performans), sadece kullanıcı
testiyle de bulunamayacak sorunlar var (güvenlik, nadir yarış
durumları, dokümantasyon tutarlılığı).
