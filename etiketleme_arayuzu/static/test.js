// Model Test — Frontend mantığı (görsel + video + webcam + metrikler modları)

const secilenYollar = {
  model_dosyasi: "", gorsel_dosyasi: "",
  video_model_dosyasi: "", video_dosyasi: "",
  webcam_model_dosyasi: "",
  metrik_model_dosyasi: "", metrik_data_yaml: "",
  klasor_model_dosyasi: "", klasor: "",
};
let sonGorselCiktiYolu = "";

// --- Mod sekmeleri ---
document.querySelectorAll(".test-mod-btn").forEach((btn) => {
  btn.addEventListener("click", () => {
    document.querySelectorAll(".test-mod-btn").forEach((b) => b.classList.remove("test-mod-aktif"));
    btn.classList.add("test-mod-aktif");
    const mod = btn.dataset.mod;
    document.getElementById("mod-gorsel").classList.toggle("gizli", mod !== "gorsel");
    document.getElementById("mod-video").classList.toggle("gizli", mod !== "video");
    document.getElementById("mod-webcam").classList.toggle("gizli", mod !== "webcam");
    document.getElementById("mod-klasor").classList.toggle("gizli", mod !== "klasor");
    document.getElementById("mod-metrik").classList.toggle("gizli", mod !== "metrik");
    // Başka bir moda geçince webcam açık kalmasın (kamerayı gereksiz
    // meşgul etmeyelim) -- arka planda otomatik durdur.
    if (mod !== "webcam") webcamDurdur();
  });
});

// --- Native dosya seçme (görsel modu + video modu ortak) ---
document.querySelectorAll(".dosya-sec-btn").forEach((btn) => {
  btn.addEventListener("click", async () => {
    if (!window.pywebview || !window.pywebview.api) {
      alert("Native pencere API'si henüz hazır değil, bir saniye sonra tekrar dene.");
      return;
    }
    const hedef = btn.dataset.hedef;
    // data-tur varsa onu kullan (video paneli), yoksa hedef adına göre çıkar (görsel paneli)
    const tur = btn.dataset.tur || (hedef === "model_dosyasi" ? "model" : "gorsel");
    const yol = await window.pywebview.api.dosya_sec(tur);
    if (!yol) return;
    secilenYollar[hedef] = yol;
    document.getElementById(`${hedef}_goster`).textContent = yol;
  });
});

// ================= GÖRSEL MODU =================
document.getElementById("test-btn").addEventListener("click", async () => {
  const hataEl = document.getElementById("test-hata");
  const listeEl = document.getElementById("tespit-listesi-kutu");
  const gorselEl = document.getElementById("sonuc-gorsel");
  hataEl.textContent = "";

  if (!secilenYollar.model_dosyasi) { hataEl.textContent = "Önce bir model dosyası seç."; return; }
  if (!secilenYollar.gorsel_dosyasi) { hataEl.textContent = "Önce bir test görseli seç."; return; }

  const btn = document.getElementById("test-btn");
  btn.disabled = true;
  btn.textContent = "Çalışıyor...";

  try {
    const cevap = await fetch("/api/test/gorsel", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        model_dosyasi: secilenYollar.model_dosyasi,
        gorsel_dosyasi: secilenYollar.gorsel_dosyasi,
        conf: document.getElementById("conf").value,
      }),
    });
    const veri = await cevap.json();

    if (veri.hata) {
      hataEl.textContent = veri.hata;
      return;
    }

    gorselEl.src = veri.sonuc_url + "?t=" + Date.now(); // cache-busting
    gorselEl.classList.remove("gizli");
    sonGorselCiktiYolu = veri.cikti_dosya_yolu || "";

    listeEl.classList.remove("gizli");
    let icerik;
    if (veri.tespitler.length === 0) {
      icerik = `<strong>Tespit yok</strong> (confidence eşiğini düşürmeyi dene)`;
    } else {
      const satirlar = veri.tespitler
        .map((t) => `${t.sinif} — ${(t.guven * 100).toFixed(1)}%${t.renk ? ` — renk: ${t.renk}` : ""}`)
        .join("<br>");
      icerik = `<strong>FPS:</strong> ${veri.fps}  <strong>Süre:</strong> ${veri.sure_ms} ms<br><br><strong>Tespitler:</strong><br>${satirlar}`;
    }
    listeEl.innerHTML = icerik;

    if (sonGorselCiktiYolu) {
      const kaydetBtn = document.createElement("button");
      kaydetBtn.type = "button";
      kaydetBtn.className = "kopyala-btn";
      kaydetBtn.style.marginTop = "10px";
      kaydetBtn.textContent = "Farklı Kaydet...";
      kaydetBtn.addEventListener("click", async () => {
        if (!window.pywebview || !window.pywebview.api) return;
        const onerilenAd = sonGorselCiktiYolu.split(/[\\/]/).pop();
        await window.pywebview.api.dosya_kaydet(sonGorselCiktiYolu, onerilenAd);
      });
      listeEl.appendChild(document.createElement("br"));
      listeEl.appendChild(kaydetBtn);
    }
  } finally {
    btn.disabled = false;
    btn.textContent = "TEST ET";
  }
});

