// Gereklilikler — Frontend mantığı
// (evrensel_toolset/'teki aynı sayfanın bu projeye uyarlanmış hali --
// burada Fusion her zaman açık olduğu için "opsiyonel" grup genelde
// boş gelir, bu script hem boş hem dolu haliyle çalışacak şekilde yazıldı.)

let kurulumPollingId = null;

function paketSatiriYaz(gorunumKurulu) {
  return gorunumKurulu
    ? `<span class="gereklilik-ok">✓ Kurulu</span>`
    : `<span class="gereklilik-eksik">✗ Eksik</span>`;
}

async function durumKontrolEt() {
  const gpuEl = document.getElementById("gpu-bilgisi");
  const paketGovde = document.getElementById("paket-govde");
  const opsiyonelAlani = document.getElementById("opsiyonel-alani");
  const opsiyonelGovde = document.getElementById("opsiyonel-govde");
  const yoloEl = document.getElementById("yolo-durumu");

  paketGovde.innerHTML = `<tr><td colspan="3">Kontrol ediliyor...</td></tr>`;

  let veri;
  try {
    const cevap = await fetch("/api/gereklilik/durum");
    veri = await cevap.json();
  } catch (e) {
    paketGovde.innerHTML = `<tr><td colspan="3">İstek başarısız: ${e}</td></tr>`;
    return;
  }

  gpuEl.classList.remove("gizli");
  gpuEl.innerHTML = veri.gpu_bulundu
    ? `<strong>GPU bulundu</strong> (nvidia-smi çalıştı) — torch varsayılan olarak CUDA'lı kurulacak.`
    : `<strong>GPU bulunamadı</strong> — torch CPU'lu kurulacak (GPU'n varsa sürücülerin kurulu olduğundan emin ol).`;
  document.getElementById("gpu_kullan").checked = !!veri.gpu_bulundu;

  paketGovde.innerHTML = veri.zorunlu.map((p) => `
    <tr>
      <td>${p.paket}</td>
      <td>${paketSatiriYaz(p.kurulu)}</td>
      <td>${p.aciklama}</td>
    </tr>
  `).join("");

  if (veri.opsiyonel && veri.opsiyonel.length) {
    opsiyonelAlani.classList.remove("gizli");
    opsiyonelGovde.innerHTML = veri.opsiyonel.map((p) => `
      <tr>
        <td>${p.paket}</td>
        <td>${paketSatiriYaz(p.kurulu)}</td>
        <td>${p.aciklama}</td>
      </tr>
    `).join("");
  } else {
    opsiyonelAlani.classList.add("gizli");
  }

  yoloEl.classList.remove("gizli");
  yoloEl.innerHTML = veri.yolo11n_var
    ? `<strong>yolo11n.pt</strong> — ✓ mevcut (hazır COCO modeli indirilmiş).`
    : `<strong>yolo11n.pt</strong> — ✗ henüz indirilmemiş (kurulum sırasında otomatik indirilecek).`;
}

document.getElementById("kontrol-btn").addEventListener("click", durumKontrolEt);

document.getElementById("kur-btn").addEventListener("click", async () => {
  const hataEl = document.getElementById("gereklilik-hata");
  const durumEl = document.getElementById("kurulum-durum-satiri");
  const logEl = document.getElementById("kurulum-log");
  hataEl.textContent = "";

  const opsiyonelKutu = document.getElementById("opsiyonel_de_kur");
  const govde = {
    opsiyonel_de: opsiyonelKutu ? opsiyonelKutu.checked : true,
    gpu_kullan: document.getElementById("gpu_kullan").checked,
  };

  const cevap = await fetch("/api/gereklilik/kur_baslat", {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(govde),
  });
  const veri = await cevap.json();

  if (veri.hata) {
    hataEl.textContent = veri.hata;
    return;
  }

  document.getElementById("kur-btn").disabled = true;
  durumEl.classList.remove("gizli");
  logEl.classList.remove("gizli");
  logEl.textContent = "";

  if (kurulumPollingId) clearInterval(kurulumPollingId);
  kurulumPollingId = setInterval(kurulumDurumGuncelle, 1200);
  kurulumDurumGuncelle();
});

async function kurulumDurumGuncelle() {
  const cevap = await fetch("/api/gereklilik/kur_durum");
  const d = await cevap.json();

  const durumEl = document.getElementById("kurulum-durum-satiri");
  const logEl = document.getElementById("kurulum-log");

  durumEl.innerHTML = d.calisiyor
    ? `<strong>Kuruluyor...</strong> (bu, özellikle torch için birkaç dakika sürebilir, internet bağlantına bağlı)`
    : (d.hata ? `<strong>Hata:</strong> ${d.hata}` : `<strong>Tamamlandı.</strong> "DURUMU KONTROL ET" ile doğrula.`);

  logEl.textContent = (d.loglar || []).join("\n");
  logEl.scrollTop = logEl.scrollHeight;

  if (!d.calisiyor && d.tamamlandi) {
    clearInterval(kurulumPollingId);
    kurulumPollingId = null;
    document.getElementById("kur-btn").disabled = false;
    durumKontrolEt();
  }
}

// Sayfa açılır açılmaz durumu göster
durumKontrolEt();
