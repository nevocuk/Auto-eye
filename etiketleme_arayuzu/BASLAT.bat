@echo off
chcp 65001 >nul
cd /d "%~dp0"

if exist ".venv\Scripts\activate.bat" (
    call ".venv\Scripts\activate.bat"
    goto calistir
)

where python >nul 2>nul
if errorlevel 1 (
    echo [HATA] Python bulunamadi ve .venv de yok. Once KURULUM.bat calistir.
    pause
    exit /b 1
)
echo [Bilgi] .venv bulunamadi, sistem Python'u ile calistiriliyor.

:calistir
python app.py
if errorlevel 1 (
    echo.
    echo Program bir hatayla kapandi, yukaridaki mesaja bakin.
    pause
)
