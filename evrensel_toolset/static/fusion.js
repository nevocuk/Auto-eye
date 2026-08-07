// Fusion (Plaka + Marka/Model) — Frontend mantığı

const fusionYollar = {
  marka_model_dosyasi: "", plaka_model_dosyasi: "", gorsel_dosyasi: "",
  izleme_marka_model_dosyasi: "", izleme_plaka_model_dosyasi: "", izleme_video_dosyasi: "",
};
let fusionSonCiktiYolu = "";

// --- Mod sekmeleri (Tekli Görsel / Sürekli İzleme) ---
document.querySelectorAll(".test-mod-btn").forEach((btn) => {
  btn.addEventListener("click", () => {
    document.querySelectorAll(".test-mod-btn").forEach((b) => b.classList.remove("test-mod-aktif"));
    btn.classList.add("test-mod-aktif");
    const mod = btn.dataset.mod;
    document.getElementById("mod-tekli").classList.toggle("gizli", mod !== "tekli");
    document.getElementById("mod-izleme").classList.toggle("gizli", mod !== "izleme");
  });
});

document.querySelectorAll(".dosya-sec-btn").forEach((btn) => {
  btn.addEventListener("click", async () => {
    if (!window.pywebview || !window.pywebview.api) {
      alert("Native pencere API'si henüz hazır değil, bir saniye sonra tekrar dene.");
      return;
    }
    const hedef = btn.dataset.hedef;
    const tur = btn.dataset.tur || "gorsel";
    const yol = await window.pywebview.api.dosya_sec(tur);
    if (!yol) return;
    fusionYollar[hedef] = yol;
    document.getElementById(`${hedef}_goster`).textContent = yol;
  });
});

// Durum -> Türkçe okunur etiket + renk sınıfı
const DURUM_ETIKET = {
  kesin: "kesin",
  muhtemel: "muhtemel",
  belirsiz: "belirsiz",
  taninmiyor: "tanımlanmadı (bilinmeyen model)",
  bulunamadi: "plaka bulunamadı",
  okunamadi: "okunamadı",
  format_gecersiz: "format geçersiz",
};

document.getElementById("fusion-btn").addEventListener("click", async () => {
  const hataEl = document.getElementById("fusion-hata");
  const tabloEl = document.getElementById("fusion-sonuc-tablo");
  const logEl = document.getElementById("fusion-log");
  const gorselEl = document.getElementById("fusion-sonuc-gorsel");
  hataEl.textContent = "";

  if (!fusionYollar.marka_model_dosyasi) { hataEl.textContent = "Önce marka/model modelini seç."; return; }
  if (!fusionYollar.plaka_model_dosyasi) { hataEl.textContent = "Önce plaka modelini seç."; return; }
  if (!fusionYollar.gorsel_dosyasi) { hataEl.textContent = "Önce bir test görseli seç."; return; }

  const btn = document.getElementById("fusion-btn");
  btn.disabled = true;
  btn.textContent = "Çalışıyor... (ilk seferde fast-plate-ocr modeli indirebilir, biraz sürebilir)";

  try {
    const cevap = await fetch("/api/fusion/calistir", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        marka_model_dosyasi: fusionYollar.marka_model_dosyasi,
        plaka_model_dosyasi: fusionYollar.plaka_model_dosyasi,
        gorsel_dosyasi: fusionYollar.gorsel_dosyasi,
      }),
    });
    const veri = await cevap.json();

    if (veri.loglar) {
      logEl.textContent = veri.loglar.join("\n");
      logEl.classList.remove("gizli");
    }

    if (veri.hata) {
      hataEl.textContent = veri.hata;
      return;
    }

    gorselEl.src = veri.sonuc_url + "?t=" + Date.now();
    gorselEl.classList.remove("gizli");
    fusionSonCiktiYolu = veri.cikti_dosya_yolu || "";

    tabloEl.classList.remove("gizli");
    const satirlar = veri.araclar.map((a) => {
      const marka = `${a.marka_model} (${DURUM_ETIKET[a.marka_model_durum] || a.marka_model_durum}, ${(a.marka_model_guven * 100).toFixed(1)}%)`;
      const plaka = a.plaka
        ? `${a.plaka} (${DURUM_ETIKET[a.plaka_durum] || a.plaka_durum}, ${(a.plaka_guven * 100).toFixed(1)}%)`
        : DURUM_ETIKET[a.plaka_durum] || "—";
      return `<strong>Araç #${a.arac_no}</strong> — marka/model: ${marka} &nbsp;|&nbsp; plaka: ${plaka}`;
    });
    tabloEl.innerHTML = satirlar.join("<br><br>");

    if (fusionSonCiktiYolu) {
      const kaydetBtn = document.createElement("button");
      kaydetBtn.type = "button";
      kaydetBtn.className = "kopyala-btn";
      kaydetBtn.style.marginTop = "10px";
      kaydetBtn.textContent = "Farklı Kaydet...";
      kaydetBtn.addEventListener("click", async () => {
        if (!window.pywebview || !window.pywebview.api) return;
        const onerilenAd = fusionSonCiktiYolu.split(/[\\/]/).pop();
        await window.pywebview.api.dosya_kaydet(fusionSonCiktiYolu, onerilenAd);
      });
      tabloEl.appendChild(document.createElement("br"));
      tabloEl.appendChild(kaydetBtn);
    }
  } finally {
    btn.disabled = false;
    btn.textContent = "ÇALIŞTIR";
  }
});

