"""
Adım 4 -> Adım 5 geçişi: Sınıf klasörlerini eğitime hazır tek yapıya birleştir

Ne yapar:
  Etiketleme sırasında her sınıfı ayrı klasörde topladık — bu klasörler
  `otopark/veri/` içinde olabilir, YA DA bilgisayarındaki BAŞKA bir yerde
  (örn. `Masaüstü/brave indirilen/clio3` gibi) olabilir. Bu script iki
  duruma da uyum sağlıyor:

  1) Argümansız çalıştırırsan: `veri/` klasörünün DOĞRUDAN İÇİNDEKİ tüm
     alt klasörleri otomatik tarar (eski davranış, veri/ içindeyse yeter).
  2) Argüman olarak klasör yolları verirsen (bilgisayarındaki HERHANGİ bir
     konumdan): SADECE o verdiğin klasörleri işler. Bunu, sınıf
     klasörlerin `veri/` klasörünün dışında bir yerdeyse kullan.

  Her iki durumda da: etiketleme arayüzünün kullandığı AYNI mantıkla
  etiket klasörünü bulur (önce `<klasör>/../labels/<klasör_adı>/`, yoksa
  eski düz `<klasör>/../labels/` konumuna bakar) ve SADECE ETİKETLENMİŞ
  (dolu bir .txt'si olan) görselleri, sınıf adı ön ekiyle (çakışma
  olmasın diye) `veri/images/` ve `veri/labels/` içine kopyalar.

  Örnek: .../clio3/x5_123.jpg + .../labels/clio3/x5_123.txt
      -> veri/images/clio3_x5_123.jpg + veri/labels/clio3_x5_123.txt

Neden "kopyala" (taşımıyor): orijinal sınıf klasörlerini bozmuyoruz —
  etiketlemeye devam edip script'i tekrar çalıştırabilirsin, sadece yeni
  eklenenler kopyalanır (zaten var olanlar atlanır).

Nasıl çalıştırılır:
  # veri/ İÇİNDEKİ sınıf klasörleri için (eski davranış):
  python kod/04_veri_birlestir.py

  # veri/ DIŞINDA, bilgisayarının başka bir yerindeki klasörler için:
  python kod/04_veri_birlestir.py "C:\\Users\\nvflb\\OneDrive\\Desktop\\brave indirilen\\clio3" "C:\\Users\\nvflb\\OneDrive\\Desktop\\brave indirilen\\clio4" "C:\\Users\\nvflb\\OneDrive\\Desktop\\brave indirilen\\egea"
"""

import sys
import shutil
from pathlib import Path

PROJE_KOK = Path(__file__).resolve().parent.parent
VERI_KLASOR = PROJE_KOK / "veri"

HEDEF_GORSEL_KLASOR = VERI_KLASOR / "images"
HEDEF_ETIKET_KLASOR = VERI_KLASOR / "labels"

# Birleştirme dışında tutulacak (rezerve) klasör adları (veri/ içini
# otomatik tararken bu isimleri sınıf klasörü SANMA)
HARIC_TUTULAN = {"images", "labels"}
GORSEL_UZANTILARI = {".jpg", ".jpeg", ".png", ".bmp", ".webp"}


def sinif_klasorlerini_bul_veri_icinde():
    """veri/ altındaki, 'images'/'labels' olmayan tüm alt klasörleri
    (yani sınıf başına toplama klasörlerini) bulur."""
    return [
        p for p in VERI_KLASOR.iterdir()
        if p.is_dir() and p.name not in HARIC_TUTULAN
    ]


def etiket_klasorunu_bul(gorsel_klasoru: Path) -> Path:
    """Etiketleme arayüzüyle (app.py) AYNI mantık: önce klasör adına özel
    yeni konum, yoksa eski düz 'labels' konumu."""
    if gorsel_klasoru.name == "images":
        return gorsel_klasoru.parent / "labels"
    return gorsel_klasoru.parent / "labels" / gorsel_klasoru.name


