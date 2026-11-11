"""Tutarlılık analizörü (kriter 3): kitap içi bilgi tutarsızlığı. Kural tabanlı; tarih ve birimli sayısal olgular.

Gerçek dünyaya göre doğruluk değil, kitabın kendi içindeki çelişki aranır: aynı varlık için kitabın
farklı yerlerinde birbirini tutmayan değer verilmişse aday çelişki üretilir. LLM kullanılmaz.

Adımlar:
  1. Olgu çıkarma.
     Tarih: "MÖ 7500", "M.Ö. 7500", "MS 1071", "MÖ 10000 yıllarında", "9 500 yıl önce",
     "12.000 yıl önce", "yaklaşık 12 bin yıl önce", "on bin yıl önce", aralıklar.
     Sayısal (sayilar.py): "24 saatte", "365 gün 6 saat", "-174 ⁰C", "384.000 km", "%71", "1 milyon km".
     Yazıyla sayılar ("yirmi dört saat") ikisinde de rakama çevrilir. Her olgu için yaklaşık / kesin kaydedilir.
  2. Normalleştirme: tarihler "günümüzden kaç yıl önce"ye (MÖ yıl + 2000, kitabın kendi kuralı, referans yıl
     parametre), ölçüler ortak tabana (saniye, metre, gram, N, °C, %) çevrilir.
  3. Olgu anahtarı = varlık + nicelik türü + bağlam. Varlık: aynı cümledeki en yakın özel isim. Tür:
     sıcaklık / uzaklık / çap / dönme süresi gibi (sözlükle); ayırıcı: gece, gündüz, ortalama, en yüksek...;
     bağlam: ifadenin çevresindeki içerik sözcükleri. Gece sıcaklığı ile gündüz sıcaklığı karıştırılmaz.
  4. Karşılaştırma: aynı varlık ve boyuttaki, değerleri toleransı aşacak kadar farklı iki olgu
       - türleri farklıysa ya da ayırıcıları farklıysa: farklı nicelik (sayılmaz),
       - tür aynı, ayırıcı aynı ve bağlam benzerse: ADAY ÇELİŞKİ,
       - emin olunamıyorsa: BELİRSİZ (ayrıca raporlanır; sonraki adımda LLM'e gidecek).
     Tarih olgularında varlık yeterlidir; yalnızca olay türleri (kuruluş / terk) farklıysa ayrı sayılır.
"""
from __future__ import annotations

import re
from collections import defaultdict
from collections.abc import Iterable, Sequence
from dataclasses import dataclass, field

from ..models import Bulgu, Konum, Paragraf
from .okunabilirlik import cumlelere_ayir
from .sayilar import (
    ARALIK,
    CARPAN,
    HARF,
    SAYI,
    kucuk,
    okunur,
    olculeri_bul,
    rakamlastir,
    sayi_oku,
    sayi_yaz,
    yaklasik_mi,
)

KRITER = "tutarlilik"
TUR_TARIH = "tarih_celiskisi"
TUR_SAYISAL = "sayisal_celiski"
REFERANS_YILI = 2000  # kitabın kendi kuralı: "2000'li yıllarda olduğumuz düşünüldüğünde"

# En yakın özel ismin aranacağı en uzak mesafe (karakter) ve en az "yıl önce" değeri
VARLIK_EN_FAZLA_UZAKLIK = 80
IKINCIL_VARLIK_UZAKLIGI = 40  # ölçülerde ikinci varlığın en uzak mesafesi
OLCU_VARLIK_SAYISI = 2
EN_AZ_YIL_ONCE = 100
# Yuvarlama basamağı üst sınırı: "MÖ 10000 yıllarında" ±5000 değil ±500 sayılır
YUVARLAMA_UST_SINIR = 1000
# Tür / ayırıcı / bağlam sözcüklerinin aranacağı pencere (karakter, ifadenin iki yanı)
BAGLAM_PENCERESI = 80
TUR_PENCERESI = 70
AYIRICI_ILERI_MESAFE = 40  # ayırıcıdan sonraki ölçüye en çok bu kadar karakter uzaklık
# Aynı nicelik sayılması için bağlam sözcüklerinin en az benzerliği (Jaccard)
EN_AZ_BAGLAM_BENZERLIGI = 0.1
# Varlığı belli olmayan olgular için ("Bu dönme hareketi 24 saatte tamamlanır") ortak bağlam eşiği: daha sıkı
VARLIKSIZ_EN_AZ_BAGLAM_BENZERLIGI = 0.25
VARLIKSIZ_EN_AZ_ORTAK_KOK = 2
# "Zayıf" belirsiz: daha gevşek eşik (alıştırma cümleleri gibi gürültü de çıkar; LLM için ayrı etiketlenir)
ZAYIF_EN_AZ_BAGLAM_BENZERLIGI = 0.15
ZAYIF_EN_AZ_ORTAK_KOK = 1

_ERA = r"M\.?\s?[ÖS]\b\.?"
_ASIL_OLMAYAN = r"(?!\s*\.?\s*(?:yüzyıl|binyıl|yy\b))"  # "MÖ 7. yüzyıl" bir yıl değildir

# "MÖ 7500", "M.Ö. 7500", "MS 1071", "MÖ 3000-2000", "MÖ 7500'lü yıllarda"
_ERA_KALIBI = re.compile(
    rf"(?<![{HARF}])(?P<era>{_ERA})\s*(?P<a>{SAYI})(?:{ARALIK}(?:{_ERA}\s*)?(?P<b>{SAYI}))?{_ASIL_OLMAYAN}"
)
# "9 500 yıl önce", "12.000 yıl önce", "12 bin yıl önce", "11.500-12.000 yıl önce", "10-12 bin yıl önce"
_ONCE_KALIBI = re.compile(
    rf"(?<![\d.,])(?P<a>{SAYI})(?:{ARALIK}(?P<b>{SAYI}))?\s*(?P<k>bin|milyon|milyar)?\s*yıl\s+önce\b"
)

_BUYUK_HARFLI = re.compile(rf"[A-ZÇĞİÖŞÜ][{HARF}0-9’']*")
_KUCUK_KELIME = re.compile(rf"\b[a-zçğıöşü][{HARF}]*")
_KESME = re.compile(r"['’]")
_SOZCUK = re.compile(rf"[{HARF}]+")
CUMLE_BASI_ISARETLERI = " \"“‘'(«-–—:;"

