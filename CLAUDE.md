# DKDS – Ders Kitabı Denetim Sistemi

Eren'in (OMÜ Yazılım Geliştirme) Yazılım Geliştirme I dersi için tek başına geliştirdiği dönem projesi.
Dönem sonunda (Aralık sonu) Milli Eğitim Bakanlığı'na sunulacak. Her hafta hocaya Word formatında
gelişim raporu teslim ediliyor; raporda commit'ler, karşılaşılan problemler ve yapay zekâ kullanımı soruluyor.

## Proje tanımı (hocanın verdiği)

PDF formatındaki ders kitaplarını inceleyen bir sistem: PDF'ten metin çıkarma, seçilen üç kritere göre
hata tespiti, hatanın açıklanması ve hatanın bulunduğu sayfa/paragrafın gösterilmesi.

## Seçilen kriterler

1. **Yazım ve dil hataları** – kural tabanlı + morfolojik analiz (Zeyrek / Zemberek)
2. **Yaş / sınıf seviyesine uygunluk** – Ateşman ve Bezirci-Yılmaz formülleri; sabit eşik yerine
   MEB kitaplarından her sınıf için referans puan dağılımı çıkarılıp paragraflar kendi sınıf düzeyiyle karşılaştırılacak
3. **Kitap içi bilgi tutarsızlığı** – LLM destekli; gerçek dünyaya göre doğruluk değil, kitabın kendi içindeki
   çelişkiler. Yanlış alarm çok çıkarsa yedek kriter: terim tutarlılığı

## Yol haritası

- Hafta 2–3: PDF metin çıkarma + temizleme (`dkds/cikarim.py`, `duzen.py`, `temizleme.py`) — kod yazıldı, gerçek MEB PDF'leriyle test edilecek
- Hafta 4–5: Yazım analizörü → ilk uçtan uca demo
- Hafta 6–7: Okunabilirlik analizörü
- Hafta 8–9: Tutarsızlık analizörü (LLM seçimi: ücretsiz katmanlı API / Claude API / Ollama — maliyet hesabı yapılacak)
- Hafta 10–11: Arayüz (Streamlit) ve raporlama; hataları PDF üzerinde koordinatla vurgulama
- Hafta 12: Hata yerleştirilmiş test seti ile precision / recall ölçümü
- Hafta 13–14: Sunum, dokümantasyon, tampon

## Mimari kurallar

- Tüm analizörler `dkds/models.py` içindeki **`Bulgu`** formatında sonuç döndürür
  (sayfa, paragraf, kriter, sorunlu_metin, aciklama, guven, oneri, konum).
- PyMuPDF'e bağlı tek modül `cikarim.py`. Düzen ve temizleme mantığı kütüphaneden bağımsız kalmalı.
- `TEXT_DEHYPHENATE` bayrağı bilerek kullanılmıyor (gerçek tireleri siliyor); tireleme `temizleme.py`'de çözülüyor.
- Kod, değişken ve fonksiyon adları **Türkçe**, ASCII olmayan harfler olmadan (`paragraflari_birlestir`, `pdf_oku`).
- Testler `unittest` ile (`python -m unittest -v`); her yeni modül testleriyle birlikte yazılır.
- Ders kitabı PDF'leri `veri/`, çıktılar `cikti/` klasöründe; ikisi de git'e eklenmez.

## Test kitabı: `veri/fen5.pdf` (5. Sınıf Fen Bilimleri, 152 sayfa, 98 MB)

Ön inceleme (poppler ile, PyMuPDF'ten önce) bulguları:
- Metin katmanı var, Türkçe karakterler sağlam; bozuk kodlama beklenmiyor.
- Satır sonu tirelemesi yok denecek kadar az.
- Metinsiz (görsel) sayfalar: 1, 2, 7, 8, 148–151 (kapak, iç kapak vb.) → OCR uyarısı vermeleri normal.
- Alt bilgi örnekleri: "10 5. SINIF / FEN BİLİMLERİ", "58 2. ÜNİTE / KUVVETİ TANIYALIM" → temizlenmeli.
- Etkinlik sayfalarında "......" cevap satırları çok fazla → `dolgu_mu` ile atılıyor.
- "BİLGİ İSTASYONU", "ÖN DEĞERLENDİRME İSTASYONU" gibi kutu başlıkları ayrı paragraf olarak gelir;
  `siniflandirma.py` her paragrafa tür atar (baslik / govde / soru / liste / etiket).
- s.146–147 haritadır (yüzlerce etiket); sayfa bağlamı kuralıyla tamamı etiket sayılır.
- Bilinen sınırlama: font bilgisi kullanılmadığı için "Temel Kabuller" gibi ilk harfi büyük
  alt başlıklar etiket olarak sınıflanır.
- Düzyazı örnek sayfası: s.35 (Ay'ın yüzeyi). Paragraf ayrımını burada kontrol et.

## Çalışma şekli

- Eren her modülün ne yaptığını hocaya ve Bakanlık sunumunda açıklayabilmeli: kod yazarken
  neyin neden yapıldığını kısaca anlat, karmaşık çözümler yerine anlaşılır olanı tercih et.
- Haftalık rapor için: her haftanın sonunda yapılanları, karşılaşılan problemleri ve kullanılan önemli
  promptları özetlemeye yardım et. Rapordaki bilgiler gerçekte yapılanlarla birebir uyuşmalı.
- İletişim dili Türkçe.
