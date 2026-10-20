"""Komut satırı: python -m dkds <pdf> [-o cikti.json] [--ocr-kapali]"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from .cikarim import pdf_oku


def main() -> int:
    ayrac = argparse.ArgumentParser(
        prog="dkds", description="DKDS – PDF'ten sayfa ve paragraf bilgisiyle metin çıkarır."
    )
    ayrac.add_argument("pdf", type=Path, help="İncelenecek PDF dosyası")
    ayrac.add_argument("-o", "--cikti", type=Path, help="Sonucun yazılacağı JSON dosyası")
    ayrac.add_argument("--ocr-kapali", action="store_true", help="Taranmış sayfalarda OCR yapma")
    ayrac.add_argument("--ornek", type=int, default=3, help="Ekrana basılacak örnek paragraf sayısı")
    arg = ayrac.parse_args()

    if not arg.pdf.exists():
        print(f"Dosya bulunamadı: {arg.pdf}", file=sys.stderr)
        return 1

    sonuc = pdf_oku(arg.pdf, ocr=not arg.ocr_kapali)

    cikti = arg.cikti or Path("cikti") / f"{arg.pdf.stem}.json"
    cikti.parent.mkdir(parents=True, exist_ok=True)
    cikti.write_text(json.dumps(sonuc.sozluk(), ensure_ascii=False, indent=2), encoding="utf-8")

    ocr_sayisi = sum(1 for p in sonuc.paragraflar if p.ocr)
    print(f"Kaynak       : {sonuc.kaynak}")
    print(f"Sayfa sayısı : {sonuc.sayfa_sayisi}")
    print(f"Paragraf     : {len(sonuc.paragraflar)} (OCR ile okunan: {ocr_sayisi})")
    print(f"Uyarı        : {len(sonuc.uyarilar)}")
    for u in sonuc.uyarilar[:10]:
        print(f"  - {u}")
    if len(sonuc.uyarilar) > 10:
        print(f"  ... ve {len(sonuc.uyarilar) - 10} uyarı daha (JSON dosyasında)")

    if arg.ornek and sonuc.paragraflar:
        print("\nÖrnek paragraflar:")
        for p in sonuc.paragraflar[: arg.ornek]:
            kisa = p.metin if len(p.metin) <= 200 else p.metin[:200] + "…"
            print(f"  [s.{p.sayfa} ¶{p.paragraf}] {kisa}")

    print(f"\nSonuç kaydedildi: {cikti}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
