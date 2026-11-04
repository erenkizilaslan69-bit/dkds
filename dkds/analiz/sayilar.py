"""Sayılar ve birimli ölçüler: yazıyla sayılar, sayı + birim ifadeleri, ortak tabana çevirme.

Tutarlılık analizörünün sayısal yardımcılarıdır; PDF kütüphanesinden bağımsızdır.

  - rakamlastir: "yirmi dört saat" -> "24 saat", "on bin yıl önce" -> "10000 yıl önce". Yeni metindeki
    konumlar eski metne haritalanır (açıklamada özgün ifade gösterilsin diye).
  - olculeri_bul: "24 saatte", "365 gün 6 saat", "-174 ⁰C", "384.000 km", "%71", "1 milyon km" gibi
    ifadeleri ortak tabana çevirir: zaman -> saniye, uzunluk -> metre, kütle -> gram, kuvvet -> N,
    sıcaklık -> °C, yüzde -> %. Yıl = 365,25 gün.
"""
from __future__ import annotations

import re
from dataclasses import dataclass

HARF = "A-Za-zÇĞİÖŞÜçğıöşüÂâÎîÛû"
SAYI = r"\d{1,3}(?:[.\s  ]\d{3})+|\d+(?:,\d+)?"
ARALIK = r"\s*[-–—]\s*"
CARPAN = {None: 1, "bin": 1_000, "milyon": 1_000_000, "milyar": 1_000_000_000}

# Göreli tolerans: bir ölçü, başka bir yerde yuvarlanmış ya da başka birimden çevrilmiş olabilir
# (384.000 km ~ 384.400 km, 365 gün ~ 1 yıl); %1'e kadar fark çelişki sayılmaz.
GORELI_TOLERANS = 0.01


def kucuk(metin: str) -> str:
    """Türkçe küçük harf (casefold "İ"yi "i̇" yapar)."""
    return metin.replace("İ", "i").replace("I", "ı").lower()


def sayi_oku(metin: str) -> float:
    """"7500", "9 500", "12.000", "1,5" gibi yazılışı sayıya çevirir (binlik ayırıcı: boşluk ya da nokta)."""
    metin = metin.strip()
    if "," in metin:
        return float(re.sub(r"[.\s  ]", "", metin).replace(",", "."))
    return float(re.sub(r"[.\s  ]", "", metin))


# ------------------------------------------------------------------ yazıyla sayılar

_BIRLER = {"sıfır": 0, "bir": 1, "iki": 2, "üç": 3, "dört": 4, "beş": 5, "altı": 6, "yedi": 7, "sekiz": 8, "dokuz": 9}
_ONLAR = {"on": 10, "yirmi": 20, "otuz": 30, "kırk": 40, "elli": 50, "altmış": 60, "yetmiş": 70, "seksen": 80,
          "doksan": 90}
_BUYUKLER = {"bin": 1_000, "milyon": 1_000_000, "milyar": 1_000_000_000}
_SAYI_SOZCUKLERI = set(_BIRLER) | set(_ONLAR) | set(_BUYUKLER) | {"yüz"}
_SOZCUK = re.compile(rf"[{HARF}]+")


def _yazili_say(sozcukler: list[str]) -> int:
    toplam = mevcut = 0
    for s in sozcukler:
        if s in _BIRLER:
            mevcut += _BIRLER[s]
        elif s in _ONLAR:
            mevcut += _ONLAR[s]
        elif s == "yüz":
            mevcut = (mevcut or 1) * 100
        else:
            toplam += (mevcut or 1) * _BUYUKLER[s]
            mevcut = 0
    return toplam + mevcut