def eski_flat_etiket_klasoru(gorsel_klasoru: Path) -> Path:
    return gorsel_klasoru.parent / "labels"


def etiket_dosyasini_bul(gorsel: Path, yeni_etiket_klasoru: Path, eski_etiket_klasoru: Path) -> Path | None:
    """Önce yeni (klasör-adına-özel) konumda, yoksa eski düz konumda arar."""
    yeni = yeni_etiket_klasoru / (gorsel.stem + ".txt")
    if yeni.exists() and yeni.stat().st_size > 0:
        return yeni
    eski = eski_etiket_klasoru / (gorsel.stem + ".txt")
    if eski.exists() and eski.stat().st_size > 0:
        return eski
    return None


def sinif_klasorunu_isle(sinif_klasoru: Path):
    sinif_adi = sinif_klasoru.name
    yeni_etiket_klasoru = etiket_klasorunu_bul(sinif_klasoru)
    eski_etiket_klasoru = eski_flat_etiket_klasoru(sinif_klasoru)

    gorseller = [
        p for p in sinif_klasoru.iterdir()
        if p.suffix.lower() in GORSEL_UZANTILARI
    ]

    kopyalanan = 0
    etiketsiz = 0
    zaten_var = 0

    for gorsel in gorseller:
        kaynak_etiket = etiket_dosyasini_bul(gorsel, yeni_etiket_klasoru, eski_etiket_klasoru)
        if kaynak_etiket is None:
            etiketsiz += 1
            continue

        yeni_ad = f"{sinif_adi}_{gorsel.name}"
        yeni_etiket_ad = f"{sinif_adi}_{gorsel.stem}.txt"

        hedef_gorsel = HEDEF_GORSEL_KLASOR / yeni_ad
        hedef_etiket = HEDEF_ETIKET_KLASOR / yeni_etiket_ad

        if hedef_gorsel.exists() and hedef_etiket.exists():
            zaten_var += 1
            continue

        shutil.copy2(gorsel, hedef_gorsel)
        shutil.copy2(kaynak_etiket, hedef_etiket)
        kopyalanan += 1

    print(f"[{sinif_adi}] (kaynak: {sinif_klasoru})")
    print(f"   toplam={len(gorseller)}  kopyalanan={kopyalanan}  "
          f"zaten_var={zaten_var}  etiketsiz_atlandi={etiketsiz}")

    return kopyalanan, zaten_var, etiketsiz



def main():
    HEDEF_GORSEL_KLASOR.mkdir(parents=True, exist_ok=True)
    HEDEF_ETIKET_KLASOR.mkdir(parents=True, exist_ok=True)

    if len(sys.argv) > 1:
        sinif_klasorleri = [Path(p) for p in sys.argv[1:]]
        for k in sinif_klasorleri:
            if not k.is_dir():
                print(f"[HATA] Klasör bulunamadı: {k}")
                return
    else:
        sinif_klasorleri = sinif_klasorlerini_bul_veri_icinde()

    if not sinif_klasorleri:
        print("[uyari] İşlenecek sınıf klasörü bulunamadı.")
        return

    toplam_kopyalanan = 0
    toplam_atlanan_etiketsiz = 0
    toplam_zaten_var = 0

    for sinif_klasoru in sinif_klasorleri:
        kopyalanan, zaten_var, etiketsiz = sinif_klasorunu_isle(sinif_klasoru)
        toplam_kopyalanan += kopyalanan
        toplam_zaten_var += zaten_var
        toplam_atlanan_etiketsiz += etiketsiz

    print(f"\n[ÖZET] Yeni kopyalanan: {toplam_kopyalanan}  "
          f"Zaten mevcuttu: {toplam_zaten_var}  "
          f"Etiketsiz (atlandı): {toplam_atlanan_etiketsiz}")
    print(f"Eğitime hazır klasör: {HEDEF_GORSEL_KLASOR}")


if __name__ == "__main__":
    main()
