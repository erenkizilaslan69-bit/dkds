"""Depodaki gerçek referans.json'un tutarlılık denetimi."""
import unittest

from dkds.analiz.okunabilirlik import OLCUM_SURUMU
from dkds.analiz.referans import referans_yukle


class ReferansDosyasiTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.ref = referans_yukle()

    def test_olcum_surumu_guncel(self):
        # Ölçüm kodu değiştiyse (OLCUM_SURUMU arttıysa) referans yeniden üretilmeli:
        # python -m dkds referans -k 3 veri\fen3.pdf -k 5 veri\fen5.pdf -k 5 veri\sosyalbilgiler5.pdf
        #                         -k 7 veri\fen7.pdf -k 9 veri\biyoloji9.pdf
        self.assertEqual(self.ref.olcum_surumu, OLCUM_SURUMU)

    def test_siniflar_ve_kaynaklar(self):
        self.assertEqual(sorted(self.ref.siniflar), [3, 4, 5, 6, 7, 8, 9])
        for no in (3, 5, 7, 9):
            r = self.ref.sinif(no)
            self.assertFalse(r.ara_deger)
            self.assertTrue(r.kitaplar)
            self.assertGreaterEqual(r.birim_sayisi, 100)  # dağılımın anlamlı olması için
        for no in (4, 6, 8):
            self.assertTrue(self.ref.sinif(no).ara_deger)
        self.assertEqual(self.ref.sinif(5).kitaplar, ["fen5.pdf", "sosyalbilgiler5.pdf"])

    def test_dilimler_sirali(self):
        for no, r in self.ref.siniflar.items():
            for ad, d in (("ateşman", r.atesman), ("bezirci_yilmaz", r.bezirci_yilmaz)):
                self.assertLess(d.p10, d.ortanca, f"{no}. sınıf {ad}")
                self.assertLess(d.ortanca, d.p90, f"{no}. sınıf {ad}")

    def test_sinif_arttikca_ortanca_zorlasir(self):
        # Referans yaklaşımının dayanağı: Ateşman ortancası düşer, Bezirci-Yılmaz ortancası yükselir.
        # Bu bozulursa (ör. yeni kitaplarla) referans yaklaşımı yeniden değerlendirilmeli.
        siniflar = sorted(self.ref.siniflar)
        for onceki, sonraki in zip(siniflar, siniflar[1:]):
            self.assertGreaterEqual(self.ref.sinif(onceki).atesman.ortanca, self.ref.sinif(sonraki).atesman.ortanca)
            self.assertLessEqual(self.ref.sinif(onceki).bezirci_yilmaz.ortanca,
                                 self.ref.sinif(sonraki).bezirci_yilmaz.ortanca)

    def test_ara_siniflar_komsularin_ortalamasi(self):
        for ara in (4, 6, 8):
            alt, ust = self.ref.sinif(ara - 1), self.ref.sinif(ara + 1)
            r = self.ref.sinif(ara)
            self.assertEqual(r.kaynak_siniflar, [ara - 1, ara + 1])
            for ad in ("ortanca", "p10", "p90"):
                self.assertAlmostEqual(getattr(r.atesman, ad),
                                       (getattr(alt.atesman, ad) + getattr(ust.atesman, ad)) / 2, places=2)


if __name__ == "__main__":
    unittest.main()
