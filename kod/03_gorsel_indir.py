"""
Adım 4 yardımcı script: Sınıf başına toplu görsel indirme

Ne yapar:
  Her sınıf için (renault_clio3, renault_clio4, fiat_egea) bir
  metin dosyasındaki URL listesini okuyup görselleri indirir, otomatik
  olarak sıralı isimlerle (0001.jpg, 0002.jpg, ...) veri/<sinif>/ altına
  kaydeder.

Neden URL listesi kendim toplamıyorum / otomatik "stok görsel scrape"
etmiyorum: telif hakkı nedeniyle rastgele bir siteden toplu görsel çekmek
riskli. Bunun yerine SEN, serbest lisanslı kaynaklardan (aşağıya bak)
URL'leri topluyorsun, ben sadece indirme/isimlendirme işini otomatikleştiriyorum.

Önerilen serbest/telifsiz kaynaklar:
  - Wikimedia Commons: https://commons.wikimedia.org
      (örn. "Renault Clio II" ya da "Fiat Egea" diye ara, kategori
      sayfasındaki görsellere sağ tık -> "resim adresini kopyala")
  - Openverse: https://openverse.org (CC lisanslı görsel arama motoru)
  - Kendi çektiğin fotoğraflar (en sağlıklısı, telif sorunu yok)

Nasıl kullanılır:
  1) Her sınıf için bir URL listesi dosyası oluştur, örn:
       veri/renault_clio3_urls.txt
     İçine her satıra bir görsel URL'i yapıştır (http://... veya https://...)
  2) python kod/03_gorsel_indir.py renault_clio3
     (bu, veri/renault_clio3_urls.txt dosyasını okuyup
      veri/renault_clio3/ klasörüne indirir)
"""

import sys
import urllib.request
from pathlib import Path

PROJE_KOK = Path(__file__).resolve().parent.parent
VERI_KLASOR = PROJE_KOK / "veri"

BASLIKLAR = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) otopark-projesi-egitim-amacli"
}


def indir(sinif_adi: str):
    url_dosyasi = VERI_KLASOR / f"{sinif_adi}_urls.txt"
    hedef_klasor = VERI_KLASOR / sinif_adi

    if not url_dosyasi.exists():
        print(f"[HATA] URL dosyası bulunamadı: {url_dosyasi}")
        print("Önce bu dosyayı oluşturup her satıra bir görsel URL'i yapıştır.")
        return

    hedef_klasor.mkdir(parents=True, exist_ok=True)

    with open(url_dosyasi, "r", encoding="utf-8") as f:
        urller = [satir.strip() for satir in f if satir.strip() and not satir.startswith("#")]

    print(f"[bilgi] {len(urller)} URL bulundu, indiriliyor -> {hedef_klasor}")

    basarili = 0
    for i, url in enumerate(urller, start=1):
        uzanti = ".jpg"
        for aday in (".jpg", ".jpeg", ".png", ".webp"):
            if aday in url.lower():
                uzanti = aday
                break

        hedef_dosya = hedef_klasor / f"{i:04d}{uzanti}"
        try:
            istek = urllib.request.Request(url, headers=BASLIKLAR)
            with urllib.request.urlopen(istek, timeout=15) as yanit:
                icerik = yanit.read()
            with open(hedef_dosya, "wb") as f:
                f.write(icerik)
            print(f"  [{i}/{len(urller)}] OK -> {hedef_dosya.name}")
            basarili += 1
        except Exception as e:
            print(f"  [{i}/{len(urller)}] HATA ({url}): {e}")

    print(f"\n[bilgi] {basarili}/{len(urller)} görsel indirildi: {hedef_klasor}")


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Kullanım: python kod/03_gorsel_indir.py <sinif_adi>")
        print("Örnek:    python kod/03_gorsel_indir.py renault_clio3")
        sys.exit(1)

    indir(sys.argv[1])
