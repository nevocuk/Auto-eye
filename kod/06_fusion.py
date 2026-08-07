"""
Adım 6: Fusion — plaka (OCR) + marka/model tespitini TEK bir kayıtta birleştirme

Ne yapar (baştan sona):
  1) Aynı fotoğrafta İKİ AYRI model çalıştırılır:
       - plaka tespit modeli (models/plaka_tespit.pt) -> plaka kutuları
       - marka/model modeliniz (runs/egitimX/weights/best.pt) -> araç kutuları + class
  2) Her plaka kutusu OCR'a (fast-plate-ocr, plakaya özel eğitilmiş bir model)
     verilip metne çevrilir -- EasyOCR (genel amaçlı OCR) yerine bunu
     kullanıyoruz çünkü gerçek fotoğraflarla test ederken EasyOCR karakter
     karıştırma/eksik okuma sorunları yaşattı (bkz. ILERLEME_GUNLUGU.md,
     "Adım 6"). fast-plate-ocr'ın kendi plaka TESPİTİ yok, sadece kırpılmış
     bir plaka görüntüsünü okuyor -- tespiti hâlâ bizim plaka_tespit.pt
     modelimiz yapıyor.
  3) EŞLEŞTİRME: bulunan her plaka kutusu, HANGİ araç kutusuna ait? Bunu plaka
     kutusunun ne kadarının araç kutusunun İÇİNDE kaldığına bakarak buluyoruz
     (plaka çok küçük olduğu için normal IoU yerine "örtüşme oranı" kullanıyoruz).
     Aynı araca birden fazla plaka adayı denk gelirse, EN YÜKSEK TESPİT
     GÜVENLİSİ seçilir (son gelen değil) -- yanlış-pozitif ikinci kutuların
     doğru sonucu ezmesini önlemek için.
  4) TANIMLANMADI FALLBACK: özel modelin (marka/model) hiçbir kutusuna
     eşlenemeyen ("öksüz") bir plaka kalırsa, SADECE O ZAMAN genel/hazır bir
     COCO modeliyle (Ön-Etiketleme'nin kullandığı aynı mantık) ek bir tarama
     yapılıp, sadece o öksüz plakayı barındıran araç kutusu "tanimlanmadi"
     diye işaretlenir. Bu YENİ BİR CLASS DEĞİL -- hiçbir dosyaya (data.yaml,
     model ağırlığı) kalıcı yazılmaz, sadece bu çalıştırmanın çıktısında
     görünen düz bir metin etiketidir.
  5) GÜVEN KATMANLAMA: hem marka/model hem plaka için "kesin / muhtemel /
     belirsiz" seviyesi atanır -- düşük güvenli bir tahmini ZORLA doğru gibi
     göstermek yerine "belirsiz" demek, kapalı-küme sınıflandırmanın (model
     bilmediği bir arabayı yanlışlıkla bilinen bir class'a benzetmesi) riskini
     azaltır.
  6) Sonuç: her araç için TEK bir sözlük (plaka + marka/model + güven +
     durum bir arada), ekrana yazdırılır, `sonuc_<gorsel_adi>.jpg` olarak
     kutulu görsel kaydedilir ve kayitlar/fusion_sonucu.json'a kaydedilir
     (ileride SQLite'a yazarken bu JSON'u okumamız yeterli olacak).

Nasıl çalıştırılır:
  python kod/06_fusion.py                      (varsayılan: "test edilecekler/telcam1/test_arac2.jpg")
  python kod/06_fusion.py "yol/gorsel.jpg"      (kendi görselinizle -- HEIC/HEIF de olabilir)

  Marka/model modelini değiştirmek isterseniz aşağıdaki MARKA_MODEL_YOLU
  sabitini güncelleyin (şu an en son/en iyi sonuçlı çalışmayı gösteriyor).

  Kurulum (bir kere): pip install fast-plate-ocr[onnx] pillow-heif
  (NVIDIA GPU'n varsa [onnx] yerine [onnx-gpu] kullanabilirsin.)
"""

