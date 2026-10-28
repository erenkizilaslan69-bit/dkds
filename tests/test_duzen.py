import unittest

from dkds.duzen import bolunmus_paragraflari_birlestir, tekrarli_metni_temizle, ust_alt_bilgi_temizle
from dkds.models import Blok

SAYFA_H = 800.0


def blok(sayfa, y0, y1, metin, x0=50.0, x1=550.0):
    return Blok(sayfa=sayfa, x0=x0, y0=y0, x1=x1, y1=y1, metin=metin)


class UstAltBilgiTest(unittest.TestCase):
    def _kitap(self, sayfa_sayisi=6):
        sayfalar = {}
        for s in range(1, sayfa_sayisi + 1):
            sayfalar[s] = [
                blok(s, 20, 35, "FEN BİLİMLERİ 5\n"),           # üst bilgi
                blok(s, 100, 160, f"Sayfa {s} için asıl paragraf metni burada yer alır.\n"),
                blok(s, 770, 785, f"{s + 10}\n"),               # sayfa numarası
            ]
        return sayfalar, {s: SAYFA_H for s in sayfalar}

    def test_ust_bilgi_ve_sayfa_numarasi_silinir(self):
        sayfalar, h = self._kitap()
        sonuc = ust_alt_bilgi_temizle(sayfalar, h)
        for s, bloklar in sonuc.items():
            self.assertEqual(len(bloklar), 1)
            self.assertIn("asıl paragraf", bloklar[0].metin)

    def test_kenarda_olmayan_tekrar_eden_metin_silinir(self):
        sayfalar = {
            s: [blok(s, 300, 315, "1. ÜNİTE: CANLILAR\n"), blok(s, 400, 460, f"İçerik {s}\n")]
            for s in range(1, 7)
        }
        sonuc = ust_alt_bilgi_temizle(sayfalar, {s: SAYFA_H for s in sayfalar})
        self.assertTrue(all("ÜNİTE" not in b.metin for bl in sonuc.values() for b in bl))

    def test_uzun_blok_kenarda_olsa_bile_korunur(self):
        uzun = "Bu çok uzun bir paragraftır. " * 10
        sayfalar = {1: [blok(1, 760, 795, uzun)]}
        sonuc = ust_alt_bilgi_temizle(sayfalar, {1: SAYFA_H})
        self.assertEqual(len(sonuc[1]), 1)


class BirlestirmeTest(unittest.TestCase):
    def test_bolunmus_paragraf_birlesir(self):
        a = blok(1, 100, 136, "Fotosentez, bitkilerin güneş ışığını\nkullanarak besin\n")
        b = blok(1, 140, 158, "ürettiği bir süreçtir.\n")
        sonuc = bolunmus_paragraflari_birlestir([a, b])
        self.assertEqual(len(sonuc), 1)
        self.assertEqual(sonuc[0].y1, 158)
        self.assertIn("besin\nürettiği", sonuc[0].metin)

    def test_nokta_ile_biten_paragraf_birlesmez(self):
        a = blok(1, 100, 118, "Birinci paragraf burada bitti.\n")
        b = blok(1, 122, 140, "ikinci paragraf küçük harfle başlasa da ayrı.\n")
        self.assertEqual(len(bolunmus_paragraflari_birlestir([a, b])), 2)

    def test_buyuk_harfle_baslayan_blok_birlesmez(self):
        a = blok(1, 100, 118, "Bir başlık gibi duran satır\n")
        b = blok(1, 122, 140, "Yeni paragraf büyük harfle başlıyor.\n")
        self.assertEqual(len(bolunmus_paragraflari_birlestir([a, b])), 2)

    def test_buyuk_harfli_baslik_altindaki_listeyle_birlesmez(self):
        # fen5.pdf s.58: "ANAHTAR KAVRAMLAR" başlığı ve altındaki kavram listesi
        a = blok(1, 100, 118, "ANAHTAR KAVRAMLAR\n")
        b = blok(1, 122, 140, "kuvvet\nkuvvet birimi\ndinamometre\n")
        self.assertEqual(len(bolunmus_paragraflari_birlestir([a, b])), 2)

    def test_ust_uste_binen_satirlar_birlesir(self):
        # sosyalbilgiler5.pdf s.127: sıkı satır aralığında kutular 1.8 pt üst üste biniyor
        a = blok(1, 448.3, 463.3, "yıkıntıların üst üste birik-\n")
        b = blok(1, 461.5, 476.5, "mesiyle oluşan yapay tepedir.\n")
        sonuc = bolunmus_paragraflari_birlestir([a, b])
        self.assertEqual(len(sonuc), 1)
        self.assertEqual(sonuc[0].y1, 476.5)

    def test_araya_giren_bloktan_sonra_da_birlesir(self):
        # sosyalbilgiler5.pdf s.64: zaman çizelgesinde yan sütundaki kutu araya giriyor
        a = blok(1, 372, 422, "1948\n8 Mart'ta\npetrol çıkarılmaya\n", x0=231, x1=323)
        yan = blok(1, 372, 437, "1946\n17 Ocak'ta\npetrol bulundu.\n", x0=388, x1=470)
        b = blok(1, 419, 437, "başlandı.\n", x0=254, x1=297)
        sonuc = bolunmus_paragraflari_birlestir([a, yan, b])
        self.assertEqual(len(sonuc), 2)
        self.assertTrue(sonuc[0].metin.endswith("başlandı.\n"))
        self.assertIn("bulundu.", sonuc[1].metin)

    def test_farkli_sutunlar_birlesmez(self):
        a = blok(1, 100, 118, "sol sütunda biten metin\n", x0=50, x1=290)
        b = blok(1, 100, 118, "sağ sütunda başlayan metin\n", x0=310, x1=550)
        self.assertEqual(len(bolunmus_paragraflari_birlestir([a, b])), 2)

    def test_uzak_bloklar_birlesmez(self):
        a = blok(1, 100, 118, "arada büyük boşluk olan\n")
        b = blok(1, 200, 218, "devam metni\n")
        self.assertEqual(len(bolunmus_paragraflari_birlestir([a, b])), 2)


