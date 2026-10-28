import unittest

from dkds.temizleme import (
    ONARIM_ESIGI,
    dolgu_mu,
    eski_turkce_kodlamayi_cevir,
    harf_iceriyor_mu,
    kodlama_bozuk_mu,
    kodlamayi_onar,
    temizle,
)


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

    def test_tek_sekme_bosluga_donusur(self):
        # fen5.pdf s.14: madde imlerinden sonra tek sekme geliyor
        self.assertEqual(temizle("•\tLaboratuvara girmeden önce"), "• Laboratuvara girmeden önce")


class DolguTest(unittest.TestCase):
    def test_cevap_satirlari_dolgu(self):
        self.assertTrue(dolgu_mu("....................................\n.................................\n"))

    def test_soru_ve_cevap_satiri_dolgu_degil(self):
        self.assertFalse(dolgu_mu("Kuvvet bir cismin yönünü değiştirebilir mi?\n..........\n"))

    def test_uzun_cevap_satirlari_soruyu_sildirmez(self):
        # fen5.pdf s.20: soru ve altındaki üç uzun cevap satırı tek blokta geliyor
        nokta = "." * 125 + "\n"
        self.assertFalse(dolgu_mu("Dünya’nın dönme hareketi hakkında bildiklerinizi yazınız.\n" + nokta * 3))

    def test_alt_cizgi_ve_uc_nokta_dolgu(self):
        self.assertTrue(dolgu_mu("______________\n…………………\n"))

    def test_metin_icindeki_noktalar_silinir(self):
        self.assertEqual(temizle("Cevap: ..........\nSonraki soru"), "Cevap: Sonraki soru")


class HarfTest(unittest.TestCase):
    def test_sayi_ve_simge_harf_icermez(self):
        for metin in ("1", "2. 3.", "12.00", "!", ""):
            self.assertFalse(harf_iceriyor_mu(metin), metin)

    def test_turkce_harf_ve_birim(self):
        for metin in ("Ay", "ı", "50°D", "0 100 200 km"):
            self.assertTrue(harf_iceriyor_mu(metin), metin)


class EskiKodlamaOnarimTest(unittest.TestCase):
    """İstiklal Marşı ve Gençliğe Hitabe sayfaları (fen5.pdf s.5-6, sosyalbilgiler5.pdf s.3-4):
    eski yazı tipi Türkçe harfleri kod numarasıyla verir."""

    # PyMuPDF'in kod numarasıyla verdiği ham metin
    MARS = "Korkma, sönmez bu úafaklarda yüzen al sancak; O benim milletimin yÕldÕzÕdÕr, parlayacak;"
    HITABE = "GENÇLøöE HøTABE"

    def test_esleme(self):
        self.assertEqual(
            eski_turkce_kodlamayi_cevir(self.MARS),
            "Korkma, sönmez bu şafaklarda yüzen al sancak; O benim milletimin yıldızıdır, parlayacak;",
        )

    def test_buyuk_harfli_kelimede_o_gug_olur(self):
        # "ø" -> İ, kelime içindeki "ö" -> Ğ
        self.assertEqual(eski_turkce_kodlamayi_cevir(self.HITABE), "GENÇLİĞE HİTABE")

    def test_karisik_harfli_kelimedeki_o_degismez(self):
        metin = "Sönmeden köşesi dökülen GÖZ MÖ"
        self.assertEqual(eski_turkce_kodlamayi_cevir(metin), metin)

    def test_bolme_isareti_bozulmaz(self):
        self.assertEqual(eski_turkce_kodlamayi_cevir("12 ÷ 3 = 4"), "12 ÷ 3 = 4")

    def test_art_arda_esleme_karakterleri(self):
        # sosyalbilgiler5.pdf s.3: "toprağı", "ruh-ı": ikinci karakterin yanında harf yok
        self.assertEqual(eski_turkce_kodlamayi_cevir("topra÷Õ sÕksan, ruh-Õ mücerret"),
                         "toprağı sıksan, ruh-ı mücerret")

    def test_buyuk_harf_sin(self):
        self.assertEqual(eski_turkce_kodlamayi_cevir("ùEHøT"), "ŞEHİT")

    def test_onarim_bozuk_sayfayi_duzeltir(self):
        metinler = [self.HITABE, "Ey Türk gençli÷i! Birinci vazifen, Türk istiklâlini muhafaza etmektir. " * 2,
                    "Bu temel, senin en kÕymetli hazinendir. østikbalde dahi bu hazineden mahrum etmek."]
        sonuc = kodlamayi_onar(metinler)
        self.assertIsNotNone(sonuc)
        self.assertEqual(sonuc[0], "GENÇLİĞE HİTABE")
        self.assertTrue(sonuc[1].startswith("Ey Türk gençliği!"))
        self.assertIn("İstikbalde", sonuc[2])
        self.assertFalse(kodlama_bozuk_mu(" ".join(sonuc), esik=ONARIM_ESIGI))

    def test_desen_yoksa_onarilmaz(self):
        # eşlemedeki karakterlerden yeterince yok: başka bir sorunun belirtisi
        self.assertIsNone(kodlamayi_onar(["Normal metin bir ú içerir.", "Başka bir cümle daha."]))

    def test_onarim_sonrasi_hala_bozuksa_onarilmaz(self):
        # eşleme uygulanır ama yine de çok sayıda anlamsız karakter kalır (ör. harita simgeleri)
        metinler = ["úafak Õúõú÷ øùúÕ÷" + "ÄÄÄÄÄÄÄÄÄÄÄÄÄÄÄÄÄÄÄÄ" * 3, "Õúafak ú÷ ø"]
        self.assertIsNone(kodlamayi_onar(metinler))


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