def yazili_sayi_dizileri(metin: str) -> list[tuple[int, int, int]]:
    """Metindeki yazıyla sayı dizileri: (başlangıç, bitiş, değer).

    Yalnızca boşlukla ayrılmış ardışık sayı sözcükleri tek sayıdır ("yirmi dört", "üç yüz altmış beş",
    "on bin"). Tek başına "bir" belirsiz ön ek / tamlayıcıdır ("bir gün") ve sayı sayılmaz.
    """
    sozcukler = [(m.start(), m.end(), m.group(0)) for m in _SOZCUK.finditer(metin)]
    sonuc: list[tuple[int, int, int]] = []
    i = 0
    while i < len(sozcukler):
        if kucuk(sozcukler[i][2]) not in _SAYI_SOZCUKLERI:
            i += 1
            continue
        # sınıflar: B birler, O onlar, Y yüz, K büyük (bin, milyon, milyar)
        j, grup, onceki, kucuk_grup = i, [], None, 0
        while j < len(sozcukler):
            s = kucuk(sozcukler[j][2])
            if s not in _SAYI_SOZCUKLERI or (j > i and metin[sozcukler[j - 1][1]:sozcukler[j][0]] != " "):
                break
            sinif = "K" if s in _BUYUKLER else "Y" if s == "yüz" else "O" if s in _ONLAR else "B"
            gecerli = (
                (onceki is None and (sinif != "K" or s == "bin"))  # "bin beş yüz"
                or (sinif == "K" and onceki in ("B", "O", "Y"))  # "on bin", "iki yüz bin"
                or (onceki == "K" and sinif != "K")
                or (onceki == "Y" and sinif in ("O", "B"))
                or (onceki == "O" and sinif == "B")
                or (onceki == "B" and sinif == "Y" and kucuk_grup == 1)  # "üç yüz"
            )
            if not gecerli:
                break
            kucuk_grup = 0 if sinif == "K" else kucuk_grup + 1
            onceki = sinif
            grup.append(s)
            j += 1
        if grup and grup != ["bir"] and grup != ["sıfır"]:
            sonuc.append((sozcukler[i][0], sozcukler[j - 1][1], _yazili_say(grup)))
        i = max(j, i + 1)
    return sonuc


@dataclass
class Rakamlama:
    """Yazıyla sayıların rakama çevrilmiş hâli ve yeni metin ile özgün metin arasındaki konum haritası."""

    yeni: str
    # (yeni_baş, yeni_son, eski_baş, eski_son, değişti mi)
    parcalar: list[tuple[int, int, int, int, bool]]

    def eski(self, bas: int, son: int) -> tuple[int, int]:
        """Yeni metindeki [bas, son) aralığının özgün metindeki karşılığı."""
        eski_bas = eski_son = None
        for yb, ys, eb, es, degisti in self.parcalar:
            if eski_bas is None and yb <= bas < ys:
                eski_bas = eb if degisti else eb + (bas - yb)
            if yb < son <= ys:
                eski_son = es if degisti else eb + (son - yb)
        return (eski_bas if eski_bas is not None else bas, eski_son if eski_son is not None else son)


# Yazıyla sayının hemen ardından gelirse rakama çevrilen birim ve sözcükler
_SAYIDAN_SONRA = re.compile(
    r"\s+(?:saniye|dakika|saat|gün|hafta|yıl|milimetre|santimetre|kilometre|metre|kilogram|gram|ton|newton|derece|"
    r"km|cm|mm|kg|mg|dk)(?![" + HARF + r"])",
    re.IGNORECASE,
)
_YUZDEDEN_SONRA = re.compile(r"yüzde\s+$", re.IGNORECASE)


def rakamlastir(cumle: str) -> Rakamlama:
    """"yirmi dört saat" -> "24 saat"; yalnızca birim ya da "yüzde"den önce gelen yazıyla sayılar çevrilir."""
    parcalar: list[tuple[int, int, int, int, bool]] = []
    yeni = ""
    son = 0
    for bas, bit, deger in yazili_sayi_dizileri(cumle):
        if not (_SAYIDAN_SONRA.match(cumle, bit) or _YUZDEDEN_SONRA.search(cumle[:bas])):
            continue
        if bas > son:
            parcalar.append((len(yeni), len(yeni) + bas - son, son, bas, False))
            yeni += cumle[son:bas]
        parcalar.append((len(yeni), len(yeni) + len(str(deger)), bas, bit, True))
        yeni += str(deger)
        son = bit
    if son < len(cumle):
        parcalar.append((len(yeni), len(yeni) + len(cumle) - son, son, len(cumle), False))
        yeni += cumle[son:]
    return Rakamlama(yeni=yeni, parcalar=parcalar)


