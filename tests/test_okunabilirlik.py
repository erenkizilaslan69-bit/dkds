"""Okunabilirlik analizörü testleri: cümle ayırma, hece sayma ve elle hesaplanmış formül örnekleri."""
import math
import unittest
import unittest.mock

from dkds.analiz.okunabilirlik import (
    OLCUM_SURUMU,
    OkunabilirlikAnalizoru,
    atlama_nedeni,
    atesman_duzeyi,
    atesman_kademesi,
    atesman_puani,
    bezirci_yilmaz_duzeyi,
    bezirci_yilmaz_puani,
    bolme_noktasi,
    cumlelere_ayir,
    hece_say,
    kelimeleri_bul,
    cikarim_suphesi,
    metin_metrikleri,
    tekrar_eden_dizi,
)
from dkds.analiz.referans import Referans, SinifVerisi, referans_olustur
from dkds.models import Paragraf


class HeceVeKelimeTest(unittest.TestCase):
    def test_hece_sesli_harf_sayisidir(self):
        for kelime, beklenen in (("Ali", 2), ("topu", 2), ("kitaplar", 3), ("öğretmenler", 4),
                                 ("Okulumuzdaki", 6), ("ışık", 2), ("ÖĞRENCİ", 3), ("âlim", 2), ("TBMM", 0)):
            self.assertEqual(hece_say(kelime), beklenen, kelime)

    def test_kelimeler_harf_iceren_parcalardir(self):
        self.assertEqual(kelimeleri_bul("Dünya’nın 9.500 yıl önce, 3,5 km e-içerik MÖ 7500."),
                         ["Dünya’nın", "yıl", "önce", "km", "e-içerik", "MÖ"])


class CumleAyirmaTest(unittest.TestCase):
    def test_basit(self):
        self.assertEqual(cumlelere_ayir("Ay bir uydudur. Dünya’nın etrafında döner! Neden? Çünkü çekim var."),
                         ["Ay bir uydudur.", "Dünya’nın etrafında döner!", "Neden?", "Çünkü çekim var."])

    def test_kisaltmalar_cumleyi_bolmez(self):
        for metin in ("Dr. Ayşe kitabı okudu.", "Kalem, silgi vb. araçlar gerekir.",
                      "Örn. su, süt ve çay içecektir.", "Hz. İsa’nın doğduğu gündür.",
                      "Bkz. Çizelge 2 ve s. 36 incelenmelidir."):
            self.assertEqual(len(cumlelere_ayir(metin)), 1, metin)

    def test_basharf_ve_zincirler(self):
        self.assertEqual(len(cumlelere_ayir("Şahin, H. Konyar, E. ve Ergin, G. Anadolu Üniversitesi yayımladı.")), 1)
        self.assertEqual(len(cumlelere_ayir("Çatalhöyük M.Ö. 7500 yıllarında kurulmuştur.")), 1)

    def test_sira_sayisi_roma_rakami_ve_birim(self):
        for metin in ("Bu konu 36. sayfada anlatılmıştır.", "II. Dünya Savaşı 1945’te bitti.",
                      "Burdur’un 26 km. güneybatısında yer alır."):
            self.assertEqual(len(cumlelere_ayir(metin)), 1, metin)

    def test_ondalik_ve_binlik_sayilar(self):
        self.assertEqual(len(cumlelere_ayir("Sıcaklık 3,5 derece arttı. Yaklaşık 9.500 yıl önce kuruldu.")), 2)

    def test_kucuk_harfle_devam_eden_metin_bolunmez(self):
        self.assertEqual(len(cumlelere_ayir("Kalem, silgi vb. araçlar ve s. 36 incelenmelidir.")), 1)

    def test_sik_isaretleri_cumleye_dahil_edilmez(self):
        # fen5.pdf s.51: şık listesi "ç. Hem… d. Kendi… e. Güneş’in…" tek cümle sayılmamalı
        sonuc = cumlelere_ayir("ç. Hem dönme hem de dolanma hareketi yapar. d. Kendi etrafında döner. e. Güneş’in yönüdür.")
        self.assertEqual(sonuc, ["Hem dönme hem de dolanma hareketi yapar.", "Kendi etrafında döner.",
                                 "Güneş’in yönüdür."])
        self.assertEqual(cumlelere_ayir("Hangi özelliği ile ilgilidir? b. Ay’ın hareketleri nelerdir?"),
                         ["Hangi özelliği ile ilgilidir?", "Ay’ın hareketleri nelerdir?"])
        self.assertEqual(len(kelimeleri_bul(" ".join(cumlelere_ayir("A) Kültür kolaydır. B) Bilim zordur."))
                                                    )), 4)

    def test_buyuk_harfli_ad_basharfi_madde_isareti_degildir(self):
        self.assertEqual(len(cumlelere_ayir("Şahin, H. Konyar, E. ve Ergin, G. yazdı.")), 1)

    def test_cumle_sonunda_kapanis_tirnagi(self):
        self.assertEqual(cumlelere_ayir("“Bu bir deneydir.” Sonuçları yazınız."),
                         ["“Bu bir deneydir.”", "Sonuçları yazınız."])

    def test_yilla_biten_cumle_bolunur(self):
        # "2023." bir sıra sayısı gibi görünür ama ardından büyük harf var
        self.assertEqual(len(cumlelere_ayir("Deprem 2023. Ay’ın yüzeyi çok farklıdır.")), 2)

    def test_kelime_icermeyen_parca_atilir(self):
        # madde numarası ("1.") ayrı bir parça olur, kelime içermediği için atılır
        self.assertEqual(cumlelere_ayir("1. Ay bir uydudur."), ["Ay bir uydudur."])
        self.assertEqual(cumlelere_ayir("... 12. 34."), [])

    def test_bos_metin(self):
        self.assertEqual(cumlelere_ayir(""), [])


