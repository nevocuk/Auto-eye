// Model Eğitimi — Frontend mantığı

const secilenYollar = { model_dosyasi: "", data_yaml: "", proje_klasoru: "", last_pt_dosyasi: "" };
let pollingId = null;

document.querySelectorAll(".dosya-sec-btn").forEach((btn) => {
  btn.addEventListener("click", async () => {
    if (!window.pywebview || !window.pywebview.api) {
      alert("Native pencere API'si henüz hazır değil, bir saniye sonra tekrar dene.");
      return;
    }
    const hedef = btn.dataset.hedef;
    const tur = btn.dataset.tur || (hedef === "model_dosyasi" ? "model" : "yaml");
    const yol = await window.pywebview.api.dosya_sec(tur);
    if (!yol) return;
    secilenYollar[hedef] = yol;
    document.getElementById(`${hedef}_goster`).textContent = yol;
  });
});

// --- Mod seçimi: Yeni Eğitim / Var Olan Eğitime Devam Et ---
document.querySelectorAll('input[name="egitim_mod"]').forEach((radio) => {
  radio.addEventListener("change", () => {
    const devamMi = document.querySelector('input[name="egitim_mod"]:checked').value === "devam";
    document.getElementById("devam-et-alanlari").classList.toggle("gizli", !devamMi);
    document.getElementById("yeni-egitim-alanlari").classList.toggle("gizli", devamMi);
  });
});

// --- Gelişmiş Ayarlar tablosunu aç/kapa ---
document.getElementById("gelismis-toggle-btn").addEventListener("click", () => {
  const tablo = document.getElementById("gelismis-tablo");
  const btn = document.getElementById("gelismis-toggle-btn");
  const acikMi = !tablo.classList.contains("gizli");
  tablo.classList.toggle("gizli", acikMi);
  btn.innerHTML = acikMi
    ? "Gelişmiş Ayarlar (loss ağırlıkları / augmentation) &#9662;"
    : "Gelişmiş Ayarlar (loss ağırlıkları / augmentation) &#9652;";
});

// Gelişmiş ayar alanlarının id listesi -- hepsi ultralytics train()'e
// aynı isimle geçiyor, varsayılan değerleri ultralytics'in kendi
// varsayılanlarıyla aynı (dokunulmazsa davranış değişmez).
const GELISMIS_ALANLAR = [
  "cls", "box", "dfl", "fl_gamma", "mosaic", "erasing",
  "hsv_h", "hsv_s", "hsv_v", "degrees", "translate", "scale",
  "shear", "perspective", "flipud", "fliplr", "mixup", "copy_paste",
  "cutmix", "bgr", "close_mosaic", "workers", "cache", "lr0", "warmup_epochs",
];

function gelismisAyarlariTopla() {
  const sonuc = {};
  GELISMIS_ALANLAR.forEach((id) => {
    sonuc[id] = document.getElementById(id).value;
  });
  // multi_scale bir onay kutusu (checkbox), diğerleri gibi .value değil
  // .checked okunmalı; freeze ise boş bırakılabilir (boş = kapalı/None).
  sonuc["multi_scale"] = document.getElementById("multi_scale").checked;
  sonuc["freeze"] = document.getElementById("freeze").value;
  sonuc["cos_lr"] = document.getElementById("cos_lr").checked;
  return sonuc;
}

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

document.getElementById("baslat-btn").addEventListener("click", async () => {
  const hataEl = document.getElementById("egitim-hata");
  hataEl.textContent = "";

  const mod = document.querySelector('input[name="egitim_mod"]:checked').value;
  let govde;

  if (mod === "devam") {
    if (!secilenYollar.last_pt_dosyasi) { hataEl.textContent = "Önce bir last.pt dosyası seç."; return; }
    govde = { mod: "devam", last_pt_dosyasi: secilenYollar.last_pt_dosyasi };
  } else {
    const modelAdiYazilan = document.getElementById("model_adi_yaz").value.trim();
    const modelDosyasi = modelAdiYazilan || secilenYollar.model_dosyasi;

    if (!modelDosyasi) { hataEl.textContent = "Önce bir başlangıç modeli seç ya da adını yaz."; return; }
    if (!secilenYollar.data_yaml) { hataEl.textContent = "Önce bir data.yaml seç."; return; }
    if (!secilenYollar.proje_klasoru) { hataEl.textContent = "Önce bir çıktı (run) klasörü seç."; return; }

    govde = {
      mod: "yeni",
      model_dosyasi: modelDosyasi,
      data_yaml: secilenYollar.data_yaml,
      proje_klasoru: secilenYollar.proje_klasoru,
      calisma_adi: document.getElementById("calisma_adi").value,
      epochs: document.getElementById("epochs").value,
      imgsz: document.getElementById("imgsz").value,
      batch: document.getElementById("batch").value,
      patience: document.getElementById("patience").value,
      optimizer: document.getElementById("optimizer").value,
      device: document.getElementById("device").value,
      ...gelismisAyarlariTopla(),
    };
  }

  const cevap = await fetch("/api/egitim/baslat", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(govde),
  });
  const veri = await cevap.json();

  if (veri.hata) {
    hataEl.textContent = veri.hata;
    return;
  }

  document.getElementById("durum-satiri").classList.remove("gizli");
  document.getElementById("egitim-log").classList.remove("gizli");
  document.getElementById("log-kopyala-btn").classList.remove("gizli");
  document.getElementById("baslat-btn").disabled = true;

  if (pollingId) clearInterval(pollingId);
  pollingId = setInterval(durumGuncelle, 1500);
  durumGuncelle();
});

