// Detect Etiketleme Arayüzü — Frontend mantığı
//
// Koordinat sistemi hakkında önemli not:
// Kutuları (x1,y1,x2,y2) hep görselin GERÇEK (natural) piksel boyutunda
// tutuyoruz — canvas'ın görüntülenen boyutu artık görselin gerçek
// boyutuyla AYNI DEĞİL (zoom eklendiği için). Canvas'a çizerken
// ctx.translate(pan) + ctx.scale(zoom) uyguluyoruz, böylece kutuları
// hep "görsel uzayında" tutup, ekranda nasıl göründüğünü zoom/pan
// belirliyor. Fare tıklamalarını da aynı şekilde tersine çeviriyoruz
// (canvas pikseli -> görsel pikseli).

function _e(s) { if (s == null) return ""; const d = document.createElement("div"); d.textContent = String(s); return d.innerHTML; }

const RENKLER = [
  "#ef4444", "#3b82f6", "#22c55e", "#eab308", "#a855f7",
  "#ec4899", "#14b8a6", "#f97316", "#6366f1", "#84cc16",
];

let siniflar = [];
let gorseller = []; // [{ad, etiketli}]
let mevcutIndex = 0;
let aktifSinif = 0;
let mevcutGorsel = new Image();
let kutular = []; // {sinif, x1, y1, x2, y2} -- GÖRSEL (natural) piksel uzayında
let seciliKutuIndex = null;

let cizimBasladi = false;
let cizimBaslangicGorsel = { x: 0, y: 0 }; // görsel uzayında başlangıç noktası
let onizlemeGorsel = null; // sürüklerken önizleme kutusu (görsel uzayında)

// --- Zoom / pan durumu ---
let zoom = 1;
let pan = { x: 0, y: 0 };
let fareCanvasNoktasi = null; // crosshair için, canvas (ekran) uzayında son fare konumu

const canvas = document.getElementById("canvas");
const ctx = canvas.getContext("2d");

// --- Seçilen yolları tutan basit state (native pencerelerle dolduruluyor) ---
const secilenYollar = { gorsel_klasoru: "", etiket_klasoru: "", data_yaml: "" };

window.addEventListener("pywebviewready", () => {});

