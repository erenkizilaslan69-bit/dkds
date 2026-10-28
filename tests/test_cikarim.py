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

    def test_paragraf_turu_atanir(self):
        turler = {p.tur for p in self.sonuc.paragraflar}
        self.assertEqual(turler, {"govde"})

    def test_konum_bilgisi_var(self):
        x0, y0, x1, y1 = self.sonuc.paragraflar[0].konum
        self.assertLess(x0, x1)
        self.assertLess(y0, y1)


class SahteSayfa:
    """PyMuPDF sayfasını taklit eder: "�" içeren çıkarım ile kod numaralı çıkarımı ayrı yanıtlar."""

    def __init__(self, bozuk_metin, kodlu_metin):
        self.bozuk_metin, self.kodlu_metin = bozuk_metin, kodlu_metin
        self.cid_cagrisi = 0

    def get_text(self, tur=None, flags=0, sort=False, textpage=None):
        if tur is None:
            return "x" * 100  # metin katmanı var, taranmış sayfa değil
        cid = bool(flags & fitz.TEXT_CID_FOR_UNKNOWN_UNICODE)
        self.cid_cagrisi += cid
        metin = self.kodlu_metin if cid else self.bozuk_metin
        return [(50.0, 100.0, 500.0, 120.0, metin, 0, 0)]

    def get_images(self):
        return []


@unittest.skipIf(fitz is None, "PyMuPDF kurulu değil")
class KodlamaOnarimiTest(unittest.TestCase):
    MARS_BOZUK = "Korkma, sönmez bu �afaklarda yüzen al sancak; O benim milletimin y�ld�z�d�r."
    MARS_KODLU = "Korkma, sönmez bu úafaklarda yüzen al sancak; O benim milletimin yÕldÕzÕdÕr, parlayacak;"

    def bloklar(self, sayfa):
        from dkds.cikarim import _sayfa_bloklari

        uyarilar = []
        bloklar, _ = _sayfa_bloklari(sayfa, 3, ocr=False, dil="tur", uyarilar=uyarilar)
        return bloklar, uyarilar

    def test_eski_turkce_kodlama_onarilir(self):
        bloklar, uyarilar = self.bloklar(SahteSayfa(self.MARS_BOZUK, self.MARS_KODLU))
        self.assertEqual(len(bloklar), 1)
        self.assertIn("şafaklarda", bloklar[0].metin)
        self.assertIn("yıldızıdır", bloklar[0].metin)
        self.assertNotIn("�", bloklar[0].metin)
        self.assertEqual((bloklar[0].sayfa, bloklar[0].y0), (3, 100.0))  # konum korunur
        self.assertEqual(len(uyarilar), 1)
        self.assertIn("onarıldı", uyarilar[0])

    def test_onarilamayan_sayfa_eski_haliyle_kalir(self):
        # harita simgeleri: eşlemede olmayan karakterler çoğunlukta
        kodlu = "Ä" * 100 + " úafak ú÷ Õ"
        bloklar, uyarilar = self.bloklar(SahteSayfa("�" * 10 + " harita", kodlu))
        self.assertIn("�", bloklar[0].metin)
        self.assertEqual(uyarilar, [])  # uyarıyı pdf_oku "bozuk kodlama" olarak verir

    def test_bozuk_karakter_yoksa_ikinci_cikarim_yapilmaz(self):
        sayfa = SahteSayfa("Normal bir sayfa metni.", "kullanılmamalı")
        bloklar, uyarilar = self.bloklar(sayfa)
        self.assertEqual(bloklar[0].metin, "Normal bir sayfa metni.")
        self.assertEqual((sayfa.cid_cagrisi, uyarilar), (0, []))


if __name__ == "__main__":
    unittest.main()