// ================= SÜREKLİ İZLEME MODU (video) =================
let izlemePollingId = null;

document.getElementById("izleme-baslat-btn").addEventListener("click", async () => {
  const hataEl = document.getElementById("izleme-hata");
  const logEl = document.getElementById("izleme-log");
  hataEl.textContent = "";

  if (!fusionYollar.izleme_marka_model_dosyasi) { hataEl.textContent = "Önce marka/model modelini seç."; return; }
  if (!fusionYollar.izleme_plaka_model_dosyasi) { hataEl.textContent = "Önce plaka modelini seç."; return; }
  if (!fusionYollar.izleme_video_dosyasi) { hataEl.textContent = "Önce bir video seç."; return; }

  const cevap = await fetch("/api/fusion/izleme_baslat", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      marka_model_dosyasi: fusionYollar.izleme_marka_model_dosyasi,
      plaka_model_dosyasi: fusionYollar.izleme_plaka_model_dosyasi,
      video_dosyasi: fusionYollar.izleme_video_dosyasi,
      conf: document.getElementById("izleme_conf").value,
    }),
  });
  const veri = await cevap.json();

  if (veri.hata) {
    hataEl.textContent = veri.hata;
    return;
  }

  document.getElementById("izleme-baslat-btn").classList.add("gizli");
  document.getElementById("izleme-durdur-btn").classList.remove("gizli");
  document.getElementById("izleme-durum-satiri").classList.remove("gizli");
  logEl.classList.remove("gizli");
  logEl.textContent = "";

  if (izlemePollingId) clearInterval(izlemePollingId);
  izlemePollingId = setInterval(izlemeDurumGuncelle, 1000);
  izlemeDurumGuncelle();
});

document.getElementById("izleme-durdur-btn").addEventListener("click", async () => {
  await fetch("/api/fusion/izleme_durdur", { method: "POST" });
});

async function izlemeDurumGuncelle() {
  const cevap = await fetch("/api/fusion/izleme_durum");
  const d = await cevap.json();

  const durumEl = document.getElementById("izleme-durum-satiri");
  const logEl = document.getElementById("izleme-log");

  const ilerleme = d.toplam_kare ? `${d.islenen_kare} / ${d.toplam_kare}` : `${d.islenen_kare}`;
  durumEl.innerHTML = d.calisiyor
    ? `<strong>İşleniyor:</strong> kare ${ilerleme} — görülen araç: ${d.gorulen_arac_sayisi} — DB'ye kaydedilen: ${d.kaydedilen_sayisi}`
    : (d.hata
        ? `<strong>Hata:</strong> ${d.hata}`
        : `<strong>Tamamlandı</strong> (${d.islenen_kare} kare, ${d.gorulen_arac_sayisi} araç görüldü, ${d.kaydedilen_sayisi} kayıt eklendi)`);

  if (d.loglar) logEl.textContent = d.loglar.join("\n");

  if (!d.calisiyor) {
    if (izlemePollingId) {
      clearInterval(izlemePollingId);
      izlemePollingId = null;
    }
    document.getElementById("izleme-baslat-btn").classList.remove("gizli");
    document.getElementById("izleme-durdur-btn").classList.add("gizli");
  }
}
