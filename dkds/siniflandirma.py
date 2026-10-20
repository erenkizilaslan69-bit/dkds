"""Paragraf türü sınıflandırması (kural tabanlı).

Analizörler her paragrafa aynı şekilde davranmamalı: örneğin okunabilirlik
formülleri yalnızca gövde metninde anlamlıdır, harita etiketleri yazım
denetiminde yanlış alarm üretir. Bu modül her paragrafa bir tür atar:

    baslik  "BİLGİ İSTASYONU", "ANAHTAR KAVRAMLAR"
    soru    "?" ile biten metin
    liste   madde işareti (•, -) veya "1." ile başlayan metin
    etiket  şekil/harita yazıları: "Kura N.", "İ R A N", "Görsel 1.2: ...", "100 N"
    govde   geri kalan her şey

İki aşama vardır:
  1. paragraf_turu: tek bir paragrafa metnine bakarak tür verir. Kurallar
     yukarıdan aşağıya denenir; ilk tutan kural türü belirler.
  2. sayfa_turleri: sayfanın bütününe bakar. Harita gibi etiketlerle dolu bir
     sayfadaki "AZERBAYCAN" metne bakınca başlığa benzer ama aslında etikettir.
"""
from __future__ import annotations

import re

BASLIK = "baslik"
GOVDE = "govde"
SORU = "soru"
LISTE = "liste"
ETIKET = "etiket"

CUMLE_SONU = (".", "!", "?", ":", ";", "…")

BASLIK_EN_FAZLA_KELIME = 8
ETIKET_EN_FAZLA_KELIME = 3  # "4 kelimeden kısa"
SORU_EN_FAZLA_KELIME = 60  # daha uzunsa "?" ile biten bir anlatı paragrafıdır
TEK_HARF_ORANI = 0.6  # "İ R A N", "S A H A ( Y A K U T ) C ."

# Harita/şekil sayfası: en az bu kadar paragraf ve bu oranda etiket
HARITA_EN_AZ_PARAGRAF = 30
HARITA_ETIKET_ORANI = 0.6

# "• Madde", "- Madde", "– Madde", "1. Madde", "12. Madde"
_MADDE = re.compile(r"^(?:[•\-–▪●]\s|\d{1,2}\.\s)")
# "Görsel 3.1.14: Büyüteç", "Tablo 2. Ölçümler"
_ALTYAZI = re.compile(r"^(?:Görsel|Tablo|Şekil|Grafik)\s+\d")
# "Kura N.", "NAHÇIVAN Ö.C.": tek harfli kısaltmayla biten metin
_KISALTMA_SONU = re.compile(r"(?:^|[\s.])\w\.$")


def _tamamen_buyuk_harf(metin: str) -> bool:
    harfler = [k for k in metin if k.isalpha()]
    return len(harfler) >= 2 and all(k.isupper() for k in harfler)


def _harf_aralikli(kelimeler: list[str]) -> bool:
    if len(kelimeler) < 3:
        return False
    tek = sum(1 for k in kelimeler if len(k) == 1)
    return tek / len(kelimeler) > TEK_HARF_ORANI


def _rakam_agirlikli(metin: str) -> bool:
    rakam = sum(k.isdigit() for k in metin)
    harf = sum(k.isalpha() for k in metin)
    return rakam > harf


def paragraf_turu(metin: str) -> str:
    """Temizlenmiş paragraf metninin türünü yalnızca metne bakarak döndürür."""
    metin = metin.strip()
    kelimeler = metin.split()
    kisa = len(kelimeler) <= ETIKET_EN_FAZLA_KELIME

    # Önce etiketin kesin işaretleri: bunlar başlığa da benzeyebilir
    # ("İ R A N", "100 N 50 N", "DAĞISTAN C.")
    if (
        _harf_aralikli(kelimeler)
        or _rakam_agirlikli(metin)
        or _ALTYAZI.match(metin)
        or (kisa and _KISALTMA_SONU.search(metin))
    ):
        return ETIKET
    if len(kelimeler) <= BASLIK_EN_FAZLA_KELIME and _tamamen_buyuk_harf(metin):
        return BASLIK
    if metin.endswith("?") and len(kelimeler) <= SORU_EN_FAZLA_KELIME:
        return SORU
    if _MADDE.match(metin):
        return LISTE
    if kisa and not metin.endswith(CUMLE_SONU):
        return ETIKET
    return GOVDE


def sayfa_turleri(metinler: list[str]) -> list[str]:
    """Bir sayfadaki paragrafların türlerini sayfa bağlamını da kullanarak döndürür.

    Sayfada çok sayıda paragraf varsa ve bunların çoğu etiketse sayfa bir harita
    veya büyük bir şekildir. Böyle bir sayfada kısa başlık ve gövde olarak
    görünen metinler ("AZERBAYCAN", "TÜRK BÖLGELERİ") de etiket kabul edilir.
    İki istisna vardır: sayfanın en üstündeki paragraf (çoğunlukla sayfanın
    gerçek başlığıdır, ör. "PEKİŞTİRME İSTASYONU-2") ve cümle sonu işaretiyle
    biten metinler (yönergeler, ör. "Aşağıda bazı ifadeler verilmiştir.").
    """
    turler = [paragraf_turu(m) for m in metinler]
    etiket = turler.count(ETIKET)
    harita = len(turler) >= HARITA_EN_AZ_PARAGRAF and etiket / len(turler) >= HARITA_ETIKET_ORANI
    if not harita:
        return turler
    sonuc = turler[:1]
    for t, m in zip(turler[1:], metinler[1:]):
        m = m.strip()
        donustur = (
            t in (BASLIK, GOVDE)
            and len(m.split()) <= BASLIK_EN_FAZLA_KELIME
            and not m.endswith(CUMLE_SONU)
        )
        sonuc.append(ETIKET if donustur else t)
    return sonuc
