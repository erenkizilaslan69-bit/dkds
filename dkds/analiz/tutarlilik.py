"""Tutarlılık analizörü (kriter 3): kitap içi bilgi tutarsızlığı. İlk sürüm: kural tabanlı, yalnızca TARİH olguları.

Gerçek dünyaya göre doğruluk değil, kitabın kendi içindeki çelişki aranır: aynı varlık için kitabın
farklı yerlerinde farklı tarih verilmişse aday çelişki üretilir. LLM kullanılmaz.

Adımlar:
  1. Olgu çıkarma: "MÖ 7500", "M.Ö. 7500", "MS 1071", "MÖ 10000 yıllarında", "9 500 yıl önce",
     "12.000 yıl önce", "yaklaşık 12 bin yıl önce", "11.500-12.000 yıl önce" gibi ifadeler.
     Her olgu için "yaklaşık mı kesin mi" kaydedilir ("yaklaşık", "civarında", "yıllarında"... yaklaşıktır).
  2. Normalleştirme: hepsi "günümüzden kaç yıl önce"ye çevrilir. Kitabın kendi sayma kuralı
     (sosyalbilgiler5.pdf s.112: "2000'li yıllarda olduğumuz düşünüldüğünde"): MÖ yıl + 2000,
     MS yıl için 2000 - yıl. Referans yıl parametredir (REFERANS_YILI).
  3. Varlık eşleştirme: tarihin ait olduğu özel isim = aynı cümledeki en yakın özel isim
     ("Çatalhöyük'te" -> "Çatalhöyük"). Bulunamazsa olgu karşılaştırmaya katılmaz.
  4. Karşılaştırma: aynı varlığın farklı sayfalardaki değerleri arasındaki fark, yuvarlama birimine
     göre tanınan toleransı aşıyorsa aday çelişki. Yaklaşık değer için tolerans, yazılan sayının
     yuvarlama basamağının yarısıdır (9000 -> binler basamağı -> ±500); kesin değerde tolerans yoktur.
"""
from __future__ import annotations

import re
from collections import defaultdict
from collections.abc import Iterable
from dataclasses import dataclass, field

from ..models import Bulgu, Konum, Paragraf
from .okunabilirlik import cumlelere_ayir

KRITER = "tutarlilik"
TUR_TARIH = "tarih_celiskisi"
REFERANS_YILI = 2000  # kitabın kendi kuralı: "2000'li yıllarda olduğumuz düşünüldüğünde"

# En yakın özel ismin aranacağı en uzak mesafe (karakter) ve en az "yıl önce" değeri
VARLIK_EN_FAZLA_UZAKLIK = 80
EN_AZ_YIL_ONCE = 100
# Yuvarlama basamağı üst sınırı: "MÖ 10000 yıllarında" ±5000 değil ±500 sayılır
YUVARLAMA_UST_SINIR = 1000

_HARF = "A-Za-zÇĞİÖŞÜçğıöşüÂâÎîÛû"
_SAYI = r"\d{1,3}(?:[.\s  ]\d{3})+|\d+(?:,\d+)?"
_ARALIK = r"\s*[-–—]\s*"
_ERA = r"M\.?\s?[ÖS]\b\.?"
_ASIL_OLMAYAN = r"(?!\s*\.?\s*(?:yüzyıl|binyıl|yy\b))"  # "MÖ 7. yüzyıl" bir yıl değildir

# "MÖ 7500", "M.Ö. 7500", "MS 1071", "MÖ 3000-2000", "MÖ 7500'lü yıllarda"
_ERA_KALIBI = re.compile(
    rf"(?<![{_HARF}])(?P<era>{_ERA})\s*(?P<a>{_SAYI})(?:{_ARALIK}(?:{_ERA}\s*)?(?P<b>{_SAYI}))?"
    rf"{_ASIL_OLMAYAN}"
)
# "9 500 yıl önce", "12.000 yıl önce", "12 bin yıl önce", "11.500-12.000 yıl önce", "10-12 bin yıl önce"
_ONCE_KALIBI = re.compile(
    rf"(?<![\d.,])(?P<a>{_SAYI})(?:{_ARALIK}(?P<b>{_SAYI}))?\s*(?P<k>bin|milyon|milyar)?\s*yıl\s+önce\b"
)
_CARPAN = {None: 1, "bin": 1_000, "milyon": 1_000_000, "milyar": 1_000_000_000}

