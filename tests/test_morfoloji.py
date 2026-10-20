"""Morfoloji (zeyrek sarmalayıcısı) testleri."""
import os
import subprocess
import sys
import unittest

from dkds.analiz.morfoloji import Morfoloji

# zeyrek 0.1.3 hatasından etkilendiği görülen kelimeler (fen5.pdf)
KELIMELER = ["alır", "olacak", "olup", "yapılmıştır", "sağlayan", "gelerek", "bakıldığında",
             "adı", "adlı", "adını", "addır", "adları"]


class MorfolojiTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.morfoloji = Morfoloji()

    def test_tekrar_cozumlemede_ayni_sonuc(self):
        # Yama olmadan "olacak" ikinci çözümlemede geçersiz çıkıyordu
        cozumle = self.morfoloji._analizor._parse
        ilk = [len(cozumle(k)) for k in KELIMELER]
        ikinci = [len(cozumle(k)) for k in KELIMELER]
        self.assertEqual(ilk, ikinci)
        self.assertTrue(all(ilk))

    def test_farkli_calistirmalarda_ayni_sonuc(self):
        # Yama yalnızca çözümleyiciye uygulandığında "adı", "adlı" bazı çalıştırmalarda
        # geçersiz çıkıyordu (Python'un küme sırası her süreçte farklı).
        kod = ("from dkds.analiz.morfoloji import Morfoloji; m = Morfoloji(); "
               f"print(''.join('1' if m.gecerli_mi(k) else '0' for k in {KELIMELER!r}))")
        sonuclar = set()
        for tohum in ("1", "2", "3"):
            ortam = dict(os.environ, PYTHONHASHSEED=tohum)
            cikti = subprocess.run([sys.executable, "-W", "ignore", "-c", kod], env=ortam,
                                   capture_output=True, text=True, check=True).stdout.strip()
            sonuclar.add(cikti)
        self.assertEqual(sonuclar, {"1" * len(KELIMELER)})

    def test_kucuk_harfli_kelime_ozel_isim_olarak_gecerli_sayilmaz(self):
        # zeyrek sözlüğünde "Günes" özel isim olarak var; küçük harfle yazılınca geçerli değildir
        self.assertFalse(self.morfoloji.gecerli_mi("günes"))
        self.assertTrue(self.morfoloji.gecerli_mi("günes", ozel_isim=True))

    def test_sonuclar_onbellege_alinir(self):
        self.morfoloji.gecerli_mi("dinamometre")
        boyut = self.morfoloji.onbellek_boyutu
        self.morfoloji.gecerli_mi("dinamometre")
        self.assertEqual(self.morfoloji.onbellek_boyutu, boyut)


if __name__ == "__main__":
    unittest.main()
