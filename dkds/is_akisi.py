"""Tam analiz iş akışı: PDF -> çıkarım -> yazım + okunabilirlik + tutarlılık -> kayıt (JSON'a yazılabilir sözlük).

Komut satırı (`python -m dkds analiz`, `python -m dkds on_hesapla`) ve Streamlit paneli (app.py) aynı
işlevleri kullanır; böylece panel ile komut satırı aynı sonucu üretir.
"""
from __future__ import annotations

import re
from collections.abc import Callable
from dataclasses import asdict
from pathlib import Path

from .cikarim import pdf_oku
from .models import Bulgu, CikarimSonucu

Ilerleme = Callable[[float, str], None]  # (0-1 arası oran, aşama adı)


def sinifi_dosya_adindan_bul(yol: Path) -> int | None:
    """"fen5.pdf" -> 5, "biyoloji9.pdf" -> 9; sondaki sayı 1-12 değilse ya da yoksa None."""
    eslesme = re.search(r"(\d{1,2})$", Path(yol).stem)
    if eslesme and 1 <= int(eslesme.group(1)) <= 12:
        return int(eslesme.group(1))
    return None


def analiz_calistir(sonuc: CikarimSonucu, sinif: int | None, ilerleme: Ilerleme | None = None):
    """Üç analizörü çalıştırır; (bulgular, okunabilirlik sonucu ya da None, tutarlılık sonucu) döndürür."""
    from .analiz.okunabilirlik import OkunabilirlikAnalizoru
    from .analiz.tutarlilik import TutarlilikAnalizoru
    from .analiz.yazim import YazimAnalizoru  # zeyrek yüklemesi yalnızca analizde

    def bildir(oran: float, ad: str) -> None:
        if ilerleme:
            ilerleme(oran, ad)

    bildir(0.35, "Yazım analizi (morfolojik kelime denetimi)")
    bulgular: list[Bulgu] = YazimAnalizoru().analiz_et(sonuc.paragraflar)
    okunabilirlik = None
    if sinif:
        bildir(0.75, "Okunabilirlik analizi")
        okunabilirlik = OkunabilirlikAnalizoru(sinif).incele(sonuc.paragraflar)
        bulgular += okunabilirlik.bulgular
    bildir(0.9, "Tutarlılık analizi")
    tutarlilik = TutarlilikAnalizoru().incele(sonuc.paragraflar)
    bulgular += tutarlilik.bulgular
    return bulgular, okunabilirlik, tutarlilik


def analiz_kaydi(sonuc: CikarimSonucu, bulgular: list[Bulgu], okunabilirlik, tutarlilik, sinif: int | None) -> dict:
    """Analiz sonucunun JSON'a yazılan biçimi (her bulguya paragrafın türü de eklenir)."""
    tur = {(p.sayfa, p.paragraf): p.tur for p in sonuc.paragraflar}
    kayit = {
        "kaynak": sonuc.kaynak, "sinif": sinif, "sayfa_sayisi": sonuc.sayfa_sayisi, "uyarilar": sonuc.uyarilar,
        "bulgular": [{**asdict(b), "paragraf_turu": tur.get((b.sayfa, b.paragraf), "")} for b in bulgular],
    }
    if okunabilirlik:
        kayit["okunabilirlik_ozeti"] = okunabilirlik.ozet
    kayit["tutarlilik_ozeti"] = tutarlilik.ozet
    kayit["tutarlilik_belirsiz"] = [x.sozluk() for x in tutarlilik.belirsizler]
    return kayit


def kitabi_analiz_et(pdf: Path, sinif: int | None, ocr: bool = True, ilerleme: Ilerleme | None = None) -> dict:
    """PDF'i baştan sona analiz eder ve kaydı (sözlük) döndürür."""
    if ilerleme:
        ilerleme(0.02, "PDF'ten metin çıkarılıyor")
    sonuc = pdf_oku(Path(pdf), ocr=ocr)
    bulgular, okunabilirlik, tutarlilik = analiz_calistir(sonuc, sinif, ilerleme)
    if ilerleme:
        ilerleme(1.0, "Tamamlandı")
    return analiz_kaydi(sonuc, bulgular, okunabilirlik, tutarlilik, sinif)
