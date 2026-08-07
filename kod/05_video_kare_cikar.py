"""
Yardımcı script: Bir videodan seyrek aralıklarla kare (frame) çıkarma

Ne yapar:
  Elindeki bir video dosyasından (vlog, dashcam, kendi çektiğin video vb.)
  saniyede belirli sayıda kare çıkarıp görsel (.jpg) olarak kaydeder. Amaç:
  video kaynağından Ön-Etiketleme/Etiketleme arayüzüne girecek ham görselleri
  üretmek.

  fps=1 gibi seyrek bir değer kullanıyoruz (varsayılan) -- saniyede TÜM
  kareleri (örn. 30 fps) alırsak art arda gelen kareler neredeyse birebir
  aynı görüntü olur (aynı araç, aynı açı, göz kırpma kadar fark), bu hem
  gereksiz emek hem de yanıltıcı "çeşitlilik" demek (aslında aynı görüntüyü
  defalarca görmüş oluyorsun). Saniyede 1 kare (ya da daha seyrek, örn.
  0.5 = 2 saniyede 1 kare) gerçek çeşitlilik için yeterli ve yönetilebilir.

  Ayrı bir ffmpeg kurulumuna GEREK YOK: etiketleme_arayuzu/requirements.txt
  içindeki "imageio-ffmpeg" paketi zaten kendi içinde bir ffmpeg programı
  taşıyor (Model Test'in video modunda da bunu kullanıyoruz) -- bu script
  onu kullanıyor.

Nasıl kullanılır:
  python kod/05_video_kare_cikar.py <video_yolu> <cikti_klasoru> [fps]

  Örnek (varsayılan fps=1, saniyede 1 kare):
    python kod/05_video_kare_cikar.py "C:\\Users\\nvflb\\Downloads\\video.mp4" veri/ham_kareler

  Örnek (daha seyrek, 2 saniyede 1 kare):
    python kod/05_video_kare_cikar.py "C:\\Users\\nvflb\\Downloads\\video.mp4" veri/ham_kareler 0.5

  Çıktı: <cikti_klasoru>/<video_adi>_kare_0001.jpg, _0002.jpg, ...
  (video adını dosya adına ekliyoruz -- birden fazla videodan kare
  çıkarınca dosya adları çakışmasın diye.)

  Sonraki adım: bu klasörü Ön-Etiketleme arayüzüne ver (hepsi aynı class'a
  aitse), sonra Etiketleme arayüzünden açıp kontrol et.
"""

import subprocess
import sys
from pathlib import Path


def kare_cikar(video_yolu: str, cikti_klasoru: str, fps: float = 1.0):
    try:
        import imageio_ffmpeg
    except ImportError:
        print("[HATA] imageio-ffmpeg kurulu değil. Kurmak için:")
        print("  pip install imageio-ffmpeg")
        sys.exit(1)

    video_yolu = Path(video_yolu)
    if not video_yolu.exists():
        print(f"[HATA] Video bulunamadı: {video_yolu}")
        sys.exit(1)

    cikti_klasoru = Path(cikti_klasoru)
    cikti_klasoru.mkdir(parents=True, exist_ok=True)

    video_adi = video_yolu.stem
    desen = str(cikti_klasoru / f"{video_adi}_kare_%04d.jpg")

    ffmpeg_yolu = imageio_ffmpeg.get_ffmpeg_exe()
    komut = [
        ffmpeg_yolu, "-y",
        "-i", str(video_yolu),
        "-vf", f"fps={fps}",
        "-q:v", "2",  # jpg kalitesi (2 = yüksek kalite, düşük sayı = daha kaliteli)
        desen,
    ]

    print(f"[bilgi] Video: {video_yolu}")
    print(f"[bilgi] Çıktı: {cikti_klasoru}  (fps={fps})")
    sonuc = subprocess.run(komut, capture_output=True, text=True)

    if sonuc.returncode != 0:
        print("[HATA] ffmpeg başarısız oldu:")
        print(sonuc.stderr[-2000:])  # son kısmı yeter, çok uzun olabiliyor
        sys.exit(1)

    uretilen = sorted(cikti_klasoru.glob(f"{video_adi}_kare_*.jpg"))
    print(f"[bilgi] {len(uretilen)} kare üretildi -> {cikti_klasoru}")


if __name__ == "__main__":
    if len(sys.argv) < 3:
        print("Kullanım: python kod/05_video_kare_cikar.py <video_yolu> <cikti_klasoru> [fps]")
        print("Örnek:    python kod/05_video_kare_cikar.py video.mp4 veri/ham_kareler 1")
        sys.exit(1)

    video_yolu = sys.argv[1]
    cikti_klasoru = sys.argv[2]
    fps = float(sys.argv[3]) if len(sys.argv) > 3 else 1.0

    kare_cikar(video_yolu, cikti_klasoru, fps)
