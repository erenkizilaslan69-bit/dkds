import unittest

from dkds.temizleme import dolgu_mu, kodlama_bozuk_mu, temizle


class TemizleTest(unittest.TestCase):
    def test_tireleme_kucuk_harfle_birlesir(self):
        self.assertEqual(temizle("Bu kitap-\nlar çok güzel."), "Bu kitaplar çok güzel.")

    def test_turkce_karakterle_tireleme(self):
        self.assertEqual(temizle("öğren-\nciler"), "öğrenciler")
        self.assertEqual(temizle("fotosen-\nteze"), "fotosenteze")

    def test_gercek_tire_korunur(self):
        self.assertEqual(temizle("Kuzey-\nGüney ekseni"), "Kuzey-Güney ekseni")

    def test_satir_sonlari_bosluga_donusur(self):
        self.assertEqual(temizle("Birinci satır\nikinci satır\n"), "Birinci satır ikinci satır")

    def test_yumusak_tire_ve_ligatur(self):
        self.assertEqual(temizle("de­ne­me ﬁkir"), "deneme fikir")

    def test_coklu_bosluk(self):
        self.assertEqual(temizle("  çok    boşluk \t var  "), "çok boşluk var")


class DolguTest(unittest.TestCase):
    def test_cevap_satirlari_dolgu(self):
        self.assertTrue(dolgu_mu("....................................\n.................................\n"))

    def test_soru_ve_cevap_satiri_dolgu_degil(self):
        self.assertFalse(dolgu_mu("Kuvvet bir cismin yönünü değiştirebilir mi?\n..........\n"))

    def test_metin_icindeki_noktalar_silinir(self):
        self.assertEqual(temizle("Cevap: ..........\nSonraki soru"), "Cevap: Sonraki soru")


class KodlamaTest(unittest.TestCase):
    def test_normal_turkce_metin(self):
        metin = "Işık, bir ortamdan diğerine geçerken kırılır. Bu olaya ışığın kırılması denir."
        self.assertFalse(kodlama_bozuk_mu(metin))

    def test_bozuk_metin(self):
        metin = "õúk bir ortamdan dóerine geçerken kóróló. Bu olaya õúóón kórólmasõ denir õúõú õúõú"
        self.assertTrue(kodlama_bozuk_mu(metin))

    def test_ust_simge_derece(self):
        metin = "Ay'da sıcaklık gece -174 ⁰C'u, gündüz ise 125 ⁰C'u bulabilmektedir."
        self.assertFalse(kodlama_bozuk_mu(metin))

    def test_taninmayan_karakter(self):
        self.assertTrue(kodlama_bozuk_mu("Normal metin � ile"))

    def test_kisa_metin_degerlendirilmez(self):
        self.assertFalse(kodlama_bozuk_mu("õúõú"))


if __name__ == "__main__":
    unittest.main()
