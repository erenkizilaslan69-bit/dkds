"""Okunabilirlik analizörü (kriter 2): yaş / sınıf seviyesine uygunluk.

Bu dosyanın ilk bölümü ölçüm araçlarıdır (cümle ayırma, hece sayma, formüller);
ikinci bölümde (OkunabilirlikAnalizoru) paragraflara uygulanır.

İki formül kullanılır:

Ateşman (1997):
    puan = 198,825 − 40,175 × (hece / kelime) − 2,610 × (kelime / cümle)
    Yüksek puan kolay metindir (90–100 ≈ 4. sınıf, 40–49 ≈ lisans).

Bezirci-Yılmaz (2010), "Yeni Okunabilirlik Düzeyi" (YOD):
    YOD = √( OKS × (H3 × 0,84 + H4 × 1,5 + H5 × 3,5 + H6 × 26,25) )
    OKS: ortalama cümle uzunluğu (kelime), H3…H6: cümle başına ortalama 3, 4, 5 ve
    6+ heceli kelime sayısı. Karekök TÜM çarpımın üzerindedir; bu, makalenin Çizelge 8
    ve 9'undaki sayılarla doğrulanmıştır (ör. 3,03 × 7 = 21,21 ve √21,21 = 4,61).
    Yüksek puan zor metindir; makale puanı doğrudan sınıf düzeyi olarak yorumlar
    (7,34 → 7–8. sınıf; 1–8 ilköğretim, 9–12 lise, 12–16 lisans, 16+ akademik).

Hece sayısı = sesli harf sayısı (Türkçede her hecenin tek ünlüsü vardır).
"""
from __future__ import annotations

import math
import re
from dataclasses import dataclass

# --------------------------------------------------------------------------- hece ve kelime

UNLULER = frozenset("aeıioöuüâîûAEIİOÖUÜÂÎÛ")

# Harflerden oluşan kelime; kesme işareti ve kısa çizgiyle bağlanan parçalar tek kelimedir
# ("Dünya’nın", "e-içerik"). Yalnızca rakamlardan oluşan parçalar ("3,5", "9.500") kelime sayılmaz.
_KELIME = re.compile(r"[^\W\d_]+(?:['’´‘-][^\W\d_]+)*")


def kelimeleri_bul(metin: str) -> list[str]:
    """Metindeki kelimeler (en az bir harf içeren parçalar)."""
    return _KELIME.findall(metin)


def hece_say(kelime: str) -> int:
    """Hece sayısı = sesli harf sayısı."""
    return sum(1 for k in kelime if k in UNLULER)


# --------------------------------------------------------------------------- cümle ayırma

# Ardından küçük harfle devam edilse de cümle bitmiş sayılmayan kısaltmalar zaten
# "sonraki küçük harf" kuralıyla ayrılır; buradaki liste ardından BÜYÜK harf gelen
# kısaltmalar içindir ("Dr. Ayşe", "Hz. İsa", "Bkz. Çizelge 2").
KISALTMALAR = frozenset({
    "dr", "prof", "doç", "yrd", "öğr", "uzm", "av", "mimar", "müh", "sn", "bn", "hz",
    "bkz", "krş", "vb", "vs", "vd", "örn", "yy", "no", "nu", "s", "sf", "çev", "haz",
    "yay", "der", "ed", "cad", "sok", "mah", "bul", "tel", "st", "mö", "ms", "tc",
})

_ROMA_RAKAMI = re.compile(r"[IVXLC]{1,4}")
# "M.Ö", "T.C", "A": tek harf ya da harf-nokta zincirleri (ad baş harfleri, kısaltmalar)
_BASHARF_ZINCIRI = re.compile(r"(?:[^\W\d_]\.)*[^\W\d_]")
_ACILIS = "\"“‘«('[ "
# Cümle sonu adayı: noktalama + kapanış tırnağı/parantezi + boşluk
_SON_ADAYI = re.compile(r"([.!?…]+)([\"”’»)\]]*)\s+")


def _kucuk_harf_mi(k: str) -> bool:
    return k.isalpha() and k.islower()


def _cumle_sonu_mu(once: str, noktalama: str, sonraki: str) -> bool:
    """Noktalamanın bir cümleyi bitirip bitirmediğine karar verir.

    once: noktalamaya kadar olan metin, sonraki: noktalama ve boşluktan sonraki metin.
    """
    sonraki = sonraki.lstrip(_ACILIS)
    if not sonraki:
        return True
    if _kucuk_harf_mi(sonraki[0]):
        return False  # "36. sayfa", "vb. araçlar", "26 km. güneybatısında", "? b. Ay’ın"
    if noktalama.endswith(".") and not noktalama.endswith(".."):
        parcalar = once.split()
        token = parcalar[-1].strip("(\"“‘«'[") if parcalar else ""
        if token.casefold() in KISALTMALAR or _BASHARF_ZINCIRI.fullmatch(token):
            return False  # "Dr. Ayşe", "Şahin, H. Konyar", "M.Ö. 7500"
        if _ROMA_RAKAMI.fullmatch(token):
            return False  # "II. Dünya Savaşı"
    return True