class FormulTest(unittest.TestCase):
    """Elle hesaplanmış örnekler.

    Cümle A: "Ali topu attı."  -> 3 kelime, her biri 2 heceli (Ali, topu, attı) = 6 hece.
    Cümle B: "Okulumuzdaki öğretmenler çocuklara kitaplar dağıttı."
        Okulumuzdaki = 6 hece (H6), öğretmenler = 4 (H4), çocuklara = 4 (H4),
        kitaplar = 3 (H3), dağıttı = 3 (H3)  -> 5 kelime, 20 hece.
    """

    A = "Ali topu attı."
    B = "Okulumuzdaki öğretmenler çocuklara kitaplar dağıttı."

    def test_sayimlar(self):
        m = metin_metrikleri(self.B)
        self.assertEqual((m.kelime, m.cumle, m.hece, m.h3, m.h4, m.h5, m.h6), (5, 1, 20, 2, 2, 0, 1))

    def test_atesman_tek_cumle(self):
        # hece/kelime = 6/3 = 2; kelime/cümle = 3
        # 198,825 - 40,175 × 2 - 2,610 × 3 = 198,825 - 80,35 - 7,83 = 110,645
        self.assertAlmostEqual(metin_metrikleri(self.A).atesman, 110.645, places=6)

    def test_atesman_ikinci_ornek(self):
        # hece/kelime = 20/5 = 4; kelime/cümle = 5
        # 198,825 - 160,7 - 13,05 = 25,075
        self.assertAlmostEqual(metin_metrikleri(self.B).atesman, 25.075, places=6)

    def test_atesman_iki_cumle(self):
        # 8 kelime, 26 hece, 2 cümle: hece/kelime = 3,25; kelime/cümle = 4
        # 198,825 - 40,175 × 3,25 - 2,610 × 4 = 198,825 - 130,56875 - 10,44 = 57,81625
        m = metin_metrikleri(self.A + " " + self.B)
        self.assertEqual((m.kelime, m.cumle, m.hece), (8, 2, 26))
        self.assertAlmostEqual(m.atesman, 57.81625, places=6)

    def test_bezirci_yilmaz_tek_cumle(self):
        # OKS = 5; H3 = 2, H4 = 2, H5 = 0, H6 = 1
        # toplam = 2 × 0,84 + 2 × 1,5 + 0 + 1 × 26,25 = 1,68 + 3 + 26,25 = 30,93
        # YOD = √(5 × 30,93) = √154,65
        self.assertAlmostEqual(metin_metrikleri(self.B).bezirci_yilmaz, math.sqrt(154.65), places=9)
        self.assertAlmostEqual(math.sqrt(154.65), 12.4358, places=4)

    def test_bezirci_yilmaz_iki_cumle_ortalamalar(self):
        # 8 kelime / 2 cümle: OKS = 4; H3 = 2/2 = 1, H4 = 2/2 = 1, H5 = 0, H6 = 1/2 = 0,5
        # toplam = 0,84 + 1,5 + 13,125 = 15,465; YOD = √(4 × 15,465) = √61,86 = 7,8651
        m = metin_metrikleri(self.A + " " + self.B)
        self.assertAlmostEqual(m.bezirci_yilmaz, math.sqrt(61.86), places=9)
        self.assertAlmostEqual(m.bezirci_yilmaz, 7.8651, places=4)

    def test_bezirci_yilmaz_makaledeki_ornekler(self):
        # Bezirci-Yılmaz (2010) Çizelge 8-9: sistematik toplam 7, 10 ve 14 için YOD değerleri
        # OKS 3,03 -> 4,61 / 5,50 / 6,51; OKS 8,3 -> 7,62 / 9,11 / 10,78; OKS 18,82 -> 11,48 / 13,72 / 16,23
        for oks, beklenenler in ((3.03, (4.61, 5.50, 6.51)), (8.3, (7.62, 9.11, 10.78)),
                                 (18.82, (11.48, 13.72, 16.23))):
            for toplam, beklenen in zip((7, 10, 14), beklenenler):
                # toplamı tek terimde (H3 × 0,84 = toplam) vererek formülün karekökünü sınar
                self.assertAlmostEqual(bezirci_yilmaz_puani(oks, toplam / 0.84, 0, 0, 0), beklenen, places=2)

    def test_karekok_tum_carpimin_uzerindedir(self):
        # yalnızca OKS'nin karekökü alınsaydı sonuç √3,03 × 7 = 12,18 olurdu (makale: 4,61)
        self.assertNotAlmostEqual(bezirci_yilmaz_puani(3.03, 7 / 0.84, 0, 0, 0), math.sqrt(3.03) * 7, places=1)

    def test_bos_metin_icin_hazir_degil(self):
        self.assertFalse(metin_metrikleri("").hazir)

    def test_metrikler_toplanir(self):
        toplam = metin_metrikleri(self.A) + metin_metrikleri(self.B)
        self.assertEqual(toplam, metin_metrikleri(self.A + " " + self.B))


