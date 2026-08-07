// Veri Birleştir — Frontend mantığı

let kaynakKlasorler = [];
let ciktiKlasoru = "";

function kaynakListesiCiz() {
  const ul = document.getElementById("kaynak-listesi");
  ul.innerHTML = "";
  kaynakKlasorler.forEach((yol, i) => {
    const li = document.createElement("li");
    li.innerHTML = `<span>${yol}</span>`;
    const silBtn = document.createElement("button");
    silBtn.textContent = "sil";
    silBtn.addEventListener("click", () => {
      kaynakKlasorler.splice(i, 1);
      kaynakListesiCiz();
    });
    li.appendChild(silBtn);
    ul.appendChild(li);
  });
}

document.getElementById("klasor-ekle-btn").addEventListener("click", async () => {
  if (!window.pywebview || !window.pywebview.api) {
    alert("Native pencere API'si henüz hazır değil, bir saniye sonra tekrar dene.");
    return;
  }
  const yol = await window.pywebview.api.klasor_sec();
  if (!yol) return;
  if (!kaynakKlasorler.includes(yol)) {
    kaynakKlasorler.push(yol);
    kaynakListesiCiz();
  }
});

document.getElementById("cikti-sec-btn").addEventListener("click", async () => {
  if (!window.pywebview || !window.pywebview.api) {
    alert("Native pencere API'si henüz hazır değil, bir saniye sonra tekrar dene.");
    return;
  }
  const yol = await window.pywebview.api.klasor_sec();
  if (!yol) return;
  ciktiKlasoru = yol;
  document.getElementById("cikti_klasoru_goster").textContent = yol;
});

document.getElementById("calistir-btn").addEventListener("click", async () => {
  const hataEl = document.getElementById("birlestir-hata");
  const sonucEl = document.getElementById("sonuc-kutu");
  hataEl.textContent = "";
  sonucEl.classList.add("gizli");

  if (kaynakKlasorler.length === 0) {
    hataEl.textContent = "En az bir kaynak klasör eklemelisin.";
    return;
  }
  if (!ciktiKlasoru) {
    hataEl.textContent = "Bir çıktı klasörü seçmelisin.";
    return;
  }

  const btn = document.getElementById("calistir-btn");
  btn.disabled = true;
  btn.textContent = "Çalışıyor...";

  let veri;
  try {
    const cevap = await fetch("/api/veribirlestir/calistir", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        kaynak_klasorler: kaynakKlasorler,
        cikti_klasoru: ciktiKlasoru,
      }),
    });
    veri = await cevap.json();
  } finally {
    btn.disabled = false;
    btn.textContent = "BİRLEŞTİR";
  }

  if (veri.hata) {
    hataEl.textContent = veri.hata;
    return;
  }

  const satirlar = veri.sonuclar.map((s) => {
    if (s.hata) return `${s.sinif}: HATA - ${s.hata}`;
    return `${s.sinif.padEnd(20)} toplam=${s.toplam}  kopyalanan=${s.kopyalanan}  zaten_var=${s.zaten_var}  etiketsiz_atlandi=${s.etiketsiz_atlandi}`;
  });

  sonucEl.classList.remove("gizli");
  sonucEl.textContent =
    satirlar.join("\n") +
    `\n\n[ÖZET] Yeni kopyalanan: ${veri.toplam_kopyalanan}  Zaten mevcuttu: ${veri.toplam_zaten_var}  Etiketsiz (atlandı): ${veri.toplam_etiketsiz}\n` +
    `Çıktı: ${veri.cikti_klasoru}`;
});
