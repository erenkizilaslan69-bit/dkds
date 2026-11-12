"""Ders kitaplarının başındaki ulusal metinler: İstiklal Marşı, Gençliğe Hitabe, Öğrenci Andı.

Bu sayfalardaki metin kitabın yazarlarına ait değildir ve arkaik sözcükler içerir ("serhaddim", "vecd", "hürriyyet");
yazım ve okunabilirlik analizinden çıkarılır. Tutarlılık analizi etkilenmez.

Sayfa şu durumlarda ulusal metin sayfasıdır:
  1. Başlık ya da etiket türündeki bir paragrafı "İSTİKLÂL MARŞI", "GENÇLİĞE HİTABE", "ÖĞRENCİ ANDI" ya da "ANDIMIZ"dır
     (fen3 s.5 "ANDIMIZ"; kitaplarda büyük İ yer yer "I" olarak kodlanmıştır, karşılaştırma bunu gözetmez), ya da
  2. sayfadaki ilk paragraf İstiklal Marşı'nın ilk dizesiyle ("Korkma, sönmez bu şafaklarda…") başlar. Marşın başlığı
     görsel olduğundan metin katmanında yoktur; dizeyle başlayan sayfa marş sayfasıdır. Başka bir metnin içinde alıntılanan
     dize (sosyalbilgiler5 s.82: "…" tırnağıyla ve ilk paragraf olmayan) sayfayı dışarıda bırakmaz.
"""
from __future__ import annotations

import re
from collections.abc import Iterable

from ..models import Paragraf

BASLIKLAR = ("istiklal marsi", "genclige hitabe", "ogrenci andi", "andimiz")
ILK_DIZE = "korkma, sönmez bu şafaklarda"

_BASLIK_TURLERI = ("baslik", "etiket")
_HARF_DISI = re.compile(r"[^\w\s,]", re.UNICODE)


def _bicimsiz(metin: str) -> str:
    """Büyük/küçük harf, i/ı/İ/I ayrımı ve şapka farkı gözetilmeden karşılaştırma biçimi (yalnızca başlıklar için)."""
    metin = metin.replace("İ", "i").replace("I", "i").replace("ı", "i").lower()
    metin = metin.translate(str.maketrans("âîû", "aiu"))
    metin = metin.translate(str.maketrans("çğöşü", "cgosu"))
    return " ".join(_HARF_DISI.sub(" ", metin).split())


def _dize_basi(metin: str) -> str:
    """Metnin başındaki tırnak/işaretler atılmış, küçük harfli biçimi (ilk dize karşılaştırması için)."""
    metin = metin.lstrip(" \t\"'“”‘’«»(")
    return metin.replace("İ", "i").replace("I", "ı").lower()


def ulusal_metin_sayfalari(paragraflar: Iterable[Paragraf]) -> set[int]:
    """Ulusal metin (İstiklal Marşı, Gençliğe Hitabe, Öğrenci Andı) içeren sayfaların numaraları."""
    sayfalar: set[int] = set()
    ilk: dict[int, Paragraf] = {}
    for p in paragraflar:
        if p.sayfa not in ilk or p.paragraf < ilk[p.sayfa].paragraf:
            ilk[p.sayfa] = p
        if p.tur in _BASLIK_TURLERI and _bicimsiz(p.metin) in BASLIKLAR:
            sayfalar.add(p.sayfa)
    for sayfa, p in ilk.items():
        if _dize_basi(p.metin).startswith(ILK_DIZE):
            sayfalar.add(sayfa)
    return sayfalar


def ulusal_metinleri_ayikla(paragraflar: Iterable[Paragraf]) -> list[Paragraf]:
    """Ulusal metin sayfalarındaki paragrafları çıkarılmış liste."""
    paragraflar = list(paragraflar)
    sayfalar = ulusal_metin_sayfalari(paragraflar)
    return [p for p in paragraflar if p.sayfa not in sayfalar] if sayfalar else paragraflar
