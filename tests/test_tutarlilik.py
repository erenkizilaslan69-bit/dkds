"""Tutarlılık analizörü testleri: tarih olgusu çıkarma, normalleştirme, varlık eşleştirme, karşılaştırma.

Örnekler sosyalbilgiler5.pdf'ten (alıntılar çıkarılan metinden doğrulandı; bkz. CLAUDE.md).
"""
import unittest

from dkds.analiz.tutarlilik import (
    TarihOlgusu,
    TutarlilikAnalizoru,
    celisiyor_mu,
    en_yakin_varlik,
    guven_hesapla,
    olgulari_bul,
    sayi_oku,
)
from dkds.models import Paragraf


def paragraf(metin, sayfa, no=1):
    return Paragraf(sayfa=sayfa, paragraf=no, metin=metin, konum=(50.0, 100.0 * no, 500.0, 100.0 * no + 40))


def tek(cumle, referans_yili=2000):
    """Cümledeki tek olgunun (alt, üst, yaklaşık, tolerans) değerleri."""
    bulunan = olgulari_bul(cumle, referans_yili)
    assert len(bulunan) == 1, bulunan
    _, _, alt, ust, yaklasik, tolerans = bulunan[0]
    return alt, ust, yaklasik, tolerans


# sosyalbilgiler5.pdf: s.112 okuma metni, s.114, s.118, s.128, s.147 (kısaltılmış, ifadeler birebir)
KITAP_SOZCUKLERI = "Kitapta bundan sonra dünyanın eski günümüzde yaşayanlar anlatılır."
S112 = ("Örneğin Göbeklitepe MÖ 10000 yıllarında inşa edilmiştir. 2000’li yıllarda olduğumuz düşünüldüğünde "
        "Göbeklitepe’nin günümüzden 12.000 yıl önce kullanıldığı söylenebilir. Anadolu’daki ilk yerleşimler "
        "Çayönü (MÖ 8200), Çatalhöyük (MÖ 7500) ve Hacılar'dır (MÖ 7000).")
S114 = ("Günümüzden yaklaşık 12 bin yıl önce avcı ve toplayıcı yaşam tarzı süren insanlar tarafından inşa edilen "
        "Göbeklitepe, tarihte bilinen ilk inanç merkezidir.")
S118 = ("“Dünyanın eski Neolitik yerleşim merkezlerinden olan Çatalhöyük, yaklaşık 9000 yıl önce kurulmuştur. "
        "İlk tarım toplulukları arasında sayılan bu kent, geniş bir alanda yer almaktadır.")
S128 = ("Karahantepe'de 11.500-12.000 yıl önce insanların bir araya gelerek yemek yapma ve yemek yeme "
        "kültürüne sahip olduğu kanıtlandı.")
S147 = ("Bundan 9 500 yıl önce Çatalhöyük sakinleri; tahıl öğütmek, ekmek pişirmek, kumaş dokumak gibi "
        "işlerle uğraşmışlardır.")


def kitap(*sayfa_metin):
    return [paragraf(KITAP_SOZCUKLERI, 1)] + [paragraf(m, s) for s, m in sayfa_metin]


class SayiOkumaTest(unittest.TestCase):
    def test_binlik_ayiricilar(self):
        self.assertEqual(sayi_oku("7500"), 7500)
        self.assertEqual(sayi_oku("9 500"), 9500)
        self.assertEqual(sayi_oku("12.000"), 12000)
        self.assertEqual(sayi_oku("600 000"), 600000)
        self.assertEqual(sayi_oku("9 500"), 9500)
        self.assertEqual(sayi_oku("1,5"), 1.5)


