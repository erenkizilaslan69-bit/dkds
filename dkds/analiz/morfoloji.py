"""Türkçe morfolojik analiz: bir kelimenin geçerli olup olmadığını söyler.

zeyrek kütüphanesi (Zemberek'in Python uyarlaması) kullanılır. zeyrek'e bağlı
tek modül budur; analizörler yalnızca Morfoloji sınıfını kullanır.

Bir kelime "geçerli" sayılırsa zeyrek onu bir köke ve eklere ayırabilmiştir:
    "gözlemlerinizi" -> gözlem + ler + iniz + i
zeyrek'in sözlüğünde çok sayıda özel isim de vardır ("Günes", "Yanlız").
Küçük harfle yazılmış bir kelimenin yalnızca özel isim olarak çözümlenmesi
onu geçerli yapmaz; bu yüzden iki ayrı soru sorulabilir:
    gecerli_mi("günes")                  -> False  (sıradan kelime değil)
    gecerli_mi("günes", ozel_isim=True)  -> True   (özel isim olarak var)

zeyrek'in genel analyze() fonksiyonu metni NLTK ile kelimelere ayırır ve ek
veri dosyası ister; kelimelere ayırmayı kendimiz yaptığımız için tek kelimeyi
çözümleyen _parse() kullanılır.
"""
from __future__ import annotations

import logging

_YAMA_UYGULANDI = False


def _zeyrek_yamasi() -> None:
    """zeyrek 0.1.3'teki durum bozulması hatasını giderir.

    Hata: aynı kelime iki kez çözümlenince farklı sonuç çıkabiliyor
    ("olacak" önce geçerli, sonra geçersiz); hatta programın her çalıştırılışında
    farklı kelimeler ("adı", "adlı") geçersiz çıkabiliyor. Sebebi:
      1. calculate_phonetic_attributes() sonuçlarını lru_cache ile saklıyor ve
         değiştirilebilir bir küme (set) döndürüyor. Hem sözlük kökleri üretilirken
         (morphotactics) hem çözümleme sırasında (rulebasedanalyzer) bu kümeye
         ekleme/çıkarma yapılıyor ve önbellekteki değer bozuluyor. Kökler Python
         kümelerinin sırasıyla üretildiği için bozulma her çalıştırmada farklıdır.
      2. İlk arama yolu, sözlükteki kökün ses özellikleri kümesini kopyalamadan
         kullanıyor; ona yapılan değişiklik de sonraki kelimeleri etkiliyor.
    Çözüm: iki noktada da kümenin kopyası verilir. Kütüphane dosyaları
    değiştirilmez; yama yalnızca bu programın çalışması sırasında geçerlidir ve
    MorphAnalyzer oluşturulmadan önce uygulanmalıdır.
    """
    global _YAMA_UYGULANDI
    if _YAMA_UYGULANDI:
        return
    from zeyrek import attributes, morphotactics, rulebasedanalyzer

    orijinal_hesap = attributes.calculate_phonetic_attributes

    def kopyalayan_hesap(*a, **k):
        return set(orijinal_hesap(*a, **k))

    # Fonksiyonu adıyla içe aktaran her modülde değiştirilmeli
    for modul in (attributes, morphotactics, rulebasedanalyzer):
        modul.calculate_phonetic_attributes = kopyalayan_hesap

    orijinal_baslangic = morphotactics.SearchPath.initial.__func__

    def baslangic(cls, stem_transition, tail):
        yol = orijinal_baslangic(cls, stem_transition, tail)
        yol.phonetic_attributes = set(yol.phonetic_attributes)
        return yol

    morphotactics.SearchPath.initial = classmethod(baslangic)
    _YAMA_UYGULANDI = True


class Morfoloji:
    def __init__(self) -> None:
        import zeyrek

        # zeyrek her çözümlemede uyarı düzeyinde günlük kaydı basıyor
        logging.getLogger("zeyrek").setLevel(logging.ERROR)
        _zeyrek_yamasi()
        self._analizor = zeyrek.MorphAnalyzer()
        # kelime -> (sıradan kelime olarak geçerli, özel isim dahil geçerli)
        self._onbellek: dict[str, tuple[bool, bool]] = {}

    def gecerli_mi(self, kelime: str, ozel_isim: bool = False) -> bool:
        """Kelime Türkçe kurallarına göre çözümlenebiliyor mu? Sonuçlar önbelleğe alınır."""
        if kelime not in self._onbellek:
            cozumler = self._analizor._parse(kelime)
            siradan = any(c.dict_item.secondary_pos.name != "ProperNoun" for c in cozumler)
            self._onbellek[kelime] = (siradan, bool(cozumler))
        siradan, herhangi = self._onbellek[kelime]
        return herhangi if ozel_isim else siradan

    @property
    def onbellek_boyutu(self) -> int:
        return len(self._onbellek)
