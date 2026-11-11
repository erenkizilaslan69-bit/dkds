"""Tam analiz iş akışı ve on_hesapla komutu."""
import contextlib
import io
import json
import tempfile
import unittest
from pathlib import Path

try:
    import pymupdf as fitz
except ImportError:
    try:
        import fitz
    except ImportError:
        fitz = None

from dkds.is_akisi import kitabi_analiz_et, sinifi_dosya_adindan_bul


class SinifTahminiTest(unittest.TestCase):
    def test_dosya_adindan_sinif(self):
        self.assertEqual(sinifi_dosya_adindan_bul(Path("veri/fen5.pdf")), 5)
        self.assertEqual(sinifi_dosya_adindan_bul(Path("biyoloji9.pdf")), 9)
        self.assertEqual(sinifi_dosya_adindan_bul(Path("matematik12.pdf")), 12)
        self.assertIsNone(sinifi_dosya_adindan_bul(Path("kitap.pdf")))
        self.assertIsNone(sinifi_dosya_adindan_bul(Path("kitap99.pdf")))


@unittest.skipIf(fitz is None, "PyMuPDF kurulu değil")
class IsAkisiTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.klasor = tempfile.TemporaryDirectory()
        cls.veri = Path(cls.klasor.name) / "veri"
        cls.veri.mkdir()
        belge = fitz.open()
        sayfa = belge.new_page()
        sayfa.insert_textbox(fitz.Rect(50, 100, 545, 300), "Projenin hayata gecmesi hedeflenmektedi . Kuvvet ve ve hareket.",
                             fontsize=11)
        belge.save(cls.veri / "ornek3.pdf")
        belge.close()

    @classmethod
    def tearDownClass(cls):
        cls.klasor.cleanup()

    def test_kayit_ve_ilerleme(self):
        adimlar = []
        kayit = kitabi_analiz_et(self.veri / "ornek3.pdf", 3, ilerleme=lambda oran, ad: adimlar.append((oran, ad)))
        self.assertEqual((kayit["kaynak"], kayit["sinif"], kayit["sayfa_sayisi"]), ("ornek3.pdf", 3, 1))
        self.assertTrue(kayit["bulgular"])
        self.assertTrue(all("paragraf_turu" in b for b in kayit["bulgular"]))
        self.assertIn("okunabilirlik_ozeti", kayit)
        self.assertIn("tutarlilik_ozeti", kayit)
        oranlar = [o for o, _ in adimlar]
        self.assertEqual(oranlar, sorted(oranlar))  # ilerleme geriye gitmez
        self.assertEqual(adimlar[-1], (1.0, "Tamamlandı"))
        json.dumps(kayit)  # JSON'a yazılabilir

    def test_sinifsiz_analizde_okunabilirlik_yok(self):
        kayit = kitabi_analiz_et(self.veri / "ornek3.pdf", None)
        self.assertNotIn("okunabilirlik_ozeti", kayit)
        self.assertEqual({b["kriter"] for b in kayit["bulgular"]}, {"yazim"})

    def test_on_hesapla_komutu(self):
        from dkds.__main__ import on_hesapla

        cikti = Path(self.klasor.name) / "cikti"
        with contextlib.redirect_stdout(io.StringIO()):
            kod = on_hesapla(["--veri", str(self.veri), "--cikti", str(cikti)])
        self.assertEqual(kod, 0)
        kayit = json.loads((cikti / "ornek3_bulgular.json").read_text(encoding="utf-8"))
        self.assertEqual(kayit["sinif"], 3)  # sınıf dosya adından bulundu

    def test_on_hesapla_pdf_yoksa_hata_kodu(self):
        from dkds.__main__ import on_hesapla

        with tempfile.TemporaryDirectory() as bos, contextlib.redirect_stderr(io.StringIO()):
            self.assertEqual(on_hesapla(["--veri", bos]), 1)


if __name__ == "__main__":
    unittest.main()
