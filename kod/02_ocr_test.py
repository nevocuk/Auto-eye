"""
Adım 3: OCR entegrasyonu — tekli görüntüde test

Ne yapar:
  1. Adım 2'de kırpıp kaydettiğimiz plaka görüntüsünü (kayitlar/plaka_kirpik_0.jpg)
     EasyOCR'a verir.
  2. Ham OCR çıktısını (okunan metin + güven skoru) yazdırır.
  3. Türk plaka formatına göre bir "temizleme" uygular:
     - Büyük harfe çevirir, boşluk/nokta/tire gibi karakterleri kaldırır
     - OCR'ın sık karıştırdığı karakterleri düzeltir (O<->0, I<->1 gibi)
       YALNIZCA plaka formatına uyacak şekilde (harf beklenen yerde 0->O,
       rakam beklenen yerde O->0 gibi)
     - Sonucu Türk plaka regex'iyle (## X(XX) #### gibi) kontrol eder

Nasıl çalıştırılır:
  python kod/02_ocr_test.py
  (Adım 2'yi çalıştırıp kayitlar/plaka_kirpik_0.jpg dosyasının oluşmuş
  olması gerekir.)
"""

import re
from pathlib import Path

import cv2
import easyocr

PROJE_KOK = Path(__file__).resolve().parent.parent
PLAKA_GORSEL = PROJE_KOK / "kayitlar" / "plaka_kirpik_0.jpg"

# Türk plaka formatı, örn: "34 ABC 123", "06 A 1234", "34 AB 123"
# Genel kalıp: 2 rakam (il kodu) + 1-3 harf + 2-4 rakam
TR_PLAKA_REGEX = re.compile(r"^(\d{2})([A-Z]{1,3})(\d{2,4})$")

# OCR'ın harf/rakam karıştırma ihtimaline karşı basit düzeltme haritaları
HARF_YERINE_RAKAM = {"O": "0", "I": "1", "S": "5", "B": "8", "Z": "2"}
RAKAM_YERINE_HARF = {"0": "O", "1": "I", "5": "S", "8": "B", "2": "Z"}


def temizle_ve_dogrula(ham_metin: str) -> tuple[str, bool]:
    """Ham OCR metnini Türk plaka formatına yaklaştırmaya çalışır.
    Döndürür: (temizlenmiş_metin, format_gecerli_mi)
    """
    metin = ham_metin.upper()
    metin = re.sub(r"[^A-Z0-9]", "", metin)  # boşluk, nokta, tire vs. temizle

    if TR_PLAKA_REGEX.match(metin):
        return metin, True

    # Doğrudan eşleşmedi -> karakter bazlı düzeltme dene:
    # baştaki 2 karakter rakam olmalı, ortadaki harf(ler), sondaki rakamlar
    # Basit bir sezgisel deneme: pozisyonuna göre O/0, I/1 gibi karakterleri düzelt
    duzeltme_denemeleri = _karakter_duzeltme_varyantlari(metin)
    for aday in duzeltme_denemeleri:
        if TR_PLAKA_REGEX.match(aday):
            return aday, True

    return metin, False


def _karakter_duzeltme_varyantlari(metin: str):
    """Metnin ilk 2 karakterini rakama, harf bölgesini harfe, son kısmı
    rakama zorlayan basit bir varyant üretir (tek bir sezgisel deneme)."""
    if len(metin) < 4:
        return []

    # İlk 2 karakter -> rakam olmalı
    bas = "".join(HARF_YERINE_RAKAM.get(c, c) for c in metin[:2])

    # Kalan kısımda: harften rakama geçişi bul (ilk rakamın göründüğü yeri
    # ortadaki harf bloğunun bitişi say)
    kalan = metin[2:]
    harf_blok = ""
    i = 0
    while i < len(kalan) and kalan[i] not in "0123456789":
        harf_blok += RAKAM_YERINE_HARF.get(kalan[i], kalan[i])
        i += 1
    son = "".join(HARF_YERINE_RAKAM.get(c, c) for c in kalan[i:])

    return [bas + harf_blok + son]


ALLOWLIST = "ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789"


def on_isle(goruntu, hedef_genislik: int = 500):
    """Plaka görüntüsünü OCR için hazırlar: büyüt + gri tonlama + kontrast
    artırma (CLAHE). Renkli/mavi şerit gibi gürültüyü azaltıp harflerin
    kenarlarını belirginleştirmeyi amaçlar."""
    mevcut_genislik = goruntu.shape[1]
    if mevcut_genislik < hedef_genislik:
        olcek = hedef_genislik / mevcut_genislik
        goruntu = cv2.resize(goruntu, None, fx=olcek, fy=olcek,
                              interpolation=cv2.INTER_CUBIC)

    gri = cv2.cvtColor(goruntu, cv2.COLOR_BGR2GRAY)
    clahe = cv2.createCLAHE(clipLimit=3.0, tileGridSize=(8, 8))
    kontrastli = clahe.apply(gri)
    return kontrastli