# Tarihin "ait olduğu varlık" olamayacak büyük harfli sözcükler: ay ve gün adları, soru/etkinlik
# sözcükleri ve çok sayıda olaya ev sahipliği yapan genel bölge/dönem adları (aynı bölgede farklı
# olayların farklı tarihleri çelişki değildir). Liste elle yazıldı; kitaplardaki gürültüye göre ayarlanmadı.
VARLIK_DISI = frozenset(
    """
    ocak şubat mart nisan mayıs haziran temmuz ağustos eylül ekim kasım aralık
    pazartesi salı çarşamba perşembe cuma cumartesi pazar
    görsel etkinlik kaynak örneğin bundan günümüzden yaklaşık milattan hz bkz dr prof
    süre amaç adı konu araç gereç malzeme yönerge kazanım soru sorular
    """.split()
)
# Yalnızca TARİH olgularında varlık sayılmayanlar: bu adlar çok sayıda olaya ev sahipliği yapar. Ölçülerde
# ("Dünya'nın çevresi", "Türkiye'nin yüzölçümü") geçerli varlıktır.
TARIH_VARLIK_DISI = frozenset(
    """
    türkiye anadolu mezopotamya avrupa asya afrika amerika dünya yunanistan mısır iran irak suriye
    neolitik paleolitik mezolitik kalkolitik çağ çağı çağ’da dönem dönemi dönemde yüzyıl
    cumhuriyet osmanlı türk türkler
    """.split()
)
_ETIKET_SONU = re.compile(r"\s+:")  # "Süre : 40 dk" gibi form etiketi
_KUNYE_ETIKETI = re.compile(r"\b(?:Adı|Amaç|Süre|Konu|Kazanım|Araç|Gereç|Malzeme)\b")
_SURE_ETIKETI = re.compile(r"\bSüre\s*:?\s*$")
# Değerlendirme/alıştırma yönergesi: altındaki maddeler (bilerek yanlış yazılmış olabilir) olgu sayılmaz
_YONERGE = re.compile(  # güçlü: altındaki maddeler doğru/yanlış ya da boşluk doldurma maddesidir
    r"doğru\s+ise|yanlış\s+ise|doğru\s+(?:ya\s+da|veya)\s+yanlış|[“”‘’]D[“”‘’].{0,20}[“”‘’]Y[“”‘’]|\bD\s*/\s*Y\b"
    r"|boşlukları\s+doldur|boşluğa",
    re.IGNORECASE)
_YONERGE_ZAYIF = re.compile(  # zayıf: etkinlik yönergesi de olabilir; yalnızca hemen altındaki madde/soru kapsanır
    r"işaretleyiniz|işaretleyin|cevaplayınız|cevaplayın|eşleştiriniz", re.IGNORECASE)
_MADDE_BASI = re.compile(r"^\(\s*[….\s]*\)")  # "(……) Türkiye'de ..." doğru/yanlış maddesi
YONERGE_EN_COK_KELIME = 40  # daha uzun paragraf yönerge değil anlatımdır
BLOK_BITIREN_KELIME = 30  # alıştırma maddeleri kısadır; bundan uzun gövde paragrafı anlatım/okuma metnidir
# Zamir çözümleme: varlığı olmayan cümle zamir/gösterme sözcüğüyle başlıyorsa varlık önceki cümleden alınır
# (bağlaçla başlayan cümleler denendi: "Ardından tahminlerinize..." gibi yanlış varlık getirdi, kapsam dışı)
_ANAFORA = re.compile(r"(?:bu|bun\w*|şu|şun\w*|o|onun|onlar\w*|ona|onu|söz konusu|aynı)\b", re.IGNORECASE)
ANAFORA_GERI_CUMLE = 2  # en çok bu kadar önceki cümleye (aynı paragrafta) bakılır
_COGUL_OZNE = re.compile(r"([A-ZÇĞİÖŞÜ][a-zçğıöşü]{3,}(?:lar|ler))\b")
_COGUL_DISI = frozenset("bunlar onlar şunlar aşağıdakiler yukarıdakiler diğerleri bazıları hepsi".split())
VARLIK_KAYNAGI_CARPANI = {"cumle": 1.0, "cogul": 0.9, "onceki": 0.8}  # bulgu güveni bununla çarpılır
KUNYE_EN_AZ_ETIKET = 2  # etkinlik künyesi ("Adı ... Amaç ... Süre 80 dk"): süre/amaç karşılaştırılacak bir olgu değil
# Öbeğin son sözcüğü bunlardan biriyse ("Karain Mağarası") son sözcükle eşleşme yapılmaz: genel ad
# olduğundan farklı varlıkları birleştirirdi
GENEL_SON_SOZCUKLER = frozenset(
    """
    mağarası höyüğü tepe tepesi şehri kenti krallığı devleti savaşı medresesi camisi kralı imparatoru
    dağı nehri ırmağı gölü denizi boğazı adası yarımadası müzesi projesi anıtı sarayı kalesi köyü
    ovası vadisi uygarlığı medeniyeti toplumu halkı bakanlığı başkanı bakanı
    """.split()
)

# ------------------------------------------------------------------ olgu modeli


def _kucuk(metin: str) -> str:
    return kucuk(metin)


@dataclass
class Olgu:
    """Metinde bulunan bir tarih ya da birimli ölçü ifadesi ve ortak tabandaki karşılığı."""

    sayfa: int
    paragraf: int
    konum: Konum
    ifade: str  # metinde geçtiği biçimiyle ("yaklaşık 9000 yıl önce", "MÖ 7500", "yirmi dört saat")
    alt: float  # tarihte günümüzden kaç yıl önce; ölçüde ortak tabanda (aralıksa alt sınır)
    ust: float
    yaklasik: bool
    tolerans: float  # yaklaşık değerde yuvarlama birimi / 2 (ölçüde ayrıca %1 göreli), tarihte kesinde 0
    cumle: str
    varlik: str | None = None  # görünen ad ("Çatalhöyük")
    anahtar: str | None = None  # karşılaştırma anahtarı (küçük harf)
    boyut: str = "tarih"  # tarih, zaman, uzunluk, kütle, kuvvet, sıcaklık, yüzde
    tur: str | None = None  # nicelik türü (sıcaklık, uzaklık, çap...) ya da tarihte olay (başlangıç/bitiş)
    ayirici: frozenset = frozenset()  # gece, gündüz, ortalama, en_yüksek...
    baglam: frozenset = frozenset()  # çevredeki içerik sözcüklerinin kökleri
    anahtarlar: tuple = ()  # eşleşme anahtarları (öbekte tam ad ve son sözcük)
    # Aynı cümledeki, farklı boyuttaki diğer ölçüler: (boyut, alt, üst, tolerans). "60 kg kütleli cismin
    # ağırlığı 100 N" cümlesinde 100 N'nin koşulu 60 kg'dır.
    kosullar: tuple = ()
    # Varlığın nereden geldiği: "cumle" (cümlede geçen özel isim), "onceki" (zamirli cümlede önceki cümleden
    # devralındı), "cogul" (çoğul özne: "Yılanlar 10 yıl yaşar"). Devralınan varlığın güveni düşürülür.
    varlik_kaynagi: str = "cumle"

    @property
    def deger(self) -> float:
        return (self.alt + self.ust) / 2


TarihOlgusu = Olgu  # ilk sürümdeki ad


