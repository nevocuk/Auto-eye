"""
Detect Etiketleme Arayüzü — Backend (Flask)

Ne yapar:
  Yerel bir web sunucusu açar (http://localhost:5000). Tarayıcıda açtığın
  arayüzden bir görsel klasörü (+ opsiyonel etiket klasörü, opsiyonel
  data.yaml) seçip, görseller üzerinde fare ile kutu (bounding box)
  çizerek YOLO detect formatında etiketleme yapmanı sağlar.

Neden yerel sunucu (Flask) + tarayıcı arayüzü:
  Bilgisayarındaki KEYFİ bir klasörü okuyup yazabilmemiz lazım (sadece
  otopark projesi değil, ileride başka veri setleri için de kullanılabilsin
  diye "evrensel" olması isteniyor). Tarayıcı güvenlik kısıtları rastgele
  bir klasöre erişime izin vermez, bu yüzden küçük bir yerel sunucu
  (senin bilgisayarında çalışan Python programı) dosya okuma/yazmayı
  yapıyor, tarayıcı sadece arayüzü gösteriyor.

İki girdi modu (nevfel.txt'deki gereksinim):
  1) Sadece görsel klasörü (+ data.yaml veya elle yazılan sınıf listesi)
     -> etiket klasörü henüz yoksa oluşturulur, sıfırdan etiketlersin.
  2) Görsel + etiket klasörü birlikte (var olan etiketler)
     -> mevcut etiketler yüklenir, düzenleyebilir/devam edebilirsin.
  İkisi de aynı mantıkla çalışıyor: etiket klasörü verilmezse, görsel
  klasörünün yanında "labels" adlı klasör varsayılıyor (YOLO'nun standart
  images/ + labels/ kardeş klasör kuralı) — bu da otopark'ın kendi
  veri/images + veri/labels yapısıyla doğrudan uyumlu.

Nasıl çalıştırılır:
  pip install -r requirements.txt   (bu klasörün içinde)
  python app.py
  -> Tarayıcı açılmaz, doğrudan native bir uygulama penceresi açılır
     (pywebview ile). Arka planda hâlâ bir Flask sunucusu çalışıyor
     (http://127.0.0.1:5000), ama kullanıcı bunu görmüyor/uğraşmıyor —
     sadece uygulama penceresini görüyor.
"""

import io
import json
import random
import re
import shutil
import subprocess
import sys
import threading
import traceback
from collections import defaultdict
from pathlib import Path

import numpy as np
import webview

# Birden fazla araç (Ön-Etiketleme, Model Test, Fusion, Sürekli İzleme) kendi
# YOLO/OCR model önbelleğini "içindeyse kullan, değilse yükle" deseniyle
# yönetiyor. Bu desen kilitsizken iki istek (örn. kullanıcı Test ve Fusion'ı
# arka arkaya hızlı tetiklerse) aynı anda "önbellekte yok" görüp aynı modeli
# iki kez yükleyebilir ya da biri .clear() çağırırken diğeri okuyabilir.
# Model yükleme nadir olduğu için tek paylaşılan bir kilit yeterli (ayrı
# kilitler eklemek karmaşıklığı artırır, kazanç sağlamaz).
MODEL_ONBELLEK_KILIDI = threading.Lock()
import yaml
from flask import Flask, jsonify, request, send_from_directory, render_template, Response
from PIL import Image, ImageEnhance, ImageFilter

app = Flask(__name__)

# ============================================================
# GELİŞMİŞ (OtoGöz'e ÖZEL) ÖZELLİKLER AYARI
# Bu klasör, nevfel.txt'nin istediği EVRENSEL 5 araçlık setin (Etiketleme,
# Splitter, Augment, Eğitim, Test) bir kopyası -- Ön-Etiketleme/Kare Çıkar/
# Veri Birleştir de evrensel (herhangi bir YOLO projesinde işe yarar), ama
# "Fusion" (plaka + marka/model birleştirme) doğrudan OtoGöz projesine özel,
# başka birinin arayüzünde bir anlamı yok. Bu yüzden burada VARSAYILAN
# OLARAK KAPALI -- hub'da görünmüyor, sayfasına gidilirse "kapalı" notu
# gösteriliyor. Tek bir ayar dosyasıyla (aşağıdaki) tek tuşla açılabiliyor.
# Orijinal otopark/etiketleme_arayuzu projesinde BU MEKANİZMA YOK -- orada
# Fusion her zaman açık (proje doğrudan OtoGöz için). (2026-08-04)
# ============================================================
AYARLAR_DOSYASI = Path(__file__).resolve().parent / "ayarlar.json"
AYARLAR_VARSAYILAN = {"gelismis_ozellikler_acik": False}


def _ayarlari_oku() -> dict:
    if not AYARLAR_DOSYASI.exists():
        return dict(AYARLAR_VARSAYILAN)
    try:
        with open(AYARLAR_DOSYASI, "r", encoding="utf-8") as f:
            veri = json.load(f)
        return {**AYARLAR_VARSAYILAN, **veri}
    except Exception:
        return dict(AYARLAR_VARSAYILAN)


def _ayarlari_kaydet(veri: dict):
    with open(AYARLAR_DOSYASI, "w", encoding="utf-8") as f:
        json.dump(veri, f, ensure_ascii=False, indent=2)


@app.before_request
def _fusion_api_kapaliysa_engelle():
    # /fusion sayfası kapalıyken kullanıcı arayüzden bu API'lere hiç
    # ulaşamaz zaten (buton yok) -- ama biri doğrudan API'yi çağırırsa
    # (örn. eski bir sekme açık kalmışsa) tutarlı davranmak için burada
    # da aynı ayarı kontrol ediyoruz.
    if request.path.startswith("/api/fusion/") and not _ayarlari_oku()["gelismis_ozellikler_acik"]:
        return jsonify({"hata": "Fusion özelliği şu an kapalı. Ana sayfadan 'Gelişmiş özellikler' anahtarını açman gerekiyor."}), 403


@app.route("/api/ayarlar", methods=["GET"])
def ayarlari_getir():
    return jsonify(_ayarlari_oku())


@app.route("/api/ayarlar", methods=["POST"])
def ayarlari_guncelle():
    veri = request.get_json() or {}
    mevcut = _ayarlari_oku()
    if "gelismis_ozellikler_acik" in veri:
        mevcut["gelismis_ozellikler_acik"] = bool(veri["gelismis_ozellikler_acik"])
    _ayarlari_kaydet(mevcut)
    return jsonify(mevcut)


GORSEL_UZANTILARI = {".jpg", ".jpeg", ".png", ".bmp", ".webp"}

# Basit, tek kullanıcılı yerel bir araç olduğu için durumu bellekte
# (global bir sözlükte) tutuyoruz — gerçek bir çok kullanıcılı web
# uygulaması olsaydı bu doğru olmazdı, ama burada tek kişi (sen),
# tek bilgisayarda çalıştırdığın için yeterli ve basit.
DURUM = {
    "gorsel_klasoru": None,
    "etiket_klasoru": None,
    "data_yaml_yolu": None,
    "siniflar": [],
    "gorseller": [],
    # "bayrakli" görseller: "bunu daha sonra tekrar kontrol et" için elle
    # işaretlenen görseller (YOLO etiketiyle karışmaz, sadece bir hatırlatma).
    # Kalıcı olsun diye etiket klasöründeki bir JSON dosyasına yazılıyor,
    # bkz. _bayrak_dosyasi()/_bayraklari_kaydet().
    "bayraklar": {},
}


def data_yaml_oku(yol: Path):
    with open(yol, "r", encoding="utf-8") as f:
        veri = yaml.safe_load(f)
    isimler = veri.get("names", {})
    if isinstance(isimler, dict):
        # {0: 'a', 1: 'b'} -> sıraya göre listeye çevir
        return [isimler[i] for i in sorted(isimler.keys())]
    return list(isimler)


def data_yaml_yaz(yol: Path, gorsel_klasoru: Path, siniflar: list[str]):
    """SADECE dosya hiç yoksa (ilk oluşturma) çağrılır.

    ÖNEMLİ: 'path' anahtarını BİLEREK yazmıyoruz. 'path: .' gibi göreli bir
    değer, dosyayı okuyan sürecin O ANKİ ÇALIŞMA DİZİNİNE (cwd) göre
    çözülüyor -- yaml dosyasının kendi bulunduğu klasöre göre değil. Bu
    yüzden aynı data.yaml, onu üreten arayüzden (cwd=etiketleme_arayuzu/)
    çalıştırılan bir eğitimde YANLIŞ yeri işaret ediyordu (bkz.
    bilgi_notlari/, "path: ." hatası). 'path' anahtarı hiç yoksa,
    ultralytics otomatik olarak yaml dosyasının KENDİ klasörünü kullanıyor
    -- bu, nereden çalıştırılırsa çalıştırılsın (Colab, bu arayüz, elle
    terminal) her zaman doğru sonucu verir.
    """
    icerik = {
        "train": gorsel_klasoru.name,
        "val": gorsel_klasoru.name,
        "test": gorsel_klasoru.name,
        "names": {i: isim for i, isim in enumerate(siniflar)},
    }
    with open(yol, "w", encoding="utf-8") as f:
        yaml.safe_dump(icerik, f, allow_unicode=True, sort_keys=False)


def data_yaml_sinif_guncelle(yol: Path, siniflar: list[str]):
    """Var olan bir data.yaml'a yeni sınıf(lar) eklerken kullanılır.
    ÖNEMLİ: path/train/val/test gibi diğer alanlara DOKUNMAZ, sadece
    'names' bölümünü günceller — aksi halde (bir hata olarak yaşadığımız
    gibi) o an hangi geçici klasörden işlem yapılıyorsa train/val/test
    yanlışlıkla o klasörün adına göre üzerine yazılabiliyordu."""
    with open(yol, "r", encoding="utf-8") as f:
        icerik = yaml.safe_load(f) or {}
    icerik["names"] = {i: isim for i, isim in enumerate(siniflar)}
    with open(yol, "w", encoding="utf-8") as f:
        yaml.safe_dump(icerik, f, allow_unicode=True, sort_keys=False)


@app.route("/")
def anasayfa():
    # "Hub" — tüm araçların (etiketleme, dataset splitter, augment, eğitim,
    # test) tek bir yerden erişildiği ana menü. nevfel.txt'deki "tüm
    # arayüzlere tek bir arayüz üstünden erişilebilinir olmalı" şartı.
    # gelismis_acik: Fusion kartının hub'da görünüp görünmeyeceği (bkz.
    # yukarıdaki "GELİŞMİŞ ÖZELLİKLER AYARI" bölümü).
    ayarlar = _ayarlari_oku()
    return render_template("index.html", gelismis_acik=ayarlar["gelismis_ozellikler_acik"])


# ============================================================
# GEREKLİLİKLER (in-app kurulum yardımcısı)
# Bu sayfanın kendisinin AÇILABİLMESİ için flask/pyyaml/pywebview/
# Pillow/numpy zaten kurulu olmalı (KURULUM.bat/BASLAT.bat ilk
# bootstrap'ı yapar, bkz. proje kökü) -- bu kutu ONLARDAN SONRA,
# Model Eğitimi/Test/Ön-Etiketleme için gereken AĞIR ve modüle göre
# OPSİYONEL bağımlılıkları (ultralytics, opencv-python,
# imageio-ffmpeg, torch, torchvision) + hazır COCO modelini
# (yolo11n.pt) tek tuşla kurmak/indirmek için var. app.py'nin geri
# kalanı bu paketleri modül BAŞINDA değil fonksiyon İÇİNDE import
# ediyor (bkz. yukarıdaki notlar) -- yani bunlar eksikken bile
# uygulama açılabiliyor, sadece o araçlar (Model Eğitimi/Test/
# Ön-Etiketleme) çalışmıyor. Bu sayfa TAM OLARAK o boşluğu dolduruyor.
# ============================================================

# (gösterim adı, import edilecek modül adı, hangi araç(lar) için gerekli)
GEREKLILIK_PAKETLERI = [
    ("flask", "flask", "arayüzün kendisi"),
    ("pyyaml", "yaml", "arayüzün kendisi"),
    ("pywebview", "webview", "arayüzün kendisi (native pencere)"),
    ("Pillow", "PIL", "arayüzün kendisi (görsel işleme)"),
    ("numpy", "numpy", "arayüzün kendisi"),
    ("ultralytics", "ultralytics", "Model Eğitimi, Model Test, Ön-Etiketleme"),
    ("opencv-python", "cv2", "Model Eğitimi, Model Test, Ön-Etiketleme, Video'dan Kare Çıkar"),
    ("imageio-ffmpeg", "imageio_ffmpeg", "Video'dan Kare Çıkar"),
    ("torch", "torch", "Model Eğitimi, Model Test (ultralytics'in altyapısı)"),
    ("torchvision", "torchvision", "Model Eğitimi, Model Test (ultralytics'in altyapısı)"),
]
# Sadece Fusion (proje-özel, varsayılan kapalı) için gerekenler --
# ayrı grupta gösteriliyor, kurmak zorunlu değil.
GEREKLILIK_OPSIYONEL_PAKETLERI = [
    ("fast-plate-ocr[onnx]", "fast_plate_ocr", "Fusion (plaka OCR)"),
    ("pillow-heif", "pillow_heif", "Fusion (iPhone HEIC görsel desteği)"),
]

GEREKLILIK_DURUMU = {
    "calisiyor": False,
    "tamamlandi": False,
    "hata": None,
    "loglar": [],
}
GEREKLILIK_KILIDI = threading.Lock()


def _gereklilik_logla(satir: str):
    with GEREKLILIK_KILIDI:
        GEREKLILIK_DURUMU["loglar"].append(satir)
        if len(GEREKLILIK_DURUMU["loglar"]) > 800:
            GEREKLILIK_DURUMU["loglar"] = GEREKLILIK_DURUMU["loglar"][-800:]


def _paket_kurulu_mu(modul_adi: str) -> bool:
    import importlib
    try:
        importlib.import_module(modul_adi)
        return True
    except Exception:
        return False


def _gpu_var_mi() -> bool:
    # nvidia-smi PATH'te varsa (NVIDIA sürücüsü kurulu demek) GPU var
    # sayıyoruz -- torch'un CUDA'lı mı CPU'lu mu kurulacağına bu karar
    # veriyor. Bulunamazsa (ya da 5 saniyede yanıt vermezse) CPU varsay.
    try:
        sonuc = subprocess.run(
            ["nvidia-smi"], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=5
        )
        return sonuc.returncode == 0
    except Exception:
        return False


def _yolo11n_dosya_yolu() -> Path:
    return Path(__file__).resolve().parent / "yolo11n.pt"


@app.route("/gereklilikler")
def gereklilikler_sayfasi():
    return render_template("gereklilikler.html")


@app.route("/api/gereklilik/durum")
def gereklilik_durum_getir():
    zorunlu = [
        {"paket": gosterim, "modul": modul, "aciklama": aciklama, "kurulu": _paket_kurulu_mu(modul)}
        for gosterim, modul, aciklama in GEREKLILIK_PAKETLERI
    ]
    opsiyonel = [
        {"paket": gosterim, "modul": modul, "aciklama": aciklama, "kurulu": _paket_kurulu_mu(modul)}
        for gosterim, modul, aciklama in GEREKLILIK_OPSIYONEL_PAKETLERI
    ]
    return jsonify({
        "zorunlu": zorunlu,
        "opsiyonel": opsiyonel,
        "yolo11n_var": _yolo11n_dosya_yolu().exists(),
        "gpu_bulundu": _gpu_var_mi(),
        "python_yorumlayici": sys.executable,
    })


def _pip_kur(paket_listesi: list[str], ekstra_argumanlar: list[str] | None = None) -> bool:
    """sys.executable -m pip install ... çalıştırır, çıktıyı SATIR SATIR
    canlı log'a yazar (Model Eğitimi'ndeki canlı log deseniyle aynı).
    Başarılıysa True, hata olursa False döner (istisna fırlatmaz --
    çağıran kod bir sonraki pakete geçmeye karar verebilsin diye)."""
    if not paket_listesi:
        return True
    komut = [sys.executable, "-m", "pip", "install", "--disable-pip-version-check"]
    komut += (ekstra_argumanlar or [])
    komut += paket_listesi
    _gereklilik_logla(f"$ {' '.join(komut)}")
    try:
        islem = subprocess.Popen(
            komut, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
            text=True, bufsize=1,
        )
        for satir in islem.stdout:
            _gereklilik_logla(satir.rstrip())
        islem.wait()
        return islem.returncode == 0
    except Exception as e:
        _gereklilik_logla(f"[HATA] pip çalıştırılamadı: {e}")
        return False


def _kurulumu_arka_planda_calistir(opsiyonel_de: bool, gpu_kullan: bool):
    GEREKLILIK_DURUMU["calisiyor"] = True
    GEREKLILIK_DURUMU["tamamlandi"] = False
    GEREKLILIK_DURUMU["hata"] = None
    GEREKLILIK_DURUMU["loglar"] = []
    try:
        # 1) torch/torchvision HARİÇ eksik paketleri topla (bunlar GPU/CPU
        # kararına göre ayrı kurulacak, tekrar kurulmasınlar).
        temel_eksikler = [
            gosterim for gosterim, modul, _ in GEREKLILIK_PAKETLERI
            if modul not in ("torch", "torchvision") and not _paket_kurulu_mu(modul)
        ]
        if temel_eksikler:
            _gereklilik_logla(f"[bilgi] Kurulacak: {', '.join(temel_eksikler)}")
            _pip_kur(temel_eksikler)
        else:
            _gereklilik_logla("[bilgi] Temel paketlerin hepsi zaten kurulu (torch hariç).")

        # 2) torch/torchvision -- GPU var mı yok mu kararına göre.
        torch_eksik = not _paket_kurulu_mu("torch")
        torchvision_eksik = not _paket_kurulu_mu("torchvision")
        if torch_eksik or torchvision_eksik:
            if gpu_kullan:
                _gereklilik_logla("[bilgi] GPU tespit edildi/seçildi -- CUDA'lı torch kurulacak (cu121).")
                _pip_kur(["torch", "torchvision"], ["--index-url", "https://download.pytorch.org/whl/cu121"])
            else:
                _gereklilik_logla("[bilgi] CPU'lu torch kurulacak.")
                _pip_kur(["torch", "torchvision"])
        else:
            _gereklilik_logla("[bilgi] torch/torchvision zaten kurulu.")

        # 3) Opsiyonel (Fusion) paketleri -- kullanıcı istediyse.
        if opsiyonel_de:
            opsiyonel_eksikler = [
                gosterim for gosterim, modul, _ in GEREKLILIK_OPSIYONEL_PAKETLERI
                if not _paket_kurulu_mu(modul)
            ]
            if opsiyonel_eksikler:
                _gereklilik_logla(f"[bilgi] Opsiyonel (Fusion) paketler kurulacak: {', '.join(opsiyonel_eksikler)}")
                _pip_kur(opsiyonel_eksikler)
            else:
                _gereklilik_logla("[bilgi] Opsiyonel (Fusion) paketler zaten kurulu.")

        # 4) yolo11n.pt (hazır COCO modeli) -- Ön-Etiketleme'nin genel
        # taramasında ve Model Test'te varsayılan olarak kullanılıyor.
        model_yolu = _yolo11n_dosya_yolu()
        if model_yolu.exists():
            _gereklilik_logla(f"[bilgi] {model_yolu.name} zaten var, indirme atlanıyor.")
        elif _paket_kurulu_mu("ultralytics"):
            _gereklilik_logla(f"[bilgi] {model_yolu.name} indiriliyor (COCO ile önceden eğitilmiş model)...")
            try:
                from ultralytics import YOLO
                YOLO(str(model_yolu))
                if model_yolu.exists():
                    _gereklilik_logla(f"[bilgi] {model_yolu.name} indirildi.")
                else:
                    _gereklilik_logla(f"[uyarı] İndirme denendi ama {model_yolu.name} beklenen yerde bulunamadı.")
            except Exception as e:
                _gereklilik_logla(f"[uyarı] {model_yolu.name} indirilemedi: {e}")
        else:
            _gereklilik_logla("[uyarı] ultralytics kurulu olmadığı için yolo11n.pt indirilemedi.")

        _gereklilik_logla("[bitti] Kurulum tamamlandı. Kontrolü tekrar çalıştırıp doğrulayabilirsin.")
    except Exception as e:
        GEREKLILIK_DURUMU["hata"] = str(e)
        _gereklilik_logla(f"[HATA] Beklenmeyen hata: {e}\n{traceback.format_exc()}")
    finally:
        GEREKLILIK_DURUMU["calisiyor"] = False
        GEREKLILIK_DURUMU["tamamlandi"] = True


@app.route("/api/gereklilik/kur_baslat", methods=["POST"])
def gereklilik_kur_baslat():
    if GEREKLILIK_DURUMU["calisiyor"]:
        return jsonify({"hata": "Kurulum zaten çalışıyor, bitmesini bekle."}), 400
    veri = request.get_json() or {}
    opsiyonel_de = bool(veri.get("opsiyonel_de", False))
    gpu_kullan = bool(veri.get("gpu_kullan", _gpu_var_mi()))
    threading.Thread(
        target=_kurulumu_arka_planda_calistir, args=(opsiyonel_de, gpu_kullan), daemon=True
    ).start()
    return jsonify({"ok": True})


@app.route("/api/gereklilik/kur_durum")
def gereklilik_kur_durum():
    with GEREKLILIK_KILIDI:
        return jsonify(dict(GEREKLILIK_DURUMU))


@app.route("/etiketleme")
def etiketleme_sayfasi():
    return render_template("etiketleme.html")


@app.route("/splitter")
def splitter_sayfasi():
    return render_template("splitter.html")


@app.route("/augment")
def augment_sayfasi():
    return render_template("augment.html")


@app.route("/egitim")
def egitim_sayfasi():
    return render_template("egitim.html")


@app.route("/test")
def test_sayfasi():
    return render_template("test.html")


