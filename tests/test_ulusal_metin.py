"""Ulusal metin sayfaları (İstiklal Marşı, Gençliğe Hitabe, Öğrenci Andı) yazım ve okunabilirlik analizi dışındadır."""
import unittest

from dkds.analiz.okunabilirlik import OLCUM_SURUMU, birimleri_olustur
from dkds.analiz.ulusal_metin import ulusal_metin_sayfalari, ulusal_metinleri_ayikla
from dkds.analiz.yazim import YazimAnalizoru
from dkds.models import Paragraf

MARS = ("Korkma, sönmez bu şafaklarda yüzen al sancak; Sönmeden yurdumun üstünde tüten en son ocak.")
MARS_2 = ("Bastığın yerleri toprak diyerek geçme, tanı: Düşün altındaki binlerce kefensiz yatanı. "
          "Sen ki, son ehlisin ve vecd ile serhaddim hürriyyet gibi arkaik sözcükler taşırsın.")
HITABE = "Ey Türk gençliği! Birinci vazifen, Türk istiklâlini, Türk Cumhuriyetini, ilelebet muhafaza ve müdafaa etmektir."
GOVDE = ("Fotosentez bitkilerin besin üretmesidir. Bitkiler güneş ışığını kullanır. Yaprak bu işin yapıldığı yerdir. "
         "Öğrenciler deney yaparak bunu gözlemler. Sonuçları defterlerine yazarlar. Ardından birlikte tartışırlar. "
         "Öğretmen her grubun bulgularını dinler ve tahtaya kısa bir özet yazar. Böylece herkes sonucu görür. Deney herkese çok eğlenceli gelir.")


def p(sayfa, no, metin, tur="govde"):
    return Paragraf(sayfa=sayfa, paragraf=no, metin=metin, konum=(0, 0, 100, 20), tur=tur)


def kitap():
    """sosyalbilgiler5 düzeni: s.3 marş (başlığı görsel), s.4 Gençliğe Hitabe, s.82 marştan alıntı yapan ders metni."""
    return [
        p(3, 1, MARS), p(3, 2, MARS_2),
        p(4, 1, "GENÇLİĞE HİTABE", "baslik"), p(4, 2, HITABE),
        p(10, 1, GOVDE),
        p(82, 1, "Vatan topraklarının işgal edilmesi üzerine İstiklal Marşı yazılmıştır."),
        p(82, 2, "“Korkma, sönmez bu şafaklarda yüzen al sancak; Sönmeden yurdumun üstünde tüten en son ocak.”"),
    ]


class SayfaTespitiTest(unittest.TestCase):
    def test_mars_hitabe_ve_alinti(self):
        # s.3: ilk paragraf marşın ilk dizesi; s.4: başlık; s.82: alıntı (ilk paragraf değil, tırnaklı) dışarı atılmaz
        self.assertEqual(ulusal_metin_sayfalari(kitap()), {3, 4})

    def test_baslik_turleri_ve_yazimlari(self):
        for baslik, tur in (("İSTİKLÂL MARŞI", "baslik"), ("İSTİKLAL MARŞI", "etiket"), ("GENÇLIĞE HITABE", "baslik"),
                            ("ÖĞRENCİ ANDI", "baslik"), ("ANDIMIZ", "baslik"), ("Öğrenci Andı", "etiket")):
            with self.subTest(baslik=baslik):
                self.assertEqual(ulusal_metin_sayfalari([p(7, 1, baslik, tur), p(7, 2, GOVDE)]), {7})

    def test_govde_metnindeki_ayni_ifade_sayfayi_disarida_birakmaz(self):
        # başlık olmayan paragrafta geçen "Gençliğe Hitabe" (ör. kitabın bir etkinliği) sayfayı dışarı atmaz
        self.assertEqual(ulusal_metin_sayfalari([p(9, 1, "Gençliğe Hitabe metnini sınıfta okuyunuz.")]), set())
        self.assertEqual(ulusal_metin_sayfalari([p(9, 1, GOVDE), p(9, 2, MARS)]), set())  # ilk paragraf değil

    def test_ayikla_yalniz_ulusal_sayfalari_cikarir(self):
        kalan = ulusal_metinleri_ayikla(kitap())
        self.assertEqual(sorted({q.sayfa for q in kalan}), [10, 82])


class YazimIleBirlikteTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.analizor = YazimAnalizoru()

    def kelimeler(self, paragraflar):
        return {b.sorunlu_metin.lower() for b in self.analizor.analiz_et(paragraflar) if b.tur == "bilinmeyen_kelime"}

    def test_mars_sayfasindaki_arkaik_sozcukler_yazim_hatasi_sayilmaz(self):
        self.assertTrue({"serhaddim", "vecd", "hürriyyet"} & self.kelimeler([p(30, 1, GOVDE), p(30, 2, MARS_2)]))
        # aynı metin marş sayfasındaysa denetlenmez
        self.assertEqual(self.kelimeler(kitap()), set())

    def test_baslikli_sayfadaki_metin_de_denetlenmez(self):
        self.assertEqual(self.kelimeler([p(5, 1, "ANDIMIZ", "baslik"), p(5, 2, "Türküm, doğruyum, çalışkanım okdum.")]),
                         set())
        self.assertEqual(self.kelimeler([p(5, 1, "Türküm, doğruyum, çalışkanım okdum.")]), {"okdum"})


class OkunabilirlikIleBirlikteTest(unittest.TestCase):
    def test_ulusal_metin_birim_olusturmaz(self):
        birimler, _ = birimleri_olustur(kitap())
        self.assertEqual(sorted({b.sayfa for b in birimler}), [10])  # s.3, 4 yok; s.82 kısa sayfa

    def test_ayni_metin_sayfa_basliksiz_olunca_birim_olur(self):
        birimler, _ = birimleri_olustur([p(20, 1, HITABE + " " + HITABE), p(20, 2, GOVDE)])
        self.assertEqual({b.sayfa for b in birimler}, {20})

    def test_olcum_surumu_artirildi(self):
        self.assertGreaterEqual(OLCUM_SURUMU, 5)  # çıkarılan sayfalar referansı değiştirir


if __name__ == "__main__":
    unittest.main()