_ONCEKI_YAKLASIK = re.compile(
    r"\b(?:yaklaşık(?: olarak)?|takriben|tahminen|kabaca|aşağı yukarı)\b[^.;:]{0,18}$", re.IGNORECASE)
_SONRAKI_YAKLASIK = re.compile(
    r"^\s*(?:(?:['’]\s*(?:li|lı|lu|lü)\s+)?(?:yıllarında|yıllarına|yıllarda|yıllarından|yılları|civarında|civarı|"
    r"dolaylarında|sıralarında)\b|['’](?:lerde|larda|lerin|ların)\b)",
    re.IGNORECASE,
)
CUMLE_BASI_ISARETLERI = " \"“‘'(«-–—:;"

_BUYUK_HARFLI = re.compile(rf"[A-ZÇĞİÖŞÜ][{_HARF}0-9’']*")
_KUCUK_KELIME = re.compile(rf"\b[a-zçğıöşü][{_HARF}]*")
_KESME = re.compile(r"['’]")

# Tarihin "ait olduğu varlık" olamayacak büyük harfli sözcükler: ay ve gün adları, soru/etkinlik
# sözcükleri ve çok sayıda olaya ev sahipliği yapan genel bölge/dönem adları (aynı bölgede farklı
# olayların farklı tarihleri çelişki değildir). Kitaplar incelenerek genişletildi (bkz. CLAUDE.md).
VARLIK_DISI = frozenset(
    """
    ocak şubat mart nisan mayıs haziran temmuz ağustos eylül ekim kasım aralık
    pazartesi salı çarşamba perşembe cuma cumartesi pazar
    görsel etkinlik kaynak örneğin bundan günümüzden yaklaşık milattan hz bkz dr prof
    türkiye anadolu mezopotamya avrupa asya afrika amerika dünya yunanistan mısır iran irak suriye
    neolitik paleolitik mezolitik kalkolitik çağ çağı çağ’da dönem dönemi dönemde yüzyıl
    cumhuriyet osmanlı türk türkler
    """.split()
)


def _kucuk(metin: str) -> str:
    """Türkçe küçük harf (casefold "İ"yi "i̇" yapar)."""
    return metin.replace("İ", "i").replace("I", "ı").lower()


def sayi_oku(metin: str) -> float:
    """"7500", "9 500", "12.000", "1,5" gibi yazılışı sayıya çevirir (binlik ayırıcı: boşluk ya da nokta)."""
    metin = metin.strip()
    if "," in metin:
        return float(metin.replace(".", "").replace(" ", "").replace(" ", "").replace(" ", "")
                     .replace(",", "."))
    return float(re.sub(r"[.\s  ]", "", metin))


def yuvarlama_birimi(yazilan: float, yil_once: float) -> float:
    """Yazılan sayının yuvarlama basamağı: sondaki sıfırların on kuvveti (9000 -> 1000, 12 bin -> 1000).

    "MÖ 10000 yıllarında" gibi çok yuvarlak sayılarda birim, günümüzden-yıl değerinin büyüklüğüne
    göre sınırlanır (en çok 1000; milyonlu değerlerde basamak sayısının üçte biri).
    """
    sayi = int(round(yazilan))
    sifirlar = len(str(sayi)) - len(str(sayi).rstrip("0")) if sayi else 0
    birim = 10 ** sifirlar
    basamak = len(str(int(abs(yil_once))))
    ust = max(YUVARLAMA_UST_SINIR, 10 ** max(0, basamak - 3))
    return float(min(birim, ust))


@dataclass
class TarihOlgusu:
    """Metinde bulunan bir tarih ifadesi ve günümüzden-yıl-önce karşılığı."""

    sayfa: int
    paragraf: int
    konum: Konum
    ifade: str  # metinde geçtiği biçimiyle ("yaklaşık 9000 yıl önce", "MÖ 7500")
    alt: float  # günümüzden kaç yıl önce (aralıksa alt sınır)
    ust: float
    yaklasik: bool
    tolerans: float  # yaklaşık değerde yuvarlama birimi / 2, kesinde 0
    cumle: str
    varlik: str | None = None  # görünen ad ("Çatalhöyük")
    anahtar: str | None = None  # karşılaştırma anahtarı (küçük harf)

    @property
    def deger(self) -> float:
        return (self.alt + self.ust) / 2