@dataclass
class Belirsiz:
    """Aynı nicelik olup olmadığı anlaşılamayan, değerleri farklı iki olgu (LLM'e gidecek)."""

    varlik: str
    boyut: str
    a: Olgu
    b: Olgu
    neden: str
    guc: str = "guclu"  # "guclu" | "zayif" (varlıksız eşleşmede gevşek eşikle bulunanlar)

    def sozluk(self) -> dict:
        return {
            "varlik": self.varlik, "boyut": self.boyut, "neden": self.neden, "guc": self.guc,
            "sayfa_1": self.a.sayfa, "ifade_1": self.a.ifade, "tur_1": self.a.tur,
            "ayirici_1": sorted(self.a.ayirici), "cumle_1": self.a.cumle,
            "sayfa_2": self.b.sayfa, "ifade_2": self.b.ifade, "tur_2": self.b.tur,
            "ayirici_2": sorted(self.b.ayirici), "cumle_2": self.b.cumle,
        }


@dataclass
class TutarlilikSonucu:
    bulgular: list[Bulgu] = field(default_factory=list)
    olgular: list[Olgu] = field(default_factory=list)
    belirsizler: list[Belirsiz] = field(default_factory=list)
    ozet: dict = field(default_factory=dict)


# ------------------------------------------------------------------ tarih olgusu çıkarma


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


def _tarihleri_bul(metin: str, referans_yili: int) -> list[tuple[int, int, float, float, bool, float]]:
    """Rakamlaştırılmış metindeki tarih ifadeleri: (başlangıç, bitiş, alt, üst, yaklaşık, tolerans)."""
    bulunanlar = []

    for m in _ERA_KALIBI.finditer(metin):
        a = sayi_oku(m.group("a"))
        b = sayi_oku(m.group("b")) if m.group("b") else a
        if m.group("era").replace(".", "").replace(" ", "")[-1] == "Ö":
            degerler = [a + referans_yili, b + referans_yili]
        else:
            degerler = [referans_yili - a, referans_yili - b]
        bulunanlar.append((m.start(), m.end(), degerler, [a, b]))

    for m in _ONCE_KALIBI.finditer(metin):
        carpan = CARPAN[m.group("k")]  # "10-12 bin yıl önce": çarpan iki uca da uygulanır
        a = sayi_oku(m.group("a")) * carpan
        b = sayi_oku(m.group("b")) * carpan if m.group("b") else a
        if max(a, b) < EN_AZ_YIL_ONCE:
            continue
        bulunanlar.append((m.start(), m.end(), [a, b], [a, b]))

    sonuc = []
    for bas, son, degerler, yazilanlar in sorted(bulunanlar):
        yaklasik, bas2, son2 = yaklasik_mi(metin, bas, son)
        alt, ust = sorted(degerler)
        tolerans = (yuvarlama_birimi(max(yazilanlar), ust) / 2) if yaklasik else 0.0
        sonuc.append((bas2, son2, alt, ust, yaklasik, tolerans))
    return sonuc


def olgulari_bul(cumle: str, referans_yili: int = REFERANS_YILI) -> list[tuple[int, int, float, float, bool, float]]:
    """Cümledeki tarih ifadeleri: (başlangıç, bitiş, alt, üst, yaklaşık, tolerans). Konumlar cümleye göredir.

    Yazıyla sayılar ("on bin yıl önce") rakama çevrilerek aranır; konumlar özgün cümleye geri çevrilir.
    """
    r = rakamlastir(cumle)
    return [(*r.eski(bas, son), *geri) for bas, son, *geri in _tarihleri_bul(r.yeni, referans_yili)]


# ------------------------------------------------------------------ varlık eşleştirme


def en_yakin_varlik(cumle: str, bas: int, son: int, kucuk_kelimeler: frozenset[str] = frozenset(),
                    orta_buyukler: frozenset[str] | None = None, kisa_paragraf: bool = False,
                    tarih: bool = True) -> str | None:
    """İfadeye (cumle[bas:son]) en yakın özel isim (öbek); yoksa None. Ayrıntı için `yakin_varliklar`."""
    adlar = yakin_varliklar(cumle, bas, son, kucuk_kelimeler, orta_buyukler, kisa_paragraf, tarih, en_fazla=1)
    return adlar[0] if adlar else None


def yakin_varliklar(cumle: str, bas: int, son: int, kucuk_kelimeler: frozenset[str] = frozenset(),
                    orta_buyukler: frozenset[str] | None = None, kisa_paragraf: bool = False,
                    tarih: bool = True, en_fazla: int = 1) -> list[str]:
    """İfadeye (cumle[bas:son]) en yakın özel isimler (öbek), yakından uzağa; en çok `en_fazla` tane.

    İlki en yakın isimdir. İkincisi ve sonrası (ölçülerde: "Ay’ın Dünya’ya uzaklığı 384.400 km" cümlesinde
    hem Ay hem Dünya) yalnızca IKINCIL_VARLIK_UZAKLIGI içindeyse alınır.

    Büyük harfle başlayan sözcük adaydır; kesme işaretinden sonraki ek atılır ("Çatalhöyük’te" ->
    "Çatalhöyük"). Yan yana büyük harfli sözcükler tek isimdir ("Karain Mağarası"). Eşit uzaklıkta önceki
    isim tercih edilir ("Çatalhöyük (MÖ 7500)").

    Cümle başındaki büyük harfli sözcük çoğu zaman sıradan sözcüktür ("Bundan", "Çemberimsi anıtsal
    yapılar..."). Şu durumlarda isim sayılmaz: kitapta küçük harfle de geçiyorsa; kesme eki, virgül,
    noktalı virgül ya da parantez almıyor, öbek değil, kitapta cümle ortasında da büyük harfle
    geçmiyor ve paragraf kısa bir etiket değilse. `orta_buyukler` None ise bu son kural uygulanmaz.
    Kesmeli sözcük ("Ay’da") her zaman isimdir. Form etiketleri ("Süre : 40 dk"), BÜYÜK HARFLİ başlık
    sözcükleri ve ay/gün adları isim sayılmaz; genel bölge/dönem adları yalnızca `tarih` iken elenir.
    """
    # 1. geçerli büyük harfli sözcükler: (başlangıç, bitiş, ad, cümle başında mı, kesmeli mi)
    sozcukler: list[tuple[int, int, str, bool, bool]] = []
    for m in _BUYUK_HARFLI.finditer(cumle):
        if bas <= m.start() < son:
            continue
        ad = _KESME.split(m.group(0))[0]
        harfler = [k for k in ad if k.isalpha()]
        if len(harfler) < 3 and ad != "Ay":  # "Ay" iki harfli ama bir varlıktır
            continue
        if len(harfler) >= 2 and ad.isupper():  # BÜYÜK HARFLİ başlık sözcükleri
            continue
        if _kucuk(ad) in VARLIK_DISI or (tarih and _kucuk(ad) in TARIH_VARLIK_DISI):
            continue
        if _ETIKET_SONU.match(cumle, m.end()):  # "Süre : 40 dk" bir form etiketidir
            continue
        kesmeli = bool(_KESME.search(m.group(0)))
        cumle_basi = not re.search(r"\w", cumle[:m.start()])
        ay_ozel = ad == "Ay" and cumle[m.end():m.end() + 1] in (",", "’", "'")
        if cumle_basi and not kesmeli and not ay_ozel and _kucuk(ad) in kucuk_kelimeler:
            continue
        sozcukler.append((m.start(), m.end(), ad, cumle_basi, kesmeli))

    # 2. yan yana (arada tek boşluk) olanları öbekte birleştir; kesmeli sözcük öbeği bitirir
    obekler: list[list] = []  # [başlangıç, bitiş, ad, ilk sözcük cümle başında mı, tek sözcük mü, kesmeli mi]
    for bs, bt, ad, cumle_basi, kesmeli in sozcukler:
        if obekler and cumle[obekler[-1][1]:bs] == " " and not obekler[-1][5]:
            obekler[-1][1:6] = [bt, obekler[-1][2] + " " + ad, obekler[-1][3], False, kesmeli]
        else:
            obekler.append([bs, bt, ad, cumle_basi, True, kesmeli])

    adaylar: list[tuple[int, int, str]] = []
    for bs, bt, ad, cumle_basi, tek, kesmeli in obekler:
        if cumle_basi and tek and orta_buyukler is not None and not kesmeli:
            sonraki = cumle[bt:].lstrip()[:1]
            if sonraki not in (",", ";", "(") and _kucuk(ad) not in orta_buyukler and not kisa_paragraf:
                continue
        uzaklik = max(bas - bt if bt <= bas else bs - son, 0)
        if uzaklik > VARLIK_EN_FAZLA_UZAKLIK:
            continue
        adaylar.append((uzaklik, 0 if bt <= bas else 1, ad))
    adaylar.sort()
    return [ad for sira, (uzaklik, _, ad) in enumerate(adaylar[:en_fazla])
            if sira == 0 or uzaklik <= IKINCIL_VARLIK_UZAKLIGI]


