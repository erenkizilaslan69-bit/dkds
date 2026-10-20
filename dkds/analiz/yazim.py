"""Yazım ve dil hatası analizörü (kriter 1).

Yalnızca gövde, soru ve liste paragraflarını inceler; başlık ve etiketler
(harita adları, tablo hücreleri) yanlış alarm üreteceği için atlanır.

Kesin kurallar (güven yüksek):
    noktalama_oncesi_bosluk   "kelime ,"        -> "kelime,"
    noktalama_sonrasi_bosluk  "ve,sonra"        -> "ve, sonra"
    tekrar                    "ve ve"           -> "ve"
    kucuk_harfle_cumle        ". bu cümle"      -> ". Bu cümle"
    sik_yanlis                "herkez"          -> "herkes"

Morfolojik denetim (güven orta):
    bilinmeyen_kelime         zeyrek'in çözümleyemediği kelime aday hatadır.
                              Özel isimler (büyük harfle başlayan), kısaltmalar,
                              TAMAMEN BÜYÜK HARFLİ kelimeler, sayılar ve birimler
                              denetlenmez.

Olası metin çıkarma sorunu (güven düşük, yazım hatası sayılmaz):
    karakter_kaybi            Kelime s->ş, g->ğ, i->ı, c->ç, o->ö, u->ü değişiklikleriyle
                              geçerli hale geliyorsa ("Günes" -> "Güneş") sorun büyük
                              olasılıkla yazımda değil PDF'in metin katmanındadır:
                              fen5.pdf s.56'da basılı sayfada "Güneş" yazar ama
                              dekoratif yazı tipi ş'yi s olarak kodlar.
"""
from __future__ import annotations

import re
from collections import Counter
from collections.abc import Iterable, Iterator
from itertools import combinations

from ..models import Bulgu, Paragraf
from .morfoloji import Morfoloji

KRITER = "yazim"
INCELENEN_TURLER = {"govde", "soru", "liste"}

KESIN_GUVEN = 0.9
BILINMEYEN_GUVEN = 0.5
KARAKTER_KAYBI_GUVEN = 0.3
KARAKTER_KAYBI_BAGLAM_GUVEN = 0.2

# Metin katmanında Türkçe harfin yerine geçebilen ASCII harf -> Türkçe harf
TURKCE_KARSILIK = {"s": "ş", "g": "ğ", "i": "ı", "c": "ç", "o": "ö", "u": "ü"}
EN_FAZLA_DEGISIKLIK = 3  # "Düsünsene" için 2 değişiklik yeterli; 3 hızı korur

# Sözlükte olmayan ama metinlerde geçen ölçü birimleri ve kısaltmalar
BIRIMLER = {"km", "cm", "mm", "kg", "mg", "ml", "sn", "dk", "kcal", "cal", "lt", "gr", "ms", "mö"}

# Türk Dil Kurumunun "sık yapılan yanlışlar" listesinden seçilmiş örnekler.
# Anahtarlar küçük harfle yazılır; iki kelimelik yanlışlar da olabilir.
SIK_YANLISLAR = {
    "herkez": "herkes",
    "yanlız": "yalnız",
    "yalnış": "yanlış",
    "birşey": "bir şey",
    "herşey": "her şey",
    "hiçbirşey": "hiçbir şey",
    "birsürü": "bir sürü",
    "hergün": "her gün",
    "herzaman": "her zaman",
    "birgün": "bir gün",
    "pekçok": "pek çok",
    "yada": "ya da",
    "orjinal": "orijinal",
    "laboratuar": "laboratuvar",
    "eşortman": "eşofman",
    "süpriz": "sürpriz",
    "mütevazi": "mütevazı",
    "traş": "tıraş",
    "deyil": "değil",
    "egzos": "egzoz",
    "entellektüel": "entelektüel",
    "bir çok": "birçok",
    "bir kaç": "birkaç",
    "hiç bir": "hiçbir",
    "her hangi": "herhangi",
}

# Art arda yazılması hiçbir zaman doğru olmayan kelimeler. "yavaş yavaş",
# "kat kat", "tek tek" gibi ikilemeler doğru olduğu için tekrar kuralı yalnızca
# bağlaç, edat ve zamirlere uygulanır.
TEKRARLANAMAZ = {
    "ve", "ile", "veya", "ya", "ama", "fakat", "ancak", "çünkü", "ki", "de", "da",
    "için", "gibi", "kadar", "göre", "bu", "şu", "o", "bir", "her", "en", "daha",
    "ben", "sen", "biz", "siz", "onlar", "olan", "olarak",
}