# ------------------------------------------------------------------ yaklaşıklık

_ONCEKI_YAKLASIK = re.compile(
    r"\b(?:yaklaşık(?: olarak)?|takriben|tahminen|kabaca|aşağı yukarı)\b[^.;:]{0,18}$", re.IGNORECASE)
_SONRAKI_YAKLASIK = re.compile(
    r"^\s*(?:(?:['’]\s*(?:li|lı|lu|lü)\s+)?(?:yıllarında|yıllarına|yıllarda|yıllarından|yılları|civarında|civarı|"
    r"dolaylarında|sıralarında)\b|['’](?:lerde|larda|lerin|ların)\b)",
    re.IGNORECASE,
)


def yaklasik_mi(cumle: str, bas: int, son: int) -> tuple[bool, int, int]:
    """İfadenin önündeki/sonundaki yaklaşıklık sözcüğüne bakar; (yaklaşık mı, yeni başlangıç, yeni bitiş)."""
    yaklasik = False
    onceki = _ONCEKI_YAKLASIK.search(cumle[max(0, bas - 30):bas])
    if onceki:
        yaklasik = True
        bas = max(0, bas - 30) + onceki.start()
    sonraki = _SONRAKI_YAKLASIK.match(cumle[son:son + 30])
    if sonraki:
        yaklasik = True
        son += sonraki.end()
    return yaklasik, bas, son


# ------------------------------------------------------------------ birimler

# boyut -> {birim: tabana çarpan}
_BIRIMLER = {
    "zaman": {"saniye": 1, "dakika": 60, "saat": 3600, "gün": 86400, "hafta": 604800, "yıl": 31_557_600},
    "uzunluk": {"mm": 0.001, "cm": 0.01, "m": 1, "km": 1000},
    "kütle": {"mg": 0.001, "g": 1, "kg": 1000, "ton": 1_000_000},
    "kuvvet": {"N": 1},
    "sıcaklık": {"°C": 1},
}
_KELIME_BIRIM = {
    "saniye": ("zaman", "saniye"), "dakika": ("zaman", "dakika"), "dk": ("zaman", "dakika"),
    "saat": ("zaman", "saat"), "gün": ("zaman", "gün"), "hafta": ("zaman", "hafta"), "yıl": ("zaman", "yıl"),
    "milimetre": ("uzunluk", "mm"), "mm": ("uzunluk", "mm"), "santimetre": ("uzunluk", "cm"),
    "cm": ("uzunluk", "cm"), "metre": ("uzunluk", "m"), "m": ("uzunluk", "m"), "kilometre": ("uzunluk", "km"),
    "km": ("uzunluk", "km"), "mg": ("kütle", "mg"), "gram": ("kütle", "g"), "g": ("kütle", "g"),
    "kilogram": ("kütle", "kg"), "kg": ("kütle", "kg"), "ton": ("kütle", "ton"), "newton": ("kuvvet", "N"),
    "N": ("kuvvet", "N"), "derece": ("sıcaklık", "°C"),
}
_SOZCUK_BIRIMLERI = (r"kilometre|santimetre|milimetre|kilogram|saniye|dakika|metre|gram|newton|derece|hafta|saat|"
                     r"gün|yıl|ton")
_SEMBOL_BIRIMLERI = r"dk|mm|cm|km|mg|kg|[°⁰º˚]\s?C|m|g|N"
_EKLER = r"(?:de|da|den|dan|te|ta|ten|tan|ye|ya|yi|yı|yle|yla|lik|lık|luk|lük|e|a)"