@app.route("/api/yukle", methods=["POST"])
def yukle():
    veri = request.get_json()
    gorsel_klasoru_str = veri.get("gorsel_klasoru", "").strip()
    etiket_klasoru_str = veri.get("etiket_klasoru", "").strip()
    data_yaml_str = veri.get("data_yaml", "").strip()
    siniflar_str = veri.get("siniflar", "").strip()

    gorsel_klasoru = Path(gorsel_klasoru_str)
    if not gorsel_klasoru.is_dir():
        return jsonify({"hata": f"Görsel klasörü bulunamadı: {gorsel_klasoru_str}"}), 400

    # Etiket klasörü verilmediyse iki durum var:
    #   1) Görsel klasörünün adı tam olarak "images" ise: bu, YOLO'nun
    #      standart images/+labels/ kardeş klasör kuralına uyan NİHAİ
    #      (eğitime girecek) klasör demektir -> düz bir "labels" kardeşi
    #      varsayıyoruz (ultralytics'in kendi iç kuralı da tam bu:
    #      ".../images/x.jpg" -> ".../labels/x.txt").
    #   2) Başka bir isimdeyse (örn. "fiat_egea", "renault_clio3" gibi
    #      GEÇİCİ, sınıf başına toplama klasörleri): bunların hepsinin
    #      üst klasörü aynı olabiliyor (örn. hepsi "veri" altında), yani
    #      düz bir "labels" kullansaydık farklı sınıflardaki AYNI İSİMLİ
    #      dosyalar (örn. hepsinde "0001.jpg") birbirinin etiketinin
    #      üzerine yazardı. Bunu önlemek için klasör adını koruyarak
    #      "labels/<klasör_adı>/" altına ayırıyoruz — bu klasörler zaten
    #      geçici, Adım 4 sonunda hepsi tek bir "images/"+"labels/" içine
    #      birleştirilecek.
    if etiket_klasoru_str:
        etiket_klasoru = Path(etiket_klasoru_str)
    elif gorsel_klasoru.name == "images":
        etiket_klasoru = gorsel_klasoru.parent / "labels"
    else:
        etiket_klasoru = gorsel_klasoru.parent / "labels" / gorsel_klasoru.name
    etiket_klasoru.mkdir(parents=True, exist_ok=True)

    # Bayrak (elle "bunu sonra kontrol et" işaretleme) durumunu yükle --
    # her etiket klasörünün kendi _bayraklar.json'u var, o proje/klasöre özel.
    bayrak_dosyasi = etiket_klasoru / "_bayraklar.json"
    bayraklar = {}
    if bayrak_dosyasi.exists():
        try:
            with open(bayrak_dosyasi, "r", encoding="utf-8") as f:
                bayraklar = json.load(f)
        except (json.JSONDecodeError, OSError):
            bayraklar = {}

    # Sınıf listesini belirleme mantığı — ÖNEMLİ GÜVENLİK KURALI:
    # Etiket dosyaları (YOLO .txt) sınıfı sadece bir SAYI (ID) olarak
    # tutar, isim tutmaz. O ID'nin hangi isme karşılık geldiğini SADECE
    # data.yaml belirler. Yani var olan bir data.yaml'ın sınıf listesini
    # (sırasını/isimlerini) DEĞİŞTİRMEK ya da bir ismi başka bir isimle
    # DEĞİŞTİRMEK, o dosyayı kullanan TÜM klasörlerdeki TÜM var olan
    # etiketlerin anlamını bozar — bir kere yaşadık: "asd" diye yeni bir
    # sınıf yazınca, önceden "clio4" ile etiketlenmiş 60 görsel geriye
    # dönük "asd" oldu.
    #
    # Kural: var olan sınıflar HİÇBİR ZAMAN silinmez/yeniden adlandırılmaz/
    # sırası değiştirilmez — bunlar hep "varsayılan" olarak korunur. Elle
    # yazılan listede, var olanların DIŞINDA YENİ bir isim varsa, bunu
    # SESSİZCE eklemek yerine kullanıcıdan onay istiyoruz (frontend'de
    # `confirm()` ile). Onay gelmeden (`onay=true` gönderilmeden) yeni
    # sınıf asla kaydedilmez — sadece "onay_gerekli" bilgisini döndürüp
    # var olan sınıflarla devam ederiz, kullanıcı isterse tekrar
    # `onay: true` ile gönderip ekletir.
    data_yaml_yolu = Path(data_yaml_str) if data_yaml_str else (gorsel_klasoru.parent / "data.yaml")
    mevcut_siniflar = data_yaml_oku(data_yaml_yolu) if data_yaml_yolu.exists() else []

    if siniflar_str:
        yazilan_siniflar = [s.strip() for s in siniflar_str.split(",") if s.strip()]
        yeni_siniflar = [s for s in yazilan_siniflar if s not in mevcut_siniflar]

        if yeni_siniflar and not veri.get("onay"):
            # Henüz onay verilmedi -> hiçbir şeyi kaydetmeden, sadece
            # frontend'e "şu yeni sınıflar var, eklemek ister misin?" diye
            # sorması gereken bilgiyi dönüyoruz.
            return jsonify({
                "onay_gerekli": True,
                "yeni_siniflar": yeni_siniflar,
                "mevcut_siniflar": mevcut_siniflar,
            })

        if yeni_siniflar and veri.get("onay"):
            # Onay geldi -> var olanları AYNEN koruyarak, yenileri SONUNA
            # ekliyoruz (mevcut ID'ler asla kaymaz/değişmez).
            siniflar = mevcut_siniflar + yeni_siniflar
            if data_yaml_yolu.exists():
                # Dosya zaten var -> SADECE 'names' güncellenir, path/
                # train/val/test gibi alanlara dokunulmaz.
                data_yaml_sinif_guncelle(data_yaml_yolu, siniflar)
            else:
                data_yaml_yaz(data_yaml_yolu, gorsel_klasoru, siniflar)
        else:
            # Yazılanların hepsi zaten var olan listede -> data.yaml'a
            # dokunmadan, mevcut (disk üzerindeki) sırayı kullan.
            siniflar = mevcut_siniflar if mevcut_siniflar else yazilan_siniflar
            if not data_yaml_yolu.exists():
                data_yaml_yaz(data_yaml_yolu, gorsel_klasoru, siniflar)
    else:
        siniflar = mevcut_siniflar if mevcut_siniflar else None

    if not siniflar:
        return jsonify({
            "hata": "Class listesi bulunamadı. Ya bir data.yaml belirt, "
                    "ya da 'Class'lar' alanına virgülle ayrılmış class "
                    "isimleri gir (örn: renault_clio3,fiat_egea)."
        }), 400

    gorseller = sorted(
        p.name for p in gorsel_klasoru.iterdir()
        if p.suffix.lower() in GORSEL_UZANTILARI
    )

    if not gorseller:
        return jsonify({"hata": "Bu klasörde desteklenen formatta görsel bulunamadı."}), 400

    DURUM.update({
        "gorsel_klasoru": gorsel_klasoru,
        "etiket_klasoru": etiket_klasoru,
        "data_yaml_yolu": data_yaml_yolu,
        "siniflar": siniflar,
        "gorseller": gorseller,
        "bayraklar": bayraklar,
    })

    return jsonify({
        "gorseller": _gorsel_durum_listesi(),
        "siniflar": siniflar,
        "etiket_klasoru": str(etiket_klasoru),
        "data_yaml_yolu": str(data_yaml_yolu),
    })


def _etiket_dosyasi(dosya_adi: str) -> Path:
    return DURUM["etiket_klasoru"] / (Path(dosya_adi).stem + ".txt")


def _eski_flat_etiket_dosyasi(dosya_adi: str) -> Path:
    """Geriye dönük uyumluluk: bir önceki sürümde (klasör-adı-bazlı
    ayrım eklenmeden önce) etiketler görsel klasörünün yanındaki DÜZ
    'labels' klasörüne kaydediliyordu. Eğer yeni (klasör adına göre
    ayrılmış) konumda etiket bulunamazsa, kaybolmuş görünmesinler diye
    bu eski konuma da bakıyoruz. Yeni kayıtlar her zaman yeni konuma
    yazılıyor — bu sadece "okuma" için bir yedek/geçiş kolaylığı."""
    return DURUM["gorsel_klasoru"].parent / "labels" / (Path(dosya_adi).stem + ".txt")


def _etiket_oku(dosya_adi: str) -> Path | None:
    """Etiket dosyasını bulur: önce yeni (klasör-adına-özel) konumda,
    yoksa eski düz 'labels' konumunda arar. Hiçbiri yoksa None döner."""
    yeni = _etiket_dosyasi(dosya_adi)
    if yeni.exists() and yeni.stat().st_size > 0:
        return yeni
    eski = _eski_flat_etiket_dosyasi(dosya_adi)
    if eski.exists() and eski.stat().st_size > 0:
        return eski
    return None


def _gorsel_durum_listesi():
    """Her görsel için isim + etiketlenmiş mi (dolu bir .txt var mı) +
    bayraklı mı (elle 'sonra tekrar kontrol et' işaretlenmiş mi) bilgisi."""
    sonuc = []
    for ad in DURUM["gorseller"]:
        etiketli = _etiket_oku(ad) is not None
        bayrakli = bool(DURUM["bayraklar"].get(ad, False))
        sonuc.append({"ad": ad, "etiketli": etiketli, "bayrakli": bayrakli})
    return sonuc


def _bayrak_dosyasi() -> Path:
    return DURUM["etiket_klasoru"] / "_bayraklar.json"


def _bayraklari_kaydet():
    if DURUM["etiket_klasoru"] is None:
        return
    DURUM["etiket_klasoru"].mkdir(parents=True, exist_ok=True)
    with open(_bayrak_dosyasi(), "w", encoding="utf-8") as f:
        json.dump(DURUM["bayraklar"], f, ensure_ascii=False, indent=2)


@app.route("/api/gorsel/<path:dosya_adi>")
def gorsel_getir(dosya_adi):
    if DURUM["gorsel_klasoru"] is None:
        return "Önce bir klasör yükle.", 400
    return send_from_directory(DURUM["gorsel_klasoru"], dosya_adi)


@app.route("/api/etiket/<path:dosya_adi>", methods=["GET"])
def etiket_getir(dosya_adi):
    if DURUM["etiket_klasoru"] is None:
        return jsonify({"hata": "Önce bir klasör yükle."}), 400
    etiket_dosyasi = _etiket_oku(dosya_adi)  # yeni konum, yoksa eski düz konum
    kutular = []
    if etiket_dosyasi is not None:
        with open(etiket_dosyasi, "r", encoding="utf-8") as f:
            for satir in f:
                parcalar = satir.strip().split()
                if len(parcalar) != 5:
                    continue
                sinif_id, x, y, w, h = parcalar
                kutular.append({
                    "sinif": int(sinif_id),
                    "x": float(x), "y": float(y),
                    "w": float(w), "h": float(h),
                })
    return jsonify({"kutular": kutular})


@app.route("/api/etiket/<path:dosya_adi>", methods=["POST"])
def etiket_kaydet(dosya_adi):
    if DURUM["etiket_klasoru"] is None:
        return jsonify({"hata": "Önce bir klasör yükle."}), 400
    veri = request.get_json()
    kutular = veri.get("kutular", [])
    etiket_dosyasi = _etiket_dosyasi(dosya_adi)

    satirlar = []
    for k in kutular:
        satirlar.append(
            f"{int(k['sinif'])} {k['x']:.6f} {k['y']:.6f} {k['w']:.6f} {k['h']:.6f}"
        )

    with open(etiket_dosyasi, "w", encoding="utf-8") as f:
        f.write("\n".join(satirlar))
        if satirlar:
            f.write("\n")

    return jsonify({"ok": True, "kutu_sayisi": len(satirlar)})


@app.route("/api/durum")
def durum_getir():
    if DURUM["gorsel_klasoru"] is None:
        return jsonify({"yuklu": False})
    return jsonify({
        "yuklu": True,
        "gorseller": _gorsel_durum_listesi(),
        "siniflar": DURUM["siniflar"],
    })


@app.route("/api/bayrak/<path:dosya_adi>", methods=["POST"])
def bayrak_ayarla(dosya_adi):
    """Bir görseli 'sonra tekrar kontrol et' diye işaretler/işareti kaldırır.
    YOLO etiket dosyasına hiç dokunmaz -- ayrı bir _bayraklar.json'da tutulur."""
    veri = request.get_json()
    bayrakli = bool(veri.get("bayrakli", False))
    if bayrakli:
        DURUM["bayraklar"][dosya_adi] = True
    else:
        DURUM["bayraklar"].pop(dosya_adi, None)
    _bayraklari_kaydet()
    return jsonify({"ok": True, "bayrakli": bayrakli})


@app.route("/api/gorsel/<path:dosya_adi>", methods=["DELETE"])
def gorsel_sil(dosya_adi):
    """Bir görseli ve varsa etiketini KALICI olarak diskten siler (örn.
    uygun olmayan/bulanık/yanlış fotoğrafları elemek için). Geri alınamaz."""
    if DURUM["gorsel_klasoru"] is None:
        return jsonify({"hata": "Önce bir klasör yükle."}), 400

    # dosya_adi <path:> ile geldiği için "../" içerebilir -- klasör dışına
    # çıkıp keyfi bir dosya silinmesini önlemek için sadece dosya adını
    # (yol bileşenlerini atarak) alıp, sonucun gerçekten gorsel_klasoru
    # ALTINDA olduğunu doğruluyoruz.
    gorsel_klasoru = DURUM["gorsel_klasoru"].resolve()
    gorsel_yolu = (gorsel_klasoru / Path(dosya_adi).name).resolve()
    if gorsel_klasoru not in gorsel_yolu.parents and gorsel_yolu != gorsel_klasoru:
        return jsonify({"hata": "Geçersiz dosya adı."}), 400
    if not gorsel_yolu.exists():
        return jsonify({"hata": f"Görsel bulunamadı: {dosya_adi}"}), 404
    gorsel_yolu.unlink()

    for etiket_yolu in (_etiket_dosyasi(dosya_adi), _eski_flat_etiket_dosyasi(dosya_adi)):
        if etiket_yolu.exists():
            etiket_yolu.unlink()

    DURUM["gorseller"] = [ad for ad in DURUM["gorseller"] if ad != dosya_adi]
    DURUM["bayraklar"].pop(dosya_adi, None)
    _bayraklari_kaydet()

    return jsonify({"ok": True, "gorseller": _gorsel_durum_listesi()})



# ============================================================
# ORTAK GİRDİ ÇÖZÜMLEME (splitter + augment ikisi de kullanır)
# Etiket klasörü / data.yaml elle verilmediyse otomatik bulmaya çalışır.
# İKİ farklı klasör düzenini tanır:
#   1) Düz:       <konum>/images/  ->  labels: <konum>/labels/
#                                       data.yaml: <konum>/data.yaml
#   2) Bölünmüş:  <konum>/images/train/ (splitter çıktısı) ->
#                       labels: <konum>/labels/train/
#                       data.yaml: <konum>/data.yaml
#      (train/val/test hangisiyse onu ayna: images/<X> -> labels/<X>)
# Bu ayrım yapılmazsa, "images/train" seçildiğinde etiket klasörü ve
# data.yaml YANLIŞ yerde (images/train'in yanında) aranıyordu.
# ============================================================

def _girdi_klasorlerini_coz(gorsel_klasoru_str, etiket_klasoru_str, data_yaml_str):
    gorsel_klasoru = Path(gorsel_klasoru_str)
    bolunmus_mu = gorsel_klasoru.parent.name == "images"  # örn. .../images/train

    if etiket_klasoru_str:
        etiket_klasoru = Path(etiket_klasoru_str)
    elif gorsel_klasoru.name == "images":
        etiket_klasoru = gorsel_klasoru.parent / "labels"
    elif bolunmus_mu:
        etiket_klasoru = gorsel_klasoru.parent.parent / "labels" / gorsel_klasoru.name
    else:
        etiket_klasoru = gorsel_klasoru.parent / "labels" / gorsel_klasoru.name

    if data_yaml_str:
        data_yaml_yolu = Path(data_yaml_str)
    elif bolunmus_mu:
        data_yaml_yolu = gorsel_klasoru.parent.parent / "data.yaml"
    else:
        data_yaml_yolu = gorsel_klasoru.parent / "data.yaml"

    return gorsel_klasoru, etiket_klasoru, data_yaml_yolu


# ============================================================
# DATASET SPLITTER (nevfel.txt madde 2)
# Girdi: images/ + labels/ (+ data.yaml). Çıktı: train/val/test'e
# bölünmüş images/+labels/ + yeni data.yaml + analiz.txt.
# ============================================================

def _splitter_klasorleri_coz(gorsel_klasoru_str, etiket_klasoru_str, data_yaml_str):
    return _girdi_klasorlerini_coz(gorsel_klasoru_str, etiket_klasoru_str, data_yaml_str)


@app.route("/api/splitter/on_izle", methods=["POST"])
def splitter_on_izle():
    """Böl butonuna basmadan önce, kullanıcıya "kaç görsel var, kaçı
    etiketli, sınıflar neler" diye bir önizleme gösterir. Hiçbir dosyaya
    dokunmaz, sadece okur."""
    veri = request.get_json()
    gorsel_klasoru, etiket_klasoru, data_yaml_yolu = _splitter_klasorleri_coz(
        veri.get("gorsel_klasoru", "").strip(),
        veri.get("etiket_klasoru", "").strip(),
        veri.get("data_yaml", "").strip(),
    )

    if not gorsel_klasoru.is_dir():
        return jsonify({"hata": f"Görsel klasörü bulunamadı: {gorsel_klasoru}"}), 400
    if not data_yaml_yolu.exists():
        return jsonify({"hata": f"data.yaml bulunamadı: {data_yaml_yolu}"}), 400

    siniflar = data_yaml_oku(data_yaml_yolu)
    gorseller = [p for p in gorsel_klasoru.iterdir() if p.suffix.lower() in GORSEL_UZANTILARI]

    eslesen = 0
    eksik_etiket = 0
    for g in gorseller:
        etiket = etiket_klasoru / (g.stem + ".txt")
        if etiket.exists() and etiket.stat().st_size > 0:
            eslesen += 1
        else:
            eksik_etiket += 1

    return jsonify({
        "toplam_gorsel": len(gorseller),
        "eslesen": eslesen,
        "eksik_etiket": eksik_etiket,
        "siniflar": siniflar,
        "etiket_klasoru": str(etiket_klasoru),
        "data_yaml_yolu": str(data_yaml_yolu),
    })


def _gorsel_boyut_analizi(bolumler: dict) -> list[str]:
    """Tüm görsellerin piksel boyutunu (genişlik x yükseklik) tarar --
    hocanın 'image size öğren tut, verilere bak' notuna karşılık. Amaç:
    eğitimde seçilecek imgsz'in veriye uygun olup olmadığını görmek ve
    çok farklı çözünürlükte görsellerin karışıp karışmadığını fark
    etmek (örn. bazıları telefon fotosu, bazıları küçük ekran görüntüsü)."""
    tire = "-" * 80
    satirlar = ["GÖRSEL BOYUTU (ÇÖZÜNÜRLÜK) ANALİZİ", tire]

    genislikler, yukseklikler = [], []
    for ciftler in bolumler.values():
        for gorsel, _etiket in ciftler:
            try:
                with Image.open(gorsel) as im:
                    w, h = im.size
                genislikler.append(w)
                yukseklikler.append(h)
            except Exception:
                continue

    if not genislikler:
        satirlar.append("(Görsel boyutu okunamadı.)")
        satirlar.append("")
        return satirlar

    ort_w = round(sum(genislikler) / len(genislikler))
    ort_h = round(sum(yukseklikler) / len(yukseklikler))
    satirlar.append(f"Taranan görsel sayısı : {len(genislikler)}")
    satirlar.append(f"Genişlik  min/ort/max : {min(genislikler)} / {ort_w} / {max(genislikler)}")
    satirlar.append(f"Yükseklik min/ort/max : {min(yukseklikler)} / {ort_h} / {max(yukseklikler)}")

    en_kucuk_kenar = min(min(genislikler), min(yukseklikler))
    en_buyuk_kenar = max(max(genislikler), max(yukseklikler))
    oran = (en_buyuk_kenar / en_kucuk_kenar) if en_kucuk_kenar else 0

    if oran > 3:
        satirlar.append(
            f"UYARI: en küçük ve en büyük görsel arasında {oran:.1f}x fark var -- "
            "veri setinde çok farklı çözünürlükte görseller karışmış olabilir."
        )
    else:
        satirlar.append("Görsel boyutları makul ölçüde tutarlı.")

    ort_kenar = round((ort_w + ort_h) / 2)
    onerilen_imgsz = min(1280, max(320, round(ort_kenar / 32) * 32))
    satirlar.append(
        f"Ortalama kenar uzunluğu ~{ort_kenar}px -- eğitimde imgsz için "
        f"~{onerilen_imgsz} civarı (32'nin katı olmalı) makul bir başlangıç olabilir. "
        "Not: YOLO görselleri zaten imgsz'e otomatik yeniden boyutlandırıyor, "
        "yani hepsinin ELLE aynı boyutta olması ZORUNLU değil -- burada amaç "
        "kaynak verinin çözünürlüğüne uygun bir imgsz seçmek ve anormal/bozuk "
        "görselleri fark etmek."
    )
    satirlar.append("")
    return satirlar


def _analiz_raporu_olustur(bolumler: dict, siniflar: list[str], eksik_sayisi: int, seed=None) -> str:
    """nevfel.txt'de örneği verilen formata uygun analiz.txt içeriğini
    üretir: bölüm özeti (görsel/etiket/eşleşen/nesne/eksik sayıları) ve
    sınıf dağılımı (her sınıftan train/val/test'te kaçar tane var)."""
    satirlar = []
    cizgi = "=" * 80
    tire = "-" * 80

    satirlar.append(cizgi)
    satirlar.append("📊 YOLO DETECT VERİ SETİ DETAYLI ANALİZ RAPORU")
    satirlar.append(cizgi)
    satirlar.append("")
    if seed is not None:
        satirlar.append(f"Bölme (shuffle) SABİT seed={seed} ile yapıldı -- aynı seed ile tekrar")
        satirlar.append("çalıştırılırsa AYNI train/val/test dağılımı üretilir (tekrarlanabilir).")
    else:
        satirlar.append("Bölme (shuffle) SEED VERİLMEDEN yapıldı -- her çalıştırmada train/val/test'e")
        satirlar.append("giren görseller FARKLI olabilir (tekrarlanabilir DEĞİL). Aynı bölünmeyi")
        satirlar.append("tekrar üretmek istersen bir dahaki sefere bir seed sayısı gir.")
    satirlar.append("")
    satirlar.append("📂 BÖLÜM ÖZETİ")
    satirlar.append(tire)
    satirlar.append(f"{'Bölüm':<12}{'Görsel':>8}{'Etiket':>9}{'Eşleşen':>9}{'Nesne':>9}{'EksikLbl':>10}{'EksikImg':>10}")
    satirlar.append(tire)

    sinif_sayaclari = {bolum: defaultdict(int) for bolum in bolumler}

    for bolum, ciftler in bolumler.items():
        gorsel_sayisi = len(ciftler)
        etiket_sayisi = len(ciftler)  # sadece eşleşenler bölümlere girdi
        nesne_sayisi = 0
        for _gorsel, etiket_yolu in ciftler:
            with open(etiket_yolu, "r", encoding="utf-8") as f:
                for satir in f:
                    satir = satir.strip()
                    if not satir:
                        continue
                    nesne_sayisi += 1
                    sinif_id = int(satir.split()[0])
                    sinif_sayaclari[bolum][sinif_id] += 1

        satirlar.append(
            f"{bolum:<12}{gorsel_sayisi:>8}{etiket_sayisi:>9}{gorsel_sayisi:>9}"
            f"{nesne_sayisi:>9}{0:>10}{0:>10}"
        )

    satirlar.append(tire)
    if eksik_sayisi:
        satirlar.append(f"(Not: {eksik_sayisi} görsel etiketsiz olduğu için bölümlere hiç dahil edilmedi.)")
    satirlar.append("")

    satirlar.append("🎯 SINIF DAĞILIMI (Train / Val / Test yan yana)")
    satirlar.append(tire)
    bolum_isimleri = list(bolumler.keys())
    baslik = f"{'ID':>4}  {'Sınıf':<24}"
    for b in bolum_isimleri:
        baslik += f"{b:>10}"
    baslik += f"{'Toplam':>10}"
    satirlar.append(baslik)
    satirlar.append(tire)

    for sinif_id, sinif_adi in enumerate(siniflar):
        satir = f"{sinif_id:>4}  {sinif_adi:<24}"
        toplam = 0
        for b in bolum_isimleri:
            adet = sinif_sayaclari[b].get(sinif_id, 0)
            toplam += adet
            satir += f"{adet:>10}"
        satir += f"{toplam:>10}"
        satirlar.append(satir)

    satirlar.append(tire)
    satirlar.append("")
    satirlar.extend(_gorsel_boyut_analizi(bolumler))
    return "\n".join(satirlar) + "\n"