class DuzeyTest(unittest.TestCase):
    def test_atesman_tablosu(self):
        for puan, beklenen in ((110.6, "4. sınıf ve altı"), (90, "4. sınıf ve altı"), (89.9, "5-6. sınıf"),
                               (80, "5-6. sınıf"), (79.99, "7-8. sınıf"), (70, "7-8. sınıf"),
                               (60, "9-10. sınıf"), (59.9, "11-12. sınıf"), (50, "11-12. sınıf"),
                               (45, "lisans"), (40, "lisans"), (39.9, "lisans üstü"), (-5, "lisans üstü")):
            self.assertEqual(atesman_duzeyi(puan), beklenen, puan)

    def test_atesman_kademeleri(self):
        self.assertEqual([atesman_kademesi(p) for p in (95, 85, 75, 65, 55, 45, 20)], [0, 1, 2, 3, 4, 5, 6])

    def test_bezirci_yilmaz_duzeyi(self):
        # makale: Yeşil Yol 7,34 -> 7-8. sınıf
        self.assertEqual(bezirci_yilmaz_duzeyi(7.34), "7-8. sınıf")
        self.assertEqual(bezirci_yilmaz_duzeyi(9.4), "9-10. sınıf")
        self.assertEqual(bezirci_yilmaz_duzeyi(13.7), "lisans")
        self.assertEqual(bezirci_yilmaz_duzeyi(16.23), "akademik")


def paragraf(metin, sayfa=1, no=1, tur="govde"):
    return Paragraf(sayfa=sayfa, paragraf=no, metin=metin, konum=(50.0, 100.0 * no, 500.0, 100.0 * no + 40), tur=tur)


# Metinler 40 kelimelik alt sınırı geçecek uzunlukta; değerler elle doğrulandı.
# Kolay: 42 kelime, 15 cümle, 81 hece -> Ateşman 114,04 (4. sınıf ve altı)
KOLAY = ("Ali topu attı. Ayşe topu tuttu. Ali koştu. Ayşe güldü. Top suya düştü. Hep birlikte eve gittik. "
         "Hava çok güzel. Kuş öttü. Biz okula gittik. Dersler başladı. Ali çok sevindi. Ayşe de sevindi. "
         "Gün güzel geçti. Akşam eve döndük. Hava çok güzeldi.")
# Zor: 44 kelime, 10 cümle, 198 hece -> Ateşman 6,55 (lisans üstü; hece/kelime 4,5 gerçek metinde bile nadir)
#   198,825 - 40,175 × (198/44) - 2,610 × 4,4 = 198,825 - 180,79 - 11,48
ZOR = ("Okulumuzdaki öğretmenlerin çocuklarımıza kazandırmaya çalıştıkları davranışların sürekliliğini "
       "sağlayabilmek gerekmektedir. Velilerin eğitim süreçlerine katılımlarını değerlendirebilecek "
       "göstergeleri belirlemeleri, okul yönetimlerinin velilerle düzenli görüşmeler gerçekleştirmesi "
       "gerekmektedir. Öğrencilerin evde yaptıkları çalışmaların kontrol edilmesi sağlanmalıdır. "
       "Sorumluluk paylaşılmalıdır. Aileler bilgilendirilmelidir. Süreç izlenmelidir. Bunlar zorunludur. "
       "Notlar tutulmalıdır. Rapor yazılmalıdır. Ödev verilmelidir.")
# Sınırdaki iki metin (5. sınıf kitabı = 5-6. sınıf düzeyi): A 1 kademe, B 2 kademe üstünde.
# Her biri iki kopyadan oluşur; kopyalarda aynı hece/kelime sayısındaki sözcükler değiştirilmiştir
# (aynı 10 kelimelik dizi tekrar ederse birim çıkarım şüphesi sayılır ve ölçüme girmez).
ORTA_A = ("Ay, Dünya’nın tek doğal uydusudur ve onun etrafında dolanır. "
          "Güneş, kendi etrafında dönen büyük bir yıldızdır. "
          "Gezegenler, Güneş’in çevresinde dolanarak hareket eder. "
          "Ay, Dünya’nın bir doğal uydusudur ve bunun etrafında dolanır. "
          "Güneş, bütün etrafında yanan küçük bir yıldızdır. "
          "Gezegenler, Dünya’nın çevresinde dolanarak devinim eder.")  # Ateşman 75,6 (7-8. sınıf)
ORTA_B = ("Ay, Dünya’nın etrafında dolanan doğal bir uydudur. "
          "Güneş, gezegenlerimize ışık ve ısı veren büyük bir yıldızdır. "
          "Gezegenler, Güneş’in çevresinde belirli yörüngelerde hareket eder. "
          "Ay, Dünya’nın çevresinde dolanan doğal bir uydudur. "
          "Yıldız, gezegenlerimize ısı ve ışık veren küçük bir yıldızdır. "
          "Gezegenler, Dünya’nın çevresinde belirli yörüngelerde devinim eder.")  # Ateşman 68,8 (9-10. sınıf)


