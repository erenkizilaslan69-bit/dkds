"""Demo panelinin Streamlit'ten bağımsız işlevleri: kayıt okuma, süzme, dışa aktarma, sayfa işaretleme."""
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

from dkds import panel
from dkds.one_cikan import ONE_CIKANLAR, one_cikani_bul


def bulgu(sayfa=1, kriter="yazim", tur="bilinmeyen_kelime", guven=0.5, **ek):
    return {"sayfa": sayfa, "paragraf": 1, "kriter": kriter, "tur": tur, "sorunlu_metin": "örnek",
            "aciklama": "Açıklama ğüşiöç.", "guven": guven, "oneri": None, "konum": [50, 100, 300, 160],
            "ilgili_sayfa": None, "ilgili_paragraf": None, "ilgili_konum": None, **ek}


BULGULAR = [
    bulgu(1, "yazim", "bilinmeyen_kelime", 0.5),
    bulgu(2, "yazim", "noktalama_oncesi_bosluk", 0.9),
    bulgu(3, "yazim", "karakter_kaybi", 0.8),
    bulgu(4, "okunabilirlik", "sinif_ustu", 0.7),
    bulgu(5, "okunabilirlik", "cikarim_sorunu", 0.3),
    bulgu(6, "tutarlilik", "tarih_celiskisi", 0.45, ilgili_sayfa=2),
]


class SuzmeTest(unittest.TestCase):
    def test_cikarim_sorunlari_varsayilan_olarak_gizli(self):
        sonuc = panel.bulgulari_suz(BULGULAR)
        self.assertEqual([b["sayfa"] for b in sonuc], [1, 2, 4, 6])
        self.assertTrue(all(b["tur"] not in panel.CIKARIM_TURLERI for b in sonuc))

    def test_cikarim_sorunlari_istenince_gorunur(self):
        self.assertEqual(len(panel.bulgulari_suz(BULGULAR, cikarim_sorunlarini_goster=True)), 6)

    def test_kriter_tur_ve_guven_suzgeci(self):
        self.assertEqual([b["sayfa"] for b in panel.bulgulari_suz(BULGULAR, kriterler=["okunabilirlik"])], [4])
        self.assertEqual([b["sayfa"] for b in panel.bulgulari_suz(BULGULAR, turler=["tarih_celiskisi"])], [6])
        self.assertEqual([b["sayfa"] for b in panel.bulgulari_suz(BULGULAR, en_dusuk_guven=0.7)], [2, 4])
        self.assertEqual(panel.bulgulari_suz(BULGULAR, kriterler=[]), [])

    def test_guven_sayilari_ve_varsayilan_esik(self):
        self.assertEqual(panel.VARSAYILAN_EN_DUSUK_GUVEN, 0.5)
        self.assertEqual(panel.guven_sayilari(BULGULAR), (4, 2))  # 0.9, 0.8, 0.7, 0.5 yüksek; 0.45, 0.3 düşük
        self.assertEqual(panel.guven_sayilari([]), (0, 0))
        # varsayılan eşik 0,5'lik (1-2 kez geçen) bilinmeyen kelime bulgusunu GÖSTERİR, alan terimi olasılığı olan
        # 0,3'lük bulguyu ve çıkarım türlerini gizler
        sonuc = panel.bulgulari_suz(BULGULAR, en_dusuk_guven=panel.VARSAYILAN_EN_DUSUK_GUVEN)
        self.assertEqual([b["sayfa"] for b in sonuc], [1, 2, 4])

    def test_turkce_adlar(self):
        self.assertEqual(panel.kriter_adi("tutarlilik"), "Tutarlılık")
        self.assertEqual(panel.tur_adi("cikarim_sorunu"), "Olası metin çıkarma sorunu")
        self.assertEqual(panel.tur_adi("bilinmeyen_yeni_tur"), "bilinmeyen_yeni_tur")  # bilinmeyen türde ham ad