_OLCU = re.compile(
    rf"(?<![\w.,])(?P<neg>[-−])?(?P<a>{SAYI})(?:{ARALIK}(?P<b>{SAYI}))?\s*(?P<k>bin|milyon|milyar)?\s*"
    rf"(?:(?P<sozcuk>{_SOZCUK_BIRIMLERI}){_EKLER}?|(?P<sembol>{_SEMBOL_BIRIMLERI})(?:['’]\w{{1,4}})?)"
    rf"(?![\w²³/])"
)
_YUZDE_ONDE = re.compile(rf"%\s?(?P<a>{SAYI})(?:{ARALIK}%?\s?(?P<b>{SAYI}))?")
_YUZDE_SONDA = re.compile(rf"(?<![\w.,])(?P<a>{SAYI})\s?%")
_YUZDE_SOZ = re.compile(rf"(?<![{HARF}])yüzde\s+(?P<a>{SAYI})(?:{ARALIK}(?P<b>{SAYI}))?", re.IGNORECASE)
_SICAKLIK_SOZLERI = re.compile(r"sıcak|soğuk|ısı|erir|kaynar|donar", re.IGNORECASE)


@dataclass
class Olcu:
    """Cümledeki bir sayı + birim ifadesi, ortak tabana çevrilmiş."""

    bas: int
    son: int
    boyut: str  # zaman, uzunluk, kütle, kuvvet, sıcaklık, yüzde
    alt: float  # ortak tabanda (saniye, metre, gram, N, °C, %)
    ust: float
    yaklasik: bool
    tolerans: float
    birim: str  # ifadede yazılan birim ("saat", "km", "°C", "%")


@dataclass
class _Ham:
    """Yaklaşıklık sözcüğü eklenmeden önceki eşleşme (bileşik birimler önce birleştirilir)."""

    bas: int
    son: int
    boyut: str
    birim: str
    yazilan: float  # ifadedeki sayı (birimin kendi cinsinden, çarpanlı), yuvarlama toleransı için
    alt: float
    ust: float


def _yuvarlama_tolerans(yazilan: float, katsayi: float) -> float:
    """Yaklaşık değerde yuvarlama toleransı: sondaki sıfırların on kuvvetinin yarısı (tabanda)."""
    sayi = int(round(abs(yazilan)))
    if sayi == 0:
        return 0.0
    metin = str(sayi)
    sifirlar = len(metin) - len(metin.rstrip("0"))
    birim = 10 ** min(sifirlar, len(metin) - 1)
    return birim * katsayi / 2


def _ham_olustur(bas: int, son: int, boyut: str, birim: str, katsayi: float, a: float, b: float) -> _Ham:
    alt, ust = sorted((a * katsayi, b * katsayi))
    return _Ham(bas=bas, son=son, boyut=boyut, birim=birim, yazilan=max(abs(a), abs(b)), alt=alt, ust=ust)


def _birlestir(hamlar: list[_Ham], metin: str) -> list[_Ham]:
    """"365 gün 6 saat": aynı boyutta, yan yana, küçülen birimli ölçüler tek ölçü olur."""
    sonuc: list[_Ham] = []
    for h in sorted(hamlar, key=lambda h: h.bas):
        if (sonuc and h.boyut == sonuc[-1].boyut and h.boyut in ("zaman", "uzunluk", "kütle")
                and re.fullmatch(r"\s*(?:ve\s+)?", metin[sonuc[-1].son:h.bas])
                and _BIRIMLER[h.boyut][h.birim] < _BIRIMLER[h.boyut][sonuc[-1].birim]
                and sonuc[-1].alt == sonuc[-1].ust and h.alt == h.ust):
            onceki = sonuc[-1]
            sonuc[-1] = _Ham(bas=onceki.bas, son=h.son, boyut=h.boyut, birim=onceki.birim, yazilan=onceki.yazilan,
                             alt=onceki.alt + h.alt, ust=onceki.ust + h.ust)
        else:
            sonuc.append(h)
    return sonuc


