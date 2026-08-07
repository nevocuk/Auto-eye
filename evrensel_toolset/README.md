# Evrensel Toolset (bağımsız kopya)

Bu klasör, `otopark/etiketleme_arayuzu/`'nün bağımsız bir kopyası --
nevfel.txt'nin istediği evrensel 5 araçlık seti (Etiketleme, Dataset
Splitter, Data Augment, Model Eğitimi, Model Test) + genel amaçlı 3 ek
araç (Ön-Etiketleme, Video'dan Kare Çıkar, Veri Birleştir) içeriyor.
Hiçbir class/model/veri seti varsayımı yok -- herhangi bir YOLO
(detect) projesinde, herhangi bir kullanıcı tarafından kullanılabilir
(araç/plaka projesine özel bir şey değil).

**2026-08-07 düzenlemesi (genelleştirme):** Ön-Etiketleme aracı eskiden
COCO'nun sadece "car/truck/bus" class'larını arayacak şekilde SABİT
kodlanmıştı (yani sadece araç projeleri için işe yarıyordu). Artık
kullanıcı hangi kaynak COCO class'ını (ya da hiçbirini -- boş
bırakılırsa en güvenilir kutu direkt kullanılır) arayacağını arayüzden
kendisi giriyor -- "person", "dog,cat" ya da herhangi bir class adı
olabilir. Ayrıca arayüzdeki metinler ve Model Eğitimi'nin gelişmiş
ayar açıklamalarındaki örnekler araç-özel olmaktan çıkarılıp nesne-nötr
hale getirildi (bu aracı fine-tuning'e ya da bir araç veri setiyle
başlamak istemeyen biri de rahatça kullanabilsin diye).

## Orijinal projeden farkı

Orijinal `otopark/etiketleme_arayuzu/` doğrudan OtoGöz projesi için,
"Fusion" (plaka + marka/model birleştirme) aracı her zaman açık.

Bu kopyada Fusion **VARSAYILAN OLARAK KAPALI** — hub'da (ana sayfa)
görünmüyor, `/fusion` adresine gidilirse "kapalı" notu gösteriliyor.
Sebebi: Fusion tek bir projeye (plaka okuma + araç marka/model tanıma)
özel, nevfel.txt'nin istediği evrensel setin dışında — bu kopyayı başka
bir YOLO projesi için kullanacak biri için anlamsız/kafa karıştırıcı.

**Nasıl açılır:** Ana sayfanın en altındaki "Gelişmiş (proje-özel)
özellikleri göster" kutucuğunu işaretlemek yeterli — tek tıkla açılır,
tekrar kapatmak için aynı kutucuğu kaldırman yeterli. Ayar
`ayarlar.json` dosyasında saklanıyor (uygulamayı kapatıp açsan bile
kalıcı).

Fusion'ı açarsan bile, ürettiği veriler (`db/otogoz.db`,
`kayitlar/fusion_sonucu.json`, `static/fusion_ciktilari/`) bu kopyanın
KENDİ İÇİNDE tutulur — orijinal `otopark/` projesinin verilerine hiç
karışmaz (bilinçli bir tasarım kararı, koddaki ilgili yorumlara bakın).

## Kurulum

**Windows'ta en kolay yol:** `KURULUM.bat`'a çift tıkla (Python var mı
kontrol eder, sanal ortam/sistem Python'u sorar, gerekli tüm
kütüphaneleri -- GPU'na göre doğru PyTorch sürümü dahil -- kurar),
sonra `BASLAT.bat`'a çift tıklayarak aç.

Elle kurmak istersen:
```
cd evrensel_toolset
pip install -r requirements.txt
python app.py
```

Fusion'ı da kullanacaksan ayrıca:
```
pip install fast-plate-ocr[onnx] pillow-heif
```

**Uygulama açıldıktan SONRA da kurulum yapılabilir:** ana sayfadaki
"Gereklilikler" kartı, hangi kütüphanelerin eksik olduğunu gösterip tek
tuşla kurar (GPU'yu otomatik algılar, hazır COCO modelini -- yolo11n.pt
-- de indirir). Bunun tek şartı, arayüzün kendisinin açılabilmesi için
gereken flask/pywebview/numpy/Pillow'un zaten kurulu olması -- yani
KURULUM.bat (ya da elle `pip install -r requirements.txt`) en az bir
kere çalışmış olmalı. Ondan sonrasında ultralytics/opencv/torch gibi
daha ağır bağımlılıkları arayüzden yönetebilirsin.

## Dosya rehberi

Orijinal projenin `README.md`'sindeki "Dosya Rehberi" ve "Arayüzü
Kullanma" bölümleri (Fusion hariç, o burada opsiyonel) bu klasör için
de aynen geçerli — ayrıntılı açıklama için oraya bakabilirsin
(`otopark/README.md`).
