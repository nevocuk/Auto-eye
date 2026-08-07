"""
Test klasöründeki (Splitter'ın ürettiği images/test + labels/test) TÜM
görselleri modelle tek seferde işleyip, tek bir HTML galeri sayfasında
gösteren araç -- tek tek Model Test'te açıp bakmak yerine, bu sayfayı
kaydırarak hepsine birden göz atabilirsin.

Her görselde:
  - MAVİ kutu  : gerçek (ground-truth) etiket
  - YEŞİL kutu : modelin doğru bulduğu tahmin (gerçek etiketle eşleşen)
  - KIRMIZI kutu: modelin YANLIŞ tahmini (eşleşmeyen sınıf/konum) ya da
                  kaçırdığı (bulunamayan) bir gerçek kutu

Görseller "Yanlış" olanlar en üstte olacak şekilde sıralanır -- sorunlu
örnekleri önce görürsün. Ayrıca sınıf adına göre filtre kutusu var.

KULLANIM: Aşağıdaki AYARLAR bölümünü kendi yollarına göre düzenleyip
çalıştır:  python 09_test_galerisi.py
"""
from pathlib import Path
import re
import html as html_lib

# ============================== AYARLAR ==============================
MODEL_YOLU = r"C:\Users\nvflb\OneDrive\Desktop\otopark\runs\06_08_egitim\weights\best.pt"
TEST_IMG_KLASORU = r"C:\Users\nvflb\OneDrive\Desktop\brave indirilen\compcars\compcars_incele_yolo_full\split\images\test"
TEST_LBL_KLASORU = r"C:\Users\nvflb\OneDrive\Desktop\brave indirilen\compcars\compcars_incele_yolo_full\split\labels\test"
DATA_YAML = r"C:\Users\nvflb\OneDrive\Desktop\brave indirilen\compcars\compcars_incele_yolo_full\split\data.yaml"
CIKTI_KLASORU = r"C:\Users\nvflb\OneDrive\Desktop\brave indirilen\compcars\test_galerisi"

GUVEN_ESIGI = 0.25       # bu güvenin altındaki tahminler yok sayılır
IOU_ESIGI = 0.5          # bir tahmin, gerçek kutuyla en az bu kadar örtüşürse "eşleşti" sayılır
THUMB_GENISLIK = 480     # galerideki küçük resim genişliği (px) -- büyütmek boyutu/süreyi artırır
MAX_GORSEL = None        # None = hepsi, test amaçlı ilk denemede örn. 200 verebilirsin
# =======================================================================

BURASI = Path(__file__).resolve().parent
CIKTI = Path(CIKTI_KLASORU)
CIKTI_GORSEL = CIKTI / "gorseller"


def data_yaml_oku(yol):
    icerik = Path(yol).read_text(encoding="utf-8")
    isim_satirlari = re.findall(r"^\s*(\d+):\s*(.+)$", icerik, re.MULTILINE)
    return {int(i): ad.strip() for i, ad in isim_satirlari}


def iou_hesapla(kutu1, kutu2):
    # kutu: (x1, y1, x2, y2) piksel
    x1 = max(kutu1[0], kutu2[0])
    y1 = max(kutu1[1], kutu2[1])
    x2 = min(kutu1[2], kutu2[2])
    y2 = min(kutu1[3], kutu2[3])
    kesisim = max(0, x2 - x1) * max(0, y2 - y1)
    if kesisim == 0:
        return 0.0
    alan1 = (kutu1[2] - kutu1[0]) * (kutu1[3] - kutu1[1])
    alan2 = (kutu2[2] - kutu2[0]) * (kutu2[3] - kutu2[1])
    birlesim = alan1 + alan2 - kesisim
    return kesisim / birlesim if birlesim > 0 else 0.0


def gt_etiket_oku(yol, genislik, yukseklik):
    kutular = []
    if not Path(yol).exists():
        return kutular
    for satir in Path(yol).read_text(encoding="utf-8").splitlines():
        parcalar = satir.split()
        if len(parcalar) < 5:
            continue
        cid = int(parcalar[0])
        xc, yc, w, h = (float(v) for v in parcalar[1:5])
        x1 = (xc - w / 2) * genislik
        y1 = (yc - h / 2) * yukseklik
        x2 = (xc + w / 2) * genislik
        y2 = (yc + h / 2) * yukseklik
        kutular.append({"cid": cid, "kutu": (x1, y1, x2, y2)})
    return kutular


