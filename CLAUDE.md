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
  `duzen.tekrarli_metni_temizle` büyük kısmını temizliyor, yazımı farklı parçalı kutular kısmen kalıyor.
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
  serinin 1. kitabı), fen5 (152) ve sosyalbilgiler5 (154) → 5. sınıf (392 birim), fen7 (153 sayfa,
  1. kitap; sözlük ve kaynakçayla bittiği için eksik değil), biyoloji9 (184). Ara sınıflar (4, 6, 8)
  komşulardan doğrusal ara değerdir. Birim bazında Ateşman (düşük = zor), ölçüm sürümü 3:

  | sınıf | birim | %10 | ortanca | %90 | B-Y ortanca |
  |---|---|---|---|---|---|
  | 3 | 133 | 38,3 | 56,1 | 87,1 | 11,2 |
  | 4 | ara | 35,2 | 52,8 | 77,0 | 13,0 |
  | 5 | 392 | 32,1 | 49,5 | 66,9 | 14,7 |
  | 6 | ara | 29,9 | 47,4 | 64,8 | 15,3 |
  | 7 | 212 | 27,6 | 45,4 | 62,8 | 15,9 |
  | 8 | ara | 27,1 | 44,8 | 62,7 | 17,3 |
  | 9 | 348 | 26,5 | 44,3 | 62,5 | 18,7 |

