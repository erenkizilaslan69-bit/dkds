"""Uçtan uca test: PyMuPDF ile örnek bir PDF üretir ve metin çıkarmayı dener.

PyMuPDF kurulu değilse bu test otomatik olarak atlanır.
"""
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


@unittest.skipIf(fitz is None, "PyMuPDF kurulu değil")
class CikarimTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.klasor = tempfile.TemporaryDirectory()
        cls.pdf = Path(cls.klasor.name) / "ornek.pdf"
        # Gövde metni her sayfada farklı olmalı: aynı metin her sayfada aynı
        # yükseklikte tekrar ederse üst/alt bilgi sayılıp (doğru olarak) silinir.
        konular = ["Gunes", "Ay", "Dunya", "Mevsimler"]
        doc = fitz.open()
        for s, konu in enumerate(konular, start=1):
            sayfa = doc.new_page()  # A4: 595 x 842
            sayfa.insert_text((50, 30), "FEN BILIMLERI 5", fontsize=9)
            sayfa.insert_text(
                (50, 120),
                f"{konu} konusundaki bu ornek paragrafta kitap-\nlar kelimesi iki satira bolunmustur.",
                fontsize=11,
            )
            sayfa.insert_text((50, 300), f"{konu} hakkinda ikinci paragraf yer alir.", fontsize=11)
            sayfa.insert_text((290, 825), str(s + 10), fontsize=9)
        doc.save(cls.pdf)
        doc.close()

        from dkds.cikarim import pdf_oku

        cls.sonuc = pdf_oku(cls.pdf, ocr=False)

    @classmethod
    def tearDownClass(cls):
        cls.klasor.cleanup()

    def test_sayfa_sayisi(self):
        self.assertEqual(self.sonuc.sayfa_sayisi, 4)

    def test_her_sayfada_iki_paragraf(self):
        for s in range(1, 5):
            sayfa_p = [p for p in self.sonuc.paragraflar if p.sayfa == s]
            self.assertEqual([p.paragraf for p in sayfa_p], [1, 2], f"sayfa {s}")

    def test_ust_alt_bilgi_yok(self):
        metinler = " ".join(p.metin for p in self.sonuc.paragraflar)
        self.assertNotIn("FEN BILIMLERI", metinler)
        self.assertNotIn("11", metinler)

    def test_tireleme_temizlendi(self):
        ilk = self.sonuc.paragraflar[0].metin
        self.assertIn("kitaplar kelimesi", ilk)
        self.assertNotIn("\n", ilk)

    def test_konum_bilgisi_var(self):
        x0, y0, x1, y1 = self.sonuc.paragraflar[0].konum
        self.assertLess(x0, x1)
        self.assertLess(y0, y1)


if __name__ == "__main__":
    unittest.main()
