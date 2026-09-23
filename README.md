# OtoGöz (AutoEye)

Sabit güvenlik kamerasından geçen araçları **plaka + marka/model + renk** üçlüsüyle tanıyıp SQLite veritabanına kaydeden bir prototip. ATÜ Bilgisayar Mühendisliği yaz stajı projesi.

Projenin asıl farkı salt plaka okuma (ANPR) değil, **Fusion** katmanı: plaka OCR'ı bulanık/eksik okuduğunda bile marka-model ve renk sinyalleriyle birleştirip güven kademeli bir çıkarım yapması.

> Tamamen hayali senaryo ve verilerle geliştirilmiştir, gerçek kişi/plaka verisi kullanılmamıştır.

---

## Ekran Görüntüleri

_Yakında eklenecek._

---

## Ne İçeriyor

| Bileşen | Açıklama |
|---|---|
| **Toolset** (`etiketleme_arayuzu/`) | YOLO projelerinde kullanılabilecek 9 araçlık masaüstü uygulama (Flask + pywebview) |
| **Fusion** | Plaka OCR + marka/model tanıma + renk tespitini birleştiren çekirdek modül |
| **CLI Script'ler** (`kod/`) | Her adımın bağımsız, tek dosyalık versiyonları |

### Toolset Araçları

- **Data Etiketleme** -- Görseller üzerinde YOLO formatında kutu çizme
- **Dataset Splitter** -- Train/val/test bölme + dağılım analizi
- **Data Augment** -- Parlaklık/kontrast/blur/gölge/gürültü/sıkıştırma ile veri çoğaltma
- **Model Eğitimi** -- YOLO eğitimi (GPU/CPU, devam ettirme destekli)
- **Model Test** -- Görsel, video, webcam ve metrik (mAP) modları
- **Ön-Etiketleme** -- Hazır modelle otomatik kutu üretimi
- **Video'dan Kare Çıkar** -- Video dosyasından ham veri üretme
- **Veri Birleştir** -- Farklı kaynaklardan gelen etiketli verileri tek yapıda toplama
- **Fusion** -- Plaka + marka/model + renk birleştirme (tekli görsel ve sürekli izleme)

---

## Kurulum

**Gereksinim:** Python 3.10+

### Windows

```
cd etiketleme_arayuzu
KURULUM.bat
BASLAT.bat
```

### Linux / macOS

```bash
cd etiketleme_arayuzu
chmod +x KURULUM.sh BASLAT.sh
./KURULUM.sh
./BASLAT.sh
```

Kurulum scripti Linux'ta pywebview için gereken sistem paketlerini (GTK3, WebKit2, ffmpeg) otomatik kurar.

### Elle kurulum

```bash
cd etiketleme_arayuzu
python3 -m venv .venv && source .venv/bin/activate

# GPU varsa (opsiyonel, eğitim/test hızı için):
pip install torch torchvision --index-url https://download.pytorch.org/whl/cu121

pip install -r requirements.txt
python app.py
```

> Uygulama açıldıktan sonra ana sayfadaki **Gereklilikler** kartından eksik paketleri tek tıkla kurabilirsin.

---

## Proje Yapısı

```
otopark/
├── etiketleme_arayuzu/     # Toolset uygulaması (backend + frontend)
│   ├── app.py               # Tüm backend mantığı
│   ├── templates/            # HTML sayfaları
│   ├── static/               # JS, CSS, çıktı görselleri
│   └── requirements.txt
├── evrensel_toolset/        # Toolset'in genel amaçlı (Fusion kapalı) kopyası
├── kod/                     # Bağımsız CLI script'ler
│   ├── 01_plaka_tespit_test.py
│   ├── 02_ocr_test.py
│   ├── 03_gorsel_indir.py
│   ├── 04_veri_birlestir.py
│   ├── 05_video_kare_cikar.py
│   ├── 06_fusion.py          # Fusion'ın GUI'siz hali
│   └── 07_veritabani.py
├── models/                  # Hazır modeller (plaka tespit vb.)
├── veri/                    # Eğitim verisi (data.yaml + split)
├── runs/                    # Eğitim çıktıları
├── db/                      # SQLite veritabanı
├── bilgi_notlari/           # Referans notlar ve terimler sözlüğü
├── PROJE_BRIEF_OTOPARK.md   # Tasarım dokümanı
├── ILERLEME_GUNLUGU.md      # Geliştirme günlüğü
└── STAJ_GUNLUK_OZET.md      # Staj raporu özeti
```

---

## Mimari

```
Kamera Görüntüsü
       │
       ├──► YOLO Detect (marka/model) ──► sınıf + güven
       │
       ├──► YOLO Detect (plaka bölgesi) ──► OCR ──► plaka metni + güven
       │
       └──► HSV Renk Analizi ──► baskın renk
              │
              └──► FUSION ──► birleştirilmiş sonuç ──► SQLite
```

Sürekli izleme modunda ByteTrack ile araç takibi yapılır; her araç kadraja girip çıkana kadar tek bir kayıt olarak işlenir.

---

## Teknolojiler

- **YOLO** (Ultralytics) -- Nesne tespiti ve sınıflandırma
- **OpenCV** -- Görüntü işleme, video okuma/yazma
- **Flask + pywebview** -- Masaüstü uygulama (native pencere)
- **fast-plate-ocr** -- Plaka karakteri tanıma (ONNX)
- **SQLite** -- Yerel veritabanı
- **ByteTrack** -- Çoklu nesne takibi

---

## Lisans

Bu proje bir üniversite staj çalışmasıdır.
