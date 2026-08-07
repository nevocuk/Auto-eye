// Data Augment — Frontend mantığı

const secilenYollar = { gorsel_klasoru: "", etiket_klasoru: "", data_yaml: "", cikti_klasoru: "" };

// Sayfa ilk açıldığındaki (HTML'deki) varsayılan değerler -- "Tümünü
// Sıfırla" butonu kullanıcı absürt/aşırı bir değer girip önizlemeyi
// bozduğunda buraya geri dönmek için kullanılıyor. Değerler
// augment.html'deki başlangıç değerleriyle BİREBİR eşleşmeli.
const AUGMENT_VARSAYILANLAR = {
  mod: "sabit",
  adet: 3,
  filtre: "",
  teknikler: {
    parlaklik: { aktif: true, taban: 1.3, hedef: 0.7 },
    kontrast: { aktif: false, taban: 1.3, hedef: 0.7 },
    keskinlik: { aktif: false, taban: 1.5, hedef: 0.3 },
    blur: { aktif: false, taban: 2, hedef: 5 },
    golge: { aktif: false, taban: 0.3, hedef: 0.6 },
    gurultu: { aktif: false, taban: 15, hedef: 40 },
    sikistirma: { aktif: false, taban: 75, hedef: 30 },
  },
};

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
  const isim = (document.getElementById("cikti_adi").value || "augment").trim() || "augment";
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
    await filtreListesiniDoldur();
    await onizlemeYenile();
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
    await filtreListesiniDoldur();
    await onizlemeYenile();
  });
});

// Mod değişince "hedef değer" sütununu ve dinamik adet alanını göster/gizle
// -- ayrıca (dinamik/sabit değişimi önizlemeyi etkilemese de -- önizleme
// hep "taban" değerini gösteriyor -- tutarlılık için yine de yeniliyoruz.
document.querySelectorAll('input[name="mod"]').forEach((radio) => {
  radio.addEventListener("change", () => {
    const dinamikMi = document.querySelector('input[name="mod"]:checked').value === "dinamik";
    document.querySelectorAll(".dinamik-sutun").forEach((el) => {
      el.style.display = dinamikMi ? "" : "none";
    });
    document.getElementById("adet-satiri").style.display = dinamikMi ? "" : "none";
  });
});

function teknikAyarlariniTopla() {
  const teknikler = {};
  document.querySelectorAll(".teknik-aktif").forEach((cb) => {
    const teknik = cb.dataset.teknik;
    const taban = document.querySelector(`.teknik-taban[data-teknik="${teknik}"]`).value;
    const hedef = document.querySelector(`.teknik-hedef[data-teknik="${teknik}"]`).value;
    teknikler[teknik] = {
      aktif: cb.checked,
      taban: parseFloat(taban),
      hedef: parseFloat(hedef),
    };
  });
  return teknikler;
}

// ================= CANLI ÖNİZLEME (sayı + görsel birlikte) =================
// Kullanıcı ayarları değiştirdikçe (checkbox, taban değer, filtre, mod)
// OTOMATİK olarak hem "kaç görsel etkilenecek" sayısını hem de örnek
// görseli (orijinal + ayarlar uygulanmış hali) yeniliyoruz -- ayrı bir
// "ÖNİZLE" butonuna basmaya gerek kalmadan. Metin kutularında (taban/
// hedef değer, adet) her tuş vuruşunda değil, kısa bir DURAKLAMADAN
// sonra (debounce) tetikleniyor -- yoksa "1.3" yazarken "1", "1.", "1.3"
// için ayrı ayrı 3 istek atılırdı.

let onizlemeIstekSirasi = 0;   // yarışan (eski) cevapların ekranı geç güncellemesini önlemek için
let onizlemeZamanlayici = null;

async function onizlemeYenile() {
  const hataEl = document.getElementById("augment-hata");
  const sonucEl = document.getElementById("onizleme-sonuc");
  const gorselSatirEl = document.getElementById("onizleme-gorsel-satiri");
  const yukleniyorEl = document.getElementById("onizleme-yukleniyor");
  hataEl.textContent = "";

  if (!secilenYollar.gorsel_klasoru) {
    sonucEl.classList.add("gizli");
    gorselSatirEl.classList.add("gizli");
    return;
  }

  const buIstek = ++onizlemeIstekSirasi;
  yukleniyorEl.classList.remove("gizli");

  const filtre = document.getElementById("filtre").value;
  const teknikler = teknikAyarlariniTopla();

  const [sayiCevap, gorselCevap] = await Promise.all([
    fetch("/api/augment/on_izle", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ ...secilenYollar, filtre }),
    }).then((r) => r.json()),
    fetch("/api/augment/onizleme_gorsel", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ ...secilenYollar, filtre, teknikler }),
    }).then((r) => r.json()),
  ]);

  // Bu sırada kullanıcı ayarı tekrar değiştirip YENİ bir istek başlatmışsa,
  // bu (artık eski) cevabı ekrana yazmıyoruz -- yoksa yavaş gelen eski bir
  // cevap, hızlı gelen yeni bir cevabın üzerine geç yazıp ekranı
  // tutarsız/yanıltıcı gösterebilirdi.
  if (buIstek !== onizlemeIstekSirasi) return;
  yukleniyorEl.classList.add("gizli");

  if (sayiCevap.hata) {
    hataEl.textContent = sayiCevap.hata;
    sonucEl.classList.add("gizli");
    gorselSatirEl.classList.add("gizli");
    return;
  }

  sonucEl.classList.remove("gizli");
  sonucEl.innerHTML = `
    <strong>Toplam görsel (etiketli + etiketsiz):</strong> ${sayiCevap.toplam_etiketli}<br>
    <strong>Filtreyle eşleşen (çoğaltılacak):</strong> ${sayiCevap.filtreyle_eslesen}<br>
    <strong>Class'lar:</strong> ${sayiCevap.siniflar.join(", ")}
  `;

  if (gorselCevap.hata) {
    gorselSatirEl.classList.add("gizli");
    return;
  }

  const t = Date.now();
  document.getElementById("onizleme-gorsel-orijinal").src = gorselCevap.orijinal_url + "?t=" + t;
  document.getElementById("onizleme-gorsel-filtreli").src = gorselCevap.filtreli_url + "?t=" + t;
  gorselSatirEl.classList.remove("gizli");

  if (gorselCevap.aktif_teknik_yok) {
    hataEl.textContent = "Hiçbir teknik seçili değil -- 'Ayarlar uygulanmış hali' orijinalle aynı görünüyor.";
  }
}