class DisaAktarmaTest(unittest.TestCase):
    def setUp(self):
        self.satirlar = panel.tablo_satirlari(BULGULAR[:2], "fen5")

    def test_satirlar_turkce_sutunlu(self):
        self.assertEqual(tuple(self.satirlar[0]), panel.SUTUNLAR)
        self.assertEqual(self.satirlar[0]["Kitap"], "fen5")
        self.assertEqual(self.satirlar[1]["Tür"], "Noktalama öncesi boşluk")

    def test_csv_excel_icin_bomlu_utf8_ve_noktalı_virgul(self):
        veri = panel.csv_bayt(self.satirlar)
        self.assertTrue(veri.startswith(b"\xef\xbb\xbf"))
        satirlar = veri.decode("utf-8-sig").splitlines()
        self.assertEqual(satirlar[0].split(";"), list(panel.SUTUNLAR))
        self.assertIn("Açıklama ğüşiöç.", satirlar[1])
        self.assertEqual(len(satirlar), 3)

    def test_excel_geri_okunur(self):
        from openpyxl import load_workbook

        sayfa = load_workbook(io.BytesIO(panel.excel_bayt(self.satirlar))).active
        self.assertEqual([h.value for h in sayfa[1]], list(panel.SUTUNLAR))
        self.assertEqual(sayfa.max_row, 3)
        self.assertEqual(sayfa.cell(2, 9).value, 0.5)  # Güven
        self.assertEqual(sayfa.cell(2, 7).value, "Açıklama ğüşiöç.")


class KayitTest(unittest.TestCase):
    def test_hazir_kayitlar_yalniz_analiz_ciktilarini_alir(self):
        with tempfile.TemporaryDirectory() as klasor:
            k = Path(klasor)
            (k / "fen5_bulgular.json").write_text(json.dumps({"bulgular": [], "sinif": 5}), encoding="utf-8")
            (k / "eski_bulgular.json").write_text(json.dumps({"bulgular": []}), encoding="utf-8")  # sınıf alanı yok
            (k / "fen5.json").write_text(json.dumps({"paragraflar": []}), encoding="utf-8")  # ham çıkarım
            (k / "bozuk_bulgular.json").write_text("{", encoding="utf-8")
            self.assertEqual(list(panel.hazir_kayitlar(k)), ["fen5"])

    def test_kitap_etiketi_ve_pdf_yolu(self):
        self.assertEqual(panel.kitap_etiketi("fen5", {"sinif": 5}), "fen5 (5. sınıf)")
        self.assertEqual(panel.kitap_etiketi("x"), "x")
        with tempfile.TemporaryDirectory() as klasor:
            self.assertIsNone(panel.pdf_yolu({"kaynak": "yok.pdf"}, Path(klasor)))
            (Path(klasor) / "var.pdf").write_bytes(b"%PDF")
            self.assertEqual(panel.pdf_yolu({"kaynak": "var.pdf"}, Path(klasor)), Path(klasor) / "var.pdf")


