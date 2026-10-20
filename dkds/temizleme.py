"""PDF'ten çıkarılan ham metni analize hazır hale getirir."""
from __future__ import annotations

import re

KUCUK_HARFLER = "a-zçğıöşüâîû"

# Bazı PDF'lerde "fi", "fl" gibi harf çiftleri tek karakter (ligatür) olarak gelir.
LIGATURLER = {
    "ﬀ": "ff",
    "ﬁ": "fi",
    "ﬂ": "fl",
    "ﬃ": "ffi",
    "ﬄ": "ffl",
}

_TIRELEME = re.compile(rf"(\w)-[ \t]*\n[ \t]*([{KUCUK_HARFLER}])")
_GERCEK_TIRE = re.compile(r"(\w)-[ \t]*\n[ \t]*(?=[A-ZÇĞİÖŞÜÂÎÛ0-9])")
_SATIR_SONU = re.compile(r"[ \t]*\n[ \t]*")
_COKLU_BOSLUK = re.compile(r"[ \t]{2,}")
_DOLGU = re.compile(r"[.…_]{5,}")


def temizle(metin: str) -> str:
    """Satır sonlarını, tirelemeyi ve gereksiz boşlukları düzeltir.

    Satır sonundaki tire yalnızca alt satır KÜÇÜK harfle başlıyorsa kaldırılır:
        "kitap-\\nlar"   -> "kitaplar"
        "Kuzey-\\nGüney" -> "Kuzey-Güney"   (gerçek tire korunur)
    """
    for lig, karsilik in LIGATURLER.items():
        metin = metin.replace(lig, karsilik)
    metin = metin.replace("­", "")  # yumuşak tire (görünmez heceleme işareti)
    metin = metin.replace(" ", " ")  # bölünmez boşluk
    metin = _TIRELEME.sub(r"\1\2", metin)
    metin = _GERCEK_TIRE.sub(r"\1-", metin)
    metin = _SATIR_SONU.sub(" ", metin)
    metin = _DOLGU.sub(" ", metin)  # "........" cevap boşlukları
    metin = _COKLU_BOSLUK.sub(" ", metin)
    return metin.strip()


def dolgu_mu(metin: str) -> bool:
    """Blok yalnızca cevap boşluğundan (nokta/alt çizgi dizileri) mı oluşuyor?

    Ders kitaplarındaki "......" satırları öğrencinin yazacağı yerlerdir; içerik
    değildir ve analizörlere gönderilmemelidir. Ancak PDF'te soru ile altındaki
    cevap satırları çoğu zaman aynı blokta gelir. Bu yüzden oran hesabı yerine
    dolgu dizileri silinir ve geriye harf ya da rakam kalıp kalmadığına bakılır;
    böylece uzun cevap satırları sorunun kendisini sildirmez.
    """
    kalan = _DOLGU.sub("", metin)
    return not any(k.isalnum() for k in kalan)


def harf_iceriyor_mu(metin: str) -> bool:
    """Metinde en az bir harf var mı?

    Kenardaki soru numaraları ("1", "2. 3."), şekil üzerindeki sayılar gibi
    harfsiz bloklar yazım, okunabilirlik veya tutarlılık analizi için anlam taşımaz.
    """
    return any(k.isalpha() for k in metin)


_BEKLENEN = re.compile(
    r"[A-Za-z0-9ÇĞİÖŞÜçğıöşüÂÎÛâîû\s.,;:!?'\"()\[\]{}\-–—…/%+=*&#@<>«»“”‘’°⁰¹²³½¼•●▪–]"
)


def kodlama_bozuk_mu(metin: str, esik: float = 0.90) -> bool:
    """Metnin bozuk yazı tipi kodlamasıyla çıkarılıp çıkarılmadığını tahmin eder.

    Bazı PDF'lerde ekranda "ışık" görünür ama çıkarılan metin "õúk" gibi
    anlamsız karakterlerden oluşur. Beklenen karakterlerin oranı eşiğin
    altındaysa metin bozuk kabul edilir.
    """
    if "�" in metin:  # Unicode "tanınmayan karakter" işareti
        return True
    harfler = [k for k in metin if not k.isspace()]
    if len(harfler) < 20:
        return False
    beklenen = sum(1 for k in harfler if _BEKLENEN.match(k))
    return beklenen / len(harfler) < esik