function onizlemeYenileGecikmeli(gecikmeMs = 450) {
  clearTimeout(onizlemeZamanlayici);
  onizlemeZamanlayici = setTimeout(onizlemeYenile, gecikmeMs);
}

// Checkbox/radio/select gibi "anlık" kontrollerde GECİKMESİZ, metin/sayı
// kutularında (yazarken sürekli tetiklenmesin diye) GECİKMELİ yeniliyoruz.
document.querySelectorAll(".teknik-aktif").forEach((cb) => {
  cb.addEventListener("change", onizlemeYenile);
});
document.querySelectorAll(".teknik-taban, .teknik-hedef").forEach((el) => {
  el.addEventListener("input", () => onizlemeYenileGecikmeli());
});
document.getElementById("filtre").addEventListener("change", onizlemeYenile);
document.querySelectorAll('input[name="mod"]').forEach((radio) => {
  radio.addEventListener("change", onizlemeYenile);
});

// Görsel/etiket/data.yaml seçilince, filtre dropdown'ını data.yaml'daki
// class listesiyle otomatik doldurur -- kullanıcı elle yazmak zorunda kalmaz.
async function filtreListesiniDoldur() {
  const secim = document.getElementById("filtre");
  if (!secilenYollar.gorsel_klasoru) return;

  const cevap = await fetch("/api/augment/on_izle", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ ...secilenYollar, filtre: "" }),
  });
  const veri = await cevap.json();
  if (veri.hata || !veri.siniflar) return;

  const oncekiSecim = secim.value;
  secim.innerHTML = '<option value="">Tümü</option>';
  veri.siniflar.forEach((isim) => {
    const opt = document.createElement("option");
    opt.value = isim;
    opt.textContent = isim;
    secim.appendChild(opt);
  });
  if (veri.siniflar.includes(oncekiSecim)) secim.value = oncekiSecim;
}

document.getElementById("calistir-btn").addEventListener("click", async () => {
  const hataEl = document.getElementById("augment-hata");
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

  const mod = document.querySelector('input[name="mod"]:checked').value;
  const govde = {
    ...secilenYollar,
    filtre: document.getElementById("filtre").value,
    mod,
    adet: document.getElementById("adet").value,
    teknikler: teknikAyarlariniTopla(),
  };

  const cevap = await fetch("/api/augment/calistir", {
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
});

// "Tümünü Sıfırla" -- kullanıcı deneme yanılma yaparken (örn. blur'u
// 50'ye çıkarıp görsel tanınmaz hale gelince) tek tıkla başlangıç
// ayarlarına dönebilsin diye. Klasör/dosya SEÇİMLERİNE dokunmuyoruz
// (onları kaybetmek can sıkıcı olurdu) -- sadece augment TEKNİK
// ayarlarını (checkbox'lar, taban/hedef değerler), modu, filtreyi ve
// önizleme/hata kutularını sıfırlıyor.
document.getElementById("sifirla-btn").addEventListener("click", async () => {
  const v = AUGMENT_VARSAYILANLAR;

  document.querySelectorAll(".teknik-aktif").forEach((cb) => {
    const teknik = cb.dataset.teknik;
    if (v.teknikler[teknik]) cb.checked = v.teknikler[teknik].aktif;
  });
  document.querySelectorAll(".teknik-taban").forEach((el) => {
    const teknik = el.dataset.teknik;
    if (v.teknikler[teknik]) el.value = v.teknikler[teknik].taban;
  });
  document.querySelectorAll(".teknik-hedef").forEach((el) => {
    const teknik = el.dataset.teknik;
    if (v.teknikler[teknik]) el.value = v.teknikler[teknik].hedef;
  });

  document.querySelector(`input[name="mod"][value="${v.mod}"]`).checked = true;
  document.querySelectorAll(".dinamik-sutun").forEach((el) => { el.style.display = "none"; });
  document.getElementById("adet-satiri").style.display = "none";
  document.getElementById("adet").value = v.adet;

  document.getElementById("filtre").value = v.filtre;

  document.getElementById("augment-hata").textContent = "";
  document.getElementById("analiz-sonuc").classList.add("gizli");
  document.getElementById("analiz-sonuc").textContent = "";

  // Ayarlar sıfırlandıktan hemen sonra önizlemeyi (sayı + görsel) de
  // TEMİZ haliyle yenile -- "resimden filtreleri sil" isteğinin tam
  // karşılığı bu: kullanıcı butona basınca görselin GERÇEKTEN temiz/
  // varsayılan haline döndüğünü görsün.
  await onizlemeYenile();
});