// ================= VİDEO MODU =================
let videoPollingId = null;

document.getElementById("video-test-btn").addEventListener("click", async () => {
  const hataEl = document.getElementById("video-test-hata");
  hataEl.textContent = "";

  if (!secilenYollar.video_model_dosyasi) { hataEl.textContent = "Önce bir model dosyası seç."; return; }
  if (!secilenYollar.video_dosyasi) { hataEl.textContent = "Önce bir test videosu seç."; return; }

  const cevap = await fetch("/api/test/video_baslat", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      model_dosyasi: secilenYollar.video_model_dosyasi,
      video_dosyasi: secilenYollar.video_dosyasi,
      conf: document.getElementById("video_conf").value,
    }),
  });
  const veri = await cevap.json();

  if (veri.hata) {
    hataEl.textContent = veri.hata;
    return;
  }

  document.getElementById("video-durum-satiri").classList.remove("gizli");
  document.getElementById("video-test-btn").disabled = true;

  if (videoPollingId) clearInterval(videoPollingId);
  videoPollingId = setInterval(videoDurumGuncelle, 1000);
  videoDurumGuncelle();
});

async function videoDurumGuncelle() {
  const cevap = await fetch("/api/test/video_durum");
  const d = await cevap.json();

  const durumEl = document.getElementById("video-durum-satiri");
  const videoEl = document.getElementById("sonuc-video");

  if (d.calisiyor) {
    durumEl.innerHTML = `<strong>İşleniyor:</strong> kare ${d.islenen_kare} / ${d.toplam_kare || "?"}`;
  } else if (d.hata) {
    durumEl.innerHTML = `<strong>Hata:</strong> ${d.hata}`;
  } else if (d.tamamlandi) {
    if (d.tarayicida_oynar) {
      durumEl.innerHTML = `<strong>Tamamlandı</strong> (${d.islenen_kare} kare işlendi)<br>`;
    } else {
      durumEl.innerHTML = `<strong>Tamamlandı</strong> (${d.islenen_kare} kare işlendi)<br>
        <span style="color:#f87171">Tarayıcıda oynatılamayabilir (codec sorunu) -- kaydedip VLC gibi bir oynatıcıda aç.</span><br>`;
    }
    const kaydetBtn = document.createElement("button");
    kaydetBtn.type = "button";
    kaydetBtn.className = "kopyala-btn";
    kaydetBtn.style.marginTop = "8px";
    kaydetBtn.textContent = "Farklı Kaydet...";
    kaydetBtn.addEventListener("click", async () => {
      if (!window.pywebview || !window.pywebview.api) return;
      const onerilenAd = d.cikti_dosya_yolu.split(/[\\/]/).pop();
      await window.pywebview.api.dosya_kaydet(d.cikti_dosya_yolu, onerilenAd);
    });
    durumEl.appendChild(kaydetBtn);

    videoEl.src = d.cikti_url + "?t=" + Date.now();
    videoEl.classList.remove("gizli");
  }

  if (!d.calisiyor) {
    clearInterval(videoPollingId);
    videoPollingId = null;
    document.getElementById("video-test-btn").disabled = false;
  }
}

// ================= WEBCAM MODU =================
let webcamPollingId = null;

