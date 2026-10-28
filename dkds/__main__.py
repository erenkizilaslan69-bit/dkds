"""Komut satırı.

    python -m dkds <pdf> [-o cikti.json] [--ocr-kapali]      metin çıkarma
    python -m dkds analiz <pdf> [--sinif 5] [-o bulgular.json]
                                                             yazım analizi; --sinif verilirse
                                                             okunabilirlik analizi de yapılır
    python -m dkds referans -k 3 <pdf> -k 5 <pdf> ... [-o referans.json]
                                                             sınıf başına okunabilirlik referansı üretir
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
    from .analiz.okunabilirlik import OkunabilirlikAnalizoru
    from .analiz.yazim import YazimAnalizoru  # zeyrek yüklemesi yalnızca analizde

    ayrac = argparse.ArgumentParser(
        prog="dkds analiz", description="DKDS – PDF'te yazım ve okunabilirlik analizi yapar."
    )
    ayrac.add_argument("pdf", type=Path, help="İncelenecek PDF dosyası")
    ayrac.add_argument("-o", "--cikti", type=Path, help="Bulguların yazılacağı JSON dosyası")
    ayrac.add_argument("--ocr-kapali", action="store_true", help="Taranmış sayfalarda OCR yapma")
    ayrac.add_argument("--sinif", type=int, choices=range(1, 13), metavar="1-12",
                       help="Kitabın sınıf düzeyi; verilirse okunabilirlik analizi de yapılır")
    arg = ayrac.parse_args(argumanlar)

    if not arg.pdf.exists():
        print(f"Dosya bulunamadı: {arg.pdf}", file=sys.stderr)
        return 1

    sonuc = pdf_oku(arg.pdf, ocr=not arg.ocr_kapali)
    bulgular = YazimAnalizoru().analiz_et(sonuc.paragraflar)

    okunabilirlik = None
    if arg.sinif:
        okunabilirlik = OkunabilirlikAnalizoru(arg.sinif).incele(sonuc.paragraflar)
        bulgular += okunabilirlik.bulgular

    cikti = arg.cikti or Path("cikti") / f"{arg.pdf.stem}_bulgular.json"
    kayit = {"kaynak": sonuc.kaynak, "uyarilar": sonuc.uyarilar, "bulgular": [asdict(b) for b in bulgular]}
    if okunabilirlik:
        kayit["okunabilirlik_ozeti"] = okunabilirlik.ozet
    _json_yaz(cikti, kayit)

    paragraf_turu = {(p.sayfa, p.paragraf): p.tur for p in sonuc.paragraflar}
    print(f"Kaynak  : {sonuc.kaynak}")
    print(f"Bulgu   : {len(bulgular)}")
    _ozet_yaz("Kriter", Counter(b.kriter for b in bulgular))
    _ozet_yaz("Bulgu türü", Counter(b.tur for b in bulgular))
    _ozet_yaz("Paragraf türü", Counter(paragraf_turu[(b.sayfa, b.paragraf)] for b in bulgular))
    if okunabilirlik:
        _okunabilirlik_ozeti_yaz(okunabilirlik.ozet)
    else:
        print("\nOkunabilirlik analizi için kitabın sınıfını verin: --sinif 5")
    _uyarilari_yaz(sonuc.uyarilar)
    print(f"\nBulgular kaydedildi: {cikti}")
    return 0


def _okunabilirlik_ozeti_yaz(ozet: dict) -> None:
    from .analiz.okunabilirlik import sayi_yaz

    etiketler = {"cumle_isaretsiz": "cümle sonu işareti olmayan paragraf", "sozluk": "sözlükçe paragrafı",
                 "kisa_sayfa": "sayfada 40 kelimelik gövde metni olmayan paragraf"}
    print(f"\nOkunabilirlik özeti ({ozet['sinif']}. sınıf kitabı):")
    print(f"  Değerlendirilen : {ozet['birim_sayisi']} metin birimi, {ozet['kelime']} kelime, {ozet['cumle']} cümle")
    if ozet["atlanan"]:
        atlanan = ", ".join(f"{etiketler.get(ad, ad)}: {sayi}" for ad, sayi in ozet["atlanan"].items())
        print(f"  Atlanan         : {atlanan}")
    if "atesman" not in ozet:
        return
    print(f"  Ateşman         : {sayi_yaz(ozet['atesman']['puan'])} ({ozet['atesman']['duzey']} düzeyi)")
    print(f"  Bezirci-Yılmaz  : {sayi_yaz(ozet['bezirci_yilmaz']['puan'], 2)} ({ozet['bezirci_yilmaz']['duzey']})")
    print(f"  Ort. cümle      : {sayi_yaz(ozet['ortalama_cumle_uzunlugu'])} kelime, "
          f"kelime başına {sayi_yaz(ozet['hece_kelime'], 2)} hece")
    d = ozet["atesman_dagilimi"]
    print(f"  Birim Ateşman   : medyan {sayi_yaz(d['medyan'])}, ortalama {sayi_yaz(d['ortalama'])} "
          f"(std {sayi_yaz(d['std'])}), %10-%90 aralığı {sayi_yaz(d['p10'])}–{sayi_yaz(d['p90'])}")
    print(f"  İşaretlenen     : {ozet['isaretlenen_birim']} / {ozet['birim_sayisi']} birim "
          f"(%{ozet['isaretlenen_oran'] * 100:.0f})")
    if ozet["isaretlenen_oran"] > 0.5:
        print(f"  ! Uyarı: birimlerin yarısından fazlası işaretlendi; ortanca paragraf bile kitap düzeyinin "
              f"{ozet['medyan_kademe_farki']} kademe üstünde. Sabit kademe eşiği bu kitapta ayırt edici değil; "
              "sınıf için referans dağılımla karşılaştırma gerekir.")
    print(f"  En zor {len(ozet['en_zor_paragraflar'])} paragraf (Ateşman puanı düşük = zor):")
    for sira, p in enumerate(ozet["en_zor_paragraflar"], start=1):
        paragraf = f"¶{p['paragraflar'][0]}" + (f"–{p['paragraflar'][-1]}" if len(p["paragraflar"]) > 1 else "")
        print(f"   {sira:>2}. s.{p['sayfa']} {paragraf}  Ateşman {sayi_yaz(p['atesman'])} ({p['atesman_duzeyi']}), "
              f"B-Y {sayi_yaz(p['bezirci_yilmaz'])}, {p['kelime']} kelime, cümle {sayi_yaz(p['ortalama_cumle_uzunlugu'])}")
        print(f"       {p['metin']}")


def referans(argumanlar: list[str]) -> int:
    from .analiz.okunabilirlik import OLCUM_SURUMU, birimleri_olustur
    from .analiz.referans import VARSAYILAN_YOL, SinifVerisi, referans_kaydet, referans_olustur

    ayrac = argparse.ArgumentParser(
        prog="dkds referans",
        description="DKDS – kitaplardan sınıf başına okunabilirlik referans tablosu (referans.json) üretir.",
    )
    ayrac.add_argument("-k", "--kitap", nargs=2, action="append", required=True, metavar=("SINIF", "PDF"),
                       help="Bir kitabın sınıfı ve PDF'i; her kitap için tekrarlanır (aynı sınıfa birden çok kitap verilebilir)")
    ayrac.add_argument("-o", "--cikti", type=Path, default=VARSAYILAN_YOL, help=f"Varsayılan: {VARSAYILAN_YOL}")
    ayrac.add_argument("--ocr-kapali", action="store_true", help="Taranmış sayfalarda OCR yapma")
    arg = ayrac.parse_args(argumanlar)

    veriler: dict[int, SinifVerisi] = {}
    for sinif_metni, pdf in arg.kitap:
        if not sinif_metni.isdigit() or not 1 <= int(sinif_metni) <= 12:
            print(f"Geçersiz sınıf: {sinif_metni} (1-12 arası olmalı)", file=sys.stderr)
            return 1
        if not Path(pdf).exists():
            print(f"Dosya bulunamadı: {pdf}", file=sys.stderr)
            return 1
        sonuc = pdf_oku(pdf, ocr=not arg.ocr_kapali)
        birimler, _ = birimleri_olustur(sonuc.paragraflar)
        veri = veriler.setdefault(int(sinif_metni), SinifVerisi())
        for b in birimler:
            if b.metrikler.hazir:
                veri.atesman.append(b.metrikler.atesman)
                veri.bezirci_yilmaz.append(b.metrikler.bezirci_yilmaz)
        veri.kitaplar.append(Path(pdf).name)
        print(f"  {sinif_metni}. sınıf: {Path(pdf).name} -> {len(birimler)} birim")

    aciklama = (
        "Sınıf başına paragraf (birim) bazında Ateşman ve Bezirci-Yılmaz puanlarının ortancası, %10 ve %90 "
        "dilimleri. Ateşman'da düşük puan, Bezirci-Yılmaz'da yüksek puan zordur. Ara_deger=true olan sınıflar "
        "komşu sınıflardan doğrusal ara değerdir. olcum_surumu, referansı üreten okunabilirlik.py ölçümünün "
        "sürümüdür; ölçüm değişirse referans yeniden üretilmelidir. Üretim: python -m dkds referans -k SINIF PDF ..."
    )
    ref = referans_olustur(veriler, OLCUM_SURUMU, aciklama)
    referans_kaydet(ref, arg.cikti)

    print(f"\n{'sınıf':>6} {'birim':>6}  {'Ateşman %10':>11} {'ortanca':>8} {'%90':>6}   {'B-Y %10':>7} {'ortanca':>8} {'%90':>6}")
    for no, r in ref.siniflar.items():
        etiket = "ara" if r.ara_deger else str(r.birim_sayisi)
        print(f"{no:>6} {etiket:>6}  {r.atesman.p10:>11.1f} {r.atesman.ortanca:>8.1f} {r.atesman.p90:>6.1f}   "
              f"{r.bezirci_yilmaz.p10:>7.1f} {r.bezirci_yilmaz.ortanca:>8.1f} {r.bezirci_yilmaz.p90:>6.1f}")
    print(f"\nReferans kaydedildi: {arg.cikti}")
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
    if argumanlar and argumanlar[0] == "referans":
        return referans(argumanlar[1:])
    return cikar(argumanlar)


if __name__ == "__main__":
    sys.exit(main())