@unittest.skipIf(fitz is None, "PyMuPDF kurulu değil")
class SayfaIsaretlemeTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.belge = fitz.open()
        cls.sayfa = cls.belge.new_page()
        cls.sayfa.insert_text((60, 120), "Bu cumle hedeflenmektedi . diye bitiyor ve devam ediyor.", fontsize=11)
        cls.sayfa.insert_text((60, 300), "Cumle MO 7500 yilinda kurulmustur.", fontsize=11)
        cls.kutu = (50, 105, 400, 130)

    def test_kelime_kutusu_paragraf_icinde_bulunur(self):
        kutular = panel.kelime_kutulari(self.sayfa, self.kutu, "hedeflenmektedi .")  # sonda boşluk+nokta düşürülür
        self.assertEqual(len(kutular), 1)
        x0, y0, x1, y1 = kutular[0]
        self.assertTrue(self.kutu[0] <= x0 and x1 <= self.kutu[2] and self.kutu[1] <= y0 and y1 <= self.kutu[3])
        self.assertIn("hedeflenmektedi", self.sayfa.get_textbox(fitz.Rect(kutular[0]) + (-1, -1, 1, 1)))

    def test_ifade_paragraf_disindaysa_bulunmaz(self):
        self.assertEqual(panel.kelime_kutulari(self.sayfa, self.kutu, "kurulmustur"), [])
        self.assertEqual(panel.kelime_kutulari(self.sayfa, self.kutu, None), [])

    def test_png_uretilir_ve_belge_degismez(self):
        isaret = panel.Isaret(1, self.kutu, "hedeflenmektedi")
        ilk = panel.sayfayi_isaretle(self.belge, isaret)
        ikinci = panel.sayfayi_isaretle(self.belge, panel.Isaret(1, self.kutu, "hedeflenmektedi"))
        self.assertTrue(ilk.startswith(b"\x89PNG"))
        self.assertEqual(ilk, ikinci)  # işaretler geçici: art arda çağrı aynı görüntüyü verir
        self.assertEqual(len(list(self.sayfa.annots())), 0)
        isaretsiz = self.sayfa.get_pixmap(matrix=fitz.Matrix(1.5, 1.5)).tobytes("png")
        self.assertNotEqual(ilk, isaretsiz)  # kırmızı kutu görüntüye gerçekten çizilmiş

    def test_yakinlastirma_gorseli_kucultur(self):
        tam = fitz.Pixmap(panel.sayfayi_isaretle(self.belge, panel.Isaret(1, self.kutu)))
        kesit = fitz.Pixmap(panel.sayfayi_isaretle(self.belge, panel.Isaret(1, self.kutu), yakinlastir=True))
        self.assertLess(kesit.height, tam.height)
        self.assertEqual(kesit.width, tam.width)

    def test_pdf_baytindan_acilir(self):
        belge = panel.acik_belge(self.belge.tobytes())
        self.assertEqual(belge.page_count, 1)

    def test_bulgu_isaretleri_yazimda_sorunlu_kelimeyi_arar_tutarlilikta_iki_sayfa(self):
        yazim = panel.bulgu_isaretleri(bulgu(1, sorunlu_metin="hedeflenmektedi ."))
        self.assertEqual([(i.sayfa, i.ara) for i in yazim], [(1, "hedeflenmektedi .")])
        uzun = panel.bulgu_isaretleri(bulgu(1, sorunlu_metin="x" * 60))
        self.assertIsNone(uzun[0].ara)  # uzun cümlede yalnızca paragraf kutusu
        tutarlilik = panel.bulgu_isaretleri(
            bulgu(118, "tutarlilik", "tarih_celiskisi", ilgili_sayfa=112, ilgili_konum=[10, 20, 30, 40]),
            ek=[(147, "9 500 yıl önce")], ara={118: "yaklaşık 9000 yıl önce"})
        self.assertEqual([i.sayfa for i in tutarlilik], [118, 112, 147])
        self.assertEqual(tutarlilik[0].ara, "yaklaşık 9000 yıl önce")
        self.assertEqual(tutarlilik[1].paragraf, (10, 20, 30, 40))
        self.assertIsNone(tutarlilik[2].paragraf)


@unittest.skipUnless(Path("cikti/fen5_bulgular.json").exists() and Path("veri/fen5.pdf").exists(),
                     "gerçek kitaplar ve hazır analizler (veri/, cikti/) yok")
