"""Komut satırı uçtan uca testi: PDF -> çıkarım -> yazım + okunabilirlik analizi -> JSON ve ekran özeti."""
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

KOLAY = ("Ali topu attı. Ayşe topu tuttu. Ali koştu. Ayşe güldü. Top suya düştü. Hep birlikte eve gittik. "
         "Hava çok güzel. Kuş öttü. Biz okula gittik. Dersler başladı. Ali çok sevindi. Ayşe de sevindi. "
         "Gün güzel geçti. Akşam eve döndük. Hava çok güzeldi.")
ZOR = ("Okulumuzdaki öğretmenlerin çocuklarımıza kazandırmaya çalıştıkları davranışların sürekliliğini "
       "sağlayabilmek amacıyla öğrencilerimizin ailelerinin eğitim süreçlerine katılımlarını "
       "değerlendirebilecek göstergeleri belirlemeleri, bu doğrultuda okul yönetimlerinin velilerle "
       "düzenli görüşmeler gerçekleştirmesi, ayrıca öğrencilerin evde yaptıkları çalışmaların düzenli "
       "kontrol edilmesi ve sınıf öğretmenlerinin bu sürecin her aşamasında aktif rol almaları "
       "gerekmektedir.")


@unittest.skipIf(fitz is None, "PyMuPDF kurulu değil")
class AnalizKomutuTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.klasor = tempfile.TemporaryDirectory()
        cls.pdf = Path(cls.klasor.name) / "ornek.pdf"
        doc = fitz.open()
        for sayfa_no, metinler in enumerate(((KOLAY, ZOR), (ZOR + " Kuvvet ve ve hareket.", KOLAY)), start=1):
            sayfa = doc.new_page()
            for i, metin in enumerate(metinler):
                sayfa.insert_textbox(fitz.Rect(50, 100 + i * 200, 545, 280 + i * 200), metin, fontsize=11)
        doc.save(cls.pdf)
        doc.close()

    @classmethod
    def tearDownClass(cls):
        cls.klasor.cleanup()

    def calistir(self, *ek):
        from dkds.__main__ import analiz

        cikti = Path(self.klasor.name) / "bulgular.json"
        ekran = io.StringIO()
        with contextlib.redirect_stdout(ekran):
            kod = analiz([str(self.pdf), "-o", str(cikti), *ek])
        return kod, ekran.getvalue(), json.loads(cikti.read_text(encoding="utf-8"))

    def test_sinif_verilince_iki_analizor_calisir(self):
        kod, ekran, kayit = self.calistir("--sinif", "5")
        self.assertEqual(kod, 0)
        kriterler = {b["kriter"] for b in kayit["bulgular"]}
        self.assertEqual(kriterler, {"yazim", "okunabilirlik"})
        okunabilirlik = [b for b in kayit["bulgular"] if b["kriter"] == "okunabilirlik"]
        self.assertEqual(sorted(b["sayfa"] for b in okunabilirlik), [1, 2])  # iki sayfadaki zor metin
        self.assertIn("tekrar", {b["tur"] for b in kayit["bulgular"]})  # "ve ve" yazım bulgusu

    def test_json_ozeti(self):
        _, _, kayit = self.calistir("--sinif", "5")
        ozet = kayit["okunabilirlik_ozeti"]
        self.assertEqual((ozet["sinif"], ozet["birim_sayisi"]), (5, 4))
        self.assertIn("puan", ozet["atesman"])
        self.assertIn("duzey", ozet["bezirci_yilmaz"])
        self.assertEqual(len(ozet["en_zor_paragraflar"]), 4)
        self.assertLess(ozet["en_zor_paragraflar"][0]["atesman"], ozet["en_zor_paragraflar"][-1]["atesman"])

    def test_ekran_ozeti(self):
        _, ekran, _ = self.calistir("--sinif", "5")
        for parca in ("okunabilirlik", "Okunabilirlik özeti (5. sınıf kitabı)", "Ateşman", "Bezirci-Yılmaz",
                      "En zor 4 paragraf", "yazim"):
            self.assertIn(parca, ekran)

    def test_sinif_verilmezse_yalnizca_yazim(self):
        _, ekran, kayit = self.calistir()
        self.assertEqual({b["kriter"] for b in kayit["bulgular"]}, {"yazim"})
        self.assertNotIn("okunabilirlik_ozeti", kayit)
        self.assertIn("--sinif 5", ekran)

    def test_gecersiz_sinif_reddedilir(self):
        with self.assertRaises(SystemExit), contextlib.redirect_stderr(io.StringIO()):
            self.calistir("--sinif", "13")


if __name__ == "__main__":
    unittest.main()
