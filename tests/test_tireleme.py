"""Satır sonu tirelemesi: yumuşak tire (U+00AD), Unicode tire çeşitleri ve eski yazı tipi ı kodu."""
import unittest

from dkds.temizleme import temizle


class YumusakTireTest(unittest.TestCase):
    def test_satir_sonu_yumusak_tire_sozcugu_birlestirir(self):
        # biyoloji9.pdf: satır sonlarındaki U+00AD "sindi rerek", "ola rak", "hüc reli" diye bölünüyordu
        self.assertEqual(temizle("sindi­\nrerek karşılar"), "sindirerek karşılar")
        self.assertEqual(temizle("kaynakların­\ndan uzak tut"), "kaynaklarından uzak tut")
        self.assertEqual(temizle("ola­ \n rak hazırlanan"), "olarak hazırlanan")
        self.assertEqual(temizle("Mikro­\nOrganizma"), "MikroOrganizma")  # yumuşak tire her zaman görünmezdir

    def test_satir_ortasindaki_yumusak_tire_silinir(self):
        self.assertEqual(temizle("de­ne­me"), "deneme")


class UnicodeTireTest(unittest.TestCase):
    def test_tire_cesitleri_satir_sonunda_tireleme_sayilir(self):
        for tire in ("-", "‐", "‑"):
            with self.subTest(tire=hex(ord(tire))):
                self.assertEqual(temizle(f"kitap{tire}\nlar"), "kitaplar")  # alt satır küçük harf: birleşir

    def test_gercek_tire_korunur(self):
        # alt satır büyük harfle başlıyorsa tire gerçektir ("Kuzey-Güney"); Unicode tire ASCII tireye çevrilir
        for tire in ("-", "‐", "‑"):
            with self.subTest(tire=hex(ord(tire))):
                self.assertEqual(temizle(f"Kuzey{tire}\nGüney"), "Kuzey-Güney")

    def test_eksi_ve_kisa_cizgi_tireleme_degildir(self):
        # U+2212 (eksi) ve U+2013 (kısa çizgi) tablo hücresi/aralık işaretidir, sözcük bölmez
        self.assertEqual(temizle("sıcaklık −\n5 derece"), "sıcaklık − 5 derece")
        self.assertEqual(temizle("1990 –\nbugün"), "1990 – bugün")


class EskiYaziTipiTest(unittest.TestCase):
    def test_ozel_kullanim_kodu_dotsuz_i_olur(self):
        # fen3 s.5 (Öğrenci Andı), biyoloji9 s.3-4 (İstiklal Marşı): U+F0F5 = ı
        self.assertEqual(temizle("Türküm, doğruyum, çalşkanm."), "Türküm, doğruyum, çalışkanım.")


if __name__ == "__main__":
    unittest.main()