def cumlelere_ayir(metin: str) -> list[str]:
    """Metni cümlelere ayırır.

    Cümle sonu: ".", "!", "?" ya da "…" işaretinden sonra boşluk ve büyük harf/rakam gelmesi.
    Bölünmeyen durumlar: Türkçe kısaltmalar ("vb.", "örn.", "s.", "Dr.", "Hz."), ad baş
    harfleri ve "M.Ö." gibi zincirler, sıra sayıları ("36. sayfa"), Roma rakamları
    ("II. Dünya Savaşı"), küçük harfle devam eden metin ve ondalık/binlik sayılar ("3,5",
    "9.500": noktadan sonra boşluk yoktur). Hiç kelime içermeyen parçalar ("1.") atılır.
    """
    metin = " ".join(metin.split())
    cumleler: list[str] = []
    baslangic = 0
    for m in _SON_ADAYI.finditer(metin):
        if _cumle_sonu_mu(metin[baslangic: m.start()], m.group(1), metin[m.end():]):
            cumleler.append(metin[baslangic: m.end()].strip())
            baslangic = m.end()
    kalan = metin[baslangic:].strip()
    if kalan:
        cumleler.append(kalan)
    return [c for c in cumleler if kelimeleri_bul(c)]


# --------------------------------------------------------------------------- ölçümler


@dataclass
class Metrikler:
    """Bir metnin (ya da birleştirilmiş birçok metnin) sayım sonuçları."""

    kelime: int = 0
    cumle: int = 0
    hece: int = 0
    h3: int = 0  # 3 heceli kelime sayısı (toplam; cümle başına ortalaması h3 / cumle)
    h4: int = 0
    h5: int = 0
    h6: int = 0  # 6 ve daha fazla heceli

    def __add__(self, diger: Metrikler) -> Metrikler:
        return Metrikler(*(a + b for a, b in zip(self._degerler(), diger._degerler())))

    def _degerler(self) -> tuple[int, ...]:
        return self.kelime, self.cumle, self.hece, self.h3, self.h4, self.h5, self.h6

    @property
    def hazir(self) -> bool:
        return self.kelime > 0 and self.cumle > 0

    @property
    def ortalama_cumle_uzunlugu(self) -> float:
        """OKS: cümle başına ortalama kelime sayısı."""
        return self.kelime / self.cumle

    @property
    def hece_kelime(self) -> float:
        return self.hece / self.kelime

    @property
    def atesman(self) -> float:
        return atesman_puani(self.hece_kelime, self.ortalama_cumle_uzunlugu)

    @property
    def bezirci_yilmaz(self) -> float:
        c = self.cumle
        return bezirci_yilmaz_puani(self.ortalama_cumle_uzunlugu, self.h3 / c, self.h4 / c, self.h5 / c, self.h6 / c)


def metrikleri_hesapla(cumleler: list[str]) -> Metrikler:
    """Cümle listesinin kelime, hece ve uzun kelime sayımlarını çıkarır."""
    m = Metrikler(cumle=len(cumleler))
    for cumle in cumleler:
        for kelime in kelimeleri_bul(cumle):
            h = hece_say(kelime)
            m.kelime += 1
            m.hece += h
            if h == 3:
                m.h3 += 1
            elif h == 4:
                m.h4 += 1
            elif h == 5:
                m.h5 += 1
            elif h >= 6:
                m.h6 += 1
    return m


def metin_metrikleri(metin: str) -> Metrikler:
    return metrikleri_hesapla(cumlelere_ayir(metin))


# --------------------------------------------------------------------------- formüller


def atesman_puani(hece_kelime: float, kelime_cumle: float) -> float:
    """Ateşman okunabilirlik puanı (yüksek = kolay)."""
    return 198.825 - 40.175 * hece_kelime - 2.610 * kelime_cumle


def bezirci_yilmaz_puani(oks: float, h3: float, h4: float, h5: float, h6: float) -> float:
    """Bezirci-Yılmaz Yeni Okunabilirlik Düzeyi (yüksek = zor). Karekök tüm çarpımın üzerindedir."""
    return math.sqrt(oks * (h3 * 0.84 + h4 * 1.5 + h5 * 3.5 + h6 * 26.25))


# Ateşman puanı → sınıf düzeyi. (alt sınır, ad); puan alt sınırı geçen ilk satırın düzeyindedir.
ATESMAN_DUZEYLERI = (
    (90, "4. sınıf ve altı"),
    (80, "5-6. sınıf"),
    (70, "7-8. sınıf"),
    (60, "9-10. sınıf"),
    (50, "11-12. sınıf"),
    (40, "lisans"),
    (float("-inf"), "lisans üstü"),
)


def atesman_kademesi(puan: float) -> int:
    """Ateşman puanının tablodaki kademesi: 0 = 4. sınıf ve altı … 6 = lisans üstü."""
    for kademe, (alt_sinir, _ad) in enumerate(ATESMAN_DUZEYLERI):
        if puan >= alt_sinir:
            return kademe
    raise AssertionError("ulaşılamaz")  # son satırın alt sınırı -sonsuz


def atesman_duzeyi(puan: float) -> str:
    return ATESMAN_DUZEYLERI[atesman_kademesi(puan)][1]


def sinif_kademesi(sinif: int) -> int:
    """Bir sınıfın (1-12) Ateşman tablosundaki kademesi: 5. sınıf → 1 (5-6. sınıf)."""
    if not 1 <= sinif <= 12:
        raise ValueError("sınıf 1 ile 12 arasında olmalı")
    return 0 if sinif <= 4 else (sinif - 3) // 2


def bezirci_yilmaz_duzeyi(puan: float) -> str:
    """Makalenin yorumu: puan sınıf düzeyidir; 7,34 → 7-8. sınıf (1-8 ilköğretim, 9-12 lise,
    12-16 lisans, 16 ve üstü akademik)."""
    if puan >= 16:
        return "akademik"
    if puan >= 12:
        return "lisans"
    tam = max(1, int(puan))
    return f"{tam}-{tam + 1}. sınıf"
