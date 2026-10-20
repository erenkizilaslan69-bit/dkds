# DKDS – Ders Kitabı Denetim Sistemi

Ders kitaplarında içerik ve tutarlılık hatalarını PDF üzerinden otomatik olarak tespit eden sistem.
Tespit edilen her sorun, açıklamasıyla birlikte kitabın ilgili **sayfa ve paragrafında** gösterilir.

## Değerlendirme kriterleri

| Kriter | Yöntem | Durum |
|---|---|---|
| Yazım ve dil hataları | Kural tabanlı + morfolojik analiz | Planlandı |
| Yaş / sınıf seviyesine uygunluk | İstatistiksel (Ateşman, Bezirci-Yılmaz) | Planlandı |
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
| `dkds/duzen.py` | Üst/alt bilgi temizliği, bölünmüş paragrafların birleştirilmesi |
| `dkds/temizleme.py` | Satır sonu tirelemesi, ligatürler, bozuk kodlama tespiti |

`duzen.py` ve `temizleme.py` hiçbir PDF kütüphanesine bağlı değildir; böylece bağımsız olarak test edilebilirler.

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
    {"sayfa": 14, "paragraf": 2, "metin": "Fotosentez, bitkilerin ...", "konum": [56.7, 120.3, 538.6, 188.1], "ocr": false}
  ],
  "uyarilar": ["Sayfa 3: taranmış görünüyor ancak OCR yapılamadı (...)"]
}
```

## Testler

```powershell
python -m unittest -v
```

## Yol haritası

- [x] **Hafta 2–3:** PDF'ten sayfa/paragraf bilgisiyle metin çıkarma ve temizleme
- [ ] **Hafta 4–5:** Yazım ve dil hataları analizörü — ilk uçtan uca demo
- [ ] **Hafta 6–7:** Okunabilirlik / sınıf seviyesi analizörü
- [ ] **Hafta 8–9:** Kitap içi bilgi tutarsızlığı analizörü (LLM)
- [ ] **Hafta 10–11:** Arayüz ve raporlama
- [ ] **Hafta 12:** Değerlendirme (precision / recall)
- [ ] **Hafta 13–14:** Sunum ve dokümantasyon
