"""Sayfa düzeni işlemleri: üst/alt bilgi temizliği ve bölünmüş paragrafların birleştirilmesi.

Bu modül hiçbir PDF kütüphanesine bağlı değildir; yalnızca Blok listeleriyle çalışır.
Böylece PDF kütüphanesi değişse bile bu mantık aynen kullanılabilir ve kolayca test edilir.
"""
from __future__ import annotations

import re
from collections import defaultdict
from dataclasses import replace
from difflib import SequenceMatcher

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


# ------------------------------------------------------------------ tekrarlı metin katmanı

# Bazı sayfalarda aynı metin PDF'e iki kez konmuş (gizli ya da kaydırılmış kopya katman):
# döndürülmüş "Bu temada" kutuları (turkce5.pdf s.68, 122), şema kutuları (sosyalbilgiler5.pdf
# s.142). Çıkarım sırasında ikisi iç içe geçer ve cümleler iki kez okunur.
SATIR_BENZERLIGI = 0.85  # art arda iki satırın benzerlik oranı bu değeri geçerse ikincisi kopyadır
BLOK_BENZERLIGI = 0.8
KUTU_ORTUSMESI = 0.7  # küçük kutunun bu kadarı büyük kutunun içinde kalıyorsa aynı yerdedirler
EN_AZ_IMZA = 4  # bundan kısa satırlar ("a)", "1.") kopya sayılmaz; tablo hücreleri gibi gerçek tekrarlar olabilir


def _imza(metin: str) -> str:
    """Karşılaştırma için yalnızca harf ve rakamlar (tire, boşluk ve noktalama yok sayılır)."""
    return "".join(k for k in metin.casefold() if k.isalnum())


def _benzer_mi(a: str, b: str, esik: float) -> bool:
    if a == b:
        return True
    return SequenceMatcher(None, a, b).ratio() >= esik


def _tekrar_satirlari_cikar(blok: Blok) -> tuple[Blok, int]:
    """Bloktaki, kendinden hemen önceki satırın kopyası olan satırları siler."""
    kalan: list[str] = []
    son_imza = ""
    silinen = 0
    for satir in blok.metin.split("\n"):
        imza = _imza(satir)
        if len(imza) >= EN_AZ_IMZA and len(son_imza) >= EN_AZ_IMZA and _benzer_mi(son_imza, imza, SATIR_BENZERLIGI):
            silinen += 1
            continue
        kalan.append(satir)
        if imza:
            son_imza = imza
    if not silinen:
        return blok, 0
    return replace(blok, metin="\n".join(kalan)), silinen


def _kutu_ortusmesi(a: Blok, b: Blok) -> float:
    """Kesişim alanının küçük kutunun alanına oranı."""
    en = max(0.0, min(a.x1, b.x1) - max(a.x0, b.x0))
    boy = max(0.0, min(a.y1, b.y1) - max(a.y0, b.y0))
    kucuk = min((a.x1 - a.x0) * (a.y1 - a.y0), (b.x1 - b.x0) * (b.y1 - b.y0))
    return en * boy / kucuk if kucuk > 0 else 0.0


def tekrarli_metni_temizle(bloklar: list[Blok]) -> tuple[list[Blok], int]:
    """Aynı sayfada iki kez bulunan metni (kopya katman) çıkarır; (bloklar, silinen parça) döndürür.

    İki aşama:
      1. Blok içinde art arda gelen benzer satırlar: kopya katman satır satır iç içe geçer.
      2. Başka bir bloğun neredeyse aynı yerinde duran, metni benzer ikinci blok silinir
         (ilk gelen kalır). Aynı konumda olmayan tekrarlar (tablo hücrelerindeki "Evet")
         silinmez.
    """
    silinen = 0
    satirlari_temiz: list[Blok] = []
    for b in bloklar:
        yeni, n = _tekrar_satirlari_cikar(b)
        satirlari_temiz.append(yeni)
        silinen += n

    sonuc: list[Blok] = []
    imzalar: list[str] = []
    for b in satirlari_temiz:
        imza = _imza(b.metin)
        kopya = False
        if imza:
            for diger, diger_imza in zip(sonuc, imzalar):
                if _kutu_ortusmesi(b, diger) >= KUTU_ORTUSMESI and _benzer_mi(imza, diger_imza, BLOK_BENZERLIGI):
                    kopya = True
                    break
        if kopya:
            silinen += 1
            continue
        sonuc.append(b)
        imzalar.append(imza)
    return sonuc, silinen