import json
import re
import sys
from pathlib import Path

import cv2
import numpy as np
from ultralytics import YOLO

PROJE_KOK = Path(__file__).resolve().parent.parent

# --- Ayarlar ---
VARSAYILAN_GORSEL = PROJE_KOK / "test edilecekler" / "telcam1" / "test_arac2.jpg"
PLAKA_MODEL_YOLU = PROJE_KOK / "models" / "plaka_tespit.pt"
# NOT: burayı elinizdeki en güncel/en iyi eğitim çalışmasına göre güncelleyin
# (örn. gece eğitimi bitince onun best.pt'sine çevirin).
MARKA_MODEL_YOLU = PROJE_KOK / "runs" / "egitim4" / "weights" / "best.pt"
CIKTI_KLASOR = PROJE_KOK / "kayitlar"

# Genel/fallback ("tanımlanmadı") tarama için hazır COCO modeli.
GENEL_MODEL_ADI = "yolo11n.pt"
GENEL_ARAC_SINIF_ADLARI = {"car", "truck", "bus"}

# fast-plate-ocr modeli.
PLAKA_OCR_MODEL_ADI = "cct-s-v2-global-model"

# --- Güven eşikleri (confidence katmanlama) ---
# Bunlar "sihirli sayı" değil, projeye göre ayarlanabilir başlangıç değerleri.
MARKA_ESIK_KESIN = 0.80
MARKA_ESIK_MUHTEMEL = 0.50
PLAKA_ESIK_KESIN = 0.60  # OCR ortalama güveni + format geçerliliği birlikte değerlendirilir
PLAKA_TESPIT_ESIK_MIN = 0.40  # bu eşiğin altındaki plaka kutuları baştan elenir

# --- Eşleştirme eşiği: plaka kutusunun en az bu oranı araç kutusunun
# İÇİNDE kalmalı ki "bu plaka bu araca ait" diyelim ---
ESLESME_ESIGI = 0.55

# --- Türk plaka format doğrulama ---
TR_PLAKA_REGEX = re.compile(r"^(\d{2})([A-Z]{1,3})(\d{2,4})$")
HARF_YERINE_RAKAM = {"O": "0", "I": "1", "S": "5", "B": "8", "Z": "2"}
RAKAM_YERINE_HARF = {"0": "O", "1": "I", "5": "S", "8": "B", "2": "Z"}


# ===============================================================
# ADIM A -- GÖRSEL OKUMA (HEIC/HEIF destekli)
# ===============================================================

def gorseli_oku(dosya_yolu: str):
    """Görseli BGR numpy array olarak okur. Önce normal cv2.imread'i dener;
    None dönerse (OpenCV'nin çözemediği bir format -- en sık HEIC/HEIF,
    iPhone fotoğrafları) pillow-heif ile açmayı dener. Uzantıya değil,
    GERÇEKTEN okunup okunamadığına bakıyoruz -- dosya adını ".heic"ten
    ".jpg"ye çevirmek İÇERİĞİNİ dönüştürmüyor.
    Döndürür: (goruntu, hata_mesaji)."""
    goruntu = cv2.imread(dosya_yolu)
    if goruntu is not None:
        return goruntu, None

    try:
        import pillow_heif
    except ImportError:
        return None, (
            f"Görsel okunamadı: {dosya_yolu} -- eğer bu bir HEIC/HEIF "
            "(iPhone) fotoğrafıysa, otomatik dönüştürmek için "
            "'pillow-heif' kütüphanesi kurulu değil "
            "(kurmak için: pip install pillow-heif)."
        )

    try:
        from PIL import Image as _PILImage
        pillow_heif.register_heif_opener()
        # Çok yüksek çözünürlüklü telefon fotoğrafları PIL'in "decompression
        # bomb" güvenlik limitini aşabiliyor -- kaynak kullanıcının kendi
        # fotoğrafı (güvenilir) olduğu için bu limiti kapatıyoruz.
        _PILImage.MAX_IMAGE_PIXELS = None
        img = _PILImage.open(dosya_yolu).convert("RGB")
        rgb = np.array(img)
        return cv2.cvtColor(rgb, cv2.COLOR_RGB2BGR), None
    except Exception as e:
        return None, f"Görsel okunamadı (HEIC dönüştürme de başarısız oldu): {e}"


