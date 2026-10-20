"""Komut satırı.

    python -m dkds <pdf> [-o cikti.json] [--ocr-kapali]      metin çıkarma
    python -m dkds analiz <pdf> [-o bulgular.json]           yazım analizi
"""
from __future__ import annotations

import argparse
import json
import sys
from collections import Counter
from dataclasses import asdict
from pathlib import Path

from .cikarim import pdf_oku


def cikar(argumanlar: list[str]) -> int:
    ayrac = argparse.ArgumentParser(
        prog="dkds", description="DKDS – PDF'ten sayfa ve paragraf bilgisiyle metin çıkarır."
    )
    ayrac.add_argument("pdf", type=Path, help="İncelenecek PDF dosyası")
    ayrac.add_argument("-o", "--cikti", type=Path, help="Sonucun yazılacağı JSON dosyası")
    ayrac.add_argument("--ocr-kapali", action="store_true", help="Taranmış sayfalarda OCR yapma")
    ayrac.add_argument("--ornek", type=int, default=3, help="Ekrana basılacak örnek paragraf sayısı")
    arg = ayrac.parse_args(argumanlar)

    if not arg.pdf.exists():
        print(f"Dosya bulunamadı: {arg.pdf}", file=sys.stderr)
        return 1

    sonuc = pdf_oku(arg.pdf, ocr=not arg.ocr_kapali)

    cikti = arg.cikti or Path("cikti") / f"{arg.pdf.stem}.json"
    _json_yaz(cikti, sonuc.sozluk())

    ocr_sayisi = sum(1 for p in sonuc.paragraflar if p.ocr)
    print(f"Kaynak       : {sonuc.kaynak}")
    print(f"Sayfa sayısı : {sonuc.sayfa_sayisi}")
    print(f"Paragraf     : {len(sonuc.paragraflar)} (OCR ile okunan: {ocr_sayisi})")
    _uyarilari_yaz(sonuc.uyarilar)

    if arg.ornek and sonuc.paragraflar:
        print("\nÖrnek paragraflar:")
        for p in sonuc.paragraflar[: arg.ornek]:
            kisa = p.metin if len(p.metin) <= 200 else p.metin[:200] + "…"
            print(f"  [s.{p.sayfa} ¶{p.paragraf}] {kisa}")

    print(f"\nSonuç kaydedildi: {cikti}")
    return 0


def analiz(argumanlar: list[str]) -> int:
    from .analiz.yazim import YazimAnalizoru  # zeyrek yüklemesi yalnızca analizde

    ayrac = argparse.ArgumentParser(prog="dkds analiz", description="DKDS – PDF'te yazım analizi yapar.")
    ayrac.add_argument("pdf", type=Path, help="İncelenecek PDF dosyası")
    ayrac.add_argument("-o", "--cikti", type=Path, help="Bulguların yazılacağı JSON dosyası")
    ayrac.add_argument("--ocr-kapali", action="store_true", help="Taranmış sayfalarda OCR yapma")
    arg = ayrac.parse_args(argumanlar)

    if not arg.pdf.exists():
        print(f"Dosya bulunamadı: {arg.pdf}", file=sys.stderr)
        return 1

    sonuc = pdf_oku(arg.pdf, ocr=not arg.ocr_kapali)
    bulgular = YazimAnalizoru().analiz_et(sonuc.paragraflar)

    cikti = arg.cikti or Path("cikti") / f"{arg.pdf.stem}_bulgular.json"
    _json_yaz(cikti, {
        "kaynak": sonuc.kaynak,
        "uyarilar": sonuc.uyarilar,
        "bulgular": [asdict(b) for b in bulgular],
    })

    paragraf_turu = {(p.sayfa, p.paragraf): p.tur for p in sonuc.paragraflar}
    print(f"Kaynak  : {sonuc.kaynak}")
    print(f"Bulgu   : {len(bulgular)}")
    _ozet_yaz("Kriter", Counter(b.kriter for b in bulgular))
    _ozet_yaz("Bulgu türü", Counter(b.tur for b in bulgular))
    _ozet_yaz("Paragraf türü", Counter(paragraf_turu[(b.sayfa, b.paragraf)] for b in bulgular))
    _uyarilari_yaz(sonuc.uyarilar)
    print(f"\nBulgular kaydedildi: {cikti}")
    return 0


def _json_yaz(yol: Path, veri) -> None:
    yol.parent.mkdir(parents=True, exist_ok=True)
    yol.write_text(json.dumps(veri, ensure_ascii=False, indent=2), encoding="utf-8")


def _ozet_yaz(baslik: str, sayac: Counter) -> None:
    print(f"\n{baslik}:")
    for ad, sayi in sayac.most_common():
        print(f"  {ad:<26} {sayi:>5}")


def _uyarilari_yaz(uyarilar: list[str]) -> None:
    print(f"Uyarı        : {len(uyarilar)}")
    for u in uyarilar[:10]:
        print(f"  - {u}")
    if len(uyarilar) > 10:
        print(f"  ... ve {len(uyarilar) - 10} uyarı daha (JSON dosyasında)")


def main() -> int:
    argumanlar = sys.argv[1:]
    if argumanlar and argumanlar[0] == "analiz":
        return analiz(argumanlar[1:])
    return cikar(argumanlar)


if __name__ == "__main__":
    sys.exit(main())
