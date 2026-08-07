"""
CompCars -> otopark YOLO veri seti aktarim scripti (Bilesen 3: marka/model).

Ne yapar:
  - CompCars'ta Renault Clio (model_id=793) klasorunden, yil klasorune gore
    clio3 (2005-2012 yillari) / clio4 (2012-2019 yillari) ayrimi yapar.
  - CompCars label formatini (satir1: acidan bagimsiz viewpoint, satir3:
    piksel bbox "x1 y1 x2 y2") YOLO formatina (class x_center y_center w h,
    hepsi 0-1 normalize) cevirir. Goruntu genislik/yuksekligi PIL ile okunur.
  - Donusturulen gorseli + etiketi otopark/veri/images ve veri/labels
    klasorlerine, "compcars_<class>_<orijinal_ad>.jpg/.txt" adiyla kopyalar
    (mevcut kullanicinin kendi verisiyle CARPISMAMASI icin bu on ek kullanildi).
  - fiat_egea CompCars'ta YOK (veri seti 2015 oncesi toplanmis, Egea 2015
    sonrasi) -- bu class icin CompCars'tan hicbir sey aktarilmiyor, kullanici
    kendi (sahibinden vb.) gorsellerini kendi arayuzunde elle etiketlemeli.

Calistirma:
    python 08_compcars_import.py

Guvenlik: bu script SADECE COMPCARS_KOK altindan okur, otopark/veri altina
sadece EKLER (var olan dosyalara dokunmaz, ayni isimde dosya varsa atlar).
"""
from pathlib import Path
from PIL import Image

COMPCARS_KOK = Path("/sessions/charming-laughing-meitner/mnt/compcars/CompCars/data/data")
OTOPARK_VERI = Path("/sessions/charming-laughing-meitner/mnt/otopark/veri")

HEDEF_IMAGES = OTOPARK_VERI / "images"
HEDEF_LABELS = OTOPARK_VERI / "labels"

# data.yaml'daki sinif id'leri (mevcut dosyadan alindi):
#   0: renault_clio3
#   1: renault_clio4
#   2: fiat_egea   (CompCars'ta yok, bu scriptte kullanilmiyor)
CLIO_MODEL_ID = 793
CLIO_MAKE_ID = 160

# yil -> (class_id, class_adi) esleme (2011-2012 CompCars'ta hic yok, o yuzden
# gecis/belirsizlik donemi sorun cikarmiyor)
YIL_SINIF_ESLEME = {
    "2009": (0, "renault_clio3"),
    "2010": (0, "renault_clio3"),
    "2013": (1, "renault_clio4"),
    "2014": (1, "renault_clio4"),
}


def compcars_labeli_yolo_formatina_cevir(label_yolu: Path, resim_genislik: int, resim_yukseklik: int, sinif_id: int):
    """CompCars label dosyasini (viewpoint + piksel bbox) okuyup YOLO satirina cevirir.
    Donen deger: 'class xc yc w h' string'i, ya da None (label bozuksa/eksikse)."""
    satirlar = [s.strip() for s in label_yolu.read_text(encoding="utf-8").splitlines() if s.strip()]
    if len(satirlar) < 3:
        return None
    try:
        x1, y1, x2, y2 = (float(v) for v in satirlar[2].split())
    except (ValueError, IndexError):
        return None
    if x2 <= x1 or y2 <= y1:
        return None
    xc = (x1 + x2) / 2 / resim_genislik
    yc = (y1 + y2) / 2 / resim_yukseklik
    w = (x2 - x1) / resim_genislik
    h = (y2 - y1) / resim_yukseklik
    # sinir kontrolu -- 0-1 disina tasan (kirpilmis bbox) varsa kirp
    xc, yc, w, h = (max(0.0, min(1.0, v)) for v in (xc, yc, w, h))
    return f"{sinif_id} {xc:.6f} {yc:.6f} {w:.6f} {h:.6f}"


def main():
    HEDEF_IMAGES.mkdir(parents=True, exist_ok=True)
    HEDEF_LABELS.mkdir(parents=True, exist_ok=True)

    goruntu_kok = COMPCARS_KOK / "image" / str(CLIO_MAKE_ID) / str(CLIO_MODEL_ID)
    label_kok = COMPCARS_KOK / "label" / str(CLIO_MAKE_ID) / str(CLIO_MODEL_ID)

    if not goruntu_kok.exists():
        print(f"HATA: CompCars klasoru bulunamadi: {goruntu_kok}")
        return

    toplam_eklendi = 0
    toplam_atlandi_var = 0
    toplam_atlandi_bozuk = 0
    sinif_sayaci = {}

    for yil_klasoru in sorted(goruntu_kok.iterdir()):
        if not yil_klasoru.is_dir():
            continue
        yil = yil_klasoru.name
        if yil not in YIL_SINIF_ESLEME:
            print(f"  [atlandi] yil={yil} -> eslesme yok (sinif belirsiz)")
            continue
        sinif_id, sinif_adi = YIL_SINIF_ESLEME[yil]

        for gorsel_yolu in sorted(yil_klasoru.glob("*.jpg")):
            hedef_ad = f"compcars_{sinif_adi}_{gorsel_yolu.stem}"
            hedef_gorsel = HEDEF_IMAGES / f"{hedef_ad}.jpg"
            hedef_etiket = HEDEF_LABELS / f"{hedef_ad}.txt"

            if hedef_gorsel.exists() or hedef_etiket.exists():
                toplam_atlandi_var += 1
                continue

            label_yolu = label_kok / yil / f"{gorsel_yolu.stem}.txt"
            if not label_yolu.exists():
                toplam_atlandi_bozuk += 1
                continue

            try:
                with Image.open(gorsel_yolu) as im:
                    genislik, yukseklik = im.size
            except Exception as e:
                print(f"  [atlandi] gorsel acilamadi: {gorsel_yolu.name} ({e})")
                toplam_atlandi_bozuk += 1
                continue

            yolo_satiri = compcars_labeli_yolo_formatina_cevir(label_yolu, genislik, yukseklik, sinif_id)
            if yolo_satiri is None:
                toplam_atlandi_bozuk += 1
                continue

            # kopyala (gercek dosya kopyasi -- symlink degil, kullanicinin
            # arayuzu ve egitim scripti duz dosya bekliyor)
            hedef_gorsel.write_bytes(gorsel_yolu.read_bytes())
            hedef_etiket.write_text(yolo_satiri + "\n", encoding="utf-8")

            toplam_eklendi += 1
            sinif_sayaci[sinif_adi] = sinif_sayaci.get(sinif_adi, 0) + 1

    print("\n=== CompCars aktarim ozeti ===")
    print(f"Eklenen gorsel+etiket cifti : {toplam_eklendi}")
    for sinif_adi, sayi in sinif_sayaci.items():
        print(f"  - {sinif_adi}: {sayi}")
    print(f"Atlandi (zaten vardi)       : {toplam_atlandi_var}")
    print(f"Atlandi (label/gorsel bozuk): {toplam_atlandi_bozuk}")
    print(f"\nNot: fiat_egea icin CompCars'ta veri yok -- bu class icin kendi")
    print(f"gorsellerini (sahibinden vb.) kendi arayuzunde elle etiketlemen gerekiyor.")


if __name__ == "__main__":
    main()
