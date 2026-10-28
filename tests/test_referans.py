"""Okunabilirlik referans tablosu testleri (yapay verilerle; gerçek referans.json için test_referans_dosyasi.py)."""
import contextlib
import io
import json
import tempfile
import unittest
from pathlib import Path

from dkds.analiz.referans import (
    Dagilim,
    Referans,
    SinifVerisi,
    referans_kaydet,
    referans_olustur,
    referans_yukle,
    yuzdelik,
)


class YuzdelikTest(unittest.TestCase):
    def test_dogrusal_ara_deger(self):
        # 11 değer 0..10: yüzdelik r -> 10 × r
        degerler = list(range(11))
        self.assertAlmostEqual(yuzdelik(degerler, 0.5), 5.0)
        self.assertAlmostEqual(yuzdelik(degerler, 0.1), 1.0)
        self.assertAlmostEqual(yuzdelik(degerler, 0.9), 9.0)
        # 4 değer: konum = 3 × 0,5 = 1,5 -> 20 ile 30'un ortası
        self.assertAlmostEqual(yuzdelik([40, 10, 30, 20], 0.5), 25.0)
        self.assertAlmostEqual(yuzdelik([40, 10, 30, 20], 0.1), 13.0)  # konum 0,3 -> 10 + 0,3 × 10

    def test_siralama_gerekmez_ve_tek_deger(self):
        self.assertEqual(yuzdelik([3, 1, 2], 0), 1)
        self.assertEqual(yuzdelik([3, 1, 2], 1), 3)
        self.assertEqual(yuzdelik([7.5], 0.9), 7.5)

    def test_dagilim(self):
        d = Dagilim.hesapla(list(range(11)))
        self.assertEqual((d.ortanca, d.p10, d.p90), (5.0, 1.0, 9.0))


def veri(ortanca, yayilim=10, kitap="a.pdf"):
    """21 birimlik yapay sınıf verisi: puanlar ortanca ± yayılım arasında eşit aralıklı."""
    atesman = [ortanca - yayilim + yayilim * i / 10 for i in range(21)]  # ortanca-yayılım … ortanca+yayılım
    return SinifVerisi(atesman=atesman, bezirci_yilmaz=[200 - a for a in atesman], kitaplar=[kitap])