@app.route("/api/splitter/calistir", methods=["POST"])
def splitter_calistir():
    veri = request.get_json()
    gorsel_klasoru, etiket_klasoru, data_yaml_yolu = _splitter_klasorleri_coz(
        veri.get("gorsel_klasoru", "").strip(),
        veri.get("etiket_klasoru", "").strip(),
        veri.get("data_yaml", "").strip(),
    )
    cikti_klasoru_str = veri.get("cikti_klasoru", "").strip()
    if not cikti_klasoru_str:
        return jsonify({"hata": "Çıktı klasörü seçmelisin."}), 400
    cikti_klasoru = Path(cikti_klasoru_str)

    try:
        train_oran = float(veri.get("train_oran", 0))
        val_oran = float(veri.get("val_oran", 0))
        test_oran = float(veri.get("test_oran", 0))
    except (TypeError, ValueError):
        return jsonify({"hata": "Oranlar sayısal olmalı."}), 400

    toplam_oran = train_oran + val_oran + test_oran
    if abs(toplam_oran - 100) > 0.5:
        return jsonify({"hata": f"Oranların toplamı 100 olmalı (şu an {toplam_oran})."}), 400

    if not gorsel_klasoru.is_dir():
        return jsonify({"hata": f"Görsel klasörü bulunamadı: {gorsel_klasoru}"}), 400
    if not data_yaml_yolu.exists():
        return jsonify({"hata": f"data.yaml bulunamadı: {data_yaml_yolu}"}), 400

    siniflar = data_yaml_oku(data_yaml_yolu)

    gorseller = sorted(p for p in gorsel_klasoru.iterdir() if p.suffix.lower() in GORSEL_UZANTILARI)
    ciftler = []
    eksik_sayisi = 0
    for g in gorseller:
        etiket = etiket_klasoru / (g.stem + ".txt")
        if etiket.exists() and etiket.stat().st_size > 0:
            ciftler.append((g, etiket))
        else:
            eksik_sayisi += 1

    if not ciftler:
        return jsonify({"hata": "Etiketli (eşleşen) hiç görsel bulunamadı, bölünecek veri yok."}), 400

    # Rastgele karıştırıp orana göre böl (yuvarlama farkı test'e devrediliyor).
    # SABİT SEED (opsiyonel): varsayılan olarak `random.shuffle` her
    # çalıştırmada FARKLI bir bölünme üretiyordu -- aynı klasörü iki kez
    # bölünce train/val/test'e giren görseller değişebiliyordu. Bu, "aynı
    # böleyle" bir modeli tekrar eğitmek/karşılaştırmak isteyen biri için
    # sorun (bkz. bilgi_notlari/09_teknik_referans.txt, bölüm 15). Kullanıcı
    # bir seed sayısı girerse `random.Random(seed)` ile İZOLE bir rastgele
    # üretici kullanıyoruz (global `random` modülünü etkilemiyor, başka bir
    # aracın rastgeleliğini -- örn. Augment'ın "dinamik" modu -- bozmuyor).
    seed_ham = veri.get("seed", "")
    if str(seed_ham).strip() != "":
        try:
            rastgele_uretici = random.Random(int(seed_ham))
        except (TypeError, ValueError):
            return jsonify({"hata": "Seed bir tam sayı olmalı (boş bırakırsan her seferinde farklı bölünür)."}), 400
        rastgele_uretici.shuffle(ciftler)
    else:
        random.shuffle(ciftler)
    n = len(ciftler)
    n_train = round(n * train_oran / 100)
    n_val = round(n * val_oran / 100)

    bolumler = {
        "train": ciftler[:n_train],
        "val": ciftler[n_train:n_train + n_val],
        "test": ciftler[n_train + n_val:],
    }

    for bolum, liste in bolumler.items():
        (cikti_klasoru / "images" / bolum).mkdir(parents=True, exist_ok=True)
        (cikti_klasoru / "labels" / bolum).mkdir(parents=True, exist_ok=True)
        for gorsel, etiket in liste:
            shutil.copy2(gorsel, cikti_klasoru / "images" / bolum / gorsel.name)
            shutil.copy2(etiket, cikti_klasoru / "labels" / bolum / etiket.name)

    yeni_data_yaml = cikti_klasoru / "data.yaml"
    # NOT: 'path' anahtarını BİLEREK yazmıyoruz -- bkz. data_yaml_yaz()'daki
    # yorum. Yoksa ultralytics train/val/test'i yaml'ın kendi klasörüne göre
    # değil, o an çalışan sürecin cwd'sine göre arıyor.
    icerik = {
        "train": "images/train",
        "val": "images/val",
        "test": "images/test",
        "names": {i: isim for i, isim in enumerate(siniflar)},
    }
    with open(yeni_data_yaml, "w", encoding="utf-8") as f:
        yaml.safe_dump(icerik, f, allow_unicode=True, sort_keys=False)

    kullanilan_seed = int(seed_ham) if str(seed_ham).strip() != "" else None
    analiz_metni = _analiz_raporu_olustur(bolumler, siniflar, eksik_sayisi, seed=kullanilan_seed)
    (cikti_klasoru / "analiz.txt").write_text(analiz_metni, encoding="utf-8")

    return jsonify({
        "ok": True,
        "cikti_klasoru": str(cikti_klasoru),
        "data_yaml_yolu": str(yeni_data_yaml),
        "sayilar": {b: len(l) for b, l in bolumler.items()},
        "analiz": analiz_metni,
    })


# ============================================================
# DATA AUGMENT (nevfel.txt madde 3)
# Girdi: images/ + labels/ (+ data.yaml). Çıktı: BAŞKA bir klasöre
# çoğaltılmış images/+labels/ (+ data.yaml). Etiketler pixel-seviyeli
# augment'lerden (parlaklık/keskinlik/blur/gölge) etkilenmediği için
# kutu koordinatları DEĞİŞMEDEN aynen kopyalanıyor.
# İki mod:
#   sabit  -> her teknik için TEK bir "taban" değer, her görselden 1 yeni
#             görsel üretilir (hepsi aynı ayarlarla).
#   dinamik -> her teknik için "taban" ve "hedef" değer aralığı, kullanıcının
#             istediği ADET kadar yeni görsel üretilir, her biri için her
#             teknik parametresi taban-hedef arasında RASTGELE seçilir.
# Filtre: yazılan sınıf adını İÇEREN etiketi olan görseller seçilir (örn.
# "clio3" yazınca sadece clio3 kutusu olan görseller çoğaltılır) — azınlıkta
# kalan sınıfı dengelemek için.
# ============================================================

def _augment_klasorleri_coz(gorsel_klasoru_str, etiket_klasoru_str, data_yaml_str):
    return _girdi_klasorlerini_coz(gorsel_klasoru_str, etiket_klasoru_str, data_yaml_str)


def _etiketteki_sinif_idleri(etiket_yolu: Path | None) -> set[int]:
    if etiket_yolu is None or not etiket_yolu.exists():
        return set()
    idler = set()
    with open(etiket_yolu, "r", encoding="utf-8") as f:
        for satir in f:
            satir = satir.strip()
            if satir:
                idler.add(int(satir.split()[0]))
    return idler


def _gorselleri_filtrele(gorsel_klasoru: Path, etiket_klasoru: Path, siniflar: list[str], filtre: str):
    """filtre boşsa hepsini döndürür (ETİKETSİZ görseller DAHİL -- nevfel.txt
    Augment'in de "sadece images + data.yaml" girdisiyle çalışabilmesini
    istiyor, yani labels klasörü hiç olmasa da araç çalışmalı). Filtre
    doluysa, etiketinde filtreyi İÇEREN (case-insensitive) bir sınıf adı
    geçen görselleri döndürür -- etiketsiz bir görsel hiçbir sınıfa
    filtrelenemeyeceği için filtre uygulanınca elenir (2026-08-05
    düzeltmesi -- eskiden etiketsiz görseller filtre boşken bile hiç
    listeye girmiyordu).

    Döndürülen ikili: (gorsel_yolu, etiket_yolu_veya_None). etiket_yolu
    None ise, o görselin gerçek bir etiket dosyası yok demektir."""
    gorseller = sorted(p for p in gorsel_klasoru.iterdir() if p.suffix.lower() in GORSEL_UZANTILARI)
    ciftler = []
    for g in gorseller:
        etiket = etiket_klasoru / (g.stem + ".txt")
        etiket_var = etiket.exists() and etiket.stat().st_size > 0
        ciftler.append((g, etiket if etiket_var else None))

    if not filtre:
        return ciftler

    filtre_kucuk = filtre.strip().lower()
    eslesen = []
    for gorsel, etiket in ciftler:
        if etiket is None:
            continue
        idler = _etiketteki_sinif_idleri(etiket)
        sinif_adlari = [siniflar[i] for i in idler if 0 <= i < len(siniflar)]
        if any(filtre_kucuk in ad.lower() for ad in sinif_adlari):
            eslesen.append((gorsel, etiket))
    return eslesen


def _rastgele_arada(taban: float, hedef: float) -> float:
    alt, ust = (taban, hedef) if taban <= hedef else (hedef, taban)
    return random.uniform(alt, ust)


def _augment_uygula(img: Image.Image, teknikler: dict) -> Image.Image:
    """teknikler: {"parlaklik": deger|None, "keskinlik": deger|None,
    "blur": deger|None, "golge": deger|None, "kontrast": deger|None,
    "gurultu": deger|None, "sikistirma": deger|None} -- None ise o teknik
    uygulanmaz."""
    sonuc = img.convert("RGB")

    if teknikler.get("parlaklik") is not None:
        sonuc = ImageEnhance.Brightness(sonuc).enhance(teknikler["parlaklik"])

    if teknikler.get("kontrast") is not None:
        sonuc = ImageEnhance.Contrast(sonuc).enhance(teknikler["kontrast"])

    if teknikler.get("keskinlik") is not None:
        sonuc = ImageEnhance.Sharpness(sonuc).enhance(teknikler["keskinlik"])

    if teknikler.get("blur") is not None and teknikler["blur"] > 0:
        sonuc = sonuc.filter(ImageFilter.GaussianBlur(radius=teknikler["blur"]))

    if teknikler.get("golge") is not None and teknikler["golge"] > 0:
        sonuc = _golge_ekle(sonuc, teknikler["golge"])

    if teknikler.get("gurultu") is not None and teknikler["gurultu"] > 0:
        sonuc = _gurultu_ekle(sonuc, teknikler["gurultu"])

    # Sıkıştırma en SONDA uygulanmalı -- gerçek bir kamera/video kaydında
    # da JPEG sıkıştırması, tüm diğer optik/sensör bozulmalarından SONRA
    # (kayıt anında) devreye giriyor. Diğer tekniklerin bozduğu görsele
    # bunu en son uygulamak, gerçek dünya sırasını daha doğru taklit ediyor.
    if teknikler.get("sikistirma") is not None and teknikler["sikistirma"] > 0:
        sonuc = _sikistirma_uygula(sonuc, teknikler["sikistirma"])

    return sonuc


def _gurultu_ekle(img: Image.Image, siddet: float) -> Image.Image:
    """Piksellere Gaussian (normal dağılımlı) rastgele gürültü ekler --
    düşük ışıkta/gece çeken bir güvenlik kamerasının sensör gürültüsünü
    kabaca taklit eder. `siddet`, gürültünün standart sapması (0-255
    ölçeğinde) -- 0'a yakın neredeyse fark edilmez, 30-50 bandı belirgin
    "taneli" bir görünüm verir."""
    dizi = np.asarray(img, dtype=np.float32)
    gurultu = np.random.normal(0, siddet, dizi.shape).astype(np.float32)
    gurultulu = np.clip(dizi + gurultu, 0, 255).astype(np.uint8)
    return Image.fromarray(gurultulu, mode="RGB")


def _sikistirma_uygula(img: Image.Image, kalite: float) -> Image.Image:
    """Görseli bellekte JPEG olarak (verilen kalite ile) sıkıştırıp tekrar
    açar -- gerçek video/kamera kaydındaki (ve WhatsApp gibi
    uygulamaların yeniden sıkıştırmasındaki) bloklu/bulanık bozulmayı
    taklit eder. `kalite`: 1-100 arası JPEG kalite değeri -- DÜŞÜK değer
    DAHA FAZLA bozulma/artefakt demek (100 = neredeyse kayıpsız)."""
    kalite_int = int(max(1, min(100, round(kalite))))
    tampon = io.BytesIO()
    img.save(tampon, format="JPEG", quality=kalite_int)
    tampon.seek(0)
    with Image.open(tampon) as sikistirilmis:
        return sikistirilmis.convert("RGB").copy()


def _golge_ekle(img: Image.Image, opaklik: float) -> Image.Image:
    """Görselin rastgele bir kenarından başlayan, doğrusal bir gradyanla
    kararan bir 'gölge' efekti bindirir -- gerçek kamerada dal/direk/bina
    gölgesi düşmesini kabaca simüle eder. numpy ile vektörize edilmiş
    (piksel piksel Python döngüsü büyük görsellerde yavaş olurdu)."""
    genislik, yukseklik = img.size
    yon = random.choice(["sol", "sag", "ust", "alt"])

    if yon in ("sol", "sag"):
        oran = np.linspace(0, 1, genislik, dtype=np.float32)
        if yon == "sag":
            oran = 1 - oran
        oran_izgara = np.tile(oran, (yukseklik, 1))
    else:
        oran = np.linspace(0, 1, yukseklik, dtype=np.float32)
        if yon == "alt":
            oran = 1 - oran
        oran_izgara = np.tile(oran.reshape(-1, 1), (1, genislik))

    maske_dizisi = (255 * (1 - opaklik * (1 - oran_izgara))).clip(0, 255).astype(np.uint8)
    maske = Image.fromarray(maske_dizisi, mode="L")

    karanlik = Image.new("RGB", img.size, (0, 0, 0))
    return Image.composite(img, karanlik, maske)


AUGMENT_ONIZLEME_KLASORU = Path(__file__).resolve().parent / "static" / "augment_onizleme"
AUGMENT_ONIZLEME_MAKS_KENAR = 900  # önizleme hızlı olsun diye görsel bu boyuta küçültülüyor


@app.route("/api/augment/onizleme_gorsel", methods=["POST"])
def augment_onizleme_gorsel():
    """ÖNİZLE butonunun sadece sayı (kaç görsel etkilenecek) değil,
    GERÇEK bir örnek görsel üzerinde ayarların nasıl göründüğünü de
    gösterebilmesi için -- kullanıcı "absürt" bir değer girdiğinde
    (örn. blur=50) bunu sayılardan değil, doğrudan görselden anlayabilsin.
    Filtreyle eşleşen İLK görseli alıp hem orijinalini hem de o an
    seçili teknik ayarlarıyla işlenmiş halini kaydedip döndürür."""
    veri = request.get_json()
    gorsel_klasoru, etiket_klasoru, data_yaml_yolu = _augment_klasorleri_coz(
        veri.get("gorsel_klasoru", "").strip(),
        veri.get("etiket_klasoru", "").strip(),
        veri.get("data_yaml", "").strip(),
    )
    filtre = veri.get("filtre", "").strip()
    teknik_ayarlari = veri.get("teknikler", {})

    if not gorsel_klasoru.is_dir():
        return jsonify({"hata": f"Görsel klasörü bulunamadı: {gorsel_klasoru}"}), 400
    if not data_yaml_yolu.exists():
        return jsonify({"hata": f"data.yaml bulunamadı: {data_yaml_yolu}"}), 400

    siniflar = data_yaml_oku(data_yaml_yolu)
    ciftler = _gorselleri_filtrele(gorsel_klasoru, etiket_klasoru, siniflar, filtre)
    if not ciftler:
        return jsonify({"hata": "Filtreye uyan hiç görsel bulunamadı -- önizlenecek örnek yok."}), 400

    ornek_gorsel_yolu, _etiket_yolu = ciftler[0]

    aktif_teknikler = {k: v for k, v in teknik_ayarlari.items() if v.get("aktif")}
    teknik_degerleri = {}
    for ad, ayar in aktif_teknikler.items():
        # Önizleme her zaman "taban" değerini gösterir (dinamik modda
        # taban-hedef ARASI rastgele bir değer kullanılacağı için TEK bir
        # önizleme görseli o rastgeleliği zaten temsil edemez -- taban,
        # kullanıcının elle girdiği/gördüğü referans nokta).
        teknik_degerleri[ad] = float(ayar.get("taban", 1.0))

    AUGMENT_ONIZLEME_KLASORU.mkdir(parents=True, exist_ok=True)

    with Image.open(ornek_gorsel_yolu) as im:
        im = im.convert("RGB")
        im.thumbnail((AUGMENT_ONIZLEME_MAKS_KENAR, AUGMENT_ONIZLEME_MAKS_KENAR))
        im.save(AUGMENT_ONIZLEME_KLASORU / "orijinal.jpg", quality=90)
        filtreli = _augment_uygula(im, teknik_degerleri)
        filtreli.save(AUGMENT_ONIZLEME_KLASORU / "filtreli.jpg", quality=90)

    return jsonify({
        "ok": True,
        "orijinal_url": "/static/augment_onizleme/orijinal.jpg",
        "filtreli_url": "/static/augment_onizleme/filtreli.jpg",
        "ornek_gorsel_adi": ornek_gorsel_yolu.name,
        "aktif_teknik_yok": len(aktif_teknikler) == 0,
    })


@app.route("/api/augment/on_izle", methods=["POST"])
def augment_on_izle():
    veri = request.get_json()
    gorsel_klasoru, etiket_klasoru, data_yaml_yolu = _augment_klasorleri_coz(
        veri.get("gorsel_klasoru", "").strip(),
        veri.get("etiket_klasoru", "").strip(),
        veri.get("data_yaml", "").strip(),
    )
    filtre = veri.get("filtre", "").strip()

    if not gorsel_klasoru.is_dir():
        return jsonify({"hata": f"Görsel klasörü bulunamadı: {gorsel_klasoru}"}), 400
    if not data_yaml_yolu.exists():
        return jsonify({"hata": f"data.yaml bulunamadı: {data_yaml_yolu}"}), 400

    siniflar = data_yaml_oku(data_yaml_yolu)
    tum_ciftler = _gorselleri_filtrele(gorsel_klasoru, etiket_klasoru, siniflar, "")
    eslesen_ciftler = _gorselleri_filtrele(gorsel_klasoru, etiket_klasoru, siniflar, filtre)

    return jsonify({
        "toplam_etiketli": len(tum_ciftler),
        "filtreyle_eslesen": len(eslesen_ciftler),
        "siniflar": siniflar,
        "etiket_klasoru": str(etiket_klasoru),
        "data_yaml_yolu": str(data_yaml_yolu),
    })


@app.route("/api/augment/calistir", methods=["POST"])
def augment_calistir():
    veri = request.get_json()
    gorsel_klasoru, etiket_klasoru, data_yaml_yolu = _augment_klasorleri_coz(
        veri.get("gorsel_klasoru", "").strip(),
        veri.get("etiket_klasoru", "").strip(),
        veri.get("data_yaml", "").strip(),
    )
    filtre = veri.get("filtre", "").strip()
    mod = veri.get("mod", "sabit")  # "sabit" | "dinamik"
    teknik_ayarlari = veri.get("teknikler", {})
    # teknik_ayarlari: {"parlaklik": {"aktif": bool, "taban": float, "hedef": float}, ...}

    cikti_klasoru_str = veri.get("cikti_klasoru", "").strip()
    if not cikti_klasoru_str:
        return jsonify({"hata": "Çıktı klasörü hesaplanamadı."}), 400
    cikti_klasoru = Path(cikti_klasoru_str)

    if not gorsel_klasoru.is_dir():
        return jsonify({"hata": f"Görsel klasörü bulunamadı: {gorsel_klasoru}"}), 400
    if not data_yaml_yolu.exists():
        return jsonify({"hata": f"data.yaml bulunamadı: {data_yaml_yolu}"}), 400

    try:
        adet = max(1, int(veri.get("adet", 1)))
    except (TypeError, ValueError):
        adet = 1
    if mod == "sabit":
        adet = 1  # sabit modda her görselden tek bir çoğaltma üretilir

    aktif_teknikler = {k: v for k, v in teknik_ayarlari.items() if v.get("aktif")}
    if not aktif_teknikler:
        return jsonify({"hata": "En az bir augment tekniği seçmelisin (parlaklık/kontrast/keskinlik/blur/gölge/gürültü/sıkıştırma)."}), 400

    # Dosya adına hangi tekniklerin uygulandığını da ekliyoruz -- yoksa
    # (bir bug olarak yaşadığımız gibi) aynı çıktı klasörüne önce "sadece
    # blur", sonra "sadece parlaklık" ile ayrı ayrı çalıştırınca, ikisi de
    # aynı "_aug.jpg" adını ürettiği için ikincisi birincinin üzerine
    # sessizce yazıyordu. Artık "_augp" (parlaklık), "_augb" (blur) gibi
    # farklı adlar üretildiği için aynı klasörde çakışmadan bir arada durabilirler.
    TEKNIK_KISALTMA = {
        "parlaklik": "p", "keskinlik": "k", "blur": "b", "golge": "g",
        "kontrast": "c", "gurultu": "n", "sikistirma": "s",
    }
    teknik_etiketi = "".join(TEKNIK_KISALTMA.get(ad, ad[:1]) for ad in sorted(aktif_teknikler.keys()))

    siniflar = data_yaml_oku(data_yaml_yolu)
    ciftler = _gorselleri_filtrele(gorsel_klasoru, etiket_klasoru, siniflar, filtre)

    if not ciftler:
        return jsonify({"hata": "Filtreye uyan hiç görsel bulunamadı."}), 400

    cikti_gorsel = cikti_klasoru / "images"
    cikti_etiket = cikti_klasoru / "labels"
    cikti_gorsel.mkdir(parents=True, exist_ok=True)
    cikti_etiket.mkdir(parents=True, exist_ok=True)

    sinif_once = defaultdict(int)
    sinif_sonra = defaultdict(int)
    uretilen_toplam = 0

    for gorsel_yolu, etiket_yolu in ciftler:
        for i in _etiketteki_sinif_idleri(etiket_yolu):
            if 0 <= i < len(siniflar):
                sinif_once[siniflar[i]] += 1

        with Image.open(gorsel_yolu) as im:
            for tekrar in range(adet):
                teknik_degerleri = {}
                for ad, ayar in aktif_teknikler.items():
                    taban = float(ayar.get("taban", 1.0))
                    hedef = float(ayar.get("hedef", taban))
                    teknik_degerleri[ad] = taban if mod == "sabit" else _rastgele_arada(taban, hedef)

                yeni_img = _augment_uygula(im, teknik_degerleri)

                ek = f"_aug{teknik_etiketi}{tekrar + 1}" if adet > 1 else f"_aug{teknik_etiketi}"
                yeni_ad = f"{gorsel_yolu.stem}{ek}{gorsel_yolu.suffix}"
                yeni_etiket_ad = f"{gorsel_yolu.stem}{ek}.txt"

                yeni_img.save(cikti_gorsel / yeni_ad)
                if etiket_yolu is not None:
                    shutil.copy2(etiket_yolu, cikti_etiket / yeni_etiket_ad)
                else:
                    # Kaynak görselin hiç etiketi yoktu (nevfel.txt'nin
                    # istediği "sadece images + data.yaml" girdi modu) --
                    # YOLO kuralına göre "bu görselde nesne yok" boş bir
                    # .txt dosyasıyla temsil edilir.
                    (cikti_etiket / yeni_etiket_ad).write_text("", encoding="utf-8")

                uretilen_toplam += 1
                for i in _etiketteki_sinif_idleri(etiket_yolu):
                    if 0 <= i < len(siniflar):
                        sinif_sonra[siniflar[i]] += 1

    yeni_data_yaml = cikti_klasoru / "data.yaml"
    # NOT: 'path' anahtarını BİLEREK yazmıyoruz -- bkz. data_yaml_yaz()'daki
    # yorum.
    icerik = {
        "train": "images",
        "val": "images",
        "test": "images",
        "names": {i: isim for i, isim in enumerate(siniflar)},
    }
    with open(yeni_data_yaml, "w", encoding="utf-8") as f:
        yaml.safe_dump(icerik, f, allow_unicode=True, sort_keys=False)

    analiz_satirlari = [
        "=" * 80,
        "DATA AUGMENT RAPORU",
        "=" * 80,
        "",
        f"Mod: {mod}",
        f"Filtre: {filtre or '(yok, tüm etiketli görseller)'}",
        f"İşlenen kaynak görsel: {len(ciftler)}",
        f"Üretilen yeni görsel: {uretilen_toplam}",
        "",
        "Class bazında yeni üretilen etiket sayısı:",
        "-" * 40,
    ]
    for isim in siniflar:
        analiz_satirlari.append(f"  {isim:<24}{sinif_sonra.get(isim, 0):>8}")
    analiz_metni = "\n".join(analiz_satirlari) + "\n"
    (cikti_klasoru / "analiz.txt").write_text(analiz_metni, encoding="utf-8")

    return jsonify({
        "ok": True,
        "cikti_klasoru": str(cikti_klasoru),
        "data_yaml_yolu": str(yeni_data_yaml),
        "islenen": len(ciftler),
        "uretilen": uretilen_toplam,
        "analiz": analiz_metni,
    })


