"""KURULUM.bat tarafından çağrılır -- pip install'dan ÖNCE hangi
kütüphanelerin zaten kurulu olduğunu kontrol edip ekrana yazar.
pip zaten kurulu bir paketi tekrar indirmez ("Requirement already
satisfied" deyip atlar), ama bunu kullanıcıya açıkça göstermek ve
torch için GPU sorusunu gereksiz yere sormamak için ayrı bir kontrol.

Çıktı formatı: "MODUL: OK" ya da "MODUL: EKSIK" -- KURULUM.bat bu
satırları okuyup ona göre davranıyor.

Çalıştırma: python _kurulum_kontrol.py
"""
import importlib

# (gösterilecek isim, import edilecek modül adı)
MODULLER = [
    ("flask", "flask"),
    ("pyyaml", "yaml"),
    ("pywebview", "webview"),
    ("Pillow", "PIL"),
    ("numpy", "numpy"),
    ("ultralytics", "ultralytics"),
    ("opencv-python", "cv2"),
    ("imageio-ffmpeg", "imageio_ffmpeg"),
    ("fast-plate-ocr", "fast_plate_ocr"),
    ("pillow-heif", "pillow_heif"),
    ("torch", "torch"),
    ("torchvision", "torchvision"),
]

if __name__ == "__main__":
    for gosterim_adi, modul_adi in MODULLER:
        try:
            importlib.import_module(modul_adi)
            print(f"{gosterim_adi}: OK")
        except Exception:
            print(f"{gosterim_adi}: EKSIK")
