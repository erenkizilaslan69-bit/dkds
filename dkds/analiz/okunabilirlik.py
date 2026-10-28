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
from collections import Counter, defaultdict
from collections.abc import Iterable
from dataclasses import dataclass, field

from ..models import Bulgu, Konum, Paragraf

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
# Madde işaretleri cümlenin parçası değildir: "a. Güneş…", "ç. Hem dönme…", "A) Kültür", "b) Ay".
# Çıkarılınca "cisimleridir. d. Kendi" gibi şık listeleri doğru yerden bölünür.
_MADDE_ISARETI = re.compile(r"(?:(?<=\s)|^)(?:[^\W\d_]\)|[a-zçğıöşü]\.(?=\s+[A-ZÇĞİÖŞÜ]))\s*")
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
    metin = " ".join(_MADDE_ISARETI.sub(" ", metin).split())
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


# =========================================================================== analizör

KRITER = "okunabilirlik"
INCELENEN_TURLER = {"govde"}

# Bundan az kelimeli gövde paragrafları aynı sayfadaki komşu gövde paragraflarıyla
# birleştirilerek değerlendirilir; çok kısa metinde formüller güvenilir sonuç vermez.
EN_AZ_KELIME = 40
# Cümle sonu işareti olmayan paragraf cümle değildir: kelime listesi (fen5.pdf s.58
# "ANAHTAR KAVRAMLAR" altındaki liste), haber başlığı, tablo hücresi ya da ifade listesi.
# Atlanır; yoksa komşu cümlelerle birleşip tek dev "cümle" oluşturur. İlk sürümde yalnızca
# 8+ kelimelik diziler atlanıyordu; kısa parçalar (fen5 s.86, sosyal5 s.115) birleşip en zor
# paragraf listesini doldurduğu için sınır, sınıflandırıcının etiket sınırına (4 kelime) çekildi.
ISARETSIZ_EN_AZ_KELIME = 4
# Paragrafın Ateşman kademesi kitabın sınıfının kademesinden en az bu kadar yüksekse bulgu üretilir.
KADEME_FARKI = 2
EN_ZOR_PARAGRAF_SAYISI = 10
EN_UZUN_KELIME_SAYISI = 4
SORUNLU_METIN_EN_FAZLA = 240

_CUMLE_SONU_ISARETI = re.compile(r"[.!?…]")
# Uzun cümleyi bölmek için uygun yerler: virgül/noktalı virgülden sonra ya da bu sözcüklerden önce
_BOLME_SOZCUKLERI = frozenset({"ancak", "fakat", "ama", "çünkü", "oysa", "ayrıca", "böylece", "ki"})
_BOLME_EN_AZ_KELIME = 5  # bölünen her parça en az bu kadar kelime içermeli


@dataclass
class Birim:
    """Değerlendirilen metin: tek bir gövde paragrafı ya da birleştirilmiş komşu paragraflar."""

    sayfa: int
    paragraflar: list[int]
    metin: str
    konum: Konum
    cumleler: list[str]
    metrikler: Metrikler


@dataclass
class OkunabilirlikSonucu:
    bulgular: list[Bulgu] = field(default_factory=list)
    ozet: dict = field(default_factory=dict)


def sayi_yaz(deger: float, ondalik: int = 1) -> str:
    return f"{deger:.{ondalik}f}".replace(".", ",")


def _buyuk_harf(kelime: str) -> str:
    """Kelimenin ilk harfini Türkçeye uygun büyütür (i → İ, ı → I)."""
    ilk = {"i": "İ", "ı": "I"}.get(kelime[:1], kelime[:1].upper())
    return ilk + kelime[1:]


def bolme_noktasi(cumle: str) -> tuple[str, str] | None:
    """Uzun cümlenin bölünebileceği yeri bulur: (birinci cümle, ikinci cümle) ya da None.

    Aday yerler virgül/noktalı virgülden sonrası ve "ancak", "çünkü" gibi sözcüklerden
    öncesidir; her iki parça da en az 5 kelime içermelidir. Cümlenin ortasına en yakın
    aday seçilir.
    """
    kelimeler = cumle.split()
    n = len(kelimeler)
    adaylar = []
    for i in range(_BOLME_EN_AZ_KELIME - 1, n - _BOLME_EN_AZ_KELIME):  # i: ilk parçanın son kelimesi
        sonraki = kelimeler[i + 1].strip(",;").casefold()
        if kelimeler[i].endswith((",", ";")) or sonraki in _BOLME_SOZCUKLERI:
            adaylar.append(i)
    if not adaylar:
        return None
    i = min(adaylar, key=lambda a: abs((a + 1) - n / 2))
    ilk = " ".join(kelimeler[: i + 1]).rstrip(",;") + "."
    ikinci = _buyuk_harf(" ".join(kelimeler[i + 1:]).lstrip(",; "))
    return ilk, ikinci


