@echo off
chcp 65001 >nul
setlocal enabledelayedexpansion
cd /d "%~dp0"

echo ============================================================
echo   Evrensel YOLO Arac Seti - Kurulum
echo ============================================================
echo.
echo Su kutuphaneler kurulacak (varsayilan, herhangi bir YOLO
echo detect projesi icin gerekli olanlar):
echo   - flask, pyyaml, pywebview, Pillow, numpy   (arayuzun kendisi)
echo   - ultralytics, opencv-python, imageio-ffmpeg (egitim/test/on-etiketleme)
echo   - torch, torchvision                         (GPU varsa CUDA'li, yoksa CPU'lu surum)
echo.
echo Bu kopyadaki "Fusion" araci (proje-ozel, varsayilan KAPALI) icin
echo ayrica fast-plate-ocr ve pillow-heif gerekiyor -- Fusion'i hic
echo acmayacaksan bunlari kurmana gerek yok, asagida ayrica sorulacak.
echo.
echo Not: Bu kurulumu KOD YAZMADAN, sadece uygulamayi actiktan sonra da
echo yapabilirsin -- ana sayfadaki "Gereklilikler" karti ayni islemi
echo arayuzden, tek tusla yapiyor. Bu .bat dosyasi sadece ILK acilis
echo icin (flask/pywebview gibi arayuzun kendisini calistirmaya
echo yetecek paketleri kurmak icin) gerekli -- once bu calismali.
echo.
echo Internet baglantisi gerekli, birkac dakika surebilir.
echo ============================================================
echo.

REM --- 1) Python var mi kontrol et --------------------------------------
where py >nul 2>nul
if %ERRORLEVEL%==0 (
    set "PYCMD=py -3"
) else (
    where python >nul 2>nul
    if %ERRORLEVEL%==0 (
        set "PYCMD=python"
    ) else (
        echo [HATA] Python bulunamadi.
        echo Once https://www.python.org/downloads/ adresinden Python 3.10+ kurun.
        echo Kurulum sirasinda "Add Python to PATH" kutusunu isaretlemeyi unutmayin.
        pause
        exit /b 1
    )
)
echo Python bulundu: %PYCMD%
echo.

REM --- 2) Sanal ortam mi, sistem Python'u mu? ----------------------------
echo Kutuphaneler nereye kurulsun?
echo   [e] Sanal ortam (.venv) icine  -- ONERILEN, bu klasore ozel, sistemi
echo       kirletmez, baska Python projelerinle cakismaz.
echo   [h] Dogrudan sistem Python'una -- daha basit ama global kurulum olur.
set /p VENV_SEC="Sanal ortam kullanilsin mi? (e/h) [varsayilan: e]: "
if "!VENV_SEC!"=="" set "VENV_SEC=e"

if /i "!VENV_SEC!"=="e" (
    if not exist ".venv" (
        echo Sanal ortam olusturuluyor (.venv)...
        %PYCMD% -m venv .venv
        if not %ERRORLEVEL%==0 (
            echo [HATA] Sanal ortam olusturulamadi.
            pause
            exit /b 1
        )
    ) else (
        echo Sanal ortam zaten var, atlaniyor.
    )
    call ".venv\Scripts\activate.bat"
    set "PIPCMD=pip"
    set "PYRUNCMD=python"
) else (
    echo Sistem Python'u kullanilacak, .venv olusturulmayacak.
    set "PIPCMD=%PYCMD% -m pip"
    set "PYRUNCMD=%PYCMD%"
)
echo.

REM --- 2.5) Neler zaten kurulu, neler eksik? -----------------------------
echo Kutuphaneler kontrol ediliyor...
echo.
set "TORCH_KURULU=h"
for /f "tokens=1,2 delims=:" %%A in ('%PYRUNCMD% _kurulum_kontrol.py') do (
    echo   %%A:%%B
    if "%%A"=="torch" if "%%B"==" OK" set "TORCH_KURULU=e"
)
echo.

echo pip guncelleniyor...
%PIPCMD% install --upgrade pip >nul
echo.

REM --- 3) GPU var mi diye sor (dogru PyTorch surumu icin onemli) --------
if /i "!TORCH_KURULU!"=="e" (
    echo torch zaten kurulu gorunuyor.
    set /p TORCH_TEKRAR="Torch/torchvision tekrar kurulsun/guncellensin mi? (e/h) [varsayilan: h]: "
    if "!TORCH_TEKRAR!"=="" set "TORCH_TEKRAR=h"
) else (
    set "TORCH_TEKRAR=e"
)

if /i "!TORCH_TEKRAR!"=="e" (
    where nvidia-smi >nul 2>nul
    if %ERRORLEVEL%==0 (
        echo NVIDIA ekran karti bulundu, GPU destekli PyTorch kurulacak.
        set "GPU_VAR=e"
    ) else (
        echo NVIDIA ekran karti algilanmadi.
        set /p GPU_VAR="NVIDIA ekran kartin var mi? (e/h) [otomatik bulunamadi]: "
    )

    if /i "!GPU_VAR!"=="e" (
        echo GPU'lu PyTorch (CUDA) kuruluyor, bu biraz uzun surebilir...
        %PIPCMD% install torch torchvision --index-url https://download.pytorch.org/whl/cu121
    ) else (
        echo CPU'lu PyTorch kuruluyor...
        %PIPCMD% install torch torchvision
    )
) else (
    echo Torch kurulumu atlandi.
)
echo.

REM --- 4) Geri kalan varsayilan kutuphaneler (requirements.txt) ----------
echo Diger kutuphaneler kuruluyor (requirements.txt)...
%PIPCMD% install -r requirements.txt
if not %ERRORLEVEL%==0 (
    echo.
    echo [UYARI] Bazi paketler kurulurken hata oldu, yukaridaki mesajlara bakin.
    pause
    exit /b 1
)
echo.

REM --- 5) Fusion (opsiyonel, proje-ozel) paketleri sorulur ---------------
set /p FUSION_KUR="Fusion aracini da kullanacak misin? (e/h) [varsayilan: h]: "
if "!FUSION_KUR!"=="" set "FUSION_KUR=h"
if /i "!FUSION_KUR!"=="e" (
    echo Fusion paketleri kuruluyor (fast-plate-ocr, pillow-heif)...
    %PIPCMD% install "fast-plate-ocr[onnx]" pillow-heif
) else (
    echo Fusion paketleri atlandi -- istersen ana sayfadaki "Gelismis
    echo ozellikler" anahtarini actiktan sonra "Gereklilikler" sayfasindan
    echo (opsiyonel kutucugunu isaretleyip) sonra da kurabilirsin.
)

echo.
echo ============================================================
echo   KURULUM TAMAMLANDI
echo   Programi baslatmak icin BASLAT.bat dosyasina cift tiklayin.
echo   Eksik/guncel olmayan bir sey olursa, uygulama acildiktan
echo   sonra ana sayfadaki "Gereklilikler" karti ile de kontrol
echo   edip tamamlayabilirsin.
echo ============================================================
pause