# ============================================================
# VİDEO'DAN KARE ÇIKARMA (yardımcı araç, kod/05_video_kare_cikar.py ile
# AYNI mantık -- CLI'ye ek olarak GUI'den de kolay kullanılsın diye).
# Bir videodan seyrek aralıklarla (varsayılan fps=1) kare çıkarıp .jpg
# olarak kaydeder -- amaç, vlog/dashcam/kendi video kayıtlarından Ön-
# Etiketleme/Etiketleme arayüzüne girecek ham görselleri üretmek.
#
# İZOLE BİR BÖLÜM: gerekirse ileride bu bölümü (route'lar + template +
# JS + hub kartı) kaldırmak, başka hiçbir şeyi bozmadan mümkün olsun diye
# kendi başına duruyor, başka hiçbir DURUM/global state'e dokunmuyor.
# ============================================================

@app.route("/karecikar")
def karecikar_sayfasi():
    return render_template("karecikar.html")


@app.route("/api/karecikar/calistir", methods=["POST"])
def karecikar_calistir():
    try:
        import imageio_ffmpeg
    except ImportError:
        return jsonify({"hata": "imageio-ffmpeg kurulu değil. Kurmak için: pip install imageio-ffmpeg"}), 400

    veri = request.get_json()
    video_yolu_str = veri.get("video_yolu", "").strip()
    cikti_klasoru_str = veri.get("cikti_klasoru", "").strip()
    try:
        fps = float(veri.get("fps", 1))
    except (TypeError, ValueError):
        fps = 1.0

    if not video_yolu_str or not Path(video_yolu_str).exists():
        return jsonify({"hata": f"Video bulunamadı: {video_yolu_str}"}), 400
    if not cikti_klasoru_str:
        return jsonify({"hata": "Çıktı klasörü hesaplanamadı."}), 400
    if fps <= 0:
        return jsonify({"hata": "fps 0'dan büyük olmalı."}), 400

    video_yolu = Path(video_yolu_str)
    cikti_klasoru = Path(cikti_klasoru_str)
    cikti_klasoru.mkdir(parents=True, exist_ok=True)

    video_adi = video_yolu.stem
    desen = str(cikti_klasoru / f"{video_adi}_kare_%04d.jpg")

    ffmpeg_yolu = imageio_ffmpeg.get_ffmpeg_exe()
    komut = [
        ffmpeg_yolu, "-y",
        "-i", str(video_yolu),
        "-vf", f"fps={fps}",
        "-q:v", "2",
        desen,
    ]

    try:
        sonuc = subprocess.run(komut, capture_output=True, text=True, timeout=600)
    except subprocess.TimeoutExpired:
        return jsonify({"hata": "ffmpeg zaman aşımına uğradı (10 dakika) -- video çok uzun olabilir."}), 500

    if sonuc.returncode != 0:
        return jsonify({"hata": f"ffmpeg başarısız oldu: {sonuc.stderr[-1500:]}"}), 500

    uretilen = sorted(cikti_klasoru.glob(f"{video_adi}_kare_*.jpg"))
    return jsonify({
        "ok": True,
        "cikti_klasoru": str(cikti_klasoru),
        "uretilen": len(uretilen),
    })


# ============================================================
# VERİ BİRLEŞTİR (yardımcı araç, kod/04_veri_birlestir.py ile AYNI mantık
# -- CLI'ye ek olarak GUI'den de kolay kullanılsın diye). Sınıf başına
# ayrı toplanan (etiketleme sırasında oluşan) klasörleri, SADECE
# ETİKETLENMİŞ görselleri sınıf adı ön ekiyle tek bir images/+labels/
# yapısına (eğitime hazır) kopyalar. Orijinal klasörlere dokunmaz
# (kopyalar, taşımaz) -- tekrar çalıştırınca sadece yenileri ekler.
#
# İZOLE BİR BÖLÜM: gerekirse ileride kaldırmak, başka hiçbir şeyi
# bozmadan mümkün olsun diye kendi başına duruyor.
# ============================================================

GORSEL_UZANTILARI_BIRLESTIR = GORSEL_UZANTILARI  # aynı liste, ayrı isimle referans


def _birlestir_etiket_klasorunu_bul(gorsel_klasoru: Path) -> Path:
    if gorsel_klasoru.name == "images":
        return gorsel_klasoru.parent / "labels"
    return gorsel_klasoru.parent / "labels" / gorsel_klasoru.name


def _birlestir_eski_flat_etiket_klasoru(gorsel_klasoru: Path) -> Path:
    return gorsel_klasoru.parent / "labels"


def _birlestir_etiket_dosyasini_bul(gorsel: Path, yeni_etiket_klasoru: Path, eski_etiket_klasoru: Path):
    yeni = yeni_etiket_klasoru / (gorsel.stem + ".txt")
    if yeni.exists() and yeni.stat().st_size > 0:
        return yeni
    eski = eski_etiket_klasoru / (gorsel.stem + ".txt")
    if eski.exists() and eski.stat().st_size > 0:
        return eski
    return None


@app.route("/veribirlestir")
def veribirlestir_sayfasi():
    return render_template("veribirlestir.html")


@app.route("/api/veribirlestir/calistir", methods=["POST"])
def veribirlestir_calistir():
    veri = request.get_json()
    kaynak_klasorler_str = veri.get("kaynak_klasorler", [])
    cikti_klasoru_str = veri.get("cikti_klasoru", "").strip()

    if not kaynak_klasorler_str:
        return jsonify({"hata": "En az bir kaynak klasör eklemelisin."}), 400
    if not cikti_klasoru_str:
        return jsonify({"hata": "Çıktı klasörü seçmelisin."}), 400

    cikti_klasoru = Path(cikti_klasoru_str)
    hedef_gorsel = cikti_klasoru / "images"
    hedef_etiket = cikti_klasoru / "labels"
    hedef_gorsel.mkdir(parents=True, exist_ok=True)
    hedef_etiket.mkdir(parents=True, exist_ok=True)

    sonuclar = []
    toplam_kopyalanan = 0
    toplam_zaten_var = 0
    toplam_etiketsiz = 0

    for kaynak_str in kaynak_klasorler_str:
        sinif_klasoru = Path(kaynak_str)
        if not sinif_klasoru.is_dir():
            sonuclar.append({"sinif": sinif_klasoru.name, "hata": f"Klasör bulunamadı: {kaynak_str}"})
            continue

        sinif_adi = sinif_klasoru.name
        yeni_etiket_klasoru = _birlestir_etiket_klasorunu_bul(sinif_klasoru)
        eski_etiket_klasoru = _birlestir_eski_flat_etiket_klasoru(sinif_klasoru)

        gorseller = [p for p in sinif_klasoru.iterdir() if p.suffix.lower() in GORSEL_UZANTILARI_BIRLESTIR]

        kopyalanan = 0
        etiketsiz = 0
        zaten_var = 0

        for gorsel in gorseller:
            kaynak_etiket = _birlestir_etiket_dosyasini_bul(gorsel, yeni_etiket_klasoru, eski_etiket_klasoru)
            if kaynak_etiket is None:
                etiketsiz += 1
                continue

            yeni_ad = f"{sinif_adi}_{gorsel.name}"
            yeni_etiket_ad = f"{sinif_adi}_{gorsel.stem}.txt"
            hedef_gorsel_yolu = hedef_gorsel / yeni_ad
            hedef_etiket_yolu = hedef_etiket / yeni_etiket_ad

            if hedef_gorsel_yolu.exists() and hedef_etiket_yolu.exists():
                zaten_var += 1
                continue

            shutil.copy2(gorsel, hedef_gorsel_yolu)
            shutil.copy2(kaynak_etiket, hedef_etiket_yolu)
            kopyalanan += 1

        sonuclar.append({
            "sinif": sinif_adi,
            "kaynak": str(sinif_klasoru),
            "toplam": len(gorseller),
            "kopyalanan": kopyalanan,
            "zaten_var": zaten_var,
            "etiketsiz_atlandi": etiketsiz,
        })
        toplam_kopyalanan += kopyalanan
        toplam_zaten_var += zaten_var
        toplam_etiketsiz += etiketsiz

    return jsonify({
        "ok": True,
        "sonuclar": sonuclar,
        "toplam_kopyalanan": toplam_kopyalanan,
        "toplam_zaten_var": toplam_zaten_var,
        "toplam_etiketsiz": toplam_etiketsiz,
        "cikti_klasoru": str(cikti_klasoru),
    })


# ============================================================
# ÖN-ETİKETLEME (yardımcı araç -- nevfel.txt'nin zorunlu maddelerinden
# biri değil, ama elle kutu çizme işini hızlandırmak için eklendi).
#
# Fikir: bir klasördeki TÜM görsellerin aynı class'a ait olduğunu zaten
# biliyorsun (örn. "bu klasördeki hepsi fiat_egea"). Hazır bir modelin
# (varsayılan: yolo11n.pt, COCO ile eğitilmiş -- "araba" kavramını
# zaten biliyor) her görselde aracın nerede olduğunu (kutu) BULMASINI
# sağlayıp, o kutuya senin verdiğin class adını OTOMATİK yazıyoruz.
# Elle kutu çizme işini ortadan kaldırıyor; sen sadece Etiketleme
# arayüzünden açıp yanlış/eksik olanları düzeltiyorsun.
#
# ÖNEMLİ SINIRLAMA: bu, TEK ARAÇ net görünen fotoğraflarda (katalog
# fotoğrafı, video karesi vb.) güvenli çalışır. Kalabalık bir sahnede
# (örn. otopark, birden fazla araç) hangi kutunun senin dediğin class'a
# ait olduğunu bilemez -- "sadece en büyük kutu" seçeneği bunun için
# var (kadrajdaki en büyük/en yakın aracı hedef class say, diğerlerini
# atla), ama yine de üretilen etiketler MUTLAKA Etiketleme arayüzünden
# gözden geçirilmeli.
#
# Hangi kaynak class'ların "hedef nesne" sayılacağını class ADINA göre
# (id'ye göre değil) buluyoruz -- böylece hem standart COCO modellerinde
# hem de farklı class sırasına sahip başka modellerde doğru çalışır.
# ÖNEMLİ (genel araç için): bu kaynak class listesi ARTIK SABİT DEĞİL --
# kullanıcı arayüzden hangi kaynak class'ı (ör. "car,truck,bus" ya da
# "person" ya da "dog,cat") arayacağını kendisi giriyor. Hiç girmezse
# (boş bırakırsa) hiç filtre uygulanmaz, modelin bulduğu en güvenilir
# kutu direkt kullanılır -- bu, "sadece araç" varsayımını kaldırıp aracı
# GERÇEKTEN herhangi bir YOLO (detect) projesi için kullanılabilir hale
# getiriyor.
# ============================================================

ONETIKET_MODEL_ONBELLEK = {}


def _onetiket_modelini_yukle(model_yolu: str):
    from ultralytics import YOLO

    with MODEL_ONBELLEK_KILIDI:
        if model_yolu not in ONETIKET_MODEL_ONBELLEK:
            ONETIKET_MODEL_ONBELLEK.clear()
            ONETIKET_MODEL_ONBELLEK[model_yolu] = YOLO(model_yolu)
    return ONETIKET_MODEL_ONBELLEK[model_yolu]


def _kaynak_class_idlerini_bul(model, hedef_adlar: list[str]) -> list[int]:
    """Kullanıcının verdiği kaynak class adlarını (ör. ["car","truck"])
    modelin kendi class isim listesinde (büyük/küçük harf duyarsız) arar,
    eşleşen id'leri döndürür. hedef_adlar boşsa [] döner -- bu, arayan
    kodda "hiç filtre uygulama" anlamına gelir (en güvenilir kutuyu al)."""
    if not hedef_adlar:
        return []
    hedefler = {ad.strip().lower() for ad in hedef_adlar if ad.strip()}
    if not hedefler:
        return []
    return [i for i, ad in model.names.items() if str(ad).lower() in hedefler]


@app.route("/onetiketleme")
def onetiketleme_sayfasi():
    return render_template("onetiketleme.html")


@app.route("/api/onetiket/on_izle", methods=["POST"])
def onetiket_on_izle():
    veri = request.get_json()
    gorsel_klasoru, etiket_klasoru, data_yaml_yolu = _girdi_klasorlerini_coz(
        veri.get("gorsel_klasoru", "").strip(),
        veri.get("etiket_klasoru", "").strip(),
        veri.get("data_yaml", "").strip(),
    )

    if not gorsel_klasoru.is_dir():
        return jsonify({"hata": f"Görsel klasörü bulunamadı: {gorsel_klasoru}"}), 400

    siniflar = data_yaml_oku(data_yaml_yolu) if data_yaml_yolu.exists() else []
    gorseller = [p for p in gorsel_klasoru.iterdir() if p.suffix.lower() in GORSEL_UZANTILARI]

    etiketli = 0
    etiketsiz = 0
    for g in gorseller:
        etiket = etiket_klasoru / (g.stem + ".txt")
        if etiket.exists() and etiket.stat().st_size > 0:
            etiketli += 1
        else:
            etiketsiz += 1

    return jsonify({
        "toplam_gorsel": len(gorseller),
        "etiketli": etiketli,
        "etiketsiz": etiketsiz,
        "siniflar": siniflar,
        "etiket_klasoru": str(etiket_klasoru),
        "data_yaml_yolu": str(data_yaml_yolu),
    })


@app.route("/api/onetiket/calistir", methods=["POST"])
def onetiket_calistir():
    veri = request.get_json()
    gorsel_klasoru, etiket_klasoru, data_yaml_yolu = _girdi_klasorlerini_coz(
        veri.get("gorsel_klasoru", "").strip(),
        veri.get("etiket_klasoru", "").strip(),
        veri.get("data_yaml", "").strip(),
    )
    hedef_class = veri.get("hedef_class", "").strip()
    model_yolu = veri.get("model_dosyasi", "").strip() or "yolo11n.pt"
    # Kaynak class filtresi -- boş bırakılırsa modelin bulduğu en
    # güvenilir kutu direkt kullanılır (eski davranış). Doldurulursa
    # (ör. "car,truck,bus" ya da "person") SADECE bu class'lardaki
    # kutular arasından seçim yapılır -- bu proje sadece araç için değil,
    # kullanıcı hangi kaynak class'ı hedef alacağını kendisi belirliyor.
    kaynak_class_ham = veri.get("kaynak_class", "").strip()
    kaynak_class_adlari = [ad for ad in kaynak_class_ham.split(",") if ad.strip()] if kaynak_class_ham else []
    try:
        conf = float(veri.get("conf", 0.35))
    except (TypeError, ValueError):
        conf = 0.35
    sadece_en_buyuk = bool(veri.get("sadece_en_buyuk", True))
    uzerine_yaz = bool(veri.get("uzerine_yaz", False))

    if not gorsel_klasoru.is_dir():
        return jsonify({"hata": f"Görsel klasörü bulunamadı: {gorsel_klasoru}"}), 400
    if not hedef_class:
        return jsonify({"hata": "Hedef class adı girmelisin (örn. fiat_egea)."}), 400

    mevcut_siniflar = data_yaml_oku(data_yaml_yolu) if data_yaml_yolu.exists() else []

    # Aynı "sessizce yeni class ekleme" güvenlik kuralı -- bkz. /api/yukle.
    if hedef_class not in mevcut_siniflar:
        if not veri.get("onay"):
            return jsonify({
                "onay_gerekli": True,
                "yeni_class": hedef_class,
                "mevcut_siniflar": mevcut_siniflar,
            })
        siniflar = mevcut_siniflar + [hedef_class]
        if data_yaml_yolu.exists():
            data_yaml_sinif_guncelle(data_yaml_yolu, siniflar)
        else:
            data_yaml_yaz(data_yaml_yolu, gorsel_klasoru, siniflar)
    else:
        siniflar = mevcut_siniflar

    hedef_id = siniflar.index(hedef_class)

    try:
        model = _onetiket_modelini_yukle(model_yolu)
    except Exception as e:
        return jsonify({"hata": f"Model yüklenemedi: {e}"}), 400

    kaynak_idleri = _kaynak_class_idlerini_bul(model, kaynak_class_adlari)
    if kaynak_class_adlari and not kaynak_idleri:
        log_uyarisi = (
            f"[uyarı] Girilen kaynak class adları ({', '.join(kaynak_class_adlari)}) "
            f"modelin class listesinde bulunamadı -- filtre uygulanmadan devam ediliyor."
        )
    else:
        log_uyarisi = None

    etiket_klasoru.mkdir(parents=True, exist_ok=True)
    gorseller = sorted(p for p in gorsel_klasoru.iterdir() if p.suffix.lower() in GORSEL_UZANTILARI)

    yazilan = 0
    atlanan_zaten_etiketli = 0
    tespit_yok = 0

    for gorsel_yolu in gorseller:
        etiket_yolu = etiket_klasoru / (gorsel_yolu.stem + ".txt")
        if etiket_yolu.exists() and etiket_yolu.stat().st_size > 0 and not uzerine_yaz:
            atlanan_zaten_etiketli += 1
            continue

        try:
            tahmin_kwargs = {"source": str(gorsel_yolu), "conf": conf, "verbose": False}
            if kaynak_idleri:
                tahmin_kwargs["classes"] = kaynak_idleri
            sonuclar = model.predict(**tahmin_kwargs)
        except Exception:
            tespit_yok += 1
            continue

        kutular = sonuclar[0].boxes
        if kutular is None or len(kutular) == 0:
            tespit_yok += 1
            continue

        xywhn = kutular.xywhn.cpu().numpy()  # normalize edilmiş cx, cy, w, h
        if sadece_en_buyuk:
            alanlar = xywhn[:, 2] * xywhn[:, 3]
            secilenler = [xywhn[alanlar.argmax()]]
        else:
            secilenler = list(xywhn)

        satirlar = [
            f"{hedef_id} {cx:.6f} {cy:.6f} {w:.6f} {h:.6f}"
            for cx, cy, w, h in secilenler
        ]
        with open(etiket_yolu, "w", encoding="utf-8") as f:
            f.write("\n".join(satirlar) + "\n")
        yazilan += 1

    return jsonify({
        "ok": True,
        "yazilan": yazilan,
        "atlanan_zaten_etiketli": atlanan_zaten_etiketli,
        "tespit_yok": tespit_yok,
        "toplam_gorsel": len(gorseller),
        "etiket_klasoru": str(etiket_klasoru),
        "data_yaml_yolu": str(data_yaml_yolu),
        "hedef_class": hedef_class,
        "hedef_id": hedef_id,
        "kaynak_class_uyarisi": log_uyarisi,
    })


# ============================================================
# MODEL EĞİTİMİ (nevfel.txt madde 4)
# Girdi: bir başlangıç modeli (yolo11n.pt / yolo11n-seg.pt / yolo11n-pose.pt
# ya da devam etmek istediğin bir last.pt/best.pt) + data.yaml + eğitim
# parametreleri. Eğitim ARKA PLAN THREAD'İNDE çalışır (Flask'ı kilitlemesin
# diye), ultralytics'in callback mekanizmasıyla her epoch sonunda metrikler
# yakalanıp EGITIM_DURUMU içine yazılır, frontend bunu düzenli aralıklarla
# (polling) okuyup "terminal" gibi bir kutuda gösterir.
#
# ultralytics/torch import'u BURADA (fonksiyon içinde, modül başında değil)
# yapılıyor -- çünkü bu ağır bir bağımlılık, sadece etiketleme/splitter/
# augment kullanan biri bunu kurmamış olabilir, modül başında import etsek
# ultralytics kurulu değilse UYGULAMA HİÇ AÇILMAZDI.
# ============================================================

EGITIM_DURUMU = {
    "calisiyor": False,
    "tamamlandi": False,
    "hata": None,
    "loglar": [],
    "son_metrikler": {},
    "epoch": 0,
    "toplam_epoch": 0,
    "en_iyi_model_yolu": None,
    "son_calisma_klasoru": None,
}

EGITIM_KILIDI = threading.Lock()


def _egitim_logla(satir: str):
    with EGITIM_KILIDI:
        EGITIM_DURUMU["loglar"].append(satir)
        # Çok uzamasın diye son 500 satırla sınırlıyoruz
        if len(EGITIM_DURUMU["loglar"]) > 500:
            EGITIM_DURUMU["loglar"] = EGITIM_DURUMU["loglar"][-500:]