document.getElementById("webcam-baslat-btn").addEventListener("click", async () => {
  const hataEl = document.getElementById("webcam-hata");
  hataEl.textContent = "";

  if (!secilenYollar.webcam_model_dosyasi) { hataEl.textContent = "Önce bir model dosyası seç."; return; }

  const cevap = await fetch("/api/test/webcam_baslat", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      model_dosyasi: secilenYollar.webcam_model_dosyasi,
      conf: document.getElementById("webcam_conf").value,
    }),
  });
  const veri = await cevap.json();

  if (veri.hata) {
    hataEl.textContent = veri.hata;
    return;
  }

  document.getElementById("webcam-baslat-btn").classList.add("gizli");
  document.getElementById("webcam-durdur-btn").classList.remove("gizli");
  document.getElementById("webcam-durum-satiri").classList.remove("gizli");

  // <img>'in kaynağını akış adresine bağlıyoruz -- tarayıcı bu bağlantıyı
  // açık tutup gelen her kareyi otomatik gösteriyor, bizim ayrıca "yenile"
  // yapmamıza gerek yok. "?t=" cache-busting için (tarayıcı aynı adresi
  // önbellekten almasın diye).
  const goruntuEl = document.getElementById("webcam-goruntu");
  goruntuEl.src = "/api/test/webcam_stream?t=" + Date.now();
  goruntuEl.classList.remove("gizli");

  if (webcamPollingId) clearInterval(webcamPollingId);
  webcamPollingId = setInterval(webcamDurumGuncelle, 1500);
  webcamDurumGuncelle();
});

document.getElementById("webcam-durdur-btn").addEventListener("click", webcamDurdur);

async function webcamDurdur() {
  if (webcamPollingId) {
    clearInterval(webcamPollingId);
    webcamPollingId = null;
  }
  document.getElementById("webcam-goruntu").src = "";
  document.getElementById("webcam-goruntu").classList.add("gizli");
  document.getElementById("webcam-baslat-btn").classList.remove("gizli");
  document.getElementById("webcam-durdur-btn").classList.add("gizli");
  document.getElementById("webcam-durum-satiri").classList.add("gizli");
  try {
    await fetch("/api/test/webcam_durdur", { method: "POST" });
  } catch (e) {
    // sayfa zaten kapanıyor olabilir, sessizce geç
  }
}

async function webcamDurumGuncelle() {
  const cevap = await fetch("/api/test/webcam_durum");
  const d = await cevap.json();

  const durumEl = document.getElementById("webcam-durum-satiri");
  if (d.hata) {
    durumEl.innerHTML = `<strong>Hata:</strong> ${d.hata}`;
    webcamDurdur();
    return;
  }
  durumEl.innerHTML = `<strong>Canlı</strong> -- işlenen kare: ${d.islenen_kare}`;

  if (!d.calisiyor) {
    // Arka planda (örn. bir hata yüzünden) kendiliğinden durmuşsa arayüzü
    // de senkronla.
    webcamDurdur();
  }
}

// ================= KLASÖR (TOPLU) MODU =================
document.querySelectorAll(".klasor-sec-btn").forEach((btn) => {
  btn.addEventListener("click", async () => {
    if (!window.pywebview || !window.pywebview.api) {
      alert("Native pencere API'si henüz hazır değil, bir saniye sonra tekrar dene.");
      return;
    }
    const yol = await window.pywebview.api.klasor_sec();
    if (!yol) return;
    const hedef = btn.dataset.hedef;
    secilenYollar[hedef] = yol;
    document.getElementById(`${hedef}_goster`).textContent = yol;
  });
});

document.getElementById("klasor-test-btn").addEventListener("click", async () => {
  const hataEl = document.getElementById("klasor-test-hata");
  const durumEl = document.getElementById("klasor-durum-satiri");
  const galeriEl = document.getElementById("klasor-galeri");
  hataEl.textContent = "";
  galeriEl.innerHTML = "";

  if (!secilenYollar.klasor_model_dosyasi) { hataEl.textContent = "Önce bir model dosyası seç."; return; }
  if (!secilenYollar.klasor) { hataEl.textContent = "Önce bir görsel klasörü seç."; return; }

  const btn = document.getElementById("klasor-test-btn");
  btn.disabled = true;
  btn.textContent = "İşleniyor...";
  durumEl.classList.remove("gizli");
  durumEl.innerHTML = "<strong>İşleniyor...</strong> (görsel sayısına göre biraz sürebilir, sayfa kilitlenmiş gibi görünebilir)";

  try {
    const cevap = await fetch("/api/test/klasor", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        model_dosyasi: secilenYollar.klasor_model_dosyasi,
        klasor: secilenYollar.klasor,
        conf: document.getElementById("klasor_conf").value,
      }),
    });
    const veri = await cevap.json();

    if (veri.hata) {
      hataEl.textContent = veri.hata;
      durumEl.classList.add("gizli");
      return;
    }

    durumEl.innerHTML = `<strong>Bitti</strong> — ${veri.toplam} görsel işlendi.`;

    galeriEl.innerHTML = veri.sonuclar.map((s) => {
      if (s.hata) {
        return `<div class="klasor-kart klasor-kart-hata">
          <div class="klasor-kart-bilgi"><strong>${s.dosya_adi}</strong><br>Hata: ${s.hata}</div>
        </div>`;
      }
      const tespitMetni = s.tespitler.length
        ? s.tespitler.map((t) => `${t.sinif} (%${(t.guven * 100).toFixed(0)})${t.renk ? ` — ${t.renk}` : ""}`).join("<br>")
        : "<em>Tespit yok</em>";
      return `<div class="klasor-kart">
        <img loading="lazy" src="${s.sonuc_url}">
        <div class="klasor-kart-bilgi">
          <strong>${s.dosya_adi}</strong><br>${tespitMetni}
        </div>
      </div>`;
    }).join("");
  } catch (e) {
    hataEl.textContent = "İstek başarısız: " + e;
    durumEl.classList.add("gizli");
  } finally {
    btn.disabled = false;
    btn.textContent = "KLASÖRÜ TEST ET";
  }
});