def varlik_anahtarlari(varlik: str) -> tuple[str, ...]:
    """Eşleşme anahtarları: tam ad ve (genel ad değilse) öbeğin son sözcüğü ("Sümer Kralı Urukagina" -> "urukagina")."""
    tam = _kucuk(varlik)
    sozcukler = tam.split()
    if len(sozcukler) > 1 and len(sozcukler[-1]) >= 4 and sozcukler[-1] not in GENEL_SON_SOZCUKLER:
        return (tam, sozcukler[-1])
    return (tam,)


# ------------------------------------------------------------------ tür, ayırıcı, bağlam

# Nicelik türleri: boyut -> [(tür, sözcük kalıbı)]; ifadeye en yakın eşleşen sözcük türü belirler
_TUR_KALIPLARI = {
    "uzunluk": [
        ("yarıçap", r"yarıçap\w*"), ("çap", r"çap(?:ı|ında|ındaki|ının|a)?"),
        ("uzaklık", r"uzaklı\w*|mesafe\w*|uzak(?:ta|ında|taki)?"), ("yükseklik", r"yüksek\w*"),
        ("derinlik", r"derin\w*"), ("uzunluk", r"uzunluk\w*|uzun\w*|boy(?:u|a|unda)?"),
        ("genişlik", r"geniş\w*"), ("kalınlık", r"kalın\w*"),
    ],
    "zaman": [
        ("dönme", r"dön(?:er|me|mesi|üş|üşü)\w*|eksen\w*"), ("dolanma", r"dolan\w*|yörünge\w*"),
        ("ömür", r"ömür\w*|yaşar|yaşam"), ("süre", r"süre(?:si|sini|yle|de|nin)?|sürer|sürecek|sürmektedir"),
    ],
}
_SABIT_TUR = {"sıcaklık": "sıcaklık", "kütle": "kütle", "kuvvet": "kuvvet", "yüzde": "oran"}
_OLAY_KALIPLARI = [
    ("başlangıç", r"kur(?:ul|dular|du|muş)\w*|inşa\w*|yapıl\w*|başla\w*|ortaya çık\w*|icat\w*|doğ(?:du|muş)\w*"),
    ("bitiş", r"terk\w*|yıkıl\w*|son bul\w*|bit(?:ti|miş)\w*|çök\w*|sona er\w*|öl(?:dü|müş)\w*"),
]
_AYIRICILAR = [
    ("gece", r"\bgece\w*"), ("gündüz", r"\bgündüz\w*"), ("ortalama", r"\bortalama\w*"), ("kış", r"\bkış\w*"),
    ("sabah", r"\bsabah\w*"), ("akşam", r"\bakşam\w*"), ("kutup", r"\bkutup\w*"), ("ekvator", r"\bekvator\w*"),
    ("yüzey", r"\byüzey\w*"), ("çekirdek", r"\bçekirdek\w*"),
    ("en_yüksek", r"en yüksek|maksimum|en fazla|en büyük|en uzun|en geniş"),
    ("en_düşük", r"en düşük|minimum|en az\b|en küçük|en kısa|en dar"),
]
_DURAK = frozenset(
    """
    olarak ancak için kadar daha gibi sonra önce veya ayrıca bunun onun bazı birçok oldukça yaklaşık civarında
    arasında olan olduğu bulunan yapılan yapılır edilir edilmiştir olduğunu olduğuna tarafından göre fakat
    çünkü hangi bütün tüm kendi sadece yalnızca ise ile bir iki üç dört beş altı yedi sekiz dokuz
    saniye dakika saat gün hafta yıl metre kilometre gram kilogram newton derece
    """.split()
)


def _pencere(cumle: str, bas: int, son: int, yaricap: int) -> tuple[str, int, int, int]:
    """Cümlenin ifade çevresindeki parçası (küçük harf), ifadenin bu parçadaki konumu ve parçanın başlangıcı."""
    b = max(0, bas - yaricap)
    return _kucuk(cumle[b:son + yaricap]), bas - b, son - b, b


def _aralik_uzakligi(bas1: int, son1: int, bas2: int, son2: int) -> int:
    return max(0, bas1 - son2, bas2 - son1)


def _bana_ait(m_bas: int, m_son: int, bas: int, son: int, digerleri: Sequence[tuple[int, int]]) -> bool:
    """Bir sözcük, cümlede başka ölçü de varsa yalnızca kendisine en yakın ölçüye aittir ("gece -174, gündüz 125")."""
    benim = _aralik_uzakligi(m_bas, m_son, bas, son)
    return all(benim <= _aralik_uzakligi(m_bas, m_son, db, ds) for db, ds in digerleri)


