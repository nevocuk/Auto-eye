"""
Adım 7: SQLite şeması — Fusion sonuçlarının kalıcı/BİRİKİMLİ kaydı

Şu ana kadar Fusion'ın sonucu SADECE kayitlar/fusion_sonucu.json'a
yazılıyordu -- her çalıştırmada ÜZERİNE yazılıyordu, bir önceki sonuç
kayboluyordu. Bu dosya, aynı sonuçları BİRİKİMLİ olarak (her tespit ayrı
bir satır, geçmiş kaybolmadan) db/otogoz.db içindeki tek bir "tespitler"
tablosuna da yazan bir katman ekliyor.

Tasarım kararları (nevfel ile konuşuldu, 2026-07-31):
- TEK TABLO yeterli (ayrı "araçlar" + "geçişler" tablosuna normalize
  etmiyoruz) -- aynı plaka/marka birden fazla kez görülse bile her
  görülme ayrı bir satır, "bu plaka kaç kez geldi" gibi sorular
  `WHERE plaka = ...` ile zaten cevaplanabiliyor.
- Zaman damgası: fotoğrafın ÇEKİLDİĞİ an değil, Fusion'ın İŞLEDİĞİ an
  kaydediliyor (tespit_zamani = kayıt satırının oluşturulduğu an).
  Sebep: projenin asıl senaryosu (sabit güvenlik kamerası, sürekli
  döngü) bu ikisini pratikte aynı ana getiriyor -- kare yakalanır
  yakalanmaz hemen işlenir. EXIF'ten çekim zamanı okumak ekstra
  karmaşıklık katardı ve her fotoğrafta garanti değil (WhatsApp/ekran
  görüntüsü gibi kaynaklar EXIF'i siler). İhtiyaç çıkarsa ayrı bir
  "cekilis_zamani" sütunu SONRADAN eklenebilir (ALTER TABLE ile, var
  olan satırlar bozulmadan).
- Görsel saklama: dosya YOLU tutuluyor (BLOB DEĞİL). Sebep: binlerce
  görseli veritabanına ham bayt olarak gömmek dosyayı hızla
  GB'larca büyütür, OneDrive senkronizasyonunu/yedeklemeyi yavaşlatır,
  DB Browser gibi araçlarla incelemeyi zorlaştırır. Dosya yolu
  yaklaşımı zaten static/fusion_ciktilari/ altında biriken görsellerle
  bire bir uyumlu -- veritabanı sadece "nerede" bilgisini taşıyor.
- Yön takibi (#12) BİLEREK şemaya eklenmedi -- sonraya bırakıldı, o
  gelince ALTER TABLE ile yeni bir sütun (örn. "yon") eklenecek.

Kullanım (başka bir Python dosyasından):
  import importlib.util
  # (numaralı dosya adları doğrudan import edilemediği için bkz. app.py'deki kullanım)

Doğrudan çalıştırılırsa: tabloyu oluşturur (yoksa) ve
kayitlar/fusion_sonucu.json'daki EN SON sonucu veritabanına ekler
(elle/manuel tek seferlik kayıt için -- normal kullanımda bu kayıt
zaten Fusion çalıştığında OTOMATİK yapılıyor, bkz. app.py).

Sorgu örnekleri (kurulumdan sonra, bir Python konsolunda ya da
DB Browser for SQLite gibi bir araçla):
  SELECT * FROM tespitler WHERE plaka = '01AZE921';
  SELECT * FROM tespitler WHERE marka_model = 'fiat_egea' ORDER BY tespit_zamani DESC;
  SELECT COUNT(*) FROM tespitler WHERE marka_model = 'tanimlanmadi';
"""

import json
import sqlite3
from datetime import datetime
from pathlib import Path

PROJE_KOK = Path(__file__).resolve().parent.parent
DB_YOLU = PROJE_KOK / "db" / "otogoz.db"
FUSION_JSON_YOLU = PROJE_KOK / "kayitlar" / "fusion_sonucu.json"


def _baglanti():
    DB_YOLU.parent.mkdir(parents=True, exist_ok=True)
    return sqlite3.connect(DB_YOLU)


def tabloyu_olustur():
    """Tablo zaten varsa hiçbir şey yapmaz (IF NOT EXISTS) -- güvenle
    her çalıştırmada/başlangıçta çağrılabilir."""
    with _baglanti() as con:
        con.execute("""
            CREATE TABLE IF NOT EXISTS tespitler (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                tespit_zamani TEXT NOT NULL,
                gorsel_yolu TEXT,
                sonuc_gorsel_yolu TEXT,
                marka_model TEXT,
                marka_model_guven REAL,
                marka_model_durum TEXT,
                plaka TEXT,
                plaka_guven REAL,
                plaka_durum TEXT
            )
        """)
        con.execute("CREATE INDEX IF NOT EXISTS idx_tespitler_plaka ON tespitler(plaka)")
        con.execute("CREATE INDEX IF NOT EXISTS idx_tespitler_marka_model ON tespitler(marka_model)")
        con.execute("CREATE INDEX IF NOT EXISTS idx_tespitler_zaman ON tespitler(tespit_zamani)")


def fusion_sonucunu_kaydet(gorsel_yolu: str, sonuc_gorsel_yolu: str, araclar: list) -> int:
    """araclar: fusion'ın ürettiği
    [{"marka_model":..., "marka_model_guven":..., "marka_model_durum":...,
      "plaka":..., "plaka_guven":..., "plaka_durum":...}, ...] listesi.
    Her araç için BİR satır ekler (üzerine yazmaz, biriktirir).
    Döndürür: eklenen satır sayısı."""
    tabloyu_olustur()
    zaman = datetime.now().isoformat(timespec="seconds")
    with _baglanti() as con:
        for arac in araclar:
            con.execute(
                """INSERT INTO tespitler
                   (tespit_zamani, gorsel_yolu, sonuc_gorsel_yolu,
                    marka_model, marka_model_guven, marka_model_durum,
                    plaka, plaka_guven, plaka_durum)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    zaman, gorsel_yolu, sonuc_gorsel_yolu,
                    arac.get("marka_model"), arac.get("marka_model_guven"), arac.get("marka_model_durum"),
                    arac.get("plaka"), arac.get("plaka_guven"), arac.get("plaka_durum"),
                ),
            )
    return len(araclar)


def main():
    tabloyu_olustur()
    print(f"[bilgi] Tablo hazır: {DB_YOLU}")
    if not FUSION_JSON_YOLU.exists():
        print(f"[bilgi] {FUSION_JSON_YOLU} bulunamadı -- önce Fusion'ı bir kez çalıştır.")
        return
    with open(FUSION_JSON_YOLU, "r", encoding="utf-8") as f:
        veri = json.load(f)
    eklenen = fusion_sonucunu_kaydet(veri.get("gorsel", ""), "", veri.get("araclar", []))
    print(f"[bilgi] {eklenen} kayıt eklendi -> {DB_YOLU}")


if __name__ == "__main__":
    main()