def _egitimi_baslat_arka_planda(ayarlar: dict):
    try:
        from ultralytics import YOLO
    except ImportError:
        EGITIM_DURUMU["hata"] = (
            "ultralytics kurulu değil. Kurmak için: pip install ultralytics "
            "(GPU kullanacaksan önce PyTorch'u CUDA'lı sürümüyle kurman gerekebilir, "
            "bkz. bilgi_notlari/)."
        )
        EGITIM_DURUMU["calisiyor"] = False
        return

    try:
        def epoch_bitince(trainer):
            metrikler = {}
            for k, v in (trainer.metrics or {}).items():
                try:
                    metrikler[k] = float(v)
                except (TypeError, ValueError):
                    pass
            EGITIM_DURUMU["son_metrikler"] = metrikler
            EGITIM_DURUMU["epoch"] = trainer.epoch + 1
            EGITIM_DURUMU["toplam_epoch"] = trainer.epochs
            ozet = ", ".join(f"{k}={v:.4f}" for k, v in metrikler.items())
            _egitim_logla(f"[epoch {trainer.epoch + 1}/{trainer.epochs}] {ozet}")

        if ayarlar.get("mod") == "devam":
            # RESUME: last.pt'nin yanındaki (aynı run klasöründeki) args.yaml
            # ultralytics tarafından otomatik okunuyor -- data.yaml, epochs,
            # augmentation ayarları dahil TÜM ayarlar o eğitimin kendi
            # kaydettiği haliyle aynen kullanılıyor, biz burada başka hiçbir
            # parametre GEÇMİYORUZ (geçersek çakışma/hata riski var).
            _egitim_logla(f"last.pt yükleniyor (devam): {ayarlar['last_pt_dosyasi']}")
            model = YOLO(ayarlar["last_pt_dosyasi"])
            model.add_callback("on_fit_epoch_end", epoch_bitince)
            _egitim_logla("Eğitime kaldığı yerden devam ediliyor...")
            model.train(resume=True)
        else:
            _egitim_logla(f"Model yükleniyor: {ayarlar['model_dosyasi']}")
            model = YOLO(ayarlar["model_dosyasi"])
            model.add_callback("on_fit_epoch_end", epoch_bitince)

            _egitim_logla("Eğitim başlıyor...")
            model.train(
                data=ayarlar["data_yaml"],
                epochs=ayarlar["epochs"],
                imgsz=ayarlar["imgsz"],
                batch=ayarlar["batch"],
                patience=ayarlar["patience"],
                optimizer=ayarlar["optimizer"],
                device=ayarlar["device"] or None,
                project=ayarlar["proje_klasoru"],
                name=ayarlar["calisma_adi"],
                exist_ok=True,
                # --- Gelişmiş ayarlar (loss ağırlıkları + augmentation) ---
                # Varsayılanları ultralytics'in kendi varsayılanlarıyla AYNI --
                # kullanıcı arayüzde hiçbirine dokunmazsa davranış değişmez.
                cls=ayarlar["cls"],
                box=ayarlar["box"],
                dfl=ayarlar["dfl"],
                fl_gamma=ayarlar["fl_gamma"],
                mosaic=ayarlar["mosaic"],
                erasing=ayarlar["erasing"],
                hsv_h=ayarlar["hsv_h"],
                hsv_s=ayarlar["hsv_s"],
                hsv_v=ayarlar["hsv_v"],
                degrees=ayarlar["degrees"],
                translate=ayarlar["translate"],
                scale=ayarlar["scale"],
                shear=ayarlar["shear"],
                perspective=ayarlar["perspective"],
                flipud=ayarlar["flipud"],
                fliplr=ayarlar["fliplr"],
                mixup=ayarlar["mixup"],
                copy_paste=ayarlar["copy_paste"],
                cutmix=ayarlar["cutmix"],
                bgr=ayarlar["bgr"],
                close_mosaic=ayarlar["close_mosaic"],
                multi_scale=ayarlar["multi_scale"],
                freeze=ayarlar["freeze"],
            )

        egitmen = model.trainer
        en_iyi = Path(egitmen.save_dir) / "weights" / "best.pt"
        EGITIM_DURUMU["en_iyi_model_yolu"] = str(en_iyi) if en_iyi.exists() else None
        EGITIM_DURUMU["son_calisma_klasoru"] = str(egitmen.save_dir)
        _egitim_logla(f"Eğitim tamamlandı. En iyi model: {EGITIM_DURUMU['en_iyi_model_yolu']}")
        EGITIM_DURUMU["tamamlandi"] = True

    except Exception as e:
        EGITIM_DURUMU["hata"] = str(e)
        _egitim_logla(f"HATA: {e}")
        _egitim_logla(traceback.format_exc())

    finally:
        EGITIM_DURUMU["calisiyor"] = False


@app.route("/api/egitim/baslat", methods=["POST"])
def egitim_baslat():
    with EGITIM_KILIDI:
        if EGITIM_DURUMU["calisiyor"]:
            return jsonify({"hata": "Zaten devam eden bir eğitim var. Bitmesini bekle."}), 400

        veri = request.get_json()
        mod = veri.get("mod", "yeni")

        if mod == "devam":
            last_pt_dosyasi = veri.get("last_pt_dosyasi", "").strip()
            if not last_pt_dosyasi or not Path(last_pt_dosyasi).exists():
                return jsonify({"hata": f"last.pt bulunamadı: {last_pt_dosyasi}"}), 400
            ayarlar = {"mod": "devam", "last_pt_dosyasi": last_pt_dosyasi}
            hedef_epochs = 0  # bilinmiyor, resume kendi kayıtlı hedefini kullanacak

        else:
            model_dosyasi = veri.get("model_dosyasi", "").strip()
            data_yaml = veri.get("data_yaml", "").strip()
            proje_klasoru = veri.get("proje_klasoru", "").strip()
            calisma_adi = veri.get("calisma_adi", "").strip() or "egitim1"

            if not model_dosyasi:
                return jsonify({"hata": "Başlangıç modeli seçmelisin (örn. yolo11n.pt)."}), 400
            if not data_yaml or not Path(data_yaml).exists():
                return jsonify({"hata": f"data.yaml bulunamadı: {data_yaml}"}), 400
            if not proje_klasoru:
                return jsonify({"hata": "Çıktı (run) klasörü seçmelisin."}), 400

            # Gelişmiş ayarlar -- kullanıcı arayüzde değiştirmediyse ultralytics'in
            # KENDİ varsayılanlarıyla aynı değerler geliyor (bkz. egitim.html),
            # yani burada float(...) ile okumak davranışı hiç değiştirmiyor.
            try:
                ayarlar = {
                    "mod": "yeni",
                    "model_dosyasi": model_dosyasi,
                    "data_yaml": data_yaml,
                    "epochs": int(veri.get("epochs", 100)),
                    "imgsz": int(veri.get("imgsz", 640)),
                    "batch": int(veri.get("batch", 16)),
                    "patience": int(veri.get("patience", 100)),
                    "optimizer": veri.get("optimizer", "auto") or "auto",
                    "device": veri.get("device", "").strip(),
                    "proje_klasoru": proje_klasoru,
                    "calisma_adi": calisma_adi,
                    "cls": float(veri.get("cls", 0.5)),
                    "box": float(veri.get("box", 7.5)),
                    "dfl": float(veri.get("dfl", 1.5)),
                    "fl_gamma": float(veri.get("fl_gamma", 0.0)),
                    "mosaic": float(veri.get("mosaic", 1.0)),
                    "erasing": float(veri.get("erasing", 0.4)),
                    "hsv_h": float(veri.get("hsv_h", 0.015)),
                    "hsv_s": float(veri.get("hsv_s", 0.7)),
                    "hsv_v": float(veri.get("hsv_v", 0.4)),
                    "degrees": float(veri.get("degrees", 0.0)),
                    "translate": float(veri.get("translate", 0.1)),
                    "scale": float(veri.get("scale", 0.5)),
                    "shear": float(veri.get("shear", 0.0)),
                    "perspective": float(veri.get("perspective", 0.0)),
                    "flipud": float(veri.get("flipud", 0.0)),
                    "fliplr": float(veri.get("fliplr", 0.5)),
                    "mixup": float(veri.get("mixup", 0.0)),
                    "copy_paste": float(veri.get("copy_paste", 0.0)),
                    "cutmix": float(veri.get("cutmix", 0.0)),
                    "bgr": float(veri.get("bgr", 0.0)),
                    "close_mosaic": int(veri.get("close_mosaic", 10)),
                    "multi_scale": bool(veri.get("multi_scale", False)),
                    "freeze": (
                        int(veri["freeze"])
                        if str(veri.get("freeze", "")).strip() != ""
                        else None
                    ),
                }
            except (TypeError, ValueError):
                return jsonify({"hata": "Parametrelerden biri sayısal olmalı."}), 400
            hedef_epochs = ayarlar["epochs"]

        EGITIM_DURUMU.update({
            "calisiyor": True,
            "tamamlandi": False,
            "hata": None,
            "loglar": [],
            "son_metrikler": {},
            "epoch": 0,
            "toplam_epoch": hedef_epochs,
            "en_iyi_model_yolu": None,
            "son_calisma_klasoru": None,
        })

        thread = threading.Thread(target=_egitimi_baslat_arka_planda, args=(ayarlar,), daemon=True)
        thread.start()

    return jsonify({"ok": True})


@app.route("/api/egitim/durum")
def egitim_durum():
    # Arka plan thread'i EGITIM_DURUMU'nu (özellikle "loglar" listesini)
    # sürekli güncellerken jsonify aynı anda serialize etmeye çalışırsa
    # (nadir de olsa) tutarsız/hatalı bir çıktı riski var -- kilit altında
    # sığ bir kopya alıp onu döndürüyoruz.
    with EGITIM_KILIDI:
        kopya = dict(EGITIM_DURUMU)
        kopya["loglar"] = list(EGITIM_DURUMU.get("loglar", []))
    return jsonify(kopya)


# Eğitim bitince ultralytics'in kendi kaydettiği sonuç grafiklerini (results.png,
# confusion_matrix.png) tarayıcıya göstermek için -- klasör EGITIM_DURUMU'ndan
# geliyor (kullanıcının seçmediği, ultralytics'in otomatik oluşturduğu bir yer),
# dosya adı ise sabit bir izin listesiyle sınırlı (keyfi dosya okumayı önlemek için).
EGITIM_GRAFIK_IZIN_LISTESI = {"results.png", "confusion_matrix.png", "confusion_matrix_normalized.png"}


@app.route("/api/egitim/grafik/<dosya_adi>")
def egitim_grafik(dosya_adi):
    klasor = EGITIM_DURUMU.get("son_calisma_klasoru")
    if not klasor or dosya_adi not in EGITIM_GRAFIK_IZIN_LISTESI:
        return jsonify({"hata": "Grafik bulunamadı."}), 404
    tam_yol = Path(klasor) / dosya_adi
    if not tam_yol.exists():
        return jsonify({"hata": "Grafik bulunamadı."}), 404
    return send_from_directory(klasor, dosya_adi)


# ============================================================
# MODEL TEST (nevfel.txt madde 5) -- şimdilik GÖRSEL modu.
# Video ve webcam modları ayrı adımlarda eklenecek (adım adım plan).
# Eğitilmiş bir modeli (best.pt gibi) seçip bir görsel üzerinde çalıştırır,
# tespit edilen kutuları + sınıf adı/güven skorunu çizer, üstüne bir de
# fps/süre bilgisi (HUD) ekler.
# ============================================================

TEST_MODEL_ONBELLEK = {}  # {model_yolu: YOLO nesnesi} -- her seferinde yeniden yüklememek için
TEST_CIKTI_KLASORU = Path(__file__).resolve().parent / "static" / "test_ciktilari"


def _test_modelini_yukle(model_yolu: str):
    from ultralytics import YOLO

    with MODEL_ONBELLEK_KILIDI:
        if model_yolu not in TEST_MODEL_ONBELLEK:
            TEST_MODEL_ONBELLEK.clear()  # aynı anda birden fazla büyük modeli bellekte tutma
            TEST_MODEL_ONBELLEK[model_yolu] = YOLO(model_yolu)
    return TEST_MODEL_ONBELLEK[model_yolu]


def _hud_ciz(cv2, img, fps: float, sure_ms: float, model_adi: str):
    metin = f"FPS: {fps:.1f}   Sure: {sure_ms:.0f} ms   Model: {model_adi}"
    (genislik, yukseklik), _ = cv2.getTextSize(metin, cv2.FONT_HERSHEY_SIMPLEX, 0.6, 2)
    cv2.rectangle(img, (0, 0), (genislik + 16, yukseklik + 16), (0, 0, 0), -1)
    cv2.putText(img, metin, (8, yukseklik + 8), cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 255), 2)
    return img


@app.route("/api/test/gorsel", methods=["POST"])
def test_gorsel():
    import time as _time

    try:
        import cv2
    except ImportError:
        return jsonify({"hata": "opencv-python kurulu değil. Kurmak için: pip install opencv-python"}), 400

    veri = request.get_json()
    model_yolu = veri.get("model_dosyasi", "").strip()
    gorsel_yolu = veri.get("gorsel_dosyasi", "").strip()
    try:
        conf = float(veri.get("conf", 0.25))
    except (TypeError, ValueError):
        conf = 0.25

    if not model_yolu:
        return jsonify({"hata": "Bir model dosyası seçmelisin (örn. best.pt)."}), 400
    if not gorsel_yolu or not Path(gorsel_yolu).exists():
        return jsonify({"hata": f"Görsel bulunamadı: {gorsel_yolu}"}), 400

    try:
        model = _test_modelini_yukle(model_yolu)
    except Exception as e:
        return jsonify({"hata": f"Model yüklenemedi: {e}"}), 400

    baslangic = _time.time()
    try:
        sonuclar = model.predict(source=gorsel_yolu, conf=conf, verbose=False)
    except Exception as e:
        return jsonify({"hata": f"Tahmin sırasında hata: {e}"}), 500
    sure_ms = (_time.time() - baslangic) * 1000
    fps = 1000 / sure_ms if sure_ms > 0 else 0

    sonuc = sonuclar[0]
    cizili = sonuc.plot()  # BGR numpy array, kutular + sınıf adı + güven zaten çizili
    cizili = _hud_ciz(cv2, cizili, fps, sure_ms, Path(model_yolu).name)

    TEST_CIKTI_KLASORU.mkdir(parents=True, exist_ok=True)
    dosya_adi = f"sonuc_{int(_time.time() * 1000)}.jpg"
    cikti_yolu = TEST_CIKTI_KLASORU / dosya_adi
    cv2.imwrite(str(cikti_yolu), cizili)

    tespitler = []
    if sonuc.boxes is not None:
        for kutu in sonuc.boxes:
            sinif_id = int(kutu.cls[0])
            tespitler.append({
                "sinif": sonuc.names.get(sinif_id, str(sinif_id)),
                "guven": round(float(kutu.conf[0]), 4),
            })

    return jsonify({
        "ok": True,
        "sonuc_url": f"/static/test_ciktilari/{dosya_adi}",
        "cikti_dosya_yolu": str(cikti_yolu),
        "fps": round(fps, 2),
        "sure_ms": round(sure_ms, 1),
        "tespitler": tespitler,
    })


# ============================================================
# MODEL TEST -- VİDEO modu (nevfel.txt madde 5, devamı)
# Video dosyasını kare kare işler (arka plan thread'inde, eğitimdeki
# aynı canlı-ilerleme deseniyle), her kareye tespit kutuları + HUD
# (fps/süre) çizer, sonucu yeni bir video dosyası olarak kaydeder.
# Tarayıcı bunu <video> etiketiyle oynatır.
# ============================================================

VIDEO_TEST_DURUMU = {
    "calisiyor": False,
    "tamamlandi": False,
    "hata": None,
    "toplam_kare": 0,
    "islenen_kare": 0,
    "cikti_url": None,
    "tarayicida_oynar": None,
}

VIDEO_TEST_KILIDI = threading.Lock()


def _tarayici_uyumlu_yap(ham_yol: Path, hedef_yol: Path) -> bool:
    """cv2'nin mp4v ile yazdığı videoyu ffmpeg ile H.264'e çevirir --
    pip'in opencv-python paketi lisans yüzünden H.264 encoder içermediği
    için VideoWriter'dan doğrudan tarayıcı-uyumlu video alamıyoruz.
    imageio-ffmpeg, sistemde kurulu ffmpeg'e gerek kalmadan küçük bir
    ffmpeg binary'si indirip kullanır. Başarısız olursa (paket kurulu
    değil, ffmpeg çalışmadı, vb.) sessizce False döner -- çağıran taraf
    bu durumda ham dosyayı öylece kullanır."""
    try:
        import subprocess
        import imageio_ffmpeg

        ffmpeg_yolu = imageio_ffmpeg.get_ffmpeg_exe()
        subprocess.run(
            [ffmpeg_yolu, "-y", "-i", str(ham_yol), "-c:v", "libx264",
             "-pix_fmt", "yuv420p", "-movflags", "+faststart", str(hedef_yol)],
            check=True, capture_output=True,
        )
        return hedef_yol.exists()
    except Exception:
        return False


def _video_testini_baslat_arka_planda(model_yolu: str, video_yolu: str, conf: float):
    import time as _time

    try:
        import cv2
    except ImportError:
        VIDEO_TEST_DURUMU["hata"] = "opencv-python kurulu değil. Kurmak için: pip install opencv-python"
        VIDEO_TEST_DURUMU["calisiyor"] = False
        return

    try:
        model = _test_modelini_yukle(model_yolu)

        acilan = cv2.VideoCapture(video_yolu)
        if not acilan.isOpened():
            raise RuntimeError(f"Video açılamadı: {video_yolu}")

        genislik = int(acilan.get(cv2.CAP_PROP_FRAME_WIDTH))
        yukseklik = int(acilan.get(cv2.CAP_PROP_FRAME_HEIGHT))
        video_fps = acilan.get(cv2.CAP_PROP_FPS) or 25.0
        toplam_kare = int(acilan.get(cv2.CAP_PROP_FRAME_COUNT))
        VIDEO_TEST_DURUMU["toplam_kare"] = toplam_kare

        TEST_CIKTI_KLASORU.mkdir(parents=True, exist_ok=True)
        dosya_adi = f"video_sonuc_{int(_time.time() * 1000)}.mp4"
        cikti_yolu = TEST_CIKTI_KLASORU / dosya_adi
        # cv2'nin yazdığı HAM dosya (genelde mp4v codec -- tarayıcı bunu
        # OYNATAMAZ, sadece VLC gibi masaüstü oynatıcılar açabilir).
        ham_yol = TEST_CIKTI_KLASORU / f"_ham_{dosya_adi}"

        # pip'in opencv-python paketi lisans yüzünden genelde H.264 (avc1)
        # encoder'ı İÇERMEZ -- bu yüzden avc1 açmayı denemek yerine
        # doğrudan her zaman çalışan mp4v ile yazıp, aşağıda ffmpeg ile
        # tarayıcı-uyumlu H.264'e çeviriyoruz (bkz. _tarayici_uyumlu_yap).
        yazici = cv2.VideoWriter(str(ham_yol), cv2.VideoWriter_fourcc(*"mp4v"), video_fps, (genislik, yukseklik))
        if not yazici.isOpened():
            raise RuntimeError("Video yazıcı (VideoWriter) açılamadı -- codec sorunu olabilir.")

        islenen = 0
        baslangic = _time.time()

        while True:
            basarili, kare = acilan.read()
            if not basarili:
                break

            kare_baslangic = _time.time()
            sonuclar = model.predict(source=kare, conf=conf, verbose=False)
            kare_sure_ms = (_time.time() - kare_baslangic) * 1000
            kare_fps = 1000 / kare_sure_ms if kare_sure_ms > 0 else 0

            cizili = sonuclar[0].plot()
            cizili = _hud_ciz(cv2, cizili, kare_fps, kare_sure_ms, Path(model_yolu).name)
            yazici.write(cizili)

            islenen += 1
            VIDEO_TEST_DURUMU["islenen_kare"] = islenen

        acilan.release()
        yazici.release()

        # Ham (mp4v) dosyayı tarayıcının oynatabileceği H.264'e çevirmeyi
        # dene. Başarısız olursa (ffmpeg indirilemedi/çalışmadı), ham
        # dosyayı öylece son isimle kullan -- en azından indirilip VLC
        # gibi bir oynatıcıda izlenebilir.
        donusturuldu = _tarayici_uyumlu_yap(ham_yol, cikti_yolu)
        if donusturuldu:
            ham_yol.unlink(missing_ok=True)
        else:
            ham_yol.rename(cikti_yolu)

        VIDEO_TEST_DURUMU["cikti_url"] = f"/static/test_ciktilari/{dosya_adi}"
        VIDEO_TEST_DURUMU["cikti_dosya_yolu"] = str(cikti_yolu)
        VIDEO_TEST_DURUMU["tarayicida_oynar"] = donusturuldu
        VIDEO_TEST_DURUMU["tamamlandi"] = True

    except Exception as e:
        VIDEO_TEST_DURUMU["hata"] = str(e)
    finally:
        VIDEO_TEST_DURUMU["calisiyor"] = False


@app.route("/api/test/video_baslat", methods=["POST"])
def test_video_baslat():
    with VIDEO_TEST_KILIDI:
        if VIDEO_TEST_DURUMU["calisiyor"]:
            return jsonify({"hata": "Zaten devam eden bir video testi var, bitmesini bekle."}), 400

        veri = request.get_json()
        model_yolu = veri.get("model_dosyasi", "").strip()
        video_yolu = veri.get("video_dosyasi", "").strip()
        try:
            conf = float(veri.get("conf", 0.25))
        except (TypeError, ValueError):
            conf = 0.25

        if not model_yolu:
            return jsonify({"hata": "Bir model dosyası seçmelisin (örn. best.pt)."}), 400
        if not video_yolu or not Path(video_yolu).exists():
            return jsonify({"hata": f"Video bulunamadı: {video_yolu}"}), 400

        VIDEO_TEST_DURUMU.update({
            "calisiyor": True,
            "tamamlandi": False,
            "hata": None,
            "toplam_kare": 0,
            "islenen_kare": 0,
            "cikti_url": None,
            "cikti_dosya_yolu": None,
        })

        thread = threading.Thread(
            target=_video_testini_baslat_arka_planda,
            args=(model_yolu, video_yolu, conf),
            daemon=True,
        )
        thread.start()

    return jsonify({"ok": True})


@app.route("/api/test/video_durum")
def test_video_durum():
    with VIDEO_TEST_KILIDI:
        kopya = dict(VIDEO_TEST_DURUMU)
    return jsonify(kopya)


# ============================================================
# MODEL TEST -- WEBCAM modu (nevfel.txt madde 5, devamı)
# Video modundan farkı: sabit bir dosya değil, bilgisayarın webcam'i
# SÜREKLİ açık kalıyor. Arka plan thread'i sürekli kare okuyup modeli
# çalıştırıyor, en son işlenmiş kareyi bellekte tutuyor. Tarayıcıya
# "bitince tek video dosyası" göndermek yerine MJPEG akışı (multipart
# HTTP response) ile CANLI gönderiyoruz -- tarayıcının <img> etiketi bu
# akışı kendiliğinden "video gibi" gösteriyor, bizim ekstra bir
# "yenile" mantığı yazmamıza gerek kalmıyor.
# ============================================================

WEBCAM_DURUMU = {
    "calisiyor": False,
    "hata": None,
    "model_yolu": None,
    "conf": 0.25,
    "son_kare_jpeg": None,  # en son işlenmiş karenin JPEG byte'ları
    "islenen_kare": 0,
}

WEBCAM_KILIDI = threading.Lock()
# Thread'i "durdur" demenin yolu -- döngü her turda bu işareti kontrol
# ediyor, set edilince kamerayı bırakıp temiz çıkıyor.
WEBCAM_DURDURMA_ISARETI = threading.Event()


