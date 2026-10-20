"""Yazım analizörü testleri."""
import unittest

from dkds.analiz.yazim import KRITER, YazimAnalizoru
from dkds.models import Paragraf


def paragraf(metin, tur="govde"):
    return Paragraf(sayfa=1, paragraf=1, metin=metin, konum=(0, 0, 100, 20), tur=tur)


class KesinKurallarTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.analizor = YazimAnalizoru()

    def turler(self, metin, tur="govde"):
        return [b.tur for b in self.analizor.analiz_et([paragraf(metin, tur)])]

    def tek_bulgu(self, metin, beklenen_tur):
        bulgular = [b for b in self.analizor.analiz_et([paragraf(metin)]) if b.tur == beklenen_tur]
        self.assertEqual(len(bulgular), 1, metin)
        return bulgular[0]

    def test_noktalama_oncesi_bosluk(self):
        b = self.tek_bulgu("Kuvvet , cisimlerin şeklini değiştirir.", "noktalama_oncesi_bosluk")
        self.assertEqual(b.oneri, "Kuvvet,")
        self.assertEqual(b.kriter, KRITER)
        self.assertGreaterEqual(b.guven, 0.9)

    def test_uc_nokta_once_bosluk_hata_degil(self):
        self.assertNotIn("noktalama_oncesi_bosluk", self.turler("Gezegenler, uydular ... gibi gök cisimleri."))

    def test_noktalama_sonrasi_bosluk(self):
        b = self.tek_bulgu("Kitabı aldı ve,sonra okudu.", "noktalama_sonrasi_bosluk")
        self.assertEqual(b.oneri, "ve, sonra")

    def test_nokta_sonrasi_bosluk(self):
        self.tek_bulgu("Deney tamamlandı.Sonuçları yazınız.", "noktalama_sonrasi_bosluk")

    def test_ondalik_sayi_ve_adres_hata_degil(self):
        turler = self.turler("Sıcaklık 3,5 derece arttı. Bilgi için meb.gov.tr adresine bakınız.")
        self.assertNotIn("noktalama_sonrasi_bosluk", turler)

    def test_tekrar(self):
        b = self.tek_bulgu("Güneş ve ve Ay gök cisimleridir.", "tekrar")
        self.assertEqual(b.sorunlu_metin, "ve ve")

    def test_ikileme_tekrar_sayilmaz(self):
        self.assertNotIn("tekrar", self.turler("Su yavaş yavaş ısındı ve kat kat buz oluştu."))

    def test_kucuk_harfle_baslayan_cumle(self):
        b = self.tek_bulgu("Ay bir uydudur. dünya etrafında döner.", "kucuk_harfle_cumle")
        self.assertEqual(b.oneri, "Dünya")

    def test_kisaltma_ve_sira_sayisindan_sonra_kucuk_harf(self):
        metin = "Kalem, silgi vb. araçlar gereklidir. Tablo 36. sayfada yer alır. Gezegenler... ve uydular."
        self.assertNotIn("kucuk_harfle_cumle", self.turler(metin))

    def test_sik_yanlislar(self):
        b = self.tek_bulgu("Herkez bu deneyi yapabilir.", "sik_yanlis")
        self.assertEqual(b.oneri, "Herkes")
        b = self.tek_bulgu("Bu konuda bir çok örnek vardır.", "sik_yanlis")
        self.assertEqual(b.oneri, "birçok")

    def test_baslik_ve_etiket_incelenmez(self):
        self.assertEqual(self.turler("Herkez", tur="etiket"), [])
        self.assertEqual(self.turler("HERKEZ VE VE", tur="baslik"), [])

    def test_soru_ve_liste_incelenir(self):
        self.assertIn("sik_yanlis", self.turler("Herkez bunu biliyor mu?", tur="soru"))
        self.assertIn("sik_yanlis", self.turler("- Herkez grup oluştursun.", tur="liste"))


if __name__ == "__main__":
    unittest.main()
