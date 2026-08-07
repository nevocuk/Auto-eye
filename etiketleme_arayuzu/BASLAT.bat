@echo off
chcp 65001 >nul
cd /d "%~dp0"

if exist ".venv\Scripts\activate.bat" (
    call ".venv\Scripts\activate.bat"
    python app.py
) else (
    where python >nul 2>nul
    if not %ERRORLEVEL%==0 (
        echo [HATA] Python bulunamadi ve .venv de yok. Once KURULUM.bat calistir.
        pause
        exit /b 1
    )
    echo [Bilgi] .venv bulunamadi, sistem Python'u ile calistiriliyor
    echo         (kurulumda "sistem Python'u" secildiyse bu normal).
    python app.py
)

if not %ERRORLEVEL%==0 (
    echo.
    echo Program bir hatayla kapandi, yukaridaki mesaja bakin.
    pause
)