def nicelik_turu(boyut: str, cumle: str, bas: int, son: int, digerleri: Sequence[tuple[int, int]] = ()) -> str | None:
    """Ölçünün türü: sıcaklık/kütle/kuvvet/oran sabittir; uzunluk ve zamanda ifadeye en yakın tür sözcüğü."""
    if boyut in _SABIT_TUR:
        return _SABIT_TUR[boyut]
    if boyut not in _TUR_KALIPLARI:
        return None
    pencere, pb, ps, b0 = _pencere(cumle, bas, son, TUR_PENCERESI)
    en_iyi: tuple[int, int, str] | None = None
    for m in _SOZCUK.finditer(pencere):
        if not _bana_ait(b0 + m.start(), b0 + m.end(), bas, son, digerleri):
            continue
        for tur, kalip in _TUR_KALIPLARI[boyut]:
            if re.fullmatch(kalip, m.group(0)):
                uzaklik = max(pb - m.end() if m.end() <= pb else m.start() - ps, 0)
                oncelik = 0 if m.end() <= pb else 1
                if en_iyi is None or (uzaklik, oncelik) < (en_iyi[0], en_iyi[1]):
                    en_iyi = (uzaklik, oncelik, tur)
                break
    return en_iyi[2] if en_iyi else None


def olay_turu(cumle: str, bas: int, son: int, digerleri: Sequence[tuple[int, int]] = ()) -> str | None:
    """Tarihin bağlı olduğu olay: başlangıç (kuruldu, inşa edildi) ya da bitiş (terk edildi); belli değilse None."""
    pencere, pb, ps, b0 = _pencere(cumle, bas, son, TUR_PENCERESI)
    en_iyi: tuple[int, str] | None = None
    for tur, kalip in _OLAY_KALIPLARI:
        for m in re.finditer(kalip, pencere):
            if not _bana_ait(b0 + m.start(), b0 + m.end(), bas, son, digerleri):
                continue
            uzaklik = max(pb - m.end(), m.start() - ps, 0)
            if en_iyi is None or uzaklik < en_iyi[0]:
                en_iyi = (uzaklik, tur)
    return en_iyi[1] if en_iyi else None


def _ayirici_benim_mi(m_bas: int, m_son: int, bas: int, son: int, digerleri: Sequence[tuple[int, int]]) -> bool:
    """Ayırıcı değerden önce gelir ("gece -174 ⁰C, gündüz ise 125 ⁰C"): kendinden sonraki ilk ölçüye aittir.

    Sonrasında ölçü yoksa ("-174 ⁰C gece") en yakın ölçüye aittir.
    """
    olculer = [(bas, son), *digerleri]
    sonrakiler = [(b - m_son, (b, s)) for b, s in olculer if b >= m_son and b - m_son <= AYIRICI_ILERI_MESAFE]
    if sonrakiler:
        return min(sonrakiler)[1] == (bas, son)
    return _bana_ait(m_bas, m_son, bas, son, digerleri)


def ayirici_bul(cumle: str, bas: int, son: int, digerleri: Sequence[tuple[int, int]] = ()) -> frozenset:
    """Aynı varlığın farklı niceliklerini ayıran sözcükler (gece / gündüz / ortalama / en yüksek...).

    Cümlede birden çok ölçü varsa her ayırıcı tek bir ölçüye aittir (bkz. _ayirici_benim_mi).
    """
    pencere, _, _, b0 = _pencere(cumle, bas, son, TUR_PENCERESI)
    bulunanlar = set()
    for ad, kalip in _AYIRICILAR:
        if any(_ayirici_benim_mi(b0 + m.start(), b0 + m.end(), bas, son, digerleri)
               for m in re.finditer(kalip, pencere)):
            bulunanlar.add(ad)
    return frozenset(bulunanlar)


def baglam_bul(cumle: str, bas: int, son: int, varlik: str | None,
               digerleri: Sequence[tuple[int, int]] = ()) -> frozenset:
    """İfade çevresindeki içerik sözcüklerinin ilk 5 harfi (varlığın kendi sözcükleri ve ifade hariç)."""
    pencere, pb, ps, b0 = _pencere(cumle, bas, son, BAGLAM_PENCERESI)
    varlik_kokleri = {s[:5] for s in _kucuk(varlik).split()} if varlik else set()
    kokler = set()
    for m in _SOZCUK.finditer(pencere):
        if pb <= m.start() < ps or not _bana_ait(b0 + m.start(), b0 + m.end(), bas, son, digerleri):
            continue
        sozcuk = m.group(0)
        if len(sozcuk) < 4 or sozcuk in _DURAK or sozcuk[:5] in varlik_kokleri:
            continue
        kokler.add(sozcuk[:5])
    return frozenset(kokler)


# ------------------------------------------------------------------ karşılaştırma


def _fark(a: Olgu, b: Olgu) -> float:
    """İki olgunun aralıkları arasındaki boşluk (üst üste biniyorsa 0)."""
    return max(0.0, max(a.alt, b.alt) - min(a.ust, b.ust))


def celisiyor_mu(a: Olgu, b: Olgu) -> bool:
    """Fark, iki olgunun yuvarlama toleransı toplamından küçükse yuvarlama olarak açıklanabilir.

    Sınırdaki fark (ör. yaklaşık 9000 ≈ 8500-9500 ve kesin 9500) aday sayılır: yuvarlamayla
    açıklanabilir ama kitabın aynı olay için iki farklı sayı vermesi okuyucuyu yanıltır.
    """
    fark = _fark(a, b)
    return fark > 0 and fark >= a.tolerans + b.tolerans


def guven_hesapla(a: Olgu, b: Olgu) -> float:
    """Fark büyüklüğüne ve yaklaşıklığa göre 0-1 güven.

    Tolerans varsa (yaklaşık değer ya da ölçü) fark/tolerans oranı 1'de 0,45 (orta), 4 ve üstünde 0,75;
    iki tarih de kesinse göreli farka göre 0,65-0,90.
    """
    fark = _fark(a, b)
    toplam_tolerans = a.tolerans + b.tolerans
    if toplam_tolerans > 0:
        oran = fark / toplam_tolerans
        return 0.45 + 0.30 * min(1.0, (oran - 1.0) / 3.0)
    goreli = fark / max((a.deger + b.deger) / 2, 1.0)
    return 0.65 + 0.25 * min(1.0, goreli / 0.2)


def baglam_benzerligi(a: Olgu, b: Olgu) -> float:
    birlesim = a.baglam | b.baglam
    return len(a.baglam & b.baglam) / len(birlesim) if birlesim else 0.0


def _kosul_celisiyor(k1: tuple, k2: tuple) -> bool:
    fark = max(0.0, max(k1[1], k2[1]) - min(k1[2], k2[2]))
    return fark > 0 and fark >= k1[3] + k2[3]


def kosullar_uyumlu_mu(a: Olgu, b: Olgu) -> bool:
    """İki olgunun cümlelerindeki diğer ölçüler (koşullar) birbirini karşılıyor mu?

    Bir koşul yalnızca birinde varsa ya da değerleri farklıysa ("60 kg'lık cismin ağırlığı 100 N" ve
    "cismin ağırlığı 60 N") aynı durumdan söz edildiği anlaşılamaz.
    """
    for kaynak, hedef in ((a.kosullar, b.kosullar), (b.kosullar, a.kosullar)):
        for k in kaynak:
            if not any(k2[0] == k[0] and not _kosul_celisiyor(k, k2) for k2 in hedef):
                return False
    return True