# ===============================================================
# ADIM B -- PLAKA OCR YARDIMCILARI
# ===============================================================

def _karakter_duzeltme_varyantlari(metin: str):
    if len(metin) < 4:
        return []
    bas = "".join(HARF_YERINE_RAKAM.get(c, c) for c in metin[:2])
    kalan = metin[2:]
    harf_blok = ""
    i = 0
    while i < len(kalan) and kalan[i] not in "0123456789":
        harf_blok += RAKAM_YERINE_HARF.get(kalan[i], kalan[i])
        i += 1
    son = "".join(HARF_YERINE_RAKAM.get(c, c) for c in kalan[i:])
    return [bas + harf_blok + son]


def temizle_ve_dogrula(ham_metin: str) -> tuple[str, bool]:
    """Ham OCR metnini Türk plaka formatına yaklaştırmaya çalışır.
    Döndürür: (temizlenmiş_metin, format_gecerli_mi)"""
    metin = ham_metin.upper()
    metin = re.sub(r"[^A-Z0-9]", "", metin)
    if TR_PLAKA_REGEX.match(metin):
        return metin, True
    for aday in _karakter_duzeltme_varyantlari(metin):
        if TR_PLAKA_REGEX.match(aday):
            return aday, True
    return metin, False


def beyaz_bolgeye_kirp(goruntu_bgr):
    """Kırpılmış plaka görüntüsünde SADECE beyaz zeminli (plakanın kendisi)
    bölgeyi bulup ona sıkıca kırpar -- siyah plastik çerçeve, bayilik
    yazısı/sticker gibi plaka OLMAYAN öğeleri OCR'a hiç vermemek için.
    Yeterince büyük bir beyaz bölge bulunamazsa orijinali döner."""
    hsv = cv2.cvtColor(goruntu_bgr, cv2.COLOR_BGR2HSV)
    alt = np.array([0, 0, 100], dtype=np.uint8)
    ust = np.array([180, 80, 255], dtype=np.uint8)
    maske = cv2.inRange(hsv, alt, ust)

    cekirdek = np.ones((5, 5), np.uint8)
    maske = cv2.morphologyEx(maske, cv2.MORPH_CLOSE, cekirdek)
    maske = cv2.morphologyEx(maske, cv2.MORPH_OPEN, np.ones((3, 3), np.uint8))

    konturlar, _ = cv2.findContours(maske, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    if not konturlar:
        return goruntu_bgr

    en_buyuk = max(konturlar, key=cv2.contourArea)
    x, y, w, h = cv2.boundingRect(en_buyuk)

    toplam_alan = goruntu_bgr.shape[0] * goruntu_bgr.shape[1]
    if w * h < 0.15 * toplam_alan:
        return goruntu_bgr

    pay_x = max(2, int(w * 0.08))
    pay_y = max(2, int(h * 0.08))
    yukseklik, genislik = goruntu_bgr.shape[:2]
    x1, y1 = max(0, x - pay_x), max(0, y - pay_y)
    x2, y2 = min(genislik, x + w + pay_x), min(yukseklik, y + h + pay_y)

    return goruntu_bgr[y1:y2, x1:x2]


def plakayi_oku(reader, plaka_kirpik_bgr):
    """fast-plate-ocr ile bir plaka kutusunun kırpılmış görüntüsünü okur.
    Hem beyaz-bölgeye-kırpılmış hem ham kırpığı dener, hangisi daha yüksek
    ortalama karakter güveniyle sonuç verirse onu kullanır.
    Döndürür: (temiz_metin, ocr_guven, format_gecerli_mi) ya da hiçbir şey
    okunamazsa (None, 0.0, False)."""
    beyaz_kirpik = beyaz_bolgeye_kirp(plaka_kirpik_bgr)

    denemeler = []
    for _etiket, goruntu_bgr in (("beyaz-bolgeye-kirpilmis", beyaz_kirpik), ("ham", plaka_kirpik_bgr)):
        rgb = cv2.cvtColor(goruntu_bgr, cv2.COLOR_BGR2RGB)
        try:
            sonuc = reader.run(rgb, return_confidence=True)[0]
        except Exception:
            continue
        metin = (sonuc.plate or "").upper()
        if sonuc.char_probs is not None and len(sonuc.char_probs):
            guven = float(np.mean(sonuc.char_probs))
        else:
            guven = 0.0
        if metin:
            denemeler.append((metin, guven))

    if not denemeler:
        return None, 0.0, False

    en_iyi_metin, en_iyi_guven = max(denemeler, key=lambda d: d[1])
    temiz, gecerli = temizle_ve_dogrula(en_iyi_metin)
    return temiz, en_iyi_guven, gecerli


# ===============================================================
# ADIM C -- EŞLEŞTİRME: plaka kutusu hangi araç kutusuna ait?
# ===============================================================

def ortusme_orani(kucuk_kutu, buyuk_kutu) -> float:
    """kucuk_kutu'nun (plaka) NE KADARI buyuk_kutu'nun (araç) içinde kalıyor?
    Normal IoU kullanmıyoruz çünkü plaka, araca göre çok küçük -- IoU her
    zaman düşük çıkar, doğru eşleşmeyi bile eleyebilir."""
    x1 = max(kucuk_kutu[0], buyuk_kutu[0])
    y1 = max(kucuk_kutu[1], buyuk_kutu[1])
    x2 = min(kucuk_kutu[2], buyuk_kutu[2])
    y2 = min(kucuk_kutu[3], buyuk_kutu[3])
    if x2 <= x1 or y2 <= y1:
        return 0.0
    kesisim = (x2 - x1) * (y2 - y1)
    kucuk_alan = (kucuk_kutu[2] - kucuk_kutu[0]) * (kucuk_kutu[3] - kucuk_kutu[1])
    return kesisim / kucuk_alan if kucuk_alan > 0 else 0.0


def plakayi_araca_esle(plaka_kutu, arac_kutulari: list) -> int | None:
    """arac_kutulari: [(x1,y1,x2,y2), ...]. En yüksek örtüşme oranına sahip
    aracın index'ini döner; hiçbiri eşiği geçmiyorsa None."""
    en_iyi_oran = 0.0
    en_iyi_index = None
    for i, arac_kutu in enumerate(arac_kutulari):
        oran = ortusme_orani(plaka_kutu, arac_kutu)
        if oran > en_iyi_oran:
            en_iyi_oran = oran
            en_iyi_index = i
    return en_iyi_index if en_iyi_oran >= ESLESME_ESIGI else None


# ===============================================================
# ADIM D -- GÜVEN KATMANLAMA
# ===============================================================

def marka_model_durumu(guven: float) -> str:
    if guven >= MARKA_ESIK_KESIN:
        return "kesin"
    if guven >= MARKA_ESIK_MUHTEMEL:
        return "muhtemel"
    return "belirsiz"


def plaka_durumu(ocr_guven: float, format_gecerli: bool) -> str:
    if not format_gecerli:
        return "format_gecersiz"
    if ocr_guven >= PLAKA_ESIK_KESIN:
        return "kesin"
    return "muhtemel"


# ===============================================================
# ANA AKIŞ
# ===============================================================

def main():
    gorsel_yolu = Path(sys.argv[1]) if len(sys.argv) > 1 else VARSAYILAN_GORSEL
    if not gorsel_yolu.exists():
        print(f"[HATA] Görsel bulunamadı: {gorsel_yolu}")
        return
    if not MARKA_MODEL_YOLU.exists():
        print(f"[HATA] Marka/model modeli bulunamadı: {MARKA_MODEL_YOLU}")
        print("MARKA_MODEL_YOLU sabitini kendi best.pt yolunuza göre güncelleyin.")
        return

    goruntu, okuma_hatasi = gorseli_oku(str(gorsel_yolu))
    if goruntu is None:
        print(f"[HATA] {okuma_hatasi}")
        return
    CIKTI_KLASOR.mkdir(parents=True, exist_ok=True)

    # --- 1) Marka/model tespiti ---
    print("[1/4] Marka/model modeli çalıştırılıyor...")
    marka_model = YOLO(str(MARKA_MODEL_YOLU))
    marka_sonuc = marka_model(goruntu, verbose=False)[0]
    arac_kutulari = []       # [(x1,y1,x2,y2), ...]
    arac_tahminleri = []     # [(class_adi, guven, durum), ...] aynı index sırasıyla
    for kutu in marka_sonuc.boxes:
        x1, y1, x2, y2 = map(int, kutu.xyxy[0].tolist())
        guven = float(kutu.conf[0])
        class_id = int(kutu.cls[0])
        class_adi = marka_model.names[class_id]
        arac_kutulari.append((x1, y1, x2, y2))
        arac_tahminleri.append((class_adi, guven, marka_model_durumu(guven)))
        print(f"  Araç kutusu: {class_adi} (guven={guven:.2f}) bbox=({x1},{y1},{x2},{y2})")

    if not arac_kutulari:
        print("[uyari] Hiç araç tespit edilemedi, fusion için devam edilemiyor.")
        return

    # --- 2) Plaka tespiti ---
    print("\n[2/4] Plaka tespit modeli çalıştırılıyor...")
    plaka_model = YOLO(str(PLAKA_MODEL_YOLU))
    plaka_sonuc = plaka_model(goruntu, verbose=False)[0]
    plaka_kutulari = []
    for kutu in plaka_sonuc.boxes:
        guven = float(kutu.conf[0])
        if guven < PLAKA_TESPIT_ESIK_MIN:
            continue
        x1, y1, x2, y2 = map(int, kutu.xyxy[0].tolist())
        plaka_kutulari.append((x1, y1, x2, y2, guven))
        print(f"  Plaka kutusu: bbox=({x1},{y1},{x2},{y2})  guven={guven:.2f}")

    # --- 3) Her plakayı OCR'la oku ---
    print("\n[3/4] Plakalar OCR ile okunuyor (ilk çalıştırmada fast-plate-ocr modeli indirebilir)...")
    from fast_plate_ocr import LicensePlateRecognizer
    reader = LicensePlateRecognizer(PLAKA_OCR_MODEL_ADI)

    plaka_okumalari = []  # [(kutu, metin, ocr_guven, format_gecerli, tespit_guven), ...]
    yukseklik, genislik = goruntu.shape[:2]
    for (x1, y1, x2, y2, tespit_guven) in plaka_kutulari:
        pay_x = int((x2 - x1) * 0.15)
        pay_y = int((y2 - y1) * 0.15)
        px1, py1 = max(0, x1 - pay_x), max(0, y1 - pay_y)
        px2, py2 = min(genislik, x2 + pay_x), min(yukseklik, y2 + pay_y)
        kirpik = goruntu[py1:py2, px1:px2]
        if kirpik.size == 0:
            plaka_okumalari.append(((x1, y1, x2, y2), None, 0.0, False, tespit_guven))
            continue

        hedef_genislik = 300
        if kirpik.shape[1] < hedef_genislik:
            olcek = hedef_genislik / kirpik.shape[1]
            kirpik = cv2.resize(kirpik, None, fx=olcek, fy=olcek, interpolation=cv2.INTER_CUBIC)

        metin, ocr_guven, gecerli = plakayi_oku(reader, kirpik)
        if metin:
            print(f"  '{metin}' (ocr_guven={ocr_guven:.2f}, format_gecerli={gecerli})")
        else:
            print("  (bu plaka kutusundan metin okunamadı)")
        plaka_okumalari.append(((x1, y1, x2, y2), metin, ocr_guven, gecerli, tespit_guven))

    # --- 4) FUSION: plakaları araçlara eşle, tanımlanmadı fallback, tek kayıt üret ---
    print("\n[4/4] Eşleştirme + güven katmanlama...")
    araclar = []
    for i, (class_adi, guven, durum) in enumerate(arac_tahminleri):
        araclar.append({
            "arac_no": i,
            "marka_model": class_adi,
            "marka_model_guven": round(guven, 3),
            "marka_model_durum": durum,
            "plaka": None,
            "plaka_guven": None,
            "plaka_durum": "bulunamadi",
        })

    araca_en_iyi_aday = {}  # arac_index -> (plaka_kutu, metin, ocr_guven, gecerli, tespit_guven)
    oksuz_plakalar = []     # eşlenemeyen plakalar
    for plaka_kutu, metin, ocr_guven, gecerli, tespit_guven in plaka_okumalari:
        hedef_index = plakayi_araca_esle(plaka_kutu, arac_kutulari)
        if hedef_index is None:
            oksuz_plakalar.append((plaka_kutu, metin, ocr_guven, gecerli, tespit_guven))
            continue
        mevcut = araca_en_iyi_aday.get(hedef_index)
        if mevcut is None or tespit_guven > mevcut[4]:
            if mevcut is not None:
                print(f"  [bilgi] Araç #{hedef_index} için daha düşük güvenli plaka adayı elendi: '{mevcut[1]}'")
            araca_en_iyi_aday[hedef_index] = (plaka_kutu, metin, ocr_guven, gecerli, tespit_guven)

    for hedef_index, (plaka_kutu, metin, ocr_guven, gecerli, _tespit_guven) in araca_en_iyi_aday.items():
        araclar[hedef_index]["plaka"] = metin
        araclar[hedef_index]["plaka_guven"] = round(ocr_guven, 3) if metin else None
        araclar[hedef_index]["plaka_durum"] = plaka_durumu(ocr_guven, gecerli) if metin else "okunamadi"

    if oksuz_plakalar:
        print(f"  [bilgi] {len(oksuz_plakalar)} plaka özel modelin bulduğu hiçbir araç kutusuna eşlenemedi -- "
              "genel/fallback araç taraması yapılıyor...")
        genel_model = YOLO(GENEL_MODEL_ADI)
        genel_sonuc = genel_model(goruntu, verbose=False)[0]
        genel_kutular = []
        for kutu in genel_sonuc.boxes:
            class_id = int(kutu.cls[0])
            class_adi = genel_model.names[class_id]
            if class_adi in GENEL_ARAC_SINIF_ADLARI:
                x1, y1, x2, y2 = map(int, kutu.xyxy[0].tolist())
                genel_kutular.append(((x1, y1, x2, y2), float(kutu.conf[0])))

        for plaka_kutu, metin, ocr_guven, gecerli, _tespit_guven in oksuz_plakalar:
            en_iyi_oran, en_iyi_kutu, en_iyi_guven = 0.0, None, 0.0
            for genel_kutu, genel_guven in genel_kutular:
                oran = ortusme_orani(plaka_kutu, genel_kutu)
                if oran > en_iyi_oran:
                    en_iyi_oran, en_iyi_kutu, en_iyi_guven = oran, genel_kutu, genel_guven
            if en_iyi_kutu is None or en_iyi_oran < ESLESME_ESIGI:
                print(f"  [uyari] '{metin}' fallback taramada da hiçbir araç kutusuna eşlenemedi (atlandı).")
                continue
            yeni_index = len(araclar)
            arac_kutulari.append(en_iyi_kutu)
            araclar.append({
                "arac_no": yeni_index,
                "marka_model": "tanimlanmadi",
                # app.py ile tutarlılık için (2026-08-03 düzeltmesi): burada
                # None yerine genel modelin bu kutu için ürettiği tespit
                # güvenini yazıyoruz -- 07_veritabani.py ile DB'ye aktarılırsa
                # marka_model_guven artık NULL kalmıyor.
                "marka_model_guven": round(en_iyi_guven, 3),
                "marka_model_durum": "taninmiyor",
                "plaka": metin,
                "plaka_guven": round(ocr_guven, 3) if metin else None,
                "plaka_durum": plaka_durumu(ocr_guven, gecerli) if metin else "okunamadi",
            })
            print(f"  [bilgi] '{metin}' plakası 'tanımlanmadı' bir araca eşlendi (bbox={en_iyi_kutu}).")

    print("\n=== FUSION SONUCU ===")
    for arac in araclar:
        print(
            f"  Araç #{arac['arac_no']}: "
            f"marka/model={arac['marka_model']} ({arac['marka_model_durum']}, "
            f"guven={arac['marka_model_guven']})  |  "
            f"plaka={arac['plaka']} ({arac['plaka_durum']}, "
            f"guven={arac['plaka_guven']})"
        )

    # --- Kutulu sonuç görselini kaydet (ölçek-uyumlu çizim) ---
    cizili = marka_sonuc.plot()
    goruntu_olcegi = max(cizili.shape[:2]) / 1000
    kalinlik = max(2, round(3 * goruntu_olcegi))
    yazi_olcek = max(0.7, 1.0 * goruntu_olcegi)
    yazi_kalinlik = max(2, round(2 * goruntu_olcegi))
    ozel_kutu_sayisi = len(arac_tahminleri)
    for i, arac in enumerate(araclar):
        if i >= ozel_kutu_sayisi:
            x1, y1, x2, y2 = arac_kutulari[i]
            cv2.rectangle(cizili, (x1, y1), (x2, y2), (0, 0, 255), kalinlik)
            cv2.putText(cizili, "tanimlanmadi", (x1, max(0, y1 - 10)),
                        cv2.FONT_HERSHEY_SIMPLEX, yazi_olcek, (0, 0, 255), yazi_kalinlik)
    for plaka_kutu, metin, _ocr_guven, _gecerli, _tespit_guven in plaka_okumalari:
        x1, y1, x2, y2 = plaka_kutu
        cv2.rectangle(cizili, (x1, y1), (x2, y2), (255, 255, 0), kalinlik)
        if metin:
            cv2.putText(cizili, metin, (x1, min(cizili.shape[0] - 5, y2 + 25)),
                        cv2.FONT_HERSHEY_SIMPLEX, yazi_olcek, (255, 255, 0), yazi_kalinlik)

    sonuc_gorsel_yolu = CIKTI_KLASOR / f"sonuc_{gorsel_yolu.stem}.jpg"
    cv2.imwrite(str(sonuc_gorsel_yolu), cizili)

    cikti_yolu = CIKTI_KLASOR / "fusion_sonucu.json"
    with open(cikti_yolu, "w", encoding="utf-8") as f:
        json.dump({"gorsel": str(gorsel_yolu), "araclar": araclar}, f, ensure_ascii=False, indent=2)
    print(f"\n[bilgi] Sonuç görseli kaydedildi: {sonuc_gorsel_yolu}")
    print(f"[bilgi] Sonuç JSON kaydedildi: {cikti_yolu}")
    print("(Bir sonraki adımda -- SQLite şeması kurulunca -- bu JSON'daki")
    print(" 'araclar' listesi doğrudan veritabanına yazılacak satırlara karşılık gelecek.)")


if __name__ == "__main__":
    main()
