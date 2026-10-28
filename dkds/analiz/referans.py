"""Sınıf başına okunabilirlik referans tablosu.

Ateşman'ın puan → sınıf tablosu Türkçe ders kitabı metnini sistematik olarak çok zor
gösterir (5. sınıf kitaplarının ortanca paragrafı bile "11-12. sınıf / lisans" çıkar).
Bu yüzden bir paragraf sabit tabloyla değil, MEB kitaplarından çıkarılan sınıf
dağılımıyla karşılaştırılır: her sınıf için paragraf (birim) bazında Ateşman ve
Bezirci-Yılmaz puanlarının ortancası, %10 ve %90 dilimleri tutulur (referans.json).

Referansı olan sınıflar kitap sağlanan sınıflardır (ör. 3, 5, 7, 9); aradaki sınıflar
(4, 6, 8) komşu sınıflardan doğrusal ara değerle bulunur. Referans kapsamı dışındaki
sınıflar için tablo yoktur (sinif() None döner).

Bu modül okunabilirlik.py'yi içe aktarmaz (karşılıklı bağımlılık olmasın diye); puan
listeleriyle çalışır.
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path

VARSAYILAN_YOL = Path(__file__).with_name("referans.json")
SURUM = 1  # dosya biçimi sürümü


def yuzdelik(degerler: list[float], oran: float) -> float:
    """Doğrusal ara değerli yüzdelik (0 ≤ oran ≤ 1); sıralı olması gerekmez."""
    sirali = sorted(degerler)
    konum = (len(sirali) - 1) * oran
    alt = int(konum)
    ust = min(alt + 1, len(sirali) - 1)
    return sirali[alt] + (sirali[ust] - sirali[alt]) * (konum - alt)


@dataclass
class Dagilim:
    """Bir puanın dağılımı: ortanca, %10 ve %90 dilimleri."""

    ortanca: float
    p10: float
    p90: float

    @classmethod
    def hesapla(cls, degerler: list[float]) -> Dagilim:
        return cls(yuzdelik(degerler, 0.5), yuzdelik(degerler, 0.1), yuzdelik(degerler, 0.9))

    def ara_deger(self, diger: Dagilim, oran: float) -> Dagilim:
        """self ile diger arasında doğrusal ara değer (oran 0 → self, 1 → diger)."""
        def al(a: float, b: float) -> float:
            return a + (b - a) * oran
        return Dagilim(al(self.ortanca, diger.ortanca), al(self.p10, diger.p10), al(self.p90, diger.p90))


@dataclass
class SinifVerisi:
    """Referans üretmek için bir sınıfın ham girdisi: birim puanları ve kitap adları."""

    atesman: list[float] = field(default_factory=list)
    bezirci_yilmaz: list[float] = field(default_factory=list)
    kitaplar: list[str] = field(default_factory=list)


@dataclass
class SinifReferansi:
    sinif: int
    atesman: Dagilim
    bezirci_yilmaz: Dagilim
    ara_deger: bool = False  # True: komşu sınıflardan doğrusal ara değerle bulundu
    birim_sayisi: int | None = None
    kitaplar: list[str] = field(default_factory=list)
    kaynak_siniflar: list[int] = field(default_factory=list)  # ara değerin dayandığı sınıflar


@dataclass
class Referans:
    siniflar: dict[int, SinifReferansi] = field(default_factory=dict)
    olcum_surumu: int = 0  # referansı üreten ölçüm kodunun sürümü (okunabilirlik.OLCUM_SURUMU)
    aciklama: str = ""

    def sinif(self, sinif: int) -> SinifReferansi | None:
        return self.siniflar.get(sinif)

    @property
    def kapsam(self) -> tuple[int, int] | None:
        return (min(self.siniflar), max(self.siniflar)) if self.siniflar else None

    def tipik_duzey(self, atesman: float) -> tuple[int, bool]:
        """Ateşman puanının hangi sınıf kitaplarının tipik düzeyinde olduğunu bulur.

        Puanın kendi %10–%90 aralığına girdiği sınıflar arasından ortancası puana en yakın
        olan seçilir. Hiçbir sınıfın aralığına girmiyorsa (False) puan tablodaki tüm
        sınıflardan zordur ya da kolaydır; en yakın uç sınıf döner.
        Dönüş: (sınıf, aralıkta_mı)
        """
        adaylar = [r for r in self.siniflar.values() if r.atesman.p10 <= atesman <= r.atesman.p90]
        if adaylar:
            return min(adaylar, key=lambda r: abs(r.atesman.ortanca - atesman)).sinif, True
        en_zor = min(self.siniflar.values(), key=lambda r: r.atesman.p10)
        en_kolay = max(self.siniflar.values(), key=lambda r: r.atesman.p90)
        return (en_zor.sinif if atesman < en_zor.atesman.p10 else en_kolay.sinif), False

    # ------------------------------------------------------------------ JSON

    def sozluk(self) -> dict:
        def dag(d: Dagilim) -> dict:
            return {"ortanca": round(d.ortanca, 3), "p10": round(d.p10, 3), "p90": round(d.p90, 3)}

        siniflar = {}
        for no in sorted(self.siniflar):
            r = self.siniflar[no]
            kayit = {"ara_deger": r.ara_deger, "atesman": dag(r.atesman), "bezirci_yilmaz": dag(r.bezirci_yilmaz)}
            if r.ara_deger:
                kayit["kaynak_siniflar"] = r.kaynak_siniflar
            else:
                kayit.update(birim_sayisi=r.birim_sayisi, kitaplar=r.kitaplar)
            siniflar[str(no)] = kayit
        return {"surum": SURUM, "olcum_surumu": self.olcum_surumu, "aciklama": self.aciklama, "siniflar": siniflar}

    @classmethod
    def sozlukten(cls, veri: dict) -> Referans:
        if veri.get("surum") != SURUM:
            raise ValueError(f"desteklenmeyen referans dosyası sürümü: {veri.get('surum')!r}")

        def dag(d: dict) -> Dagilim:
            return Dagilim(d["ortanca"], d["p10"], d["p90"])

        siniflar = {}
        for no, k in veri["siniflar"].items():
            siniflar[int(no)] = SinifReferansi(
                sinif=int(no), atesman=dag(k["atesman"]), bezirci_yilmaz=dag(k["bezirci_yilmaz"]),
                ara_deger=k.get("ara_deger", False), birim_sayisi=k.get("birim_sayisi"),
                kitaplar=k.get("kitaplar", []), kaynak_siniflar=k.get("kaynak_siniflar", []),
            )
        return cls(siniflar=siniflar, olcum_surumu=veri.get("olcum_surumu", 0), aciklama=veri.get("aciklama", ""))


def referans_olustur(veriler: dict[int, SinifVerisi], olcum_surumu: int, aciklama: str = "") -> Referans:
    """Sınıf başına ham puanlardan referans üretir; veri olmayan ara sınıfları doğrusal ara değerle doldurur."""
    if not veriler:
        raise ValueError("en az bir sınıf için veri gerekli")
    siniflar: dict[int, SinifReferansi] = {}
    for no, v in sorted(veriler.items()):
        if not v.atesman or len(v.atesman) != len(v.bezirci_yilmaz):
            raise ValueError(f"{no}. sınıf için puan listesi boş ya da tutarsız")
        siniflar[no] = SinifReferansi(
            sinif=no, atesman=Dagilim.hesapla(v.atesman), bezirci_yilmaz=Dagilim.hesapla(v.bezirci_yilmaz),
            birim_sayisi=len(v.atesman), kitaplar=sorted(v.kitaplar),
        )
    olculenler = sorted(siniflar)
    for alt, ust in zip(olculenler, olculenler[1:]):
        for no in range(alt + 1, ust):
            oran = (no - alt) / (ust - alt)
            siniflar[no] = SinifReferansi(
                sinif=no, ara_deger=True, kaynak_siniflar=[alt, ust],
                atesman=siniflar[alt].atesman.ara_deger(siniflar[ust].atesman, oran),
                bezirci_yilmaz=siniflar[alt].bezirci_yilmaz.ara_deger(siniflar[ust].bezirci_yilmaz, oran),
            )
    return Referans(siniflar=dict(sorted(siniflar.items())), olcum_surumu=olcum_surumu, aciklama=aciklama)


def referans_yukle(yol: Path | str = VARSAYILAN_YOL) -> Referans:
    return Referans.sozlukten(json.loads(Path(yol).read_text(encoding="utf-8")))


def referans_kaydet(referans: Referans, yol: Path | str = VARSAYILAN_YOL) -> None:
    Path(yol).write_text(json.dumps(referans.sozluk(), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