@dataclass
class TutarlilikSonucu:
    bulgular: list[Bulgu] = field(default_factory=list)
    olgular: list[TarihOlgusu] = field(default_factory=list)
    ozet: dict = field(default_factory=dict)


# ------------------------------------------------------------------ olgu çıkarma


def _yaklasik_mi(cumle: str, bas: int, son: int) -> tuple[bool, int, int]:
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


def olgulari_bul(cumle: str, referans_yili: int = REFERANS_YILI) -> list[tuple[int, int, float, float, bool, float]]:
    """Cümledeki tarih ifadeleri: (başlangıç, bitiş, alt, üst, yaklaşık, tolerans). Konumlar cümleye göredir."""
    bulunanlar = []

    for m in _ERA_KALIBI.finditer(cumle):
        a = sayi_oku(m.group("a"))
        b = sayi_oku(m.group("b")) if m.group("b") else a
        if m.group("era").replace(".", "").replace(" ", "")[-1] == "Ö":
            degerler = [a + referans_yili, b + referans_yili]
        else:
            degerler = [referans_yili - a, referans_yili - b]
        bulunanlar.append((m.start(), m.end(), degerler, [a, b]))

    for m in _ONCE_KALIBI.finditer(cumle):
        carpan = _CARPAN[m.group("k")]  # "10-12 bin yıl önce": çarpan iki uca da uygulanır
        a = sayi_oku(m.group("a")) * carpan
        b = sayi_oku(m.group("b")) * carpan if m.group("b") else a
        if max(a, b) < EN_AZ_YIL_ONCE:
            continue
        bulunanlar.append((m.start(), m.end(), [a, b], [a, b]))

    sonuc = []
    for bas, son, degerler, yazilanlar in sorted(bulunanlar):
        yaklasik, bas2, son2 = _yaklasik_mi(cumle, bas, son)
        alt, ust = sorted(degerler)
        tolerans = (yuvarlama_birimi(max(yazilanlar), ust) / 2) if yaklasik else 0.0
        sonuc.append((bas2, son2, alt, ust, yaklasik, tolerans))
    return sonuc


# ------------------------------------------------------------------ varlık eşleştirme


def en_yakin_varlik(cumle: str, bas: int, son: int, kucuk_kelimeler: frozenset[str] = frozenset()) -> str | None:
    """Tarih ifadesine (cumle[bas:son]) en yakın özel isim (öbek); yoksa None.

    Büyük harfle başlayan sözcük adaydır; kesme işaretinden sonraki ek atılır ("Çatalhöyük’te" ->
    "Çatalhöyük"). Yan yana büyük harfli sözcükler tek isimdir ("Karain Mağarası"). Cümle başındaki
    büyük harfli sözcük, kitapta küçük harfle de geçiyorsa sıradan bir sözcüktür ("Bundan",
    "Günümüzde"). Eşit uzaklıkta önceki isim tercih edilir ("Çatalhöyük (MÖ 7500)").
    """
    # 1. geçerli büyük harfli sözcükler: (başlangıç, bitiş, ad)
    sozcukler: list[tuple[int, int, str]] = []
    for m in _BUYUK_HARFLI.finditer(cumle):
        if bas <= m.start() < son:
            continue
        ad = _KESME.split(m.group(0))[0]
        if len([k for k in ad if k.isalpha()]) < 3 or _kucuk(ad) in VARLIK_DISI:
            continue
        cumle_basi = not cumle[:m.start()].strip(CUMLE_BASI_ISARETLERI)
        if cumle_basi and _kucuk(ad) in kucuk_kelimeler:
            continue
        sozcukler.append((m.start(), m.end(), ad))

    # 2. yan yana (arada tek boşluk) olanları öbekte birleştir; kesmeli sözcük öbeği bitirir
    obekler: list[tuple[int, int, str]] = []
    for bs, bt, ad in sozcukler:
        if obekler and cumle[obekler[-1][1]:bs] == " " and not _KESME.search(cumle[obekler[-1][0]:obekler[-1][1]]):
            obekler[-1] = (obekler[-1][0], bt, obekler[-1][2] + " " + ad)
        else:
            obekler.append((bs, bt, ad))

    en_iyi: tuple[int, int, str] | None = None
    for bs, bt, ad in obekler:
        uzaklik = max(bas - bt if bt <= bas else bs - son, 0)
        if uzaklik > VARLIK_EN_FAZLA_UZAKLIK:
            continue
        oncelik = 0 if bt <= bas else 1
        if en_iyi is None or (uzaklik, oncelik) < (en_iyi[0], en_iyi[1]):
            en_iyi = (uzaklik, oncelik, ad)
    return en_iyi[2] if en_iyi else None