class AtlamaNedeniTest(unittest.TestCase):
    def test_cumle_isaretsiz_paragraf(self):
        # fen5.pdf s.58 kavram listesi, haber başlığı, tablo hücresi
        self.assertEqual(atlama_nedeni("kuvvet kuvvet birimi dinamometre kütle ağırlık sürtünme"), "cumle_isaretsiz")
        self.assertEqual(atlama_nedeni("Valizlerin altına tekerlek takılması"), "cumle_isaretsiz")

    def test_sayidaki_nokta_cumle_sonu_degildir(self):
        # sosyalbilgiler5.pdf s.128: haber başlığındaki "4.000" noktası başlığı cümle yapmaz
        self.assertEqual(atlama_nedeni("Tavşanlı’da 4.000 yıllık nohut ve ekmek kalıntıları gün yüzüne çıkarıldı"),
                         "cumle_isaretsiz")
        self.assertEqual(atlama_nedeni("Bilgi için meb.gov.tr adresine ortak metin sayfasına bakınız"), "cumle_isaretsiz")

    def test_cumle_sonu_tirnak_ve_parantezle_biter(self):
        self.assertIsNone(atlama_nedeni("Bakan “Burada çalışıyoruz.” dedi (Genel ağ). Haberler bitti."))
        self.assertIsNone(atlama_nedeni("Soruyu yazınız ve cevaplayınız."))

    def test_cumle_isaretli_paragraf_uygun(self):
        self.assertIsNone(atlama_nedeni(KOLAY))
        self.assertIsNone(atlama_nedeni("Su kaynayınca buhar olur."))

    def test_sozluk(self):
        # fen5.pdf s.144
        metin = ("A-B-C-Ç abeslang: Hekimlerin boğazı görebilmek için dili bastırdıkları araç; dilbasar. "
                 "âlim: İlim sahibi kişi. astronomi: Gök cisimlerini inceleyen bilim. ataş: Kâğıtları tutturan araç.")
        self.assertEqual(atlama_nedeni(metin), "sozluk")

    def test_form_kunyesi(self):
        # sosyalbilgiler5.pdf s.56 ve fen3.pdf s.32 (biyoloji9.pdf s.89'daki rapor başlığı noktasız
        # olduğu için zaten "cumle_isaretsiz" ile eleniyor)
        for metin in ("ETKİNLİK Adı : Yaşadığım İlin Göreceli Konumu Amacı : Konumunu açıklayabilme Beceri : "
                      "Mekânsal düşünme Süre : 2 ders saati Malzemeler: Karton, kalem.",
                      "Süre : İki ders saati Konu : Yaşam döngüsü Görev : Bir bitki veya hayvanın yaşam döngüsünü anlatınız."):
            self.assertEqual(atlama_nedeni(metin), "form", metin)
        self.assertIsNotNone(atlama_nedeni("Kurum : Kimlik No : Hasta Adı : Cinsiyeti : Doğum Tarihi :"))

    def test_az_alanli_veya_diyalog_form_degil(self):
        self.assertIsNone(atlama_nedeni("Gerekli malzeme : kalem. Süre : 2 saat. Çalışmaya başlayınız."))  # 2 alan
        self.assertIsNone(atlama_nedeni("Sena: Önce kaynakları belirleyelim. Samet: Haklısın. Sena: Başlayalım."))

    def test_iki_nokta_ust_uste_olan_normal_cumle_sozluk_degil(self):
        self.assertIsNone(atlama_nedeni("Gerekli malzemeler: kalem, silgi ve defter. Sonra çalışmaya başlayın."))


class BirimlerTest(unittest.TestCase):
    def setUp(self):
        self.analizor = OkunabilirlikAnalizoru(sinif=5)

    def birimler(self, paragraflar):
        return self.analizor.birimleri_olustur(paragraflar)

    def test_yalnizca_govde_degerlendirilir(self):
        birimler, _ = self.birimler([paragraf(KOLAY, no=1, tur="soru"), paragraf(KOLAY, no=2, tur="liste"),
                                     paragraf(KOLAY, no=3, tur="etiket"), paragraf(KOLAY, no=4, tur="baslik")])
        self.assertEqual(birimler, [])

    def test_uzun_paragraf_tek_birim(self):
        birimler, atlanan = self.birimler([paragraf(ZOR, no=1), paragraf(KOLAY, no=2)])
        self.assertEqual([b.paragraflar for b in birimler], [[1], [2]])
        self.assertEqual(sum(atlanan.values()), 0)

    def test_kisa_paragraflar_komsularla_birlestirilir(self):
        kisa = "Ali topu attı. Ayşe topu tuttu."  # 6 kelime
        birimler, _ = self.birimler([paragraf(kisa, no=n) for n in range(1, 9)])  # 48 kelime
        # ilk 7 paragraf 42 kelime, sonuncu kalan parça öncekine eklenir
        self.assertEqual([b.paragraflar for b in birimler], [[1, 2, 3, 4, 5, 6, 7, 8]])
        self.assertEqual(birimler[0].metrikler.kelime, 48)
        self.assertEqual(birimler[0].konum, (50.0, 100.0, 500.0, 840.0))  # paragraf konumlarının birleşimi

    def test_sayfada_yeterli_metin_yoksa_atlanir(self):
        birimler, atlanan = self.birimler([paragraf("Ali topu attı.", no=1), paragraf("Ayşe güldü.", no=2)])
        self.assertEqual((birimler, dict(atlanan)), ([], {"kisa_sayfa": 2}))

    def test_birlestirme_sayfa_sinirini_asmaz(self):
        kisa = "Ali topu attı. Ayşe topu tuttu."
        birimler, _ = self.birimler([paragraf(kisa, sayfa=1, no=1), paragraf(ZOR, sayfa=2, no=1)])
        self.assertEqual([(b.sayfa, b.paragraflar) for b in birimler], [(2, [1])])

    def test_isaretsiz_paragraf_birlesmeden_atlanir(self):
        # başlık gibi noktasız parça komşuyla birleşip dev cümle oluşturmamalı
        baslik = "Diyarbakır’da Kral Yolu rotaları tanıtıldı"
        birimler, atlanan = self.birimler([paragraf(baslik, no=1), paragraf(KOLAY, no=2)])
        self.assertEqual([b.paragraflar for b in birimler], [[2]])
        self.assertEqual(dict(atlanan), {"cumle_isaretsiz": 1})
        self.assertEqual(birimler[0].metrikler.cumle, 15)  # başlık cümle sayısına katılmadı

    def test_gecersiz_sinif(self):
        with self.assertRaises(ValueError):
            OkunabilirlikAnalizoru(sinif=0)


