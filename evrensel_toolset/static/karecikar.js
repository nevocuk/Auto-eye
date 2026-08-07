// Video'dan Kare Çıkar — Frontend mantığı

const secilenYollar = { video_yolu: "", cikti_klasoru: "" };

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
  if (!secilenYollar.video_yolu) {
    secilenYollar.cikti_klasoru = "";
    goster.textContent = "— önce video seç —";
    return;
  }
  const isim = (document.getElementById("cikti_adi").value || "ham_kareler").trim() || "ham_kareler";
  const ust = ustDizin(secilenYollar.video_yolu);
  const tamYol = `${ust}${ayrac(secilenYollar.video_yolu)}${isim}`;
  secilenYollar.cikti_klasoru = tamYol;
  goster.textContent = tamYol;
}

document.getElementById("cikti_adi").addEventListener("input", ciktiKlasorunuGuncelle);

document.querySelectorAll(".dosya-sec-btn").forEach((btn) => {
  btn.addEventListener("click", async () => {
    if (!window.pywebview || !window.pywebview.api) {
      alert("Native pencere API'si henüz hazır değil, bir saniye sonra tekrar dene.");
      return;
    }
    const hedef = btn.dataset.hedef;
    const tur = btn.dataset.tur || "video";
    const yol = await window.pywebview.api.dosya_sec(tur);
    if (!yol) return;
    secilenYollar[hedef] = yol;
    document.getElementById(`${hedef}_goster`).textContent = yol;
    ciktiKlasorunuGuncelle();
  });
});

document.getElementById("calistir-btn").addEventListener("click", async () => {
  const hataEl = document.getElementById("karecikar-hata");
  const sonucEl = document.getElementById("sonuc-kutu");
  hataEl.textContent = "";
  sonucEl.classList.add("gizli");

  if (!secilenYollar.video_yolu) {
    hataEl.textContent = "Önce bir video dosyası seçmelisin.";
    return;
  }
  if (!secilenYollar.cikti_klasoru) {
    hataEl.textContent = "Çıktı klasörü hesaplanamadı, önce video seç.";
    return;
  }

  const btn = document.getElementById("calistir-btn");
  btn.disabled = true;
  btn.textContent = "Çalışıyor... (video uzunsa biraz sürebilir)";

  let veri;
  try {
    const cevap = await fetch("/api/karecikar/calistir", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        video_yolu: secilenYollar.video_yolu,
        cikti_klasoru: secilenYollar.cikti_klasoru,
        fps: document.getElementById("fps").value,
      }),
    });
    veri = await cevap.json();
  } finally {
    btn.disabled = false;
    btn.textContent = "KARE ÇIKAR";
  }

  if (veri.hata) {
    hataEl.textContent = veri.hata;
    return;
  }

  sonucEl.classList.remove("gizli");
  sonucEl.innerHTML = `
    <strong>${veri.uretilen}</strong> kare üretildi.<br>
    <strong>Klasör:</strong> ${veri.cikti_klasoru}<br><br>
    Şimdi bu klasörü Ön-Etiketleme veya Etiketleme arayüzüne verebilirsin.
  `;
});
