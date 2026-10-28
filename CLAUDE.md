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