def veri_ref(en_dusuk, en_yuksek, kitap):
    """21 birimlik yapay referans verisi: Ateşman puanları en_dusuk..en_yuksek arasında eşit aralıklı
    (%10 sınırı = en_dusuk + 0,1 × aralık, ortanca ortada); Bezirci-Yılmaz = 200 - Ateşman."""
    atesman = [en_dusuk + (en_yuksek - en_dusuk) * i / 20 for i in range(21)]
    return SinifVerisi(atesman=atesman, bezirci_yilmaz=[200 - a for a in atesman], kitaplar=[kitap])


# 5. sınıf: Ateşman 70-110 (%10 = 74, ortanca 90, %90 = 106); Bezirci-Yılmaz ortanca 110, %90 = 126
# 7. sınıf: Ateşman 30-70  (%10 = 34, ortanca 50, %90 = 66)
# 6. sınıf: ikisinin ara değeri (%10 = 54, ortanca 70, %90 = 86)
REFERANS = referans_olustur({5: veri_ref(70, 110, "ref5.pdf"), 7: veri_ref(30, 70, "ref7.pdf")},
                            olcum_surumu=OLCUM_SURUMU)


class AnalizTest(unittest.TestCase):
    def sonuc(self, paragraflar, sinif=5, referans=REFERANS):
        return OkunabilirlikAnalizoru(sinif=sinif, referans=referans).incele(paragraflar)

    def test_kolay_metin_bulgu_uretmez_zor_metin_uretir(self):
        s = self.sonuc([paragraf(KOLAY, no=1), paragraf(ZOR, no=2)])
        self.assertEqual([(b.paragraf, b.kriter, b.tur) for b in s.bulgular], [(2, "okunabilirlik", "sinif_ustu")])

    def test_bulgu_alanlari(self):
        b = self.sonuc([paragraf(KOLAY, no=1), paragraf(ZOR, no=2)]).bulgular[0]
        self.assertEqual((b.sayfa, b.konum), (1, (50.0, 200.0, 500.0, 240.0)))
        # metin 240 karakteri aştığı için ilk 40 kelime + "…" gösterilir
        self.assertTrue(b.sorunlu_metin.endswith(" …"))
        self.assertTrue(ZOR.startswith(b.sorunlu_metin[:-2]))
        self.assertEqual(b.guven, 0.7)  # eşiğin ortancaya olan mesafesinden çok daha aşağıda: üst sınır
        # açıklama referansa dayanır; Ateşman tablosu yalnızca bilgidir
        for parca in (
            "Bu paragraf, 5. sınıf kitaplarındaki paragrafların %90'ından daha zor (Ateşman puanı 6,6; "
            "5. sınıf referansında %10 sınırı 74,0, ortanca 90,0)",
            "referanstaki hiçbir sınıfın tipik aralığına girmiyor: 7. sınıf kitaplarındaki paragrafların da "
            "%90'ından daha zor",
            "Bezirci-Yılmaz puanı 12,1 (lisans); 5. sınıf referansının ortancası 110,0, %90 sınırı 126,0",
            "Ortalama cümle uzunluğu 4,4 kelime (kitap ortalaması 3,4), kelime başına 4,50 hece",
            "Ateşman tablosuna göre lisans üstü düzeyi (yalnızca bilgi)",
        ):
            self.assertIn(parca, b.aciklama)
        self.assertNotIn("kademe", b.aciklama)  # eski kademe kuralının dili kalmadı
        self.assertIn("En uzun cümle 14 kelime", b.oneri)

    def test_en_uzun_kelimeler_hece_sirasiyla(self):
        b = self.sonuc([paragraf(KOLAY, no=1), paragraf(ZOR, no=2)]).bulgular[0]
        self.assertIn("En uzun kelimeler: bilgilendirilmelidir (8 hece), değerlendirebilecek (8 hece), "
                      "gerçekleştirmesi (6 hece), paylaşılmalıdır (6 hece).", b.aciklama)

    def test_oneri_cumleyi_virgulden_boler(self):
        b = self.sonuc([paragraf(ZOR)]).bulgular[0]
        self.assertIn("«… eğitim süreçlerine katılımlarını değerlendirebilecek göstergeleri belirlemeleri.»", b.oneri)
        self.assertIn("«Okul yönetimlerinin velilerle düzenli görüşmeler gerçekleştirmesi …»", b.oneri)

    def test_esik_referansin_yuzde_10_dilimidir(self):
        # ORTA_A (Ateşman 75,6) %10 sınırının (74) üstünde: bulgu yok; ORTA_B (68,8) altında: bulgu
        self.assertEqual(self.sonuc([paragraf(ORTA_A)]).bulgular, [])
        b = self.sonuc([paragraf(ORTA_B)]).bulgular
        self.assertEqual(len(b), 1)
        # 68,8 hiçbir sınıfın %10 sınırının altında değil: 6. sınıf aralığında (54-86), ortancası (70) en yakın
        self.assertIn("6. sınıf kitaplarının tipik düzeyinde (o sınıfın paragraflarının %10-%90 aralığı "
                      "54,0-86,0 içinde)", b[0].aciklama)
        # güven: eşiğin altındaki mesafe / (ortanca - eşik) = (74 - 68,77) / 16
        self.assertAlmostEqual(b[0].guven, 0.4 + 0.3 * (74 - 68.77) / 16, places=2)

    def test_her_sinif_kendi_referansini_kullanir(self):
        # aynı ORTA_B paragrafı 6. sınıfta (%10 sınırı 54) ve 7. sınıfta (34) bulgu değildir
        self.assertEqual(self.sonuc([paragraf(ORTA_B)], sinif=6).bulgular, [])
        self.assertEqual(self.sonuc([paragraf(ORTA_B)], sinif=7).bulgular, [])
        b = self.sonuc([paragraf(ZOR)], sinif=7).bulgular
        self.assertEqual(len(b), 1)
        self.assertIn("7. sınıf referansında %10 sınırı 34,0, ortanca 50,0", b[0].aciklama)

    def test_ara_sinif_referansi_ara_degerdir(self):
        s = self.sonuc([paragraf(KOLAY, no=1), paragraf(ZOR, no=2)], sinif=6)
        r = s.ozet["referans"]
        self.assertEqual((r["yontem"], r["sinif"], r["ara_deger"], r["kaynak_siniflar"]),
                         ("sinif_referansi", 6, True, [5, 7]))
        self.assertAlmostEqual(r["p10"], 54.0)
        self.assertAlmostEqual(r["ortanca"], 70.0)

    def test_referansi_olmayan_sinifta_kitap_ici_esik(self):
        # referans yalnızca 5-7. sınıfları kapsar; 3. sınıf kitabı için kitabın kendi %10 dilimi kullanılır
        s = self.sonuc([paragraf(KOLAY, no=1), paragraf(ZOR, no=2)], sinif=3)
        self.assertEqual([b.paragraf for b in s.bulgular], [2])
        aciklama = s.bulgular[0].aciklama
        self.assertIn("Bu paragraf, bu kitaptaki paragrafların %90'ından daha zor", aciklama)
        self.assertIn("3. sınıf için referans tablosu yok (referans 5-7. sınıf kitaplarını kapsıyor); "
                      "bu yüzden kitabın kendi dağılımı kullanıldı.", aciklama)
        self.assertNotIn("Bezirci-Yılmaz puanı 122,7 (akademik);", aciklama)  # referans karşılaştırması yok
        self.assertEqual(s.ozet["referans"]["yontem"], "kitap_ici")
        # iki birimin puanları 6,55 ve 114,04: kitabın %10 sınırı 6,55 + 107,48 × 0,1 = 17,30
        self.assertAlmostEqual(s.ozet["referans"]["p10"], 17.30, places=1)

    def test_referans_hic_yoksa_kitap_ici(self):
        s = self.sonuc([paragraf(KOLAY, no=1), paragraf(ZOR, no=2)], referans=Referans())
        self.assertEqual([b.paragraf for b in s.bulgular], [2])
        self.assertIn("referans tablosu bulunamadı", s.bulgular[0].aciklama)

    def test_kitap_ici_tek_birimde_bulgu_olmaz(self):
        # tek birimin puanı kendi %10 sınırına eşittir: "altında" değil
        self.assertEqual(self.sonuc([paragraf(ZOR)], sinif=3).bulgular, [])

    def test_varsayilan_referans_depodaki_dosyadan_yuklenir(self):
        a = OkunabilirlikAnalizoru(5)
        self.assertEqual(a.referans.sinif(5).kitaplar, ["fen5.pdf", "sosyalbilgiler5.pdf"])
        self.assertEqual(a.referans.kapsam, (3, 9))

    def test_eski_olcum_surumlu_referans_uyari_verir(self):
        with unittest.mock.patch("dkds.analiz.okunabilirlik.referans_yukle", return_value=Referans(olcum_surumu=0)):
            with self.assertWarnsRegex(UserWarning, "ölçüm sürümü 0"):
                OkunabilirlikAnalizoru(5)

    def test_referans_dosyasi_yoksa_bos_referans(self):
        with unittest.mock.patch("dkds.analiz.okunabilirlik.referans_yukle", side_effect=FileNotFoundError):
            a = OkunabilirlikAnalizoru(5)
        self.assertIsNone(a.referans.kapsam)

    def test_ozet(self):
        ozet = self.sonuc([paragraf(KOLAY, no=1), paragraf(ZOR, no=2)]).ozet
        self.assertEqual((ozet["sinif"], ozet["birim_sayisi"], ozet["kelime"], ozet["cumle"]), (5, 2, 86, 25))
        # toplam: 86 kelime, 25 cümle -> kelime/cümle = 3,44
        self.assertAlmostEqual(ozet["ortalama_cumle_uzunlugu"], 86 / 25)
        self.assertIn("puan", ozet["atesman"])
        self.assertIn("duzey", ozet["bezirci_yilmaz"])
        # en zor paragraf listesi Ateşman puanı düşükten yükseğe sıralıdır
        en_zor = ozet["en_zor_paragraflar"]
        self.assertEqual([p["paragraflar"] for p in en_zor], [[2], [1]])
        self.assertLess(en_zor[0]["atesman"], en_zor[1]["atesman"])

    def test_ozet_referans(self):
        ozet = self.sonuc([paragraf(KOLAY, no=1), paragraf(ZOR, no=2)]).ozet
        r = ozet["referans"]
        self.assertEqual((r["yontem"], r["sinif"], r["ara_deger"], r["kitaplar"], r["birim_sayisi"]),
                         ("sinif_referansi", 5, False, ["ref5.pdf"], 21))
        self.assertEqual((r["p10"], r["ortanca"]), (74.0, 90.0))
        # kitabın ortanca birim puanı 60,30; referans ortancası 90
        self.assertAlmostEqual(r["medyan_farki"], (114.037 + 6.553) / 2 - 90, places=2)

    def test_ozet_isaretlenen_oran_ve_dagilim(self):
        ozet = self.sonuc([paragraf(KOLAY, no=1), paragraf(ZOR, no=2)]).ozet
        self.assertEqual((ozet["isaretlenen_birim"], ozet["isaretlenen_oran"]), (1, 0.5))
        d = ozet["atesman_dagilimi"]
        # iki birimin puanı 114,037 ve 6,553 (elle doğrulandı): ortalama 60,30, medyan aynı
        self.assertAlmostEqual(d["ortalama"], (114.037 + 6.553) / 2, places=2)
        self.assertAlmostEqual(d["medyan"], d["ortalama"], places=6)
        self.assertAlmostEqual(d["std"], (114.037 - 6.553) / 2, places=2)
        # doğrusal ara değerli yüzdelik: 6,553 + 107,484 × 0,1 ve × 0,9
        self.assertAlmostEqual(d["p10"], 17.30, places=1)
        self.assertAlmostEqual(d["p90"], 103.29, places=1)

    def test_ozet_en_zor_paragraf_sayisi_sinirlidir(self):
        paragraflar = [paragraf(ZOR + f" Ek{n}.", no=n) for n in range(1, 16)]
        ozet = self.sonuc(paragraflar).ozet
        self.assertEqual(len(ozet["en_zor_paragraflar"]), 10)

    def test_bos_girdi(self):
        s = self.sonuc([])
        self.assertEqual((s.bulgular, s.ozet["birim_sayisi"]), ([], 0))
        self.assertNotIn("atesman", s.ozet)

    def test_birlestirilen_paragraflar_aciklamada_belirtilir(self):
        zor_kisalar = [  # 7 kelimelik, birbirinden farklı zor cümleler
            "Okulumuzdaki öğretmenlerin çocuklarımıza kazandırmaya çalıştıkları davranışların sürekliliği.",
            "Velilerin eğitim süreçlerine katılımlarını değerlendirebilecek göstergeleri belirlemeleri.",
            "Yönetimlerin düzenli görüşmeler gerçekleştirmesi gerekmektedir sürekli olarak.",
            "Öğrencilerin evde yaptıkları çalışmaların kontrol edilmesi sağlanmalıdır.",
            "Aileler çocukları ile birlikte kitap okumalıdır elbette.",
            "Biz her gün okula gidip ders çalışırız.",
            "Ali ile Ayşe bugün parkta top oynadı.",
        ]
        s = self.sonuc([paragraf(m, no=n) for n, m in enumerate(zor_kisalar, start=1)])  # 6. paragrafta 42 kelimeye ulaşılır
        self.assertEqual(len(s.bulgular), 1)
        self.assertIn("7 kısa gövde paragrafı birleştirilerek", s.bulgular[0].aciklama)  # 7. kalan parça eklenir
        self.assertIn("paragraf 1–7", s.bulgular[0].aciklama)