class OlguCikarmaTest(unittest.TestCase):
    def test_mo_yazilislari(self):
        self.assertEqual(tek("Çatalhöyük (MÖ 7500)"), (9500, 9500, False, 0))
        self.assertEqual(tek("Çatalhöyük M.Ö. 7500 yılında kuruldu"), (9500, 9500, False, 0))
        self.assertEqual(tek("Çatalhöyük MÖ. 7500 yılında kuruldu")[:2], (9500, 9500))

    def test_ms(self):
        self.assertEqual(tek("Malazgirt Savaşı MS 1071 yılında yapıldı"), (929, 929, False, 0))
        self.assertEqual(tek("Malazgirt Savaşı M.S. 1071 yılında yapıldı")[:2], (929, 929))

    def test_referans_yili_parametre(self):
        self.assertEqual(tek("Çatalhöyük MÖ 7500", referans_yili=2025)[:2], (9525, 9525))
        self.assertEqual(tek("Malazgirt MS 1071", referans_yili=2025)[:2], (954, 954))

    def test_yillarinda_yaklasik_sayilir(self):
        alt, ust, yaklasik, tolerans = tek("Göbeklitepe MÖ 10000 yıllarında inşa edilmiştir")
        self.assertEqual((alt, ust, yaklasik), (12000, 12000, True))
        self.assertEqual(tolerans, 500)  # on binler değil binler basamağı

    def test_civarinda_yaklasik_sayilir(self):
        self.assertEqual(tek("yapılar MÖ 8000 civarında terk edilmiştir")[:3], (10000, 10000, True))

    def test_eki_olan_yil_yaklasik_sayilir(self):
        self.assertEqual(tek("tekerlek MÖ 5000’lerde bulunmuştur")[:3], (7000, 7000, True))

    def test_yil_once_binlik_ayiricilar(self):
        self.assertEqual(tek("Bundan 9 500 yıl önce Çatalhöyük sakinleri")[:3], (9500, 9500, False))
        self.assertEqual(tek("Günümüzden 12.000 yıl önce kullanıldı")[:3], (12000, 12000, False))

    def test_bin_kelimesi(self):
        self.assertEqual(tek("Günümüzden yaklaşık 12 bin yıl önce inşa edildi"), (12000, 12000, True, 500))
        self.assertEqual(tek("Tahıl tarımı yaklaşık 10 000 yıl önce başladı")[:3], (10000, 10000, True))

    def test_yaklasik_kesin_ayrimi(self):
        self.assertFalse(tek("kurulalı 9000 yıl önce")[2])
        self.assertTrue(tek("kurulalı yaklaşık 9000 yıl önce")[2])
        self.assertEqual(tek("kurulalı yaklaşık 9000 yıl önce")[3], 500)  # binler basamağının yarısı
        self.assertEqual(tek("kurulalı yaklaşık 9500 yıl önce")[3], 50)  # yüzler basamağının yarısı

    def test_aralik(self):
        self.assertEqual(tek("Karahantepe'de 11.500-12.000 yıl önce insanlar yaşadı")[:3], (11500, 12000, False))
        self.assertEqual(tek("Yerleşim MÖ 3000-2000 arasında kullanıldı")[:2], (4000, 5000))
        self.assertEqual(tek("Karahantepe'de 10-12 bin yıl önce insanlar yaşadı")[:2], (10000, 12000))

    def test_yuzyil_ve_kucuk_degerler_olgu_degildir(self):
        self.assertEqual(olgulari_bul("MÖ 7. yüzyılda kurulmuştur"), [])
        self.assertEqual(olgulari_bul("Bu olay 5 yıl önce yaşandı"), [])
        self.assertEqual(olgulari_bul("Cumhuriyet ilan edildi."), [])

    def test_bir_cumlede_birden_cok_olgu(self):
        cumle = "Çayönü (MÖ 8200), Çatalhöyük (MÖ 7500) ve Hacılar'dır (MÖ 7000)."
        self.assertEqual([round(o[2]) for o in olgulari_bul(cumle)], [10200, 9500, 9000])


