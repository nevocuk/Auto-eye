import scipy.io
import pandas as pd

# 1. Dosya Yolları
yol_isimler = r"C:\Users\nvflb\OneDrive\Desktop\brave indirilen\compcars\CompCars\data\data\misc\make_model_name.mat"
yol_tipler = r"C:\Users\nvflb\OneDrive\Desktop\brave indirilen\compcars\CompCars\data\data\misc\car_type.mat" 
yol_ozellikler = r"C:\Users\nvflb\OneDrive\Desktop\brave indirilen\compcars\CompCars\data\data\misc\attributes.txt"

# 2. .mat Dosyalarını Yükle
mat_isimler = scipy.io.loadmat(yol_isimler)
mat_tipler = scipy.io.loadmat(yol_tipler)

# Güvenli Okuma: Boş verilerde çökmeyi engellemek için Try-Except bloğu
model_isimleri = []
for item in mat_isimler['model_names']:
    try:
        model_isimleri.append(item[0][0])
    except IndexError:
        # Eğer hücre boşsa çökme, bu metni ekle
        model_isimleri.append("Bilinmeyen Model")

arac_tipleri = []
for item in mat_tipler['types'][0]:
    try:
        arac_tipleri.append(item[0])
    except IndexError:
        arac_tipleri.append("Bilinmeyen Tip")

# 3. attributes.txt Dosyasını Oku
df = pd.read_csv(yol_ozellikler, sep=r'\s+')

# 4. Güvenli Eşleştirme Fonksiyonları
def model_getir(x):
    # Eğer ID 0'dan büyükse ve listemizin sınırları içindeyse ismini al
    if 0 < x <= len(model_isimleri):
        return model_isimleri[x-1]
    return "Bilinmeyen Model"

def tip_getir(x):
    if 0 < x <= len(arac_tipleri):
        return arac_tipleri[x-1]
    return "Bilinmeyen Tip"

# Sütunları Uygula
df['Gercek_Model_Ismi'] = df['model_id'].apply(model_getir)
df['Gercek_Kasa_Tipi'] = df['type'].apply(tip_getir)

# Tablo Düzeni
df = df[['model_id', 'Gercek_Model_Ismi', 'type', 'Gercek_Kasa_Tipi', 'maximum_speed', 'displacement', 'door_number', 'seat_number']]

# 5. Excel'e Kaydet
excel_kayit_yolu = r"C:\Users\nvflb\OneDrive\Desktop\otopark\arac_ozellikleri.xlsx"
df.to_excel(excel_kayit_yolu, index=False)

print(f"İşlem tamam! İçinde boş veri olan hücreler atlanarak Excel dosyası oluşturuldu: {excel_kayit_yolu}")