// Galeri kartlarındaki görsele tıklayınca büyük halini göster (lightbox).
// Kartlar dinamik olarak eklendiği için tıklamayı sabit üst elemana
// (event delegation) bağlıyoruz.
const klasorLightbox = document.getElementById("klasor-lightbox");
const klasorLightboxImg = document.getElementById("klasor-lightbox-img");

document.getElementById("klasor-galeri").addEventListener("click", (e) => {
  if (e.target.tagName !== "IMG") return;
  klasorLightboxImg.src = e.target.src;
  klasorLightbox.classList.remove("gizli");
});

klasorLightbox.addEventListener("click", () => klasorLightbox.classList.add("gizli"));
document.addEventListener("keydown", (e) => {
  if (e.key === "Escape") klasorLightbox.classList.add("gizli");
});

// ================= METRİKLER (mAP) MODU =================
let metrikPollingId = null;

document.getElementById("metrik-btn").addEventListener("click", async () => {
  const hataEl = document.getElementById("metrik-hata");
  const sonucEl = document.getElementById("metrik-sonuc-kutu");
  const durumEl = document.getElementById("metrik-durum-satiri");
  hataEl.textContent = "";
  sonucEl.classList.add("gizli");

  if (!secilenYollar.metrik_model_dosyasi) { hataEl.textContent = "Önce bir model dosyası seç."; return; }
  if (!secilenYollar.metrik_data_yaml) { hataEl.textContent = "Önce val içeren bir data.yaml seç."; return; }

  const cevap = await fetch("/api/test/metrik_hesapla", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({
      model_dosyasi: secilenYollar.metrik_model_dosyasi,
      data_yaml: secilenYollar.metrik_data_yaml,
    }),
  });
  const veri = await cevap.json();

  if (veri.hata) {
    hataEl.textContent = veri.hata;
    return;
  }

  document.getElementById("metrik-btn").disabled = true;
  durumEl.classList.remove("gizli");
  durumEl.innerHTML = "<strong>Hesaplanıyor...</strong> (val seti boyutuna göre biraz sürebilir)";

  if (metrikPollingId) clearInterval(metrikPollingId);
  metrikPollingId = setInterval(metrikDurumGuncelle, 1500);
});

async function metrikDurumGuncelle() {
  const cevap = await fetch("/api/test/metrik_durum");
  const d = await cevap.json();

  const hataEl = document.getElementById("metrik-hata");
  const durumEl = document.getElementById("metrik-durum-satiri");
  const sonucEl = document.getElementById("metrik-sonuc-kutu");

  if (d.hata) {
    hataEl.textContent = d.hata;
    durumEl.classList.add("gizli");
    clearInterval(metrikPollingId);
    metrikPollingId = null;
    document.getElementById("metrik-btn").disabled = false;
    return;
  }

  if (!d.calisiyor && d.tamamlandi && d.sonuc) {
    durumEl.classList.add("gizli");
    sonucEl.classList.remove("gizli");
    sonucEl.innerHTML = `
      <strong>mAP50:</strong> ${d.sonuc.map50}<br>
      <strong>mAP50-95:</strong> ${d.sonuc.map50_95}<br>
      <strong>Precision:</strong> ${d.sonuc.precision}<br>
      <strong>Recall:</strong> ${d.sonuc.recall}
    `;
    clearInterval(metrikPollingId);
    metrikPollingId = null;
    document.getElementById("metrik-btn").disabled = false;
  }
}