# Tek 44 kelimelik cümle: Ateşman -82,19 (gerçek bir kitapta bu, çıkarım hatasının işaretidir)
UZUN_CUMLE = ("Okulumuzdaki öğretmenlerin çocuklarımıza kazandırmaya çalıştıkları davranışların sürekliliğini "
              "sağlayabilmek amacıyla öğrencilerimizin ailelerinin eğitim süreçlerine katılımlarını "
              "değerlendirebilecek göstergeleri belirlemeleri, bu doğrultuda okul yönetimlerinin velilerle "
              "düzenli görüşmeler gerçekleştirmesi, ayrıca öğrencilerin evde yaptıkları çalışmaların düzenli "
              "kontrol edilmesi ve sınıf öğretmenlerinin bu sürecin her aşamasında aktif rol almaları "
              "gerekmektedir.")


class TekrarEdenDiziTest(unittest.TestCase):
    def test_ornusmeden_tekrar_eden_dizi_bulunur(self):
        dizi = "bu temada yazılarınızı zenginleştirecek biçimde söz varlığınızı kullanmaya yönelik öğrendiklerinizden"
        metin = f"{dizi} ilk kez. Sonra başka şeyler anlatılır. {dizi.capitalize()} ikinci kez."
        self.assertEqual(tekrar_eden_dizi(metin), dizi)

    def test_buyuk_kucuk_harf_ve_noktalama_ayirt_edilmez(self):
        self.assertIsNotNone(tekrar_eden_dizi("Ali topu attı, Ayşe topu tuttu, Veli de koştu sonra. "
                                              "ALİ topu attı; ayşe TOPU tuttu; VELİ de koştu SONRA."))

    def test_kisa_ortak_dizi_tekrar_sayilmaz(self):
        # 5 kelimelik ortak dizi (eşik 10): "Güneş'in çevresinde dolanır" gibi doğal tekrarlar
        self.assertIsNone(tekrar_eden_dizi("Gezegenler Güneş’in çevresinde dolanır ve döner. "
                                           "Dünya Güneş’in çevresinde dolanır ve döner."))

    def test_ust_uste_binen_tekrar_sayilmaz(self):
        self.assertIsNone(tekrar_eden_dizi("ve ve ve ve ve ve ve ve"))  # örtüşen pencereler aynı dizi değil

    def test_cikarim_suphesi_nedenleri(self):
        self.assertEqual(cikarim_suphesi("herhangi bir metin", -0.1), "negatif_puan")
        self.assertEqual(cikarim_suphesi("a b c d e f g h i j a b c d e f g h i j", 50.0), "tekrar")
        self.assertIsNone(cikarim_suphesi("kısa bir metin", 0.0))  # 0 tam sınırda: şüphe yok


