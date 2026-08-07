"""
Adım 2: Plaka tespiti - tekli görüntüde test

Ne yapar:
  1. Hazır (eğitilmiş) bir plaka tespit modelini indirir (Hugging Face'ten,
     hesap/API key gerekmez, halka açık bir model).
  2. Verdiğin bir fotoğrafta plaka bölgesini/bölgelerini tespit eder.
  3. Bulunan her plaka için: bbox koordinatlarını, güven skorunu yazdırır
     ve plaka bölgesini kırpıp ayrı bir dosya olarak kaydeder
     (bir sonraki adımda bu kırpılmış görüntüyü OCR'a vereceğiz).

Nasıl çalıştırılır:
  1) Proje klasörünün kökünde (otopark/) bir terminal aç.
  2) pip install -r requirements.txt   (henüz yapmadıysan)
  3) Test edeceğin bir araç fotoğrafını (plakası görünen) şu isimle koy:
       otopark/veri/test_arac.jpg
  4) python kod/01_plaka_tespit_test.py
  5) Sonuçlar: otopark/kayitlar/plaka_kirpik_0.jpg, plaka_kirpik_1.jpg ...
     ve terminalde bbox/güven skoru yazdırılır.
"""

from pathlib import Path
from ultralytics import YOLO
import cv2

# --- Ayarlar ---
PROJE_KOK = Path(__file__).resolve().parent.parent
TEST_GORSEL = PROJE_KOK / "veri" / "test_arac2.jpg"
MODEL_YOLU = PROJE_KOK / "models" / "plaka_tespit.pt"
CIKTI_KLASOR = PROJE_KOK / "kayitlar"

# Halka açık, hazır eğitilmiş plaka tespit modeli (Hugging Face, Ultralytics
# YOLOv8 formatında, MIT lisanslı, ~6 MB). Hesap/API key gerekmez.
# https://huggingface.co/Koushim/yolov8-license-plate-detection
MODEL_URL = "https://huggingface.co/Koushim/yolov8-license-plate-detection/resolve/main/best.pt"


def modeli_hazirla() -> Path:
    """Model dosyasını yoksa indirir, varsa doğrudan yolunu döner."""
    if MODEL_YOLU.exists():
        print(f"[bilgi] Model zaten var: {MODEL_YOLU}")
        return MODEL_YOLU

    print("[bilgi] Model bulunamadı, indiriliyor...")
    import urllib.request

    MODEL_YOLU.parent.mkdir(parents=True, exist_ok=True)
    urllib.request.urlretrieve(MODEL_URL, MODEL_YOLU)
    print(f"[bilgi] Model indirildi: {MODEL_YOLU}")
    return MODEL_YOLU


def main():
    if not TEST_GORSEL.exists():
        print(f"[HATA] Test görseli bulunamadı: {TEST_GORSEL}")
        print("Lütfen plakası görünen bir araç fotoğrafını bu isimle koy:")
        print(f"  {TEST_GORSEL}")
        return

    model_yolu = modeli_hazirla()
    model = YOLO(str(model_yolu))

    print(f"[bilgi] Tespit çalıştırılıyor: {TEST_GORSEL}")
    sonuclar = model(str(TEST_GORSEL))

    goruntu = cv2.imread(str(TEST_GORSEL))
    CIKTI_KLASOR.mkdir(parents=True, exist_ok=True)

    yukseklik, genislik = goruntu.shape[:2]
    PAY_ORANI = 0.15  # bbox'ın her yönüne %15 pay bırak (harfler kesilmesin)

    toplam = 0
    for sonuc in sonuclar:
        for i, kutu in enumerate(sonuc.boxes):
            x1, y1, x2, y2 = map(int, kutu.xyxy[0].tolist())
            guven = float(kutu.conf[0])
            print(f"  Plaka #{i}: bbox=({x1},{y1},{x2},{y2})  guven={guven:.2f}")

            # Kırpmadan önce bbox'a pay ekle (OCR harfleri kesmesin diye)
            pay_x = int((x2 - x1) * PAY_ORANI)
            pay_y = int((y2 - y1) * PAY_ORANI)
            px1, py1 = max(0, x1 - pay_x), max(0, y1 - pay_y)
            px2, py2 = min(genislik, x2 + pay_x), min(yukseklik, y2 + pay_y)

            kirpik = goruntu[py1:py2, px1:px2]

            # Plaka bölgeleri küçük çıktığı için OCR öncesi büyütüyoruz.
            # Genişliği en az 300 piksele getirecek şekilde ölçekle.
            hedef_genislik = 300
            mevcut_genislik = kirpik.shape[1]
            if mevcut_genislik < hedef_genislik:
                olcek = hedef_genislik / mevcut_genislik
                kirpik = cv2.resize(kirpik, None, fx=olcek, fy=olcek,
                                     interpolation=cv2.INTER_CUBIC)

            cikti_yolu = CIKTI_KLASOR / f"plaka_kirpik_{i}.jpg"
            cv2.imwrite(str(cikti_yolu), kirpik)
            print(f"    -> kaydedildi: {cikti_yolu} (buyutulmus boyut: {kirpik.shape[1]}x{kirpik.shape[0]})")
            toplam += 1

    if toplam == 0:
        print("[uyari] Hiç plaka tespit edilemedi. Farklı bir fotoğrafla dene "
              "(plaka net görünür, çok küçük/uzak olmayan bir kare).")
    else:
        print(f"[bilgi] Toplam {toplam} plaka tespit edildi.")


if __name__ == "__main__":
    main()
