"""Streamlit demo panelinin (app.py) temel akış testi: streamlit.testing.v1.AppTest.

Gerçek kitaplara bağlı değildir: geçici bir veri/ ve cikti/ klasörü kurulur (örnek PDF + gerçek analiz kaydı),
app.py bu klasörleri DKDS_VERI / DKDS_CIKTI ortam değişkenleriyle kullanır.
"""
import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest import mock

try:
    import pymupdf as fitz
except ImportError:
    try:
        import fitz
    except ImportError:
        fitz = None

try:
    from streamlit.testing.v1 import AppTest
except ImportError:
    AppTest = None

APP = str(Path(__file__).resolve().parent.parent / "app.py")

# fen5 s.31'in gerçek hatası ("hedeflenmektedi .") ve iki sayfada çelişen tarih içeren örnek kitap
S31 = ("Türkiye, uzay alanındaki yeteneklerini ve teknolojik kapasitesini artırmak amacıyla bir program başlatmıştır. "
       "Projenin hayata geçmesi ile birlikte uzay ile ilgili daha birçok alanda başarı sağlanması hedeflenmektedi .")
S31 = S31.translate(str.maketrans("ğşıĞŞİ", "gsiGSI"))  # PDF'e yazılan yerleşik yazı tipi bu harfleri taşımaz


def ornek_kitap(klasor: Path) -> None:
    """veri/fen5.pdf (31 sayfa) ve cikti/fen5_bulgular.json (gerçek analiz) oluşturur."""
    from dkds.is_akisi import kitabi_analiz_et

    (klasor / "veri").mkdir()
    (klasor / "cikti").mkdir()
    pdf = klasor / "veri" / "fen5.pdf"
    belge = fitz.open()
    for no in range(1, 32):
        sayfa = belge.new_page()
        if no == 31:
            sayfa.insert_textbox(fitz.Rect(60, 400, 540, 520), S31, fontsize=11)
        else:
            sayfa.insert_textbox(fitz.Rect(60, 100, 540, 200), "Kuvvet hareketi değiştirebilir.", fontsize=11)
    belge.save(pdf)
    belge.close()
    kayit = kitabi_analiz_et(pdf, 5)
    (klasor / "cikti" / "fen5_bulgular.json").write_text(json.dumps(kayit, ensure_ascii=False), encoding="utf-8")