def _fark(a: TarihOlgusu, b: TarihOlgusu) -> float:
    """İki olgunun aralıkları arasındaki boşluk (üst üste biniyorsa 0)."""
    return max(0.0, max(a.alt, b.alt) - min(a.ust, b.ust))


def celisiyor_mu(a: TarihOlgusu, b: TarihOlgusu) -> bool:
    """Fark, iki olgunun yuvarlama toleransı toplamından küçükse yuvarlama olarak açıklanabilir.

    Sınırdaki fark (ör. yaklaşık 9000 ≈ 8500-9500 ve kesin 9500) aday sayılır: yuvarlamayla
    açıklanabilir ama kitabın aynı olay için iki farklı sayı vermesi okuyucuyu yanıltır.
    """
    fark = _fark(a, b)
    return fark > 0 and fark >= a.tolerans + b.tolerans


def guven_hesapla(a: TarihOlgusu, b: TarihOlgusu) -> float:
    """Fark büyüklüğüne ve yaklaşıklığa göre 0-1 güven.

    Yaklaşık değer varsa fark/tolerans oranı 1'de 0,45 (orta), 4 ve üstünde 0,75; ikisi de kesinse
    göreli farka göre 0,65-0,90.
    """
    fark = _fark(a, b)
    toplam_tolerans = a.tolerans + b.tolerans
    if toplam_tolerans > 0:
        oran = fark / toplam_tolerans
        return 0.45 + 0.30 * min(1.0, (oran - 1.0) / 3.0)
    goreli = fark / max((a.deger + b.deger) / 2, 1.0)
    return 0.65 + 0.25 * min(1.0, goreli / 0.2)


# ------------------------------------------------------------------ analizör