class CikarimSuphesiTest(unittest.TestCase):
    """Ateşman < 0 ya da tekrarlayan dizi: okunabilirlik bulgusu değil, olası metin çıkarma sorunu."""

    def sonuc(self, paragraflar, sinif=5):
        return OkunabilirlikAnalizoru(sinif=sinif, referans=REFERANS).incele(paragraflar)

    def test_negatif_puanli_birim_cikarim_sorunu_olarak_raporlanir(self):
        s = self.sonuc([paragraf(KOLAY, no=1), paragraf(UZUN_CUMLE, no=2)])
        self.assertEqual([(b.paragraf, b.kriter, b.tur) for b in s.bulgular],
                         [(2, "okunabilirlik", "cikarim_sorunu")])
        b = s.bulgular[0]
        self.assertEqual(b.guven, 0.3)
        self.assertIn("Olası metin çıkarma sorunu, okunabilirlik bulgusu değil.", b.aciklama)
        self.assertIn("Ateşman puanı -82,2 (0'ın altında)", b.aciklama)
        self.assertNotIn("sinif_ustu", {x.tur for x in s.bulgular})

    def test_cikarim_suphesi_olcume_ve_orana_girmez(self):
        s = self.sonuc([paragraf(KOLAY, no=1), paragraf(UZUN_CUMLE, no=2), paragraf(ZOR, no=3)])
        o = s.ozet
        self.assertEqual((o["birim_sayisi"], o["cikarim_suphesi_birim"]), (2, 1))
        self.assertEqual((o["isaretlenen_birim"], o["isaretlenen_oran"]), (1, 0.5))  # yalnızca ZOR sayılır
        self.assertEqual([p["paragraflar"] for p in o["en_zor_paragraflar"]], [[3], [1]])
        # kitap dağılımı ve toplam metrikler şüpheli birimi içermez: 42 + 44 kelime
        self.assertEqual(o["kelime"], 86)
        self.assertAlmostEqual(o["atesman_dagilimi"]["medyan"], (114.037 + 6.553) / 2, places=2)

    def test_tekrarlayan_dizi_cikarim_sorunu(self):
        # aynı metnin iki kez gelmesi (kopya katman); puan pozitif olsa bile ölçüm dışı
        s = self.sonuc([paragraf(ZOR + " " + ZOR)])
        self.assertEqual([b.tur for b in s.bulgular], ["cikarim_sorunu"])
        self.assertIn("aynı kelime dizisi iki kez geçiyor", s.bulgular[0].aciklama)
        self.assertEqual((s.ozet["birim_sayisi"], s.ozet["cikarim_suphesi_birim"]), (0, 1))

    def test_suphe_birimi_degeri_ne_olursa_olsun_raporlanir(self):
        # kolay ama kopyalanmış metin de çıkarım sorunudur (puanı eşiğin üstünde olsa da)
        s = self.sonuc([paragraf(KOLAY + " " + KOLAY)])
        self.assertEqual([b.tur for b in s.bulgular], ["cikarim_sorunu"])

    def test_olculebilir_birimler_aynen_degerlendirilir(self):
        s = self.sonuc([paragraf(KOLAY, no=1), paragraf(ZOR, no=2)])
        self.assertEqual([b.tur for b in s.bulgular], ["sinif_ustu"])
        self.assertEqual(s.ozet["cikarim_suphesi_birim"], 0)

    def test_birim_alanlari(self):
        birimler, _ = OkunabilirlikAnalizoru(5, referans=REFERANS).birimleri_olustur(
            [paragraf(UZUN_CUMLE, no=1), paragraf(KOLAY, no=2)])
        self.assertEqual([(b.suphe, b.olculebilir) for b in birimler], [("negatif_puan", False), (None, True)])


