"""Okunabilirlik analizörü testleri: cümle ayırma, hece sayma ve elle hesaplanmış formül örnekleri."""
import math
import unittest

from dkds.analiz.okunabilirlik import (
    atesman_duzeyi,
    atesman_kademesi,
    atesman_puani,
    bezirci_yilmaz_duzeyi,
    bezirci_yilmaz_puani,
    cumlelere_ayir,
    hece_say,
    kelimeleri_bul,
    metin_metrikleri,
    sinif_kademesi,
)


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
        self.assertEqual(len(cumlelere_ayir("Hangi özelliği ile ilgilidir? b. Ay’ın hareketleri nelerdir?")), 1)

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

    def test_sinif_kademesi(self):
        self.assertEqual([sinif_kademesi(s) for s in range(1, 13)], [0, 0, 0, 0, 1, 1, 2, 2, 3, 3, 4, 4])
        with self.assertRaises(ValueError):
            sinif_kademesi(13)

    def test_bezirci_yilmaz_duzeyi(self):
        # makale: Yeşil Yol 7,34 -> 7-8. sınıf
        self.assertEqual(bezirci_yilmaz_duzeyi(7.34), "7-8. sınıf")
        self.assertEqual(bezirci_yilmaz_duzeyi(9.4), "9-10. sınıf")
        self.assertEqual(bezirci_yilmaz_duzeyi(13.7), "lisans")
        self.assertEqual(bezirci_yilmaz_duzeyi(16.23), "akademik")


if __name__ == "__main__":
    unittest.main()
