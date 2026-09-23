// Dataset Splitter — Frontend mantığı

const secilenYollar = { gorsel_klasoru: "", etiket_klasoru: "", data_yaml: "", cikti_klasoru: "" };

// Görsel klasörünün üst dizinini bulur (Windows "\" ve "/" ikisini de destekler),
// çıktı klasörü her zaman görsel klasörünün YANINA (üst dizinine), yazılan
// isimle otomatik oluşturuluyor -- kullanıcının boş bir klasör seçmesine gerek yok.
function ustDizin(yol) {
  const temiz = yol.replace(/[\\/]+$/, "");
  const kesim = Math.max(temiz.lastIndexOf("/"), temiz.lastIndexOf("\\"));
  if (kesim === -1) return temiz;
  return temiz.slice(0, kesim);
}

function ayrac(yol) {
  return yol.includes("\\") && !yol.includes("/") ? "\\" : "/";
}

function ciktiKlasorunuGuncelle() {
  const goster = document.getElementById("cikti_klasoru_goster");
  if (!secilenYollar.gorsel_klasoru) {
    secilenYollar.cikti_klasoru = "";
    goster.textContent = "— önce görsel klasörü seç —";
    return;
  }
  const isim = (document.getElementById("cikti_adi").value || "split").trim() || "split";
  const ust = ustDizin(secilenYollar.gorsel_klasoru);
  const tamYol = `${ust}${ayrac(secilenYollar.gorsel_klasoru)}${isim}`;
  secilenYollar.cikti_klasoru = tamYol;
  goster.textContent = tamYol;
}

document.getElementById("cikti_adi").addEventListener("input", ciktiKlasorunuGuncelle);

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
    if (hedef === "gorsel_klasoru") ciktiKlasorunuGuncelle();
  });
});

document.querySelectorAll(".dosya-sec-btn").forEach((btn) => {
  btn.addEventListener("click", async () => {
    if (!window.pywebview || !window.pywebview.api) {
      alert("Native pencere API'si henüz hazır değil, bir saniye sonra tekrar dene.");
      return;
    }
    const yol = await window.pywebview.api.dosya_sec("yaml");
    if (!yol) return;
    const hedef = btn.dataset.hedef;
    secilenYollar[hedef] = yol;
    document.getElementById(`${hedef}_goster`).textContent = yol;
  });
});

document.getElementById("onizle-btn").addEventListener("click", async () => {
  const hataEl = document.getElementById("splitter-hata");
  const sonucEl = document.getElementById("onizleme-sonuc");
  hataEl.textContent = "";

  if (!secilenYollar.gorsel_klasoru) {
    hataEl.textContent = "Önce bir görsel klasörü seçmelisin.";
    return;
  }

  const cevap = await fetch("/api/splitter/on_izle", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(secilenYollar),
  });
  const veri = await cevap.json();

  if (veri.hata) {
    hataEl.textContent = veri.hata;
    sonucEl.classList.add("gizli");
    return;
  }

  sonucEl.classList.remove("gizli");
  sonucEl.innerHTML = `
    <strong>Toplam görsel:</strong> ${veri.toplam_gorsel}<br>
    <strong>Etiketli (bölünecek):</strong> ${veri.eslesen}<br>
    <strong>Etiketsiz (atlanacak):</strong> ${veri.eksik_etiket}<br>
    <strong>Class'lar:</strong> ${veri.siniflar.join(", ")}
  `;
});

document.getElementById("bol-btn").addEventListener("click", async () => {
  const hataEl = document.getElementById("splitter-hata");
  const analizEl = document.getElementById("analiz-sonuc");
  hataEl.textContent = "";
  analizEl.classList.add("gizli");

  if (!secilenYollar.gorsel_klasoru) {
    hataEl.textContent = "Önce bir görsel klasörü seçmelisin.";
    return;
  }
  if (!secilenYollar.cikti_klasoru) {
    hataEl.textContent = "Çıktı klasörü hesaplanamadı, önce görsel klasörü seç.";
    return;
  }

  const govde = {
    ...secilenYollar,
    train_oran: document.getElementById("train_oran").value,
    val_oran: document.getElementById("val_oran").value,
    test_oran: document.getElementById("test_oran").value,
    seed: document.getElementById("seed").value,
  };

  const cevap = await fetch("/api/splitter/calistir", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(govde),
  });
  const veri = await cevap.json();

  if (veri.hata) {
    hataEl.textContent = veri.hata;
    return;
  }

  analizEl.classList.remove("gizli");
  analizEl.textContent = veri.analiz;
  const bosEl = document.getElementById("analiz-bos");
  if (bosEl) bosEl.style.display = "none";
});
