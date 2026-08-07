// Ön-Etiketleme — Frontend mantığı

const secilenYollar = { gorsel_klasoru: "", etiket_klasoru: "", data_yaml: "", model_dosyasi: "" };

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
    await classListesiniDoldur();
  });
});

document.querySelectorAll(".dosya-sec-btn").forEach((btn) => {
  btn.addEventListener("click", async () => {
    if (!window.pywebview || !window.pywebview.api) {
      alert("Native pencere API'si henüz hazır değil, bir saniye sonra tekrar dene.");
      return;
    }
    const hedef = btn.dataset.hedef;
    const tur = btn.dataset.tur || "yaml";
    const yol = await window.pywebview.api.dosya_sec(tur);
    if (!yol) return;
    secilenYollar[hedef] = yol;
    document.getElementById(`${hedef}_goster`).textContent = yol;
    if (hedef === "data_yaml") await classListesiniDoldur();
  });
});

// Görsel klasörü (veya data.yaml) seçilince, "Hedef class" dropdown'ını
// data.yaml'daki class listesiyle otomatik doldurur -- kullanıcı elle
// yazmak zorunda kalmaz, sadece var olanlardan seçer. Yeni bir class
// eklemek isterse "+ Yeni class ekle..." seçeneğiyle ayrı bir metin
// kutusu açılır (var olanlara sessizce dokunmayan onay akışı için).
async function classListesiniDoldur() {
  const secim = document.getElementById("hedef_class_secim");
  if (!secilenYollar.gorsel_klasoru) return;

  const cevap = await fetch("/api/onetiket/on_izle", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(secilenYollar),
  });
  const veri = await cevap.json();
  if (veri.hata) return;

  const oncekiSecim = secim.value;
  secim.innerHTML = "";
  (veri.siniflar || []).forEach((isim) => {
    const opt = document.createElement("option");
    opt.value = isim;
    opt.textContent = isim;
    secim.appendChild(opt);
  });
  const yeniOpt = document.createElement("option");
  yeniOpt.value = "__yeni__";
  yeniOpt.textContent = "+ Yeni class ekle...";
  secim.appendChild(yeniOpt);

  if ([...secim.options].some((o) => o.value === oncekiSecim)) {
    secim.value = oncekiSecim;
  }
  yeniClassAlaniniGuncelle();
}

function yeniClassAlaniniGuncelle() {
  const secim = document.getElementById("hedef_class_secim");
  const satir = document.getElementById("yeni_class_satiri");
  satir.classList.toggle("gizli", secim.value !== "__yeni__");
}

document.getElementById("hedef_class_secim").addEventListener("change", yeniClassAlaniniGuncelle);

document.getElementById("onizle-btn").addEventListener("click", async () => {
  const hataEl = document.getElementById("onetiket-hata");
  const sonucEl = document.getElementById("onizleme-sonuc");
  hataEl.textContent = "";

  if (!secilenYollar.gorsel_klasoru) {
    hataEl.textContent = "Önce bir görsel klasörü seçmelisin.";
    return;
  }

  const cevap = await fetch("/api/onetiket/on_izle", {
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
    <strong>Zaten etiketli:</strong> ${veri.etiketli}<br>
    <strong>Etiketsiz (işlenecek):</strong> ${veri.etiketsiz}<br>
    <strong>Var olan class'lar:</strong> ${veri.siniflar.length ? veri.siniflar.join(", ") : "(yok, data.yaml henüz oluşmamış)"}
  `;
});

document.getElementById("calistir-btn").addEventListener("click", async () => {
  await calistir(false);
});

// onay: true/false -> daha önce "onay_gerekli" cevabı geldiyse, kullanıcının
// confirm() penceresine verdiği cevaba göre tekrar çağrılır.
async function calistir(onay) {
  const hataEl = document.getElementById("onetiket-hata");
  const sonucEl = document.getElementById("sonuc-kutu");
  hataEl.textContent = "";
  sonucEl.classList.add("gizli");

  if (!secilenYollar.gorsel_klasoru) {
    hataEl.textContent = "Önce bir görsel klasörü seçmelisin.";
    return;
  }
  const secim = document.getElementById("hedef_class_secim").value;
  const hedefClass = secim === "__yeni__"
    ? document.getElementById("yeni_class_adi").value.trim()
    : secim;
  if (!hedefClass) {
    hataEl.textContent = secim === "__yeni__"
      ? "Yeni class için bir isim yazmalısın (örn. fiat_egea)."
      : "Bir hedef class seçmelisin.";
    return;
  }

  const govde = {
    ...secilenYollar,
    hedef_class: hedefClass,
    conf: document.getElementById("conf").value,
    sadece_en_buyuk: document.getElementById("sadece_en_buyuk").checked,
    uzerine_yaz: document.getElementById("uzerine_yaz").checked,
    onay,
  };

  const btn = document.getElementById("calistir-btn");
  btn.disabled = true;
  btn.textContent = "Çalışıyor...";

  let veri;
  try {
    const cevap = await fetch("/api/onetiket/calistir", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(govde),
    });
    veri = await cevap.json();
  } finally {
    btn.disabled = false;
    btn.textContent = "ÇALIŞTIR";
  }

  if (veri.onay_gerekli) {
    const mesaj =
      `"${veri.yeni_class}" var olan class listesinde yok.\n\n` +
      `Var olan class'lar (dokunulmayacak): ${veri.mevcut_siniflar.join(", ") || "(yok)"}\n\n` +
      `Bunu YENİ bir class olarak eklemek istiyor musun?`;
    if (confirm(mesaj)) {
      await calistir(true);
    }
    return;
  }

  if (veri.hata) {
    hataEl.textContent = veri.hata;
    return;
  }

  sonucEl.classList.remove("gizli");
  sonucEl.innerHTML = `
    <strong>Hedef class:</strong> ${veri.hedef_class} (id: ${veri.hedef_id})<br>
    <strong>Toplam görsel:</strong> ${veri.toplam_gorsel}<br>
    <strong>Yeni etiketlenen:</strong> ${veri.yazilan}<br>
    <strong>Zaten etiketli olduğu için atlanan:</strong> ${veri.atlanan_zaten_etiketli}<br>
    <strong>Araç tespit edilemeyen:</strong> ${veri.tespit_yok}<br><br>
    Şimdi Etiketleme arayüzünden bu klasörü açıp kontrol et ve yanlış/eksik olanları düzelt.
  `;
}