- **Sınıf eğilimi gerçek ama zayıf ve eşit adımlı değil** (ölçüm sürümü 3, bootstrap %95 aralığı):
  fen3→fen5 Ateşman ortanca farkı -1,2 [-6,3; +2,7] gürültü (B-Y +1,5 gerçek), fen5→fen7 -9,5 [-12,2; -6,5]
  gerçek, fen7→biyoloji9 -1,1 [-3,5; +1,6] gürültü (B-Y +2,8 gerçek), fen3→biyoloji9 -11,8 gerçek;
  Spearman (n=836) Ateşman -0,30, Bezirci-Yılmaz +0,44. **Ders etkisi bir sınıf adımı kadar büyük:**
  fen5→sosyal5 -7,7 [-10,7; -5,0]. Bu yüzden 5. sınıf referansı iki dersi birleştirir; diğer sınıflar
  tek kitaptan (fen/biyoloji) gelir. (Kopya metin temizliği öncesi, sürüm 1'de Spearman -0,26 / +0,40 idi.)
- **Referansın duyarlılığı** (işaretlenen birim oranı; * = kitabın kendi sınıfı; beklenen ≈ %10, turkce5
  referansta yok):

  | kitap | 3. sınıf ref. | 5. sınıf ref. | 7. sınıf ref. | 9. sınıf ref. |
  |---|---|---|---|---|
  | fen3 | %10,5* | %6,0 | %3,8 | %3,0 |
  | fen5 | %14,7 | %6,3* | %4,2 | %2,8 |
  | sosyalbilgiler5 | %26,5 | %12,4* | %6,0 | %5,6 |
  | fen7 | %30,7 | %17,0 | %10,4* | %7,5 |
  | biyoloji9 | %35,6 | %17,5 | %12,1 | %10,1* |
  | turkce5 | %17,9 | %7,6 | %4,0 | %3,6 |

  Kopya metin temizliğinden sonra eğilim eskisinden net: 5. sınıf referansında fen3 %6,0 < fen5 %6,3 <
  sosyal5 %12,4 < fen7 %17,0 ≈ biyoloji9 %17,5 (öncekinde fen3 %12,3 ile sosyal5 %12,8 aynıydı; fen3'ün
  eski çıkarımında birimlerin %26'sı kopya metinli olduğu için yapay zordu). Ders etkisi sürüyor
  (sosyal5 fen5'in iki katı). Çok sayıda kitap ve ders eklenince iyileşir.
- **Referans ölçüme bağlıdır:** cümle ayırma, birim oluşturma, atlama kuralları ya da formüller
  değişirse `okunabilirlik.OLCUM_SURUMU` artırılır ve referans yeniden üretilir
  (`tests/test_referans_dosyasi.py` uyuşmazlığı yakalar, analizör uyarı verir). Metin çıkarma
  değişikliği de ölçümü değiştirir (sürüm 3 kopya metin temizliğiyle birlikte geldi). Üretim komutu:
  `python -m dkds referans -k 3 veri\fen3.pdf -k 5 veri\fen5.pdf -k 5 veri\sosyalbilgiler5.pdf
  -k 7 veri\fen7.pdf -k 9 veri\biyoloji9.pdf`
- **Kopya metin katmanı** (`duzen.tekrarli_metni_temizle`, çıkarımda çalışır): bazı sayfalarda aynı metin
  PDF'e iki kez konmuş ve çıkarımda iç içe geçiyordu (turkce5 s.68/122 döndürülmüş "Bu temada" kutuları,
  biyoloji9 s.18 zaman çizelgesi, sosyal5 s.142 şeması, fen3'ün birçok sayfası). Art arda gelen benzer
  satırlar (≥ %85) tek satıra iner; başka bir bloğun aynı yerinde duran, metni ≥ %80 benzeyen blok
  silinir; temizlenen sayfalar uyarıyla bildirilir. Paragraf sayısı: turkce5 3813→3362, biyoloji9
  3822→3787, sosyal5 4182→4173, fen5 2164→2163, fen3/fen7 aynı (fen3'te satır içi temizlik: tekrarlı
  birim 35→8). Yazımı farklı kopyalar (sosyal5 s.142 "Anadolu'ya"/"Anadoluya" gibi parçalı kutular)
  kısmen kalır. Tek harfli döndürülmüş başlık parçaları ("s", "a", "ı"…) hâlâ ayrı etiket olarak çıkıyor.
- **Çıkarım şüphesi kuralı** (okunabilirlik): birimin Ateşman puanı 0'ın altındaysa ya da metinde aynı
  10 kelimelik dizi örtüşmeden iki kez geçiyorsa birim ölçüme (dağılım, oran, referans) girmez ve
  okunabilirlik bulgusu yerine `tur="cikarim_sorunu"` ("olası metin çıkarma sorunu", güven 0,3) olarak
  raporlanır; özet ve ekranda "Çıkarım şüphesi: N birim". Dizi uzunluğu 6 ve 8 kelimede gerçek şablon
  cümleleri de yakalıyordu (turkce5 s.12 iki ödev maddesi, fen7 "…sistemini oluşturan yapı ve organların"
  soruları), 10'a çıkarıldı. Kural kaba bir sezgisel: şüpheli birimlerin çoğu çıkarım hatası değil.
  turkce5'te ayrılan 5 birim: 2 şablon tekrarı (s.65, 171), 2 form örneği (s.88/98 "Kişiler: Yer: Zaman:
  Olaylar:"), 1 madde imli uzun cümle (s.68); sosyal5'te 4'ü s.54 harita simgeleri ("Ä!" tekrarı, yerinde
  ayırma), s.62, s.151 kaynakça, ve **s.125 ile s.128 gerçek ama aşırı uzun haber/görev cümleleri**
  (Ateşman -8 / -12; basılı sayfayla gerçek metin olduğu doğrulanmıştı, kural bunları sınıf üstü
  yerine çıkarım sorunu diye ayırıyor).
- Ölçüme girmeyenler: cümle sonu işareti olmayan paragraflar (kavram listesi, haber başlığı, tablo
  hücresi), sözlükçe paragrafları, form/etkinlik künyeleri ("Adı : … Amacı : … Süre :"; ≥3 alan),
  sayfada 40 kelimelik gövde metni olmayan paragraflar, çıkarım şüphesi birimleri. Sayıdaki nokta
  ("4.000") cümle sonu sayılmaz. Şık işaretleri ("a.", "A)") cümleye katılmaz.
- fen5'te %6 (9/143), sosyal5'te %12 (31/249) birim işaretlenir. En zor 10 paragraf basılı sayfayla
  kontrol edildi (kopya temizliği öncesi): gerçek ve gerçekten zor düzyazı (sosyal5'te haber alıntıları
  s.106, 115, 128; fen5 s.17 mühendislik tasarım döngüsü kutu metni; s.13 güvenlik sembolü kartları).
  Temizlikten sonra fen5'in en zor 10'u aynı kaldı; sosyal5'te s.125 ve s.128 (biri) çıkarım şüphesine
  geçti, listeye s.128'in ikinci parçası ve s.37 girdi.
- **Bağımsız doğrulama: turkce5.pdf** (5. sınıf Türkçe, 178 sayfa; referansta YOK, referans eklenmeden
  `--sinif 5`, 28.10.2026). İlk çalıştırma (kopya temizliği ve çıkarım şüphesi kuralından önce, eski
  referansla): 335 birimde 28 işaretlendi = **%8,4**. En zor 10'dan 4'ü basılı sayfayla kontrol edildi:
  s.122 ve s.68 çıkarım sorunu (döndürülmüş kutularda satırlar üst üste binmiş; sahte 60 kelimelik cümle,
  Ateşman -129 / -42), s.98 form örneği, s.35 gerçek (kitabın "uzun cümleyi böl" etkinliği). En zor
  listenin ilk dördü çıkarım artığı veya form metniydi.
  Temizlik ve kuraldan sonra (referans sürüm 3, turkce5 hâlâ referansta değil): **25 / 329 birim = %7,6**
  (beklenen ≈ %10; standart hata ≈ %1,7, yani tutarlı); kitap ortancası 55,0, referans ortancasından
  (49,5) +5,5 puan kolay. Çıkarım şüphesi 5 birim. Yeni en zor 10 (s.45, 35, 16, 112, 12, 162, 112, 125,
  72, 160) metin olarak okundu: hepsi gerçek, etkinlik yönergesi/tanım/ödev metni; s.35 ve s.45 önceden
  basılı sayfayla doğrulanmıştı, kalan 8'i basılı sayfayla yeniden karşılaştırılmadı. Tek kitap ve
  referansın oranı iki yönde de oynatmamış olması şans da olabilir; Türkçe dersi dil kitabı olduğundan
  ders etkisi beklenir. fen5/sosyal5 oranları referansın içinde olduğu için bağımsız sınav sayılmaz.
- Bilinen sınırlamalar: referans kitap sayısı az (sınıf başına 1-2) ve dersler karışık; kitabın
  yöntem/tanıtım metinleri (s.17 gibi) ile öğrencinin okuması beklenen metinler ayırt edilmiyor;
  tablo/kart düzenindeki cümleler (s.13) okuma sırasına göre birleşebiliyor; etkinlik yönergeleri
  ("ETKİNLİK a.a. …" etiketleri dahil) ile öğrenci örnek metinleri ölçüme giriyor; kopya katman
  temizliği yalnızca aynı yerde duran ve benzer metinleri yakalar.

## Tutarlılık analizörü notları (kriter 3, kural tabanlı: tarih ve birimli sayısal olgular)

- `dkds/analiz/tutarlilik.py` + `sayilar.py`, `python -m dkds analiz` içinde her çalıştırmada koşar (sınıf
  gerekmez). Bulgu `kriter="tutarlilik"`, `tur="tarih_celiskisi"` / `"sayisal_celiski"`; `Bulgu`da isteğe
  bağlı `ilgili_sayfa`, `ilgili_paragraf`, `ilgili_konum` (çelişen diğer yer). JSON'da `tutarlilik_ozeti` ve
  `tutarlilik_belirsiz` (LLM'e gidecek çiftler). LLM henüz yok.
- **Tarih olgusu:** "MÖ 7500", "M.Ö. 7500", "MS 1071", "MÖ 10000 yıllarında", "9 500 yıl önce", "12.000 yıl önce",
  "yaklaşık 12 bin yıl önce", "on bin yıl önce", aralık. Yaklaşık: "yaklaşık", "civarında", "yıllarında",
  "MÖ 5000'lerde". Günümüzden-yıl-önce: MÖ yıl + referans yıl (varsayılan 2000, kitabın s.112 kuralı),
  MS için referans yıl - yıl. Yüzyıl ve 100'den küçük "yıl önce" olgu değil.
- **Sayısal olgu** (`sayilar.py`): zaman (saniye/dakika/saat/gün/hafta/yıl; "365 gün 6 saat" bileşik, yıl=365,25
  gün), uzunluk (mm/cm/m/km, "384.000 km", "1 milyon km"), sıcaklık (°C/⁰C/ºC, "-174 ⁰C"), kütle (g/kg/ton),
  kuvvet (N), yüzde ("%71", "yüzde 71"). Hepsi ortak tabana (saniye, metre, gram, N, °C, %) çevrilir.
  Yazıyla sayılar ("yirmi dört saat", "on bin yıl") rakama çevrilir (tek başına "bir" sayı değil; "12 bin"deki
  "bin" çarpan). Ölçü değil: "15 Nisan", "2024 günü", "100 km/saat", "50 m²", "45 derece açı". Tolerans: tüm
  ölçülerde %1 (384.000 ~ 384.400 yuvarlama farkı çelişki değil), yaklaşık olanda yuvarlama basamağının yarısı
  eklenir; tarihte yaklaşık değer ±(yuvarlama birimi/2) (9000 → ±500; "MÖ 10000 yıllarında" en çok ±500), kesinde 0.
- **Varlık:** aynı cümledeki en yakın özel isim (en çok 80 karakter; ölçülerde en yakın iki isim, tarihte tek).
  Kesme eki atılır; yan yana büyük harfli sözcükler öbek ("Karain Mağarası") ve öbek son sözcüğüyle de eşleşir
  ("Sümer Kralı Urukagina" ~ "Urukagina"; son sözcük genel adsa mağarası/höyüğü/kralı... eşleşmez). Cümle başındaki
  büyük harfli sıradan sözcük ("Çemberimsi", "Bundan") isim değil: kesme eki, virgül/noktalı virgül/parantez,
  öbek, kitapta cümle ortasında da büyük harfle geçme ya da kısa etiket gerekir. "Ay" iki harfli ama varlık.
  Ay/gün adları, form etiketleri ("Süre : 40 dk"), BÜYÜK HARFLİ başlık sözcükleri isim değil; Dünya/Türkiye/
  Anadolu gibi genel adlar yalnızca tarihte elenir. Harita/şema etiket paragrafları ve etkinlik künyeleri
  ("Adı … Amaç … Süre 80 dk") ölçü olgusu sayılmaz.
- **Alıştırma/değerlendirme içeriği olgu değil:** iki kademe. *Güçlü yönerge* ("doğru ise", "yanlış ise", "doğru ya da yanlış",
  "D/Y", "boşlukları doldurunuz"; ≤ 40 kelimelik paragraf) altındaki maddeleri, ilk gerçek başlığa, ilk uzun gövde paragrafına
  (> 30 kelime: anlatım/okuma metni) ya da sayfa sonuna kadar olgu dışı bırakır ("D Y" gibi sütun etiketleri başlık değil).
  *Zayıf yönerge* ("cevaplayınız", "işaretleyiniz", "eşleştiriniz": etkinlik yönergesi de olabilir) yalnızca kendisini ve hemen
  altındaki soru/liste/"(……)" maddelerini kapsar. `soru` türündeki paragraflar her zaman dışarıda
  (`TutarlilikAnalizoru.alistirma_paragraflari`). Neden: fen5 s.50 Pekiştirme İstasyonu'nda "5. Dünya, dolanma hareketini 24
  saatte tamamlar" bilerek yanlış yazılmış doğru/yanlış maddesidir, kitap hatası değil (s.49-s.50 testi). İlk sürüm blok
  sayfa sonuna kadar sürüyor ve anlatımı da düşürüyordu (fen7 s.120 "3-4 saniye nefes", s.140 diyaliz); biyoloji9 s.157
  "tahıl tarımı yaklaşık 10 000 yıl önce" basılı sayfayla kontrol edildi: 20. sorunun "Boş bırakılan bölümleri işaretleyiniz"
  maddesi, yani gerçekten soru bağlamı; olgu dışı kalması doğru.
- **Zamir çözümleme (varlık devralma):** cümlede özel isim yoksa (1) cümle zamir/gösterme sözcüğüyle başlıyorsa ("Bu dolanma
  hareketi…", "Bunun…", "O…", "Söz konusu…", "Aynı…") varlık aynı paragraftaki en çok iki önceki cümleden (en yakından, cümlenin
  ilk özel ismi) alınır; paragraf sınırı aşılmaz; (2) cümle başı çoğul isimse ("Yılanlar 10 ila 15 yıl yaşar") o isim varlıktır
  ("Bunlar", "Onlar" hariç). `Olgu.varlik_kaynagi` = "cumle" / "onceki" / "cogul"; bulgu güveni önceki için ×0,8, çoğul için ×0,9
  (iki olgudan düşük olan). Bağlaçla başlayan cümleler ("Ardından…", "Sonra…") denendi, yanlış varlık getirdi (turkce5 s.111
  "Ardından … 2-3 dakikalık konuşma" → "Cumhuriyet"), kapsam dışı.
- **Olgu anahtarı = varlık + nicelik türü + ayırıcı + bağlam.** Tür: sıcaklık/kütle/kuvvet/oran sabit; uzunlukta
  çap, yarıçap, uzaklık, yükseklik, derinlik, uzunluk...; zamanda dönme, dolanma, ömür, süre (en yakın sözcük).
  Ayırıcı: gece, gündüz, ortalama, kış, kutup, ekvator, yüzey, en yüksek/en düşük... (değerden önce geldiği için
  izleyen ilk ölçüye bağlanır: "gece -174 ⁰C, gündüz ise 125 ⁰C"). Bağlam: çevredeki içerik sözcüklerinin ilk 5
  harfi (Jaccard ≥ 0,1). Koşul ölçüsü: aynı cümledeki diğer boyuttaki ölçüler ("60 kg kütleli cismin ağırlığı
  100 N"); yalnızca birinde varsa ya da farklıysa çift belirsiz.
- **Karşılaştırma:** aynı varlık ve boyutta, değerleri toleransı aşan, farklı sayfalardaki iki olgu:
  tür ya da ayırıcı farklı → farklı nicelik (sayılmaz); tür aynı + ayırıcı aynı + koşullar uyumlu + bağlam benzer
  → **aday çelişki**; emin olunamıyorsa → **belirsiz** (tür belli değil, ayırıcı yalnızca birinde, koşul farklı,
  bağlam benzemiyor; ayrıca varlığı bulunamayan ama bağlamı benzeyen çiftler: güçlü = Jaccard ≥ 0,25 ve ≥ 2 ortak
  kök, zayıf = ≥ 0,15 ve ≥ 1). Tarihte varlık yeterli; olay türü (başlangıç: kuruldu/inşa / bitiş: terk edildi)
  ikisinde de belli ve farklıysa ayrı olay. Güven: fark/tolerans 1'de 0,45, 4'te 0,75; ölçüde bağlam benzerliğiyle
  hafif azalır.
- **Sonuç (6 kitap, 11.11.2026, alıştırma filtresi sınırı ve zamir çözümlemeden sonra):**

  | kitap | olgu (tarih+sayısal) | varlıkla eşleşen | aday çelişki | belirsiz (zayıf) | farklı nicelik |
  |---|---|---|---|---|---|
  | fen3 | 14 (0+14) | 6 | 0 | 0 | 0 |
  | fen5 | 36 (0+36) | 23 | 0 | 4 (0) | 1 |
  | fen7 | 25 (0+25) | 8 | 0 | 0 | 0 |
  | biyoloji9 | 58 (0+58) | 11 | 0 | 0 | 0 |
  | sosyalbilgiler5 | 43 (18+25) | 29 | 1 | 0 | 0 |
  | turkce5 | 7 (0+7) | 0 | 0 | 0 | 0 |

  Varlıkla eşleşen oran %36,6 (67/183) → %42,1 (77/183); 10 olgunun varlığı zamir/çoğul özneden geldi (fen3 3 çoğul,
  fen5 2 + 1 önceki cümle, biyoloji9 3 çoğul, sosyal5 1). Filtre sınırı olgu sayısını 161 → 183 yaptı (fen7 21 → 25,
  biyoloji9 40 → 58 olgu geri geldi). Belirsiz 6 → 4: fen3 yılan/kaplumbağa çifti artık farklı varlık, fen5 s.49 dönme (24 saat)
  ve dolanma (365 gün 6 saat) aynı varlıkta (Dünya) "farklı nicelik". Aday çelişki değişmedi (yalnızca Çatalhöyük).
  Tarih olgusu çıkmayan fen/Türkçe kitaplarında sayısal olgu çıktı.
- **Aday kontrolü (basılı sayfayla):** tek aday gerçek çelişki ve eşleştirme doğru: Çatalhöyük s.118 "yaklaşık
  9000 yıl önce" ↔ s.112 "MÖ 7500" (=9.500) ve s.147 "9 500 yıl önce"; üçü de kuruluş/ilk yerleşme, güven 0,45
  (fark 500 yıl, yuvarlamanın tam sınırı; s.118 tırnak içi dış kaynak alıntısı). Göbeklitepe (s.112, 114) ve
  Karahantepe bulgu üretmedi.
- **En sık hata nedenleri (geliştirme sırasında çıkan 7 farklı aday: 1 gerçek, 6 sahte):** (1) **eşleştirme
  hatası, etkinlik künyesi:** "Adı … Amaç Çevresindeki … Süre 80 dk" ve "Süre : 40 dk" cümlelerinde "Süre"/"Çevresindeki"
  varlık sanıldı → 4 sahte aday (biyoloji9); çözüm: künye/etiket paragrafları ölçü dışı, form etiketi varlık değil.
  (2) **farklı nesne:** fen5 s.76 "60 kg'lık cismin ağırlığı Ay'da 100 N" ile s.93 başka cismin "Ay'da 60 N"si →
  koşul ölçüsü kuralıyla belirsiz. (3) **kod hatası:** "12 bin yıl önce"deki "bin" yazıyla sayı sanılıp Göbeklitepe
  için sahte 11.000 yıllık fark üretti; giderildi (test var). (4) ayırıcı yanlış bağlama: "gece -174, gündüz ise 125"
  cümlesinde "gündüz" -174'e atanıyordu; izleyen ilk ölçüye bağlanarak düzeltildi.
- **Belirsiz (JSON `tutarlilik_belirsiz`; toplam 4):** fen5 s.20 "Ay'ı 30 gün boyunca gözleyin" ↔ s.35 "yedi yılda" ve
  s.49 "27 gün 8 saatte" (tür belli değil; farklı nicelik; 3 çift); fen5 s.67 "10 N'lık" ↔ s.97 "20 N'dı" (dinamometre; s.97
  "Bu arada…" cümlesi varlığı yanlış olarak önceki cümlenin başındaki "Arkadaşımız"dan aldı).
  Filtreden önce 16 çiftin 10'u fen5'teydi: s.49 "365 gün 6 saat" ↔ s.50 "24 saatte" (bilerek yanlış D/Y maddesi) ve
  s.66-67-70 dinamometre soruları (filtreyle çıktı). Filtre aşırı kapsayabilir: yönergeden sonra sayfa sonuna kadar
  süren blokta anlatım da düşüyordu; blok sınırı sıkılaştırıldı (yukarıda).
- **Bilinen sınırlar:** (1) Zamir çözümleme kaba: önceki cümlenin ilk özel ismi alınır (yanlış isim gelebilir: "Arkadaşımız"), bağlaçla başlayan
  ya da öznesi hiç olmayan cümleler ("Ardından…") çözülmüyor; çoğul özne olmayan sıradan özneli cümleler ("Bir tur…") varlıksız. (2) Cümlede birden çok varlık varsa ("Dünya ve Ay, Güneş etrafındaki…") yalnızca en yakın
  (ölçüde en yakın iki) isim alınır. (3) Tür sözlüğü küçük (zaman ve uzunlukta 12 tür); tür bulunamazsa çift
  belirsiz olur. (4) Aynı varlığın farklı olayları yalnızca başlangıç/bitiş ayrımıyla ayrılıyor. (5) s.114
  "Çemberimsi anıtsal yapılar, MÖ 8000 civarında…" artık varlıksız kalıyor (doğrusu Göbeklitepe yapıları).
  (6) MS için referans yıl 2000 ("MS 1071" = 929 yıl önce, gerçek 954). (7) Yalnızca tek aday bulunduğundan
  kesinlik (precision) ve duyarlılık (recall) ölçülemez; hata yerleştirilmiş test seti (hafta 12) gerekir.

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