class TutarlilikAnalizoru:
    """Kitaptaki tarih olgularını çıkarır ve aynı varlığın farklı sayfalardaki tarihlerini karşılaştırır."""

    def __init__(self, referans_yili: int = REFERANS_YILI) -> None:
        self.referans_yili = referans_yili

    def analiz_et(self, paragraflar: Iterable[Paragraf]) -> list[Bulgu]:
        return self.incele(paragraflar).bulgular

    def olgulari_cikar(self, paragraflar: Iterable[Paragraf]) -> list[TarihOlgusu]:
        paragraflar = list(paragraflar)
        kucukler = frozenset(_kucuk(k) for p in paragraflar for k in _KUCUK_KELIME.findall(p.metin))
        olgular: list[TarihOlgusu] = []
        for p in paragraflar:
            for cumle in cumlelere_ayir(p.metin):
                for bas, son, alt, ust, yaklasik, tolerans in olgulari_bul(cumle, self.referans_yili):
                    varlik = en_yakin_varlik(cumle, bas, son, kucukler)
                    olgular.append(TarihOlgusu(
                        sayfa=p.sayfa, paragraf=p.paragraf, konum=p.konum, ifade=cumle[bas:son].strip(),
                        alt=alt, ust=ust, yaklasik=yaklasik, tolerans=tolerans, cumle=cumle,
                        varlik=varlik, anahtar=_kucuk(varlik) if varlik else None,
                    ))
        return olgular

    def incele(self, paragraflar: Iterable[Paragraf]) -> TutarlilikSonucu:
        olgular = self.olgulari_cikar(paragraflar)
        varlik_olgulari: dict[str, list[TarihOlgusu]] = defaultdict(list)
        for o in olgular:
            if o.anahtar:
                varlik_olgulari[o.anahtar].append(o)

        bulgular: list[Bulgu] = []
        for anahtar, liste in varlik_olgulari.items():
            bulgular += self._varlik_bulgulari(liste)
        bulgular.sort(key=lambda b: (b.sayfa, b.paragraf))

        ozet = {
            "referans_yili": self.referans_yili,
            "olgu_sayisi": len(olgular),
            "varlikli_olgu": sum(1 for o in olgular if o.anahtar),
            "varliksiz_olgu": sum(1 for o in olgular if not o.anahtar),
            "varlik_sayisi": len(varlik_olgulari),
            "birden_cok_sayfadaki_varlik": sum(1 for v in varlik_olgulari.values() if len({o.sayfa for o in v}) > 1),
            "aday_celiski": len(bulgular),
        }
        return TutarlilikSonucu(bulgular=bulgular, olgular=olgular, ozet=ozet)

    # ------------------------------------------------------------------ karşılaştırma

    def _varlik_bulgulari(self, liste: list[TarihOlgusu]) -> list[Bulgu]:
        """Bir varlığın olgularını birbiriyle çelişmeyen kümelere ayırır; kümeler çelişiyorsa bulgu üretir."""
        liste = sorted(liste, key=lambda o: (o.sayfa, o.paragraf, o.alt))
        kumeler: list[list[TarihOlgusu]] = []
        for o in liste:
            for kume in kumeler:
                if not celisiyor_mu(kume[0], o):
                    kume.append(o)
                    break
            else:
                kumeler.append([o])

        bulgular = []
        for i, k1 in enumerate(kumeler):
            for k2 in kumeler[i + 1:]:
                cift = next(((a, b) for a in k1 for b in k2 if a.sayfa != b.sayfa and celisiyor_mu(a, b)), None)
                if cift is None:
                    continue
                a, b = cift
                # Bulgu, küçük kümedeki (eşitse sonraki sayfadaki) olguya yazılır; diğer tarafı "ilgili" gösterir
                if (len(k1), -a.sayfa) < (len(k2), -b.sayfa):
                    asil, ilgili, asil_kume, ilgili_kume = a, b, k1, k2
                else:
                    asil, ilgili, asil_kume, ilgili_kume = b, a, k2, k1
                bulgular.append(self._bulgu(asil, ilgili, asil_kume, ilgili_kume))
        return bulgular

    def _bulgu(self, asil: TarihOlgusu, ilgili: TarihOlgusu, asil_kume: list[TarihOlgusu],
               ilgili_kume: list[TarihOlgusu]) -> Bulgu:
        fark = _fark(asil, ilgili)
        destek = sorted({o.sayfa for o in ilgili_kume if o is not ilgili})
        aciklama = (
            f"«{asil.varlik}» için kitabın iki yerinde farklı tarih var: s.{asil.sayfa}'de «{asil.ifade}»"
            f"{self._yil_ifadesi(asil)}, s.{ilgili.sayfa}'de «{ilgili.ifade}»{self._yil_ifadesi(ilgili)}. "
            f"Fark yaklaşık {self._yil(fark)} yıl (referans yıl {self.referans_yili})."
        )
        if destek:
            aciklama += " Diğer değer s." + ", s.".join(str(s) for s in destek) + "'de de geçiyor."
        if asil.yaklasik or ilgili.yaklasik:
            aciklama += (" Değerlerden biri yaklaşık olduğu için fark yuvarlamayla açıklanabilir; yine de aynı olay "
                         "için iki farklı sayı okuyucuyu yanıltabilir.")
        aciklama += " Olayların aynı olup olmadığı (kuruluş / yaşam dönemi gibi) basılı sayfada kontrol edilmeli."
        return Bulgu(
            sayfa=asil.sayfa, paragraf=asil.paragraf, kriter=KRITER,
            sorunlu_metin=asil.cumle if len(asil.cumle) <= 240 else asil.cumle[:237] + "…",
            aciklama=aciklama, guven=guven_hesapla(asil, ilgili),
            oneri=f"Her iki yeri kontrol edip «{asil.varlik}» için tek bir tarih kullanın ya da farkın nedenini açıklayın.",
            konum=asil.konum, tur=TUR_TARIH,
            ilgili_sayfa=ilgili.sayfa, ilgili_paragraf=ilgili.paragraf, ilgili_konum=ilgili.konum,
        )

    @staticmethod
    def _yil(sayi: float) -> str:
        return f"{round(sayi):,}".replace(",", ".")

    def _yil_ifadesi(self, o: TarihOlgusu) -> str:
        """Yalnızca "yıl önce" biçiminde yazılmamış ifadelerin yanına normalleştirilmiş değeri ekler."""
        if "yıl önce" in o.ifade:
            return ""
        if o.alt == o.ust:
            return f" (≈{self._yil(o.alt)} yıl önce)"
        return f" (≈{self._yil(o.alt)}-{self._yil(o.ust)} yıl önce)"