def _webcam_yakalama_dongusu():
    import time as _time

    try:
        import cv2
    except ImportError:
        WEBCAM_DURUMU["hata"] = "opencv-python kurulu değil. Kurmak için: pip install opencv-python"
        WEBCAM_DURUMU["calisiyor"] = False
        return

    kamera = None
    try:
        model = _test_modelini_yukle(WEBCAM_DURUMU["model_yolu"])

        # 0 = bilgisayarın varsayılan/birincil webcam'i. Windows'ta
        # varsayılan backend bazen kamerayı "açık" gösterip hiç kare
        # vermiyor (özellikle Windows'un Gizlilik > Kamera ayarında
        # masaüstü uygulamalarına izin verilmemişse) -- DSHOW backend'i
        # bu sorunu genelde çözüyor, önce onu deniyoruz.
        kamera = cv2.VideoCapture(0, cv2.CAP_DSHOW)
        if not kamera.isOpened():
            kamera = cv2.VideoCapture(0)
        if not kamera.isOpened():
            raise RuntimeError(
                "Webcam açılamadı -- başka bir uygulama (Zoom, Teams vb.) "
                "kullanıyor olabilir, bilgisayarda webcam yok, ya da Windows "
                "Ayarlar > Gizlilik ve Güvenlik > Kamera altında masaüstü "
                "uygulamalarına izin verilmemiş olabilir."
            )

        # Kamera "açık" görünüp hiç kare vermeyebiliyor (tam olarak bu
        # oturumda yaşandığı gibi) -- art arda çok fazla başarısız
        # okuma olursa bunu sessizce sonsuza kadar denemek yerine gerçek
        # bir hata olarak bildiriyoruz.
        ardarda_basarisiz = 0
        MAKSIMUM_ARDARDA_BASARISIZ = 100  # ~birkaç saniye

        while not WEBCAM_DURDURMA_ISARETI.is_set():
            basarili, kare = kamera.read()
            if not basarili:
                ardarda_basarisiz += 1
                if ardarda_basarisiz >= MAKSIMUM_ARDARDA_BASARISIZ:
                    raise RuntimeError(
                        "Webcam açıldı ama hiç görüntü alınamadı -- muhtemelen "
                        "Windows Ayarlar > Gizlilik ve Güvenlik > Kamera "
                        "altında bu uygulamaya (masaüstü uygulamaları) izin "
                        "verilmemiş. Ayarı açıp tekrar deneyin."
                    )
                _time.sleep(0.05)
                continue
            ardarda_basarisiz = 0

            baslangic = _time.time()
            sonuclar = model.predict(source=kare, conf=WEBCAM_DURUMU["conf"], verbose=False)
            sure_ms = (_time.time() - baslangic) * 1000
            fps = 1000 / sure_ms if sure_ms > 0 else 0

            cizili = sonuclar[0].plot()
            cizili = _hud_ciz(cv2, cizili, fps, sure_ms, Path(WEBCAM_DURUMU["model_yolu"]).name)

            basarili_jpeg, jpeg_veri = cv2.imencode(".jpg", cizili)
            if basarili_jpeg:
                with WEBCAM_KILIDI:
                    WEBCAM_DURUMU["son_kare_jpeg"] = jpeg_veri.tobytes()
                    WEBCAM_DURUMU["islenen_kare"] += 1

    except Exception as e:
        WEBCAM_DURUMU["hata"] = str(e)
    finally:
        # Hata olsun olmasın, açılmış olabilecek kamerayı MUTLAKA serbest
        # bırak -- yoksa bir sonraki denemede "başka bir uygulama
        # kullanıyor" hatası ALIRIZ, halbuki kullanan kendi eski thread'imiz.
        if kamera is not None:
            kamera.release()
        WEBCAM_DURUMU["calisiyor"] = False


@app.route("/api/test/webcam_baslat", methods=["POST"])
def test_webcam_baslat():
    with WEBCAM_KILIDI:
        if WEBCAM_DURUMU["calisiyor"]:
            return jsonify({"hata": "Webcam zaten çalışıyor, önce durdur."}), 400

        veri = request.get_json()
        model_yolu = veri.get("model_dosyasi", "").strip()
        try:
            conf = float(veri.get("conf", 0.25))
        except (TypeError, ValueError):
            conf = 0.25

        if not model_yolu:
            return jsonify({"hata": "Bir model dosyası seçmelisin (örn. best.pt)."}), 400

        WEBCAM_DURUMU.update({
            "calisiyor": True,
            "hata": None,
            "model_yolu": model_yolu,
            "conf": conf,
            "son_kare_jpeg": None,
            "islenen_kare": 0,
        })
        WEBCAM_DURDURMA_ISARETI.clear()

        thread = threading.Thread(target=_webcam_yakalama_dongusu, daemon=True)
        thread.start()

    return jsonify({"ok": True})


@app.route("/api/test/webcam_durdur", methods=["POST"])
def test_webcam_durdur():
    # Sadece işareti veriyoruz -- gerçek kapatma (kamerayı release etme)
    # arka plandaki döngünün kendi işi, burada senkron beklemiyoruz.
    WEBCAM_DURDURMA_ISARETI.set()
    return jsonify({"ok": True})


@app.route("/api/test/webcam_durum")
def test_webcam_durum():
    return jsonify({
        "calisiyor": WEBCAM_DURUMU["calisiyor"],
        "hata": WEBCAM_DURUMU["hata"],
        "islenen_kare": WEBCAM_DURUMU["islenen_kare"],
    })


@app.route("/api/test/webcam_stream")
def test_webcam_stream():
    import time as _time

    def kare_uret():
        # Döngü daha ilk kareyi üretmemiş olabilir -- kısa bir süre bekle
        # (en fazla ~5 saniye), yoksa hemen boş akışla bitebilir.
        bekleme = 0
        while WEBCAM_DURUMU["son_kare_jpeg"] is None and WEBCAM_DURUMU["calisiyor"] and bekleme < 50:
            _time.sleep(0.1)
            bekleme += 1

        while WEBCAM_DURUMU["calisiyor"]:
            with WEBCAM_KILIDI:
                jpeg_veri = WEBCAM_DURUMU["son_kare_jpeg"]
            if jpeg_veri is not None:
                yield (b"--frame\r\nContent-Type: image/jpeg\r\n\r\n" + jpeg_veri + b"\r\n")
            # Gerçek hız modelin işleme süresine bağlı -- burada sadece
            # "en son kareyi ne sıklıkla kontrol edelim" aralığı bu.
            _time.sleep(0.05)

    return Response(kare_uret(), mimetype="multipart/x-mixed-replace; boundary=frame")


# ============================================================
# MODEL TEST -- METRİKLER (mAP) modu (nevfel.txt madde 5, devamı)
# Görsel/video/webcam modları tek bir tahmini gösteriyor ama bir
# tahminin "iyi" olup olmadığını (gerçek etiketlerle karşılaştırarak)
# SAYISAL olarak ölçmüyorlardı -- nevfel.txt bunun için mAP (mean
# Average Precision) değerinin arayüzde görünmesini istiyor. mAP tek
# bir görselde hesaplanamaz (gerçek/ground-truth etiket gerekir) --
# bunun için etiketli bir VAL seti (Dataset Splitter'ın ürettiği
# data.yaml gibi) gerekiyor. Burada ultralytics'in kendi model.val()
# fonksiyonunu kullanıyoruz -- val seti boyutuna göre (video testi gibi)
# biraz sürebileceği için arka plan thread'inde çalıştırıp polling ile
# ilerlemeyi/sonucu döndürüyoruz.
# ============================================================

METRIK_DURUMU = {
    "calisiyor": False,
    "tamamlandi": False,
    "hata": None,
    "sonuc": None,  # {"map50": .., "map50_95": .., "precision": .., "recall": ..}
}

METRIK_KILIDI = threading.Lock()


def _metrik_hesapla_arka_planda(model_yolu: str, data_yaml: str):
    try:
        model = _test_modelini_yukle(model_yolu)
        # val() kendi çıktı klasörünü de (grafikler, confusion matrix)
        # runs/ altına yazıyor -- burada sadece sayısal özet ilgimizi
        # çekiyor, o klasörle ilgilenmiyoruz (proje=None -> ultralytics
        # varsayılan runs/detect/val<n> klasörünü kullanır).
        sonuc = model.val(data=data_yaml, split="val", verbose=False)
        kutu = sonuc.box
        METRIK_DURUMU["sonuc"] = {
            "map50": round(float(kutu.map50), 4),
            "map50_95": round(float(kutu.map), 4),
            "precision": round(float(kutu.mp), 4),
            "recall": round(float(kutu.mr), 4),
            "sinif_sayisi": len(sonuc.names) if hasattr(sonuc, "names") else None,
        }
        METRIK_DURUMU["tamamlandi"] = True
    except Exception as e:
        METRIK_DURUMU["hata"] = str(e)
    finally:
        METRIK_DURUMU["calisiyor"] = False


@app.route("/api/test/metrik_hesapla", methods=["POST"])
def test_metrik_hesapla():
    with METRIK_KILIDI:
        if METRIK_DURUMU["calisiyor"]:
            return jsonify({"hata": "Zaten devam eden bir metrik hesaplaması var, bitmesini bekle."}), 400

        veri = request.get_json()
        model_yolu = veri.get("model_dosyasi", "").strip()
        data_yaml = veri.get("data_yaml", "").strip()

        if not model_yolu:
            return jsonify({"hata": "Bir model dosyası seçmelisin (örn. best.pt)."}), 400
        if not data_yaml or not Path(data_yaml).exists():
            return jsonify({"hata": f"data.yaml bulunamadı: {data_yaml} (val bölümü içeren bir data.yaml gerekiyor -- Dataset Splitter'ın ürettiği gibi)."}), 400

        METRIK_DURUMU.update({"calisiyor": True, "tamamlandi": False, "hata": None, "sonuc": None})

        thread = threading.Thread(
            target=_metrik_hesapla_arka_planda,
            args=(model_yolu, data_yaml),
            daemon=True,
        )
        thread.start()

    return jsonify({"ok": True})


@app.route("/api/test/metrik_durum")
def test_metrik_durum():
    with METRIK_KILIDI:
        kopya = dict(METRIK_DURUMU)
    return jsonify(kopya)


# ============================================================
# FUSION -- PLAKA + MARKA/MODEL BİRLEŞTİRME (OtoGöz'e özel bir araç,
# nevfel.txt'nin istediği evrensel setin dışında -- ama diğer araçlarla
# aynı desende: model(ler) seç, görsel seç, çalıştır, sonucu + adım adım
# logu arayüzden gör). Mantığın komut satırı hali kod/06_fusion.py'de de
# var (tek başına da çalıştırılabilir), burada AYNI adımlar arayüzden:
#   1) marka/model modeliniz araç kutularını + class'ı bulur
#   2) plaka modeli plaka kutularını bulur
#   3) her plaka kutusu OCR (fast-plate-ocr) ile okunur
#   4) her plaka, HANGİ araç kutusunun içinde kaldığına göre o araca
#      eşlenir (IoU değil "örtüşme oranı" -- plaka araca göre çok küçük)
#   5) hem marka/model hem plaka için "kesin/muhtemel/belirsiz" güven
#      seviyesi atanır, tek bir sonuç kaydında (araç başına) birleştirilir
# ============================================================

FUSION_MARKA_MODEL_ONBELLEK = {}
FUSION_PLAKA_MODEL_ONBELLEK = {}
FUSION_OCR_READER = {"reader": None}

FUSION_MARKA_ESIK_KESIN = 0.80
FUSION_MARKA_ESIK_MUHTEMEL = 0.50
FUSION_PLAKA_ESIK_KESIN = 0.60
FUSION_ESLESME_ESIGI = 0.55

# Plaka tespit modelinin ürettiği, bariz yanlış-pozitif (plaka olmayan bir
# şeyi plaka sanma) kutuları elemek için minimum tespit güveni.
FUSION_PLAKA_TESPIT_ESIK_MIN = 0.40

# Genel (hazır/COCO) araç tespiti için model adı -- Ön-Etiketleme'nin
# kullandığı AYNI mantık: kendi marka/model modelimizin HİÇ tanımadığı
# (class listesinde olmayan) bir araç kutuya da düşsün diye fallback.
FUSION_GENEL_MODEL_ADI = "yolo11n.pt"
# Genel modelin bulduğu bir kutu, özel modelin bulduğu bir kutuyla bu IoU'nun
# üzerinde örtüşüyorsa "zaten aynı araç, tekrar ekleme" sayılır.
FUSION_GENEL_ARAC_IOU_ESIGI = 0.5

FUSION_TR_PLAKA_REGEX = re.compile(r"^(\d{2})([A-Z]{1,3})(\d{2,4})$")
FUSION_HARF_YERINE_RAKAM = {"O": "0", "I": "1", "S": "5", "B": "8", "Z": "2"}
FUSION_RAKAM_YERINE_HARF = {"0": "O", "1": "I", "5": "S", "8": "B", "2": "Z"}
FUSION_CIKTI_KLASORU = Path(__file__).resolve().parent / "static" / "fusion_ciktilari"


def _fusion_marka_modelini_yukle(model_yolu: str):
    from ultralytics import YOLO
    with MODEL_ONBELLEK_KILIDI:
        if model_yolu not in FUSION_MARKA_MODEL_ONBELLEK:
            FUSION_MARKA_MODEL_ONBELLEK.clear()
            FUSION_MARKA_MODEL_ONBELLEK[model_yolu] = YOLO(model_yolu)
    return FUSION_MARKA_MODEL_ONBELLEK[model_yolu]


def _fusion_plaka_modelini_yukle(model_yolu: str):
    from ultralytics import YOLO
    with MODEL_ONBELLEK_KILIDI:
        if model_yolu not in FUSION_PLAKA_MODEL_ONBELLEK:
            FUSION_PLAKA_MODEL_ONBELLEK.clear()
            FUSION_PLAKA_MODEL_ONBELLEK[model_yolu] = YOLO(model_yolu)
    return FUSION_PLAKA_MODEL_ONBELLEK[model_yolu]


FUSION_PLAKA_OCR_MODEL_ADI = "cct-s-v2-global-model"

# --- SQLite (Adım 7) -- Fusion sonuçlarının BİRİKİMLİ kaydı ---
# kayitlar/fusion_sonucu.json her çalıştırmada ÜZERİNE yazılıyor (sadece
# "son sonuç" için pratik bir önizleme dosyası). Burada AYRICA, her
# çalıştırmanın ürettiği her aracı db/otogoz.db içindeki "tespitler"
# tablosuna EKLEME (accumulate) olarak yazıyoruz -- geçmiş kaybolmuyor,
# ileride "bu plaka daha önce ne zaman görüldü" gibi sorgular
# yapılabiliyor. Şema detayları/kararların gerekçesi: kod/07_veritabani.py
# (aynı mantığı burada tekrarlıyoruz çünkü "07_..." rakamla başlayan
# dosya adları Python'da doğrudan import edilemiyor -- bkz. o dosyanın
# başındaki not).
# NOT (2026-08-04, bu Toolset kopyasına özel): orijinal projede bu yol
# parent.parent/db/otogoz.db idi (proje kökündeki paylaşılan DB). Burada
# BİLEREK bu kopyanın KENDİ İÇİNDE bir db/ klasörüne yazıyoruz -- aksi
# halde Fusion biri tarafından açılırsa (varsayılan kapalı olsa da),
# yanlışlıkla otopark/ projesinin canlı veritabanına (db/otogoz.db)
# karışırdı. Bu kopya bağımsız/taşınabilir olmalı.
FUSION_DB_YOLU = Path(__file__).resolve().parent / "db" / "otogoz.db"


def _fusion_db_tablosunu_olustur():
    import sqlite3
    FUSION_DB_YOLU.parent.mkdir(parents=True, exist_ok=True)
    with sqlite3.connect(FUSION_DB_YOLU) as con:
        con.execute("""
            CREATE TABLE IF NOT EXISTS tespitler (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                tespit_zamani TEXT NOT NULL,
                gorsel_yolu TEXT,
                sonuc_gorsel_yolu TEXT,
                marka_model TEXT,
                marka_model_guven REAL,
                marka_model_durum TEXT,
                plaka TEXT,
                plaka_guven REAL,
                plaka_durum TEXT
            )
        """)
        con.execute("CREATE INDEX IF NOT EXISTS idx_tespitler_plaka ON tespitler(plaka)")
        con.execute("CREATE INDEX IF NOT EXISTS idx_tespitler_marka_model ON tespitler(marka_model)")
        con.execute("CREATE INDEX IF NOT EXISTS idx_tespitler_zaman ON tespitler(tespit_zamani)")


