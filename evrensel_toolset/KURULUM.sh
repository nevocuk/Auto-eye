#!/usr/bin/env bash
# ============================================================
#   Evrensel YOLO Araç Seti — Linux/macOS Kurulum
# ============================================================
set -e
cd "$(dirname "$0")"

echo "============================================================"
echo "  Evrensel YOLO Araç Seti — Kurulum (Linux/macOS)"
echo "============================================================"
echo ""

# --- 1) Python kontrolü ---
if command -v python3 &>/dev/null; then
    PYCMD="python3"
elif command -v python &>/dev/null; then
    PYCMD="python"
else
    echo "[HATA] Python bulunamadı."
    echo "  Ubuntu/Debian: sudo apt install python3 python3-pip python3-venv"
    echo "  Fedora:        sudo dnf install python3 python3-pip"
    echo "  macOS:         brew install python3"
    exit 1
fi
echo "Python bulundu: $($PYCMD --version)"
echo ""

# --- 2) Linux sistem bağımlılıkları (pywebview için) ---
if [[ "$(uname)" == "Linux" ]]; then
    echo "Linux algılandı — pywebview için GTK ve WebKit2 gerekli."
    echo ""

    EKSIK=""
    # GObject introspection + GTK3 + WebKit2 kontrolü
    $PYCMD -c "import gi; gi.require_version('Gtk','3.0'); gi.require_version('WebKit2','4.1')" 2>/dev/null || EKSIK="var"

    if [[ -n "$EKSIK" ]]; then
        echo "Sistem paketleri eksik, kurmaya çalışıyorum..."
        echo "(sudo şifresi istenebilir)"
        echo ""

        if command -v apt &>/dev/null; then
            sudo apt update
            sudo apt install -y python3-gi python3-gi-cairo gir1.2-gtk-3.0 gir1.2-webkit2-4.1 \
                python3-dev libcairo2-dev libgirepository1.0-dev ffmpeg
        elif command -v dnf &>/dev/null; then
            sudo dnf install -y python3-gobject gtk3 webkit2gtk4.1 cairo-gobject-devel \
                gobject-introspection-devel ffmpeg
        elif command -v pacman &>/dev/null; then
            sudo pacman -S --noconfirm python-gobject gtk3 webkit2gtk-4.1 cairo ffmpeg
        else
            echo "[UYARI] Paket yöneticisi tanınamadı. Lütfen şunları elle kurun:"
            echo "  - python3-gi, python3-gi-cairo"
            echo "  - gir1.2-gtk-3.0, gir1.2-webkit2-4.1"
            echo "  - ffmpeg"
            echo ""
        fi
    else
        echo "GTK ve WebKit2 zaten kurulu, atlanıyor."
    fi
    echo ""
fi

# --- 3) Sanal ortam oluştur ---
if [[ ! -d ".venv" ]]; then
    echo "Sanal ortam oluşturuluyor (.venv)..."
    $PYCMD -m venv .venv
else
    echo "Sanal ortam zaten var, atlanıyor."
fi
source .venv/bin/activate
echo ""

# --- 4) pip güncelle ---
echo "pip güncelleniyor..."
pip install --upgrade pip -q
echo ""

# --- 5) PyTorch ---
echo "Kütüphaneler kontrol ediliyor..."
python _kurulum_kontrol.py
echo ""

TORCH_KURULU="hayir"
python -c "import torch" 2>/dev/null && TORCH_KURULU="evet"

if [[ "$TORCH_KURULU" == "hayir" ]]; then
    if command -v nvidia-smi &>/dev/null; then
        echo "NVIDIA GPU algılandı — CUDA destekli PyTorch kuruluyor..."
        pip install torch torchvision --index-url https://download.pytorch.org/whl/cu121
    else
        echo "GPU algılanmadı — CPU PyTorch kuruluyor..."
        pip install torch torchvision
    fi
else
    echo "torch zaten kurulu, atlanıyor."
fi
echo ""

# --- 6) requirements.txt ---
echo "Diğer kütüphaneler kuruluyor..."
pip install -r requirements.txt
echo ""

echo "============================================================"
echo "  KURULUM TAMAMLANDI"
echo "  Programı başlatmak için: ./BASLAT.sh"
echo "============================================================"