async function durumGuncelle() {
  const cevap = await fetch("/api/egitim/durum");
  const d = await cevap.json();

  const durumEl = document.getElementById("durum-satiri");
  const logEl = document.getElementById("egitim-log");

  let durumMetni;
  if (d.calisiyor) {
    durumMetni = `Çalışıyor -- epoch ${d.epoch}/${d.toplam_epoch}`;
  } else if (d.hata) {
    durumMetni = `Hata: ${d.hata}`;
  } else if (d.tamamlandi) {
    durumMetni = `Tamamlandı. En iyi model: ${d.en_iyi_model_yolu}`;
  } else {
    durumMetni = "Beklemede";
  }

  const metrikSatiri = Object.entries(d.son_metrikler || {})
    .map(([k, v]) => `${k}=${v.toFixed(4)}`)
    .join("  ");

  durumEl.innerHTML = `<strong>${durumMetni}</strong>${metrikSatiri ? "<br>" + metrikSatiri : ""}`;
  logEl.textContent = (d.loglar || []).join("\n");
  logEl.scrollTop = logEl.scrollHeight;

  if (!d.calisiyor) {
    clearInterval(pollingId);
    pollingId = null;
    document.getElementById("baslat-btn").disabled = false;
    if (d.tamamlandi) grafikleriGoster();
  }
}

// Eğitim bitince ultralytics'in kendi kaydettiği sonuç grafiklerini (varsa)
// göster -- klasörde dosya yoksa (örn. çok kısa/erken durmuş bir eğitim)
// img.onerror ile o sütunu sessizce gizli tutuyoruz.
function grafikleriGoster() {
  const kutu = document.getElementById("egitim-grafikler");
  const zamanDamgasi = `?t=${Date.now()}`; // tarayıcı önbelleğini bypass etmek için

  const results = document.getElementById("grafik-results");
  const confusion = document.getElementById("grafik-confusion");

  results.onerror = () => { results.closest(".egitim-grafik-sutun").classList.add("gizli"); };
  confusion.onerror = () => { confusion.closest(".egitim-grafik-sutun").classList.add("gizli"); };
  results.onload = () => { results.closest(".egitim-grafik-sutun").classList.remove("gizli"); };
  confusion.onload = () => { confusion.closest(".egitim-grafik-sutun").classList.remove("gizli"); };

  results.src = `/api/egitim/grafik/results.png${zamanDamgasi}`;
  confusion.src = `/api/egitim/grafik/confusion_matrix.png${zamanDamgasi}`;
  kutu.classList.remove("gizli");
}

// Native pywebview penceresinde metin seçip sağ-tıkla kopyalamak her zaman
// sorunsuz çalışmayabiliyor -- bu yüzden tek tuşla panoya kopyalama butonu.
document.getElementById("log-kopyala-btn").addEventListener("click", async () => {
  const metin = document.getElementById("egitim-log").textContent;
  const btn = document.getElementById("log-kopyala-btn");
  try {
    await navigator.clipboard.writeText(metin);
  } catch (e) {
    // navigator.clipboard bazı native pencerelerde kısıtlı olabilir --
    // gizli bir textarea üzerinden eski yöntemle (execCommand) dene.
    const gecici = document.createElement("textarea");
    gecici.value = metin;
    gecici.style.position = "fixed";
    gecici.style.opacity = "0";
    document.body.appendChild(gecici);
    gecici.focus();
    gecici.select();
    document.execCommand("copy");
    document.body.removeChild(gecici);
  }
  const oncekiMetin = btn.textContent;
  btn.textContent = "Kopyalandı";
  setTimeout(() => { btn.textContent = oncekiMetin; }, 1500);
});