def _fusion_db_kaydet(gorsel_yolu: str, sonuc_gorsel_yolu: str, araclar: list) -> int:
    import sqlite3
    from datetime import datetime as _datetime
    _fusion_db_tablosunu_olustur()
    zaman = _datetime.now().isoformat(timespec="seconds")
    with sqlite3.connect(FUSION_DB_YOLU) as con:
        for arac in araclar:
            con.execute(
                """INSERT INTO tespitler
                   (tespit_zamani, gorsel_yolu, sonuc_gorsel_yolu,
                    marka_model, marka_model_guven, marka_model_durum,
                    plaka, plaka_guven, plaka_durum)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    zaman, gorsel_yolu, sonuc_gorsel_yolu,
                    arac.get("marka_model"), arac.get("marka_model_guven"), arac.get("marka_model_durum"),
                    arac.get("plaka"), arac.get("plaka_guven"), arac.get("plaka_durum"),
                ),
            )
    return len(araclar)


def _fusion_ocr_okuyucusunu_yukle():
    # ESKİDEN EasyOCR (genel amaçlı, plakaya özel eğitilmemiş bir OCR)
    # kullanıyorduk -- gerçek fotoğraflarla test ederken karakter
    # karıştırma/eksik okuma sorunları yaşandı (bkz. ILERLEME_GUNLUGU.md).
    # Bunun yerine artık PLAKAYA ÖZEL eğitilmiş "fast-plate-ocr"
    # kütüphanesini kullanıyoruz -- profesyonel ANPR sistemlerinin de
    # yaptığı gibi, dar bir alanda (sadece plaka metni) eğitilmiş bir
    # model, genel amaçlı bir OCR'dan çok daha isabetli oluyor. Bu
    # kütüphane SADECE okuma yapıyor (kendi plaka tespiti YOK), bizim
    # kendi plaka_tespit.pt modelimizin bulup kırptığı görüntüyü okuyor.
    with MODEL_ONBELLEK_KILIDI:
        if FUSION_OCR_READER["reader"] is None:
            from fast_plate_ocr import LicensePlateRecognizer
            FUSION_OCR_READER["reader"] = LicensePlateRecognizer(FUSION_PLAKA_OCR_MODEL_ADI)
    return FUSION_OCR_READER["reader"]


def _fusion_karakter_duzeltme_varyantlari(metin: str):
    if len(metin) < 4:
        return []
    bas = "".join(FUSION_HARF_YERINE_RAKAM.get(c, c) for c in metin[:2])
    kalan = metin[2:]
    harf_blok = ""
    i = 0
    while i < len(kalan) and kalan[i] not in "0123456789":
        harf_blok += FUSION_RAKAM_YERINE_HARF.get(kalan[i], kalan[i])
        i += 1
    son = "".join(FUSION_HARF_YERINE_RAKAM.get(c, c) for c in kalan[i:])
    return [bas + harf_blok + son]


def _fusion_temizle_ve_dogrula(ham_metin: str):
    metin = ham_metin.upper()
    metin = re.sub(r"[^A-Z0-9]", "", metin)
    if FUSION_TR_PLAKA_REGEX.match(metin):
        return metin, True
    for aday in _fusion_karakter_duzeltme_varyantlari(metin):
        if FUSION_TR_PLAKA_REGEX.match(aday):
            return aday, True
    return metin, False




def _fusion_gorseli_oku(cv2, dosya_yolu: str):
    """Görseli BGR numpy array olarak okur. Önce normal cv2.imread'i
    dener; None dönerse (OpenCV'nin çözemediği bir format -- en sık HEIC/
    HEIF, iPhone fotoğrafları) pillow-heif ile açmayı dener.

    ÖNEMLİ: uzantıya değil, GERÇEKTEN OKUNUP OKUNAMADIĞINA bakıyoruz --
    bir dosyanın adını ".heic"ten ".jpg"ye çevirmek İÇERİĞİNİ dönüştürmüyor,
    dosya hâlâ ham HEIC verisi olarak kalıyor ve cv2.imread onu çözemiyor
    (uzantı ne olursa olsun). Bu yüzden önce normal okumayı deniyoruz,
    başarısız olursa (uzantısı ne olursa olsun) HEIC dönüştürmeyi
    deniyoruz -- kullanıcının uzantıyı elle değiştirmiş olması bile
    sorun olmuyor.

    Döndürür: (goruntu, hata_mesaji). goruntu None ise hata_mesaji
    kullanıcıya gösterilecek açıklamayı içerir."""
    goruntu = cv2.imread(dosya_yolu)
    if goruntu is not None:
        return goruntu, None

    try:
        import pillow_heif
    except ImportError:
        return None, (
            f"Görsel okunamadı: {dosya_yolu} -- eğer bu bir iPhone fotoğrafıysa "
            "(HEIC/HEIF formatı), sadece dosya adını .jpg yapmak yeterli değil, "
            "içeriğin GERÇEKTEN dönüştürülmesi gerekiyor. Bunu otomatik "
            "yapabilmemiz için 'pillow-heif' kütüphanesi kurulu değil "
            "(kurmak için: pip install pillow-heif)."
        )

    try:
        from PIL import Image as _PILImage
        pillow_heif.register_heif_opener()
        # PIL, çok yüksek piksel sayılı görselleri "decompression bomb"
        # (kötü niyetli/aşırı büyük dosya) sanıp güvenlik amaçlı
        # reddediyor -- ama burada kaynak kullanıcının KENDİ telefon
        # fotoğrafı (güvenilir), sadece modern telefonlar gerçekten çok
        # yüksek çözünürlük üretebiliyor. Bu güvenlik limitini kapatıyoruz.
        _PILImage.MAX_IMAGE_PIXELS = None
        img = _PILImage.open(dosya_yolu).convert("RGB")
        rgb = np.array(img)
        return cv2.cvtColor(rgb, cv2.COLOR_RGB2BGR), None
    except Exception as e:
        return None, f"Görsel okunamadı (HEIC dönüştürme de başarısız oldu): {e}"


def _fusion_beyaz_bolgeye_kirp(cv2, goruntu_bgr):
    """Kırpılmış plaka görüntüsünde SADECE beyaz zeminli (plakanın
    kendisi -- Türk plakaları beyaz zemin + siyah yazı) bölgeyi bulup ona
    sıkıca kırpar. Amaç: plaka kutusunun içine giren ama plaka OLMAYAN
    öğeleri (siyah plastik çerçeve, bayilik yazısı/sticker, marka logosu
    gibi -- bunlar OCR'ı yanlış okumaya sürüklüyordu) OCR'a hiç vermemek.
    Yeterince büyük/anlamlı bir beyaz bölge bulunamazsa orijinali döner
    (güvenli varsayılan -- hiçbir şeyi YANLIŞLIKLA aşırı kırpmamak için)."""
    hsv = cv2.cvtColor(goruntu_bgr, cv2.COLOR_BGR2HSV)
    # beyaz: düşük doygunluk (S), yüksek parlaklık (V). Eşiği kasten
    # gevşek tuttuk (V >= 100) -- açılı/gölgeli plakalarda parlaklık
    # uçtan uca EŞİT değil, sıkı bir eşik plakanın gölgeli ucunu
    # "beyaz değil" sayıp o taraftaki karakterleri kırpabiliyordu.
    alt = np.array([0, 0, 100], dtype=np.uint8)
    ust = np.array([180, 80, 255], dtype=np.uint8)
    maske = cv2.inRange(hsv, alt, ust)

    # Önce CLOSE (küçük boşlukları/gölge lekelerini doldur -- plakanın
    # beyaz zemini tek parça/bağlantılı kalsın), sonra OPEN (gürültüyü temizle).
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
        # Bulunan beyaz bölge anlamsız derecede küçükse (muhtemelen
        # gürültü/yansıma), güvenli tarafta kal -- orijinali kullan.
        return goruntu_bgr

    # Bulunan sınırın TAM kenarından kesmek yerine küçük bir güvenlik payı
    # bırakıyoruz -- maske mükemmel olmayabilir (açılı ışıkta plakanın bir
    # ucu hafifçe dışarıda kalabilir), pay olmadan uçtaki karakterler kesilebiliyordu.
    pay_x = max(2, int(w * 0.08))
    pay_y = max(2, int(h * 0.08))
    yukseklik, genislik = goruntu_bgr.shape[:2]
    x1, y1 = max(0, x - pay_x), max(0, y - pay_y)
    x2, y2 = min(genislik, x + w + pay_x), min(yukseklik, y + h + pay_y)

    return goruntu_bgr[y1:y2, x1:x2]


def _fusion_plakayi_oku(cv2, reader, plaka_kirpik_bgr):
    # Önce SADECE beyaz zeminli (plakanın kendisi) bölgeye sıkıca kırp --
    # çevredeki siyah çerçeve/bayilik yazısı gibi plaka olmayan öğeleri
    # OCR'a hiç vermemek için.
    #
    # NOT: burada AYRICA _fusion_sol_seridi_kirp (körlemesine sol %16 kesme)
    # UYGULAMIYORUZ. Sebep: bazı plakalarda mavi/renkli "TR" şeridi hiç
    # yok (düz beyaz plaka), o zaman bu kesme gerçek baştaki karakterleri
    # (örn. "01 A...") de kesip atıyordu -- beyaz bölgeye kırpma zaten
    # mavi/renkli bir şerit VARSA onu doğal olarak dışarıda bırakıyor
    # (beyaz değil diye), o yüzden ayrı bir körlemesine kesmeye gerek yok.
    beyaz_kirpik = _fusion_beyaz_bolgeye_kirp(cv2, plaka_kirpik_bgr)

    # fast-plate-ocr, EasyOCR'ın aksine tek bir "plaka metni" tahmini
    # döndürüyor (blok blok birleştirme gerekmiyor, çünkü zaten baştan
    # sona tek bir plaka okumak için eğitilmiş). Hem beyaz-bölgeye-kırpılmış
    # hem de ham kırpığı deniyoruz, hangisi daha yüksek ortalama karakter
    # güveniyle sonuç veriyorsa onu kullanıyoruz -- beyaz bölge kırpma bazen
    # (nadir) yanlış bölgeyi bulabiliyor, ham görüntü bir yedek gibi duruyor.
    denemeler = []
    for etiket, goruntu_bgr in (("beyaz-bolgeye-kirpilmis", beyaz_kirpik), ("ham", plaka_kirpik_bgr)):
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
            denemeler.append((etiket, metin, guven))

    if not denemeler:
        return None, 0.0, False

    _etiket, en_iyi_metin, en_iyi_guven = max(denemeler, key=lambda d: d[2])
    temiz, gecerli = _fusion_temizle_ve_dogrula(en_iyi_metin)
    return temiz, en_iyi_guven, gecerli


def _fusion_ortusme_orani(kucuk_kutu, buyuk_kutu) -> float:
    """kucuk_kutu'nun (plaka) ne kadarı buyuk_kutu'nun (araç) içinde
    kalıyor -- normal IoU yerine bunu kullanıyoruz çünkü plaka araca göre
    çok küçük, IoU her zaman düşük çıkıp doğru eşleşmeyi bile eleyebilir."""
    x1 = max(kucuk_kutu[0], buyuk_kutu[0])
    y1 = max(kucuk_kutu[1], buyuk_kutu[1])
    x2 = min(kucuk_kutu[2], buyuk_kutu[2])
    y2 = min(kucuk_kutu[3], buyuk_kutu[3])
    if x2 <= x1 or y2 <= y1:
        return 0.0
    kesisim = (x2 - x1) * (y2 - y1)
    kucuk_alan = (kucuk_kutu[2] - kucuk_kutu[0]) * (kucuk_kutu[3] - kucuk_kutu[1])
    return kesisim / kucuk_alan if kucuk_alan > 0 else 0.0


def _fusion_iou(kutu1, kutu2) -> float:
    """Standart IoU (Intersection over Union) -- iki kutu da BENZER
    boyuttaysa (örn. iki ayrı modelin bulduğu aynı araç kutusu) bu metrik
    doğru sonuç verir. Plaka<->araç gibi çok farklı boyutlu kutular için
    yerine _fusion_ortusme_orani kullanılıyor (yukarıda)."""
    x1 = max(kutu1[0], kutu2[0])
    y1 = max(kutu1[1], kutu2[1])
    x2 = min(kutu1[2], kutu2[2])
    y2 = min(kutu1[3], kutu2[3])
    if x2 <= x1 or y2 <= y1:
        return 0.0
    kesisim = (x2 - x1) * (y2 - y1)
    alan1 = (kutu1[2] - kutu1[0]) * (kutu1[3] - kutu1[1])
    alan2 = (kutu2[2] - kutu2[0]) * (kutu2[3] - kutu2[1])
    birlesim = alan1 + alan2 - kesisim
    return kesisim / birlesim if birlesim > 0 else 0.0


def _fusion_plakayi_araca_esle(plaka_kutu, arac_kutulari: list):
    en_iyi_oran = 0.0
    en_iyi_index = None
    for i, arac_kutu in enumerate(arac_kutulari):
        oran = _fusion_ortusme_orani(plaka_kutu, arac_kutu)
        if oran > en_iyi_oran:
            en_iyi_oran = oran
            en_iyi_index = i
    return en_iyi_index if en_iyi_oran >= FUSION_ESLESME_ESIGI else None


def _fusion_marka_model_durumu(guven: float) -> str:
    if guven >= FUSION_MARKA_ESIK_KESIN:
        return "kesin"
    if guven >= FUSION_MARKA_ESIK_MUHTEMEL:
        return "muhtemel"
    return "belirsiz"


def _fusion_plaka_durumu(ocr_guven: float, format_gecerli: bool) -> str:
    if not format_gecerli:
        return "format_gecersiz"
    if ocr_guven >= FUSION_PLAKA_ESIK_KESIN:
        return "kesin"
    return "muhtemel"


@app.route("/fusion")
def fusion_sayfasi():
    # Bu araç OtoGöz'e özel, varsayılan kapalı -- ayarlardan açılmadıysa
    # sayfayı göstermek yerine kısa bir "kapalı" notu gösteriyoruz.
    if not _ayarlari_oku()["gelismis_ozellikler_acik"]:
        return render_template("fusion_kapali.html")
    return render_template("fusion.html")


@app.route("/api/fusion/calistir", methods=["POST"])
def fusion_calistir():
    import time as _time

    try:
        import cv2
    except ImportError:
        return jsonify({"hata": "opencv-python kurulu değil. Kurmak için: pip install opencv-python"}), 400

    veri = request.get_json()
    marka_model_yolu = veri.get("marka_model_dosyasi", "").strip()
    plaka_model_yolu = veri.get("plaka_model_dosyasi", "").strip()
    gorsel_yolu = veri.get("gorsel_dosyasi", "").strip()

    if not marka_model_yolu or not Path(marka_model_yolu).exists():
        return jsonify({"hata": f"Marka/model modeli bulunamadı: {marka_model_yolu}"}), 400
    if not plaka_model_yolu or not Path(plaka_model_yolu).exists():
        return jsonify({"hata": f"Plaka modeli bulunamadı: {plaka_model_yolu}"}), 400
    if not gorsel_yolu or not Path(gorsel_yolu).exists():
        return jsonify({"hata": f"Görsel bulunamadı: {gorsel_yolu}"}), 400

    loglar = []

    def log(mesaj):
        loglar.append(mesaj)

    try:
        marka_model = _fusion_marka_modelini_yukle(marka_model_yolu)
        plaka_model = _fusion_plaka_modelini_yukle(plaka_model_yolu)
    except Exception as e:
        return jsonify({"hata": f"Model yüklenemedi: {e}"}), 400

    goruntu, okuma_hatasi = _fusion_gorseli_oku(cv2, gorsel_yolu)
    if goruntu is None:
        return jsonify({"hata": okuma_hatasi or f"Görsel okunamadı: {gorsel_yolu}"}), 400

    # --- 1) Marka/model tespiti ---
    # NOT: modele dosya YOLU değil, az önce okuduğumuz numpy array
    # (goruntu) veriliyor -- HEIC gibi cv2/ultralytics'in kendi başına
    # çözemediği formatları da kapsasın diye (goruntu zaten normal BGR
    # array'e dönüştürülmüş durumda, formattan bağımsız).
    log("[1/4] Marka/model modeli çalıştırılıyor...")
    marka_sonuc = marka_model(goruntu, verbose=False)[0]
    arac_kutulari = []
    arac_tahminleri = []  # [(class_adi, guven, durum), ...] durum: kesin/muhtemel/belirsiz/taninmiyor
    for kutu in marka_sonuc.boxes:
        x1, y1, x2, y2 = map(int, kutu.xyxy[0].tolist())
        guven = float(kutu.conf[0])
        class_id = int(kutu.cls[0])
        class_adi = marka_model.names[class_id]
        arac_kutulari.append((x1, y1, x2, y2))
        arac_tahminleri.append((class_adi, guven, _fusion_marka_model_durumu(guven)))
        log(f"  Araç kutusu: {class_adi} (guven={guven:.2f}) bbox=({x1},{y1},{x2},{y2})")

    if not arac_kutulari:
        return jsonify({"hata": "Hiç araç tespit edilemedi, fusion için devam edilemiyor.", "loglar": loglar}), 400

    # --- 2) Plaka tespiti ---
    log("[2/4] Plaka tespit modeli çalıştırılıyor...")
    plaka_sonuc = plaka_model(goruntu, verbose=False)[0]
    plaka_kutulari = []
    for kutu in plaka_sonuc.boxes:
        x1, y1, x2, y2 = map(int, kutu.xyxy[0].tolist())
        guven = float(kutu.conf[0])
        if guven < FUSION_PLAKA_TESPIT_ESIK_MIN:
            log(f"  [atlandi] Çok düşük güvenli plaka adayı elendi: bbox=({x1},{y1},{x2},{y2}) guven={guven:.2f}")
            continue
        plaka_kutulari.append((x1, y1, x2, y2, guven))
        log(f"  Plaka kutusu: bbox=({x1},{y1},{x2},{y2})  guven={guven:.2f}")

    # --- 3) OCR ---
    log("[3/4] Plakalar OCR ile okunuyor (ilk çalıştırmada fast-plate-ocr modeli indirebilir)...")
    reader = _fusion_ocr_okuyucusunu_yukle()
    plaka_okumalari = []  # [((x1,y1,x2,y2), metin, ocr_guven, gecerli, tespit_guven), ...]
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
        metin, ocr_guven, gecerli = _fusion_plakayi_oku(cv2, reader, kirpik)
        if metin:
            log(f"  '{metin}' (ocr_guven={ocr_guven:.2f}, format_gecerli={gecerli})")
        else:
            log("  (bu plaka kutusundan metin okunamadı)")
        plaka_okumalari.append(((x1, y1, x2, y2), metin, ocr_guven, gecerli, tespit_guven))

    # --- 4) Fusion: önce özel modelin kutularıyla eşleştir, SADECE öksüz
    # (hiçbir kutuya eşlenemeyen) plaka kalırsa genel/fallback araç
    # taramasını devreye sok. Fallback'ı HER çalıştırmada tüm kadrajı
    # taramak yerine sadece gerektiğinde yapmamızın sebebi: kalabalık bir
    # otopark sahnesinde arka plandaki onlarca alakasız/uzak araç da
    # "tanımlanmadı" diye işaretlenip sonucu anlamsızca kalabalıklaştırıyordu
    # -- oysa asıl amaç sadece "plakası var ama eşi yok" durumunu kurtarmak.
    log("[4/4] Eşleştirme + güven katmanlama...")
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

    # Aynı araca birden fazla plaka kutusu eşlenebilir (örn. plaka olmayan
    # bir yanlış-pozitif kutu da aynı araca denk gelebilir) -- bu yüzden son
    # geleni yazmak yerine, HER araç için en yüksek plaka TESPİT güvenine
    # sahip adayı seçip kullanıyoruz.
    araca_en_iyi_aday = {}  # {arac_index: (tespit_guven, metin, ocr_guven, gecerli)}
    oksuz_plakalar = []  # eşlenemeyen (plaka_kutu, metin, ocr_guven, gecerli, tespit_guven)
    for aday in plaka_okumalari:
        plaka_kutu, metin, ocr_guven, gecerli, tespit_guven = aday
        hedef_index = _fusion_plakayi_araca_esle(plaka_kutu, arac_kutulari)
        if hedef_index is None:
            oksuz_plakalar.append(aday)
            continue
        mevcut = araca_en_iyi_aday.get(hedef_index)
        if mevcut is None or tespit_guven > mevcut[0]:
            if mevcut is not None:
                log(f"  [bilgi] Araç #{hedef_index} için birden fazla plaka adayı vardı, "
                    f"en yüksek tespit güvenli olan ('{metin}', guven={tespit_guven:.2f}) seçildi.")
            araca_en_iyi_aday[hedef_index] = (tespit_guven, metin, ocr_guven, gecerli)

    # Öksüz plaka VARSA: sadece o zaman genel/fallback araç taraması yap.
    # Ön-Etiketleme'nin kullandığı AYNI mantıkla (hazır COCO modeli, "car/
    # truck/bus" class'larını İSİMLE arayarak) tüm araçları buluyoruz, ama
    # SADECE öksüz plakayı İÇİNDE barındıran (bu plakanın gerçekten üzerinde
    # durduğu) kutuyu yeni bir "tanımlanmadı" araç olarak ekliyoruz --
    # alakasız arka plan araçlarını asla eklemiyoruz.
    if oksuz_plakalar:
        log(f"  {len(oksuz_plakalar)} plaka hiçbir bilinen araca eşlenemedi, "
            "genel/fallback araç taraması deneniyor...")
        try:
            genel_model = _onetiket_modelini_yukle(FUSION_GENEL_MODEL_ADI)
            genel_class_idleri = set(_arac_class_idlerini_bul(genel_model))
            genel_sonuc = genel_model(goruntu, verbose=False)[0]
            genel_kutular = []
            for kutu in genel_sonuc.boxes:
                class_id = int(kutu.cls[0])
                if genel_class_idleri and class_id not in genel_class_idleri:
                    continue
                x1, y1, x2, y2 = map(int, kutu.xyxy[0].tolist())
                genel_kutular.append(((x1, y1, x2, y2), float(kutu.conf[0])))

            for plaka_kutu, metin, ocr_guven, gecerli, tespit_guven in oksuz_plakalar:
                # bu öksüz plakayı İÇİNDE barındıran genel araç kutusunu bul
                en_iyi_oran, en_iyi_kutu, en_iyi_guven = 0.0, None, 0.0
                for genel_kutu, genel_guven in genel_kutular:
                    oran = _fusion_ortusme_orani(plaka_kutu, genel_kutu)
                    if oran > en_iyi_oran:
                        en_iyi_oran, en_iyi_kutu, en_iyi_guven = oran, genel_kutu, genel_guven

                if en_iyi_kutu is None or en_iyi_oran < FUSION_ESLESME_ESIGI:
                    log(f"  [uyari] '{metin}' için genel modelde de araç kutusu bulunamadı (atlandı).")
                    continue

                yeni_index = len(araclar)
                arac_kutulari.append(en_iyi_kutu)
                arac_tahminleri.append(("tanimlanmadi", en_iyi_guven, "taninmiyor"))
                araclar.append({
                    "arac_no": yeni_index,
                    "marka_model": "tanimlanmadi",
                    "marka_model_guven": round(en_iyi_guven, 3),
                    "marka_model_durum": "taninmiyor",
                    "plaka": metin,
                    "plaka_guven": round(ocr_guven, 3) if metin else None,
                    "plaka_durum": _fusion_plaka_durumu(ocr_guven, gecerli) if metin else "okunamadi",
                })
                log(f"  [fallback] '{metin}' plakası, genel modelin bulduğu bilinmeyen bir "
                    f"araca (guven={en_iyi_guven:.2f}) eşlendi.")
        except Exception as e:
            log(f"  [uyari] Genel/fallback araç taraması çalıştırılamadı: {e}")

    for hedef_index, (_tespit_guven, metin, ocr_guven, gecerli) in araca_en_iyi_aday.items():
        araclar[hedef_index]["plaka"] = metin
        araclar[hedef_index]["plaka_guven"] = round(ocr_guven, 3) if metin else None
        araclar[hedef_index]["plaka_durum"] = _fusion_plaka_durumu(ocr_guven, gecerli) if metin else "okunamadi"

    for arac in araclar:
        log(
            f"  Araç #{arac['arac_no']}: marka/model={arac['marka_model']} "
            f"({arac['marka_model_durum']}, guven={arac['marka_model_guven']})  |  "
            f"plaka={arac['plaka']} ({arac['plaka_durum']}, guven={arac['plaka_guven']})"
        )

    # --- Görselleştirme: araç kutuları (ultralytics .plot()) + fallback/plaka çizimleri ---
    cizili = marka_sonuc.plot()
    # ultralytics'in kendi .plot()'u çizgi kalınlığını/yazı boyutunu
    # görsel boyutuna göre OTOMATİK ölçekliyor -- ama bizim elle çizdiğimiz
    # (aşağıdaki) kutular sabit kalınlıktaydı (2px, 0.7 font). Küçük/normal
    # fotoğraflarda sorun olmasa da, telefon HEIC'i gibi ÇOK yüksek
    # çözünürlüklü (örn. 12000+ piksel) bir görselde 2 piksel ekranda
    # görünmez oluyordu -- bu yüzden plaka kutuları "hiç çizilmemiş" gibi
    # görünüyordu. Şimdi biz de görsel boyutuna göre ölçekliyoruz.
    goruntu_olcegi = max(cizili.shape[:2]) / 1000  # 1000px = referans boyut
    kalinlik = max(2, round(3 * goruntu_olcegi))
    yazi_olcek = max(0.7, 1.0 * goruntu_olcegi)
    yazi_kalinlik = max(2, round(2 * goruntu_olcegi))

    # "tanımlanmadı" (fallback/genel model) kutularını elle çiziyoruz --
    # .plot() sadece marka_sonuc'un kendi tespitlerini biliyor, bunları bilmiyor.
    for i, (class_adi, guven, durum) in enumerate(arac_tahminleri):
        if durum != "taninmiyor":
            continue
        x1, y1, x2, y2 = arac_kutulari[i]
        cv2.rectangle(cizili, (x1, y1), (x2, y2), (0, 165, 255), kalinlik)
        cv2.putText(cizili, f"tanimlanmadi {guven:.2f}", (x1, max(0, y1 - 8)),
                    cv2.FONT_HERSHEY_SIMPLEX, yazi_olcek, (0, 165, 255), yazi_kalinlik)
    for (x1, y1, x2, y2, _tespit_guven), (_kutu2, metin, _ocr_guven, _gecerli, _tg2) in zip(plaka_kutulari, plaka_okumalari):
        cv2.rectangle(cizili, (x1, y1), (x2, y2), (0, 255, 255), kalinlik)
        cv2.putText(cizili, metin or "?", (x1, max(0, y1 - 8)),
                    cv2.FONT_HERSHEY_SIMPLEX, yazi_olcek, (0, 255, 255), yazi_kalinlik)

    FUSION_CIKTI_KLASORU.mkdir(parents=True, exist_ok=True)
    dosya_adi = f"fusion_{int(_time.time() * 1000)}.jpg"
    cikti_yolu = FUSION_CIKTI_KLASORU / dosya_adi
    cv2.imwrite(str(cikti_yolu), cizili)

    # --- kayitlar/fusion_sonucu.json'a da kaydet (SQLite adımına hazır olsun) ---
    # NOT (bu kopyaya özel, 2026-08-04): FUSION_DB_YOLU'ndaki gerekçenin
    # aynısı -- otopark/'ın kendi kayitlar/ klasörüne karışmasın diye bu
    # kopyanın KENDİ İÇİNDE bir kayitlar/ klasörü kullanıyoruz.
    kayitlar_klasoru = Path(__file__).resolve().parent / "kayitlar"
    kayitlar_klasoru.mkdir(parents=True, exist_ok=True)
    with open(kayitlar_klasoru / "fusion_sonucu.json", "w", encoding="utf-8") as f:
        json.dump({"gorsel": gorsel_yolu, "araclar": araclar}, f, ensure_ascii=False, indent=2)

    # --- db/otogoz.db'ye BİRİKİMLİ (üzerine yazmayan) kayıt ---
    # JSON'un aksine bu her çalıştırmada EKLİYOR, geçmiş kaybolmuyor.
    # DB'ye yazarken bir sorun çıkarsa (örn. dosya kilitli) Fusion'ın asıl
    # sonucunu (görsel + JSON zaten üretildi) BOZMAMASI için hatayı
    # yutup sadece log'a yazıyoruz.
    try:
        eklenen_sayisi = _fusion_db_kaydet(gorsel_yolu, str(cikti_yolu), araclar)
        log(f"[bilgi] {eklenen_sayisi} kayıt db/otogoz.db'ye eklendi.")
    except Exception as e:
        log(f"[uyari] Veritabanına kaydedilemedi (Fusion sonucu yine de geçerli): {e}")

    return jsonify({
        "ok": True,
        "sonuc_url": f"/static/fusion_ciktilari/{dosya_adi}",
        "cikti_dosya_yolu": str(cikti_yolu),
        "araclar": araclar,
        "loglar": loglar,
    })


# ============================================================
# FUSION -- SÜREKLİ İZLEME (Adım 9, video kaynaklı MVP)
# ============================================================
# Tek görsel yerine bir VİDEOYU baştan sona, kare kare işler -- Fusion'ın
# tüm zincirini (marka/model + plaka + OCR + DB kayıt) her karede
# TEKRARLAMAK yerine, aynı aracın ekranda kaldığı sürece SADECE BİR KEZ
# kaydedilmesini sağlayan bir "dedup" (tekrar kayıt önleme) mantığı
# kullanıyor.
#
# DEDUP MANTIĞI -- neden tracking ID seçildi (plaka+zaman penceresi
# yerine): plaka okunamadığı durumlarda da çalışması gerekiyordu (plaka+
# zaman penceresi yaklaşımı, plaka NULL olduğunda hiçbir şeye
# dayanamazdı). `model.track()` (ByteTrack, ultralytics'e yerleşik) her
# fiziksel araca kareler arasında KALICI bir kimlik (ID) atıyor -- bir ID
# ilk göründüğünde tek seferlik "yeni araç" sayılıp DB'ye yazılıyor, aynı
# ID kadrajda kaldığı sürece bir daha yazılmıyor. Araç kadraj dışına
# çıkıp (örn. bir tur atıp) farklı bir ID ile geri gelirse bu YENİ bir
# geçiş sayılır -- bu aslında istenen davranış.
#
# BİLİNEN RİSK VE ÖNLEMİ: aynı fiziksel araca marka/model modelinin
# (class karışıklığından) birden fazla üst üste binen kutu vermesi
# ihtimaline karşı `agnostic_nms=True` kullanıyoruz -- bu, kutuları
# TAHMİN EDİLEN SINIFI görmezden gelerek sadece geometrik örtüşmeye göre
# birleştiriyor (NMS'in normal hali sadece AYNI sınıftaki kutuları
# birleştirir, farklı sınıf tahminli iki üst üste kutuyu birleştirmez).
# Bu olmadan aynı araç yanlışlıkla iki farklı ID/iki ayrı DB kaydı
# alabilirdi.
#
# İLERİDE WEBCAM'E BAĞLAMA: bu fonksiyon bir video DOSYASI okuyor
# (cv2.VideoCapture(video_yolu)), ama döngünün gövdesi (track ->
# yeni ID mi -> plaka eşle -> OCR -> DB kaydet) kaynaktan bağımsız --
# webcam'e geçmek istendiğinde sadece VideoCapture(0) ile değiştirmek
# ve WEBCAM bölümündeki MJPEG akış mantığını eklemek yeterli olacak,
# çekirdek mantığı yeniden yazmaya gerek yok.

IZLEME_DURUMU = {
    "calisiyor": False,
    "hata": None,
    "toplam_kare": 0,
    "islenen_kare": 0,
    "gorulen_arac_sayisi": 0,
    "kaydedilen_sayisi": 0,
    "loglar": [],
}
IZLEME_KILIDI = threading.Lock()
IZLEME_DURDURMA_ISARETI = threading.Event()
IZLEME_MAKSIMUM_LOG = 200

# Varsayılan bytetrack.yaml yerine ÖZEL bir tracker ayarı kullanıyoruz --
# gerçek bir test videosunda bulunan bir hata yüzünden (2026-07-31): aynı
# fiziksel araç bir bariyer önünde kısa süre kısmen kapanınca/düşük
# confidence'a düşünce tracker ID'sini kaybediyor, araç tekrar görününce
# YENİ bir ID ile 2. kez DB'ye kaydediliyordu. bytetrack_ozel.yaml bu
# "kayıp" toleransını (track_buffer) uzatıyor. Detay dosyanın içinde.
IZLEME_TRACKER_YAML = Path(__file__).resolve().parent / "bytetrack_ozel.yaml"

# Bir araç kaç kare boyunca hiç görünmezse "kadrajdan çıktı" sayılıp
# finalize edilsin (DB'ye o ana kadarki EN İYİ okumayla yazılsın)?
# tracker_buffer'dan (90) kasten biraz düşük tutuluyor -- amaç, araç
# gerçekten gittiğinde makul bir gecikmeyle (saniyeler içinde) DB'ye
# yazmak, tracker'ın kendi iç belleğinin dolmasını beklemek değil. Video
# sonuna kadar kadrajda kalan araçlar zaten döngü bitince ayrıca finalize
# ediliyor.
IZLEME_KAYIP_ESIGI_KARE = 45

# --- İKİNCİ GÜVENLİK AĞI: plaka + zaman penceresi ---
# Tracker'ın track_buffer'ı uzatılsa bile ID kaybı teorik olarak yine
# olabilir (örn. araç birkaç saniyeden UZUN süre kapalı kalırsa). Bu
# yüzden DB'ye yazmadan hemen önce EK bir kontrol yapıyoruz: okunan
# plaka, son birkaç saniye içinde zaten kaydedilmiş mi? Öyleyse bu YENİ
# track ID'yi kaydetmiyoruz -- muhtemelen aynı aracın tracker'da ID
# değiştirmiş hali. Bu, daha önce "tracking ID mi, plaka+zaman penceresi
# mi" tartışmasında ELENEN plaka+zaman penceresi yaklaşımının, tracking'i
# TAMAMEN İKAME ETMEK yerine ona EK bir güvenlik katmanı olarak
# kullanılması -- plaka okunamayan (NULL) durumlarda hâlâ çalışmaz ama
# okunabilen durumlarda tracker'ın kaçırdığı tekrarları da yakalar.
IZLEME_PLAKA_TEKRAR_PENCERESI_SN = 15


def _fusion_db_yakinda_ayni_plaka_var_mi(plaka: str, pencere_saniye: int = IZLEME_PLAKA_TEKRAR_PENCERESI_SN) -> bool:
    if not plaka:
        return False
    import sqlite3
    from datetime import datetime as _datetime, timedelta as _timedelta
    esik = (_datetime.now() - _timedelta(seconds=pencere_saniye)).isoformat(timespec="seconds")
    try:
        with sqlite3.connect(FUSION_DB_YOLU) as con:
            satir = con.execute(
                "SELECT 1 FROM tespitler WHERE plaka = ? AND tespit_zamani >= ? LIMIT 1",
                (plaka, esik),
            ).fetchone()
        return satir is not None
    except Exception:
        return False


def _izleme_log(mesaj: str):
    with IZLEME_KILIDI:
        IZLEME_DURUMU["loglar"].append(mesaj)
        if len(IZLEME_DURUMU["loglar"]) > IZLEME_MAKSIMUM_LOG:
            IZLEME_DURUMU["loglar"] = IZLEME_DURUMU["loglar"][-IZLEME_MAKSIMUM_LOG:]


def _izleme_dongusu(marka_model_yolu: str, plaka_model_yolu: str, video_yolu: str, conf: float):
    import time as _time
    try:
        import cv2
    except ImportError:
        IZLEME_DURUMU["hata"] = "opencv-python kurulu değil. Kurmak için: pip install opencv-python"
        IZLEME_DURUMU["calisiyor"] = False
        return

    acilan = None
    try:
        # DİKKAT: burada _fusion_marka_modelini_yukle (paylaşılan önbellek)
        # KASITLI OLARAK kullanılmıyor. ultralytics'in track(persist=True)
        # çağrısı, tracker state'ini (ByteTrack kimlikleri, kayıp-track
        # tamponu) doğrudan Model nesnesinin üzerine kalıcı olarak
        # ekliyor. Önbellekteki paylaşılan nesne kullanılsaydı: (a) İzleme
        # art arda iki kez çalıştırıldığında önceki videodan kalan track
        # ID'ler track_buffer=90 kare boyunca yeni videodaki araçlarla
        # yanlış eşleşebilirdi, (b) İzleme'den sonra aynı model dosyasıyla
        # Tekli Görsel Fusion çalıştırılırsa o çağrı da (fark etmeden)
        # tracker hattından geçip farklı davranırdı. Bu yüzden İzleme için
        # HER ÇALIŞTIRMADA taze, İZLEME'YE ÖZEL bir YOLO nesnesi yüklüyoruz
        # ve paylaşılan önbelleğe hiç yazmıyoruz (2026-08-03).
        from ultralytics import YOLO as _IzlemeYOLO
        marka_model = _IzlemeYOLO(marka_model_yolu)
        plaka_model = _fusion_plaka_modelini_yukle(plaka_model_yolu)
        reader = _fusion_ocr_okuyucusunu_yukle()

        acilan = cv2.VideoCapture(video_yolu)
        if not acilan.isOpened():
            raise RuntimeError(f"Video açılamadı: {video_yolu}")
        IZLEME_DURUMU["toplam_kare"] = int(acilan.get(cv2.CAP_PROP_FRAME_COUNT))

        # bekleyenler: track_id -> hâlâ kadrajda görülmeyi bekleyen (DB'ye
        # HENÜZ yazılmamış) araçların en güncel/en iyi bilgisi. Araç
        # kadrajdan kaybolunca (ya da video bitince) FİNALİZE edilip
        # DB'ye yazılıyor -- yani "ilk gördüğün anı" değil, "araç
        # kadrajda kaldığı SÜRE BOYUNCA elde edilen en iyi sonucu"
        # kaydediyoruz (2026-07-31, kullanıcı geri bildirimiyle
        # düzeltildi -- eskiden SADECE ilk karede tek seferlik OCR
        # deneniyordu, ilk kare genelde en kötü kare olabiliyordu --
        # far yansıması, açı, kısmi görünürlük gibi).
        bekleyenler = {}
        IZLEME_CIKTI_KLASORU = FUSION_CIKTI_KLASORU
        IZLEME_CIKTI_KLASORU.mkdir(parents=True, exist_ok=True)

        def _finalize_et(track_id):
            kayit = bekleyenler.pop(track_id, None)
            if kayit is None:
                return
            metin = kayit["plaka"]

            # İKİNCİ GÜVENLİK AĞI: tracker'ın (kısa süreli kapanma/düşük
            # confidence yüzünden) yeni bir ID atadığı ama AYNI plakayı
            # taşıyan bir araç mı bu? Öyleyse gerçek bir yeni geçiş
            # değil, tracker'ın kaçırdığı bir devamlılık -- atlıyoruz.
            if metin and _fusion_db_yakinda_ayni_plaka_var_mi(metin):
                _izleme_log(
                    f"Araç #{track_id} -- plaka '{metin}' son "
                    f"{IZLEME_PLAKA_TEKRAR_PENCERESI_SN} saniyede zaten kaydedilmişti "
                    "(muhtemelen tracker ID değiştirdi) -- tekrar kaydedilmedi."
                )
                return

            arac_kaydi = {
                "arac_no": track_id,
                "marka_model": kayit["class_adi"],
                "marka_model_guven": round(kayit["guven"], 3),
                "marka_model_durum": _fusion_marka_model_durumu(kayit["guven"]),
                "plaka": metin,
                "plaka_guven": round(kayit["plaka_guven"], 3) if metin else None,
                # Not: burada "okunamadi" kullanıyoruz (tek-görsel modundaki
                # OCR-başarısız durumuyla aynı etiket) -- çünkü İzleme
                # döngüsü araç kadrajda kaldığı SÜRE BOYUNCA her karede OCR
                # denemesi yapıyor (bkz. yukarısı); metin boşsa bu "hiç plaka
                # kutusu görülmedi" değil, "denendi ama hiçbir karede
                # okunamadı" anlamına geliyor. "bulunamadi" tek-görsel
                # modunda sadece "araca hiç plaka kutusu eşlenmedi" durumu
                # için ayrılmış (2026-08-03, tutarlılık düzeltmesi).
                "plaka_durum": _fusion_plaka_durumu(kayit["plaka_guven"], kayit["plaka_gecerli"]) if metin else "okunamadi",
            }

            sonuc_gorsel_yolu = ""
            if kayit.get("gorsel_kare") is not None:
                try:
                    dosya_adi = f"izleme_{int(_time.time() * 1000)}_id{track_id}.jpg"
                    tam_yol = IZLEME_CIKTI_KLASORU / dosya_adi
                    cv2.imwrite(str(tam_yol), kayit["gorsel_kare"])
                    sonuc_gorsel_yolu = str(tam_yol)
                except Exception:
                    pass

            try:
                _fusion_db_kaydet(video_yolu, sonuc_gorsel_yolu, [arac_kaydi])
                IZLEME_DURUMU["kaydedilen_sayisi"] += 1
                dusuk_guven_notu = " [DÜŞÜK GÜVEN -- muhtemelen yanlış/hayalet algılama olabilir]" if kayit["guven"] < FUSION_MARKA_ESIK_MUHTEMEL else ""
                _izleme_log(
                    f"Araç #{track_id} tamamlandı (kare {kayit['ilk_gorulen_kare']}-{kayit['son_gorulen_kare']}) -- "
                    f"{kayit['class_adi']} (guven={kayit['guven']:.2f}){dusuk_guven_notu}, "
                    f"plaka={metin or '(okunamadı)'} -- DB'ye kaydedildi."
                )
            except Exception as e:
                _izleme_log(f"Araç #{track_id} kaydedilemedi (DB hatası): {e}")

        islenen = 0
        while not IZLEME_DURDURMA_ISARETI.is_set():
            basarili, kare = acilan.read()
            if not basarili:
                break
            islenen += 1
            IZLEME_DURUMU["islenen_kare"] = islenen

            sonuc = marka_model.track(
                kare, persist=True, conf=conf, agnostic_nms=True,
                tracker=str(IZLEME_TRACKER_YAML), verbose=False,
            )[0]

            gorulen_bu_karede = {}  # track_id -> (arac_kutu, class_adi, guven)
            if sonuc.boxes is not None and sonuc.boxes.id is not None:
                for kutu in sonuc.boxes:
                    track_id = int(kutu.id[0])
                    x1, y1, x2, y2 = map(int, kutu.xyxy[0].tolist())
                    guven = float(kutu.conf[0])
                    class_adi = marka_model.names[int(kutu.cls[0])]
                    gorulen_bu_karede[track_id] = ((x1, y1, x2, y2), class_adi, guven)

                    if track_id not in bekleyenler:
                        bekleyenler[track_id] = {
                            "class_adi": class_adi, "guven": guven,
                            "plaka": None, "plaka_guven": 0.0, "plaka_gecerli": False,
                            "arac_kutu": (x1, y1, x2, y2),
                            "ilk_gorulen_kare": islenen, "son_gorulen_kare": islenen,
                            "gorsel_kare": None,
                        }
                        IZLEME_DURUMU["gorulen_arac_sayisi"] += 1
                    else:
                        kayit = bekleyenler[track_id]
                        kayit["son_gorulen_kare"] = islenen
                        kayit["arac_kutu"] = (x1, y1, x2, y2)
                        # Kareler arasında en YÜKSEK güvenli marka/model
                        # tahminini tutuyoruz -- tek bir kötü karenin
                        # (açı/ışık) yanlış class'ı kalıcı kılmasını
                        # önlemek için basit bir "en iyi kareyi seç"
                        # yaklaşımı (tam bir çoğunluk oylaması değil,
                        # ama tek kareye güvenmekten daha sağlam).
                        if guven > kayit["guven"]:
                            kayit["class_adi"], kayit["guven"] = class_adi, guven

            # Kayıp (bu karede görünmeyen) araçları kontrol et -- yeterince
            # uzun süredir kayıpsa finalize et (DB'ye yaz, bekleyenlerden çıkar).
            for tid in [t for t in bekleyenler if t not in gorulen_bu_karede]:
                if islenen - bekleyenler[tid]["son_gorulen_kare"] >= IZLEME_KAYIP_ESIGI_KARE:
                    _finalize_et(tid)

            if not gorulen_bu_karede:
                continue

            # Plaka tespitini SADECE henüz format-geçerli bir plakası
            # olmayan en az bir araç varsa çalıştırıyoruz (her karede
            # değil -- performans için, ama araç kadrajda kaldığı sürece
            # TEKRAR TEKRAR deneniyor, tek seferlik değil).
            okunmasi_gereken_var = any(not bekleyenler[tid]["plaka_gecerli"] for tid in gorulen_bu_karede)
            if not okunmasi_gereken_var:
                continue

            plaka_sonuc = plaka_model(kare, verbose=False)[0]
            plaka_kutulari = []
            for kutu in plaka_sonuc.boxes:
                pguven = float(kutu.conf[0])
                if pguven < FUSION_PLAKA_TESPIT_ESIK_MIN:
                    continue
                px1, py1, px2, py2 = map(int, kutu.xyxy[0].tolist())
                plaka_kutulari.append((px1, py1, px2, py2, pguven))

            yukseklik, genislik = kare.shape[:2]
            for track_id, (arac_kutu, class_adi, guven) in gorulen_bu_karede.items():
                kayit = bekleyenler[track_id]

                # Görsel anlık görüntüsünü HER karede güncelliyoruz (en
                # son/en net görünüşü tutmak için) -- finalize anında bu
                # kullanılacak.
                cizili_kare = kare.copy()
                x1, y1, x2, y2 = arac_kutu
                cv2.rectangle(cizili_kare, (x1, y1), (x2, y2), (0, 255, 0), 2)
                cv2.putText(cizili_kare, f"#{track_id} {kayit['class_adi']}", (x1, max(0, y1 - 8)),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 0), 2)
                kayit["gorsel_kare"] = cizili_kare

                if kayit["plaka_gecerli"]:
                    continue  # zaten geçerli formatlı bir okuma var, tekrar denemeye gerek yok

                en_iyi_oran, en_iyi_plaka = 0.0, None
                for pk in plaka_kutulari:
                    oran = _fusion_ortusme_orani(pk[:4], arac_kutu)
                    if oran > en_iyi_oran:
                        en_iyi_oran, en_iyi_plaka = oran, pk
                if en_iyi_plaka is None or en_iyi_oran < FUSION_ESLESME_ESIGI:
                    continue

                px1, py1, px2, py2, _pguven = en_iyi_plaka
                pay_x = int((px2 - px1) * 0.15)
                pay_y = int((py2 - py1) * 0.15)
                kx1, ky1 = max(0, px1 - pay_x), max(0, py1 - pay_y)
                kx2, ky2 = min(genislik, px2 + pay_x), min(yukseklik, py2 + pay_y)
                kirpik = kare[ky1:ky2, kx1:kx2]
                if kirpik.size == 0:
                    continue
                if kirpik.shape[1] < 300:
                    olcek = 300 / kirpik.shape[1]
                    kirpik = cv2.resize(kirpik, None, fx=olcek, fy=olcek, interpolation=cv2.INTER_CUBIC)
                metin, ocr_guven, gecerli = _fusion_plakayi_oku(cv2, reader, kirpik)
                if not metin:
                    continue

                # Bu okuma öncekinden DAHA İYİ mi? Önce format-geçerlilik
                # kazanır (geçerli > geçersiz), eşitse en yüksek OCR
                # güveni kazanır -- ilk bulunanı değil, en iyisini tutuyoruz.
                daha_iyi = (
                    (gecerli and not kayit["plaka_gecerli"]) or
                    (gecerli == kayit["plaka_gecerli"] and ocr_guven > kayit["plaka_guven"])
                )
                if daha_iyi:
                    kayit["plaka"], kayit["plaka_guven"], kayit["plaka_gecerli"] = metin, ocr_guven, gecerli

        # Video bitti (ya da durduruldu) -- hâlâ bekleyen (henüz kadrajdan
        # kaybolmamış/kayıp eşiğine ulaşmamış) tüm araçları finalize et.
        for tid in list(bekleyenler.keys()):
            _finalize_et(tid)

    except Exception as e:
        IZLEME_DURUMU["hata"] = str(e)
        _izleme_log(f"[HATA] {e}")
    finally:
        if acilan is not None:
            acilan.release()
        IZLEME_DURUMU["calisiyor"] = False


@app.route("/api/fusion/izleme_baslat", methods=["POST"])
def fusion_izleme_baslat():
    with IZLEME_KILIDI:
        if IZLEME_DURUMU["calisiyor"]:
            return jsonify({"hata": "Zaten devam eden bir izleme var, bitmesini bekle (ya da durdur)."}), 400

        veri = request.get_json()
        marka_model_yolu = veri.get("marka_model_dosyasi", "").strip()
        plaka_model_yolu = veri.get("plaka_model_dosyasi", "").strip()
        video_yolu = veri.get("video_dosyasi", "").strip()
        try:
            conf = float(veri.get("conf", 0.25))
        except (TypeError, ValueError):
            conf = 0.25

        if not marka_model_yolu:
            return jsonify({"hata": "Bir marka/model modeli seçmelisin."}), 400
        if not plaka_model_yolu:
            return jsonify({"hata": "Bir plaka modeli seçmelisin."}), 400
        if not video_yolu or not Path(video_yolu).exists():
            return jsonify({"hata": f"Video bulunamadı: {video_yolu}"}), 400

        IZLEME_DURUMU.update({
            "calisiyor": True,
            "hata": None,
            "toplam_kare": 0,
            "islenen_kare": 0,
            "gorulen_arac_sayisi": 0,
            "kaydedilen_sayisi": 0,
            "loglar": [],
        })
        IZLEME_DURDURMA_ISARETI.clear()

        thread = threading.Thread(
            target=_izleme_dongusu,
            args=(marka_model_yolu, plaka_model_yolu, video_yolu, conf),
            daemon=True,
        )
        thread.start()

    return jsonify({"ok": True})


@app.route("/api/fusion/izleme_durdur", methods=["POST"])
def fusion_izleme_durdur():
    IZLEME_DURDURMA_ISARETI.set()
    return jsonify({"ok": True})


@app.route("/api/fusion/izleme_durum")
def fusion_izleme_durum():
    with IZLEME_KILIDI:
        kopya = dict(IZLEME_DURUMU)
        kopya["loglar"] = list(IZLEME_DURUMU.get("loglar", []))
    return jsonify(kopya)


class Api:
    """pywebview'ın "js_api" köprüsü — JavaScript tarafından
    `window.pywebview.api.<metod>()` şeklinde çağrılabilen Python
    fonksiyonları. Native (gerçek Windows) klasör/dosya seçme
    pencerelerini burada açıyoruz, böylece kullanıcı hiçbir yolu elle
    yazmıyor — SADEKTECH'in kendi arayüzündeki gibi.
    """

    def klasor_sec(self):
        pencere = webview.windows[0]
        sonuc = pencere.create_file_dialog(webview.FOLDER_DIALOG)
        if not sonuc:
            return ""
        # pywebview sürümüne göre tek string ya da (string,) tuple dönebilir
        return sonuc[0] if isinstance(sonuc, (list, tuple)) else sonuc

    def dosya_sec(self, tur: str = "yaml"):
        # 'tur' parametresi, hangi sayfadan çağrıldığına göre dosya
        # seçme penceresinde varsayılan filtreyi doğru dosya tipine
        # ayarlar -- yoksa her yerde (model/görsel/video seçerken bile)
        # sadece YAML filtresi çıkıyordu, kullanıcı her seferinde elle
        # "Tüm dosyalar"a çevirmek zorunda kalıyordu.
        FILTRELER = {
            "yaml": ("YAML dosyaları (*.yaml;*.yml)", "Tüm dosyalar (*.*)"),
            "model": ("Model dosyaları (*.pt)", "Tüm dosyalar (*.*)"),
            "gorsel": ("Görsel dosyaları (*.jpg;*.jpeg;*.png;*.bmp;*.webp)", "Tüm dosyalar (*.*)"),
            "video": ("Video dosyaları (*.mp4;*.avi;*.mov;*.mkv)", "Tüm dosyalar (*.*)"),
        }
        file_types = FILTRELER.get(tur, ("Tüm dosyalar (*.*)",))

        pencere = webview.windows[0]
        sonuc = pencere.create_file_dialog(
            webview.OPEN_DIALOG,
            file_types=file_types,
        )
        if not sonuc:
            return ""
        return sonuc[0] if isinstance(sonuc, (list, tuple)) else sonuc

    def dosya_kaydet(self, kaynak_yol: str, onerilen_ad: str = ""):
        # Tarayıcının <a download> mekanizması pywebview'ın native
        # penceresinde güvenilir çalışmıyor (indirme diyaloğu hiç
        # açılmıyor). Bunun yerine gerçek bir Windows "Farklı Kaydet"
        # penceresi açıp, seçilen dosyayı doğrudan Python tarafında
        # kopyalıyoruz -- tarayıcı indirme mekanizmasına hiç ihtiyaç yok.
        if not kaynak_yol or not Path(kaynak_yol).exists():
            return ""
        pencere = webview.windows[0]
        sonuc = pencere.create_file_dialog(
            webview.SAVE_DIALOG,
            save_filename=onerilen_ad or Path(kaynak_yol).name,
        )
        if not sonuc:
            return ""
        hedef = sonuc[0] if isinstance(sonuc, (list, tuple)) else sonuc
        shutil.copy2(kaynak_yol, hedef)
        return hedef


def _sunucuyu_baslat():
    # debug=False + use_reloader=False: pywebview ile aynı süreçte
    # arka planda çalışacağı için Flask'ın kendi kendini yeniden
    # başlatan "reloader" özelliği burada işimize yaramaz/karışır.
    app.run(port=5000, debug=False, use_reloader=False)


if __name__ == "__main__":
    import threading

    # Flask sunucusunu arka planda ayrı bir thread'de çalıştırıyoruz,
    # ana thread'i ise pywebview'ın native pencere döngüsüne bırakıyoruz.
    sunucu_thread = threading.Thread(target=_sunucuyu_baslat, daemon=True)
    sunucu_thread.start()

    webview.create_window(
        "YOLO Araç Seti",
        "http://127.0.0.1:5000",
        width=1500,
        height=950,
        min_size=(1100, 700),
        js_api=Api(),
    )
    webview.start()