class OlusturTest(unittest.TestCase):
    def setUp(self):
        self.ref = referans_olustur({3: veri(60, kitap="fen3.pdf"), 5: veri(50, kitap="fen5.pdf"),
                                     7: veri(40, kitap="fen7.pdf")}, olcum_surumu=7, aciklama="deneme")

    def test_olculen_siniflar(self):
        r = self.ref.sinif(5)
        self.assertFalse(r.ara_deger)
        self.assertEqual((r.birim_sayisi, r.kitaplar), (21, ["fen5.pdf"]))
        self.assertAlmostEqual(r.atesman.ortanca, 50.0)
        # %10 = ortanca - yayılım × 0,8 (21 değerli eşit aralıklı dizi): 40 + 20 × 0,1 = 42
        self.assertAlmostEqual(r.atesman.p10, 42.0)
        self.assertAlmostEqual(r.atesman.p90, 58.0)
        # bezirci_yilmaz = 200 - ateşman: ortanca 150, %10 142, %90 158
        self.assertAlmostEqual(r.bezirci_yilmaz.ortanca, 150.0)

    def test_ara_siniflar_komsulardan_dogrusal(self):
        r4, r6 = self.ref.sinif(4), self.ref.sinif(6)
        self.assertTrue(r4.ara_deger and r6.ara_deger)
        self.assertEqual((r4.kaynak_siniflar, r6.kaynak_siniflar), ([3, 5], [5, 7]))
        self.assertAlmostEqual(r4.atesman.ortanca, 55.0)  # (60 + 50) / 2
        self.assertAlmostEqual(r6.atesman.ortanca, 45.0)  # (50 + 40) / 2
        self.assertAlmostEqual(r4.atesman.p10, (self.ref.sinif(3).atesman.p10 + self.ref.sinif(5).atesman.p10) / 2)
        self.assertAlmostEqual(r6.bezirci_yilmaz.p90, (self.ref.sinif(5).bezirci_yilmaz.p90
                                                       + self.ref.sinif(7).bezirci_yilmaz.p90) / 2)

    def test_uc_basamakli_aralikta_dogrusal(self):
        ref = referans_olustur({3: veri(60), 7: veri(40)}, olcum_surumu=1)
        self.assertEqual(sorted(ref.siniflar), [3, 4, 5, 6, 7])
        self.assertAlmostEqual(ref.sinif(4).atesman.ortanca, 55.0)  # 60 + (40-60) × 1/4
        self.assertAlmostEqual(ref.sinif(5).atesman.ortanca, 50.0)
        self.assertAlmostEqual(ref.sinif(6).atesman.ortanca, 45.0)

    def test_kapsam_disi_sinif_yok(self):
        self.assertIsNone(self.ref.sinif(2))
        self.assertIsNone(self.ref.sinif(8))
        self.assertEqual(self.ref.kapsam, (3, 7))

    def test_ayni_sinifa_birden_cok_kitap_birlesir(self):
        a, b = veri(60, kitap="fen5.pdf"), veri(40, kitap="sosyal5.pdf")
        a.atesman += b.atesman
        a.bezirci_yilmaz += b.bezirci_yilmaz
        a.kitaplar += b.kitaplar
        ref = referans_olustur({5: a}, olcum_surumu=1)
        self.assertEqual(ref.sinif(5).birim_sayisi, 42)
        self.assertEqual(ref.sinif(5).kitaplar, ["fen5.pdf", "sosyal5.pdf"])
        self.assertAlmostEqual(ref.sinif(5).atesman.ortanca, 50.0)  # iki kitabın birleşik ortancası

    def test_gecersiz_girdi(self):
        with self.assertRaises(ValueError):
            referans_olustur({}, olcum_surumu=1)
        with self.assertRaises(ValueError):
            referans_olustur({5: SinifVerisi()}, olcum_surumu=1)
        with self.assertRaises(ValueError):
            referans_olustur({5: SinifVerisi(atesman=[1.0, 2.0], bezirci_yilmaz=[1.0])}, olcum_surumu=1)


class TipikDuzeyTest(unittest.TestCase):
    def setUp(self):
        # 3: [40, 60], 5: [30, 50], 7: [20, 40] aralıklı (yayılım ~ 0,8 × 10 = 8 -> p10/p90 ortanca ± 8)
        self.ref = referans_olustur({3: veri(50), 5: veri(40), 7: veri(30)}, olcum_surumu=1)

    def test_araliga_giren_en_yakin_ortanca(self):
        # 31: 7. sınıf aralığında (22-38, ortanca 30), 6. sınıfta (30-46...) da; en yakın ortanca 7. sınıf
        sinif, araliga_girdi = self.ref.tipik_duzey(31)
        self.assertEqual((sinif, araliga_girdi), (7, True))
        self.assertEqual(self.ref.tipik_duzey(49), (3, True))  # 3. sınıf ortancası 50

    def test_tum_siniflardan_zor(self):
        sinif, araliga_girdi = self.ref.tipik_duzey(-50)
        self.assertEqual((sinif, araliga_girdi), (7, False))  # en düşük %10 diliminin sahibi sınıf

    def test_tum_siniflardan_kolay(self):
        sinif, araliga_girdi = self.ref.tipik_duzey(500)
        self.assertEqual((sinif, araliga_girdi), (3, False))