@unittest.skipIf(fitz is None or AppTest is None, "PyMuPDF ya da streamlit kurulu değil")
class PanelAkisiTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.klasor = tempfile.TemporaryDirectory()
        cls.kok = Path(cls.klasor.name)
        ornek_kitap(cls.kok)

    @classmethod
    def tearDownClass(cls):
        cls.klasor.cleanup()

    def setUp(self):
        # tıklama/süzgeç değişince panel yeniden çalışır: ortam testin sonuna kadar geçerli kalmalı
        self.enterContext(mock.patch.dict(os.environ, {"DKDS_CIKTI": str(self.kok / "cikti"),
                                                       "DKDS_VERI": str(self.kok / "veri")}))

    def ac(self) -> "AppTest":
        at = AppTest.from_file(APP, default_timeout=60).run()
        self.assertEqual(len(at.exception), 0, [e.value for e in at.exception])
        return at

    def metinler(self, at) -> str:
        return "\n".join(m.value for m in at.markdown)

    def test_acilista_ozet_ve_uc_sekme(self):
        at = self.ac()
        self.assertEqual([t.label for t in at.tabs], ["📊 Özet", "🔎 Bulgular", "⭐ Öne çıkan bulgular"])
        self.assertEqual(at.title[0].value, "DKDS – Ders Kitabı Denetim Sistemi")
        etiketler = [m.label for m in at.metric]
        for beklenen in ("Toplam bulgu", "Yazım", "Okunabilirlik", "Tutarlılık", "Aday çelişki"):
            self.assertIn(beklenen, etiketler)
        # örnek kitapta ölçülecek gövde metni yok: puan yerine açıklama gösterilir (çökmez)
        self.assertIn("okunabilirlik puanı hesaplanamadı", " ".join(i.value for i in at.info))
        self.assertEqual(at.sidebar.selectbox(key="hazir_kitap").value, "fen5")
        self.assertIn("fen5 (5. sınıf)", at.sidebar.selectbox(key="hazir_kitap").format_func("fen5"))

    def test_bulgu_tablosu_ve_suzgecler(self):
        at = self.ac()
        sayi = lambda a: next(m for m in (x.value for x in a.markdown) if "bulgu gösteriliyor" in m)  # noqa: E731
        self.assertIn("(toplam ", sayi(at))
        toplam = int(sayi(at).split("**")[1])
        # güven eşiğini 1'e çekince hiç bulgu kalmaz ve kullanıcıya söylenir
        at.slider(key="f_guven").set_value(1.0).run()
        self.assertEqual(len(at.exception), 0)
        self.assertIn("**0** bulgu gösteriliyor", sayi(at))
        self.assertIn("Bu süzgeçle bulgu yok", " ".join(i.value for i in at.info))
        # kriter süzgeci: yalnızca okunabilirlik
        at.slider(key="f_guven").set_value(0.0)
        at.multiselect(key="f_kriter").set_value(["okunabilirlik"]).run()
        okunabilirlik = int(sayi(at).split("**")[1])
        self.assertLessEqual(okunabilirlik, toplam)
        # çıkarım sorunları varsayılan olarak gizli, kutu işaretlenince tabloya girer
        self.assertFalse(at.checkbox(key="f_cikarim").value)
        self.assertNotIn("cikarim_sorunu", at.multiselect(key="f_tur").value)

    def test_indirme_dugmeleri_var(self):
        at = self.ac()
        indirmeler = at.get("download_button")
        self.assertEqual(sorted(d.proto.label for d in indirmeler), ["CSV indir", "Excel indir"])

    def test_one_cikan_bulgu_tek_tikla_sayfayi_acar(self):
        at = self.ac()
        # örnek kitapta yalnızca fen5 var: diğer kitapların düğmeleri pasif
        self.assertFalse(at.button(key="oc_fen5_s31").disabled)
        self.assertTrue(at.button(key="oc_sosyal5_catalhoyuk").disabled)
        at.button(key="oc_fen5_s31").click().run()
        self.assertEqual(len(at.exception), 0, [e.value for e in at.exception])
        metin = self.metinler(at)
        self.assertIn("fen5 s.31 – yarım kalmış kelime", " ".join(h.value for h in at.subheader))
        self.assertIn("hedeflenmektedi", " ".join(i.value for i in at.info))  # sorunlu metin kutusu
        self.assertIn("sayfa 31", metin)
        self.assertEqual(len(at.get("image")), 1)  # sayfa görüntüsü
        self.assertEqual(len(at.warning), 0)

    def test_pdf_yoksa_uyari_verir_ama_bozulmaz(self):
        with tempfile.TemporaryDirectory() as bos:
            os.environ["DKDS_VERI"] = bos
            at = self.ac()
            at.button(key="oc_fen5_s31").click().run()
            self.assertEqual(len(at.exception), 0)
            self.assertIn("PDF bulunamadı", " ".join(w.value for w in at.warning))

    def test_yeni_pdf_yukle_secenegi_analiz_dugmesi_pasif(self):
        at = self.ac()
        at.sidebar.radio(key="kaynak_turu").set_value("Yeni PDF yükle").run()
        self.assertEqual(len(at.exception), 0)
        self.assertTrue(at.sidebar.button(key="analiz_et").disabled)  # dosya seçilmeden
        self.assertIn("Soldan bir kitap seçin", " ".join(i.value for i in at.info))

    def test_hazir_analiz_yoksa_yonlendirir(self):
        with tempfile.TemporaryDirectory() as bos:
            os.environ.update({"DKDS_CIKTI": bos, "DKDS_VERI": bos})
            at = AppTest.from_file(APP, default_timeout=60).run()
            self.assertEqual(len(at.exception), 0)
            self.assertIn("on_hesapla", " ".join(e.value for e in at.sidebar.error))


if __name__ == "__main__":
    unittest.main()