def eslestir(a: Olgu, b: Olgu) -> tuple[str, str]:
    """Değerleri çelişen iki olgunun ilişkisi: ("aday" | "belirsiz" | "farkli", neden).

    Tarihte varlık yeterlidir (yalnızca olay türleri farklıysa "farkli"). Ölçüde aday olmak için tür
    aynı ve bilinen, ayırıcı kümeleri aynı, koşul ölçüleri uyumlu ve bağlam benzer olmalıdır;
    emin olunamıyorsa "belirsiz".
    """
    if a.boyut == "tarih":
        if a.tur and b.tur and a.tur != b.tur:
            return "farkli", f"olay türleri farklı ({a.tur} / {b.tur})"
        return "aday", ""
    if a.tur and b.tur and a.tur != b.tur:
        return "farkli", f"nicelik türleri farklı ({a.tur} / {b.tur})"
    if a.ayirici and b.ayirici and a.ayirici != b.ayirici:
        return "farkli", f"ayırıcılar farklı ({', '.join(sorted(a.ayirici))} / {', '.join(sorted(b.ayirici))})"
    if not (a.tur and b.tur):
        return "belirsiz", "nicelik türü belli değil"
    if a.ayirici != b.ayirici:
        tek = sorted(a.ayirici | b.ayirici)
        return "belirsiz", f"ayırıcı yalnızca birinde ({', '.join(tek)})"
    if not kosullar_uyumlu_mu(a, b):
        return "belirsiz", "cümlelerdeki koşul ölçüleri farklı ya da yalnızca birinde var"
    if baglam_benzerligi(a, b) < EN_AZ_BAGLAM_BENZERLIGI:
        return "belirsiz", "bağlam sözcükleri benzemiyor"
    return "aday", ""


# ------------------------------------------------------------------ analizör


