# Staj Günlük Özet — OtoGöz (AutoEye) Projesi

Bu dosya, staj raporuna işlenmek üzere GÜN BAZINDA tuttuğum kısa özet.
(Teknik detayların tamamı `ILERLEME_GUNLUGU.md`'de — orası kod/hata
seviyesinde, bu dosya rapor için "gün gün ne yapıldı" özeti.)

---

## 28 Temmuz 2026 (Salı)

- Proje klasör yapısı kuruldu (`models/`, `veri/`, `kayitlar/`, `db/`),
  gerekli kütüphaneler belirlendi (`ultralytics`, `opencv-python`,
  `easyocr`, `pyyaml`, `flask`, `pywebview`).
- Plaka tespiti tekli görüntüde test edildi (hazır bir YOLO modeliyle,
  ~%90 güvenle çalıştı).
- OCR entegrasyonu (EasyOCR) tekli görüntüde denendi; birkaç ön-işleme
  iyileştirmesi (büyütme, kontrast, şerit kırpma, blokları birleştirme)
  sonrası uçtan uca çalışır hale getirildi. Türk plaka formatı için
  temizleme/doğrulama mantığı yazıldı.
- Marka/model tanıma için mimari karar: önce "classify" planlanmıştı,
  sonra tek karede birden fazla/farklı konumdaki araç senaryosunu
  karşılamak için **YOLO detect**'e geçildi (aynı zamanda staj hocanın
  istediği evrensel araç setiyle de örtüşüyor).
- Renk ayrı bir sinyal olarak (HSV ile, eğitimsiz) ele alınmasına karar
  verildi — marka/model modeline renk class'ı olarak eklenmedi.
- Sınıflar netleşti: `renault_clio3`, `renault_clio4`, `fiat_egea`.
- Kendi **Data Etiketleme Arayüzü** (Flask + native pencere, pywebview)
  sıfırdan geliştirildi: canvas üzerinde fare ile kutu çizme, native
  klasör/dosya seçme, zoom/pan, klavye kısayolları, sınıf listesi,
  görsel listesi (etiketli/etiketsiz takibi).
- Birkaç gerçek kullanıcı hatası bulunup düzeltildi: klasör
  değiştirince aktif sınıfın sessizce eskide kalması, `data.yaml`'ın
  elle yazılan sınıfları görmezden gelmesi, yeni sınıf yazınca eski
  etiketlerin anlamının bozulması. Sonuncusu için kalıcı güvenlik
  kuralı kondu: var olan sınıflar asla silinmez/değişmez, yeni sınıf
  ancak kullanıcı onayıyla eklenir.
- Sınıf klasörlerinden eğitime hazır `images/`+`labels/` yapısına
  geçiren birleştirme script'i (`04_veri_birlestir.py`) yazıldı, harici
  klasör yollarını da destekleyecek şekilde güncellendi.
- Ana menü (Hub) arayüzü kuruldu — tüm araçlara (nevfel.txt'nin
  istediği evrensel araç seti) tek yerden erişim.
- Proje adı ve senaryo netleşti: **OtoGöz / AutoEye** — sabit güvenlik
  kamerası, giriş/çıkış loglama, aranabilirlik.

---

## 29 Temmuz 2026 (Çarşamba)

- **Model Test arayüzü** tamamlandı: görsel modu + video modu.
  - Video modunda "İndir" butonu çalışmıyordu (pywebview native
    pencere tarayıcı-tarzı indirmeyi desteklemiyor) — gerçek bir
    "Farklı Kaydet..." (native Save Dialog) butonuna çevrilerek
    düzeltildi, aynı düzeltme görsel modu sonucuna da eklendi.
- **Ön-Etiketleme arayüzü** (yeni araç, hub'a 6. kart olarak eklendi):
  bir klasördeki tüm görsellerin aynı class'a ait olduğu bilindiğinde,
  hazır bir modelle (varsayılan yolo11n.pt) aracı bulup otomatik etiket
  yazdırıyor — elle kutu çizme ihtiyacını ortadan kaldırıp sadece
  kontrol/düzeltme bırakıyor.
- **Video'dan Kare Çıkar arayüzü** (yeni araç, hub'a 7. kart): bir
  video dosyasından (vlog/dashcam/kendi kayıt) seyrek aralıklarla
  (varsayılan saniyede 1 kare) görsel çıkarıp ham veri üretiyor; aynı
  mantıkla bağımsız bir CLI script'i (`kod/05_video_kare_cikar.py`) de
  yazıldı.