# Ardından küçük harf gelebilen kısaltmalar: "vb. araçlar", "örn. hücre"
KISALTMALAR = {"vb", "vs", "örn", "bkz", "yy", "vd", "s", "sf", "no", "nu", "çev", "haz", "yay", "der"}

_URL = re.compile(r"(?:https?://|www\.)\S+|\b[\w.-]+\.(?:gov|com|org|edu|net|tr)\b\S*", re.IGNORECASE)
_NOKTALAMA_ONCESI = re.compile(r"(\w+)(\s+)([,;:!?]|\.(?!\.))")
_NOKTALAMA_SONRASI = re.compile(r"([^\W\d_]+)([,;:!?])([^\W\d_]+)")
_NOKTA_SONRASI = re.compile(r"([a-zçğıöşü]{2,})\.([A-ZÇĞİÖŞÜ][a-zçğıöşü])")
_TEKRAR = re.compile(r"\b(\w+)\s+(\1)\b", re.IGNORECASE)
_KUCUK_HARFLE_CUMLE = re.compile(r"(\S*)([.!?])\s+([a-zçğıöşüâîû]\w*)")
# Kelime: harflerden oluşur, kesme işareti ve kısa çizgiyle bağlanmış parçaları olabilir
# ("Dünya’nın", "e-içerik"). Rakama veya kesme işaretine bitişik başlayan parçalar
# ("10’uncu" içindeki "uncu") kelime sayılmaz.
_KELIME = re.compile(r"(?<![\w'’´-])[^\W\d_]+(?:[-'’´][^\W\d_]+)*(?![\w'’´])")
_KESME = re.compile(r"['’´]")  # ´: sosyalbilgiler5.pdf'te "New York´taki"


def _sik_yanlis_deseni() -> re.Pattern:
    secenekler = sorted(SIK_YANLISLAR, key=len, reverse=True)  # önce uzun ifadeler
    return re.compile(r"\b(" + "|".join(re.escape(s).replace(r"\ ", r"\s+") for s in secenekler) + r")\b",
                      re.IGNORECASE)


_SIK_YANLIS = _sik_yanlis_deseni()


def _kucuk(metin: str) -> str:
    """Türkçeye uygun küçük harfe çevirme ("I" -> "ı", "İ" -> "i")."""
    return metin.replace("I", "ı").replace("İ", "i").lower()


def _denetlenecek_parcalar(kelime: str) -> list[str]:
    """Bir kelimenin morfolojik olarak denetlenecek parçaları (küçük harfle).

    Boş liste dönerse kelime denetlenmez:
      - Büyük harf içeren kelimeler: özel isim ("Hattuşa"), kısaltma ("MÖ", "pH")
        veya TAMAMEN BÜYÜK HARFLİ yazı. Büyük harfli yazıda sosyalbilgiler5.pdf'te
        İ harfi metin katmanında I olarak geliyor ("ÖĞRENELIM"); denetlemek yanlış
        alarm üretir.
      - Kesme işaretinden sonraki ek ("km’dir" -> "km") ayrıca denetlenmez.
      - İki harfli parçalar ve birimler ("km", "kcal").
    Kısa çizgiyle bağlı kelimelerin ("e-içerik") her parçası ayrı denetlenir.
    """
    if any(k.isupper() for k in kelime):
        return []
    govde = _KESME.split(kelime)[0]
    return [p for p in govde.split("-") if len(p) > 2 and p not in BIRIMLER]


def turkce_karakterli_bicimler(kelime: str) -> Iterator[str]:
    """Kelimedeki s, g, i, c, o, u harflerinin Türkçe karşılıklarıyla değiştirildiği biçimler.

    Önce tek harfi değişmiş biçimler, sonra iki, en fazla EN_FAZLA_DEGISIKLIK:
        "günes" -> "güneş", ...
    """
    yerler = [i for i, k in enumerate(kelime) if k in TURKCE_KARSILIK]
    for adet in range(1, min(len(yerler), EN_FAZLA_DEGISIKLIK) + 1):
        for secilen in combinations(yerler, adet):
            harfler = list(kelime)
            for i in secilen:
                harfler[i] = TURKCE_KARSILIK[harfler[i]]
            yield "".join(harfler)


def _kelimeler(metin: str) -> list[str]:
    """Metindeki kelimeler, küçük harfle ve kesme işaretinden sonraki ek atılarak ("Güneş’in" -> "güneş")."""
    return [_kucuk(_KESME.split(m.group())[0]) for m in _KELIME.finditer(metin)]


