// Veritabanı Sorgu sayfası -- marka/model ve plaka AYRI kutulardan,
// birbirinden bağımsız (istersen ikisi birden) aranır + opsiyonel yıl
// (tespit_zamani'nin yılı) filtresi. Sunucudan /api/veritabani/ara ile
// JSON alır, tabloya basar. Birkaç harf yazar yazmaz (debounce ile)
// otomatik arar -- ARA butonuna basmaya ya da Enter'a gerek yok.

const markaModelKutusu = document.getElementById("db_marka_model_kutusu");
const plakaKutusu = document.getElementById("db_plaka_kutusu");
const renkKutusu = document.getElementById("db_renk_kutusu");
const yilKutusu = document.getElementById("db_yil_kutusu");
const araBtn = document.getElementById("db_ara_btn");
const ozetDiv = document.getElementById("db_ozet");
const sonuclarDiv = document.getElementById("db_sonuclar");

function durumEtiketiSinifi(durum) {
  if (!durum) return "";
  const d = durum.toLowerCase();
  if (d.includes("bulundu") || d.includes("okundu") || d === "ok") return "db-durum-iyi";
  if (d.includes("tanimlanmadi") || d.includes("bulunamadi") || d.includes("okunamadi")) return "db-durum-kotu";
  return "";
}

async function ara() {
  sonuclarDiv.innerHTML = '<p class="db-yukleniyor">Aranıyor...</p>';
  ozetDiv.textContent = "";

  const params = new URLSearchParams();
  if (markaModelKutusu.value.trim()) params.set("marka_model", markaModelKutusu.value.trim());
  if (plakaKutusu.value.trim()) params.set("plaka", plakaKutusu.value.trim());
  if (renkKutusu.value.trim()) params.set("renk", renkKutusu.value.trim());
  if (yilKutusu.value.trim()) params.set("yil", yilKutusu.value.trim());

  let veri;
  try {
    const yanit = await fetch(`/api/veritabani/ara?${params.toString()}`);
    veri = await yanit.json();
  } catch (e) {
    sonuclarDiv.innerHTML = `<p class="db-hata">İstek başarısız: ${e}</p>`;
    return;
  }

  if (veri.hata) {
    sonuclarDiv.innerHTML = `<p class="db-hata">${veri.hata}</p>`;
    return;
  }

  ozetDiv.textContent = `${veri.gosterilen} kayıt gösteriliyor (veritabanında toplam ${veri.toplam_kayit_veritabaninda} kayıt var).`;

  if (!veri.kayitlar.length) {
    sonuclarDiv.innerHTML = '<p class="db-bos">Eşleşen kayıt yok.</p>';
    return;
  }

  const satirlar = veri.kayitlar.map((k) => `
    <tr>
      <td>${k.id}</td>
      <td>${k.tespit_zamani || ""}</td>
      <td>${k.gorsel_url ? `<img class="db-thumb" src="${k.gorsel_url}" loading="lazy">` : "—"}</td>
      <td>${k.marka_model || "—"}</td>
      <td>${k.marka_model_guven != null ? k.marka_model_guven.toFixed(2) : "—"}</td>
      <td class="${durumEtiketiSinifi(k.marka_model_durum)}">${k.marka_model_durum || "—"}</td>
      <td>${k.renk || "—"}</td>
      <td>${k.plaka || "—"}</td>
      <td>${k.plaka_guven != null ? k.plaka_guven.toFixed(2) : "—"}</td>
      <td class="${durumEtiketiSinifi(k.plaka_durum)}">${k.plaka_durum || "—"}</td>
    </tr>
  `).join("");

  sonuclarDiv.innerHTML = `
    <table class="db-tablo">
      <thead>
        <tr>
          <th>ID</th><th>Tespit Zamanı</th><th>Görsel</th>
          <th>Marka/Model</th><th>Güven</th><th>Durum</th>
          <th>Renk</th>
          <th>Plaka</th><th>Güven</th><th>Durum</th>
        </tr>
      </thead>
      <tbody>${satirlar}</tbody>
    </table>
  `;
}

// Birkaç harf yazınca (300ms bekleyip) otomatik ara -- her tuşta sunucuya
// istek atmamak için debounce uyguluyoruz.
let debounceId = null;
function gecikmeliAra() {
  if (debounceId) clearTimeout(debounceId);
  debounceId = setTimeout(ara, 300);
}

araBtn.addEventListener("click", ara);
markaModelKutusu.addEventListener("input", gecikmeliAra);
plakaKutusu.addEventListener("input", gecikmeliAra);
renkKutusu.addEventListener("input", gecikmeliAra);
yilKutusu.addEventListener("input", gecikmeliAra);
markaModelKutusu.addEventListener("keyup", (e) => { if (e.key === "Enter") ara(); });
plakaKutusu.addEventListener("keyup", (e) => { if (e.key === "Enter") ara(); });
renkKutusu.addEventListener("keyup", (e) => { if (e.key === "Enter") ara(); });
yilKutusu.addEventListener("keyup", (e) => { if (e.key === "Enter") ara(); });

// sayfa açılır açılmaz son kayıtları (filtresiz) göster
ara();