- Etiketleme arayüzüne **görsel silme** (uygunsuz/ara sahne
  fotoğraflarını eleme) ve **bayrak/işaretleme** ("bu görseli sonra
  tekrar kontrol et") özellikleri eklendi; klavye kısayolları kullanıcı
  tercihine göre birkaç kez ayarlandı (son hali: bayrak = Numpad1 / `.`
  tuşu, silme = Shift+Delete).
- Gerçek bir hata bulundu ve düzeltildi: ok tuşlarıyla hızlı gezinirken
  bazı etiketli görsellerin etiketinin kayboluyor olması — sebebi,
  görsel/etiket yüklemesinin arka planda tam bitmeden bir sonraki
  görsele geçilebilmesiydi (yarış durumu/race condition). Yükleme artık
  tam olarak beklenip bir kilit mekanizmasıyla üst üste geçişler
  engellendi.
- Ön-Etiketleme'de "Hedef class" alanı serbest metinden, var olan
  class'ları otomatik listeleyen bir açılır menüye çevrildi (yeni class
  eklemek istenirse ayrı bir onaylı alan açılıyor).
- Veri toplama stratejisi üzerine planlama/danışmanlık: gerçekçi
  senaryoda class başına görsel sayısı, video kaynaklı verinin katalog
  fotoğrafına göre önceliği, aynı fiziksel araçtan çok kare almanın
  riski (o arabaya özgü detayları ezberleme + train/val sızıntısı
  riski), uzak/küçük araç görüntülerinin etkisi, çok benzeyen
  model/jenerasyonların (örn. Clio4/Clio5) ayrı class mı yoksa
  birleştirilmiş mi tutulması gerektiği, ve kapalı-küme sınıflandırma
  sınırlamaları (bilinmeyen bir model geldiğinde sistemin zorla yanlış
  bir isim vermek yerine "belirsiz" diyebilmesi gerekliliği) konuşuldu.
  Bunların confidence-katmanlama ve fusion mantığı (#6) ile birlikte
  çözüleceği netleşti.
- **Veri Birleştir arayüzü** eklendi (hub'a 8. kart): `04_veri_birlestir.py`
  script'inin GUI'den de kolay kullanılabilir hali — birden fazla sınıf
  klasörünü (clio3, clio4, egea, megane...) seçip tek bir images/+labels/
  yapısına, sadece etiketli olanları class adı ön ekiyle birleştiriyor.
- Etiketleme arayüzünde klavye kısayolları kullanıcı geri bildirimine göre
  netleşti: bayrak = Numpad1 / `.` tuşu; görsel silme = Shift+Delete / `L`
  tuşu (hepsi confirm() penceresiyle, Enter=onay/Esc=vazgeç, fare
  gerektirmeden).
- **Yanlış etiketlenmiş kutunun class'ını düzeltme** özelliği eklendi:
  "Bu görseldeki kutular" listesindeki her satıra bir class dropdown'ı
  kondu (silip yeniden çizmeden düzeltme), ayrıca bir kutu seçiliyken
  rakam tuşuna basmak da artık o kutunun class'ını değiştiriyor (önceden
  sadece yeni çizilecek kutular için "aktif class" değiştiriyordu).
- **İki bilgisayar arası dosya senkronizasyonu (OneDrive) kuruldu.**
  Uzun bir teşhis sürecinden sonra netleşti: proje klasörü göründüğü
  isme rağmen gerçekte OneDrive'ın senkronize ettiği kökün DIŞINDaydı
  (Desktop, OneDrive'a hiç bağlanmamıştı — sadece isimde "OneDrive"
  geçiyordu). Gerçek senkronize OneDrive kökü bulunup proje oraya
  kopyalandı, "Dosyaları İsteğe Bağlı Kullanma" (Files On-Demand)
  mantığı öğrenildi: aktif çalışılan bilgisayarda ilgili klasörler
  "Always keep on this device" yapılıyor (tam yerel hız, ağ gecikmesi
  yok), kullanılmayan makinede "Free up space" ile disk tasarrufu
  sağlanabiliyor. Ayrıca Claude/Cowork uygulamasının "bağlı klasör"
  ayarının OneDrive'dan bağımsız, her bilgisayarda AYRI kurulması
  gereken bir ayar olduğu netleşti (masaüstünde de klasör tekrar
  bağlandı).
- Masaüstü bilgisayarda (RTX 4060 Ti, 16GB VRAM) ortamı çalışır hale
  getirirken ayrı bir oturumda (Claude Code) ciddi bir ortam sorunu
  yaşandı ve çözüldü: Claude Code'un kendisi bir MSIX sandbox içinde
  çalıştığı için, o sandbox'tan yapılan TÜM `pip install` komutları
  gerçek sisteme değil sanal/izole bir klasöre gidiyordu — yani
  "kuruldu" görünen paketler (`torch`, `ultralytics` vs.) kullanıcının
  kendi CMD'sinden çalıştırılan Python'da HİÇ YOKTU, bu yüzden
  çift-tıklamayla veya CUDA ile ilgili tuhaf/tutarsız hatalar çıkıyordu.
  Çözüm: kurulumların kullanıcının KENDİ CMD penceresinden yapılması
  gerektiği netleşti (`pip install ...` + CUDA'lı `torch` kurulumu bu
  şekilde tekrarlandı). `app.py`'ye zararsız bir `os.chdir` satırı ve
  kolay başlatma için bir `baslat.bat` dosyası eklendi (ikisi de
  OneDrive üzerinden laptopa da yansıyor, laptoptaki çalışan durumu
  bozmuyor).
- **Gerçek/kapsamlı GPU eğitimi** (#22) masaüstünde başlatıldı: önce
  `yolo11m.pt` + imgsz=960 denendi ama epoch başına ~20 dk sürdüğü
  (kısmen ilk model indirmesiyle karışmış olabilir) ve ertesi sabah 6'ya
  kadar bitmesi gerektiği için `yolo11s.pt` + imgsz=960'a geçildi — ilk
  ölçümde epoch başına ~6 dk çıktı. Kalan süreye göre (o an saat 22:00,
  hedef 06:00) **epochs=70, patience=25, batch=32** ile eğitim gece
  boyu çalışmaya bırakıldı. GPU %100 kullanımda ama sıcaklık düşük/fan
  dönmüyor olması normal (modern kartların "zero RPM" boşta/hafif yük
  modu), zarar riski yok diye doğrulandı.

---

## 30 Temmuz 2026 (Perşembe)

- **Model Eğitimi arayüzüne "Gelişmiş Ayarlar" + Devam Et (resume) modu
  eklendi.** Hocanın verdiği notlar (loss ağırlıkları, focal loss, ek
  augmentation türleri, checkpoint'ten devam etme) tek tek açıklanıp
  önce anlatıldı, sonra kodlandı: `cls/box/dfl/fl_gamma` (kayıp
  ağırlıkları), tüm geometrik/renk augmentation'ları (hsv, degrees,
  translate, scale, mosaic, mixup, copy_paste, erasing), ardından
  ayrıca **cutmix**, **bgr**, **close_mosaic**, **multi_scale**,
  **freeze** eklendi (her biri projeye özel gerekçesiyle: cutmix kısmi
  kapanmaya dayanıklılık, multi_scale yakın/uzak araç ölçek farkına
  dayanıklılık, freeze az veriyle aşırı öğrenmeyi azaltma). "Var Olan
  Eğitime Devam Et" modu `resume=True` ile last.pt'den kaldığı yerden
  devam ettiriyor.
- **Dataset Splitter'ın analiz.txt'sine görsel boyutu (çözünürlük)
  analizi eklendi** — min/ort/max genişlik-yükseklik, tutarsızlık
  uyarısı, veriye göre önerilen `imgsz` değeri.
- **`bilgi_notlari/09_teknik_referans.txt` oluşturuldu** — data.yaml
  formatı, YOLO etiket formatı, tüm araçların (kalıcı mı/nereye
  kaydediliyor/class'a dokunuyor mu/hangi model/koşullu mu/tekrarlanabilir
  mi) tek tek dökümü, ve "herhangi bir yeni özellik için sorulması
  gereken sorular" bölümü.
- **Fusion aracı (plaka + marka/model birleştirme) kodlandı ve gerçek
  fotoğraflarla test edildi** — hem `kod/06_fusion.py` (komut satırı)
  hem Toolset'e 9. kart olarak (`/fusion`) eklendi. Akış: marka/model
  tespiti → plaka tespiti → OCR (EasyOCR) → eşleştirme (plaka kutusunun
  araç kutusuna örtüşme oranı) → "kesin/muhtemel/belirsiz" güven
  katmanlama. Test sürecinde bulunup düzeltilen gerçek hatalar:
  - Aynı araca birden fazla plaka adayı eşlenince SON geleni değil, en
    yüksek tespit güvenlisini seçme mantığı eklendi (yanlış-pozitif
    ikinci kutuların doğru sonucu ezmesini önlemek için).
  - "Tanımlanmadı" (modelin bilmediği bir araç) fallback'i eklendi:
    genel/hazır bir COCO modeliyle ek araç taraması yapılıp özel
    modelin bulamadığı araçlar da kutulanıyor. İlk versiyon HER
    çalıştırmada TÜM kadrajı tarayıp kalabalık sahnelerde onlarca
    alakasız arka plan aracını da işaretliyordu — bu, SADECE öksüz
    (eşlenemeyen) bir plaka varsa VE sadece o plakayı barındıran kutu
    için çalışacak şekilde düzeltildi.
  - Plaka OCR'ı iyileştirmeye çalışırken (beyaz zemine kırpma, sol şerit
    kırpma) bir DÖNGÜSEL kırpma hatası bulundu: iki ayrı kırpma adımı
    üst üste binip gerçek baştaki karakterleri kesiyordu — sol şerit
    kırpma tamamen kaldırıldı, beyaz-bölge kırpmaya güvenlik payı (%8)
    ve daha gevşek/CLOSE'lu bir maske eklendi. Sonuç kısmen iyileşti
    ama AÇIK BIR SORUN OLARAK KALDI: bazı fotoğraflarda plaka etrafındaki
    beyaz bayilik çerçevesi/yazısı da "beyaz bölge" sayılıp OCR'a
    karışıyor (bkz. ILERLEME_GUNLUGU.md).
  - HEIC/HEIF (iPhone fotoğrafı) desteği eklendi — `pillow-heif` ile
    otomatik JPEG'e çevirme, PIL'in "decompression bomb" güvenlik
    limiti (çok yüksek çözünürlüklü telefon fotoğrafları için) kapatıldı.
  - Çok yüksek çözünürlüklü (12000+ piksel) bir HEIC fotoğrafta plaka
    kutusunun EKRANDA GÖRÜNMEME hatası bulundu ve düzeltildi: sabit
    piksel kalınlığındaki çizimler artık görsel boyutuna göre otomatik
    ölçekleniyor.
- Gece boyu bırakılan GPU eğitiminin sonucu (`runs/egitim10s70960`,
  s.pt/imgsz=960) gerçek fotoğraflarla Fusion üzerinden dolaylı olarak
  test edildi — bilinen class'larda (fiat_egea) yüksek güvenle
  ("kesin", %90-96) doğru çalıştığı görüldü.
- Hocanın verdiği yeni bir araştırma konusu (kamera kalibrasyonu, mono
  vs stereo, ne için kullanıldığı) açıklandı, görsel/blog kaynaklar
  önerildi — bu proje için stereo'ya gerek olmadığı, mono'nun ileride
  (lens bükülmesi düzeltme, piksel→gerçek dünya konumu) işe yarayabileceği
  netleşti.
- Ev bilgisayarı (RTX 4060 Ti, 16GB VRAM) ile Google Colab'ın GPU
  seçenekleri (T4/L4/A100) karşılaştırıldı — ev kartı ücretsiz T4'ten
  hızlı, ücretli L4'e yakın/altında, A100'ün oldukça altında ama A100
  garantisiz/kota-yoğun.

---

## 31 Temmuz 2026 (Cuma)

- **Model Test'e gerçek zamanlı Webcam modu eklendi** — Görsel/Video
  modlarının yanına üçüncü sekme: canlı kamera görüntüsü üzerinde anlık
  tespit, MJPEG akış + arka plan yakalama thread'i ile. Windows'ta
  kamera izni engeliyle ortaya çıkan sessiz bir hata modu (kamera
  "açık" görünüyor ama hiç kare gelmiyor) teşhis edilip düzeltildi
  (DirectShow backend + zaman aşımlı açık hata mesajı + garantili kamera
  serbest bırakma). Kullanıcı test edip onayladı.
- **Fusion'daki OCR sorunu çözüldü:** plaka + bayilik çerçeve yazısını
  karıştırma sorununun kök sebebi araştırıldı — EasyOCR genel amaçlı bir
  OCR, plakaya özel eğitilmemiş. Profesyonel ANPR sistemlerinin yaptığı
  gibi, plaka metnini okumaya özel eğitilmiş bir model (`fast-plate-ocr`,
  `cct-s-v2-global-model`) entegre edildi — kendi plaka tespiti olmayan,
  sadece kırpılmış görüntüyü okuyan bir kütüphane seçildi ki mevcut
  `plaka_tespit.pt` modelimizle çakışmasın. Hem Toolset'teki Fusion
  sekmesi hem `kod/06_fusion.py` (komut satırı) güncellendi, ikisi
  tekrar senkron hale getirildi. Kullanıcı test edip "iyi çalışıyor"
  dedi.
- Dokümantasyon temizliği: `bilgi_notlari/09_teknik_referans.txt` ve
  `ILERLEME_GUNLUGU.md`'deki Fusion/OCR bölümleri güncel duruma göre
  yenilendi.
- **SQLite şeması kuruldu (#7):** `db/otogoz.db` içinde tek bir
  `tespitler` tablosu (plaka, marka/model, güven skorları, zaman, görsel
  yolları) tasarlandı ve kodlandı. Fusion artık her çalıştığında bu
  tabloya otomatik, birikimli (üzerine yazmayan) kayıt yazıyor -- daha
  önce sadece tek-seferlik bir JSON dosyasına yazılıyordu, geçmiş
  kayboluyordu. Tasarım kararları (tek tablo/normalize etmeme, zaman
  damgası olarak işlenme anının kullanılması, görselin dosya yolu olarak
  tutulup veritabanına gömülmemesi) kullanıcıyla birlikte netleştirildi.
- **#8 (statik görüntüden uçtan uca zincir) fiilen tamamlandı olarak
  işaretlendi:** Fusion aracı zaten detect->OCR->classify->fusion->DB
  kayıt zincirini tek tıklamada yapıyor; DB Browser'da gerçek
  fotoğraflarla üretilen doğru satırlar görülerek doğrulandı, ayrı bir
  kod yazmaya gerek kalmadı.
- **Sürekli izleme modu (#9) video-kaynaklı ilk sürüm olarak kodlandı:**
  Fusion sayfasına "Sürekli İzleme (Video)" modu eklendi -- bir video
  dosyasını kare kare işleyip, YOLO'nun takip özelliğiyle (ByteTrack)
  her fiziksel araca kalıcı bir kimlik atıyor, aynı aracı sadece İLK
  göründüğünde bir kez veritabanına kaydediyor (tekrar tekrar
  kaydetmiyor). Aynı fiziksel aracın yanlışlıkla iki farklı kimlik
  alma riski ("agnostic NMS" ile kutuları sınıf tahminini görmezden
  gelerek birleştirme) kullanıcıyla birlikte tartışılıp önlendi.
  Webcam'e bağlanması bilerek sonraya bırakıldı (şu an webcam testi
  imkanı yoktu), ama altyapı ileride kolayca genişletilebilecek şekilde
  tasarlandı. Henüz gerçek bir videoyla uçtan uca test edilmedi.
- Diğer bekleyenler: #9'un gerçek videoyla testi, arama/sorgu script'i
  (#10, artık DB hazır olduğu için mümkün), gece eğitiminin tam metrik
  kontrolü, kamera kalibrasyonu araştırmasının derinleştirilmesi.

---

## 1–7 Ağustos 2026 (Cumartesi–Cuma)

Bu aralıkta yoğun geliştirme oldu ama günlük bu kadar süre
güncellenmedi -- aşağıda o haftanın işleri toplu özetleniyor (teknik
detaylar için `ILERLEME_GUNLUGU.md`, sorun/çözüm örnekleri için
`sorunlar_ve_cozumler/SORUNLAR_VE_COZUMLER.md`):

- CompCars veri setinde üçüncü tur temizlik: çok az örnekli sınıflar
  için eşik 60'tan 40'a düşürüldü, lüks/nadir (Türk trafiğinde nadiren
  görülen) modeller SİLİNMEDEN ayrı bir klasöre taşındı (geri
  alınabilir olsun diye) -- Alfa Romeo 159 gibi yaygın modeller nadir
  kabul edilmedi, sadece gerçekten nadir olanlar (BMW i3/i8/Z4 gibi)
  taşındı.
- Model Eğitimi için donanıma göre (RTX 4060 Ti 16GB, 32GB RAM, Ryzen 5
  5600) somut bir ayar kontrol listesi çıkarıldı (`cache=disk`,
  `workers`, split oranı gibi kararların HERBİRİNİN gerekçesiyle).
- Toolset'in başka bir bilgisayara kolay kurulabilmesi için otomatik
  kurulum scripti (`KURULUM.bat`/`BASLAT.bat`) yazıldı -- hangi
  kütüphanelerin kurulacağını önceden gösteriyor, zaten kurulu
  olanları atlıyor, GPU/CPU PyTorch'u otomatik seçiyor.
- Veritabanı Sorgu arayüzündeki gerçek bir kullanıcı hatası düzeltildi:
  marka/model ve plaka aynı kutuda aranıyordu, kısa yazınca (ör.
  "egea") hiç sonuç gelmiyordu -- iki ayrı kutuya bölündü, birkaç harf
  yazınca canlı (debounce'lu) arama eklendi.
- Model Test'e "Klasör (Toplu)" modu eklendi: etiketsiz bir klasördeki
  TÜM görseller tek seferde işlenip, sonuçlar büyütülebilir (lightbox)
  bir galeri olarak gösteriliyor -- görsel görsel tek tek test etme
  zorunluluğu kalktı.
- **Staj raporu** hazırlandı (`staj_raporu.docx`) -- üniversitenin
  resmi Ek-4 şablonuna birebir uyularak, staj komisyonunun istediği
  gibi (genel geçer/placeholder değil, gerçek sorun->kök neden->çözüm
  örnekleriyle), Sadektech'teki gizlilik kapsamındaki içerik hariç
  tutulup gizli OLMAYAN gerçek işler (etiketleme, hatalı veri
  düzeltme, 4K->1080p döşeme stratejisi tartışmaları) ayrı bir bölümde
  anlatıldı, OtoGöz de uygulamalı örnek olarak kullanıldı.
- Gerçek veriden (dosya adlarından) doğru bir marka/model/yıl referans
  listesi çıkarıldı -- test ederken yanlış nesil/yıl bir araçla
  (ör. "2023 Polo") test edilince hiç tespit alınmamasının nedeni
  (eğitim verisi 2004-2016 aralığında, model o nesli hiç görmemiş)
  netleştirildi.
- Fusion Sürekli İzleme'de video testinde bulunan **gerçek bir hata**
  düzeltildi: DB'ye kaydedilen görsel, aracın kadrajdan ÇIKARKEN
  görülen (genelde en kırpık) son kareydi -- artık en yüksek güvenli
  sınıflandırmanın yapıldığı, kutunun kare kenarına değmediği kare
  kaydediliyor.
- **7 Ağustos:** Fusion'a canlı Webcam test modu eklendi (Model
  Test'teki webcam moduyla aynı desende); proje geneli bir denetimde
  PROJE_BRIEF'te planlanıp hiç kodlanmamış tek eksik bulundu: **renk
  tespiti** (bileşen 3'ün marka/model'den ayrı ikinci yarısı). Bu,
  yeni bir model EĞİTMEDEN, tespit kutusunun HSV renk uzayındaki
  medyan tonuna bakarak yapılan basit bir klasik görüntü işleme
  hesaplaması -- Fusion (tekli görsel + sürekli izleme), Model Test
  (tekli + klasör toplu) ve Veritabanı Sorgu arayüzüne (yeni "renk"
  arama kutusu + `tespitler` tablosuna yeni `renk` kolonu) uçtan uca
  eklendi. Diğer bilinen boşluk (giriş/çıkış yön takibi) baştan
  opsiyonel/genişletme olarak işaretlenmişti, kasıtlı olarak
  yapılmadı.

---

*Not: Bu dosyayı her günün sonunda güncelliyorum. Eğer bir gün
güncellemeyi unutursam, "günlüğü güncelle" diye hatırlatman yeterli.*
