"""Paragraf türü kuralları. Örneklerin çoğu fen5.pdf'ten alınmıştır."""
import unittest

from dkds.siniflandirma import (
    BASLIK,
    ETIKET,
    GOVDE,
    LISTE,
    SORU,
    paragraf_turu,
    sayfa_turleri,
)


class ParagrafTuruTest(unittest.TestCase):
    def kontrol(self, beklenen, *metinler):
        for metin in metinler:
            self.assertEqual(paragraf_turu(metin), beklenen, metin)

    def test_baslik(self):
        self.kontrol(BASLIK, "BİLGİ İSTASYONU", "ANAHTAR KAVRAMLAR", "2. ÜNİTE", "PEKİŞTİRME İSTASYONU-2")

    def test_uzun_buyuk_harfli_metin_baslik_degil(self):
        uzun = "BU CÜMLE ÇOK UZUN OLDUĞU İÇİN BAŞLIK SAYILMAMALI VE GÖVDE OLMALI."
        self.assertNotEqual(paragraf_turu(uzun), BASLIK)

    def test_soru(self):
        self.kontrol(
            SORU,
            "Bir varlığın canlı mı, cansız mı olduğunu nasıl anlarız?",
            "4. Kütle nedir? Kütlenin birimi nedir?",  # numaralı olsa da soru
        )

    def test_soruyla_biten_uzun_anlati_govde(self):
        # s.142: mektup paragrafı okuyucuya soru sorarak bitiyor
        mektup = "Hücre konusu beni çok heyecanlandırdı. " * 12 + "Sence de ilginç değil mi?"
        self.assertEqual(paragraf_turu(mektup), GOVDE)

    def test_liste(self):
        self.kontrol(
            LISTE,
            "• Çatlak ve kırık cam eşyalar kullanılmamalıdır.",
            "- Üçer veya dörder kişilik gruplar oluşturunuz.",
            "12. Kürek kemiği kemikler sınıfında yer alır.",
        )

    def test_kisa_ve_cumle_olmayan_etiket(self):
        self.kontrol(ETIKET, "Akciğer Hücresi", "Ribozom", "Cam zemin")

    def test_harf_aralikli_etiket(self):
        self.kontrol(ETIKET, "İ R A N", "B e r i n g D e n i z i", "S A H A ( Y A K U T ) C .", "İSRAİL M I S I R")

    def test_kisaltmayla_biten_etiket(self):
        self.kontrol(ETIKET, "Kura N.", "Baykal G.", "DAĞISTAN C.", "NAHÇIVAN Ö.C.")

    def test_rakam_agirlikli_etiket(self):
        self.kontrol(ETIKET, "100 N 50 N 5 N 25 N", "0 100 200 300 400 50 km")

    def test_altyazi_etiket(self):
        self.kontrol(
            ETIKET,
            "Görsel 3.1.14: Büyüteç ile yaprak incelemesi",
            "Tablo 2: Ölçüm sonuçları",
            "Harita 2.3 Kars Mülkî İdare İl Haritası",  # sosyalbilgiler5.pdf s.55
        )

    def test_baslik_bicimli_sekil_ve_tablo_adlari_etiket(self):
        self.kontrol(
            ETIKET,
            "Mezopotamya Medeniyetleri Tarih Şeridi",  # sosyalbilgiler5.pdf s.130
            "Yazılı Kaynaklar Görsel Kaynaklar Dijital Kaynaklar",  # s.91 tablo başlığı
            "Destek ve Hareket Sisteminin Bileşenleri",  # fen5.pdf s.120, bağlaç küçük harfli
        )

    def test_kucuk_harfli_kelime_iceren_metin_baslik_bicimli_degil(self):
        self.kontrol(GOVDE, "Mustafa Kemal Atatürk ataturkansiklopedisi.gov.tr adresinden alınmıştır")

    def test_kisa_cumle_govde(self):
        self.kontrol(GOVDE, "Güneş, sıcak gazlardan ve katmanlardan oluşur.", "Kemik sertir.")

    def test_govde(self):
        self.kontrol(
            GOVDE,
            "Ay’ın atmosferi yok denecek kadar incedir. Bu yüzden gök taşlarının büyük kısmı yüzeye düşer.",
        )


class SayfaTurleriTest(unittest.TestCase):
    def test_normal_sayfada_baslik_korunur(self):
        metinler = ["BİLGİ İSTASYONU", "Ay yüzeyinde çukurlar ve kraterler oldukça fazladır."]
        self.assertEqual(sayfa_turleri(metinler), [BASLIK, GOVDE])

    def test_harita_sayfasinda_buyuk_harfli_adlar_etiket(self):
        metinler = ["KARA VE DENİZ KOMŞULARI HARİTASI"] + ["Kura N."] * 30 + [
            "AZERBAYCAN",
            "TÜRK BÖLGELERİ",
            "Harita Genel Müdürlüğü tarafından üretilmiştir.",
        ]
        turler = sayfa_turleri(metinler)
        self.assertEqual(turler[0], BASLIK)  # sayfanın en üstündeki başlık korunur
        self.assertEqual(turler[-3:-1], [ETIKET, ETIKET])
        self.assertEqual(turler[-1], GOVDE)  # cümle sonu işaretiyle biten metin korunur

    def test_buyuk_harfli_yer_adlari_da_harita_sayilir(self):
        # sosyalbilgiler5.pdf s.54: yer adlarının çoğu büyük harfli, yani "başlık"
        metinler = ["Akdağmadeni", "KASTAMONU", "AĞRI DAĞI", "Sinop", "KARADAĞ", "OTOYOL"] * 6
        self.assertEqual(set(sayfa_turleri(metinler)), {ETIKET})

    def test_ilk_etiketten_onceki_baslik_ve_yonerge_korunur(self):
        # sosyalbilgiler5.pdf s.142: yönerge, kutu başlığı, ardından şema
        metinler = ["Şemadaki cümlelerden bazıları doğru, bazıları yanlıştır.", "DEĞERLENDİRELİM"]
        metinler += ["Sümerler", "İlk yazılı kanunları", "7. ÇIKIŞ"] * 10
        turler = sayfa_turleri(metinler)
        self.assertEqual(turler[:2], [GOVDE, BASLIK])

    def test_tek_kelimelik_etiketler_arasindaki_baslik_etiket(self):
        # sosyalbilgiler5.pdf s.136: metin içindeki küçük harita
        metinler = ["Lidyalılar ile ilgili kaynakları inceleyiniz.", "Sardes", "HAZAR DENIZI", "Efes"]
        self.assertEqual(sayfa_turleri(metinler), [GOVDE, ETIKET, ETIKET, ETIKET])

    def test_iki_kelimelik_alt_basliklar_arasindaki_baslik_korunur(self):
        # fen5.pdf s.25: "Görünen Boyut" / ETKİNLİK İSTASYONU / "Etkinliğin Yapılışı"
        metinler = ["Güneş çok uzaktadır.", "Görünen Boyut", "ETKİNLİK İSTASYONU", "Etkinliğin Yapılışı"]
        self.assertEqual(sayfa_turleri(metinler)[2], BASLIK)

    def test_az_paragrafli_sayfada_kural_uygulanmaz(self):
        metinler = ["Ribozom", "Mitokondri", "HÜCRE ZARI"]
        self.assertEqual(sayfa_turleri(metinler), [ETIKET, ETIKET, BASLIK])


if __name__ == "__main__":
    unittest.main()