def sol_seridi_kirp(goruntu, oran: float = 0.16):
    """Avrupa tipi plakaların solundaki mavi/renkli şeridi (TR/ülke kodu
    bandı) kırpar — bu şerit metin değil, OCR'ı gereksiz yere şaşırtabilir."""
    genislik = goruntu.shape[1]
    kesim = int(genislik * oran)
    return goruntu[:, kesim:]


def otsu_esikleme(gri_goruntu):
    """Gri görüntüyü siyah-beyaza (binary) çevirir. Otsu yöntemi eşik
    değerini otomatik seçer — karakterleri arka plandan netçe ayırmak
    için OCR öncesi klasik bir adım."""
    bulanik = cv2.GaussianBlur(gri_goruntu, (3, 3), 0)
    _esik, ikili = cv2.threshold(bulanik, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
    return ikili


def bloklari_birlestir(sonuclar):
    """EasyOCR genelde plakayı tek blok değil, birkaç parçaya bölünmüş
    olarak döner (örn. '31', '585', 'RS'). Bunları soldan sağa doğru
    (bbox'ın en sol x koordinatına göre) sıralayıp birleştiriyoruz ki
    tam plaka metnini elde edelim — tek bir parçayı almak yanlış olurdu.
    Döndürür: (birlesik_metin, ortalama_guven)
    """
    if not sonuclar:
        return "", 0.0

    # bbox 4 köşe noktasından oluşur: [[x1,y1],[x2,y2],[x3,y3],[x4,y4]]
    # en sol x'i bulmak için hepsinin x'lerinin minimumunu alıyoruz.
    sirali = sorted(sonuclar, key=lambda s: min(nokta[0] for nokta in s[0]))
    metinler = [metin for _bbox, metin, _guven in sirali]
    guvenler = [guven for _bbox, metin, guven in sirali]

    birlesik_metin = " ".join(metinler)
    ortalama_guven = sum(guvenler) / len(guvenler)
    return birlesik_metin, ortalama_guven


def en_iyi_sonucu_sec(denemeler):
    """[(etiket, sonuclar_listesi), ...] arasından, bloklarını birleştirip
    en yüksek ortalama güvene sahip varyantı seçer.
    Döndürür: (etiket, birlesik_metin, ortalama_guven)"""
    en_iyi = None
    for etiket, sonuclar in denemeler:
        birlesik_metin, ortalama_guven = bloklari_birlestir(sonuclar)
        if not birlesik_metin:
            continue
        if en_iyi is None or ortalama_guven > en_iyi[2]:
            en_iyi = (etiket, birlesik_metin, ortalama_guven)
    return en_iyi


def main():
    if not PLAKA_GORSEL.exists():
        print(f"[HATA] Plaka görseli bulunamadı: {PLAKA_GORSEL}")
        print("Önce kod/01_plaka_tespit_test.py çalıştırılmalı.")
        return

    print("[bilgi] EasyOCR başlatılıyor (ilk çalıştırmada model indirir, biraz sürebilir)...")
    reader = easyocr.Reader(["en"])  # Türk plakaları Latin harf/rakam, 'en' yeterli

    orijinal = cv2.imread(str(PLAKA_GORSEL))
    sol_seritsiz = sol_seridi_kirp(orijinal)
    islenmis = on_isle(sol_seritsiz)
    ikili = otsu_esikleme(islenmis)

    # Birden fazla varyant deniyoruz (renkli ham, gri+kontrast, siyah-beyaz
    # eşiklenmiş), çünkü hangisinin daha iyi sonuç vereceği görüntüden
    # görüntüye değişebilir — hepsini karşılaştırıp en yüksek güvenliyi seçiyoruz.
    denemeler = [
        ("ham (renkli)", reader.readtext(orijinal, allowlist=ALLOWLIST)),
        ("gri+kontrast+buyutulmus (sol serit kirpilmis)", reader.readtext(islenmis, allowlist=ALLOWLIST)),
        ("siyah-beyaz esiklenmis (Otsu)", reader.readtext(ikili, allowlist=ALLOWLIST)),
    ]

    for etiket, sonuclar in denemeler:
        print(f"\n[deneme: {etiket}] {len(sonuclar)} metin bloğu bulundu")
        for _bbox, metin, guven in sonuclar:
            print(f"  Ham OCR metni: '{metin}'  (guven={guven:.2f})")
        birlesik_metin, ortalama_guven = bloklari_birlestir(sonuclar)
        if birlesik_metin:
            print(f"  -> birleştirilmiş (soldan sağa): '{birlesik_metin}'  (ort. guven={ortalama_guven:.2f})")

    en_iyi = en_iyi_sonucu_sec(denemeler)
    if en_iyi is None:
        print("\n[uyari] Hiçbir denemede metin bulunamadı.")
        return

    etiket, birlesik_metin, ortalama_guven = en_iyi
    temiz, gecerli = temizle_ve_dogrula(birlesik_metin)
    durum = "GEÇERLİ TR plaka formatı" if gecerli else "format eşleşmedi (düşük güvenle kaydedilebilir)"
    print(f"\n[SONUÇ] En iyi deneme: '{etiket}' -> '{birlesik_metin}' (ort. guven={ortalama_guven:.2f})")
    print(f"  Temizlenmiş: '{temiz}'  [{durum}]")


if __name__ == "__main__":
    main()