class YazimAnalizoru:
    def __init__(self, morfoloji: Morfoloji | None = None, sozluk_denetimi: bool = True) -> None:
        """sozluk_denetimi=False ise yalnızca kesin kurallar uygulanır (zeyrek yüklenmez)."""
        if sozluk_denetimi and morfoloji is None:
            morfoloji = Morfoloji()
        self.morfoloji = morfoloji if sozluk_denetimi else None
        self._turkce_bicim: dict[str, str | None] = {}  # kelime -> geçerli Türkçe karakterli biçimi
        self._kitap_kelimeleri: Counter[str] = Counter()

    def analiz_et(self, paragraflar: Iterable[Paragraf]) -> list[Bulgu]:
        paragraflar = list(paragraflar)
        # Kitaptaki kelime sıklıkları: "yasamın" gibi geçerli görünen ama karakter
        # kaybına uğramış kelimeleri ayırt etmek için kullanılır.
        self._kitap_kelimeleri = Counter(k for p in paragraflar for k in _kelimeler(p.metin))
        bulgular: list[Bulgu] = []
        for p in paragraflar:
            if p.tur in INCELENEN_TURLER:
                bulgular.extend(self.paragraf_incele(p))
        return bulgular

    def turkce_bicim(self, kelime: str) -> str | None:
        """Kelimenin geçerli olan ilk Türkçe karakterli biçimi (yoksa None). Önbelleğe alınır."""
        if kelime not in self._turkce_bicim:
            self._turkce_bicim[kelime] = next(
                (b for b in turkce_karakterli_bicimler(kelime) if self.morfoloji.gecerli_mi(b)), None
            )
        return self._turkce_bicim[kelime]

    def paragraf_incele(self, p: Paragraf) -> list[Bulgu]:
        metin = _URL.sub(lambda m: " " * len(m.group()), p.metin)  # adresler denetlenmez

        def bulgu(tur, sorunlu, aciklama, oneri, guven=KESIN_GUVEN):
            return Bulgu(sayfa=p.sayfa, paragraf=p.paragraf, kriter=KRITER, sorunlu_metin=sorunlu,
                         aciklama=aciklama, guven=guven, oneri=oneri, konum=p.konum, tur=tur)

        sonuc = []
        for m in _NOKTALAMA_ONCESI.finditer(metin):
            sonuc.append(bulgu("noktalama_oncesi_bosluk", m.group(),
                               f"'{m.group(3)}' işaretinden önce boşluk bırakılmaz.",
                               m.group(1) + m.group(3)))
        for m in _NOKTALAMA_SONRASI.finditer(metin):
            sonuc.append(bulgu("noktalama_sonrasi_bosluk", m.group(),
                               f"'{m.group(2)}' işaretinden sonra boşluk bırakılmalı.",
                               f"{m.group(1)}{m.group(2)} {m.group(3)}"))
        for m in _NOKTA_SONRASI.finditer(metin):
            sonuc.append(bulgu("noktalama_sonrasi_bosluk", m.group(),
                               "Cümle sonundaki noktadan sonra boşluk bırakılmalı.",
                               f"{m.group(1)}. {m.group(2)}"))
        for m in _TEKRAR.finditer(metin):
            if _kucuk(m.group(1)) == _kucuk(m.group(2)) and _kucuk(m.group(1)) in TEKRARLANAMAZ:
                sonuc.append(bulgu("tekrar", m.group(), f"'{m.group(1)}' kelimesi art arda iki kez yazılmış.",
                                   m.group(1)))
        for m in _KUCUK_HARFLE_CUMLE.finditer(metin):
            onceki, kelime = m.group(1), m.group(3)
            if onceki.endswith((".", "…")) or onceki[-1:].isdigit() or _kucuk(onceki) in KISALTMALAR:
                continue  # "...", "36. sayfa", "vb. araçlar"
            if len(onceki) <= 1:
                continue  # "a. şık", "s. 35"
            sonuc.append(bulgu("kucuk_harfle_cumle", f"{m.group(2)} {kelime}",
                               "Cümle büyük harfle başlamalı.", kelime[0].upper() + kelime[1:]))
        for m in _SIK_YANLIS.finditer(metin):
            yanlis = m.group()
            dogru = SIK_YANLISLAR[" ".join(_kucuk(yanlis).split())]
            if yanlis[0].isupper():
                dogru = dogru[0].upper() + dogru[1:]
            sonuc.append(bulgu("sik_yanlis", yanlis, f"Sık yapılan bir yazım yanlışı; doğrusu '{dogru}'.",
                               dogru, guven=0.95))
        if self.morfoloji is not None:
            sonuc.extend(self._morfolojik_denetim(metin, sonuc, bulgu))
        return sonuc

    def _morfolojik_denetim(self, metin: str, kesin_bulgular: list[Bulgu], bulgu) -> list[Bulgu]:
        sonuc: list[Bulgu] = []
        sik_yanlislar = {_kucuk(b.sorunlu_metin) for b in kesin_bulgular if b.tur == "sik_yanlis"}
        gecerli_kelimeler: list[str] = []  # paragrafta karakter kaybı varsa üçüncü adımda bakılır

        def karakter_kaybi(kelime, dogru, guven, neden=None):
            neden = neden or f"'{_kucuk(kelime)}' çözümlenemedi ama '{_kucuk(dogru)}' geçerli bir kelime."
            return bulgu("karakter_kaybi", kelime,
                         f"{neden} Yazım hatası değil, olası metin çıkarma sorunu: basılı sayfada doğru "
                         "yazılmış olabilir; bazı yazı tipleri ş, ğ gibi harfleri metin katmanına s, g "
                         "olarak aktarır.",
                         dogru, guven=guven)

        for m in _KELIME.finditer(metin):
            kelime = m.group()
            kucuk = _kucuk(kelime)
            if kucuk in sik_yanlislar:
                continue  # zaten sık yanlış olarak raporlandı

            # 1) Büyük harfle başlayan kelime: özel isim olabilir, bilinmeyen kelime denetlenmez.
            #    Ama sıradan kelime olarak çözümlenemiyor, Türkçe karakterli biçimi geçerli ve
            #    kitapta kendisinden daha sık geçiyorsa ("Günes" 2 kez, "güneş" 115 kez)
            #    karakter kaybıdır. Sıklık şartı özel isimleri korur: "Sivas" -> "sıvaş" de
            #    zeyrek'e göre geçerli ama kitapta hiç geçmez.
            #    Cümle başındaki büyük harf özel isim olduğunu göstermez: cümle başındaki
            #    kelime özel isim olarak da tanınmıyorsa ("Düsünsene") sıklık şartı aranmaz.
            if kelime[0].isupper() and kelime[1:].islower():
                govde = _kucuk(_KESME.split(kelime)[0])
                if len(govde) > 2 and not self.morfoloji.gecerli_mi(govde):
                    dogru = self.turkce_bicim(govde)
                    onceki = metin[: m.start()].rstrip()
                    cumle_basi = not onceki or onceki.endswith((".", "!", "?", ":"))
                    kanit = (self._kitap_kelimeleri[dogru] > self._kitap_kelimeleri[govde]
                             or (cumle_basi and not self.morfoloji.gecerli_mi(govde, ozel_isim=True)))
                    if dogru and kanit:
                        sonuc.append(karakter_kaybi(kelime, dogru[0].upper() + dogru[1:], KARAKTER_KAYBI_GUVEN))
                continue

            # 2) Küçük harfli kelime: çözümlenemeyen parça önce karakter kaybı açısından denenir
            for parca in _denetlenecek_parcalar(kelime):
                if self.morfoloji.gecerli_mi(parca):
                    continue
                dogru = self.turkce_bicim(parca)
                if dogru:
                    sonuc.append(karakter_kaybi(kelime, dogru, KARAKTER_KAYBI_GUVEN))
                else:
                    sonuc.append(bulgu(
                        "bilinmeyen_kelime", kelime,
                        f"'{parca}' Türkçe kök ve eklere ayrılamadı; yazım hatası olabilir.",
                        None, guven=BILINMEYEN_GUVEN))
                break
            else:
                if _denetlenecek_parcalar(kelime) == [kucuk]:
                    gecerli_kelimeler.append(kelime)

        # 3) Paragrafta karakter kaybı bulunduysa aynı yazı tipiyle yazılmış başka kelimeler de
        #    etkilenmiş olabilir. "yasamın" geçerli bir kelimedir (yasa + m + ın) ama kitapta
        #    "yaşamın" daha sık geçiyorsa büyük olasılıkla o da karakter kaybına uğramıştır.
        if any(b.tur == "karakter_kaybi" for b in sonuc):
            for kelime in gecerli_kelimeler:
                kucuk = _kucuk(kelime)
                for bicim in turkce_karakterli_bicimler(kucuk):
                    if (self._kitap_kelimeleri[bicim] > self._kitap_kelimeleri[kucuk]
                            and self.morfoloji.gecerli_mi(bicim)):
                        sonuc.append(karakter_kaybi(
                            kelime, bicim, KARAKTER_KAYBI_BAGLAM_GUVEN,
                            neden=f"'{kucuk}' geçerli bir kelime ama kitapta '{bicim}' daha sık geçiyor "
                                  "ve aynı paragrafta başka karakter kaybı bulundu."))
                        break
        return sonuc
