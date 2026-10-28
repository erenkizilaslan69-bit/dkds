# DKDS – Ders Kitabı Denetim Sistemi

Ders kitaplarında içerik ve tutarlılık hatalarını PDF üzerinden otomatik olarak tespit eden sistem.
Tespit edilen her sorun, açıklamasıyla birlikte kitabın ilgili **sayfa ve paragrafında** gösterilir.

## Değerlendirme kriterleri

| Kriter | Yöntem | Durum |
|---|---|---|
| Yazım ve dil hataları | Kural tabanlı + morfolojik analiz (zeyrek) | İlk sürüm |
| Yaş / sınıf seviyesine uygunluk | İstatistiksel (Ateşman, Bezirci-Yılmaz) | İlk sürüm (sınıf referansı) |
| Kitap içi bilgi tutarsızlığı | Yapay zekâ destekli (LLM) | Planlandı |

## Mimari

```
PDF ─► Metin çıkarma ─► Temizleme ─► Analizörler ─► Bulgular ─► Arayüz / Rapor
       (sayfa, paragraf,             ├─ Yazım
        koordinat)                   ├─ Okunabilirlik
                                     └─ Tutarsızlık (LLM)
```

| Modül | Görevi |
|---|---|
| `dkds/models.py` | Ortak veri yapıları: `Blok`, `Paragraf`, `Bulgu`, `CikarimSonucu` |
| `dkds/cikarim.py` | PyMuPDF ile PDF okuma, taranmış sayfalarda OCR |
| `dkds/duzen.py` | Üst/alt bilgi temizliği, kopya (tekrarlı) metin katmanının temizlenmesi, bölünmüş paragrafların birleştirilmesi |
| `dkds/temizleme.py` | Satır sonu tirelemesi, ligatürler, bozuk kodlama tespiti |
| `dkds/siniflandirma.py` | Paragraf türü: `baslik`, `govde`, `soru`, `liste`, `etiket` (kural tabanlı) |
| `dkds/analiz/yazim.py` | Yazım analizörü: kesin kurallar, bilinmeyen kelime, Türkçe karakter kaybı ayrımı |
| `dkds/analiz/morfoloji.py` | zeyrek sarmalayıcısı: kelime geçerliliği, önbellek, zeyrek hata yaması |
| `dkds/analiz/okunabilirlik.py` | Okunabilirlik analizörü: cümle ayırma, Ateşman ve Bezirci-Yılmaz formülleri, sınıf referansıyla karşılaştırma |
| `dkds/analiz/referans.py`, `referans.json` | Sınıf başına okunabilirlik referansı: ortanca, %10 ve %90 dilimleri (3-9. sınıf kitaplarından) |

`duzen.py`, `temizleme.py` ve `siniflandirma.py` hiçbir PDF kütüphanesine bağlı değildir; böylece bağımsız olarak test edilebilirler.

## Kurulum (Windows)

```powershell
python -m venv .venv
.venv\Scripts\activate
pip install -r requirements.txt
```

Taranmış (görsel) PDF'ler için ayrıca [Tesseract OCR](https://github.com/UB-Mannheim/tesseract/wiki) kurulmalı
ve kurulum sırasında **Turkish** dil paketi seçilmelidir. Tesseract yoksa sistem yine çalışır,
yalnızca taranmış sayfalar için uyarı verir.

## Kullanım

```powershell
python -m dkds veri\kitap.pdf
```

Çıktı `cikti\kitap.json` dosyasına yazılır:

```json
{
  "kaynak": "kitap.pdf",
  "sayfa_sayisi": 212,
  "paragraflar": [
    {"sayfa": 14, "paragraf": 2, "metin": "Fotosentez, bitkilerin ...", "konum": [56.7, 120.3, 538.6, 188.1], "ocr": false, "tur": "govde"}
  ],
  "uyarilar": ["Sayfa 3: taranmış görünüyor ancak OCR yapılamadı (...)"]
}
```

Yazım ve okunabilirlik analizi:

```powershell
python -m dkds analiz veri\kitap.pdf --sinif 5
```

`--sinif` (1-12) kitabın sınıf düzeyidir; verilirse okunabilirlik analizi de yapılır, verilmezse
yalnızca yazım analizi çalışır. Okunabilirlik analizi yalnızca gövde paragraflarını değerlendirir:
paragrafın Ateşman puanı, kitabın sınıfındaki referans dağılımın %10 diliminin altındaysa (yani o
sınıf kitaplarındaki paragrafların %90'ından daha zorsa) bulgu üretilir. Referans 3-9. sınıf
kitaplarından çıkarılmıştır (`dkds\analiz\referans.json`); bu aralığın dışındaki sınıflarda kitabın
kendi %10 dilimi kullanılır. Ateşman puanı 0'ın altındaki ya da aynı 10 kelimelik diziyi iki kez içeren
birimler okunabilirlik bulgusu sayılmaz; ölçüme katılmadan `cikarim_sorunu` türünde "olası metin çıkarma
sorunu" olarak ayrıca raporlanır. Ekranda ve JSON'daki `okunabilirlik_ozeti` bölümünde kitabın genel
Ateşman / Bezirci-Yılmaz puanı, kullanılan referans, puan dağılımı, işaretlenen oran ve en zor 10
paragraf yer alır.

Referansı yeniden üretmek (ölçüm kodu değiştiğinde ya da yeni kitap eklendiğinde):

```powershell
python -m dkds referans -k 3 veri\fen3.pdf -k 5 veri\fen5.pdf -k 5 veri\sosyalbilgiler5.pdf `
    -k 7 veri\fen7.pdf -k 9 veri\biyoloji9.pdf
```

Bulgular `cikti\kitap_bulgular.json` dosyasına yazılır; ekranda kriter, bulgu türü ve paragraf
türüne göre özet gösterilir. Her bulgu `Bulgu` formatındadır (sayfa, paragraf, kriter,
sorunlu_metin, aciklama, guven, oneri, konum, tur). `karakter_kaybi` türündeki bulgular yazım
hatası değil, olası metin çıkarma sorunudur (ör. dekoratif yazı tipi ş'yi s olarak kodlar).

## Testler

```powershell
python -m unittest -v
```

## Yol haritası

- [x] **Hafta 2–3:** PDF'ten sayfa/paragraf bilgisiyle metin çıkarma ve temizleme
- [x] **Hafta 4–5:** Yazım ve dil hataları analizörü — ilk uçtan uca demo (ilk sürüm)
- [x] **Hafta 6–7:** Okunabilirlik / sınıf seviyesi analizörü (ilk sürüm; sınıf referansı 3-9. sınıfta sınıf başına 1-2 kitaptan)
- [ ] **Hafta 8–9:** Kitap içi bilgi tutarsızlığı analizörü (LLM)
- [ ] **Hafta 10–11:** Arayüz ve raporlama
- [ ] **Hafta 12:** Değerlendirme (precision / recall)
- [ ] **Hafta 13–14:** Sunum ve dokümantasyon
