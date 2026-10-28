"""PDF'ten sayfa ve paragraf bilgisini koruyarak metin çıkarma (PyMuPDF katmanı).

PyMuPDF'e bağlı tek modül budur. Düzen ve temizleme mantığı duzen.py ve
temizleme.py içindedir.
"""
from __future__ import annotations

from dataclasses import replace
from pathlib import Path

try:
    import pymupdf as fitz
except ImportError:  # eski sürümler yalnızca "fitz" adıyla gelir
    import fitz

from .duzen import bolunmus_paragraflari_birlestir, tekrarli_metni_temizle, ust_alt_bilgi_temizle
from .models import Blok, CikarimSonucu, Paragraf
from .siniflandirma import sayfa_turleri
from .temizleme import dolgu_mu, harf_iceriyor_mu, kodlama_bozuk_mu, kodlamayi_onar, temizle

# Bir sayfada bundan az karakter varsa ve görsel içeriyorsa "taranmış" kabul edilir.
TARANMIS_ESIK = 30

# Not: PyMuPDF'in TEXT_DEHYPHENATE bayrağını bilerek kullanmıyoruz. Bu bayrak
# "Kuzey-\nGüney" gibi gerçek tireleri de siler. Tirelemeyi temizleme.py'deki
# Türkçeye uygun kuralla (yalnızca alt satır küçük harfle başlıyorsa) çözüyoruz.
METIN_BAYRAKLARI = fitz.TEXT_PRESERVE_WHITESPACE | fitz.TEXT_MEDIABOX_CLIP


def _sayfa_bloklari(sayfa, sayfa_no: int, ocr: bool, dil: str, uyarilar: list[str]):
    """Bir sayfanın metin bloklarını döndürür; gerekirse OCR uygular."""
    textpage = None
    ocr_kullanildi = False

    if len(sayfa.get_text().strip()) < TARANMIS_ESIK and sayfa.get_images():
        if not ocr:
            uyarilar.append(f"Sayfa {sayfa_no}: taranmış görünüyor, OCR kapalı olduğu için atlandı.")
            return [], False
        try:
            textpage = sayfa.get_textpage_ocr(language=dil, dpi=300, full=True)
            ocr_kullanildi = True
        except Exception as hata:  # Tesseract kurulu değilse veya dil paketi yoksa
            uyarilar.append(f"Sayfa {sayfa_no}: taranmış görünüyor ancak OCR yapılamadı ({hata}).")
            return [], False

    ham = sayfa.get_text("blocks", flags=METIN_BAYRAKLARI, sort=True, textpage=textpage)
    bloklar = _bloklara_cevir(ham, sayfa_no)
    if textpage is None:  # OCR çıktısı zaten Unicode, onarım gerekmez
        bloklar = _kodlamayi_onar(sayfa, sayfa_no, bloklar, uyarilar)
    return bloklar, ocr_kullanildi


def _bloklara_cevir(ham, sayfa_no: int) -> list[Blok]:
    return [
        Blok(sayfa=sayfa_no, x0=x0, y0=y0, x1=x1, y1=y1, metin=metin)
        for x0, y0, x1, y1, metin, _no, tip in ham
        if tip == 0 and metin.strip()  # tip 0 = metin, 1 = görsel
    ]