def olculeri_bul(metin: str) -> list[Olcu]:
    """Metindeki sayı + birim ifadeleri (konumlar `metin`e göredir; yazıyla sayılar önceden rakamlaştırılmalı)."""
    hamlar: list[_Ham] = []

    for m in _OLCU.finditer(metin):
        ad = m.group("sozcuk") or re.sub(r"\s", "", m.group("sembol"))
        if ad.endswith("C") and ad[0] in "°⁰º˚":
            boyut, birim = "sıcaklık", "°C"
        else:
            boyut, birim = _KELIME_BIRIM[ad]
        if ad == "derece" and not _SICAKLIK_SOZLERI.search(metin):
            continue  # "45 derece açı"
        carpan = CARPAN[m.group("k")]
        a = sayi_oku(m.group("a")) * carpan
        b = sayi_oku(m.group("b")) * carpan if m.group("b") else a
        bas = m.start()
        if m.group("neg"):
            if boyut == "sıcaklık":  # "-174 ⁰C"
                a, b = -a, (-b if not m.group("b") else b)
            else:
                bas = m.start("a")  # eksi işareti yalnızca sıcaklıkta sayının parçasıdır
        hamlar.append(_ham_olustur(bas, m.end(), boyut, birim, _BIRIMLER[boyut][birim], a, b))

    for desen in (_YUZDE_ONDE, _YUZDE_SONDA, _YUZDE_SOZ):
        for m in desen.finditer(metin):
            a = sayi_oku(m.group("a"))
            b = sayi_oku(m.group("b")) if "b" in m.groupdict() and m.group("b") else a
            if max(a, b) > 1000:
                continue
            hamlar.append(_ham_olustur(m.start(), m.end(), "yüzde", "%", 1.0, a, b))

    # çakışan eşleşmelerde (ör. "%71" iki desenle) ilk bulunanı tut
    hamlar.sort(key=lambda h: (h.bas, -(h.son - h.bas)))
    temiz: list[_Ham] = []
    for h in hamlar:
        if temiz and h.bas < temiz[-1].son:
            continue
        temiz.append(h)

    sonuc: list[Olcu] = []
    for h in _birlestir(temiz, metin):
        yaklasik, bas, son = yaklasik_mi(metin, h.bas, h.son)
        katsayi = _BIRIMLER[h.boyut][h.birim] if h.boyut in _BIRIMLER else 1.0
        tolerans = GORELI_TOLERANS * max(abs(h.alt), abs(h.ust))
        if yaklasik:
            tolerans += _yuvarlama_tolerans(h.yazilan, katsayi)
        sonuc.append(Olcu(bas=bas, son=son, boyut=h.boyut, alt=h.alt, ust=h.ust, yaklasik=yaklasik,
                          tolerans=tolerans, birim=h.birim))
    return sonuc


# ------------------------------------------------------------------ gösterim


def sayi_yaz(deger: float) -> str:
    """Türkçe sayı yazımı: binlik ayırıcı nokta, ondalık virgül (en çok 2 basamak)."""
    if abs(deger - round(deger)) < 0.005:
        return f"{round(deger):,}".replace(",", ".")
    tam, _, kesir = f"{deger:,.2f}".partition(".")
    return tam.replace(",", ".") + "," + kesir.rstrip("0")


def okunur(deger: float, boyut: str) -> str:
    """Tabandaki değeri okunur bir birimle yazar: 86400 (zaman) -> "24 saat"."""
    if boyut == "zaman":
        for birim, katsayi in (("yıl", 31_557_600), ("gün", 86400), ("saat", 3600), ("dakika", 60)):
            if abs(deger) >= katsayi:
                return f"{sayi_yaz(deger / katsayi)} {birim}"
        return f"{sayi_yaz(deger)} saniye"
    if boyut == "uzunluk":
        for birim, katsayi in (("km", 1000), ("m", 1), ("cm", 0.01)):
            if abs(deger) >= katsayi:
                return f"{sayi_yaz(deger / katsayi)} {birim}"
        return f"{sayi_yaz(deger * 1000)} mm"
    if boyut == "kütle":
        for birim, katsayi in (("ton", 1_000_000), ("kg", 1000)):
            if abs(deger) >= katsayi:
                return f"{sayi_yaz(deger / katsayi)} {birim}"
        return f"{sayi_yaz(deger)} g"
    if boyut == "yüzde":
        return f"%{sayi_yaz(deger)}"
    return f"{sayi_yaz(deger)} {'N' if boyut == 'kuvvet' else '°C'}"