class VarlikTest(unittest.TestCase):
    def varlik(self, cumle, ifade, sozcukler=frozenset()):
        bas = cumle.index(ifade)
        return en_yakin_varlik(cumle, bas, bas + len(ifade), sozcukler)

    def test_kesme_isaretinden_sonraki_ek_atilir(self):
        self.assertEqual(self.varlik("Çatalhöyük’te MÖ 7500 yıllarında evler vardı", "MÖ 7500"), "Çatalhöyük")
        self.assertEqual(self.varlik("Karahantepe'de 11.500-12.000 yıl önce insanlar yaşadı",
                                     "11.500-12.000 yıl önce"), "Karahantepe")

    def test_parantezden_onceki_isim(self):
        self.assertEqual(self.varlik("Çayönü (MÖ 8200), Çatalhöyük (MÖ 7500)", "MÖ 7500"), "Çatalhöyük")
        self.assertEqual(self.varlik("Çayönü (MÖ 8200), Çatalhöyük (MÖ 7500)", "MÖ 8200"), "Çayönü")

    def test_cumle_basi_siradan_sozcuk_isim_degildir(self):
        sozcukler = frozenset({"bundan"})
        self.assertEqual(self.varlik("Bundan 9 500 yıl önce Çatalhöyük sakinleri tahıl öğütürdü",
                                     "9 500 yıl önce", sozcukler), "Çatalhöyük")

    def test_obek_isim(self):
        self.assertEqual(self.varlik("Karain Mağarası MÖ 600 000 yıllarında kullanıldı", "MÖ 600 000 yıllarında"),
                         "Karain Mağarası")

    def test_genel_bolge_adi_varlik_degildir(self):
        self.assertIsNone(self.varlik("Tekerlek MÖ 5000’lerde Mezopotamya’da bulundu", "MÖ 5000’lerde", frozenset({"tekerlek"})))

    def test_isim_yoksa_none(self):
        self.assertIsNone(self.varlik("tahıl tarımı yaklaşık 10 000 yıl önce başlamıştır", "yaklaşık 10 000 yıl önce"))

    def test_uzak_isim_kullanilmaz(self):
        cumle = "Çatalhöyük " + "çok uzun bir açıklama " * 8 + "MÖ 7500 yılında"
        self.assertIsNone(self.varlik(cumle, "MÖ 7500"))


def olgu(alt, ust=None, yaklasik=False, tolerans=0.0, sayfa=1):
    return TarihOlgusu(sayfa=sayfa, paragraf=1, konum=(0, 0, 1, 1), ifade="x", alt=alt, ust=alt if ust is None else ust,
                       yaklasik=yaklasik, tolerans=tolerans, cumle="x")


class KarsilastirmaTest(unittest.TestCase):
    def test_yuvarlama_toleransi_icindeki_fark_celisme_degildir(self):
        # yaklaşık 9000 (binler basamağı, ±500) ile MÖ 7400 = 9400
        self.assertFalse(celisiyor_mu(olgu(9000, yaklasik=True, tolerans=500), olgu(9400)))

    def test_sinirdaki_fark_aday_sayilir(self):
        # yaklaşık 9000 ile MÖ 7500 = 9500: tam toleransın sınırında
        self.assertTrue(celisiyor_mu(olgu(9000, yaklasik=True, tolerans=500), olgu(9500)))

    def test_iki_kesin_deger_az_farkla_bile_celisir(self):
        self.assertTrue(celisiyor_mu(olgu(9500), olgu(9400)))
        self.assertFalse(celisiyor_mu(olgu(9500), olgu(9500)))

    def test_aralik_icindeki_deger_celismez(self):
        self.assertFalse(celisiyor_mu(olgu(11500, 12000), olgu(11800)))
        self.assertTrue(celisiyor_mu(olgu(11500, 12000), olgu(9500)))

    def test_guven_farkla_artar(self):
        yaklasik = olgu(9000, yaklasik=True, tolerans=500)
        sinirda = guven_hesapla(yaklasik, olgu(9500))
        uzak = guven_hesapla(yaklasik, olgu(12000))
        self.assertAlmostEqual(sinirda, 0.45)
        self.assertGreater(uzak, sinirda)
        self.assertLessEqual(uzak, 0.75)

    def test_iki_kesin_deger_yaklasik_olandan_guvenlidir(self):
        self.assertGreater(guven_hesapla(olgu(9500), olgu(9000)), guven_hesapla(olgu(9500), olgu(9000, 9000, True, 500)))


