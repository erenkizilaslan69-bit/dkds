"""DKDS veri modelleri.

Tüm modüller bu ortak yapıları kullanır. Böylece metin çıkarma, analizörler
ve arayüz birbirinden bağımsız geliştirilebilir.
"""
from __future__ import annotations

from dataclasses import asdict, dataclass, field

# (x0, y0, x1, y1) — PDF sayfası üzerindeki dikdörtgen, punto cinsinden
Konum = tuple[float, float, float, float]


@dataclass
class Blok:
    """PDF kütüphanesinden gelen ham metin bloğu (henüz paragraf değil)."""

    sayfa: int
    x0: float
    y0: float
    x1: float
    y1: float
    metin: str

    @property
    def satir_sayisi(self) -> int:
        return max(1, self.metin.strip("\n").count("\n") + 1)

    @property
    def satir_yuksekligi(self) -> float:
        return (self.y1 - self.y0) / self.satir_sayisi

    @property
    def konum(self) -> Konum:
        return (self.x0, self.y0, self.x1, self.y1)


@dataclass
class Paragraf:
    """Temizlenmiş, numaralandırılmış paragraf. Analizörlerin girdisi."""

    sayfa: int
    paragraf: int
    metin: str
    konum: Konum
    ocr: bool = False  # True ise metin OCR ile okundu, karakter hataları olabilir
    tur: str = "govde"  # baslik, govde, soru, liste, etiket (bkz. siniflandirma.py)


@dataclass
class Bulgu:
    """Bir analizörün tespit ettiği sorun. Üç kriter de bu formatı kullanır."""

    sayfa: int
    paragraf: int
    kriter: str  # "yazim", "okunabilirlik", "tutarlilik"
    sorunlu_metin: str
    aciklama: str
    guven: float  # 0.0 – 1.0
    oneri: str | None = None
    konum: Konum | None = None


@dataclass
class CikarimSonucu:
    """Bir PDF'in metin çıkarma sonucu."""

    kaynak: str
    sayfa_sayisi: int
    paragraflar: list[Paragraf] = field(default_factory=list)
    uyarilar: list[str] = field(default_factory=list)

    def sozluk(self) -> dict:
        return asdict(self)
