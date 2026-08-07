# Düzenleme Günlüğü — Klasör Temizliği (2026-08-04)

> **DURUM: Yukarıdaki plan UYGULANDI.** Tüm "SİLİNENLER" ve "TAŞINAN"
> bölümlerindeki işlemler gerçekten yapıldı ve doğrulandı (aşağıdaki
> "5) SONUÇ" bölümüne bakın). `.venv` silinmesi, dosya sayısı çok
> olduğu için (1216 dosya) parça parça yapıldı ama sonuç aynı.

Bu dosya, kullanıcının isteği üzerine `otopark/` klasöründe yapılan TÜM
temizlik/düzenleme işlemlerinin kaydı. Özellikle SİLİNEN her şey burada,
neden silindiğiyle birlikte listeleniyor. Hiçbir şey "sanırım gerek yok"
diye rastgele silinmedi -- her karar, o dosyanın hangi araç/pipeline
tarafından üretildiği/kullanıldığı kod içinde veya dosya adlandırma
deseninde doğrulanarak verildi (aşağıda "Neden" satırlarında açıklanıyor).

Yöntem: Önce tüm klasör ağacı (`du -sh`, `find`) tarandı, hangi
klasörün hangi aracın (Splitter/Augment/Eğitim/Veri Birleştir) çıktısı
olduğu dosya adlandırma desenlerinden ve `runs/*/args.yaml` içindeki
`data:` yollarından çapraz kontrol edilerek doğrulandı.

---

## 1) SİLİNENLER

### Çalışma zamanı çıktı önbellekleri (kalıcı temizliği yok, kod zaten
### "klasör zamanla büyür" diye belgelemişti -- bkz. bilgi_notlari/09)

| Yol | Boyut | Neden |
|---|---|---|
| `etiketleme_arayuzu/static/fusion_ciktilari/*` | 273 MB (88 dosya) | Fusion + Sürekli İzleme'nin ürettiği kutulu sonuç görselleri. Tamamen yeniden üretilebilir (aracı tekrar çalıştırınca aynı klasöre yeniden yazılıyor). Bazı dosyalar 28-33 MB'a kadar çıkmış (İzleme modunun büyük kare kayıtları). |
| `etiketleme_arayuzu/static/test_ciktilari/*` | 29 MB (51 dosya) | Model Test'in ürettiği sonuç görselleri/videoları. Aynı şekilde yeniden üretilebilir. |
| `etiketleme_arayuzu/static/augment_onizleme/*` | 152 KB (2 dosya) | Augment canlı önizlemesinin `orijinal.jpg`/`filtreli.jpg` çıktısı -- zaten her önizlemede ÜZERİNE yazılıyor, kalıcı bir anlamı yok. |
| `etiketleme_arayuzu/runs/detect/val/*` | 3.2 MB | ultralytics'in `model.val()` çağrıldığında CWD'ye bıraktığı, projenin asıl `runs/` klasöründen (proje kökünde) BAĞIMSIZ, yanlışlıkla oraya düşmüş bir val-sonucu klasörü. Muhtemelen az önce eklenen "Metrikler (mAP)" özelliğinin test çıktısı -- işlevsel olarak hiçbir yerden okunmuyor. |
| `etiketleme_arayuzu/__pycache__/`, `kod/__pycache__/` | ~32 KB + birkaç KB | Python bytecode önbelleği, her çalıştırmada otomatik yeniden oluşur. |

### Boş/kullanılmayan klasörler

| Yol | Neden |
|---|---|
| `labels/` (kök, `labels/db`, `labels/kayitlar` dahil) | Tamamen BOŞ (0 dosya). README'nin dosya rehberinde zaten "legacy/stray" diye işaretlenmişti. |
| `veri/boş/fiat_egea`, `veri/boş/renault_clio_eski`, `veri/boş/renault_clio_yeni` | Tamamen BOŞ (0 dosya), klasör adı zaten "boş" (empty) -- kullanıcının kendi bıraktığı yer tutucular. |
| `veri/labels/fiat_egea`, `veri/labels/test_klasor` | Tamamen BOŞ (0 dosya). |

### Süperlenmiş/eskimiş deneme çıktıları

