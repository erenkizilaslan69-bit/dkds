"""Paragraf türü sınıflandırması (kural tabanlı).

Analizörler her paragrafa aynı şekilde davranmamalı: örneğin okunabilirlik
formülleri yalnızca gövde metninde anlamlıdır, harita etiketleri yazım
denetiminde yanlış alarm üretir. Bu modül her paragrafa bir tür atar:

    baslik  "BİLGİ İSTASYONU", "ANAHTAR KAVRAMLAR"
    soru    "?" ile biten metin
    liste   madde işareti (•, -) veya "1." ile başlayan metin
    etiket  şekil/harita/tablo yazıları: "Kura N.", "İ R A N", "Görsel 1.2: ...",
            "100 N", "Mezopotamya Medeniyetleri Tarih Şeridi"
    govde   geri kalan her şey

İki aşama vardır:
  1. paragraf_turu: tek bir paragrafa metnine bakarak tür verir. Kurallar
     yukarıdan aşağıya denenir; ilk tutan kural türü belirler.
  2. sayfa_turleri: sayfanın bütününe bakar. Harita gibi etiketlerle dolu bir
     sayfadaki "AZERBAYCAN" metne bakınca başlığa benzer ama aslında etikettir.

Kurallar fen5.pdf ve sosyalbilgiler5.pdf üzerinde denenmiştir. Bilinen sınırlama:
font bilgisi kullanılmadığı için "Etkinliğin Yapılışı" gibi ilk harfi büyük alt
başlıklar, "Akciğer Hücresi" gibi şekil etiketlerinden ayırt edilemez (ikisi de etiket).
"""
from __future__ import annotations

import re

BASLIK = "baslik"
GOVDE = "govde"
SORU = "soru"
LISTE = "liste"
ETIKET = "etiket"

CUMLE_SONU = (".", "!", "?", ":", ";", "…")
BAGLACLAR = {"ve", "ile", "veya", "ya", "da", "de"}  # başlıklarda küçük harfle yazılır

BASLIK_EN_FAZLA_KELIME = 8
ETIKET_EN_FAZLA_KELIME = 3  # "4 kelimeden kısa"
SORU_EN_FAZLA_KELIME = 60  # daha uzunsa "?" ile biten bir anlatı paragrafıdır
TEK_HARF_ORANI = 0.6  # "İ R A N", "S A H A ( Y A K U T ) C ."

# Harita/şekil sayfası: en az bu kadar paragraf ve bu oranda kısa paragraf
# (etiket ya da en fazla ETIKET_EN_FAZLA_KELIME kelime)
HARITA_EN_AZ_PARAGRAF = 30
HARITA_KISA_ORANI = 0.6

# "• Madde", "- Madde", "– Madde", "1. Madde", "12. Madde"
_MADDE = re.compile(r"^(?:[•\-–▪●]\s|\d{1,2}\.\s)")
# "Görsel 3.1.14: Büyüteç", "Tablo 2. Ölçümler"
_ALTYAZI = re.compile(r"^(?:Görsel|Tablo|Şekil|Grafik|Harita)\s+\d")
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


def _baslik_bicimli(kelimeler: list[str]) -> bool:
    """Harfle başlayan bütün kelimeler büyük harfle mi başlıyor? (bağlaçlar hariç)

    "Mezopotamya Medeniyetleri Tarih Şeridi", "Yazılı Kaynaklar Görsel Kaynaklar"
    """
    harfli = [k for k in kelimeler if k[0].isalpha() and k not in BAGLACLAR]
    return len(harfli) >= 2 and all(k[0].isupper() for k in harfli)


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
    if not metin.endswith(CUMLE_SONU):
        # Şekil/tablo adları: "Mezopotamya Medeniyetleri Tarih Şeridi"
        if kisa or (len(kelimeler) <= BASLIK_EN_FAZLA_KELIME and _baslik_bicimli(kelimeler)):
            return ETIKET
    return GOVDE


def _komsuluk_duzelt(turler: list[str], metinler: list[str]) -> list[str]:
    """İki tek kelimelik etiketin arasında kalan başlık, bir haritanın içindedir.

    Küçük haritalı sayfalarda (sosyalbilgiler5.pdf s.136) "HAZAR DENİZİ" gibi
    büyük harfli yer adları "Sardes", "Efes" gibi şehir adlarının arasında gelir.
    Komşuların tek kelime olması şartı gerçek başlıkları korur: fen5.pdf'te
    "ETKİNLİK İSTASYONU" da iki etiketin arasındadır ama bunlar "Görünen Boyut",
    "Etkinliğin Yapılışı" gibi iki kelimelik alt başlıklardır.
    """

    def tek_kelimelik_etiket(j: int) -> bool:
        return turler[j] == ETIKET and len(metinler[j].split()) == 1

    sonuc = list(turler)
    for i in range(1, len(turler) - 1):
        if turler[i] == BASLIK and tek_kelimelik_etiket(i - 1) and tek_kelimelik_etiket(i + 1):
            sonuc[i] = ETIKET
    return sonuc


def sayfa_turleri(metinler: list[str]) -> list[str]:
    """Bir sayfadaki paragrafların türlerini sayfa bağlamını da kullanarak döndürür.

    Sayfada çok sayıda paragraf varsa ve bunların çoğu kısaysa (etiket ya da en
    fazla üç kelime) sayfa bir harita veya büyük bir şekildir. Etiket yerine kısa
    metin sayılır, çünkü haritadaki büyük harfli yer adları ("KASTAMONU", "AĞRI
    DAĞI") tek başına başlık olarak sınıflanır ve etiket oranını düşürür. Böyle bir sayfada kısa başlık ve gövde olarak
    görünen metinler ("AZERBAYCAN", "TÜRK BÖLGELERİ") de etiket kabul edilir.
    İki istisna vardır:
      - Sayfada ilk etiketten önce gelen paragraflar: şekil başlamadan önceki
        kısım sayfa başlığı ve yönergedir ("PEKİŞTİRME İSTASYONU-2",
        "DEĞERLENDİRELİM").
      - Cümle sonu işaretiyle biten metinler (yönergeler, ör. "Aşağıda bazı
        ifadeler verilmiştir.").
    """
    turler = _komsuluk_duzelt([paragraf_turu(m) for m in metinler], metinler)
    kisa = sum(
        1 for t, m in zip(turler, metinler) if t == ETIKET or len(m.split()) <= ETIKET_EN_FAZLA_KELIME
    )
    harita = len(turler) >= HARITA_EN_AZ_PARAGRAF and kisa / len(turler) >= HARITA_KISA_ORANI
    if not harita:
        return turler
    ilk_etiket = turler.index(ETIKET) if ETIKET in turler else 1
    sonuc = turler[:ilk_etiket]
    for t, m in zip(turler[ilk_etiket:], metinler[ilk_etiket:]):
        m = m.strip()
        donustur = (
            t in (BASLIK, GOVDE)
            and len(m.split()) <= BASLIK_EN_FAZLA_KELIME
            and not m.endswith(CUMLE_SONU)
        )
        sonuc.append(ETIKET if donustur else t)
    return sonuc