class BolmeNoktasiTest(unittest.TestCase):
    def test_virgulden_bolunur(self):
        cumle = ("Güneş sisteminin merkezindeki yıldız çok büyük bir enerji yayar, bu enerji sayesinde "
                 "gezegenler aydınlanır ve ısınır.")
        ilk, ikinci = bolme_noktasi(cumle)
        self.assertTrue(ilk.endswith("yayar."))
        self.assertTrue(ikinci.startswith("Bu enerji"))

    def test_baglactan_once_bolunur(self):
        cumle = "Öğrenciler deneyi dikkatle ve eksiksiz tamamladılar ancak sonuçları defterlerine yazmayı unuttular."
        ilk, ikinci = bolme_noktasi(cumle)
        self.assertEqual((ilk, ikinci), ("Öğrenciler deneyi dikkatle ve eksiksiz tamamladılar.",
                                         "Ancak sonuçları defterlerine yazmayı unuttular."))
        # ilk parçası 4 kelime olan cümle bölünmez (iki parça da en az 5 kelime olmalı)
        self.assertIsNone(bolme_noktasi("Öğrenciler deneyi dikkatle tamamladılar ancak sonuçları defterlerine yazmayı unuttular."))

    def test_turkce_buyuk_harf(self):
        ilk, ikinci = bolme_noktasi("Bu deney çok uzun sürdü, ışık kaynağı çok zayıf olduğu için sonuç alınamadı.")
        self.assertTrue(ikinci.startswith("Işık"))
        ilk, ikinci = bolme_noktasi("Bu deney çok uzun sürdü, iyi bir sonuç alınmasını bekliyorduk ama olmadı.")
        self.assertTrue(ikinci.startswith("İyi"))

    def test_kisa_parca_birakan_yer_secilmez(self):
        self.assertIsNone(bolme_noktasi("Evet, bunu yapabiliriz ama çok zor, sanırım olmaz."))

    def test_aday_yoksa_none(self):
        self.assertIsNone(bolme_noktasi("Okulumuzdaki öğretmenlerin çocuklarımıza kazandırmaya çalıştıkları davranışlar."))


if __name__ == "__main__":
    unittest.main()