// --- Native klasör/dosya seçme butonları ---
document.querySelectorAll(".klasor-sec-btn").forEach((btn) => {
  btn.addEventListener("click", async () => {
    if (!window.pywebview || !window.pywebview.api) {
      alert("Native pencere API'si henüz hazır değil, bir saniye sonra tekrar dene.");
      return;
    }
    const yol = await window.pywebview.api.klasor_sec();
    if (!yol) return; // kullanıcı iptal etti
    const hedef = btn.dataset.hedef;
    secilenYollar[hedef] = yol;
    document.getElementById(`${hedef}_goster`).textContent = yol;
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

// --- Yükleme butonu ---
document.getElementById("yukle-btn").addEventListener("click", async () => {
  await projeyiYukle(false);
});

// onay: true/false -> daha önce "onay_gerekli" cevabı geldiyse, kullanıcının
// confirm() penceresine verdiği cevaba göre tekrar çağrılır.
async function projeyiYukle(onay) {
  if (!secilenYollar.gorsel_klasoru) {
    document.getElementById("yukleme-hata").textContent = "Önce bir görsel klasörü seçmelisin.";
    return;
  }

  const govde = {
    gorsel_klasoru: secilenYollar.gorsel_klasoru,
    etiket_klasoru: secilenYollar.etiket_klasoru,
    data_yaml: secilenYollar.data_yaml,
    siniflar: document.getElementById("siniflar").value.trim(),
    onay: onay,
  };

  const yanit = await fetch("/api/yukle", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(govde),
  });
  const veri = await yanit.json();

  if (!yanit.ok) {
    document.getElementById("yukleme-hata").textContent = veri.hata || "Bilinmeyen hata.";
    return;
  }

  // Backend "bunlar yeni sınıflar, eklemek ister misin?" diye soruyor —
  // var olan sınıflara ASLA dokunmadan, sadece kullanıcı onaylarsa
  // sona ekleniyor (bkz. app.py'deki güvenlik kuralı yorumu).
  if (veri.onay_gerekli) {
    const mesaj =
      `Şu yeni class(lar) mevcut listede yok: ${veri.yeni_siniflar.join(", ")}\n\n` +
      `Var olan class'lar (dokunulmayacak): ${veri.mevcut_siniflar.join(", ")}\n\n` +
      `Bunları EKLEMEK istiyor musun? (İptal = sadece var olan class'larla devam et)`;
    const kullanici_onayladi = confirm(mesaj);

    if (kullanici_onayladi) {
      await projeyiYukle(true); // aynı isteği onay=true ile tekrar gönder
    } else {
      // Kullanıcı istemedi -> yeni yazılanları unutup var olan sınıflarla devam et
      document.getElementById("siniflar").value = "";
      await projeyiYukle(false);
    }
    return;
  }

  siniflar = veri.siniflar;
  gorseller = veri.gorseller;
  kutular = [];
  mevcutIndex = 0;

  aktifSinif = sinifiOtomatikSecmeyeCalis(govde.gorsel_klasoru) ?? 0;

  document.getElementById("yukleme-ekrani").classList.add("gizli");
  document.getElementById("ana-ekran").classList.remove("gizli");

  // Yol bilgisini göster
  const yolBilgi = document.getElementById("yol-bilgisi");
  if (yolBilgi && (veri.etiket_klasoru || veri.data_yaml_yolu)) {
    yolBilgi.textContent =
      `Etiketler: ${veri.etiket_klasoru || "—"}  |  data.yaml: ${veri.data_yaml_yolu || "—"}`;
  }

  sinifListesiCiz();
  gorselListesiCiz();
  await gorselYukle(mevcutIndex);
}

// Klasör yolunun son parçasını (klasör adını) bir sınıf ismiyle
// eşleştirmeye çalışır (case-insensitive, iki yönlü "içeriyor mu" kontrolü
// — örn. klasör "fiat_egea" ise sınıf "fiat_egea" ile eşleşir, klasör
// "egea_fotograflari" olsa bile yine "egea" geçtiği için eşleşebilir).
// Eşleşme bulamazsa null döner.
function sinifiOtomatikSecmeyeCalis(gorselKlasoruYolu) {
  const parcalar = gorselKlasoruYolu.split(/[\\/]/).filter(Boolean);
  const klasorAdi = (parcalar[parcalar.length - 1] || "").toLowerCase();
  if (!klasorAdi) return null;

  for (let i = 0; i < siniflar.length; i++) {
    const sinifAdi = siniflar[i].toLowerCase();
    if (klasorAdi.includes(sinifAdi) || sinifAdi.includes(klasorAdi)) {
      return i;
    }
  }
  return null;
}

// --- Sınıf listesi (popup) + üst bardaki "aktif sınıf" göstergesi ---
function sinifListesiCiz() {
  const ul = document.getElementById("sinif-listesi");
  ul.innerHTML = "";
  siniflar.forEach((isim, i) => {
    const li = document.createElement("li");
    li.className = i === aktifSinif ? "aktif" : "";
    li.innerHTML = `<span class="renk-kutucuk" style="background:${RENKLER[i % RENKLER.length]}"></span>
                     ${i + 1}. ${_e(isim)}`;
    li.addEventListener("click", () => {
      aktifSinif = i;
      sinifListesiCiz();
      sinifPopupKapat();
    });
    ul.appendChild(li);
  });

  const bar = document.getElementById("aktif-sinif-bar");
  const aktifIsim = siniflar[aktifSinif] || "—";
  bar.textContent = `Aktif class: ${aktifIsim}  (C tuşu = class seç)`;
  bar.style.background = RENKLER[aktifSinif % RENKLER.length];
}

function sinifPopupAc() {
  sinifListesiCiz();
  document.getElementById("sinif-popup").classList.remove("gizli");
}
function sinifPopupKapat() {
  document.getElementById("sinif-popup").classList.add("gizli");
}
document.getElementById("sinif-popup").addEventListener("click", (e) => {
  if (e.target.id === "sinif-popup") sinifPopupKapat();
});
document.getElementById("aktif-sinif-bar").addEventListener("click", sinifPopupAc);

// --- Görsel listesi (sağ panel) + genel ilerleme sayacı ---
function gorselListesiCiz() {
  const ul = document.getElementById("gorsel-listesi");
  ul.innerHTML = "";
  gorseller.forEach((g, i) => {
    const li = document.createElement("li");
    li.className = i === mevcutIndex ? "mevcut" : "";
    li.innerHTML = `<span>${_e(g.ad)}</span>
      <span class="gorsel-sag">
        <span class="bayrak-nokta ${g.bayrakli ? "aktif" : ""}"></span>
        <span class="isaret ${g.etiketli ? "" : "bos"}">${g.etiketli ? "OK" : "-"}</span>
      </span>`;
    li.addEventListener("click", async () => { await gorselDegistir(i); });
    ul.appendChild(li);
  });

  const etiketliSayisi = gorseller.filter(g => g.etiketli).length;
  document.getElementById("ilerleme").textContent = `Etiketlenen: ${etiketliSayisi} / ${gorseller.length}`;
}

// --- Görsel yükleme + mevcut etiketleri çekme ---
//
// ÖNEMLİ (bir bug'ın düzeltmesi): bu fonksiyon eskiden `img.onload` içinde
// resmi/etiketi yüklüyordu ama dışarıdaki `async function` bunu HİÇ
// beklemiyordu -- `await gorselYukle(...)` çağrısı, resim/etiket gerçekten
// yüklenmeden, sadece `.src` atanır atanmaz hemen dönüyordu. Ok tuşuna hızlı
// basınca (özellikle basılı tutunca) bir önceki geçiş bitmeden bir sonraki
// başlıyordu; o anda `kaydet()` hâlâ ESKİ görselin `kutular` dizisini, artık
// mevcutIndex'in işaret ettiği YENİ (henüz yüklenmemiş) görselin dosyasına
// yazıyordu -- bu da o görselin etiketinin üzerine yazıp siliyordu. Şimdi
// tüm yükleme (resim + etiket fetch) tek bir Promise zincirinde, ve
// gorselDegistir()'deki kilit (aşağıda) aynı anda sadece TEK bir geçişe
// izin veriyor.
async function gorselYukle(index) {
  const ad = gorseller[index].ad;
  document.getElementById("sayac").textContent = `${index + 1} / ${gorseller.length}`;

  await new Promise((resolve, reject) => {
    const img = new Image();
    img.onload = () => { mevcutGorsel = img; resolve(); };
    img.onerror = () => reject(new Error(`Görsel yüklenemedi: ${ad}`));
    img.src = `/api/gorsel/${encodeURIComponent(ad)}?t=${Date.now()}`;
  });

  // Canvas'ın GÖRÜNTÜLENECEK (viewport) boyutu — sarmalayıcı kutunun
  // boyutu kadar, artık görselin kendi boyutuyla birebir aynı değil.
  const sarici = document.querySelector(".canvas-sarici");
  canvas.width = Math.max(sarici.clientWidth - 20, 400);
  canvas.height = Math.max(sarici.clientHeight - 20, 300);

  yakinlastirmayiSifirla(); // görseli pencereye sığdır (fit)

  const yanit = await fetch(`/api/etiket/${encodeURIComponent(ad)}`);
  const veri = await yanit.json();
  kutular = veri.kutular.map(k => ({
    sinif: k.sinif,
    x1: (k.x - k.w / 2) * mevcutGorsel.naturalWidth,
    y1: (k.y - k.h / 2) * mevcutGorsel.naturalHeight,
    x2: (k.x + k.w / 2) * mevcutGorsel.naturalWidth,
    y2: (k.y + k.h / 2) * mevcutGorsel.naturalHeight,
  }));
  seciliKutuIndex = null;
  ciz();
  kutuListesiCiz();
}

// Görseli canvas'a tam sığdıracak zoom/pan değerlerini hesaplar
// (klavyede 'R' tuşuna basınca da bu çağrılıyor — "zoom reset").
function yakinlastirmayiSifirla() {
  const genislikOrani = canvas.width / mevcutGorsel.naturalWidth;
  const yukseklikOrani = canvas.height / mevcutGorsel.naturalHeight;
  zoom = Math.min(genislikOrani, yukseklikOrani);
  pan.x = (canvas.width - mevcutGorsel.naturalWidth * zoom) / 2;
  pan.y = (canvas.height - mevcutGorsel.naturalHeight * zoom) / 2;
  ciz();
}

// Aynı anda sadece TEK bir geçişin sürmesini garanti eden kilit -- ok
// tuşunu basılı tutunca art arda gelen keydown olayları, bir önceki geçiş
// (kaydet + yükle) bitmeden yenisini başlatıp yarış durumuna (yukarıdaki
// yoruma bkz.) yol açmasın diye.
let gecisDevamEdiyor = false;

async function gorselDegistir(yeniIndex) {
  if (yeniIndex < 0 || yeniIndex >= gorseller.length) return;
  if (gecisDevamEdiyor) return; // önceki geçiş hâlâ sürüyor, bunu yok say
  gecisDevamEdiyor = true;
  try {
    await kaydet(); // görsel değişmeden önce otomatik kaydet
    mevcutIndex = yeniIndex;
    gorselListesiCiz();
    await gorselYukle(mevcutIndex);
  } finally {
    gecisDevamEdiyor = false;
  }
}

document.getElementById("onceki-btn").addEventListener("click", () => gorselDegistir(mevcutIndex - 1));
document.getElementById("sonraki-btn").addEventListener("click", () => gorselDegistir(mevcutIndex + 1));
document.getElementById("kaydet-btn").addEventListener("click", () => kaydet(true));

// "Klasör Değiştir": uygulamayı kapatıp açmadan başka bir görsel
// klasörüne geçmeyi sağlar (örn. sınıf başına ayrı klasörler arasında
// gidip gelirken kullanışlı).
document.getElementById("klasor-degistir-btn").addEventListener("click", async () => {
  await kaydet();

  // Backend state'i sıfırla (eski data.yaml kalmasın)
  await fetch("/api/sifirla", { method: "POST" });

  // Frontend state'i sıfırla
  siniflar = [];
  gorseller = [];
  kutular = [];
  secilenYollar.gorsel_klasoru = "";
  secilenYollar.etiket_klasoru = "";
  secilenYollar.data_yaml = "";
  document.getElementById("gorsel_klasoru_goster").textContent = "— seçilmedi —";
  document.getElementById("etiket_klasoru_goster").textContent = "— seçilmedi (otomatik: 'labels') —";
  document.getElementById("data_yaml_goster").textContent = "— seçilmedi (otomatik aranacak) —";
  document.getElementById("siniflar").value = "";
  document.getElementById("yukleme-hata").textContent = "";
  const yolBilgi = document.getElementById("yol-bilgisi");
  if (yolBilgi) yolBilgi.textContent = "";

  document.getElementById("ana-ekran").classList.add("gizli");
  document.getElementById("yukleme-ekrani").classList.remove("gizli");
});

// --- Çizim (canvas'a görsel + kutular + crosshair) ---
function ciz() {
  ctx.setTransform(1, 0, 0, 1, 0, 0);
  ctx.clearRect(0, 0, canvas.width, canvas.height);

  // --- Görsel uzayı: zoom + pan uygulanmış olarak görsel ve kutular ---
  ctx.save();
  ctx.translate(pan.x, pan.y);
  ctx.scale(zoom, zoom);

  ctx.drawImage(mevcutGorsel, 0, 0, mevcutGorsel.naturalWidth, mevcutGorsel.naturalHeight);

  const tumKutular = onizlemeGorsel ? [...kutular, { ...onizlemeGorsel, onizleme: true }] : kutular;
  tumKutular.forEach((k, i) => {
    const renk = RENKLER[k.sinif % RENKLER.length];
    ctx.strokeStyle = renk;
    ctx.lineWidth = (k.onizleme ? 2 : (i === seciliKutuIndex ? 4 : 2)) / zoom;
    if (k.onizleme) ctx.setLineDash([6 / zoom, 4 / zoom]); else ctx.setLineDash([]);
    ctx.strokeRect(k.x1, k.y1, k.x2 - k.x1, k.y2 - k.y1);
    ctx.setLineDash([]);

    if (!k.onizleme) {
      const etiket = siniflar[k.sinif] || `sinif_${k.sinif}`;
      ctx.font = `${16 / zoom}px sans-serif`;
      const metinGenislik = ctx.measureText(etiket).width;
      ctx.fillStyle = renk;
      ctx.fillRect(k.x1, k.y1 - 20 / zoom, metinGenislik + 8 / zoom, 20 / zoom);
      ctx.fillStyle = "#000";
      ctx.fillText(etiket, k.x1 + 4 / zoom, k.y1 - 5 / zoom);
    }
  });
  ctx.restore();

  // --- Ekran uzayı: crosshair (fareyi izleyen kesişen çizgiler) ---
  // Açık renkli (toprak/beyaz gibi) arka planlarda düz beyaz çizgi
  // kaybolabiliyor. Bunu önlemek için önce kalın siyah bir "hale", sonra
  // üstüne ince parlak sarı bir çizgi çiziyoruz — hem açık hem koyu
  // arka planda görünür kalıyor.
  if (fareCanvasNoktasi) {
    const cizgiCiz = (renk, kalinlik) => {
      ctx.strokeStyle = renk;
      ctx.lineWidth = kalinlik;
      ctx.beginPath();
      ctx.moveTo(0, fareCanvasNoktasi.y);
      ctx.lineTo(canvas.width, fareCanvasNoktasi.y);
      ctx.moveTo(fareCanvasNoktasi.x, 0);
      ctx.lineTo(fareCanvasNoktasi.x, canvas.height);
      ctx.stroke();
    };
    cizgiCiz("rgba(0,0,0,0.7)", 3);      // siyah hale (alt katman, kalın)
    cizgiCiz("rgba(255,230,0,0.95)", 1); // parlak sarı çizgi (üst katman, ince)
  }
}

// Yanlış etiketlenmiş bir kutunun class'ını, silip yeniden çizmeden
// düzeltebilmek için: her satırda bir class dropdown'ı var, değiştirince
// kutunun sinif'i anında güncellenir (koordinatlara dokunmaz).
function kutuListesiCiz() {
  const ul = document.getElementById("kutular-ul");
  ul.innerHTML = "";
  kutular.forEach((k, i) => {
    const li = document.createElement("li");
    li.className = "kutu-satiri";

    const secim = document.createElement("select");
    secim.className = "kutu-sinif-secim";
    siniflar.forEach((isim, sIdx) => {
      const opt = document.createElement("option");
      opt.value = sIdx;
      opt.textContent = isim;
      if (sIdx === k.sinif) opt.selected = true;
      secim.appendChild(opt);
    });
    secim.addEventListener("change", () => {
      kutular[i].sinif = parseInt(secim.value, 10);
      ciz();
    });

    const silBtn = document.createElement("button");
    silBtn.textContent = "sil";
    silBtn.addEventListener("click", () => {
      kutular.splice(i, 1);
      seciliKutuIndex = null;
      ciz();
      kutuListesiCiz();
    });

    li.appendChild(secim);
    li.appendChild(silBtn);
    ul.appendChild(li);
  });
}

// --- Koordinat dönüşümleri ---
// Fare olayından, canvas'ın kendi (ekran) piksel uzayındaki konumu.
function fareCanvasKonumu(e) {
  const dikdortgen = canvas.getBoundingClientRect();
  const olcekX = canvas.width / dikdortgen.width;
  const olcekY = canvas.height / dikdortgen.height;
  return {
    x: (e.clientX - dikdortgen.left) * olcekX,
    y: (e.clientY - dikdortgen.top) * olcekY,
  };
}

// Canvas (ekran) uzayındaki bir noktayı, zoom/pan'i tersine çevirerek
// GÖRSEL (natural piksel) uzayına çevirir.
function canvasNoktasindanGorsele(canvasNoktasi) {
  return {
    x: (canvasNoktasi.x - pan.x) / zoom,
    y: (canvasNoktasi.y - pan.y) / zoom,
  };
}

// Bir noktanın (görsel uzayında) bir kutunun içinde olup olmadığını kontrol eder.
function noktaKutuIcindeMi(nokta, kutu) {
  return nokta.x >= kutu.x1 && nokta.x <= kutu.x2 &&
         nokta.y >= kutu.y1 && nokta.y <= kutu.y2;
}

// Bir noktanın altındaki EN ÜSTTEKİ (son çizilen) kutunun index'ini bulur.
function noktadakiKutuyuBul(nokta) {
  for (let i = kutular.length - 1; i >= 0; i--) {
    if (noktaKutuIcindeMi(nokta, kutular[i])) return i;
  }
  return null;
}

// --- Orta tuşla gezinme (pan) durumu ---
let panBasladi = false;
let panBaslangicCanvas = { x: 0, y: 0 };
let panBaslangicPan = { x: 0, y: 0 };

// --- Fare ile kutu çizme / seçme / gezinme ---
canvas.addEventListener("mousedown", (e) => {
  // Orta tuş (tekerlek basılı) = gezinme (pan), kutu çizmeyle karışmasın
  if (e.button === 1) {
    e.preventDefault();
    panBasladi = true;
    panBaslangicCanvas = fareCanvasKonumu(e);
    panBaslangicPan = { x: pan.x, y: pan.y };
    canvas.style.cursor = "grabbing";
    return;
  }
  if (e.button !== 0) return; // sadece sol tık kutu çizsin/seçsin

  const gorselNoktasi = canvasNoktasindanGorsele(fareCanvasKonumu(e));
  const tiklananKutu = noktadakiKutuyuBul(gorselNoktasi);

  if (tiklananKutu !== null) {
    // Var olan bir kutunun üstüne tıklandı -> yeni kutu çizmek yerine SEÇ
    seciliKutuIndex = tiklananKutu;
    ciz();
    kutuListesiCiz();
    return;
  }

  seciliKutuIndex = null;
  cizimBasladi = true;
  cizimBaslangicGorsel = gorselNoktasi;
});

canvas.addEventListener("mousemove", (e) => {
  fareCanvasNoktasi = fareCanvasKonumu(e);

  if (panBasladi) {
    pan.x = panBaslangicPan.x + (fareCanvasNoktasi.x - panBaslangicCanvas.x);
    pan.y = panBaslangicPan.y + (fareCanvasNoktasi.y - panBaslangicCanvas.y);
    ciz();
    return;
  }

  if (cizimBasladi) {
    const simdiGorsel = canvasNoktasindanGorsele(fareCanvasNoktasi);
    onizlemeGorsel = {
      sinif: aktifSinif,
      x1: Math.min(cizimBaslangicGorsel.x, simdiGorsel.x),
      y1: Math.min(cizimBaslangicGorsel.y, simdiGorsel.y),
      x2: Math.max(cizimBaslangicGorsel.x, simdiGorsel.x),
      y2: Math.max(cizimBaslangicGorsel.y, simdiGorsel.y),
    };
  }
  ciz();
});

canvas.addEventListener("mouseleave", () => {
  fareCanvasNoktasi = null;
  if (panBasladi) { panBasladi = false; canvas.style.cursor = "crosshair"; }
  ciz();
});

canvas.addEventListener("mouseup", (e) => {
  if (e.button === 1 && panBasladi) {
    panBasladi = false;
    canvas.style.cursor = "crosshair";
    return;
  }
  if (!cizimBasladi) return;
  cizimBasladi = false;

  const bitisGorsel = canvasNoktasindanGorsele(fareCanvasKonumu(e));
  const w = mevcutGorsel.naturalWidth, h = mevcutGorsel.naturalHeight;
  const x1 = Math.max(0, Math.min(cizimBaslangicGorsel.x, bitisGorsel.x));
  const y1 = Math.max(0, Math.min(cizimBaslangicGorsel.y, bitisGorsel.y));
  const x2 = Math.min(w, Math.max(cizimBaslangicGorsel.x, bitisGorsel.x));
  const y2 = Math.min(h, Math.max(cizimBaslangicGorsel.y, bitisGorsel.y));

  onizlemeGorsel = null;

  // Çok küçük (yanlışlıkla tıklama) kutucukları ekleme (görsel pikselinde 5px)
  if (x2 - x1 < 5 || y2 - y1 < 5) { ciz(); return; }

  kutular.push({ sinif: aktifSinif, x1, y1, x2, y2 });
  ciz();
  kutuListesiCiz();
});

// Sağ tık = kutunun üstündeyse DİREKT SİL (seçmeye gerek kalmadan, hızlı silme)
canvas.addEventListener("contextmenu", (e) => {
  e.preventDefault();
  const gorselNoktasi = canvasNoktasindanGorsele(fareCanvasKonumu(e));
  const tiklananKutu = noktadakiKutuyuBul(gorselNoktasi);
  if (tiklananKutu !== null) {
    kutular.splice(tiklananKutu, 1);
    seciliKutuIndex = null;
    ciz();
    kutuListesiCiz();
  }
});

// Fare tekerleğinin varsayılan orta-tık otomatik kaydırma davranışını
// engelle (aksi halde tarayıcı kendi "autoscroll" ikonunu göstermeye çalışır).
canvas.addEventListener("auxclick", (e) => { if (e.button === 1) e.preventDefault(); });

// --- Ctrl + tekerlek ile yakınlaştırma (fare imlecine göre zoom) ---
canvas.addEventListener("wheel", (e) => {
  if (!e.ctrlKey) return; // Ctrl basılı değilse normal sayfa davranışına dokunma
  e.preventDefault();

  const canvasNoktasi = fareCanvasKonumu(e);
  const gorselNoktasiOnce = canvasNoktasindanGorsele(canvasNoktasi);

  const carpan = e.deltaY < 0 ? 1.15 : 1 / 1.15;
  zoom = Math.min(Math.max(zoom * carpan, 0.1), 10);

  // Zoom sonrası, fare imlecinin altındaki görsel noktası hep aynı
  // ekran konumunda kalsın diye pan'i buna göre yeniden hesaplıyoruz
  // ("fare imlecine göre yakınlaştırma").
  pan.x = canvasNoktasi.x - gorselNoktasiOnce.x * zoom;
  pan.y = canvasNoktasi.y - gorselNoktasiOnce.y * zoom;

  ciz();
}, { passive: false });

// --- Klavye kısayolları ---
document.addEventListener("keydown", (e) => {
  if (document.getElementById("ana-ekran").classList.contains("gizli")) return;

  // ÖNEMLİ: e.code === "Numpad1" kontrolünü rakam (1-9) kontrolünden ÖNCE
  // yapıyoruz -- NumLock açıkken fiziksel Numpad1 tuşu da e.key="1" üretir,
  // aksi halde bu her zaman "class 1'i seç" dalına düşer, bayrak kısayoluna
  // hiç ulaşmazdı. e.code fiziksel tuş konumunu verir, NumLock'tan etkilenmez.
  //
  // Numpad'i olmayan (laptop) klavyeler için "." (nokta) de aynı işi
  // yapıyor -- tek elle, sağ elin bulunduğu bölgede rahat basılan bir tuş,
  // başka hiçbir kısayolla çakışmıyor.
  if (e.code === "Numpad1" || (e.key === "." && !e.repeat)) {
    e.preventDefault();
    bayrakDegistir();
    return;
  }

  if (e.key >= "1" && e.key <= "9") {
    const idx = parseInt(e.key, 10) - 1;
    if (idx < siniflar.length) {
      if (seciliKutuIndex !== null) {
        // Bir kutu seçiliyken rakam tuşuna basmak, yanlış etiketlenmiş
        // O KUTUYU düzeltir (silip yeniden çizmeye gerek kalmaz) --
        // seçili kutu yoksa eskisi gibi sadece aktif class'ı değiştirir.
        kutular[seciliKutuIndex].sinif = idx;
        ciz();
        kutuListesiCiz();
      } else {
        aktifSinif = idx;
        sinifListesiCiz();
      }
    }
  } else if (e.key === "ArrowRight") {
    gorselDegistir(mevcutIndex + 1);
  } else if (e.key === "ArrowLeft") {
    gorselDegistir(mevcutIndex - 1);
  } else if (((e.key === "Delete" || e.key === "Backspace") && e.shiftKey) || e.key === "l" || e.key === "L") {
    // Shift+Delete/Backspace VEYA tek başına "L" tuşu: gezinirken tek
    // tuşla görseli KALICI sil -- fare gerekmez, açılan confirm()
    // penceresini de Enter/Esc ile klavyeden onaylayabilirsin (ara
    // sahne/alakasız görselleri hızlıca eleme ihtiyacı için).
    e.preventDefault();
    gorselSil();
  } else if (e.key === "Delete" || e.key === "Backspace") {
    if (seciliKutuIndex !== null) {
      kutular.splice(seciliKutuIndex, 1);
      seciliKutuIndex = null;
      ciz();
      kutuListesiCiz();
    }
  } else if (e.key === "r" || e.key === "R") {
    yakinlastirmayiSifirla();
  } else if (e.key === "c" || e.key === "C") {
    const popup = document.getElementById("sinif-popup");
    if (popup.classList.contains("gizli")) {
      sinifPopupAc();
    } else {
      sinifPopupKapat();
    }
  } else if (e.key === "Escape") {
    sinifPopupKapat();
  }
});

// --- Kaydetme ---
async function kaydet(elleTetiklendi) {
  if (gorseller.length === 0) return;
  const ad = gorseller[mevcutIndex].ad;
  const genislik = mevcutGorsel.naturalWidth;
  const yukseklik = mevcutGorsel.naturalHeight;

  const govde = {
    kutular: kutular.map(k => ({
      sinif: k.sinif,
      x: ((k.x1 + k.x2) / 2) / genislik,
      y: ((k.y1 + k.y2) / 2) / yukseklik,
      w: (k.x2 - k.x1) / genislik,
      h: (k.y2 - k.y1) / yukseklik,
    })),
  };

  const yanit = await fetch(`/api/etiket/${encodeURIComponent(ad)}`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(govde),
  });
  const veri = await yanit.json();

  gorseller[mevcutIndex].etiketli = veri.kutu_sayisi > 0;
  gorselListesiCiz();

  const durumEl = document.getElementById("kayit-durumu");
  durumEl.textContent = `Kaydedildi (${veri.kutu_sayisi} kutu)`;
  setTimeout(() => { durumEl.textContent = ""; }, elleTetiklendi ? 2000 : 900);
}

// --- Bayrak ("sonra tekrar kontrol et" işareti) ---
// YOLO etiket dosyasına hiç dokunmaz, ayrı bir _bayraklar.json'da tutulur
// (bkz. app.py). Numpad 1 ile açılıp kapatılır, listede kırmızı nokta olarak
// görünür (OK/- yazısının solunda).
async function bayrakDegistir() {
  if (gorseller.length === 0) return;
  const ad = gorseller[mevcutIndex].ad;
  const yeniDurum = !gorseller[mevcutIndex].bayrakli;

  await fetch(`/api/bayrak/${encodeURIComponent(ad)}`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ bayrakli: yeniDurum }),
  });

  gorseller[mevcutIndex].bayrakli = yeniDurum;
  gorselListesiCiz();

  const durumEl = document.getElementById("kayit-durumu");
  durumEl.textContent = yeniDurum ? "İşaretlendi (sonra kontrol et)" : "İşaret kaldırıldı";
  setTimeout(() => { durumEl.textContent = ""; }, 1200);
}

