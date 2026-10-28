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
       "sağlayabilmek gerekmektedir. Velilerin eğitim süreçlerine katılımlarını değerlendirebilecek "
       "göstergeleri belirlemeleri, okul yönetimlerinin velilerle düzenli görüşmeler gerçekleştirmesi "
       "gerekmektedir. Öğrencilerin evde yaptıkları çalışmaların kontrol edilmesi sağlanmalıdır. "
       "Sorumluluk paylaşılmalıdır. Aileler bilgilendirilmelidir. Süreç izlenmelidir. Bunlar zorunludur. "
       "Notlar tutulmalıdır. Rapor yazılmalıdır. Ödev verilmelidir.").translate(str.maketrans("ğşıĞŞİ", "gsiGSI"))
# (PDF'e yazılan yerleşik yazı tipi ğ, ş, ı'yı taşımaz; ı→i, ğ→g, ş→s hece sayısını değiştirmez)


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
                      "En zor 4 paragraf", "yazim", "Birim Ateşman", "İşaretlenen     : 2 / 4 birim (%50)",
                      "Referans        : 5. sınıf kitapları (fen5.pdf, sosyalbilgiler5.pdf;"):
            self.assertIn(parca, ekran)
        # birimlerin yarısı referansın %10 diliminin altında (beklenen ≈ %10): kitap genel olarak zor
        self.assertIn("Uyarı: 5. sınıf referansının %10 diliminin altına düşen birim oranı %50 (beklenen ≈ %10)", ekran)

    def ozet_yaz(self, **degisiklik):
        from dkds.__main__ import _okunabilirlik_ozeti_yaz

        ozet = {"sinif": 5, "birim_sayisi": 10, "atlanan": {}, "kelime": 500, "cumle": 50,
                "atesman": {"puan": 55.0, "duzey": "11-12. sınıf"}, "bezirci_yilmaz": {"puan": 13.0, "duzey": "lisans"},
                "ortalama_cumle_uzunlugu": 10.0, "hece_kelime": 2.9, "en_zor_paragraflar": [],
                "atesman_dagilimi": {"medyan": 54.0, "ortalama": 54.0, "std": 14.0, "p10": 35.0, "p90": 72.0},
                "isaretlenen_birim": 1, "isaretlenen_oran": 0.1,
                "referans": {"yontem": "sinif_referansi", "sinif": 5, "p10": 31.7, "ortanca": 49.9, "medyan_farki": 4.1,
                             "ara_deger": False, "kitaplar": ["fen5.pdf"], "birim_sayisi": 144, "kaynak_siniflar": []}}
        ozet.update(degisiklik)
        ekran = io.StringIO()
        with contextlib.redirect_stdout(ekran):
            _okunabilirlik_ozeti_yaz(ozet)
        return ekran.getvalue()

    def test_referans_satiri_ve_beklenen_oranda_uyari_yok(self):
        ekran = self.ozet_yaz()
        self.assertIn("Referans        : 5. sınıf kitapları (fen5.pdf; 144 birim): %10 sınırı 31,7, ortanca 49,9; "
                      "bu kitabın ortancası referanstan +4,1 puan farklı", ekran)
        self.assertIn("İşaretlenen     : 1 / 10 birim (%10)", ekran)
        self.assertNotIn("Uyarı", ekran)

    def test_ara_sinif_referansi_kaynagi(self):
        ekran = self.ozet_yaz(referans={"yontem": "sinif_referansi", "sinif": 6, "p10": 29.4, "ortanca": 47.6,
                                        "medyan_farki": -1.0, "ara_deger": True, "kitaplar": [],
                                        "birim_sayisi": None, "kaynak_siniflar": [5, 7]})
        self.assertIn("6. sınıf kitapları (komşu sınıflardan ara değer)", ekran)
        self.assertIn("-1,0 puan farklı", ekran)

    def test_cok_isaretlenince_uyari_verilir(self):
        ekran = self.ozet_yaz(isaretlenen_birim=4, isaretlenen_oran=0.4)
        self.assertIn("Uyarı: 5. sınıf referansının %10 diliminin altına düşen birim oranı %40 (beklenen ≈ %10): "
                      "kitap, sınıf düzeyinin genelinde üstünde.", ekran)

    def test_kitap_ici_esikte_uyari_verilmez(self):
        ekran = self.ozet_yaz(isaretlenen_birim=9, isaretlenen_oran=0.9,
                              referans={"yontem": "kitap_ici", "sinif": 11, "p10": 20.0, "ortanca": 50.0,
                                        "medyan_farki": 4.0})
        self.assertIn("Referans        : 11. sınıf için referans tablosu yok; kitabın kendi %10 sınırı 20,0 kullanıldı",
                      ekran)
        self.assertNotIn("Uyarı", ekran)

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
