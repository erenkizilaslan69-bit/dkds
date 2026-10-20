"""Sayfa düzeni işlemleri: üst/alt bilgi temizliği ve bölünmüş paragrafların birleştirilmesi.

Bu modül hiçbir PDF kütüphanesine bağlı değildir; yalnızca Blok listeleriyle çalışır.
Böylece PDF kütüphanesi değişse bile bu mantık aynen kullanılabilir ve kolayca test edilir.
"""
from __future__ import annotations

import re
from collections import defaultdict

from .models import Blok

CUMLE_SONU = (".", "!", "?", ":", ";", "…", '"', "”", "»", ")")
_RAKAMLAR = re.compile(r"\d+")


def _anahtar(b: Blok) -> tuple[str, int]:
    """Tekrar eden üst/alt bilgileri yakalamak için bloğun "imzası".

    Üst/alt bilgiler her sayfada aynı metinle ve yaklaşık aynı yükseklikte bulunur.
    Çok kısa bloklarda (sayfa numarası, "12 | FEN BİLİMLERİ" gibi) rakamlar yok
    sayılır; uzun bloklarda metin birebir aynı olmalıdır. Böylece yalnızca bir
    sayısı farklı olan gövde paragrafları yanlışlıkla silinmez.
    """
    metin = " ".join(b.metin.lower().split())
    if len(metin) <= 40:
        metin = _RAKAMLAR.sub("#", metin)
    return metin, round(b.y0 / 20)


def ust_alt_bilgi_temizle(
    sayfalar: dict[int, list[Blok]],
    sayfa_yukseklikleri: dict[int, float],
    kenar_orani: float = 0.07,
    tekrar_orani: float = 0.3,
    kisa_metin: int = 100,
) -> dict[int, list[Blok]]:
    """Sayfa numarası, kitap adı, ünite başlığı gibi tekrar eden blokları çıkarır.

    İki kural uygulanır (yalnızca kısa bloklara):
      1. Sayfanın en üst veya en alt %7'lik şeridinde kalan bloklar.
      2. Sayfaların en az %30'unda aynı metinle ve aynı yükseklikte tekrar eden bloklar.
    """
    tekrar_sayaci: dict[tuple[str, int], set[int]] = defaultdict(set)
    for sayfa, bloklar in sayfalar.items():
        for b in bloklar:
            if len(b.metin.strip()) <= kisa_metin:
                tekrar_sayaci[_anahtar(b)].add(sayfa)

    toplam = len(sayfalar)
    esik = max(3, int(toplam * tekrar_orani))
    tekrarlayanlar = {m for m, s in tekrar_sayaci.items() if len(s) >= esik}

    sonuc: dict[int, list[Blok]] = {}
    for sayfa, bloklar in sayfalar.items():
        h = sayfa_yukseklikleri[sayfa]
        kalan = []
        for b in bloklar:
            kisa = len(b.metin.strip()) <= kisa_metin
            kenarda = b.y1 <= h * kenar_orani or b.y0 >= h * (1 - kenar_orani)
            if kisa and (kenarda or _anahtar(b) in tekrarlayanlar):
                continue
            kalan.append(b)
        sonuc[sayfa] = kalan
    return sonuc


def _yatay_ortusme(a: Blok, b: Blok) -> float:
    """İki bloğun yatayda ne kadar örtüştüğü (dar olanın genişliğine oranla)."""
    ortak = min(a.x1, b.x1) - max(a.x0, b.x0)
    dar = min(a.x1 - a.x0, b.x1 - b.x0)
    return ortak / dar if dar > 0 else 0.0


def birlestirilmeli_mi(a: Blok, b: Blok) -> bool:
    """b bloğu, a bloğunun devamı olan aynı paragraf mı?

    Hepsi sağlanmalı:
      - Aynı sütunda olmaları (yatayda en az %50 örtüşme)
      - Aralarındaki dikey boşluğun bir satır yüksekliğinden az olması. Sıkı satır
        aralıklı kitaplarda satır kutuları biraz üst üste biner (sosyalbilgiler5.pdf
        s.127'de -1.8 pt); yarım satıra kadar üst üste binmeye izin verilir.
      - a'nın cümle sonu işaretiyle bitmemesi
      - a'nın tamamen büyük harfli (başlık) olmaması: "ANAHTAR KAVRAMLAR" altındaki
        "kuvvet, kütle..." listesine eklenmemeli
      - b'nin küçük harfle başlaması
    """
    if _yatay_ortusme(a, b) < 0.5:
        return False
    bosluk = b.y0 - a.y1
    satir = max(a.satir_yuksekligi, b.satir_yuksekligi)
    if bosluk < -satir / 2 or bosluk > satir:
        return False
    a_metin, b_metin = a.metin.rstrip(), b.metin.lstrip()
    if not a_metin or not b_metin or a_metin.endswith(CUMLE_SONU):
        return False
    if _tamamen_buyuk_harf(a_metin):
        return False
    return b_metin[0].islower()


def _tamamen_buyuk_harf(metin: str) -> bool:
    harfler = [k for k in metin if k.isalpha()]
    return len(harfler) >= 2 and all(k.isupper() for k in harfler)


def bolunmus_paragraflari_birlestir(bloklar: list[Blok]) -> list[Blok]:
    """Bir paragrafın devamı olan blokları önceki parçasıyla tek blokta birleştirir.

    Her blok için yalnızca hemen önceki bloğa değil, okuma sırasında kendinden
    önce gelen bloklara da (sondan başa doğru) bakılır. Zaman çizelgesi gibi çok
    sütunlu düzenlerde başka sütundan bir blok araya girebilir: sosyalbilgiler5.pdf
    s.64'te "1948 ... petrol çıkarılmaya" ile devamı "başlandı." arasına yan
    sütundaki bir kutu giriyor. Aynı sütun ve dikey yakınlık koşulları yanlış
    bloğa eklenmeyi önler.
    """
    sonuc: list[Blok] = []
    for b in bloklar:
        for i in range(len(sonuc) - 1, -1, -1):
            a = sonuc[i]
            if birlestirilmeli_mi(a, b):
                sonuc[i] = Blok(
                    sayfa=a.sayfa,
                    x0=min(a.x0, b.x0),
                    y0=a.y0,
                    x1=max(a.x1, b.x1),
                    y1=b.y1,
                    metin=a.metin.rstrip("\n") + "\n" + b.metin,
                )
                break
        else:
            sonuc.append(b)
    return sonuc
