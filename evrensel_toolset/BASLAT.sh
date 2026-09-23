#!/usr/bin/env bash
cd "$(dirname "$0")"

if [[ -d ".venv" ]]; then
    source .venv/bin/activate
    python app.py
else
    if ! command -v python3 &>/dev/null; then
        echo "[HATA] Python bulunamadı ve .venv de yok. Önce KURULUM.sh çalıştır."
        exit 1
    fi
    echo "[Bilgi] .venv bulunamadı, sistem Python'u ile çalıştırılıyor."
    python3 app.py
fi