def _kodlamayi_onar(sayfa, sayfa_no: int, bloklar: list[Blok], uyarilar: list[str]) -> list[Blok]:
    """Sayfada "�" varsa eski Türkçe yazı tipi eşlemesiyle onarmayı dener.

    "�", PDF'teki yazı tipi kodunun Unicode karşılığı olmadığı anlamına gelir ve
    bilgi kaybıdır. TEXT_CID_FOR_UNKNOWN_UNICODE bayrağı bu karakterler yerine kod
    numarasına göre karakter verir; temizleme.kodlamayi_onar eşlemeyi uygular. Onarım
    kabul edilmezse sayfa olduğu gibi (bozuk) kalır ve aşağıda uyarı verilir.
    """
    if not any("�" in b.metin for b in bloklar):
        return bloklar
    ham = sayfa.get_text("blocks", flags=METIN_BAYRAKLARI | fitz.TEXT_CID_FOR_UNKNOWN_UNICODE, sort=True)
    kodlu = _bloklara_cevir(ham, sayfa_no)
    onarilmis = kodlamayi_onar([b.metin for b in kodlu])
    if onarilmis is None:
        return bloklar
    uyarilar.append(
        f"Sayfa {sayfa_no}: bozuk yazı tipi kodlaması eski Türkçe yazı tipi eşlemesiyle onarıldı; "
        "metin basılı sayfayla karşılaştırılmalı."
    )
    return [replace(b, metin=m) for b, m in zip(kodlu, onarilmis)]


def pdf_oku(yol: str | Path, ocr: bool = True, dil: str = "tur") -> CikarimSonucu:
    """PDF'i okuyup sayfa/paragraf bilgisiyle temizlenmiş paragrafları döndürür."""
    yol = Path(yol)
    uyarilar: list[str] = []
    sayfalar: dict[int, list[Blok]] = {}
    yukseklikler: dict[int, float] = {}
    ocr_sayfalari: set[int] = set()
    tekrarli_sayfalar: list[int] = []

    with fitz.open(yol) as doc:
        sayfa_sayisi = doc.page_count
        for i, sayfa in enumerate(doc, start=1):
            bloklar, ocr_oldu = _sayfa_bloklari(sayfa, i, ocr, dil, uyarilar)
            bloklar, silinen = tekrarli_metni_temizle(bloklar)
            if silinen:
                tekrarli_sayfalar.append(i)
            sayfalar[i] = bloklar
            yukseklikler[i] = sayfa.rect.height
            if ocr_oldu:
                ocr_sayfalari.add(i)

    if tekrarli_sayfalar:
        gosterilen = ", ".join(str(s) for s in tekrarli_sayfalar[:20]) + (" ..." if len(tekrarli_sayfalar) > 20 else "")
        uyarilar.append(f"{len(tekrarli_sayfalar)} sayfada metin iki kez (kopya katman) bulunuyordu; tekrar eden "
                        f"parçalar çıkarıldı (sayfa {gosterilen}).")

    sayfalar = ust_alt_bilgi_temizle(sayfalar, yukseklikler)

    paragraflar: list[Paragraf] = []
    for sayfa_no in sorted(sayfalar):
        bloklar = bolunmus_paragraflari_birlestir(sayfalar[sayfa_no])
        sayfa_paragraflari: list[Paragraf] = []
        for b in bloklar:
            if dolgu_mu(b.metin):
                continue
            metin = temizle(b.metin)
            if not harf_iceriyor_mu(metin):  # boş, yalnızca sayı veya simge
                continue
            sayfa_paragraflari.append(
                Paragraf(
                    sayfa=sayfa_no,
                    paragraf=len(sayfa_paragraflari) + 1,
                    metin=metin,
                    konum=b.konum,
                    ocr=sayfa_no in ocr_sayfalari,
                )
            )
        sayfa_metni = [p.metin for p in sayfa_paragraflari]
        # Tür sayfa bağlamıyla belirlenir (ör. harita sayfasındaki büyük harfli adlar)
        for p, tur in zip(sayfa_paragraflari, sayfa_turleri(sayfa_metni)):
            p.tur = tur
        paragraflar.extend(sayfa_paragraflari)
        if kodlama_bozuk_mu(" ".join(sayfa_metni)):
            uyarilar.append(
                f"Sayfa {sayfa_no}: metin bozuk yazı tipi kodlamasıyla çıkarılmış olabilir "
                "(anlamsız karakterler). Bu sayfa için OCR denenmeli."
            )

    return CikarimSonucu(
        kaynak=yol.name,
        sayfa_sayisi=sayfa_sayisi,
        paragraflar=paragraflar,
        uyarilar=uyarilar,
    )
