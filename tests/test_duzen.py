import unittest

from dkds.duzen import bolunmus_paragraflari_birlestir, ust_alt_bilgi_temizle
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

    def test_farkli_sutunlar_birlesmez(self):
        a = blok(1, 100, 118, "sol sütunda biten metin\n", x0=50, x1=290)
        b = blok(1, 100, 118, "sağ sütunda başlayan metin\n", x0=310, x1=550)
        self.assertEqual(len(bolunmus_paragraflari_birlestir([a, b])), 2)

    def test_uzak_bloklar_birlesmez(self):
        a = blok(1, 100, 118, "arada büyük boşluk olan\n")
        b = blok(1, 200, 218, "devam metni\n")
        self.assertEqual(len(bolunmus_paragraflari_birlestir([a, b])), 2)


if __name__ == "__main__":
    unittest.main()