class AnalizTest(unittest.TestCase):
    def incele(self, *sayfa_metin):
        return TutarlilikAnalizoru().incele(kitap(*sayfa_metin))

    def test_catalhoyuk_orta_guvenle_yakalanir(self):
        s = self.incele((112, S112), (118, S118), (147, S147))
        catal = [b for b in s.bulgular if "Çatalhöyük" in b.aciklama]
        self.assertEqual(len(catal), 1)
        b = catal[0]
        self.assertEqual((b.kriter, b.tur), ("tutarlilik", "tarih_celiskisi"))
        self.assertTrue(0.35 <= b.guven <= 0.6, b.guven)  # orta güven: "yaklaşık" yuvarlama savunması olabilir
        # bulgu "yaklaşık 9000" olan s.118'e yazılır, çelişen yer s.112'dir (s.147 de 9500 diyerek onu destekler)
        self.assertEqual((b.sayfa, b.ilgili_sayfa), (118, 112))
        self.assertIsNotNone(b.konum)
        self.assertIsNotNone(b.ilgili_konum)
        for parca in ("s.118'de «yaklaşık 9000 yıl önce»", "s.112'de «MÖ 7500» (≈9.500 yıl önce)",
                      "Fark yaklaşık 500 yıl", "s.147'de de geçiyor", "yuvarlamayla açıklanabilir"):
            self.assertIn(parca, b.aciklama)

    def test_gobeklitepe_bulgu_uretmez(self):
        # s.112: MÖ 10000 yıllarında = 12.000 yıl önce; s.114: yaklaşık 12 bin yıl önce (aynı değer, farklı yazım)
        s = self.incele((112, S112), (114, S114))
        self.assertEqual([b for b in s.bulgular if "Göbeklitepe" in b.aciklama], [])
        gobekli = [o for o in s.olgular if o.anahtar == "göbeklitepe"]
        self.assertEqual(sorted(o.alt for o in gobekli), [12000, 12000, 12000])

    def test_karahantepe_gobeklitepe_ile_karismaz(self):
        s = self.incele((112, S112), (114, S114), (128, S128))
        karahan = [o for o in s.olgular if o.anahtar == "karahantepe"]
        self.assertEqual([(o.alt, o.ust) for o in karahan], [(11500, 12000)])
        self.assertTrue(all(o.anahtar != "göbeklitepe" for o in karahan))
        self.assertEqual(s.bulgular, [])

    def test_bes_sayfada_tek_aday(self):
        s = self.incele((112, S112), (114, S114), (118, S118), (128, S128), (147, S147))
        self.assertEqual(len(s.bulgular), 1)
        self.assertEqual(s.bulgular[0].sayfa, 118)

    def test_ayni_sayfadaki_farkli_degerler_aday_degildir(self):
        s = self.incele((112, "Çatalhöyük (MÖ 7500) kuruldu. Çatalhöyük MÖ 6000 yıllarında terk edildi."))
        self.assertEqual(s.bulgular, [])

    def test_varliksiz_olgu_karsilastirmaya_katilmaz(self):
        s = self.incele((10, "kuruluş MÖ 7500 yılında"), (20, "yerleşim MÖ 3000 yılında"))
        self.assertEqual(s.bulgular, [])
        self.assertEqual(s.ozet["varliksiz_olgu"], 2)

    def test_farkli_varliklarin_tarihleri_karsilastirilmaz(self):
        s = self.incele((112, S112))
        self.assertEqual(s.bulgular, [])
        self.assertEqual(s.ozet["varlikli_olgu"], 5)

    def test_ozet(self):
        s = self.incele((112, S112), (118, S118), (147, S147))
        o = s.ozet
        self.assertEqual((o["olgu_sayisi"], o["aday_celiski"], o["referans_yili"]), (7, 1, 2000))
        self.assertEqual(o["varlik_sayisi"], 4)  # Göbeklitepe, Çayönü, Çatalhöyük, Hacılar
        self.assertEqual(o["birden_cok_sayfadaki_varlik"], 1)  # Çatalhöyük

    def test_referans_yili_parametresi(self):
        # iki ifade aynı referans yılıyla hesaplanır: 2025'te de fark değişmez ve çelişki sürer
        s = TutarlilikAnalizoru(referans_yili=2025).incele(kitap((112, S112), (118, S118)))
        self.assertEqual(len(s.bulgular), 1)
        self.assertIn("9.525 yıl önce", s.bulgular[0].aciklama)  # MÖ 7500 + 2025


if __name__ == "__main__":
    unittest.main()
