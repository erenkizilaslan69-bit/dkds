"""Tutarlılık analizörü testleri: tarih olgusu çıkarma, normalleştirme, varlık eşleştirme, karşılaştırma.

Örnekler sosyalbilgiler5.pdf'ten (alıntılar çıkarılan metinden doğrulandı; bkz. CLAUDE.md).
"""
import unittest

from dkds.analiz.tutarlilik import (
    Olgu,
    TarihOlgusu,
    TutarlilikAnalizoru,
    celisiyor_mu,
    en_yakin_varlik,
    guven_hesapla,
    olgulari_bul,
    kosullar_uyumlu_mu,
    sayi_oku,
    varlik_anahtarlari,
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


class YaziylaSayiTarihTest(unittest.TestCase):
    def test_yazili_yil_once_tarih_olgusudur(self):
        self.assertEqual(tek("Bu eserler on bin yıl önce yapıldı")[:3], (10000, 10000, False))

    def test_yazili_sayi_konumu_ozgun_cumlede_kalir(self):
        cumle = "Bu eserler on bin yıl önce yapıldı"
        bas, son, *_ = olgulari_bul(cumle)[0]
        self.assertEqual(cumle[bas:son], "on bin yıl önce")


class VarlikDuzeltmeTest(unittest.TestCase):
    def varlik(self, cumle, ifade, orta=frozenset(), kisa=False, tarih=True, sozcukler=frozenset()):
        bas = cumle.index(ifade)
        return en_yakin_varlik(cumle, bas, bas + len(ifade), sozcukler, orta, kisa, tarih)

    def test_cumle_basindaki_siradan_sozcuk_isim_degildir(self):
        # s.114: "Çemberimsi anıtsal yapılar, MÖ 8000 civarında ... terk edilmiştir"
        cumle = "Çemberimsi anıtsal yapılar, MÖ 8000 civarında terk edilmiştir."
        self.assertIsNone(self.varlik(cumle, "MÖ 8000 civarında", orta=frozenset()))

    def test_cumle_basindaki_isim_kitapta_ortada_buyukse_kalir(self):
        cumle = "Hacılar yerleşimi MÖ 7000 yıllarında kurulmuştur."
        self.assertIsNone(self.varlik(cumle, "MÖ 7000 yıllarında", orta=frozenset()))
        self.assertEqual(self.varlik(cumle, "MÖ 7000 yıllarında", orta=frozenset({"hacılar"})), "Hacılar")

    def test_cumle_basinda_kesmeli_parantezli_ve_obek_isim_kalir(self):
        self.assertEqual(self.varlik("Karahantepe'de 11.500 yıl önce insanlar yaşadı.", "11.500 yıl önce",
                                     orta=frozenset()), "Karahantepe")
        self.assertEqual(self.varlik("Çayönü (MÖ 8200) bir yerleşimdir.", "MÖ 8200", orta=frozenset()), "Çayönü")
        self.assertEqual(self.varlik("Karain Mağarası MÖ 600 000 yıllarında kullanıldı.", "MÖ 600 000 yıllarında",
                                     orta=frozenset()), "Karain Mağarası")

    def test_kisa_etiket_paragrafinda_cumle_basi_isim_kalir(self):
        self.assertEqual(self.varlik("Göbeklitepe MÖ 10000", "MÖ 10000", orta=frozenset(), kisa=True), "Göbeklitepe")

    def test_ay_iki_harfli_olsa_da_varliktir(self):
        cumle = "Ay’da sıcaklık gece -174 ⁰C’u bulabilmektedir."
        self.assertEqual(self.varlik(cumle, "-174 ⁰C’u", orta=frozenset(), tarih=False, sozcukler=frozenset({"ay"})), "Ay")

    def test_genel_bolge_adi_yalnizca_tarihte_elenir(self):
        cumle = "Dünya, kendi ekseni etrafında 24 saatte döner."
        self.assertIsNone(self.varlik(cumle, "24 saatte", tarih=True, sozcukler=frozenset()))
        self.assertEqual(self.varlik(cumle, "24 saatte", tarih=False, sozcukler=frozenset()), "Dünya")

    def test_form_etiketi_ve_baslik_harfleri_isim_degildir(self):
        self.assertIsNone(self.varlik("Süre : 40 dk", "40 dk", tarih=False))
        self.assertIsNone(self.varlik("İSTİRAHAT 10-15 dakika", "10-15 dakika", tarih=False, orta=frozenset()))

    def test_obek_son_sozcukle_eslesir(self):
        self.assertEqual(varlik_anahtarlari("Sümer Kralı Urukagina"), ("sümer kralı urukagina", "urukagina"))
        self.assertEqual(varlik_anahtarlari("Göbeklitepe"), ("göbeklitepe",))

    def test_genel_son_sozcuk_eslesme_anahtari_olmaz(self):
        self.assertEqual(varlik_anahtarlari("Karain Mağarası"), ("karain mağarası",))
        self.assertEqual(varlik_anahtarlari("Şarklı Keper Mağarası"), ("şarklı keper mağarası",))


S131 = "Sümer Kralı Urukagina’nın MÖ 2375’te hazırlattığı kanunlar, tarihte bilinen ilk yazılı kanunlar olmuştur."


class ObekEslesmeTest(unittest.TestCase):
    def test_obek_baska_yerdeki_kisa_adla_eslesir(self):
        s = TutarlilikAnalizoru().incele(kitap((131, S131), (140, "Bu dönemde Urukagina MÖ 2400’de krallık yaptı.")))
        self.assertEqual([(b.sayfa, b.ilgili_sayfa) for b in s.bulgular], [(140, 131)])

    def test_farkli_magaralar_karismaz(self):
        s = TutarlilikAnalizoru().incele(kitap(
            (113, "Şarklı Keper Mağarası’nın MÖ 600 000 yıllarında kullanıldığı düşünülmektedir."),
            (105, "Karain Mağarası MÖ 500 000 yıllarında kullanıldı.")))
        self.assertEqual(s.bulgular, [])


def paragraf_tur(metin, sayfa, tur="govde", no=1):
    return Paragraf(sayfa=sayfa, paragraf=no, metin=metin, konum=(50.0, 100.0 * no, 500.0, 100.0 * no + 40), tur=tur)


AY_SICAKLIK = "Ay’da sıcaklık gece -174 ⁰C’u, gündüz ise 125 ⁰C’u bulabilmektedir."


class SayisalCelismeTest(unittest.TestCase):
    def incele(self, *sayfa_metin):
        return TutarlilikAnalizoru().incele(kitap(*sayfa_metin))

    def test_gece_ve_gunduz_sicakligi_karismaz(self):
        # s.35'te gece -174, gündüz 125; başka sayfada "Ay’da gündüz sıcaklık 127": gündüz-gündüz tutarlı,
        # gece-gündüz çiftleri farklı nicelik
        s = self.incele((35, AY_SICAKLIK), (40, "Ay’da gündüz sıcaklık 127 ⁰C’ye ulaşır."))
        self.assertEqual(s.bulgular, [])
        self.assertEqual(s.belirsizler, [])
        self.assertGreaterEqual(s.ozet["farkli_nicelik"], 1)

    def test_ayni_ayirici_ve_tur_ise_aday(self):
        s = self.incele((35, AY_SICAKLIK), (40, "Ay’da sıcaklık gece -150 ⁰C’ye düşer."))
        self.assertEqual(len(s.bulgular), 1)
        b = s.bulgular[0]
        self.assertEqual((b.kriter, b.tur), ("tutarlilik", "sayisal_celiski"))
        self.assertEqual({b.sayfa, b.ilgili_sayfa}, {35, 40})
        self.assertIn("«Ay»", b.aciklama)
        self.assertIn("ayırıcı: gece", b.aciklama)
        self.assertIn("-174 °C", b.aciklama)
        self.assertTrue(0.4 <= b.guven <= 0.8, b.guven)

    def test_yuvarlama_farki_celisme_degildir(self):
        s = self.incele((34, "Ay’ın Dünya’ya uzaklığı 384.400 km kadardır."),
                        (60, "Ay’ın Dünya’ya uzaklığı 384.000 km civarındadır."))
        self.assertEqual(s.bulgular, [])

    def test_ayni_uzaklik_farkli_deger_aday(self):
        s = self.incele((34, "Ay’ın Dünya’ya uzaklığı 384.400 km kadardır."),
                        (60, "Ay’ın Dünya’ya uzaklığı 150.000 km olarak verilmiştir."))
        self.assertEqual(len(s.bulgular), 1)
        self.assertIn("tür: uzaklık", s.bulgular[0].aciklama)

    def test_farkli_nicelik_turu_aday_degildir(self):
        s = self.incele((34, "Ay’ın Dünya’ya uzaklığı 384.400 km kadardır."),
                        (60, "Ay’ın çapı 3.474 km uzunluğundadır."))
        self.assertEqual(s.bulgular, [])
        self.assertEqual(s.belirsizler, [])
        self.assertEqual(s.ozet["farkli_nicelik"], 1)

    def test_tur_belli_degilse_belirsiz(self):
        s = self.incele((20, "Performans görevi olarak Ay’ı 30 gün boyunca gözlemleyiniz."),
                        (49, "Ay’ın dönme hareketi yaklaşık 27 gün 8 saatte tamamlanır."))
        self.assertEqual(s.bulgular, [])
        self.assertEqual(len(s.belirsizler), 1)
        self.assertEqual(s.belirsizler[0].neden, "nicelik türü belli değil")

    def test_ayirici_yalnizca_birinde_belirsiz(self):
        s = self.incele((35, "Ay’da sıcaklık gece -174 ⁰C’u bulabilir."), (40, "Ay’da sıcaklık -150 ⁰C’dir."))
        self.assertEqual(s.bulgular, [])
        self.assertEqual(len(s.belirsizler), 1)
        self.assertIn("ayırıcı yalnızca birinde (gece)", s.belirsizler[0].neden)

    def test_kosul_olcusu_farkliysa_belirsiz(self):
        # s.76: "60 kg kütleli cismin ağırlığı Ay'da 100 N"; s.93: başka bir cismin ağırlığı Ay'da 60 N
        s = self.incele((76, "Örneğin 60 kg kütleli bir cismin ağırlığı Dünya’da yaklaşık 600 N ölçülürken Ay’da 100 N ölçülür."),
                        (93, "Ay’da 60 N ağırlığında olan bir cismin ağırlığı Dünya’da kaç N’dır?"))
        self.assertEqual(s.bulgular, [])
        self.assertTrue(any("koşul" in b.neden for b in s.belirsizler), [b.neden for b in s.belirsizler])

    def test_composit_zaman_dolanma(self):
        s = self.incele((49, "Dünya, Güneş etrafındaki dolanma hareketini yaklaşık 365 gün 6 saatte tamamlar."),
                        (56, "Dünya, Güneş etrafındaki dolanma hareketini 24 saatte tamamlar."))
        self.assertEqual(len(s.bulgular), 1)
        self.assertEqual(s.bulgular[0].tur, "sayisal_celiski")

    def test_yaziyla_sayi_olcu_olgusudur(self):
        s = self.incele((49, "Dünya kendi ekseni etrafındaki dönme hareketini yirmi dört saatte tamamlar."),
                        (56, "Dünya kendi ekseni etrafındaki dönme hareketini 24 saatte tamamlar."))
        sicakliklar = [o for o in s.olgular if o.boyut == "zaman"]
        self.assertEqual([o.alt for o in sicakliklar], [86400, 86400])
        self.assertEqual(s.bulgular, [])

    def test_olgu_ifadesi_ozgun_yazilisla_gosterilir(self):
        s = self.incele((49, "Dünya kendi ekseni etrafındaki dönme hareketini yirmi dört saatte tamamlar."))
        self.assertEqual(s.olgular[0].ifade, "yirmi dört saatte")

    def test_ayni_sayfadaki_farklar_aday_degildir(self):
        s = self.incele((35, "Ay’da sıcaklık gece -174 ⁰C’u bulabilir. Ay’da sıcaklık gece -100 ⁰C’dir."))
        self.assertEqual(s.bulgular, [])

    def test_etiket_paragrafindaki_olculer_alinmaz(self):
        s = TutarlilikAnalizoru().incele([paragraf_tur("Burdur G. ( 854 m. )", 54, tur="etiket")])
        self.assertEqual(s.olgular, [])

    def test_kunye_paragrafindaki_sure_alinmaz(self):
        kunye = "Adı Canlıların Sınıflandırılması Amaç Çevresindeki canlıları sınıflandırabilme Süre 80 dk."
        s = TutarlilikAnalizoru().incele([paragraf_tur(kunye, 126), paragraf_tur(kunye.replace("80", "40"), 128)])
        self.assertEqual((s.olgular, s.bulgular, s.belirsizler), ([], [], []))

    def test_varliksiz_benzer_olgular_belirsiz_ve_zayif_ayrimi(self):
        s = self.incele((49, "Bu dönme hareketi 24 saatte tamamlanır."),
                        (50, "Dünya dolanma hareketini yaklaşık 365 gün 6 saatte tamamlar; bu hareket tamamlanır."))
        # tür her ikisinde belirli (dönme / dolanma farklı): aynı nicelik değil -> belirsiz bile değil
        self.assertEqual(s.bulgular, [])

    def test_belirsiz_sozluk_llm_icin_iki_ifadeyi_tasir(self):
        s = self.incele((20, "Performans görevi olarak Ay’ı 30 gün boyunca gözlemleyiniz."),
                        (49, "Ay’ın dönme hareketi yaklaşık 27 gün 8 saatte tamamlanır."))
        d = s.belirsizler[0].sozluk()
        self.assertEqual((d["sayfa_1"], d["sayfa_2"], d["varlik"], d["guc"]), (20, 49, "Ay", "guclu"))
        self.assertEqual((d["ifade_1"], d["ifade_2"]), ("30 gün", "yaklaşık 27 gün 8 saatte"))
        self.assertIn("cumle_1", d)

    def test_ozet_alanlari(self):
        s = self.incele((35, AY_SICAKLIK), (40, "Ay’da sıcaklık gece -150 ⁰C’ye düşer."), (112, S112))
        o = s.ozet
        self.assertEqual(o["olgu_sayisi"], o["tarih_olgusu"] + o["sayisal_olgu"])
        self.assertEqual((o["tarih_olgusu"], o["sayisal_olgu"]), (5, 3))
        self.assertEqual((o["aday_tarih"], o["aday_sayisal"], o["aday_celiski"]), (0, 1, 1))
        self.assertIn("belirsiz_zayif", o)


class KosulTest(unittest.TestCase):
    def olgu_kosullu(self, kosullar):
        return Olgu(sayfa=1, paragraf=1, konum=(0, 0, 1, 1), ifade="x", alt=1, ust=1, yaklasik=False, tolerans=0,
                    cumle="x", kosullar=kosullar)

    def test_koşulsuz_iki_olgu_uyumludur(self):
        self.assertTrue(kosullar_uyumlu_mu(self.olgu_kosullu(()), self.olgu_kosullu(())))

    def test_yalnizca_birinde_kosul_varsa_uyumsuz(self):
        self.assertFalse(kosullar_uyumlu_mu(self.olgu_kosullu((("kütle", 60000, 60000, 600),)), self.olgu_kosullu(())))

    def test_ayni_kosul_uyumlu_farkli_kosul_uyumsuz(self):
        a = self.olgu_kosullu((("kütle", 60000, 60000, 600),))
        self.assertTrue(kosullar_uyumlu_mu(a, self.olgu_kosullu((("kütle", 60100, 60100, 601),))))
        self.assertFalse(kosullar_uyumlu_mu(a, self.olgu_kosullu((("kütle", 10000, 10000, 100),))))


class AlistirmaTest(unittest.TestCase):
    """fen5 s.49-50: doğru/yanlış sorusunun 5. maddesi bilerek yanlıştır; kitap bilgisi sayılmaz."""

    S49 = ("Dünya’nın kendi ekseni etrafındaki dönme hareketi 24 saatte tamamlanır. Dünya’nın Güneş’in etrafındaki "
           "dolanma hareketi yaklaşık 365 gün 6 saatte tamamlanır.")

    def sayfa50(self, yonerge, madde="5. Dünya, dolanma hareketini 24 saatte tamamlar."):
        return [
            Paragraf(sayfa=50, paragraf=3, metin="PEKİŞTİRME İSTASYONU-1", konum=(0, 0, 1, 1), tur="baslik"),
            Paragraf(sayfa=50, paragraf=4, metin=yonerge, konum=(0, 1, 1, 2)),
            Paragraf(sayfa=50, paragraf=5, metin="D Y", konum=(0, 2, 1, 3), tur="baslik"),
            Paragraf(sayfa=50, paragraf=10, metin=madde, konum=(0, 3, 1, 4), tur="liste"),
        ]

    def incele(self, *paragraflar):
        return TutarlilikAnalizoru().incele(list(paragraflar))

    def test_dogru_yanlis_maddesi_olgu_sayilmaz(self):
        yonerge = "Aşağıdaki ifadelerin doğruluk durumunu belirleyiniz. İfade doğru ise “D”, yanlış ise “Y” kutusunu işaretleyiniz."
        s49 = paragraf(self.S49, 49)
        sonuc = self.incele(s49, *self.sayfa50(yonerge))
        self.assertEqual({o.sayfa for o in sonuc.olgular}, {49})
        self.assertEqual(sonuc.belirsizler, [])
        self.assertEqual(sonuc.bulgular, [])

    def test_yonergesiz_ayni_madde_olgu_olur(self):
        # aynı madde yönergesiz (düz anlatım) ise olgudur: kural yalnızca yönergeli bloğu dışarıda bırakır
        sonuc = self.incele(paragraf(self.S49, 49), paragraf("Dünya, dolanma hareketini 24 saatte tamamlar.", 50))
        self.assertIn(50, {o.sayfa for o in sonuc.olgular})

    def test_diger_yonerge_turleri(self):
        for yonerge in ("Boşlukları doldurunuz.", "İfade doğru ya da yanlış ise işaretleyiniz.",
                        "Doğru ise D yanlış ise Y yazınız."):
            sonuc = self.incele(*self.sayfa50(yonerge, "Dünya, dolanma hareketini 24 saatte tamamlar."))
            self.assertEqual(sonuc.olgular, [], yonerge)

    def test_blok_yeni_baslikta_biter(self):
        paragraflar = self.sayfa50("İfade doğru ise D, yanlış ise Y yazınız.") + [
            Paragraf(sayfa=50, paragraf=11, metin="BİLGİ İSTASYONU", konum=(0, 4, 1, 5), tur="baslik"),
            Paragraf(sayfa=50, paragraf=12, metin="Dünya, dolanma hareketini 365 gün 6 saatte tamamlar.", konum=(0, 5, 1, 6)),
        ]
        sonuc = self.incele(*paragraflar)
        self.assertEqual([o.paragraf for o in sonuc.olgular], [12])

    def test_blok_sayfa_sonunda_biter_ve_uzun_anlatim_yonerge_degil(self):
        sonuc = self.incele(*self.sayfa50("İfade doğru ise D, yanlış ise Y yazınız."),
                            paragraf("Dünya, dolanma hareketini 24 saatte tamamlar.", 51))
        self.assertEqual({o.sayfa for o in sonuc.olgular}, {51})
        uzun = "Bu cümle doğru ise önemlidir. " + "Uzun anlatım sözcüğü " * 20
        sonuc = self.incele(paragraf(uzun, 60), paragraf("Dünya, dolanma hareketini 24 saatte tamamlar.", 60, 2))
        self.assertEqual([o.paragraf for o in sonuc.olgular], [2])

    def test_uzun_okuma_metni_blogu_bitirir(self):
        # fen7 s.140: yönergeden sonra 30 kelimeden uzun gövde paragrafı (haber/anlatım) alıştırma maddesi değildir
        uzun = ("Mehmet, bir yıldır böbrek yetmezliği ile mücadele ediyordu. Haftada üç gün gittiği diyaliz "
                "merkezindeki makineler yaşamının bir parçası olmuştu. Her seans dört saat sürüyordu ve sürekli yorgundu. Doktorlar nakil için aileyi bilgilendirdi.")
        sonuc = self.incele(*self.sayfa50("Doğru ya da yanlış olduğuna karar veriniz."), paragraf(uzun, 50, 20))
        self.assertEqual({o.paragraf for o in sonuc.olgular}, {20})  # "üç gün", "dört saat"

    def test_zayif_yonerge_yalniz_hemen_alti_kapsar(self):
        # fen7 s.120: "... cevaplayınız" etkinlik yönergesidir; sonraki anlatım ve madde imli liste olgudur
        yonerge = Paragraf(sayfa=120, paragraf=6, metin="Sunum sonunda değerlendirme sorusunu cevaplayınız.",
                           konum=(0, 0, 1, 1))
        anlatim = Paragraf(sayfa=120, paragraf=11, metin="Doğru nefes için dikkat edin: 3-4 saniye nefesinizi tutun.",
                           konum=(0, 1, 1, 2))
        self.assertEqual(TutarlilikAnalizoru.alistirma_paragraflari([yonerge, anlatim]), {(120, 6)})

    def test_zayif_yonerge_madde_ve_bosluklu_maddeleri_kapsar(self):
        # biyoloji9 s.157: "Boş bırakılan bölümleri işaretleyiniz" + "(……) ... 10 000 yıl önce" maddeleri
        yonerge = Paragraf(sayfa=157, paragraf=10, metin="20. Hangisi doğrudur? Boş bırakılan bölümleri işaretleyiniz.",
                           konum=(0, 0, 1, 1), tur="liste")
        madde = Paragraf(sayfa=157, paragraf=11, metin="(……) Tahıl tarımı yaklaşık 10 000 yıl önce başlamıştır.",
                         konum=(0, 1, 1, 2))
        self.assertEqual(TutarlilikAnalizoru.alistirma_paragraflari([yonerge, madde]), {(157, 10), (157, 11)})

    def test_soru_turundeki_paragraf_olgu_sayilmaz(self):
        soru = Paragraf(sayfa=70, paragraf=1, metin="Dünya, dolanma hareketini kaç saatte tamamlar, 24 saatte mi?",
                        konum=(0, 0, 1, 1), tur="soru")
        self.assertEqual(self.incele(soru).olgular, [])


if __name__ == "__main__":
    unittest.main()
