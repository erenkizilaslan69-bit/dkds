"""PDF'ten sayfa ve paragraf bilgisini koruyarak metin çıkarma (PyMuPDF katmanı).

PyMuPDF'e bağlı tek modül budur. Düzen ve temizleme mantığı duzen.py ve
temizleme.py içindedir.
"""
from __future__ import annotations

from pathlib import Path

try:
    import pymupdf as fitz
except ImportError:  # eski sürümler yalnızca "fitz" adıyla gelir
    import fitz

from .duzen import bolunmus_paragraflari_birlestir, ust_alt_bilgi_temizle
from .models import Blok, CikarimSonucu, Paragraf
from .temizleme import dolgu_mu, harf_iceriyor_mu, kodlama_bozuk_mu, temizle

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
    bloklar = [
        Blok(sayfa=sayfa_no, x0=x0, y0=y0, x1=x1, y1=y1, metin=metin)
        for x0, y0, x1, y1, metin, _no, tip in ham
        if tip == 0 and metin.strip()  # tip 0 = metin, 1 = görsel
    ]
    return bloklar, ocr_kullanildi


def pdf_oku(yol: str | Path, ocr: bool = True, dil: str = "tur") -> CikarimSonucu:
    """PDF'i okuyup sayfa/paragraf bilgisiyle temizlenmiş paragrafları döndürür."""
    yol = Path(yol)
    uyarilar: list[str] = []
    sayfalar: dict[int, list[Blok]] = {}
    yukseklikler: dict[int, float] = {}
    ocr_sayfalari: set[int] = set()

    with fitz.open(yol) as doc:
        sayfa_sayisi = doc.page_count
        for i, sayfa in enumerate(doc, start=1):
            bloklar, ocr_oldu = _sayfa_bloklari(sayfa, i, ocr, dil, uyarilar)
            sayfalar[i] = bloklar
            yukseklikler[i] = sayfa.rect.height
            if ocr_oldu:
                ocr_sayfalari.add(i)

    sayfalar = ust_alt_bilgi_temizle(sayfalar, yukseklikler)

    paragraflar: list[Paragraf] = []
    for sayfa_no in sorted(sayfalar):
        bloklar = bolunmus_paragraflari_birlestir(sayfalar[sayfa_no])
        sayfa_metni = []
        no = 0
        for b in bloklar:
            if dolgu_mu(b.metin):
                continue
            metin = temizle(b.metin)
            if not harf_iceriyor_mu(metin):  # boş, yalnızca sayı veya simge
                continue
            no += 1
            sayfa_metni.append(metin)
            paragraflar.append(
                Paragraf(
                    sayfa=sayfa_no,
                    paragraf=no,
                    metin=metin,
                    konum=b.konum,
                    ocr=sayfa_no in ocr_sayfalari,
                )
            )
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