class TutarlilikAnalizoru:
    """Kitaptaki tarih ve ölçü olgularını çıkarır; aynı varlığın farklı sayfalardaki değerlerini karşılaştırır."""

    def __init__(self, referans_yili: int = REFERANS_YILI) -> None:
        self.referans_yili = referans_yili

    def analiz_et(self, paragraflar: Iterable[Paragraf]) -> list[Bulgu]:
        return self.incele(paragraflar).bulgular

    @staticmethod
    def alistirma_paragraflari(paragraflar: Sequence[Paragraf]) -> set[tuple[int, int]]:
        """Yönergesi ("doğru ise D, yanlış ise Y", "boşlukları doldurunuz"...) olan alıştırma bloklarının
        (yönerge dahil) ve soru türündeki paragrafların (sayfa, paragraf) kimlikleri.

        Güçlü yönerge ("doğru ise D, yanlış ise Y", "boşlukları doldurunuz") bloğu sonraki ilk gerçek başlığa,
        ilk uzun gövde paragrafına (BLOK_BITIREN_KELIME'den uzun; düz anlatım ya da okuma metni) ya da sayfa
        sonuna kadar sürer ("D Y" gibi sütun etiketleri başlık sayılmaz). Zayıf yönerge ("cevaplayınız",
        "işaretleyiniz": etkinlik yönergesi de olabilir) yalnızca kendisini ve hemen altındaki soru/liste/
        "(……)" maddelerini kapsar. Maddeler bilerek yanlış olabileceğinden kitap bilgisi değildir."""
        dis: set[tuple[int, int]] = set()
        blok_sayfasi = None
        zayif_sayfasi = None
        for p in paragraflar:
            kelime = len(p.metin.split())
            uzun = kelime > BLOK_BITIREN_KELIME
            if blok_sayfasi is not None and (p.sayfa != blok_sayfasi or (
                    p.tur == "baslik" and re.search(r"\w{2,}", p.metin)) or (p.tur == "govde" and uzun)):
                blok_sayfasi = None
            madde = p.tur in ("soru", "liste") or bool(_MADDE_BASI.match(p.metin))
            if zayif_sayfasi is not None and (p.sayfa != zayif_sayfasi or not madde):
                zayif_sayfasi = None
            kisa = kelime <= YONERGE_EN_COK_KELIME and p.tur != "baslik"
            if kisa and _YONERGE.search(p.metin):
                blok_sayfasi = p.sayfa
                zayif_sayfasi = None
            elif kisa and _YONERGE_ZAYIF.search(p.metin):
                zayif_sayfasi = p.sayfa
                dis.add((p.sayfa, p.paragraf))
            if blok_sayfasi is not None or zayif_sayfasi is not None or p.tur == "soru":
                dis.add((p.sayfa, p.paragraf))
        return dis

    @staticmethod
    def _varlik_devral(cumle: str, bas: int, onceki: Sequence[str], kucukler: frozenset[str],
                       orta_buyukler: frozenset[str], kisa: bool, tarih: bool) -> tuple[list[str], str]:
        """Cümlede özel isim yoksa varlığı başka yerden bul: (adlar, kaynak).

        1. Zamirli/gösterme sözcüklü cümle ("Bu dolanma hareketi ... 365 gün 6 saatte"): aynı paragraftaki
           önceki cümleden (en çok ANAFORA_GERI_CUMLE) ilk özel isim alınır; kaynak "onceki".
        2. Çoğul özneli cümle ("Yılanlar 10 ila 15 yıl yaşar"): cümle başındaki çoğul isim varlıktır; "cogul".
        Bulunamazsa ([], "cumle")."""
        if _ANAFORA.match(cumle):
            for geri in onceki:
                adlar = yakin_varliklar(geri, 0, 0, kucukler, orta_buyukler, kisa, tarih, en_fazla=1)
                if adlar:
                    return adlar, "onceki"
            return [], "cumle"
        m = _COGUL_OZNE.match(cumle)
        if m and m.end() <= bas and _kucuk(m.group(1)) not in _COGUL_DISI:
            return [m.group(1)], "cogul"
        return [], "cumle"

    def olgulari_cikar(self, paragraflar: Iterable[Paragraf]) -> list[Olgu]:
        paragraflar = list(paragraflar)
        dis = self.alistirma_paragraflari(paragraflar)
        paragraflar = [p for p in paragraflar if (p.sayfa, p.paragraf) not in dis]
        cumleler = []  # (paragraf, cümle, aynı paragraftaki önceki cümleler: en yakın başta, en çok ANAFORA_GERI_CUMLE)
        for p in paragraflar:
            liste = cumlelere_ayir(p.metin)
            for i, c in enumerate(liste):
                cumleler.append((p, c, tuple(reversed(liste[max(0, i - ANAFORA_GERI_CUMLE):i]))))
        kucukler = frozenset(_kucuk(k) for p in paragraflar for k in _KUCUK_KELIME.findall(p.metin))
        orta_buyukler = frozenset(
            _kucuk(_KESME.split(m.group(0))[0])
            for _, c, _ in cumleler for m in _BUYUK_HARFLI.finditer(c)
            if re.search(r"\w", c[:m.start()])
        )

        olgular: list[Olgu] = []
        for p, cumle, onceki in cumleler:
            kisa = len(p.metin.split()) <= 6
            r = rakamlastir(cumle)
            tarihler = [(*r.eski(bas, son), *geri) for bas, son, *geri in _tarihleri_bul(r.yeni, self.referans_yili)]
            adaylar = [(bas, son, alt, ust, yak, tol, "tarih", "tarih") for bas, son, alt, ust, yak, tol in tarihler]
            # Etiket paragrafları (harita/şema yazıları: "Burdur G. ( 854 m. )") ve etkinlik künyeleri
            # ("Amaç ... Süre 80 dk") cümle değildir; yalnızca tarihleri alınır
            kunye = len(_KUNYE_ETIKETI.findall(cumle)) >= KUNYE_EN_AZ_ETIKET
            olculer = [] if (p.tur == "etiket" or kunye) else olculeri_bul(r.yeni)
            for o in olculer:
                bas, son = r.eski(o.bas, o.son)
                if any(bas < t[1] and t[0] < son for t in tarihler):
                    continue  # "9 500 yıl önce" bir süre değil, tarihtir
                if _SURE_ETIKETI.search(cumle[:bas]):
                    continue  # "Süre 80 dk" etkinlik künyesidir
                adaylar.append((bas, son, o.alt, o.ust, o.yaklasik, o.tolerans, o.boyut, o.birim))

            for bas, son, alt, ust, yaklasik, tolerans, boyut, birim in adaylar:
                adlar = yakin_varliklar(cumle, bas, son, kucukler, orta_buyukler, kisa, tarih=boyut == "tarih",
                                        en_fazla=1 if boyut == "tarih" else OLCU_VARLIK_SAYISI)
                kaynak = "cumle"
                if not adlar:
                    adlar, kaynak = self._varlik_devral(cumle, bas, onceki, kucukler, orta_buyukler, kisa, boyut == "tarih")
                varlik = adlar[0] if adlar else None
                kosullar = tuple((d[6], d[2], d[3], d[5]) for d in adaylar
                                 if d[6] not in (boyut, "tarih") and boyut != "tarih")
                digerleri = tuple((d[0], d[1]) for d in adaylar if (d[0], d[1]) != (bas, son))
                tur = (olay_turu(cumle, bas, son, digerleri) if boyut == "tarih"
                       else nicelik_turu(boyut, cumle, bas, son, digerleri))
                olgular.append(Olgu(
                    sayfa=p.sayfa, paragraf=p.paragraf, konum=p.konum, ifade=cumle[bas:son].strip(),
                    alt=alt, ust=ust, yaklasik=yaklasik, tolerans=tolerans, cumle=cumle,
                    varlik=varlik, anahtar=_kucuk(varlik) if varlik else None, boyut=boyut, tur=tur,
                    ayirici=ayirici_bul(cumle, bas, son, digerleri), baglam=baglam_bul(cumle, bas, son, varlik, digerleri),
                    anahtarlar=tuple(dict.fromkeys(k for ad in adlar for k in varlik_anahtarlari(ad))), kosullar=kosullar,
                    varlik_kaynagi=kaynak,
                ))
        return olgular

    def incele(self, paragraflar: Iterable[Paragraf]) -> TutarlilikSonucu:
        olgular = self.olgulari_cikar(paragraflar)
        gruplar: dict[tuple[str, str], list[Olgu]] = defaultdict(list)
        for o in olgular:
            for anahtar in o.anahtarlar:
                gruplar[(anahtar, o.boyut)].append(o)

        bulgular: list[Bulgu] = []
        belirsizler: list[Belirsiz] = []
        gorulen: set[tuple[int, int]] = set()
        farkli = 0
        for (anahtar, boyut), liste in gruplar.items():
            b, bel, f = self._grup_incele(liste, gorulen)
            bulgular += b
            belirsizler += bel
            farkli += f
        belirsizler += self._varliksiz_belirsizler(olgular)
        bulgular.sort(key=lambda b: (b.sayfa, b.paragraf))
        belirsizler.sort(key=lambda x: (x.a.sayfa, x.b.sayfa, x.varlik))

        varlikli = [o for o in olgular if o.anahtar]
        ozet = {
            "referans_yili": self.referans_yili,
            "olgu_sayisi": len(olgular),
            "tarih_olgusu": sum(1 for o in olgular if o.boyut == "tarih"),
            "sayisal_olgu": sum(1 for o in olgular if o.boyut != "tarih"),
            "varlikli_olgu": len(varlikli),
            "varlik_devralinan": sum(1 for o in varlikli if o.varlik_kaynagi != "cumle"),
            "varliksiz_olgu": len(olgular) - len(varlikli),
            "varlik_sayisi": len({o.anahtar for o in varlikli}),
            "birden_cok_sayfadaki_varlik": sum(
                1 for k in {o.anahtar for o in varlikli}
                if len({o.sayfa for o in varlikli if o.anahtar == k}) > 1),
            "aday_celiski": len(bulgular),
            "aday_tarih": sum(1 for b in bulgular if b.tur == TUR_TARIH),
            "aday_sayisal": sum(1 for b in bulgular if b.tur == TUR_SAYISAL),
            "belirsiz": len(belirsizler),
            "belirsiz_zayif": sum(1 for x in belirsizler if x.guc == "zayif"),
            "farkli_nicelik": farkli,
        }
        return TutarlilikSonucu(bulgular=bulgular, olgular=olgular, belirsizler=belirsizler, ozet=ozet)

    def _varliksiz_belirsizler(self, olgular: list[Olgu]) -> list[Belirsiz]:
        """Varlığı bulunamayan olgular, aynı türde ve bağlamı çok benzeyen başka bir olguyla çelişiyorsa belirsizdir.

        Aday olamazlar (aynı varlıktan söz edildiği bilinmiyor) ama aynı niceliğin iki farklı değeri
        olabilir; sonraki adımda LLM karar verir. İki olgunun da varlığı varsa ve farklıysa çift alınmaz.
        """
        gruplar: dict[tuple[str, str], list[Olgu]] = defaultdict(list)
        for o in olgular:
            if o.boyut != "tarih" and o.tur:
                gruplar[(o.boyut, o.tur)].append(o)
        sonuc: list[Belirsiz] = []
        for liste in gruplar.values():
            for i, a in enumerate(liste):
                for b in liste[i + 1:]:
                    if a.sayfa == b.sayfa or (a.anahtar and b.anahtar) or not celisiyor_mu(a, b):
                        continue
                    if a.ayirici and b.ayirici and a.ayirici != b.ayirici:
                        continue
                    if not kosullar_uyumlu_mu(a, b):
                        continue
                    ortak = a.baglam & b.baglam
                    benzerlik = baglam_benzerligi(a, b)
                    if benzerlik >= VARLIKSIZ_EN_AZ_BAGLAM_BENZERLIGI and len(ortak) >= VARLIKSIZ_EN_AZ_ORTAK_KOK:
                        guc = "guclu"
                    elif benzerlik >= ZAYIF_EN_AZ_BAGLAM_BENZERLIGI and len(ortak) >= ZAYIF_EN_AZ_ORTAK_KOK:
                        guc = "zayif"
                    else:
                        continue
                    sonuc.append(Belirsiz(varlik=a.varlik or b.varlik or "", boyut=a.boyut, a=a, b=b, guc=guc,
                                          neden="varlık belli değil; bağlam benzer (" + ", ".join(sorted(ortak)) + ")"))
        return sonuc

    # ------------------------------------------------------------------ karşılaştırma

    def _grup_incele(self, liste: list[Olgu], gorulen: set[tuple[int, int]]) -> tuple[list[Bulgu], list[Belirsiz], int]:
        """Aynı varlık ve boyuttaki olguları değerce kümelere ayırır; çelişen kümelerin çiftlerini sınıflar."""
        liste = sorted(liste, key=lambda o: (o.sayfa, o.paragraf, o.alt))
        kumeler: list[list[Olgu]] = []
        for o in liste:
            for kume in kumeler:
                if not celisiyor_mu(kume[0], o):
                    kume.append(o)
                    break
            else:
                kumeler.append([o])

        bulgular: list[Bulgu] = []
        belirsizler: list[Belirsiz] = []
        farkli = 0
        for i, k1 in enumerate(kumeler):
            for k2 in kumeler[i + 1:]:
                en_iyi = None  # ("aday" önce, sonra "belirsiz")
                for a in k1:
                    for b in k2:
                        if a.sayfa == b.sayfa or not celisiyor_mu(a, b):
                            continue
                        sinif, neden = eslestir(a, b)
                        oncelik = {"aday": 0, "belirsiz": 1, "farkli": 2}[sinif]
                        if en_iyi is None or oncelik < en_iyi[0]:
                            en_iyi = (oncelik, sinif, neden, a, b)
                if en_iyi is None:
                    continue
                _, sinif, neden, a, b = en_iyi
                cift = (id(a), id(b))
                if cift in gorulen or (cift[1], cift[0]) in gorulen:
                    continue
                gorulen.add(cift)
                if sinif == "farkli":
                    farkli += 1
                elif sinif == "belirsiz":
                    belirsizler.append(Belirsiz(varlik=a.varlik or "", boyut=a.boyut, a=a, b=b, neden=neden))
                else:
                    # Bulgu, küçük kümedeki (eşitse sonraki sayfadaki) olguya yazılır; diğer tarafı "ilgili" gösterir
                    if (len(k1), -a.sayfa) < (len(k2), -b.sayfa):
                        asil, ilgili, ilgili_kume = a, b, k2
                    else:
                        asil, ilgili, ilgili_kume = b, a, k1
                    bulgular.append(self._bulgu(asil, ilgili, ilgili_kume))
        return bulgular, belirsizler, farkli

    def _bulgu(self, asil: Olgu, ilgili: Olgu, ilgili_kume: list[Olgu]) -> Bulgu:
        fark = _fark(asil, ilgili)
        destek = sorted({o.sayfa for o in ilgili_kume if o is not ilgili})
        tarih = asil.boyut == "tarih"
        if tarih:
            fark_metni = f"Fark yaklaşık {self._yil(fark)} yıl (referans yıl {self.referans_yili})."
        else:
            fark_metni = (f"Fark yaklaşık {okunur(fark, asil.boyut)}; aynı nicelik gibi görünüyor "
                          f"(tür: {asil.tur}" + (f", ayırıcı: {', '.join(sorted(asil.ayirici))}" if asil.ayirici else "")
                          + ").")
        aciklama = (
            f"«{asil.varlik}» için kitabın iki yerinde farklı {'tarih' if tarih else 'değer'} var: "
            f"s.{asil.sayfa}'de «{asil.ifade}»{self._normal(asil)}, s.{ilgili.sayfa}'de «{ilgili.ifade}»"
            f"{self._normal(ilgili)}. {fark_metni}"
        )
        if destek:
            aciklama += " Diğer değer s." + ", s.".join(str(s) for s in destek) + "'de de geçiyor."
        if asil.yaklasik or ilgili.yaklasik:
            aciklama += (" Değerlerden biri yaklaşık olduğu için fark yuvarlamayla açıklanabilir; yine de aynı olay "
                         "için iki farklı sayı okuyucuyu yanıltabilir." if tarih else
                         " Değerlerden biri yaklaşık olduğu için fark yuvarlamayla açıklanabilir.")
        aciklama += (" Olayların aynı olup olmadığı (kuruluş / yaşam dönemi gibi) basılı sayfada kontrol edilmeli."
                     if tarih else " Aynı koşulda aynı şeyin ölçüldüğü basılı sayfada kontrol edilmeli.")
        guven = guven_hesapla(asil, ilgili)
        if not tarih:
            guven *= 0.85 + 0.15 * min(1.0, baglam_benzerligi(asil, ilgili) / 0.3)
        # zamirden/çoğul özneden bulunan varlık daha az kesin
        guven *= min(VARLIK_KAYNAGI_CARPANI[asil.varlik_kaynagi], VARLIK_KAYNAGI_CARPANI[ilgili.varlik_kaynagi])
        return Bulgu(
            sayfa=asil.sayfa, paragraf=asil.paragraf, kriter=KRITER,
            sorunlu_metin=asil.cumle if len(asil.cumle) <= 240 else asil.cumle[:237] + "…",
            aciklama=aciklama, guven=guven,
            oneri=f"Her iki yeri kontrol edip «{asil.varlik}» için tek bir "
                  f"{'tarih' if tarih else 'değer'} kullanın ya da farkın nedenini açıklayın.",
            konum=asil.konum, tur=TUR_TARIH if tarih else TUR_SAYISAL,
            ilgili_sayfa=ilgili.sayfa, ilgili_paragraf=ilgili.paragraf, ilgili_konum=ilgili.konum,
        )

    @staticmethod
    def _yil(sayi: float) -> str:
        return sayi_yaz(sayi)

    def _normal(self, o: Olgu) -> str:
        """İfadenin yanına normalleştirilmiş değeri ekler (zaten aynı biçimde yazılmışsa eklemez)."""
        if o.boyut == "tarih":
            if "yıl önce" in o.ifade:
                return ""
            if o.alt == o.ust:
                return f" (≈{self._yil(o.alt)} yıl önce)"
            return f" (≈{self._yil(o.alt)}-{self._yil(o.ust)} yıl önce)"
        if o.alt == o.ust:
            return f" (≈{okunur(o.alt, o.boyut)})"
        return f" (≈{okunur(o.alt, o.boyut)}-{okunur(o.ust, o.boyut)})"