class OneCikanBulgularGercekKitaplarTest(unittest.TestCase):
    """Sunumda kullanılan her öne çıkan bulgu doğru kitapta, doğru sayfada ve doğru kutuyla gösterilmeli."""

    def test_her_oge_dogru_sayfa_ve_kutuyu_gosterir(self):
        hazir = panel.hazir_kayitlar(Path("cikti"))
        for oge in ONE_CIKANLAR:
            with self.subTest(oge=oge.anahtar):
                self.assertIn(oge.kitap, hazir)
                kayit = panel.kayit_yukle(hazir[oge.kitap])
                b = one_cikani_bul(kayit["bulgular"], oge)
                self.assertIsNotNone(b, "öne çıkan bulgu hazır analizde bulunamadı")
                belge = panel.acik_belge(panel.pdf_yolu(kayit, Path("veri")))
                isaretler = panel.bulgu_isaretleri(b, list(oge.ek), oge.ara)
                self.assertEqual(sorted(i.sayfa for i in isaretler), sorted(oge.beklenen))
                for isaret in isaretler:
                    resim = panel.sayfayi_isaretle(belge, isaret)
                    self.assertTrue(resim.startswith(b"\x89PNG"))
                    sayfa = belge[isaret.sayfa - 1]
                    metinler = [sayfa.get_textbox(fitz.Rect(k) + (-1, -1, 1, 1)) for k in isaret.kelimeler]
                    if isaret.paragraf:
                        metinler.append(sayfa.get_textbox(fitz.Rect(isaret.paragraf)))
                    birlesik = " ".join(" ".join(m.split()) for m in metinler)
                    self.assertIn(oge.beklenen[isaret.sayfa], birlesik)
                    if isaret.ara:
                        self.assertEqual(len(isaret.kelimeler) >= 1, True, f"s.{isaret.sayfa}: «{isaret.ara}» bulunamadı")
                belge.close()


class VarsayilanFiltreSentetikTest(unittest.TestCase):
    """Gerçek hatalar (1-2 kez geçen bilinmeyen kelime, 0,5 güven) varsayılan süzgeçte görünür; alan terimleri gizlenir."""

    def test_gercek_hatalar_gorunur_alan_terimi_gizli(self):
        hatalar = [bulgu(79, tur="bilinmeyen_kelime", sorunlu_metin="öğretmlerimiz", guven=0.5),
                   bulgu(37, tur="bilinmeyen_kelime", sorunlu_metin="anektod", guven=0.5),
                   bulgu(31, tur="noktalama_oncesi_bosluk", sorunlu_metin="hedeflenmektedi .", guven=0.9),
                   bulgu(124, tur="noktalama_oncesi_bosluk", sorunlu_metin="sınıflandırılı .", guven=0.9)]
        terim = bulgu(5, tur="bilinmeyen_kelime", sorunlu_metin="ökaryot", guven=0.3)
        gorunen = panel.bulgulari_suz(hatalar + [terim], en_dusuk_guven=panel.VARSAYILAN_EN_DUSUK_GUVEN)
        self.assertEqual([b["sorunlu_metin"] for b in gorunen], [b["sorunlu_metin"] for b in hatalar])


@unittest.skipUnless(Path("cikti/fen5_bulgular.json").exists() and Path("cikti/sosyalbilgiler5_bulgular.json").exists(),
                     "hazır analizler (cikti/) yok")
class VarsayilanFiltreGercekKitaplarTest(unittest.TestCase):
    def gorunenler(self, kitap):
        kayit = panel.kayit_yukle(panel.hazir_kayitlar(Path("cikti"))[kitap])
        return panel.bulgulari_suz(kayit["bulgular"], en_dusuk_guven=panel.VARSAYILAN_EN_DUSUK_GUVEN)

    def test_dort_gercek_hata_varsayilan_tabloda_gorunur(self):
        beklenen = {"fen5": [(31, "hedeflenmektedi"), (124, "sınıflandırılı")],
                    "sosyalbilgiler5": [(79, "öğretmlerimiz"), (37, "anektod")]}
        for kitap, hatalar in beklenen.items():
            gorunen = self.gorunenler(kitap)
            for sayfa, kelime in hatalar:
                with self.subTest(kitap=kitap, kelime=kelime):
                    self.assertTrue(any(b["sayfa"] == sayfa and kelime in b["sorunlu_metin"] for b in gorunen),
                                    f"{kitap} s.{sayfa} «{kelime}» varsayılan tabloda görünmüyor")


if __name__ == "__main__":
    unittest.main()