def _kisalt(metin: str, kelime_sayisi: int, sondan: bool = False) -> str:
    kelimeler = metin.split()
    if len(kelimeler) <= kelime_sayisi:
        return metin
    if sondan:
        return "… " + " ".join(kelimeler[-kelime_sayisi:])
    return " ".join(kelimeler[:kelime_sayisi]) + " …"


# Sözlükçe maddesi: ". âlim: İlim sahibi kişi." Madde başı küçük harfle başlar ve iki nokta ile biter.
# Bir paragrafta en az 3 madde varsa paragraf sözlükçedir (başında "A-B-C-Ç" gibi harf başlığı olabilir).
_SOZLUK_MADDESI = re.compile(
    r"(?:^|[.;?!]\s+)(?:[A-ZÇĞİÖŞÜ](?:-[A-ZÇĞİÖŞÜ])+\s+)?"
    r"[a-zçğıöşüâîû][\w’'-]*(?:\s+[a-zçğıöşüâîû][\w’'-]*){0,2}:\s"
)
SOZLUK_EN_AZ_MADDE = 3


def atlama_nedeni(metin: str) -> str | None:
    """Paragraf okunabilirlik ölçümüne uygun değilse nedeni, uygunsa None."""
    if not _CUMLE_SONU_ISARETI.search(metin) and len(kelimeleri_bul(metin)) >= ISARETSIZ_EN_AZ_KELIME:
        return "cumle_isaretsiz"
    if len(_SOZLUK_MADDESI.findall(metin)) >= SOZLUK_EN_AZ_MADDE:
        return "sozluk"
    return None


def _birlestir(konumlar: list[Konum]) -> Konum:
    return (min(k[0] for k in konumlar), min(k[1] for k in konumlar),
            max(k[2] for k in konumlar), max(k[3] for k in konumlar))