class DosyaTest(unittest.TestCase):
    def test_kaydet_yukle_gidis_donus(self):
        ref = referans_olustur({3: veri(60, kitap="fen3.pdf"), 5: veri(50, kitap="fen5.pdf")}, olcum_surumu=4,
                               aciklama="açıklama")
        with tempfile.TemporaryDirectory() as klasor:
            yol = Path(klasor) / "referans.json"
            referans_kaydet(ref, yol)
            geri = referans_yukle(yol)
            ham = json.loads(yol.read_text(encoding="utf-8"))
        self.assertEqual((geri.olcum_surumu, geri.aciklama, sorted(geri.siniflar)), (4, "açıklama", [3, 4, 5]))
        for no in (3, 4, 5):
            self.assertAlmostEqual(geri.sinif(no).atesman.p10, ref.sinif(no).atesman.p10, places=3)
            self.assertEqual(geri.sinif(no).ara_deger, ref.sinif(no).ara_deger)
        self.assertEqual(geri.sinif(4).kaynak_siniflar, [3, 5])
        self.assertEqual(geri.sinif(3).kitaplar, ["fen3.pdf"])
        self.assertEqual(sorted(ham["siniflar"]), ["3", "4", "5"])  # sınıf anahtarları sayı sırasıyla yazılır
        self.assertNotIn("kitaplar", ham["siniflar"]["4"])  # ara değerde kitap listesi yok

    def test_desteklenmeyen_surum(self):
        with self.assertRaises(ValueError):
            Referans.sozlukten({"surum": 99, "siniflar": {}})


class KomutTest(unittest.TestCase):
    """python -m dkds referans: küçük bir PDF'ten referans üretir."""

    @classmethod
    def setUpClass(cls):
        try:
            import pymupdf as fitz
        except ImportError:
            try:
                import fitz
            except ImportError:
                raise unittest.SkipTest("PyMuPDF kurulu değil")
        cls.klasor = tempfile.TemporaryDirectory()
        cls.pdf = Path(cls.klasor.name) / "kitap.pdf"
        metin = ("Ali topu attı. Ayşe topu tuttu. Ali koştu. Ayşe güldü. Top suya düştü. Hep birlikte eve gittik. "
                 "Hava çok güzel. Kuş öttü. Biz okula gittik. Dersler başladı. Ali çok sevindi. Ayşe de sevindi. "
                 "Gün güzel geçti. Akşam eve döndük. Hava çok güzeldi.")
        doc = fitz.open()
        for _ in range(2):
            doc.new_page().insert_textbox(fitz.Rect(50, 100, 545, 300), metin, fontsize=11)
        doc.save(cls.pdf)
        doc.close()

    @classmethod
    def tearDownClass(cls):
        cls.klasor.cleanup()

    def calistir(self, *argumanlar):
        from dkds.__main__ import referans

        ekran = io.StringIO()
        with contextlib.redirect_stdout(ekran), contextlib.redirect_stderr(ekran):
            kod = referans(list(argumanlar))
        return kod, ekran.getvalue()

    def test_uretir(self):
        cikti = Path(self.klasor.name) / "ref.json"
        kod, ekran = self.calistir("-k", "3", str(self.pdf), "-k", "5", str(self.pdf), "-o", str(cikti))
        self.assertEqual(kod, 0)
        ref = referans_yukle(cikti)
        self.assertEqual(sorted(ref.siniflar), [3, 4, 5])
        self.assertEqual(ref.sinif(3).birim_sayisi, 2)
        self.assertEqual(ref.sinif(3).kitaplar, ["kitap.pdf"])
        self.assertTrue(ref.sinif(4).ara_deger)
        from dkds.analiz.okunabilirlik import OLCUM_SURUMU

        self.assertEqual(ref.olcum_surumu, OLCUM_SURUMU)
        self.assertIn("Referans kaydedildi", ekran)

    def test_ayni_sinifa_iki_kitap(self):
        cikti = Path(self.klasor.name) / "ref2.json"
        self.calistir("-k", "5", str(self.pdf), "-k", "5", str(self.pdf), "-o", str(cikti))
        self.assertEqual(referans_yukle(cikti).sinif(5).birim_sayisi, 4)

    def test_gecersiz_sinif_ve_dosya(self):
        kod, ekran = self.calistir("-k", "13", str(self.pdf), "-o", str(Path(self.klasor.name) / "x.json"))
        self.assertEqual(kod, 1)
        self.assertIn("Geçersiz sınıf", ekran)
        kod, ekran = self.calistir("-k", "5", "yok.pdf", "-o", str(Path(self.klasor.name) / "x.json"))
        self.assertEqual(kod, 1)
        self.assertIn("Dosya bulunamadı", ekran)


if __name__ == "__main__":
    unittest.main()
