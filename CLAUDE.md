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
- s.5–6 (İstiklal Marşı, Gençliğe Hitabe) eski bir yazı tipiyle basılmış; ön incelemedeki "bozuk
  kodlama beklenmiyor" notu bu sayfalar için geçerli değil. `temizleme.kodlamayi_onar` onarıyor.
- Düzyazı örnek sayfası: s.35 (Ay'ın yüzeyi). Paragraf ayrımını burada kontrol et.

## İkinci test kitabı: `veri/sosyalbilgiler5.pdf` (5. Sınıf Sosyal Bilgiler, 154 sayfa)

Kurallar iki kitapta da denenmeli; tek kitaba göre eşik ayarlanmamalı.
- Satır aralığı fen5'ten sıkı: satır kutuları üst üste biniyor (birleştirme toleransı buna göre).
- Haritalar: s.54 (1289 paragraf), 55, 90, 94, 111, 153, 154. Harita simgeleri ESRI yazı
  tiplerinden "Ä!", "!p" gibi anlamsız karakterler olarak geliyor.
- Bazı başlıklarda İ harfi metin katmanında I olarak kodlanmış ("ÖĞRENELIM", "TÜRKIYE");
  basılı halde doğru. Yazım analizöründe yanlış alarm üretebilir.
- s.142'de aynı cümleler iki farklı yazımla iki kez çıkıyor (gizli/üst üste metin katmanı).
- Madde imi az kullanılmış; liste türünün düşük çıkması (%1) kural hatası değil.
- s.3–4 (İstiklal Marşı, Gençliğe Hitabe) eski Türkçe yazı tipi: ş, ı, ğ, İ, Ş harfleri Unicode'a
  eşlenmemiş kodlarla saklanıyor (ú→ş, Õ→ı, ÷→ğ, ø→İ, ù→Ş; büyük harfli kelimedeki ö→Ğ).
  PyMuPDF'in varsayılan bayrağıyla (TEXT_CID_FOR_UNKNOWN_UNICODE) bu kodlar gelir; bu bayrak
  olmadan "�" olur ve bilgi kaybedilir. Onarım sayfa başına yapılır ve uyarıyla bildirilir.
  Harita sayfaları (ESRI simge yazı tipleri) bu eşlemeyle onarılamaz, eski davranışta kalır.

## Tutarsızlık kriteri test örnekleri (sosyalbilgiler5)

Alıntılar çıkarılan metinden doğrulandı (28.10.2026). Bu kitapta PDF sayfa numarası basılı
sayfa numarasıyla aynıdır. Kitap kendi sayma kuralını s.112'de verir: "2000'li yıllarda olduğumuz
düşünüldüğünde" yani günümüzden kaç yıl önce = MÖ yıl + 2000.

Çelişki adayı (analizör yakalamalı):
- Çatalhöyük: s.112 "Çatalhöyük (MÖ 7500)" → 9.500 yıl önce; s.147 "Bundan 9 500 yıl önce
  Çatalhöyük sakinleri…" bununla tutarlı; s.118 "Çatalhöyük, yaklaşık 9000 yıl önce kurulmuştur"
  ise 500 yıl farklı. "yaklaşık" yuvarlama savunması olabilir, güven orta tutulmalı.

Tutarlı örnek (yanlış alarm üretmemeli):
- Göbeklitepe: s.112 "MÖ 10000 yıllarında inşa edilmiştir" = "günümüzden 12.000 yıl önce"; s.114
  "Günümüzden yaklaşık 12 bin yıl önce" (aynı değer, farklı yazım: "12.000" / "12 bin").
  Not: s.128'deki "11.500-12.000 yıl önce" Karahantepe için, Göbeklitepe için değil.

## Okunabilirlik analizörü notları

- Bezirci-Yılmaz formülünde karekök TÜM çarpımın üzerindedir: √(OKS × (H3×0,84 + H4×1,5 + H5×3,5 +
  H6×26,25)). Orijinal makaleden (Bezirci ve Yılmaz 2010, DEÜ Fen ve Müh. Dergisi 12(3), Çizelge 8-9)
  doğrulandı; `tests/test_okunabilirlik.py` makaledeki 9 değeri yeniden üretir.
- **Kural (referans tabanlı):** birimin Ateşman puanı, kitabın sınıfındaki referans dağılımın %10
  diliminin altındaysa bulgu (`dkds/analiz/referans.json`: sınıf → ortanca, %10, %90; Ateşman ve
  Bezirci-Yılmaz). Referansta olmayan sınıflarda (1-2, 10-12) kitabın kendi %10 dilimi kullanılır ve
  açıklama bunu söyler. Ateşman'ın puan → sınıf tablosu yalnızca bilgi olarak gösterilir.
  Birim: gövde paragrafı; 40 kelimeden kısalar aynı sayfadaki komşu gövde paragraflarıyla birleştirilir.
- **Neden referans:** Ateşman tablosu Türkçe ders kitabı metnini sistematik olarak çok zor gösterir.
  İlk sürümdeki sabit kural ("kitabın sınıfının ≥2 kademe üstü") fen5'te birimlerin %88'ini, sosyal5'te
  %93'ünü işaretliyordu (ortanca birim puanı 54,9 / 47,2 = "11-12. sınıf / lisans").
- **Referans kitapları** (`python -m dkds referans -k SINIF PDF ...` ile üretilir): fen3 (160 sayfa,
  serinin 1. kitabı), fen5 (152) ve sosyalbilgiler5 (154) → 5. sınıf (401 birim), fen7 (153 sayfa,
  1. kitap; sözlük ve kaynakçayla bittiği için eksik değil), biyoloji9 (184). Ara sınıflar (4, 6, 8)
  komşulardan doğrusal ara değerdir. Birim bazında Ateşman (düşük = zor), ölçüm sürümü 2:

  | sınıf | birim | %10 | ortanca | %90 | B-Y ortanca |
  |---|---|---|---|---|---|
  | 3 | 155 | 29,5 | 52,5 | 80,8 | 11,8 |
  | 4 | ara | 30,6 | 51,2 | 74,5 | 13,2 |
  | 5 | 401 | 31,7 | 49,9 | 68,3 | 14,6 |
  | 6 | ara | 29,4 | 47,6 | 65,4 | 15,3 |
  | 7 | 216 | 27,1 | 45,3 | 62,6 | 16,0 |
  | 8 | ara | 25,8 | 44,5 | 62,5 | 17,4 |
  | 9 | 362 | 24,5 | 43,8 | 62,4 | 18,9 |

- **Sınıf eğilimi gerçek ama zayıf ve eşit adımlı değil** (ölçüm sürümü 1 birimleriyle, bootstrap
  %95 aralığı): fen3→fen5 ortanca farkı +2,3 [-3,0; +5,7] gürültü, fen5→fen7 -9,6 [-12,5; -6,7] gerçek,
  fen7→biyoloji9 -1,5 [-4,0; +1,3] gürültü, fen3→biyoloji9 -8,9 gerçek; Spearman (n=878) Ateşman -0,26,
  Bezirci-Yılmaz +0,40. **Ders etkisi bir sınıf adımı kadar büyük:** fen5→sosyal5 -7,7 [-11,0; -5,2].
  Bu yüzden 5. sınıf referansı iki dersi birleştirir; diğer sınıflar tek kitaptan (fen/biyoloji) gelir.
- **Referansın duyarlılığı** (işaretlenen birim oranı; * = kitabın kendi sınıfı, beklenen ≈ %10):

  | kitap | 3. sınıf ref. | 5. sınıf ref. | 7. sınıf ref. | 9. sınıf ref. |
  |---|---|---|---|---|
  | fen3 | %10,3* | %12,3 | %8,4 | %6,5 |
  | fen5 | %4,2 | %4,9* | %3,5 | %2,1 |
  | sosyalbilgiler5 | %7,4 | %12,8* | %6,6 | %5,1 |
  | fen7 | %14,4 | %16,7 | %10,2* | %6,5 |
  | biyoloji9 | %16,9 | %19,9 | %14,1 | %10,2* |

  Üst sınıf kitapları 5. sınıf referansında daha çok işaretlenir (%16,7 / %19,9) ama ayrım zayıf ve
  ders etkisiyle karışık (sosyal5 %12,8 ≈ fen3 %12,3). Çok sayıda kitap ve ders eklenince iyileşir.
- **Referans ölçüme bağlıdır:** cümle ayırma, birim oluşturma, atlama kuralları ya da formüller
  değişirse `okunabilirlik.OLCUM_SURUMU` artırılır ve referans yeniden üretilir
  (`tests/test_referans_dosyasi.py` uyuşmazlığı yakalar, analizör uyarı verir). Üretim komutu:
  `python -m dkds referans -k 3 veri\fen3.pdf -k 5 veri\fen5.pdf -k 5 veri\sosyalbilgiler5.pdf
  -k 7 veri\fen7.pdf -k 9 veri\biyoloji9.pdf`
- Ölçüme girmeyenler: cümle sonu işareti olmayan paragraflar (kavram listesi, haber başlığı, tablo
  hücresi), sözlükçe paragrafları, form/etkinlik künyeleri ("Adı : … Amacı : … Süre :"; ≥3 alan),
  sayfada 40 kelimelik gövde metni olmayan paragraflar. Sayıdaki nokta ("4.000") cümle sonu
  sayılmaz. Şık işaretleri ("a.", "A)") cümleye katılmaz.
- fen5'te %5, sosyal5'te %13 birim işaretlenir. En zor 10 paragraf basılı sayfayla kontrol edildi:
  gerçek ve gerçekten zor düzyazı (sosyal5'te haber alıntıları s.106, 115, 128; uzun görev cümleleri
  s.125; fen5 s.17 mühendislik tasarım döngüsü kutu metni; s.13 güvenlik sembolü kartları).
- Bilinen sınırlamalar: referans kitap sayısı az (sınıf başına 1-2) ve dersler karışık; kitabın
  yöntem/tanıtım metinleri (s.17 gibi) ile öğrencinin okuması beklenen metinler ayırt edilmiyor;
  tablo/kart düzenindeki cümleler (s.13) okuma sırasına göre birleşebiliyor.

## Yazım analizörü notları

- zeyrek 0.1.3'te durum bozulması hatası var (lru_cache'li küme değiştiriliyor); `morfoloji.py`
  çalışma anında yamalıyor. Yama kaldırılırsa sonuçlar çalıştırmadan çalıştırmaya değişir.
  Yama bu sürümün iç yapısına bağlı: requirements.txt'de `zeyrek==0.1.3` sabit, yükseltme yapılırsa
  yamanın hâlâ işe yaradığı `tests/test_morfoloji.py` ile kontrol edilmeli.