class TekrarliMetinTest(unittest.TestCase):
    """Kopya metin katmanı (turkce5.pdf s.68, 122; sosyalbilgiler5.pdf s.142 kalıbı)."""

    def test_art_arda_tekrar_eden_satirlar_tek_satira_iner(self):
        b = blok(1, 100, 160, "Bu temada\nBu temada\nyazılarınızı zenginleştirecek biçimde söz varlığınızı kullanır-\n"
                              "yazılarınızı zenginleştirecek biçimde söz varlığınızı kullanır-\nken birinci temadaki\n")
        sonuc, silinen = tekrarli_metni_temizle([b])
        self.assertEqual(silinen, 2)
        self.assertEqual(sonuc[0].metin.count("Bu temada"), 1)
        self.assertEqual(sonuc[0].metin.count("zenginleştirecek"), 1)
        self.assertIn("ken birinci temadaki", sonuc[0].metin)

    def test_sonu_farkli_yazilan_kopya_satir_da_silinir(self):
        b = blok(1, 100, 130, "Anadolu'ya çivi yazısını getirmişlerdir.\nAnadoluya çivi yazısını getirmişlerdir\n")
        sonuc, silinen = tekrarli_metni_temizle([b])
        self.assertEqual(silinen, 1)
        self.assertEqual(sonuc[0].metin.count("getirmişlerdir"), 1)

    def test_ayni_yerdeki_benzer_ikinci_blok_silinir(self):
        a = blok(1, 100, 130, "Asurlular\nkurdukları\nticaret kolonileri\n", x0=410, x1=490)
        b = blok(1, 101, 131, "Asurlar\nkurdukları\nticaret kolonileri\n", x0=411, x1=489)
        sonuc, silinen = tekrarli_metni_temizle([a, b])
        self.assertEqual(sonuc, [a])
        self.assertEqual(silinen, 1)

    def test_farkli_yerdeki_ayni_metin_silinmez(self):
        # tablo hücreleri: aynı metin farklı konumlarda gerçek tekrardır
        a = blok(1, 100, 120, "Doğru cevap\n", x0=50, x1=150)
        b = blok(1, 300, 320, "Doğru cevap\n", x0=50, x1=150)
        sonuc, silinen = tekrarli_metni_temizle([a, b])
        self.assertEqual(len(sonuc), 2)
        self.assertEqual(silinen, 0)

    def test_ayni_yerde_farkli_metin_silinmez(self):
        a = blok(1, 100, 130, "Fotosentez bitkilerde gerçekleşir.\n")
        b = blok(1, 100, 130, "Solunum hücrelerde gerçekleşir.\n")
        sonuc, _ = tekrarli_metni_temizle([a, b])
        self.assertEqual(len(sonuc), 2)

    def test_kisa_ve_farkli_satirlar_korunur(self):
        # şık işaretleri kısa ve birbirine benzer ama kopya değil; art arda benzer olmayan satırlar da kalır
        b = blok(1, 100, 200, "a)\na)\nKuvvet birimi newtondur.\nKütle birimi kilogramdır.\n")
        sonuc, silinen = tekrarli_metni_temizle([b])
        self.assertEqual(silinen, 0)
        self.assertEqual(sonuc[0].metin, b.metin)

    def test_tekrar_yoksa_bloklar_degismez(self):
        bloklar = [blok(1, 100, 160, "Birinci paragraf metni burada.\n"), blok(1, 200, 260, "İkinci paragraf başka.\n")]
        sonuc, silinen = tekrarli_metni_temizle(bloklar)
        self.assertEqual(sonuc, bloklar)
        self.assertEqual(silinen, 0)


if __name__ == "__main__":
    unittest.main()
