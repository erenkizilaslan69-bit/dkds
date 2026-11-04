"""Sayılar ve birimli ölçüler testleri: yazıyla sayılar, rakamlaştırma, sayı + birim, ortak taban."""
import unittest

from dkds.analiz.sayilar import (
    okunur,
    olculeri_bul,
    rakamlastir,
    sayi_yaz,
    yaklasik_mi,
    yazili_sayi_dizileri,
)


def tek(metin):
    """Metindeki tek ölçünün (boyut, alt, üst, yaklaşık) değerleri; yazıyla sayılar önce rakama çevrilir."""
    bulunan = olculeri_bul(rakamlastir(metin).yeni)
    assert len(bulunan) == 1, bulunan
    o = bulunan[0]
    return o.boyut, o.alt, o.ust, o.yaklasik


class YaziylaSayiTest(unittest.TestCase):
    def degerler(self, metin):
        return [d for _, _, d in yazili_sayi_dizileri(metin)]

    def test_temel_sayilar(self):
        self.assertEqual(self.degerler("yirmi dört saat"), [24])
        self.assertEqual(self.degerler("on bin yıl"), [10000])
        self.assertEqual(self.degerler("üç yüz altmış beş gün"), [365])
        self.assertEqual(self.degerler("bin beş yüz metre"), [1500])
        self.assertEqual(self.degerler("iki milyon üç yüz bin"), [2_300_000])
        self.assertEqual(self.degerler("yüz yirmi kilogram"), [120])

    def test_tek_basina_bir_sayi_degildir(self):
        self.assertEqual(self.degerler("bir gün boyunca"), [])
        self.assertEqual(self.degerler("bir milyon kilometre"), [1_000_000])

    def test_ayri_diziler(self):
        self.assertEqual(self.degerler("beş gün ve yirmi dakika"), [5, 20])
        self.assertEqual(self.degerler("on beş yirmi"), [15, 20])  # "beş yirmi" tek sayı olamaz

    def test_noktalama_diziyi_boler(self):
        self.assertEqual(self.degerler("on, beş"), [10, 5])


class RakamlastirTest(unittest.TestCase):
    def test_birimden_once_gelen_yazili_sayi_cevrilir(self):
        r = rakamlastir("Dünya 24 saatte döner, yani yirmi dört saat sürer.")
        self.assertEqual(r.yeni, "Dünya 24 saatte döner, yani 24 saat sürer.")

    def test_birimi_olmayan_yazili_sayi_kalir(self):
        self.assertEqual(rakamlastir("On kişi geldi.").yeni, "On kişi geldi.")

    def test_yuzde_sonrasi(self):
        self.assertEqual(rakamlastir("Suyun yüzde yetmiş bir kısmı").yeni, "Suyun yüzde 71 kısmı")

    def test_rakamli_sayinin_carpani_cevrilmez(self):
        # "12 bin yıl önce": "bin" 12'nin çarpanıdır, ayrı bir sayı (1000) değildir
        self.assertEqual(rakamlastir("yaklaşık 12 bin yıl önce").yeni, "yaklaşık 12 bin yıl önce")
        self.assertEqual(rakamlastir("500 bin yıl önce").yeni, "500 bin yıl önce")
        self.assertEqual(rakamlastir("bin yıl önce").yeni, "1000 yıl önce")

    def test_konum_haritasi_ozgun_metne_doner(self):
        metin = "Bu olay on bin yıl önce yaşandı."
        r = rakamlastir(metin)
        self.assertEqual(r.yeni, "Bu olay 10000 yıl önce yaşandı.")
        bas = r.yeni.index("10000")
        eski_bas, eski_son = r.eski(bas, bas + len("10000 yıl önce"))
        self.assertEqual(metin[eski_bas:eski_son], "on bin yıl önce")

    def test_degismeyen_kisimlarda_konum_kayar(self):
        metin = "yirmi dört saat ve 5 gün"
        r = rakamlastir(metin)
        bas = r.yeni.index("5 gün")
        self.assertEqual(metin[slice(*r.eski(bas, bas + 5))], "5 gün")


class ZamanTest(unittest.TestCase):
    def test_saat_ve_ekli_biciimler(self):
        self.assertEqual(tek("Dünya kendi ekseni etrafında 24 saatte döner"), ("zaman", 86400, 86400, False))
        self.assertEqual(tek("yirmi dört saat sürer"), ("zaman", 86400, 86400, False))
        self.assertEqual(tek("Her gün 8 saatlik uyku gerekir")[:2], ("zaman", 28800))

    def test_gun_saat_bilesigi(self):
        boyut, alt, ust, yaklasik = tek("Dünya yaklaşık 365 gün 6 saatte tamamlar")
        self.assertEqual((boyut, alt, ust, yaklasik), ("zaman", 365 * 86400 + 6 * 3600, 365 * 86400 + 6 * 3600, True))

    def test_uc_birimli_bilesik(self):
        self.assertEqual(tek("365 gün 6 saat 10 dakika")[1], 365 * 86400 + 6 * 3600 + 600)

    def test_yil_haftaya_dayali(self):
        self.assertEqual(tek("Ömrü 10 yıl kadardır")[1], 10 * 31_557_600)
        self.assertEqual(tek("iki hafta sürer")[1], 2 * 604800)
        self.assertEqual(tek("10 dakikada gitti")[1], 600)

    def test_aralik(self):
        self.assertEqual(tek("10-15 dakika bekleyin")[:3], ("zaman", 600, 900))

    def test_gun_birim_degil_tarih_eki(self):
        self.assertEqual(olculeri_bul("19 Ocak 2024 günü saat 00.49’da"), [])
        self.assertEqual(olculeri_bul("15 Nisan 2023’te uzaya gönderildi"), [])