- fen5 s.56–57, 96–97: dekoratif Jokerman yazı tipi ş/ğ'yi s/g kodluyor; basılı hali doğru
  ("Günes", "kaynagı") → `karakter_kaybi` (çıkarım sorunu), yazım hatası değil.
- Bulgu değerlendirmesi metin katmanına değil, PDF'in basılı görüntüsüne bakılarak yapılır.
- Bulunan gerçek hatalar: fen5 "hedeflenmektedi ." (s.31), "nesile" (s.111), "sınıflandırılı ."
  (s.124, 129), boşluklu tire (s.31, 118); sosyal5 "anektod" (s.37), "öğretmlerimiz" (s.79),
  "nakışı" (s.23), "fotoğraf,gazete" (s.62), kaynakça "Özyürek,A" (s.21).
- Kalan yanlış alarmların çoğu yabancı/yöresel kelimeler ("kukeri", "resfebe") ve zeyrek'in
  tanımadığı biçimler ("bulmalıyız", "sahipti"). `ek_sozluk.txt`'ye yalnızca TDK'da olan sözcük eklenir.
- İstiklal Marşı sayfaları (fen5 s.5, sosyal5 s.3) onarıldıktan sonra yazıma girer; metnin
  arkaik sözcükleri ("serhaddim", "vecd", "hürriyyet") düşük güvenli yanlış alarm üretir.

## Çalışma şekli

- Eren her modülün ne yaptığını hocaya ve Bakanlık sunumunda açıklayabilmeli: kod yazarken
  neyin neden yapıldığını kısaca anlat, karmaşık çözümler yerine anlaşılır olanı tercih et.
- Haftalık rapor için: her haftanın sonunda yapılanları, karşılaşılan problemleri ve kullanılan önemli
  promptları özetlemeye yardım et. Rapordaki bilgiler gerçekte yapılanlarla birebir uyuşmalı.
- İletişim dili Türkçe.