| Yol | Boyut | Neden |
|---|---|---|
| `veri/split/images/splittest3agu/` | ~1500+ dosya | Splitter'ın `images/` klasörünün İÇİNE yanlışlıkla iç içe düşmüş, ayrı bir "test" bölme denemesi. `veri/split/labels/` altında bu isimde bir karşılığı YOK (etiketsiz, kullanılamaz durumda) ve hiçbir `runs/*/args.yaml` bu yolu göstermiyor -- hiçbir eğitimde kullanılmamış, yalnız Splitter'ı test ederken oluşmuş bir kalıntı. |
| `veri/augments/augment/`, `veri/augments/augment2/` | 155 + 155 görsel | Augment aracının en eski deneme çıktıları -- dosya adlandırması eski tek-teknik `_aug` deseninde (yeni çoklu-teknik `_augb/_augk/_augp/_augg` deseninden ÖNCE). Şu anki `veri/split/`'te kullanılan augment dosyalarıyla eşleşmiyor. |
| `veri/augments/augment3/` | 465 görsel | Ara bir deneme -- 3 teknik suffix'i var ama `veri/split/images/train`'deki 432 augment dosyasıyla BİREBİR eşleşmiyor (augment4 eşleşiyor, aşağıya bakın). |
| `etiketleme_arayuzu/yolo26n.pt` | 5.3 MB | Kodun hiçbir yerinde (`grep -rn "yolo26"`) referans verilmiyor -- muhtemelen bir denemede indirilmiş, kullanılmayan bir COCO ağırlığı. (`yolo11n.pt` KALDI -- Fusion'ın "tanımlanmadı" fallback'i ve Ön-Etiketleme'nin varsayılanı olarak AKTİF kullanılıyor.) |
| `kayitlar/plaka_kirpik_0.jpg` | 8 KB | Projenin en ilk günlerinden (28 Temmuz) kalma, tek seferlik bir plaka-kırpma test görseli. Aktif pipeline'ın hiçbir parçası değil (aktif olan `kayitlar/fusion_sonucu.json` her Fusion çalıştırmasında zaten yeniden yazılıyor, o KALDI). |
| `veri/split.zip` | 7.3 MB | 28 Temmuz'a ait, çok daha küçük/erken bir split denemesinin elle alınmış zip yedeği. İçindeki `split/images/test` görselleri şu anki (çok daha büyük, 587 görsellik) `veri/split/`'ten farklı ve onun tarafından tamamen süperlendi. Hiçbir kod bu zip'e referans vermiyor. |

### Tek dosyalar

| Yol | Neden |
|---|---|
| `alakasiztest.py` | Adının kendisi zaten "alakasız test" (irrelevant test) -- 2 satırlık, sadece `torch.cuda.is_available()` yazdıran, tek seferlik bir GPU kontrol scripti. Toolset'in/OtoGöz'ün hiçbir parçası değil. |
| `.venv/` | 21 MB, içinde SADECE pip+setuptools var (ultralytics/opencv/flask YOK) -- yani proje bağımlılıkları hiç bu venv'e kurulmamış. `.vscode/settings.json` da zaten `"python-envs.defaultEnvManager": "system"` diyor, yani VS Code da bu venv'i DEĞİL sistem Python'ını kullanıyor. Kullanılmayan, yarım kalmış bir venv denemesi. |

**SİLİNMEDEN BIRAKILANLAR (önemli, kafa karışıklığı olmasın diye not
düşüyorum):** `veri/augments/augment4/` (şu an `veri/split`'teki
augment görsellerinin BİREBİR kaynağı -- 432 dosya birebir eşleşiyor,
korundu), `runs/egitim1/` ve `runs/egitim2/` (eski/kısa 3-epoch deneme
eğitimleri, `veri\augment\data.yaml` -- artık var olmayan bir yola
işaret ediyorlar, ama gerçek eğitilmiş ağırlık dosyaları oldukları için
SİLİNMEDİ, sadece aşağıda "gözden geçirmen gerekebilir" diye
işaretlendi), `runs/egitim10s70960/` (43 MB, yolo11s + 70 epoch, ciddi
bir eğitim ama `data:` yolu artık var olmayan farklı bir bilgisayara
ait bir klasörü gösteriyor -- SİLİNMEDİ, sadece not düşüldü).

---

## 2) TAŞINAN/YENİDEN DÜZENLENEN

| Eski yol | Yeni yol | Neden |
|---|---|---|
| `ARABALAR/` | `veri/kaynak_gorseller/` | Proje kökünde BÜYÜK HARFLERLE, `veri/`'nin dışında duran bu klasör aslında `veri/images`+`veri/labels`'in KAYNAĞI (Veri Birleştir aracının class-prefix'li birleştirdiği ham, sınıf-başına klasörler -- `clio3/`, `clio4/`, `egea/`, `megane/`). Hiçbir kod bu klasöre sabit bir yoldan referans vermiyor (sadece dosya seçiciyle kullanıcı tarafından seçiliyor), bu yüzden taşımak güvenli. Artık tüm veri zinciri (`kaynak_gorseller` → `images`/`labels` → `split` → `augments`) tek bir `veri/` klasörü altında toplu duruyor. |

---

## 3) DOKUNULMAYANLAR (özellikle belirtmek istedim)

- `models/plaka_tespit.pt`, `etiketleme_arayuzu/yolo11n.pt` — aktif kullanılan modeller.
- `db/otogoz.db`, `kayitlar/fusion_sonucu.json` — aktif proje verisi.
- `test edilecekler/telcam1/*` — gerçek test görselleri/videosu (CLI'nin varsayılan test görseli dahil), hiçbiri dokunulmadı.
- `veri/images`, `veri/labels`, `veri/split` (splittest3agu HARİÇ), `veri/augments/augment4` — aktif pipeline verisi.
- `PROJE_BRIEF_OTOPARK.md`, `ILERLEME_GUNLUGU.md`, `STAJ_GUNLUK_OZET.md`, `bilgi_notlari/`, `README.md`, `nevfel.txt` — proje dokümanları.
- `.vscode/` — IDE ayarları, dokunulmadı.

---

## 4) SONUÇ (boyut karşılaştırması)

| Klasör | Öncesi | Sonrası |
|---|---|---|
| `etiketleme_arayuzu/` | 316 MB | 5.7 MB |
| `veri/` (ARABALAR'ın taşınmasıyla) | 91 MB | 94 MB |
| proje kökü (`labels/`, `.venv/`, `alakasiztest.py` silindi) | — | temiz |

`etiketleme_arayuzu/` klasöründeki ~310 MB'lık düşüşün neredeyse tamamı
`fusion_ciktilari/` + `test_ciktilari/` + yanlışlıkla oraya düşmüş
`runs/` klasöründen geldi -- hiçbiri kaynak kod ya da kalıcı veri
değildi, hepsi çalışma zamanı çıktısıydı. Toplamda proje ~350 MB
küçüldü, hiçbir kaynak kod, model ağırlığı, eğitim verisi veya test
görseli kaybolmadı.

## 5) "Evrensel Toolset" kopyası oluşturuldu — `evrensel_toolset/`

Yukarıdaki temizlik bittikten SONRA, `etiketleme_arayuzu/`'nün TAMAMI
`evrensel_toolset/` adıyla kopyalandı (`cp -r`). Bu andan itibaren
**orijinal `etiketleme_arayuzu/`'ye bir daha dokunulmadı** — sadece
kopya üzerinde değişiklik yapıldı (doğrulama: `grep -c
"gelismis_ozellikler_acik" etiketleme_arayuzu/app.py` → 0, aynı grep
`evrensel_toolset/app.py`'de → 6 eşleşme).

Kopyada yapılan değişiklikler (SADECE kopyada, orijinalde YOK):

1. **`ayarlar.json` tabanlı bir açma/kapama ayarı eklendi**
   (`_ayarlari_oku`/`_ayarlari_kaydet`, `/api/ayarlar` GET/POST
   route'ları). Varsayılan: `{"gelismis_ozellikler_acik": false}`.
2. **Hub'da (`templates/index.html`) Fusion kartı** artık
   `{% if gelismis_acik %}` ile SARILI — kapalıyken hiç görünmüyor.
   Sayfanın altına "Gelişmiş (proje-özel) özellikleri göster" diye bir
   anahtar (checkbox) eklendi -- işaretlenince `/api/ayarlar`'a POST
   atıp sayfayı yeniliyor.
3. **`/fusion` sayfası** kapalıyken `fusion.html` yerine YENİ bir
   `templates/fusion_kapali.html` gösteriyor (kısa açıklama + "Fusion'ı
   Aç" butonu — o da aynı ayarı açıp `/fusion`'a yönlendiriyor).
4. **`/api/fusion/*` route'ları** için bir `@app.before_request` guard
   eklendi -- kapalıyken biri API'yi doğrudan çağırırsa 403 dönüyor
   (arayüzde zaten buton yok ama tutarlılık için).
5. **Veri izolasyonu (önemli düzeltme):** kopyalanan koddaki
   `FUSION_DB_YOLU` ve `kayitlar_klasoru` değişkenleri `parent.parent`
   kullanıyordu -- yani Fusion açılıp çalıştırılsaydı, kopyanın
   ÜRETTİĞİ veri (SQLite kayıtları, `fusion_sonucu.json`) yanlışlıkla
   otopark/'ın KENDİ `db/` ve `kayitlar/` klasörlerine yazılacaktı. Bu
   kopyada `parent` (tek seviye) olarak düzeltildi -- artık
   `evrensel_toolset/db/` ve `evrensel_toolset/kayitlar/` kendi
   içinde, orijinal projeden tamamen izole.
6. **`requirements.txt`**: `fast-plate-ocr[onnx]` ve `pillow-heif`
   (sadece Fusion'ın ihtiyaç duyduğu paketler) yorum satırına alındı --
   Fusion'ı hiç açmayacak biri bu paketleri kurmak zorunda değil.
7. **Hub başlığı/açıklaması** ("NEVO PROJE TOOLSET" / "dedect için, ve
   bişeyler...") daha açıklayıcı, proje-nötr bir metinle değiştirildi.
8. Kendi `README.md`'si eklendi (bu kopyanın ne olduğunu, orijinalden
   farkını ve Fusion'ı nasıl açacağını anlatıyor).

Kopyalanmadan ÖNCE `etiketleme_arayuzu/` zaten temizlenmiş olduğu için
(`fusion_ciktilari/`, `test_ciktilari/`, `augment_onizleme/` boştu,
`__pycache__` yoktu) kopya baştan temiz -- 5.7 MB.

Doğrulama: `evrensel_toolset/app.py` üzerinde `ast.parse` temiz,
`static/*.js` dosyaları `node --check` ile temiz.