class OkunabilirlikAnalizoru:
    """Gövde paragraflarının okunabilirliğini kitabın sınıf düzeyiyle karşılaştırır."""

    def __init__(self, sinif: int) -> None:
        self.sinif = sinif
        self.kitap_kademesi = sinif_kademesi(sinif)  # geçersiz sınıf burada ValueError verir

    # ------------------------------------------------------------------ değerlendirme birimleri

    def birimleri_olustur(self, paragraflar: Iterable[Paragraf]) -> tuple[list[Birim], Counter]:
        """Gövde paragraflarını değerlendirme birimlerine ayırır; atlananları sayar.

        - Cümle sonu işareti olmayan paragraflar ve sözlükçe paragrafları atlanır
          (bkz. atlama_nedeni).
        - EN_AZ_KELIME'den kısa paragraflar aynı sayfadaki sonraki gövde paragraflarıyla
          birleştirilir; sayfanın sonunda kalan kısa parça bir öncekine eklenir.
        - Sayfada toplam EN_AZ_KELIME kelimelik gövde metni yoksa sayfa atlanır.
        """
        sayfalar: dict[int, list[Paragraf]] = defaultdict(list)
        for p in paragraflar:
            if p.tur in INCELENEN_TURLER:
                sayfalar[p.sayfa].append(p)

        birimler: list[Birim] = []
        atlanan: Counter = Counter()
        for sayfa_no in sorted(sayfalar):
            gruplar: list[list[Paragraf]] = []
            mevcut: list[Paragraf] = []
            mevcut_kelime = 0
            for p in sayfalar[sayfa_no]:
                neden = atlama_nedeni(p.metin)
                if neden:
                    atlanan[neden] += 1
                    continue
                mevcut.append(p)
                mevcut_kelime += len(kelimeleri_bul(p.metin))
                if mevcut_kelime >= EN_AZ_KELIME:
                    gruplar.append(mevcut)
                    mevcut, mevcut_kelime = [], 0
            if mevcut:
                if gruplar:
                    gruplar[-1].extend(mevcut)
                else:
                    atlanan["kisa_sayfa"] += len(mevcut)
            birimler.extend(self._birim(sayfa_no, g) for g in gruplar)
        return birimler, atlanan

    @staticmethod
    def _birim(sayfa_no: int, grup: list[Paragraf]) -> Birim:
        metin = " ".join(p.metin for p in grup)
        cumleler = cumlelere_ayir(metin)
        return Birim(
            sayfa=sayfa_no,
            paragraflar=[p.paragraf for p in grup],
            metin=metin,
            konum=_birlestir([p.konum for p in grup]),
            cumleler=cumleler,
            metrikler=metrikleri_hesapla(cumleler),
        )

    # ------------------------------------------------------------------ analiz

    def analiz_et(self, paragraflar: Iterable[Paragraf]) -> list[Bulgu]:
        return self.incele(paragraflar).bulgular

    def incele(self, paragraflar: Iterable[Paragraf]) -> OkunabilirlikSonucu:
        birimler, atlanan = self.birimleri_olustur(paragraflar)
        birimler = [b for b in birimler if b.metrikler.hazir]
        toplam = Metrikler()
        for b in birimler:
            toplam = toplam + b.metrikler

        kitap_oks = toplam.ortalama_cumle_uzunlugu if toplam.hazir else 0.0
        bulgular = []
        for b in birimler:
            fark = atesman_kademesi(b.metrikler.atesman) - self.kitap_kademesi
            if fark >= KADEME_FARKI:
                bulgular.append(self._bulgu(b, fark, kitap_oks))
        return OkunabilirlikSonucu(bulgular=bulgular, ozet=self._ozet(birimler, toplam, atlanan))

    def _bulgu(self, b: Birim, fark: int, kitap_oks: float) -> Bulgu:
        m = b.metrikler
        puan = m.atesman
        yod = m.bezirci_yilmaz
        sinif_adi = ATESMAN_DUZEYLERI[self.kitap_kademesi][1]

        kelime_heceleri: dict[str, int] = {}
        for k in kelimeleri_bul(b.metin):
            kelime_heceleri.setdefault(k.casefold(), hece_say(k))
        en_uzunlar = sorted(kelime_heceleri.items(), key=lambda kv: (-kv[1], -len(kv[0]), kv[0]))
        en_uzunlar = ", ".join(f"{k} ({h} hece)" for k, h in en_uzunlar[:EN_UZUN_KELIME_SAYISI])

        aciklama = (
            f"Ateşman okunabilirlik puanı {sayi_yaz(puan)}: {atesman_duzeyi(puan)} düzeyine denk geliyor; "
            f"{self.sinif}. sınıf kitabının düzeyinin ({sinif_adi}) {fark} kademe üstünde. "
            f"Bezirci-Yılmaz puanı {sayi_yaz(yod)} ({bezirci_yilmaz_duzeyi(yod)}). "
            f"Ortalama cümle uzunluğu {sayi_yaz(m.ortalama_cumle_uzunlugu)} kelime "
            f"(kitap ortalaması {sayi_yaz(kitap_oks)}), kelime başına {sayi_yaz(m.hece_kelime, 2)} hece. "
            f"En uzun kelimeler: {en_uzunlar}."
        )
        if len(b.paragraflar) > 1:
            aciklama += (f" {len(b.paragraflar)} kısa gövde paragrafı birleştirilerek değerlendirildi "
                         f"(paragraf {b.paragraflar[0]}–{b.paragraflar[-1]}).")

        return Bulgu(
            sayfa=b.sayfa, paragraf=b.paragraflar[0], kriter=KRITER,
            sorunlu_metin=_kisalt(b.metin, 40) if len(b.metin) > SORUNLU_METIN_EN_FAZLA else b.metin,
            aciklama=aciklama, guven=min(0.7, 0.4 + 0.1 * (fark - 2)),
            oneri=self._oneri(b), konum=b.konum, tur="sinif_ustu",
        )

    @staticmethod
    def _oneri(b: Birim) -> str:
        en_uzun = max(b.cumleler, key=lambda c: len(kelimeleri_bul(c)))
        n = len(kelimeleri_bul(en_uzun))
        nokta = bolme_noktasi(en_uzun)
        if nokta:
            ilk, ikinci = nokta
            return (f"En uzun cümle {n} kelime; şu noktadan iki cümleye bölünebilir: "
                    f"«{_kisalt(ilk, 6, sondan=True)}» | «{_kisalt(ikinci, 6)}»")
        return (f"En uzun cümle {n} kelime: «{_kisalt(en_uzun, 12)}». Daha kısa cümlelere bölünmeli "
                "ve uzun kelimeler sadeleştirilmeli.")

    # ------------------------------------------------------------------ kitap özeti

    def _ozet(self, birimler: list[Birim], toplam: Metrikler, atlanan: Counter) -> dict:
        ozet: dict = {"sinif": self.sinif, "birim_sayisi": len(birimler),
                      "atlanan": dict(atlanan), "kelime": toplam.kelime, "cumle": toplam.cumle}
        if not toplam.hazir:
            return ozet
        atesman, yod = toplam.atesman, toplam.bezirci_yilmaz
        ozet.update(
            ortalama_cumle_uzunlugu=toplam.ortalama_cumle_uzunlugu,
            hece_kelime=toplam.hece_kelime,
            atesman={"puan": atesman, "duzey": atesman_duzeyi(atesman)},
            bezirci_yilmaz={"puan": yod, "duzey": bezirci_yilmaz_duzeyi(yod)},
        )
        en_zorlar = sorted(birimler, key=lambda b: b.metrikler.atesman)[:EN_ZOR_PARAGRAF_SAYISI]
        ozet["en_zor_paragraflar"] = [
            {
                "sayfa": b.sayfa, "paragraflar": b.paragraflar,
                "atesman": b.metrikler.atesman, "atesman_duzeyi": atesman_duzeyi(b.metrikler.atesman),
                "bezirci_yilmaz": b.metrikler.bezirci_yilmaz,
                "kelime": b.metrikler.kelime, "cumle": b.metrikler.cumle,
                "ortalama_cumle_uzunlugu": b.metrikler.ortalama_cumle_uzunlugu,
                "metin": _kisalt(b.metin, 30),
            }
            for b in en_zorlar
        ]
        return ozet