def main():
    from ultralytics import YOLO
    import cv2

    CIKTI_GORSEL.mkdir(parents=True, exist_ok=True)

    siniflar = data_yaml_oku(DATA_YAML)
    model = YOLO(MODEL_YOLU)

    gorsel_dosyalari = sorted(
        p for p in Path(TEST_IMG_KLASORU).iterdir()
        if p.suffix.lower() in (".jpg", ".jpeg", ".png")
    )
    if MAX_GORSEL:
        gorsel_dosyalari = gorsel_dosyalari[:MAX_GORSEL]

    print(f"Toplam {len(gorsel_dosyalari)} test görseli işlenecek...")

    sonuclar = []  # her biri: dict(dosya_adi, durum, thumb_yolu, ...)
    dogru_sayisi = 0

    for i, gorsel_yolu in enumerate(gorsel_dosyalari):
        img = cv2.imread(str(gorsel_yolu))
        if img is None:
            continue
        yukseklik, genislik = img.shape[:2]

        etiket_yolu = Path(TEST_LBL_KLASORU) / (gorsel_yolu.stem + ".txt")
        gt_kutular = gt_etiket_oku(etiket_yolu, genislik, yukseklik)

        sonuc = model.predict(str(gorsel_yolu), conf=GUVEN_ESIGI, verbose=False)[0]
        tahminler = []
        for kutu in sonuc.boxes:
            cid = int(kutu.cls[0])
            conf = float(kutu.conf[0])
            x1, y1, x2, y2 = (float(v) for v in kutu.xyxy[0])
            tahminler.append({"cid": cid, "conf": conf, "kutu": (x1, y1, x2, y2)})

        # eşleştirme: her gt kutusu için en iyi IoU'lu, aynı class'lı tahmini bul
        gt_bulundu = [False] * len(gt_kutular)
        tahmin_eslesti = [False] * len(tahminler)
        for gi, gt in enumerate(gt_kutular):
            en_iyi_iou, en_iyi_ti = 0.0, -1
            for ti, t in enumerate(tahminler):
                if t["cid"] != gt["cid"] or tahmin_eslesti[ti]:
                    continue
                iou = iou_hesapla(gt["kutu"], t["kutu"])
                if iou > en_iyi_iou:
                    en_iyi_iou, en_iyi_ti = iou, ti
            if en_iyi_iou >= IOU_ESIGI:
                gt_bulundu[gi] = True
                tahmin_eslesti[en_iyi_ti] = True

        goruntu_dogru = all(gt_bulundu) and len(gt_kutular) > 0

        # Kaçırılan (eşleşmeyen) her GT için: sınıf farketmeksizin konumca
        # örtüşen bir tahmin var mı? Varsa bu "kaçırma" değil, muhtemelen
        # SINIF KARIŞIKLIĞI (doğru yerde yanlış sınıf tahmin edilmiş).
        karisiklik_notlari = []
        for gi, gt in enumerate(gt_kutular):
            if gt_bulundu[gi]:
                continue
            for t in tahminler:
                if iou_hesapla(gt["kutu"], t["kutu"]) >= IOU_ESIGI:
                    gt_ad = siniflar.get(gt["cid"], f"sinif_{gt['cid']}")
                    t_ad = siniflar.get(t["cid"], f"sinif_{t['cid']}")
                    karisiklik_notlari.append(f"{gt_ad} yerine {t_ad} (%{t['conf']*100:.0f}) tahmin edilmiş")
                    break

        # Çift tespit kontrolü: iki farklı tahmin kutusu aynı fiziksel
        # nesneyi (sınıf farketmeksizin, yüksek IoU) işaretlemiş mi?
        cift_tespit_var = False
        for a in range(len(tahminler)):
            for b in range(a + 1, len(tahminler)):
                if iou_hesapla(tahminler[a]["kutu"], tahminler[b]["kutu"]) >= 0.6:
                    cift_tespit_var = True
                    break
            if cift_tespit_var:
                break

        # çizim: GT = mavi, eşleşen tahmin = yeşil, eşleşmeyen tahmin/kaçan gt = kırmızı
        cizim = img.copy()
        for gi, gt in enumerate(gt_kutular):
            renk = (255, 130, 0) if not gt_bulundu[gi] else (255, 180, 80)  # (BGR) turuncu tonları -- kaçan daha koyu
            x1, y1, x2, y2 = (int(v) for v in gt["kutu"])
            cv2.rectangle(cizim, (x1, y1), (x2, y2), (255, 0, 0), 2)  # mavi = gerçek
        for ti, t in enumerate(tahminler):
            renk = (0, 200, 0) if tahmin_eslesti[ti] else (0, 0, 255)  # yeşil / kırmızı
            x1, y1, x2, y2 = (int(v) for v in t["kutu"])
            ad = siniflar.get(t["cid"], f"sinif_{t['cid']}")
            cv2.rectangle(cizim, (x1, y1), (x2, y2), renk, 2)
            cv2.putText(cizim, f"{ad} {t['conf']:.2f}", (x1, max(0, y1 - 6)),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.5, renk, 1, cv2.LINE_AA)

        oran = THUMB_GENISLIK / genislik
        thumb = cv2.resize(cizim, (THUMB_GENISLIK, int(yukseklik * oran)))
        thumb_ad = f"{i:05d}_{gorsel_yolu.stem}.jpg"
        cv2.imwrite(str(CIKTI_GORSEL / thumb_ad), thumb, [cv2.IMWRITE_JPEG_QUALITY, 80])

        gt_siniflar = sorted({siniflar.get(g["cid"], "?") for g in gt_kutular})
        tahmin_listesi = [
            {
                "ad": siniflar.get(t["cid"], f"sinif_{t['cid']}"),
                "conf": t["conf"],
                "eslesti": tahmin_eslesti[ti],
            }
            for ti, t in enumerate(tahminler)
        ]
        sonuclar.append({
            "thumb": thumb_ad,
            "durum": "dogru" if goruntu_dogru else "yanlis",
            "gt_sinif": ", ".join(gt_siniflar) if gt_siniflar else "(etiketsiz)",
            "tahmin_sayisi": len(tahminler),
            "gt_sayisi": len(gt_kutular),
            "tahminler": tahmin_listesi,
            "karisiklik": karisiklik_notlari,
            "cift_tespit": cift_tespit_var,
        })
        if goruntu_dogru:
            dogru_sayisi += 1

        if (i + 1) % 200 == 0:
            print(f"  {i + 1}/{len(gorsel_dosyalari)} işlendi...")

    # yanlışlar üstte olacak şekilde sırala
    sonuclar.sort(key=lambda s: (s["durum"] != "yanlis", s["gt_sinif"]))

    toplam = len(sonuclar)
    oran = (dogru_sayisi / toplam * 100) if toplam else 0

    kartlar = []
    for s in sonuclar:
        renk_sinif = "kart-dogru" if s["durum"] == "dogru" else "kart-yanlis"
        etiket = "DOĞRU" if s["durum"] == "dogru" else "YANLIŞ/EKSİK"

        tahmin_satirlari = "".join(
            f'<div class="tahmin {"t-ok" if t["eslesti"] else "t-kotu"}">'
            f'{"✓" if t["eslesti"] else "✗"} {html_lib.escape(t["ad"])} (%{t["conf"]*100:.0f})</div>'
            for t in s["tahminler"]
        ) or '<div class="tahmin t-kotu">(hiç tahmin yok)</div>'

        uyarilar = ""
        if s["karisiklik"]:
            uyarilar += "".join(
                f'<div class="uyari">⚠ {html_lib.escape(n)}</div>' for n in s["karisiklik"]
            )
        if s["cift_tespit"]:
            uyarilar += '<div class="uyari">⚠ Olası çift tespit (aynı araca 2 örtüşen kutu)</div>'

        kartlar.append(f"""
        <div class="kart {renk_sinif}" data-sinif="{html_lib.escape(s['gt_sinif'].lower())}">
          <img loading="lazy" src="gorseller/{s['thumb']}">
          <div class="bilgi">
            <span class="durum">{etiket}</span>
            <div>Gerçek: {html_lib.escape(s['gt_sinif'])}</div>
            <div>GT kutu: {s['gt_sayisi']} | Tahmin: {s['tahmin_sayisi']}</div>
            <div class="tahmin-listesi">{tahmin_satirlari}</div>
            {uyarilar}
          </div>
        </div>""")

    sayfa = f"""<!DOCTYPE html>
<html lang="tr"><head><meta charset="UTF-8"><title>Test Galerisi</title>
<style>
body {{ background:#181818; color:#eee; font-family:sans-serif; margin:0; padding:20px; }}
h1 {{ margin-top:0; }}
.ozet {{ margin-bottom:16px; font-size:15px; }}
.ozet b {{ color:#4caf50; }}
input {{ padding:8px; width:300px; font-size:14px; margin-bottom:16px; }}
.grid {{ display:flex; flex-wrap:wrap; gap:14px; }}
.kart {{ width:{THUMB_GENISLIK}px; border:3px solid #444; border-radius:6px; overflow:hidden; background:#222; }}
.kart img {{ width:100%; display:block; }}
.kart-dogru {{ border-color:#4caf50; }}
.kart-yanlis {{ border-color:#e53935; }}
.bilgi {{ padding:8px; font-size:13px; }}
.durum {{ font-weight:bold; }}
.kart-dogru .durum {{ color:#4caf50; }}
.kart-yanlis .durum {{ color:#e53935; }}
.tahmin-listesi {{ margin-top:6px; border-top:1px solid #444; padding-top:6px; }}
.tahmin {{ font-size:12px; }}
.t-ok {{ color:#4caf50; }}
.t-kotu {{ color:#ff9800; }}
.uyari {{ color:#ffca28; font-size:12px; margin-top:4px; }}
.gizli {{ display:none; }}
</style></head>
<body>
<h1>Test Galerisi</h1>
<div class="ozet">Toplam <b>{toplam}</b> görsel &mdash; Doğru: <b>{dogru_sayisi}</b> (%{oran:.1f}) &mdash; Yanlış/Eksik: <b>{toplam - dogru_sayisi}</b>
<br><small>Mavi kutu = gerçek etiket. Yeşil = doğru tahmin. Kırmızı = eşleşmeyen tahmin/kaçan gerçek kutu.
Her kartın altında modelin TÜM tahminleri (✓ eşleşen / ✗ eşleşmeyen) ve varsa uyarılar (sınıf karışıklığı, çift tespit) metin olarak listelenir.
<br><b>Önemli not:</b> CompCars kaynak verisi bir fotoğrafta birden fazla araç görünse bile SADECE BİR aracı etiketler
(diğer fotoğraflardaki gibi vitrin/galeri sahnelerinde). Bu yüzden "YANLIŞ/EKSİK" kartlarının bir kısmında model aslında
diğer (etiketlenmemiş) araçları da doğru bulmuş olabilir -- bunlar gerçek hata değildir. Asıl dikkat etmen gereken,
✗ işaretli tahminlerin sınıf isminin gerçek sınıfa YAKIN/BENZER mi olduğu (gerçek karışıklık) yoksa "⚠ Olası çift tespit"
uyarısı olan kartlar (aynı arabaya 2 farklı kutu/sınıf atanması).</small></div>
<input id="filtre" placeholder="sınıf adına göre filtrele (ör: egea)...">
<div class="grid" id="grid">{''.join(kartlar)}</div>
<script>
document.getElementById('filtre').addEventListener('input', (e) => {{
  const q = e.target.value.toLowerCase();
  document.querySelectorAll('.kart').forEach((k) => {{
    k.classList.toggle('gizli', q && !k.dataset.sinif.includes(q));
  }});
}});
</script>
</body></html>"""

    (CIKTI / "_galeri.html").write_text(sayfa, encoding="utf-8")
    print(f"\n=== BİTTİ ===")
    print(f"Toplam: {toplam} | Doğru: {dogru_sayisi} (%{oran:.1f}) | Yanlış/Eksik: {toplam - dogru_sayisi}")
    print(f"Galeri: {CIKTI / '_galeri.html'}")


if __name__ == "__main__":
    main()