// --- Görseli kalıcı olarak silme (uygun olmayan fotoğrafları elemek için) ---
// Hem "Görseli Sil" butonuyla hem Ctrl+Delete/Ctrl+Backspace kısayoluyla
// çağrılabilsin diye ayrı bir fonksiyon. confirm() penceresi native bir
// dialog olduğu için mouse gerekmez -- Enter = onayla, Esc = vazgeç.
async function gorselSil() {
  if (gorseller.length === 0) return;
  const ad = gorseller[mevcutIndex].ad;

  const onay = confirm(
    `"${ad}" görselini (ve varsa etiketini) KALICI OLARAK silmek istediğine emin misin?\n\n` +
    `Enter = SİL, Esc = vazgeç. Bu işlem GERİ ALINAMAZ.`
  );
  if (!onay) return;

  const yanit = await fetch(`/api/gorsel/${encodeURIComponent(ad)}`, { method: "DELETE" });
  const veri = await yanit.json();

  if (veri.hata) {
    alert(veri.hata);
    return;
  }

  gorseller = veri.gorseller;

  if (gorseller.length === 0) {
    alert("Bu klasörde başka görsel kalmadı.");
    document.getElementById("ana-ekran").classList.add("gizli");
    document.getElementById("yukleme-ekrani").classList.remove("gizli");
    return;
  }

  if (mevcutIndex >= gorseller.length) mevcutIndex = gorseller.length - 1;
  gorselListesiCiz();
  await gorselYukle(mevcutIndex);
}

document.getElementById("gorsel-sil-btn").addEventListener("click", gorselSil);