class UzunlukKutleTest(unittest.TestCase):
    def test_km_ve_carpan(self):
        self.assertEqual(tek("Ay’a uzaklığı 384.000 km"), ("uzunluk", 384_000_000, 384_000_000, False))
        self.assertEqual(tek("Güneş’e 150 milyon km uzaklıkta")[1], 150_000_000_000)
        self.assertEqual(tek("1 milyon km ötede")[1], 1_000_000_000)

    def test_cm_mm_m(self):
        self.assertEqual(tek("boyu 50 cm")[1], 0.5)
        self.assertEqual(tek("kalınlığı 3 mm")[1], 0.003)
        self.assertEqual(tek("1 metre yükseklikte")[1], 1)
        self.assertEqual(tek("yaklaşık 4 santimetre")[:2], ("uzunluk", 0.04))

    def test_kutle(self):
        self.assertEqual(tek("kütlesi 2 kg")[:2], ("kütle", 2000))
        self.assertEqual(tek("5 gram şeker")[:2], ("kütle", 5))
        self.assertEqual(tek("3 ton yük")[:2], ("kütle", 3_000_000))
        self.assertEqual(tek("iki kilogram elma")[:2], ("kütle", 2000))

    def test_kuvvet(self):
        self.assertEqual(tek("yaya 20 N kuvvet uygulandı")[:2], ("kuvvet", 20))
        self.assertEqual(tek("30 N’lık kuvvet")[:2], ("kuvvet", 30))

    def test_birlesik_birimler_ve_alan_olcu_degildir(self):
        self.assertEqual(olculeri_bul("hızı 100 km/saat"), [])
        self.assertEqual(olculeri_bul("alanı 50 m² kadar"), [])
        self.assertEqual(olculeri_bul("yoğunluğu 5 g/cm³"), [])
        self.assertEqual(olculeri_bul("6 madde belirleyelim"), [])


class SicaklikYuzdeTest(unittest.TestCase):
    def test_negatif_sicaklik(self):
        self.assertEqual(tek("gece -174 ⁰C’u bulabilir")[:3], ("sıcaklık", -174, -174))
        self.assertEqual(tek("sıcaklık −20 °C’ye düştü")[:3], ("sıcaklık", -20, -20))
        self.assertEqual(tek("ortalama 15 ºC")[:3], ("sıcaklık", 15, 15))

    def test_derece_yalnizca_sicaklik_baglaminda(self):
        self.assertEqual(tek("su 100 derece sıcaklıkta kaynar")[:3], ("sıcaklık", 100, 100))
        self.assertEqual(olculeri_bul("45 derece açı çizin"), [])

    def test_aralik_eksi_degildir(self):
        self.assertEqual(tek("sıcaklık 20-30 °C arasında")[:3], ("sıcaklık", 20, 30))

    def test_yuzde(self):
        self.assertEqual(tek("Dünya’nın %71’i sudur")[:3], ("yüzde", 71, 71))
        self.assertEqual(tek("Dünya’nın yüzde 71’i sudur")[:2], ("yüzde", 71))
        self.assertEqual(tek("yüzde yetmiş bir oranında")[:2], ("yüzde", 71))
        self.assertEqual(tek("oran 71% kadar")[:2], ("yüzde", 71))
        self.assertEqual(tek("oranı %60-70 arasındadır")[:3], ("yüzde", 60, 70))


class YaklasiklikToleransTest(unittest.TestCase):
    def olcu(self, metin):
        return olculeri_bul(metin)[0]

    def test_kesin_olcude_yuzde_bir_tolerans(self):
        o = self.olcu("384.000 km uzaklıkta")
        self.assertAlmostEqual(o.tolerans, 0.01 * 384_000_000)  # 384.000 ~ 384.400 yuvarlama farkı çelişki değil

    def test_yaklasik_olcude_yuvarlama_eklenir(self):
        o = self.olcu("yaklaşık 30 °C")
        self.assertTrue(o.yaklasik)
        self.assertAlmostEqual(o.tolerans, 0.01 * 30 + 5)  # %1 + onlar basamağının yarısı

    def test_yaklasik_mi(self):
        metin = "yaklaşık 30 °C"
        self.assertEqual(yaklasik_mi(metin, 9, 14)[0], True)
        self.assertEqual(yaklasik_mi("30 °C", 0, 5)[0], False)


class GosterimTest(unittest.TestCase):
    def test_sayi_yaz(self):
        self.assertEqual(sayi_yaz(9500), "9.500")
        self.assertEqual(sayi_yaz(1.33333), "1,33")
        self.assertEqual(sayi_yaz(2.5), "2,5")

    def test_okunur(self):
        self.assertEqual(okunur(86400, "zaman"), "1 gün")
        self.assertEqual(okunur(5 * 3600, "zaman"), "5 saat")
        self.assertEqual(okunur(2400, "zaman"), "40 dakika")
        self.assertEqual(okunur(384_000_000, "uzunluk"), "384.000 km")
        self.assertEqual(okunur(0.5, "uzunluk"), "50 cm")
        self.assertEqual(okunur(2000, "kütle"), "2 kg")
        self.assertEqual(okunur(-174, "sıcaklık"), "-174 °C")
        self.assertEqual(okunur(71, "yüzde"), "%71")
        self.assertEqual(okunur(20, "kuvvet"), "20 N")


if __name__ == "__main__":
    unittest.main()
